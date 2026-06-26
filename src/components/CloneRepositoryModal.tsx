import { useState } from "react";
import { desktopApi } from "../lib/api";
import type { Repository } from "../lib/types";

interface CloneRepositoryModalProps {
  onCloned: (repository: Repository) => void;
  onCancel: () => void;
}

function folderNameFromUrl(url: string): string {
  const part = url.trim().replace(/\/$/, "").split("/").pop() ?? "";
  return part.endsWith(".git") ? part.slice(0, -4) : part;
}

export function CloneRepositoryModal({ onCloned, onCancel }: CloneRepositoryModalProps) {
  const [url, setUrl] = useState("");
  const [parentPath, setParentPath] = useState("");
  const [folderName, setFolderName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleUrlChange(value: string) {
    setUrl(value);
    if (!folderName || folderName === folderNameFromUrl(url)) {
      setFolderName(folderNameFromUrl(value));
    }
  }

  async function handleBrowse() {
    const picked = await desktopApi.pickCloneTarget();
    if (picked) setParentPath(picked);
  }

  async function handleClone() {
    const trimmedUrl = url.trim();
    const trimmedFolder = folderName.trim();
    if (!trimmedUrl || !parentPath) return;

    setBusy(true);
    setError(null);
    try {
      const repo = await desktopApi.cloneRepository(trimmedUrl, parentPath, trimmedFolder || undefined);
      onCloned(repo);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  const canClone = url.trim().length > 0 && parentPath.length > 0 && !busy;

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <h2 className="modal-title">Clone repository</h2>

        <div className="clone-field">
          <label className="clone-label">Remote URL</label>
          <input
            type="text"
            className="clone-input"
            placeholder="https://github.com/user/repo.git"
            value={url}
            onChange={(e) => handleUrlChange(e.target.value)}
            disabled={busy}
            autoFocus
          />
          <small className="clone-hint">HTTPS or SSH URL. Existing credentials (GCM / SSH key) are used automatically.</small>
        </div>

        <div className="clone-field">
          <label className="clone-label">Clone into folder</label>
          <div className="clone-path-row">
            <input
              type="text"
              className="clone-input clone-path-input"
              placeholder="No folder selected"
              value={parentPath}
              readOnly
              disabled={busy}
            />
            <button
              type="button"
              className="clone-browse-button"
              onClick={handleBrowse}
              disabled={busy}
            >
              Browse...
            </button>
          </div>
        </div>

        <div className="clone-field">
          <label className="clone-label">Folder name</label>
          <input
            type="text"
            className="clone-input"
            placeholder="Auto-detected from URL"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            disabled={busy}
          />
        </div>

        {parentPath && folderName && (
          <p className="clone-target-preview">
            Will clone into: <code>{parentPath.replace(/\\/g, "/")}/{folderName}</code>
          </p>
        )}

        {error && (
          <div className="clone-error">
            <strong>Clone failed</strong>
            <p>{error}</p>
          </div>
        )}

        <div className="modal-actions">
          <button
            type="button"
            className="modal-confirm-button"
            disabled={!canClone}
            onClick={handleClone}
          >
            {busy ? "Cloning..." : "Clone"}
          </button>
          <button
            type="button"
            className="modal-cancel-button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
