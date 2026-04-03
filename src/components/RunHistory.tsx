import type { RunRecord } from '../lib/types';

interface RunHistoryProps {
  runs: RunRecord[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
}

export function RunHistory({ runs, selectedRunId, onSelectRun }: RunHistoryProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Run history</h2>
        <span className="badge">{runs.length}</span>
      </div>
      <div className="panel__body run-list">
        {runs.length === 0 ? (
          <div className="empty-state">No runs yet. Start a task to populate the timeline.</div>
        ) : null}

        {runs.map((run) => (
          <button
            type="button"
            key={run.id}
            className={`run-card ${selectedRunId === run.id ? 'is-selected' : ''}`}
            onClick={() => onSelectRun(run.id)}
          >
            <div className="run-card__top">
              <span className={`badge badge--${run.state}`}>{run.state}</span>
            </div>
            <p className="run-card__prompt">{run.prompt}</p>
            <div className="meta-row">
              <span className="muted">{new Date(run.updatedAt).toLocaleString()}</span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
