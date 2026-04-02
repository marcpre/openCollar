import { toAssetUrl } from '../lib/tauri';
import type { RunRecord } from '../lib/types';

interface InspectorPanelProps {
  run: RunRecord | null;
}

export function InspectorPanel({ run }: InspectorPanelProps) {
  const screenshot = [...(run?.artifacts ?? [])]
    .reverse()
    .find((artifact) => artifact.kind === 'screenshot');

  const activeWindow = [...(run?.observations ?? [])]
    .reverse()
    .find((observation) => observation.kind === 'active_window');

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Inspector</h2>
        <span className="badge">Artifacts</span>
      </div>
      <div className="panel__body">
        <div className="inspector-card">
          <h3>Latest screenshot</h3>
          <div className="inspector-preview">
            {screenshot ? (
              <img src={toAssetUrl(screenshot.path)} alt={screenshot.label} />
            ) : (
              <span className="artifact-muted">No screenshot captured yet.</span>
            )}
          </div>
        </div>

        <div className="observation-card">
          <h3>Active window</h3>
          <p className="observation-card__text">
            {activeWindow?.content ?? 'Waiting for window metadata from the worker.'}
          </p>
        </div>

        <div className="panel">
          <div className="panel__header">
            <h3>Observations</h3>
            <span className="badge">{run?.observations.length ?? 0}</span>
          </div>
          <div className="panel__body observation-list">
            {(run?.observations ?? []).map((observation) => (
              <article key={observation.id} className="observation-card">
                <div className="meta-row">
                  <strong>{observation.kind}</strong>
                  <span className="muted mono">{new Date(observation.createdAt).toLocaleTimeString()}</span>
                </div>
                <p className="observation-card__text">{observation.content}</p>
              </article>
            ))}
            {run?.observations.length ? null : (
              <div className="empty-state">Window text, focus details, and verification notes will show up here.</div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel__header">
            <h3>Artifacts</h3>
            <span className="badge">{run?.artifacts.length ?? 0}</span>
          </div>
          <div className="panel__body artifact-list">
            {(run?.artifacts ?? []).map((artifact) => (
              <a
                key={artifact.id}
                href={toAssetUrl(artifact.path)}
                target="_blank"
                rel="noreferrer"
                className="artifact-card"
              >
                <div className="artifact-row">
                  <strong>{artifact.label}</strong>
                  <span className="badge">{artifact.kind}</span>
                </div>
                <p className="artifact-muted mono">{artifact.path}</p>
              </a>
            ))}
            {run?.artifacts.length ? null : (
              <div className="empty-state">Captured screenshots and saved-file paths will be linked here.</div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
