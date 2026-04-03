import { useEffect, useMemo, useRef, useState } from 'react';
import { toAssetUrl } from '../lib/tauri';
import type { ArtifactRecord, EventRecord, ObservationRecord, RunRecord, StepRecord } from '../lib/types';

interface PromptComposerProps {
  run: RunRecord | null;
  geminiApiKey: string;
  onStartRun: (prompt: string, apiKey?: string) => Promise<string>;
  onCancel: (runId: string) => Promise<void>;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  createdAt: string;
  title: string;
  body: string;
}

function getAssistantEventMessage(event: EventRecord): ChatMessage | null {
  switch (event.eventType) {
    case 'planner_summary':
      return {
        id: `event-${event.id}`,
        role: 'assistant',
        createdAt: event.createdAt,
        title: 'Plan ready',
        body: event.message,
      };
    case 'step_started':
      return {
        id: `event-${event.id}`,
        role: 'assistant',
        createdAt: event.createdAt,
        title: 'Working',
        body: event.message,
      };
    case 'step_completed':
      return {
        id: `event-${event.id}`,
        role: 'assistant',
        createdAt: event.createdAt,
        title: 'Progress',
        body: event.message,
      };
    case 'run_cancelled':
      return {
        id: `event-${event.id}`,
        role: 'assistant',
        createdAt: event.createdAt,
        title: 'Stopped',
        body: event.message,
      };
    case 'tool_error':
      return {
        id: `event-${event.id}`,
        role: 'assistant',
        createdAt: event.createdAt,
        title: 'Failed',
        body: event.message,
      };
    case 'execution_failed':
      return null;
    default:
      return null;
  }
}

function getLatestObservation(observations: ObservationRecord[]) {
  return observations[observations.length - 1] ?? null;
}

function getLatestArtifact(artifacts: ArtifactRecord[]) {
  return artifacts[artifacts.length - 1] ?? null;
}

function getActiveStep(steps: StepRecord[]) {
  return steps.find((step) => step.state === 'running') ?? steps.find((step) => step.state === 'pending') ?? null;
}

