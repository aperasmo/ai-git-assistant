import { useEffect, useMemo, useState } from "react";
import { desktopApi } from "../lib/api";
import type { DiagnosticsStatus } from "../lib/types";

interface DiagnosticsModalProps {
  open: boolean;
  onClose: () => void;
}

type DiagnosticsValue = string | number | boolean | null | undefined;
type DiagnosticsRow = { label: string; value: DiagnosticsValue };

function valueOrDash(value?: string | number | boolean | null): string {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

export function DiagnosticsModal({ open, onClose }: DiagnosticsModalProps) {
  const [diagnostics, setDiagnostics] = useState<DiagnosticsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;

    setDiagnostics(null);
    setError(null);
    setCopied(false);

    desktopApi
      .getDiagnosticsStatus()
      .then(setDiagnostics)
      .catch((cause) =>
        setError(typeof cause === "string" ? cause : "Unable to load diagnostics."),
      );
  }, [open]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const rows = useMemo(() => {
    if (!diagnostics) return [];
    return [
      { label: "App version", value: diagnostics.appVersion },
      { label: "Environment", value: diagnostics.environment },
      { label: "Protocol", value: diagnostics.protocolVersion },
      { label: "Git status", value: diagnostics.gitStatus },
      { label: "Git version", value: diagnostics.gitVersion },
      { label: "Repositories", value: diagnostics.repositoryCount },
      { label: "Database exists", value: diagnostics.databaseExists },
      { label: "Database path", value: diagnostics.databasePath },
      { label: "AI provider", value: diagnostics.llmProvider },
      { label: "AI model", value: diagnostics.llmModel },
      { label: "API key set", value: diagnostics.llmApiKeySet },
      { label: "API key storage", value: diagnostics.apiKeyStorage },
      { label: "Sidecar messages", value: diagnostics.recentSidecarMessages.length },
      { label: "Generated", value: diagnostics.generatedAt },
    ] satisfies DiagnosticsRow[];
  }, [diagnostics]);

  const diagnosticText = useMemo(
    () => {
      const lines = rows.map((row) => `${row.label}: ${valueOrDash(row.value)}`);
      if (diagnostics?.recentSidecarMessages.length) {
        lines.push("", "Recent sidecar messages:");
        lines.push(...diagnostics.recentSidecarMessages.map((message) => `- ${message}`));
      }
      return lines.join("\n");
    },
    [diagnostics, rows],
  );

  if (!open) return null;

  async function copyDiagnostics() {
    if (!diagnosticText) return;
    await navigator.clipboard.writeText(diagnosticText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div
      className="modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Diagnostics"
    >
      <div className="modal-panel diagnostics-panel" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Diagnostics</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            x
          </button>
        </div>

        <div className="modal-body">
          <p className="settings-hint">
            Local support details only. API keys, session tokens, and repository file contents are not included.
          </p>

          {error && <p className="settings-error">{error}</p>}
          {!error && !diagnostics && <p className="settings-hint">Loading diagnostics...</p>}

          {diagnostics && (
            <dl className="diagnostics-list">
              {rows.map((row) => (
                <div key={row.label} className="diagnostics-row">
                  <dt>{row.label}</dt>
                  <dd>{valueOrDash(row.value)}</dd>
                </div>
              ))}
            </dl>
          )}

          {diagnostics && diagnostics.recentSidecarMessages.length > 0 && (
            <div className="diagnostics-log">
              <p className="settings-section-heading">RECENT SIDECAR MESSAGES</p>
              <pre>{diagnostics.recentSidecarMessages.join("\n")}</pre>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="text-button" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={() => void copyDiagnostics()}
            disabled={!diagnostics}
          >
            {copied ? "Copied" : "Copy diagnostics"}
          </button>
        </div>
      </div>
    </div>
  );
}
