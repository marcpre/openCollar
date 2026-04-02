import { useMemo, useState } from 'react';
import { InspectorPanel } from './components/InspectorPanel';
import { PromptComposer } from './components/PromptComposer';
import { RunDetails } from './components/RunDetails';
import { RunHistory } from './components/RunHistory';
import { useOpenCollarApp } from './hooks/useOpenCollarApp';
import { EMPTY_SNAPSHOT } from './lib/mock';
import './index.css';

function App() {
  const { snapshot, loading, error, actions } = useOpenCollarApp();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const runs = snapshot?.runs ?? EMPTY_SNAPSHOT.runs;
  const selectedId = useMemo(() => {
    if (selectedRunId && runs.some((run) => run.id === selectedRunId)) {
      return selectedRunId;
    }

    return snapshot?.selectedRunId ?? runs[0]?.id ?? null;
  }, [runs, selectedRunId, snapshot?.selectedRunId]);

  const currentRun = useMemo(
    () => runs.find((run) => run.id === selectedId) ?? null,
    [runs, selectedId],
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Windows-first desktop computer-use agent</p>
          <h1>open collar</h1>
        </div>
        <div className="worker-status">
          <span className={`status-dot status-dot--${snapshot?.workerStatus ?? 'offline'}`} />
          <span>{snapshot?.workerStatus ?? 'offline'}</span>
        </div>
      </header>

      {error ? <div className="banner banner--error">{error}</div> : null}
      {loading ? <div className="banner">Loading current snapshot…</div> : null}

      <main className="workspace">
        <RunHistory
          runs={runs}
          selectedRunId={selectedId}
          onSelectRun={setSelectedRunId}
        />
        <RunDetails
          run={currentRun}
          onApprove={actions.approveStepGroup}
          onPause={actions.pauseRun}
          onResume={actions.resumeRun}
          onCancel={actions.cancelRun}
        />
        <InspectorPanel run={currentRun} />
      </main>

      <PromptComposer onStartRun={actions.startRun} />
    </div>
  );
}

export default App;
