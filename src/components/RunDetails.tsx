import type { RunRecord } from '../lib/types';

interface RunDetailsProps {
  run: RunRecord | null;
  onApprove: (runId: string, groupIndex: number) => Promise<void>;
  onPause: (runId: string) => Promise<void>;
  onResume: (runId: string) => Promise<void>;
  onCancel: (runId: string) => Promise<void>;
}

export function RunDetails({
  run,
  onApprove,
  onPause,
  onResume,
  onCancel,
}: RunDetailsProps) {
  if (!run) {
    return (
      <section className="panel">
        <div className="panel__header">
          <h2>Current run</h2>
        </div>
        <div className="panel__body">
          <div className="empty-state">
            open collar will show the active plan, grouped steps, and live logs here once a run starts.
          </div>
        </div>
      </section>
    );
  }

  const activeStep = run.steps.find((step) => step.state === 'running') ?? run.steps[0] ?? null;

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2>Current run</h2>
          <p className="meta-copy">{run.prompt}</p>
        </div>
        <span className={`badge badge--${run.state}`}>{run.state}</span>
      </div>

      <div className="panel__body details-grid">
        <div className="summary-card">
          <div className="meta-row">
            <div>
              <h3>{activeStep?.title ?? run.summary ?? 'Plan ready'}</h3>
              <p className="meta-copy">
                {run.summary ?? activeStep?.goal ?? 'Waiting for the worker to produce a plan.'}
              </p>
              <p className="meta-copy">
                Model: <span className="mono">{run.modelProvider}:{run.modelName}</span>
              </p>
            </div>
            <span className="badge">{run.mode}</span>
          </div>

          <div className="toolbar-row">
            {run.pendingApproval ? (
              <button
                type="button"
                className="button button--primary"
                onClick={() => onApprove(run.id, run.pendingApproval!.groupIndex)}
              >
                Approve group {run.pendingApproval.groupIndex + 1}
              </button>
            ) : null}

            {run.state === 'running' ? (
              <button type="button" className="button" onClick={() => onPause(run.id)}>
                Pause
              </button>
            ) : null}

            {run.state === 'paused' ? (
              <button type="button" className="button" onClick={() => onResume(run.id)}>
                Resume
              </button>
            ) : null}

            {run.state !== 'completed' && run.state !== 'cancelled' ? (
              <button type="button" className="button button--danger" onClick={() => onCancel(run.id)}>
                Stop
              </button>
            ) : null}
          </div>
        </div>

        {run.pendingApproval ? (
          <div className="approval-card">
            <h3>Approval required</h3>
            <p className="meta-copy">
              Group {run.pendingApproval.groupIndex + 1} is waiting for confirmation.
            </p>
            <p className="meta-copy">{run.pendingApproval.reason}</p>
          </div>
        ) : null}

        <div className="panel">
          <div className="panel__header">
            <h3>Plan</h3>
            <span className="badge">{run.steps.length} steps</span>
          </div>
          <div className="panel__body">
            <div className="step-list">
              {run.steps.map((step) => (
                <article key={step.id} className="step-card">
                  <div className="step-row">
                    <h4 className="step-card__title">
                      {step.groupIndex + 1}.{step.stepIndex + 1} {step.title}
                    </h4>
                    <span className={`badge badge--${step.state}`}>{step.state}</span>
                  </div>
                  <p className="step-card__detail">{step.goal}</p>
                  <div className="meta-row">
                    <span className="muted mono">{step.toolName ?? 'planner'}</span>
                    <span className="muted">{step.verificationTarget ?? 'Verification pending'}</span>
                  </div>
                </article>
              ))}
            </div>
            {run.steps.length ? null : (
              <div className="empty-state">The planner has not emitted step cards for this run yet.</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
