import { useEffect, useState } from 'react';
import {
  cancelRun,
  getAppSnapshot,
  listenForSnapshots,
  startRun,
} from '../lib/tauri';
import { EMPTY_SNAPSHOT } from '../lib/mock';
import type { AppSnapshot } from '../lib/types';

export function useOpenCollarApp() {
  const [snapshot, setSnapshot] = useState<AppSnapshot>(EMPTY_SNAPSHOT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const boot = async () => {
      try {
        const initial = await getAppSnapshot();
        if (mounted) {
          setSnapshot(initial);
        }
      } catch (reason) {
        if (mounted) {
          setError(reason instanceof Error ? reason.message : 'Failed to load open collar snapshot.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void boot();

    let cleanup: () => void = () => {};
    void listenForSnapshots((next) => {
      if (mounted) {
        setSnapshot(next);
      }
    }).then((unlisten) => {
      cleanup = () => {
        void unlisten();
      };
    });

    return () => {
      mounted = false;
      cleanup();
    };
  }, []);

  return {
    snapshot,
    loading,
    error,
    actions: {
      startRun: async (prompt: string, apiKey?: string) => {
        return startRun({ prompt, apiKey });
      },
      cancelRun,
    },
  };
}
