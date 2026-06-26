import { useState } from "react";
import type { ChatTranscriptEntry } from "../lib/types";
import type { WizardData } from "../lib/flows";

type WizardStepEntry = Extract<ChatTranscriptEntry, { kind: "wizard_step" }>;

interface WizardStepProps {
  entry: WizardStepEntry;
  busy: boolean;
  onNext: (choiceLabel: string, data: Partial<WizardData>) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onAddToGitignore?: (paths: string[]) => Promise<void>;
}

export function WizardStep({
  entry,
  busy,
  onNext,
  onConfirm,
  onCancel,
  onAddToGitignore,
}: WizardStepProps) {
  if (entry.status === "done") {
    return (
      <div className="wizard-step-done">
        <span className="wizard-done-icon">✓</span>
        <span className="wizard-done-text">
          {entry.prompt}: <strong>{entry.chosenLabel}</strong>
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
      return <TextInputStep entry={entry} busy={busy} onNext={onNext} onCancel={onCancel} />;
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
          Continue →
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

function TextInputStep({
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
  const [value, setValue] = useState("");

  function handleNext() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onNext(trimmed, { message: trimmed });
  }

  return (
    <div className="wizard-step-card">
      <p className="wizard-step-prompt">{entry.prompt}</p>
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
      <div className="wizard-step-actions">
        <button
          type="button"
          className="wizard-next-button"
          disabled={busy || !value.trim()}
          onClick={handleNext}
        >
          Continue →
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
          {busy ? "Executing..." : danger ? "Discard ▶" : "Execute ▶"}
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
