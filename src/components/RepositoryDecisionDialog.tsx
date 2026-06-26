import type { FolderClassification } from "../lib/types";

interface RepositoryDecisionDialogProps {
  classification: FolderClassification;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function RepositoryDecisionDialog({
  classification,
  busy,
  onCancel,
  onConfirm,
}: RepositoryDecisionDialogProps) {
  const isNestedRepository = classification.kind === "nested_repository";
  const isPlainFolder = classification.kind === "initialisation_required";

  if (!isNestedRepository && !isPlainFolder) {
    return null;
  }

  const title = isNestedRepository
    ? "Add parent repository?"
    : "Initialise Git repository?";

  const confirmLabel = isNestedRepository
    ? "Add Parent Repository"
    : "Initialise Git & Add Repository";

  return (
    <div
      className="repository-decision-backdrop"
      role="presentation"
    >
      <section
        className="repository-decision-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="repository-decision-title"
      >
        <p className="repository-decision-eyebrow">REPOSITORY SETUP</p>
        <h2 id="repository-decision-title">{title}</h2>

        {isNestedRepository ? (
          <>
            <p>
              The selected folder belongs to an existing Git repository. Adding
              the parent repository prevents creation of an unsafe nested
              repository.
            </p>

            <div className="repository-decision-path-group">
              <span>Selected folder</span>
              <code>{classification.selectedPath}</code>
            </div>

            <div className="repository-decision-path-group">
              <span>Repository root</span>
              <code>{classification.repositoryRoot}</code>
            </div>
          </>
        ) : (
          <>
            <p>
              This folder is not currently a Git repository. Initialising it
              creates local Git metadata only.
            </p>

            <div className="repository-decision-path-group">
              <span>Selected folder</span>
              <code>{classification.selectedPath}</code>
            </div>

            <p className="repository-decision-note">
              This creates a hidden <code>.git</code> directory. It will not
              stage files, create a commit, push code, create a remote, or
              modify your existing project files.
            </p>
          </>
        )}

        <div className="repository-decision-actions">
          <button
            type="button"
            className="small-button"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>

          <button
            type="button"
            className="repository-decision-primary"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working..." : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}