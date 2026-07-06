import { useState } from "react";
import type { ChatTranscriptEntry, CommitMessageStyle, GenerateCommitMessageResponse } from "../lib/types";
import type { WizardData } from "../lib/flows";

type WizardStepEntry = Extract<ChatTranscriptEntry, { kind: "wizard_step" }>;

const COMMIT_MESSAGE_STYLES: { value: CommitMessageStyle; label: string }[] = [
  { value: "detailed", label: "Detailed" },
  { value: "concise", label: "Concise" },
  { value: "conventional", label: "Conventional" },
  { value: "release_ready", label: "Release" },
];

function toWizardErrorMessage(cause: unknown): string {
  if (cause instanceof Error && cause.message.trim()) return cause.message;
  if (typeof cause === "string" && cause.trim()) return cause;
  return "AI message generation failed.";
}

function composeCommitMessage(subject: string, body: string[]): string {
  const cleanSubject = subject.trim();
  const cleanBody = body.map((line) => line.trim()).filter(Boolean);
  if (cleanBody.length === 0) return cleanSubject;
  return `${cleanSubject}\n\n${cleanBody.map((line) => `- ${line}`).join("\n")}`;
}

interface WizardStepProps {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (choiceLabel: string, data: Partial<WizardData>) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onAddToGitignore?: (paths: string[]) => Promise<void>;
  onGenerateCommitMessage?: (paths: string[], style?: CommitMessageStyle) => Promise<GenerateCommitMessageResponse>;
  onPickReleaseAsset?: () => Promise<string | null>;
}

export function WizardStep({
  entry,
  busy,
  onNext,
  onConfirm,
  onCancel,
  onAddToGitignore,
  onGenerateCommitMessage,
  onPickReleaseAsset,
}: WizardStepProps) {
  if (entry.status === "done") {
    const isExecutingConfirm = busy && entry.stepKind === "confirm" && entry.chosenLabel === "Confirmed";

    return (
      <div className={isExecutingConfirm ? "wizard-step-done wizard-step-executing" : "wizard-step-done"}>
        {isExecutingConfirm ? (
          <span className="wizard-done-spinner" aria-hidden="true" />
        ) : (
          <span className="wizard-done-icon">✓</span>
        )}
        <span className="wizard-done-text">
          {entry.prompt}: <strong>{isExecutingConfirm ? "Executing..." : entry.chosenLabel}</strong>
        </span>
      </div>
    );
  }

  switch (entry.stepKind) {
    case "file_pick":
      return (
        <FilePickStep
          entry={entry}
          busy={busy}
          onNext={onNext}
          onCancel={onCancel}
          onAddToGitignore={onAddToGitignore}
        />
      );
    case "text_input":
      return (
        <TextInputStep
          entry={entry}
          busy={busy}
          onNext={onNext}
          onCancel={onCancel}
          onGenerateCommitMessage={onGenerateCommitMessage}
        />
      );
    case "asset_pick":
      return (
        <AssetPickStep
          entry={entry}
          busy={busy}
          onNext={onNext}
          onCancel={onCancel}
          onPickReleaseAsset={onPickReleaseAsset}
        />
      );
    case "option_select":
      return <OptionSelectStep entry={entry} busy={busy} onNext={onNext} onCancel={onCancel} />;
    case "confirm":
      return <ConfirmStep entry={entry} busy={busy} onConfirm={onConfirm} onCancel={onCancel} danger={entry.danger} />;
  }
}

