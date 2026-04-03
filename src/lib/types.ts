export type RunState =
  | 'queued'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type StepState =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'blocked'
  | 'cancelled';

export interface StepRecord {
  id: string;
  runId: string;
  title: string;
  goal: string;
  groupIndex: number;
  stepIndex: number;
  toolName: string | null;
  verificationTarget: string | null;
  state: StepState;
  startedAt: string | null;
  completedAt: string | null;
  updatedAt: string;
}

export interface EventRecord {
  id: number;
  runId: string;
  level: 'debug' | 'info' | 'warn' | 'error';
  eventType: string;
  message: string;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface ObservationRecord {
  id: number;
  runId: string;
  kind: string;
  content: string;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface ArtifactRecord {
  id: number;
  runId: string;
  kind: string;
  label: string;
  path: string;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface ApprovalRequest {
  groupIndex: number;
  reason: string;
}

export interface RunRecord {
  id: string;
  prompt: string;
  state: RunState;
  summary: string | null;
  error: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  completedAt: string | null;
  pendingApproval: ApprovalRequest | null;
  steps: StepRecord[];
  events: EventRecord[];
  observations: ObservationRecord[];
  artifacts: ArtifactRecord[];
}

export interface AppSnapshot {
  workerStatus: 'offline' | 'ready' | 'busy' | 'error';
  selectedRunId: string | null;
  runs: RunRecord[];
}

export interface StartRunInput {
  prompt: string;
  apiKey?: string;
}