export function PromptComposer({ run, geminiApiKey, onStartRun, onCancel }: PromptComposerProps) {
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const canStart = Boolean(prompt.trim()) && Boolean(geminiApiKey.trim()) && !busy;
  const activeRun = run && !['completed', 'failed', 'cancelled'].includes(run.state);

  const transcript = useMemo(() => {
    if (!run) {
      return [];
    }

    const messages: ChatMessage[] = [
      {
        id: `prompt-${run.id}`,
        role: 'user',
        createdAt: run.createdAt,
        title: 'You',
        body: run.prompt,
      },
    ];

    for (const event of run.events) {
      const message = getAssistantEventMessage(event);
      if (message) {
        messages.push(message);
      }
    }

    if (run.state === 'completed') {
      messages.push({
        id: `terminal-${run.id}-completed`,
        role: 'assistant',
        createdAt: run.completedAt ?? run.updatedAt,
        title: 'Done',
        body: run.summary ?? 'The agent finished the task and recorded the result.',
      });
    } else if (run.state === 'failed') {
      messages.push({
        id: `terminal-${run.id}-failed`,
        role: 'assistant',
        createdAt: run.completedAt ?? run.updatedAt,
        title: 'Failed',
        body: run.error ?? run.summary ?? 'The agent could not finish the task.',
      });
    } else if (run.state === 'cancelled') {
      messages.push({
        id: `terminal-${run.id}-cancelled`,
        role: 'assistant',
        createdAt: run.completedAt ?? run.updatedAt,
        title: 'Stopped',
        body: run.summary ?? 'The run was stopped.',
      });
    }

    return messages.sort((left, right) => new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime());
  }, [run]);

  const visibleTranscript = useMemo(() => {
    if (transcript.length) {
      return transcript;
    }

    if (!pendingPrompt) {
      return [];
    }

    const timestamp = new Date().toISOString();
    return [
      {
        id: 'pending-user',
        role: 'user' as const,
        createdAt: timestamp,
        title: 'You',
        body: pendingPrompt,
      },
      {
        id: 'pending-assistant',
        role: 'assistant' as const,
        createdAt: timestamp,
        title: 'Working',
        body: 'Submitting your request to the agent...',
      },
    ];
  }, [pendingPrompt, transcript]);

  const latestObservation = useMemo(() => getLatestObservation(run?.observations ?? []), [run?.observations]);
  const latestArtifact = useMemo(() => getLatestArtifact(run?.artifacts ?? []), [run?.artifacts]);
  const activeStep = useMemo(() => getActiveStep(run?.steps ?? []), [run?.steps]);

  useEffect(() => {
    const node = feedRef.current;
    if (!node) {
      return;
    }

    node.scrollTop = node.scrollHeight;
  }, [visibleTranscript.length]);

  useEffect(() => {
    if (run) {
      setPendingPrompt(null);
    }
  }, [run]);

  const handleSubmit = async () => {
    if (!canStart) {
      return;
    }

    const nextPrompt = prompt.trim();
    setBusy(true);
    setPendingPrompt(nextPrompt);
    try {
      await onStartRun(nextPrompt, geminiApiKey.trim());
      setPrompt('');
    } catch {
      setPendingPrompt(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="agent-shell">
      <header className="agent-shell__header">
        <div>
          <p className="eyebrow">Agent Console</p>
          <h2>{run ? 'Watching the agent work' : 'Give the agent a task'}</h2>
        </div>

        {activeRun ? (
          <button type="button" className="button button--danger" onClick={() => onCancel(run.id)}>
            Stop
          </button>
        ) : null}
      </header>

      <div className="agent-shell__body">
        <section className="chat-shell">
          <div className="chat-feed" ref={feedRef}>
            {visibleTranscript.length ? (
              visibleTranscript.map((message) => (
                <article
                  key={message.id}
                  className={`message message--${message.role}`}
                >
                  <div className="message__meta">
                    <strong>{message.title}</strong>
                    <span className="muted mono">{new Date(message.createdAt).toLocaleTimeString()}</span>
                  </div>
                  <p>{message.body}</p>
                </article>
              ))
            ) : (
              <div className="empty-state empty-state--chat">
                The chat starts empty. Send a task and the agent will plan it, act on the computer, and keep you updated here.
              </div>
            )}
          </div>

          <div className="composer">
            <textarea
              className="composer__textarea"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  void handleSubmit();
                }
              }}
              placeholder="Tell the agent what to do on this computer."
            />

            <div className="composer__footer">
              {!geminiApiKey.trim() ? (
                <span className="hint">Add your Gemini API key in Settings before starting a run.</span>
              ) : (
                <span className="hint">The agent will begin automatically and you can stop it at any time.</span>
              )}

              <button type="button" className="button button--primary" onClick={handleSubmit} disabled={!canStart}>
                {busy ? 'Starting...' : 'Send'}
              </button>
            </div>
          </div>
        </section>

        <aside className="observer-panel">
          <section className="observer-card">
            <div className="observer-card__header">
              <h3>Status</h3>
              <span className={`badge badge--${run?.state ?? 'paused'}`}>{run?.state ?? 'idle'}</span>
            </div>
            <p>{run?.summary ?? 'Waiting for your first task.'}</p>
          </section>

          <section className="observer-card">
            <div className="observer-card__header">
              <h3>Current goal</h3>
            </div>
            <p>{activeStep?.goal ?? 'The agent has not started acting yet.'}</p>
            {activeStep ? <span className="muted mono">{activeStep.title}</span> : null}
          </section>

          <section className="observer-card">
            <div className="observer-card__header">
              <h3>Latest observation</h3>
            </div>
            <p>{latestObservation?.content ?? 'No observation yet.'}</p>
            {latestObservation?.kind ? <span className="muted mono">{latestObservation.kind}</span> : null}
          </section>

          <section className="observer-card observer-card--artifact">
            <div className="observer-card__header">
              <h3>Latest artifact</h3>
            </div>
            {latestArtifact ? (
              <>
                {latestArtifact.kind === 'screenshot' ? (
                  <img
                    className="observer-card__image"
                    src={toAssetUrl(latestArtifact.path)}
                    alt={latestArtifact.label}
                  />
                ) : null}
                <p>{latestArtifact.label}</p>
                <span className="muted mono">{latestArtifact.kind}</span>
              </>
            ) : (
              <p>No artifact captured yet.</p>
            )}
          </section>
        </aside>
      </div>
    </section>
  );
}
