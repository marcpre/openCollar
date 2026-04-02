import { convertFileSrc, invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { EMPTY_SNAPSHOT } from './mock';
import type { AppSnapshot, Mode, ModelConfig, StartRunInput } from './types';

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

export async function startRun(input: StartRunInput): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  await invoke('start_run', { input });
}

export async function approveStepGroup(runId: string, groupIndex: number): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  await invoke('approve_step_group', { runId, groupIndex });
}

export async function pauseRun(runId: string): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  await invoke('pause_run', { runId });
}

export async function resumeRun(runId: string): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  await invoke('resume_run', { runId });
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

export const AVAILABLE_MODES: Mode[] = ['observe', 'assist', 'auto'];
export const GEMINI_MODELS: ModelConfig[] = [
  { provider: 'deterministic', modelName: 'deterministic-mvp' },
  { provider: 'gemini', modelName: 'gemini-2.5-flash' },
  { provider: 'gemini', modelName: 'gemini-2.5-pro' },
];
