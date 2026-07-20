import { useEffect, useRef, useState } from "react";
import { desktopApi } from "../lib/api";
import type {
  GitHubSettings,
  GitIdentitySettings,
  GitLabSettings,
  LLMProviderKind,
  LLMSettings,
} from "../lib/types";

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
  const [githubSettings, setGithubSettings] = useState<GitHubSettings | null>(null);
  const [gitlabSettings, setGitlabSettings] = useState<GitLabSettings | null>(null);
  const [gitIdentity, setGitIdentity] = useState<GitIdentitySettings | null>(null);
  const [provider, setProvider] = useState<LLMProviderKind | "">("");
  const [apiKey, setApiKey] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [gitlabToken, setGitlabToken] = useState("");
  const [gitlabBaseUrl, setGitlabBaseUrl] = useState("https://gitlab.com");
  const [gitUserName, setGitUserName] = useState("");
  const [gitUserEmail, setGitUserEmail] = useState("");
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
    Promise.all([
      desktopApi.getLlmSettings(),
      desktopApi.getGithubSettings(),
      desktopApi.getGitlabSettings(),
      desktopApi.getGitIdentitySettings(),
    ])
      .then(([s, gh, gl, identity]) => {
        setSettings(s);
        setGithubSettings(gh);
        setGitlabSettings(gl);
        setGitIdentity(identity);
        setProvider(s.provider ?? "");
        setModel(s.model ?? "");
        setBaseUrl(s.baseUrl ?? "http://localhost:11434");
        setApiKey("");
        setGithubToken("");
        setGitlabToken("");
        setGitlabBaseUrl(gl.baseUrl ?? "https://gitlab.com");
        setGitUserName(identity.userName ?? "");
        setGitUserEmail(identity.userEmail ?? "");
      })
      .catch((err) => {
        setSaveError(typeof err === "string" ? err : "Failed to load settings.");
      });

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

  const gitIdentityChanged =
    gitUserName.trim() !== (gitIdentity?.userName ?? "") ||
    gitUserEmail.trim() !== (gitIdentity?.userEmail ?? "");

  const isDirty =
    provider !== (settings?.provider ?? "") ||
    model.trim() !== (settings?.model ?? "") ||
    (isOllama && baseUrl.trim() !== (settings?.baseUrl ?? "http://localhost:11434")) ||
    apiKey !== "" ||
    githubToken !== "" ||
    gitlabToken !== "" ||
    gitlabBaseUrl.trim() !== (gitlabSettings?.baseUrl ?? "https://gitlab.com") ||
    gitIdentityChanged;

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
      if (githubToken !== "") {
        await desktopApi.updateGithubSettings({ token: githubToken || null });
      }
      if (gitlabToken !== "" || gitlabBaseUrl.trim() !== (gitlabSettings?.baseUrl ?? "https://gitlab.com")) {
        await desktopApi.updateGitlabSettings({
          token: gitlabToken || null,
          baseUrl: gitlabBaseUrl.trim() || null,
        });
      }
      if (gitIdentityChanged) {
        const updatedIdentity = await desktopApi.updateGitIdentitySettings({
          userName: gitUserName.trim() || null,
          userEmail: gitUserEmail.trim() || null,
        });
        setGitIdentity(updatedIdentity);
        setGitUserName(updatedIdentity.userName ?? "");
        setGitUserEmail(updatedIdentity.userEmail ?? "");
      }

      const [updated, updatedGithub, updatedGitlab, updatedIdentity] = await Promise.all([
        desktopApi.getLlmSettings(),
        desktopApi.getGithubSettings(),
        desktopApi.getGitlabSettings(),
        desktopApi.getGitIdentitySettings(),
      ]);
      setSettings(updated);
      setGithubSettings(updatedGithub);
      setGitlabSettings(updatedGitlab);
      setGitIdentity(updatedIdentity);
      setApiKey("");
      setGithubToken("");
      setGitlabToken("");
      setGitlabBaseUrl(updatedGitlab.baseUrl ?? "https://gitlab.com");
      setGitUserName(updatedIdentity.userName ?? "");
      setGitUserEmail(updatedIdentity.userEmail ?? "");
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
      setTestResult({ ok: false, message: "You have unsaved changes - save first, then test." });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await desktopApi.testLlmConnection();
      setTestResult(result);
    } catch {
      setTestResult({ ok: false, message: "Request failed - check that the sidecar is running." });
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
      <div className="modal-panel settings-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            x
          </button>
        </div>

        <div className="modal-body settings-body">
          <section className="settings-section">
            <p className="settings-section-heading">GIT AUTHOR IDENTITY</p>
            <p className="settings-hint">
              Required before this machine can create commits. These fields save to global Git config,
              the same as running git config --global user.name and user.email.
            </p>
            <label className="settings-label" htmlFor="git-user-name-input">
              Name
            </label>
            <input
              id="git-user-name-input"
              type="text"
              className="settings-input"
              value={gitUserName}
              onChange={(e) => {
                setGitUserName(e.target.value);
                markDirty();
              }}
              placeholder="Allan Perasmo"
              autoComplete="name"
              disabled={gitIdentity?.gitAvailable === false}
            />
            <label className="settings-label" htmlFor="git-user-email-input">
              Email
            </label>
            <input
              id="git-user-email-input"
              type="email"
              className="settings-input"
              value={gitUserEmail}
              onChange={(e) => {
                setGitUserEmail(e.target.value);
                markDirty();
              }}
              placeholder="you@example.com"
              autoComplete="email"
              disabled={gitIdentity?.gitAvailable === false}
            />
            {gitIdentity && (
              <p className={gitIdentity.configured ? "settings-test-ok" : "settings-hint warning"}>
                {gitIdentity.message}
              </p>
            )}
          </section>

          <section className="settings-section">
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
              <option value="">None - local planner only</option>
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
                  onChange={(e) => {
                    setModel(e.target.value);
                    markDirty();
                  }}
                  placeholder={DEFAULT_MODELS[provider as LLMProviderKind] ?? ""}
                />

                {needsKey && (
                  <>
                    <label className="settings-label" htmlFor="apikey-input">
                      API Key{settings?.apiKeySet ? " (key stored - enter a new one to replace)" : ""}
                    </label>
                    <input
                      id="apikey-input"
                      type="password"
                      className="settings-input"
                      value={apiKey}
                      onChange={(e) => {
                        setApiKey(e.target.value);
                        markDirty();
                      }}
                      placeholder={settings?.apiKeySet ? "Stored key" : "Paste your API key"}
                      autoComplete="off"
                    />
                    <p className="settings-hint warning">
                      API keys are encrypted locally before storage. Use a key with minimal permissions.
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
                      onChange={(e) => {
                        setBaseUrl(e.target.value);
                        markDirty();
                      }}
                      placeholder="http://localhost:11434"
                    />
                  </>
                )}
              </>
            )}
          </section>

          <section className="settings-section">
            <p className="settings-section-heading">GITHUB PLATFORM ACTIONS</p>
            <p className="settings-hint">
              Required for drafting GitHub releases and pull requests. The same token is also used
              for GitHub HTTPS pull, push, fetch, and tag push operations so Git does not ask for a
              terminal password. Use a fine-grained token scoped to the repository with Contents:
              Read and write. Pull request actions also need Pull requests: Read and write.
            </p>
            <label className="settings-label" htmlFor="github-token-input">
              GitHub token{githubSettings?.tokenSet ? " (token stored - enter a new one to replace)" : ""}
            </label>
            <input
              id="github-token-input"
              type="password"
              className="settings-input"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder={githubSettings?.tokenSet ? "Stored token" : "Paste a fine-grained GitHub token"}
              autoComplete="off"
            />
            <p className="settings-hint warning">
              GitHub API actions and Git HTTPS writes still require your explicit wizard confirmation
              before anything is sent to GitHub.
            </p>
          </section>

          <section className="settings-section">
            <p className="settings-section-heading">GITLAB PLATFORM ACTIONS</p>
            <p className="settings-hint">
              Required for drafting GitLab merge requests. Use a personal access token with api scope
              for the target project. Self-managed GitLab can use its own base URL.
            </p>
            <label className="settings-label" htmlFor="gitlab-token-input">
              GitLab token{gitlabSettings?.tokenSet ? " (token stored - enter a new one to replace)" : ""}
            </label>
            <input
              id="gitlab-token-input"
              type="password"
              className="settings-input"
              value={gitlabToken}
              onChange={(e) => setGitlabToken(e.target.value)}
              placeholder={gitlabSettings?.tokenSet ? "Stored token" : "Paste a GitLab personal access token"}
              autoComplete="off"
            />
            <label className="settings-label" htmlFor="gitlab-base-url-input">
              GitLab base URL
            </label>
            <input
              id="gitlab-base-url-input"
              type="text"
              className="settings-input"
              value={gitlabBaseUrl}
              onChange={(e) => setGitlabBaseUrl(e.target.value)}
              placeholder="https://gitlab.com"
            />
            <p className="settings-hint warning">
              Draft merge requests still require your explicit wizard confirmation before anything is
              sent to GitLab.
            </p>
          </section>

          {(saveError || testResult) && (
            <section className="settings-section settings-section-full">
              {saveError && <p className="settings-error">{saveError}</p>}
              {testResult && (
                <p className={testResult.ok ? "settings-test-ok" : "settings-error"}>
                  {testResult.ok ? "OK: " : "Error: "}
                  {testResult.message}
                </p>
              )}
            </section>
          )}
        </div>

        <div className="modal-footer settings-footer">
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
          <button type="button" className="primary-button" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
