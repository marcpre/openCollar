import type { RunRecord } from '../lib/types';

interface RunDetailsProps {
  run: RunRecord | null;
  onCancel: (runId: string) => Promise<void>;
}

export function RunDetails({ run, onCancel }: RunDetailsProps) {
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
            </div>
            <span className={`badge badge--${run.state}`}>{run.state}</span>
          </div>

          <div className="toolbar-row">
            {run.state !== 'completed' && run.state !== 'cancelled' ? (
              <button type="button" className="button button--danger" onClick={() => onCancel(run.id)}>
                Stop
              </button>
            ) : null}
          </div>
        </div>

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
