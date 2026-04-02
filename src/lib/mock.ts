import type { AppSnapshot } from './types';

export const EMPTY_SNAPSHOT: AppSnapshot = {
  workerStatus: 'offline',
  selectedRunId: null,
  runs: [],
};
