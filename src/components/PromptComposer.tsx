import { useEffect, useMemo, useRef, useState } from 'react';
import { AVAILABLE_MODES } from '../lib/tauri';
import type { EventRecord, Mode, ModelConfig, ModelProvider, RunRecord } from '../lib/types';

interface PromptComposerProps {
  run: RunRecord | null;
  geminiApiKey: string;
  onStartRun: (prompt: string, mode: Mode, modelConfig: ModelConfig) => Promise<void>;
  onApprove: (runId: string, groupIndex: number) => Promise<void>;
  onPause: (runId: string) => Promise<void>;
  onResume: (runId: string) => Promise<void>;
  onCancel: (runId: string) => Promise<void>;
}

const DEFAULT_PROMPT = 'Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt.';

function getDisplayRole(event: EventRecord) {
  if (event.eventType === 'prompt') {
    return 'You';
  }
  if (event.eventType === 'planner_summary' || event.eventType === 'approval_requested') {
    return 'Model';
  }
  return 'System';
}

function getDisplayMessage(event: EventRecord) {
  if (event.eventType === 'run_enqueued') {
    return 'Run queued and sent to the worker.';
  }
  if (event.eventType === 'planner_summary') {
    return event.message;
  }
  if (event.eventType === 'tool_call') {
    return `Action: ${event.message}`;
  }
  if (event.eventType === 'tool_result') {
    return event.message;
  }
  return event.message;
}

export function PromptComposer({
  run,
  geminiApiKey,
  onStartRun,
  onApprove,
  onPause,
  onResume,
  onCancel,
}: PromptComposerProps) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [mode, setMode] = useState<Mode>('assist');
  const [provider, setProvider] = useState<ModelProvider>('deterministic');
  const [busy, setBusy] = useState(false);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const canStart = Boolean(prompt.trim()) && (provider !== 'gemini' || Boolean(geminiApiKey.trim()));

  const transcript = useMemo(() => {
    if (!run) {
      return [];
    }

    const promptEvent: EventRecord = {
      id: -1,
      runId: run.id,
      level: 'info',
      eventType: 'prompt',
      message: run.prompt,
      payload: null,
      createdAt: run.createdAt,
    };

    return [promptEvent, ...run.events].sort(
      (left, right) => new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime(),
    );
  }, [run]);

  useEffect(() => {
    const node = feedRef.current;
    if (!node) {
      return;
    }

    node.scrollTop = node.scrollHeight;
  }, [transcript.length, run?.state, run?.pendingApproval]);

  const handleSubmit = async () => {
    if (!canStart) {
      return;
    }

    setBusy(true);
    try {
      await onStartRun(prompt.trim(), mode, {
        provider,
        modelName: provider === 'gemini' ? 'gemini-2.5-pro' : 'deterministic-mvp',
        apiKey: provider === 'gemini' ? geminiApiKey.trim() : undefined,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="chat-shell">
      {run?.pendingApproval ? (
        <section className="approval-banner">
          <div className="approval-banner__copy">
            <p className="eyebrow">Approval needed</p>
            <h2>Approve group {run.pendingApproval.groupIndex + 1}</h2>
            <p>{run.pendingApproval.reason}</p>
          </div>

          <div className="approval-options">
            <button
              type="button"
              className="approval-card approval-card--recommended"
              onClick={() => onApprove(run.id, run.pendingApproval!.groupIndex)}
            >
              <div className="approval-card__top">
                <strong>Approve and continue</strong>
                <span className="badge badge--info">Recommended</span>
              </div>
              <p>Let the model execute the next approved step group now.</p>
            </button>

            <button type="button" className="approval-card" onClick={() => onPause(run.id)}>
              <div className="approval-card__top">
                <strong>Keep it paused</strong>
              </div>
              <p>Stay in review mode and inspect the conversation before continuing.</p>
            </button>

            <button type="button" className="approval-card approval-card--danger" onClick={() => onCancel(run.id)}>
              <div className="approval-card__top">
                <strong>Stop run</strong>
              </div>
              <p>Cancel this run instead of approving the next action.</p>
            </button>
          </div>
        </section>
      ) : null}

      <div className="chat-feed" ref={feedRef}>
        {transcript.length ? (
          transcript.map((event) => (
            <article
              key={`${event.id}-${event.createdAt}`}
              className={`message message--${getDisplayRole(event).toLowerCase()}`}
            >
              <div className="message__meta">
                <strong>{getDisplayRole(event)}</strong>
                <span className="muted mono">{new Date(event.createdAt).toLocaleTimeString()}</span>
              </div>
              <p>{getDisplayMessage(event)}</p>
            </article>
          ))
        ) : (
          <div className="empty-state empty-state--chat">
            Start a run and the interaction with the model will appear here.
          </div>
        )}
      </div>

      {run?.state === 'running' ? (
        <div className="status-strip">
          <span className="badge badge--running">Running</span>
          <button type="button" className="button" onClick={() => onCancel(run.id)}>
            Stop run
          </button>
        </div>
      ) : null}

      {run?.state === 'paused' && !run.pendingApproval ? (
        <div className="status-strip">
          <span className="badge badge--paused">Paused</span>
          <button type="button" className="button" onClick={() => onResume(run.id)}>
            Resume
          </button>
          <button type="button" className="button" onClick={() => onCancel(run.id)}>
            Stop run
          </button>
        </div>
      ) : null}

      <div className="composer">
        <textarea
          className="composer__textarea"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Describe the task for the desktop agent."
        />

        <div className="composer__footer">
          <div className="composer__controls">
            <select
              className="field field--small"
              value={mode}
              onChange={(event) => setMode(event.target.value as Mode)}
            >
              {AVAILABLE_MODES.map((availableMode) => (
                <option key={availableMode} value={availableMode}>
                  {availableMode}
                </option>
              ))}
            </select>

            <select
              className="field field--medium"
              value={provider}
              onChange={(event) => setProvider(event.target.value as ModelProvider)}
            >
              <option value="deterministic">deterministic</option>
              <option value="gemini">gemini</option>
            </select>

            {provider === 'gemini' && !geminiApiKey.trim() ? (
              <span className="hint">Add your Gemini API key from the gear icon.</span>
            ) : null}
          </div>

          <button type="button" className="button button--primary" onClick={handleSubmit} disabled={busy || !canStart}>
            {busy ? 'Starting…' : 'Send'}
          </button>
        </div>
      </div>
    </section>
  );
}
