import type { Repository } from "../lib/types";

interface RepositorySidebarProps {
  repositories: Repository[];
  activeRepositoryId?: string | null;
  isBusy: boolean;
  onSelect: (repositoryId: string) => void;
  onAdd: () => void;
  onClone: () => void;
  onRemove: (repositoryId: string) => void;
}

export function RepositorySidebar({
  repositories,
  activeRepositoryId,
  isBusy,
  onSelect,
  onAdd,
  onClone,
  onRemove,
}: RepositorySidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-section-heading">
        <span>REPOSITORIES</span>
        <div className="sidebar-heading-actions">
          <button
            type="button"
            className="small-button"
            onClick={onClone}
            disabled={isBusy}
          >
            ↓ Clone
          </button>
          <button
            type="button"
            className="small-button"
            onClick={onAdd}
            disabled={isBusy}
          >
            + Add
          </button>
        </div>
      </div>

      <div className="repo-filter-placeholder">Filter repositories...</div>

      <div className="repository-list">
        {repositories.length === 0 ? (
          <p className="sidebar-empty">No repository added yet.</p>
        ) : (
          repositories.map((repository) => {
            const active = repository.id === activeRepositoryId;
            return (
              <div key={repository.id} className="repository-item-row">
                <button
                  type="button"
                  className={active ? "repository-item active" : "repository-item"}
                  onClick={() => onSelect(repository.id)}
                  disabled={isBusy}
                >
                  <span className="repository-avatar">
                    {repository.displayName.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="repository-item-copy">
                    <strong>{repository.displayName}</strong>
                    <small>{repository.pathLabel}</small>
                    <em>⑂ {repository.currentBranch ?? "No branch"}</em>
                  </span>
                  {active && <span className="active-indicator" aria-label="Active repository" />}
                </button>
                <button
                  type="button"
                  className="repo-remove-button"
                  title="Remove from list"
                  disabled={isBusy}
                  onClick={(e) => { e.stopPropagation(); onRemove(repository.id); }}
                >
                  ×
                </button>
              </div>
            );
          })
        )}
      </div>

      <div className="conversation-section">
        <div className="sidebar-section-heading">
          <span>SESSION HISTORY</span>
        </div>
        <p className="sidebar-empty">
          Requests and reviewed Git plans remain visible for this repository while the app is open.
        </p>
      </div>

      <div className="provider-status">
        <span className="status-dot local" />
        <span>Local Git + existing credentials</span>
      </div>
    </aside>
  );
}
