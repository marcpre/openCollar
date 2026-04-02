import { useMemo, useState } from 'react';
import { AVAILABLE_MODES, GEMINI_MODELS } from '../lib/tauri';
import type { Mode, ModelConfig, ModelProvider } from '../lib/types';

interface PromptComposerProps {
  onStartRun: (prompt: string, mode: Mode, modelConfig: ModelConfig) => Promise<void>;
}

const DEFAULT_PROMPT = `Open Notepad++, write a poem, and save it to Desktop/agent_test/gedicht.txt.`;

export function PromptComposer({ onStartRun }: PromptComposerProps) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [mode, setMode] = useState<Mode>('assist');
  const [provider, setProvider] = useState<ModelProvider>('deterministic');
  const [modelName, setModelName] = useState('deterministic-mvp');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  const requiresApiKey = provider === 'gemini';
  const availableModels = useMemo(
    () => GEMINI_MODELS.filter((entry) => entry.provider === provider),
    [provider],
  );
  const canStart = Boolean(prompt.trim()) && (!requiresApiKey || Boolean(apiKey.trim()));

  const handleSubmit = async () => {
    if (!canStart) {
      return;
    }

    setBusy(true);
    try {
      await onStartRun(prompt.trim(), mode, {
        provider,
        modelName,
        apiKey: requiresApiKey ? apiKey.trim() : undefined,
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="composer">
      <div>
        <label className="composer__label" htmlFor="prompt">
          Prompt
        </label>
        <textarea
          id="prompt"
          className="composer__textarea"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Describe the Windows task you want open collar to complete."
        />
      </div>

      <div>
        <label className="composer__label" htmlFor="mode">
          Mode
        </label>
        <select
          id="mode"
          className="composer__select"
          value={mode}
          onChange={(event) => setMode(event.target.value as Mode)}
        >
          {AVAILABLE_MODES.map((availableMode) => (
            <option key={availableMode} value={availableMode}>
              {availableMode}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="composer__label" htmlFor="provider">
          AI provider
        </label>
        <select
          id="provider"
          className="composer__select"
          value={provider}
          onChange={(event) => {
            const nextProvider = event.target.value as ModelProvider;
            setProvider(nextProvider);
            const defaultModel = GEMINI_MODELS.find((entry) => entry.provider === nextProvider);
            setModelName(defaultModel?.modelName ?? 'deterministic-mvp');
            if (nextProvider !== 'gemini') {
              setApiKey('');
            }
          }}
        >
          <option value="deterministic">deterministic MVP</option>
          <option value="gemini">Google Gemini</option>
        </select>
      </div>

      <div>
        <label className="composer__label" htmlFor="modelName">
          Model
        </label>
        <select
          id="modelName"
          className="composer__select"
          value={modelName}
          onChange={(event) => setModelName(event.target.value)}
        >
          {availableModels.map((availableModel) => (
            <option key={`${availableModel.provider}-${availableModel.modelName}`} value={availableModel.modelName}>
              {availableModel.modelName}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="composer__label" htmlFor="apiKey">
          API key
        </label>
        <input
          id="apiKey"
          className="composer__select"
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          placeholder={requiresApiKey ? 'Paste your Gemini API key for this run.' : 'Not required for deterministic mode'}
          disabled={!requiresApiKey}
        />
      </div>

      <div className="toolbar-row">
        <button type="button" className="button button--primary" onClick={handleSubmit} disabled={busy || !canStart}>
          {busy ? 'Starting…' : 'Start run'}
        </button>
      </div>
    </section>
  );
}
