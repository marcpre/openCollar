import { convertFileSrc, invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { EMPTY_SNAPSHOT } from './mock';
import type { AppSnapshot, StartRunInput } from './types';

const STATE_EVENT = 'open-collar://state';

function isTauriRuntime() {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export async function getAppSnapshot(): Promise<AppSnapshot> {
  if (!isTauriRuntime()) {
    return EMPTY_SNAPSHOT;
  }

  return invoke<AppSnapshot>('get_app_snapshot');
}

export async function startRun(input: StartRunInput): Promise<string> {
  if (!isTauriRuntime()) {
    return 'mock-run';
  }

  return invoke<string>('start_run', { input });
}

export async function cancelRun(runId: string): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  await invoke('cancel_run', { runId });
}

export async function listenForSnapshots(
  callback: (snapshot: AppSnapshot) => void,
): Promise<() => void> {
  if (!isTauriRuntime()) {
    return () => undefined;
  }

  const unlisten = await listen<AppSnapshot>(STATE_EVENT, (event) => {
    callback(event.payload);
  });

  return unlisten;
}

export function toAssetUrl(path: string): string {
  if (!path) {
    return '';
  }

  return isTauriRuntime() ? convertFileSrc(path) : path;
}
