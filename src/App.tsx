import { useEffect, useMemo, useState } from 'react';
import { PromptComposer } from './components/PromptComposer';
import { useOpenCollarApp } from './hooks/useOpenCollarApp';
import { EMPTY_SNAPSHOT } from './lib/mock';
import './index.css';

const GEMINI_API_KEY_STORAGE = 'open-collar.gemini-api-key';

function App() {
  const { snapshot, loading, error, actions } = useOpenCollarApp();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [geminiApiKey, setGeminiApiKey] = useState('');

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const stored = window.localStorage.getItem(GEMINI_API_KEY_STORAGE);
    if (stored) {
      setGeminiApiKey(stored);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    if (geminiApiKey) {
      window.localStorage.setItem(GEMINI_API_KEY_STORAGE, geminiApiKey);
    } else {
      window.localStorage.removeItem(GEMINI_API_KEY_STORAGE);
    }
  }, [geminiApiKey]);

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

  useEffect(() => {
    if (currentRun?.id) {
      setSelectedRunId(currentRun.id);
    }
  }, [currentRun?.id]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__title">
          <span className={`status-dot status-dot--${snapshot?.workerStatus ?? 'offline'}`} />
          <div>
            <p className="eyebrow">open collar</p>
            <h1>Desktop agent chat</h1>
          </div>
        </div>

        <button
          type="button"
          className="icon-button"
          aria-label="Open settings"
          onClick={() => setSettingsOpen((current) => !current)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M10.3 2.7h3.4l.6 2.2c.4.1.8.3 1.2.5l2-1.1 2.4 2.4-1.1 2c.2.4.4.8.5 1.2l2.2.6v3.4l-2.2.6c-.1.4-.3.8-.5 1.2l1.1 2-2.4 2.4-2-1.1c-.4.2-.8.4-1.2.5l-.6 2.2h-3.4l-.6-2.2a6 6 0 0 1-1.2-.5l-2 1.1-2.4-2.4 1.1-2a6 6 0 0 1-.5-1.2l-2.2-.6v-3.4l2.2-.6c.1-.4.3-.8.5-1.2l-1.1-2 2.4-2.4 2 1.1c.4-.2.8-.4 1.2-.5zm1.7 6a3.3 3.3 0 1 0 0 6.6 3.3 3.3 0 0 0 0-6.6Z" />
          </svg>
        </button>
      </header>

      {settingsOpen ? (
        <section className="settings-popover">
          <div className="settings-popover__header">
            <h2>Settings</h2>
            <button type="button" className="icon-button icon-button--small" onClick={() => setSettingsOpen(false)}>
              ×
            </button>
          </div>
          <label className="composer__label" htmlFor="geminiApiKey">
            Gemini API key
          </label>
          <input
            id="geminiApiKey"
            className="field"
            type="password"
            value={geminiApiKey}
            onChange={(event) => setGeminiApiKey(event.target.value)}
            placeholder="Paste your Gemini API key"
          />
          <p className="hint">Used for Gemini runs from this chat window.</p>
        </section>
      ) : null}

      {error ? <div className="banner banner--error">{error}</div> : null}
      {loading ? <div className="banner">Loading chat…</div> : null}

      <main className="workspace workspace--single">
        <PromptComposer
          run={currentRun}
          geminiApiKey={geminiApiKey}
          onStartRun={actions.startRun}
          onApprove={actions.approveStepGroup}
          onPause={actions.pauseRun}
          onResume={actions.resumeRun}
          onCancel={actions.cancelRun}
        />
      </main>
    </div>
  );
}

export default App;
