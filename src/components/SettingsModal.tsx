import { useEffect, useRef, useState } from "react";
import { desktopApi } from "../lib/api";
import type { LLMProviderKind, LLMSettings } from "../lib/types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  onSaved?: (provider: string, model: string) => void;
}

const PROVIDERS: { value: LLMProviderKind; label: string; needsKey: boolean }[] = [
  { value: "anthropic", label: "Anthropic (Claude)", needsKey: true },
  { value: "gemini", label: "Google Gemini", needsKey: true },
  { value: "openai", label: "OpenAI", needsKey: true },
  { value: "groq", label: "Groq (fast inference)", needsKey: true },
  { value: "ollama", label: "Ollama (local, no key needed)", needsKey: false },
];

const DEFAULT_MODELS: Record<LLMProviderKind, string> = {
  anthropic: "claude-haiku-4-5-20251001",
  gemini: "gemini-3.5-flash",
  openai: "gpt-4o-mini",
  groq: "llama-3.3-70b-versatile",
  ollama: "deepseek-r1:8b",
};

export function SettingsModal({ open, onClose, onSaved }: SettingsModalProps) {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [provider, setProvider] = useState<LLMProviderKind | "">("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const firstFocusRef = useRef<HTMLSelectElement>(null);

  useEffect(() => {
    if (!open) return;
    setSaveError(null);
    setSaved(false);
    setTestResult(null);
    desktopApi
      .getLlmSettings()
      .then((s) => {
        setSettings(s);
        setProvider(s.provider ?? "");
        setModel(s.model ?? "");
        setBaseUrl(s.baseUrl ?? "http://localhost:11434");
        setApiKey("");
      })
      .catch(() => {});

    setTimeout(() => firstFocusRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const selectedProviderInfo = PROVIDERS.find((p) => p.value === provider) ?? null;
  const needsKey = selectedProviderInfo?.needsKey ?? false;
  const isOllama = provider === "ollama";

  const isDirty =
    provider !== (settings?.provider ?? "") ||
    model.trim() !== (settings?.model ?? "") ||
    (isOllama && baseUrl.trim() !== (settings?.baseUrl ?? "http://localhost:11434")) ||
    apiKey !== "";

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      await desktopApi.updateLlmSettings({
        provider: provider || null,
        apiKey: apiKey || null,
        model: model.trim() || null,
        baseUrl: isOllama ? (baseUrl.trim() || null) : null,
      });
      // Re-fetch so settings reflects saved state and isDirty resets to false
      const updated = await desktopApi.getLlmSettings();
      setSettings(updated);
      setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      if (provider) onSaved?.(provider, (model.trim() || DEFAULT_MODELS[provider as LLMProviderKind]) ?? "");
    } catch (err) {
      setSaveError(typeof err === "string" ? err : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTestConnection() {
    if (isDirty) {
      setTestResult({ ok: false, message: "You have unsaved changes — save first, then test." });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await desktopApi.testLlmConnection();
      setTestResult(result);
    } catch {
      setTestResult({ ok: false, message: "Request failed — check that the sidecar is running." });
    } finally {
      setTesting(false);
    }
  }

  function handleProviderChange(value: string) {
    setProvider(value as LLMProviderKind | "");
    setModel(value ? DEFAULT_MODELS[value as LLMProviderKind] ?? "" : "");
    setTestResult(null);
  }

  function markDirty() {
    setTestResult(null);
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Settings">
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="settings-section-heading">AI ASSISTANT PROVIDER</p>
          <p className="settings-hint">
            When the local planner does not recognise a request, it is automatically sent to the
            configured AI provider. Save your settings, then use "Test connection" to verify.
          </p>

          <label className="settings-label" htmlFor="provider-select">
            Provider
          </label>
          <select
            id="provider-select"
            ref={firstFocusRef}
            className="settings-select"
            value={provider}
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            <option value="">None — local planner only</option>
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>

          {provider && (
            <>
              <label className="settings-label" htmlFor="model-input">
                Model
              </label>
              <input
                id="model-input"
                type="text"
                className="settings-input"
                value={model}
                onChange={(e) => { setModel(e.target.value); markDirty(); }}
                placeholder={DEFAULT_MODELS[provider as LLMProviderKind] ?? ""}
              />

              {needsKey && (
                <>
                  <label className="settings-label" htmlFor="apikey-input">
                    API Key{settings?.apiKeySet ? " (key stored — enter a new one to replace)" : ""}
                  </label>
                  <input
                    id="apikey-input"
                    type="password"
                    className="settings-input"
                    value={apiKey}
                    onChange={(e) => { setApiKey(e.target.value); markDirty(); }}
                    placeholder={settings?.apiKeySet ? "••••••••••••••••" : "Paste your API key"}
                    autoComplete="off"
                  />
                  <p className="settings-hint warning">
                    API keys are encrypted with Windows account protection before they are stored locally.
                    Use a key with minimal permissions.
                  </p>
                </>
              )}

              {isOllama && (
                <>
                  <label className="settings-label" htmlFor="baseurl-input">
                    Ollama base URL
                  </label>
                  <input
                    id="baseurl-input"
                    type="text"
                    className="settings-input"
                    value={baseUrl}
                    onChange={(e) => { setBaseUrl(e.target.value); markDirty(); }}
                    placeholder="http://localhost:11434"
                  />
                </>
              )}
            </>
          )}

          {saveError && <p className="settings-error">{saveError}</p>}
          {testResult && (
            <p className={testResult.ok ? "settings-test-ok" : "settings-error"}>
              {testResult.ok ? "✓ " : "✗ "}{testResult.message}
            </p>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="text-button" onClick={onClose}>
            Cancel
          </button>
          {provider && (
            <button
              type="button"
              className="text-button"
              onClick={handleTestConnection}
              disabled={testing || saving}
            >
              {testing ? "Testing..." : "Test connection"}
            </button>
          )}
          <button
            type="button"
            className="primary-button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : saved ? "Saved ✓" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