function FilePickStep({
  entry,
  busy,
  onNext,
  onCancel,
  onAddToGitignore,
}: {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (label: string, data: Partial<WizardData>) => void;
  onCancel: () => void;
  onAddToGitignore?: (paths: string[]) => Promise<void>;
}) {
  const initial = entry.choices ?? [];
  const [choices, setChoices] = useState<string[]>(initial);
  const [selected, setSelected] = useState<string[]>(initial);
  const [gitignoring, setGitignoring] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    path: string;
  } | null>(null);

  const allSelected = choices.length > 0 && selected.length === choices.length;

  function toggle(path: string, checked: boolean) {
    setSelected((prev) => (checked ? [...prev, path] : prev.filter((f) => f !== path)));
  }

  function toggleAll() {
    setSelected(allSelected ? [] : [...choices]);
  }

  function handleNext() {
    const label = selected.length === 1 ? selected[0] : `${selected.length} files`;
    onNext(label, { files: selected });
  }

  async function handleGitignore(path: string) {
    if (!onAddToGitignore || gitignoring) return;
    // Optimistic: remove from UI immediately before the async call
    setChoices((prev) => prev.filter((p) => p !== path));
    setSelected((prev) => prev.filter((p) => p !== path));
    setGitignoring(true);
    try {
      await onAddToGitignore([path]);
    } finally {
      setGitignoring(false);
    }
  }

  const isLocked = busy || gitignoring;

  return (
    <div className="wizard-step-card">
      <div className="wizard-file-header">
        <p className="wizard-step-prompt">{entry.prompt}</p>
        {choices.length > 0 && (
          <button
            type="button"
            className="wizard-select-all-button"
            disabled={isLocked}
            onClick={toggleAll}
          >
            {allSelected ? "Deselect all" : "Select all"}
          </button>
        )}
      </div>

      <div className="wizard-file-list">
        {choices.map((path) => (
          <label
            key={path}
            className="wizard-file-item"
            onContextMenu={(e) => {
              e.preventDefault();
              setContextMenu({ x: e.clientX, y: e.clientY, path });
            }}
          >
            <input
              type="checkbox"
              checked={selected.includes(path)}
              onChange={(e) => toggle(path, e.target.checked)}
              disabled={isLocked}
            />
            <code>{path}</code>
          </label>
        ))}
        {choices.length === 0 && (
          <p className="wizard-empty-hint">No changed files found.</p>
        )}
      </div>

      <div className="wizard-step-actions">
        <button
          type="button"
          className="wizard-next-button"
          disabled={isLocked || selected.length === 0}
          onClick={handleNext}
        >
          Continue
        </button>
        <button
          type="button"
          className="wizard-cancel-button"
          disabled={isLocked}
          onClick={onCancel}
        >
          Cancel
        </button>
        <span className={`wizard-file-count ${selected.length === 0 ? "wizard-file-count-zero" : ""}`}>
          {selected.length}/{choices.length} files selected
        </span>
      </div>

      {contextMenu && (
        <>
          <div
            className="wizard-context-backdrop"
            onClick={() => setContextMenu(null)}
          />
          <div
            className="wizard-context-menu"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              type="button"
              className="wizard-context-item"
              disabled={gitignoring || !onAddToGitignore}
              onClick={() => {
                void handleGitignore(contextMenu.path);
                setContextMenu(null);
              }}
            >
              Add to .gitignore
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function AssetPickStep({
  entry,
  busy,
  onNext,
  onCancel,
  onPickReleaseAsset,
}: {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (label: string, data: Partial<WizardData>) => void;
  onCancel: () => void;
  onPickReleaseAsset?: () => Promise<string | null>;
}) {
  const [value, setValue] = useState("");
  const [picking, setPicking] = useState(false);

  async function handleBrowse() {
    if (!onPickReleaseAsset || picking) return;
    setPicking(true);
    try {
      const selected = await onPickReleaseAsset();
      if (selected) setValue(selected);
    } finally {
      setPicking(false);
    }
  }

  function handleNext() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onNext(trimmed.split(/[\\/]/).pop() ?? trimmed, { assetPath: trimmed });
  }

  return (
    <div className="wizard-step-card">
      <p className="wizard-step-prompt">{entry.prompt}</p>
      <div className="wizard-asset-row">
        <input
          type="text"
          className="wizard-text-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleNext();
          }}
          placeholder="Select or paste the asset path..."
          disabled={busy || picking}
          autoFocus
        />
        <button
          type="button"
          className="wizard-browse-button"
          disabled={busy || picking || !onPickReleaseAsset}
          onClick={() => void handleBrowse()}
        >
          {picking ? "..." : "Browse"}
        </button>
      </div>
      <div className="wizard-step-actions">
        <button
          type="button"
          className="wizard-next-button"
          disabled={busy || picking || !value.trim()}
          onClick={handleNext}
        >
          Continue
        </button>
        <button
          type="button"
          className="wizard-cancel-button"
          disabled={busy || picking}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function TextInputStep({
  entry,
  busy,
  onNext,
  onCancel,
  onGenerateCommitMessage,
}: {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (label: string, data: Partial<WizardData>) => void;
  onCancel: () => void;
  onGenerateCommitMessage?: (paths: string[], style?: CommitMessageStyle) => Promise<GenerateCommitMessageResponse>;
}) {
  const [value, setValue] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<GenerateCommitMessageResponse | null>(null);
  const [style, setStyle] = useState<CommitMessageStyle>("detailed");
  const isCommitMessage = entry.prompt === "Commit message";
  const selectedPaths = isCommitMessage ? entry.choices ?? [] : [];
  const canGenerate = selectedPaths.length > 0 && Boolean(onGenerateCommitMessage);

  function handleNext() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onNext(trimmed, { message: trimmed });
  }

  async function handleGenerate(nextStyle = style) {
    if (!onGenerateCommitMessage || generating || selectedPaths.length === 0) return;
    setStyle(nextStyle);
    setGenerating(true);
    setError(null);
    try {
      const generated = await onGenerateCommitMessage(selectedPaths, nextStyle);
      setValue(generated.message);
      setReceipt(generated);
    } catch (cause) {
      setError(toWizardErrorMessage(cause));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="wizard-step-card">
      <p className="wizard-step-prompt">{entry.prompt}</p>
      {isCommitMessage ? (
        <textarea
          className="wizard-text-input wizard-textarea-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Type here..."
          disabled={busy}
          autoFocus
          rows={receipt?.body.length ? 6 : 3}
        />
      ) : (
        <input
          type="text"
          className="wizard-text-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleNext();
          }}
          placeholder="Type here..."
          disabled={busy}
          autoFocus
        />
      )}
      {canGenerate && (
        <div className="wizard-ai-tools">
          <div className="wizard-ai-style-row">
            {COMMIT_MESSAGE_STYLES.map((option) => (
              <button
                key={option.value}
                type="button"
                className={style === option.value ? "wizard-ai-style-button wizard-ai-style-button-active" : "wizard-ai-style-button"}
                disabled={busy || generating}
                onClick={() => setStyle(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="wizard-ai-row">
            <button
              type="button"
              className="wizard-ai-button"
              disabled={busy || generating}
              onClick={() => void handleGenerate()}
            >
              {generating ? "Generating..." : "Generate with AI"}
            </button>
            <span>Uses selected diffs, stats, and recent commit style.</span>
          </div>
        </div>
      )}
      {receipt && (
        <div className="wizard-ai-draft-meta">
          <span>Confidence: {receipt.confidence}</span>
          {receipt.detectedScope.length > 0 && <span>Scope: {receipt.detectedScope.join(", ")}</span>}
        </div>
      )}
      {receipt?.alternatives.length ? (
        <div className="wizard-ai-alternatives">
          {receipt.alternatives.map((alternative) => (
            <button
              key={alternative}
              type="button"
              className="wizard-ai-alternative-button"
              disabled={busy}
              onClick={() => setValue(composeCommitMessage(alternative, receipt.body))}
            >
              {alternative}
            </button>
          ))}
        </div>
      ) : null}
      {receipt?.warning && <p className="wizard-ai-warning">{receipt.warning}</p>}
      {error && <p className="wizard-inline-error">{error}</p>}
      {receipt?.privacyReceipt && (
        <details className="wizard-privacy-receipt">
          <summary>Privacy receipt</summary>
          <p>{receipt.contextSummary}</p>
          <p>
            Sent to: <code>{receipt.privacyReceipt.provider ?? "AI provider"}</code>
            {receipt.privacyReceipt.model ? <> / <code>{receipt.privacyReceipt.model}</code></> : null}
          </p>
          <p>
            Files: <code>{receipt.privacyReceipt.files.length}</code> · Characters:{" "}
            <code>{receipt.privacyReceipt.characterCount}</code>
          </p>
          <ul>
            {receipt.privacyReceipt.contextItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {receipt.privacyReceipt.exactContext && (
            <pre>{receipt.privacyReceipt.exactContext}</pre>
          )}
        </details>
      )}
      <div className="wizard-step-actions">
        <button
          type="button"
          className="wizard-next-button"
          disabled={busy || !value.trim()}
          onClick={handleNext}
        >
          Continue
        </button>
        <button
          type="button"
          className="wizard-cancel-button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function OptionSelectStep({
  entry,
  busy,
  onNext,
  onCancel,
}: {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (label: string, data: Partial<WizardData>) => void;
  onCancel: () => void;
}) {
  return (
    <div className="wizard-step-card">
      <p className="wizard-step-prompt">{entry.prompt}</p>
      <div className="wizard-option-grid">
        {(entry.choices ?? []).map((choice) => (
          <button
            key={choice}
            type="button"
            className="wizard-option-button"
            disabled={busy}
            onClick={() => onNext(choice, { remote: choice })}
          >
            {choice}
          </button>
        ))}
      </div>
      <div className="wizard-step-actions">
        <button
          type="button"
          className="wizard-cancel-button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function ConfirmStep({
  entry,
  busy,
  onConfirm,
  onCancel,
  danger,
}: {
  entry: WizardStepEntry;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}) {
  return (
    <div className="wizard-step-card wizard-step-confirm">
      <p className={danger ? "wizard-step-prompt wizard-step-prompt-danger" : "wizard-step-prompt"}>{entry.prompt}</p>
      <ul className="wizard-confirm-lines">
        {(entry.confirmLines ?? []).map((line, i) =>
          line === "" ? (
            <li key={i} className="wizard-confirm-divider" />
          ) : (
            <li key={i}>{line}</li>
          )
        )}
      </ul>
      <div className="wizard-step-actions">
        <button
          type="button"
          className={danger ? "wizard-execute-button wizard-execute-button-danger" : "wizard-execute-button"}
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? (
            <>
              <span className="wizard-button-spinner" aria-hidden="true" />
              Executing...
            </>
          ) : danger ? (
            "Discard"
          ) : (
            "Execute"
          )}
        </button>
        <button
          type="button"
          className="wizard-cancel-button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
