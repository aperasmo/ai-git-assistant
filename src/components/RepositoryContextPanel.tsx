import type { ReadAction, Repository, RepositorySnapshot } from "../lib/types";

interface RepositoryContextPanelProps {
  repository?: Repository | null;
  snapshot?: RepositorySnapshot | null;
  busy: boolean;
  onAction: (action: ReadAction) => void;
  onToggleLlm?: (allowed: boolean) => void;
}

function CountRow({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="count-row">
      <span>{label}</span>
      <strong className={`count-badge ${tone}`}>{value}</strong>
    </div>
  );
}

export function RepositoryContextPanel({
  repository,
  snapshot,
  busy,
  onAction,
  onToggleLlm,
}: RepositoryContextPanelProps) {
  if (!repository || !snapshot) {
    return (
      <aside className="context-panel">
        <p className="context-heading">REPOSITORY CONTEXT</p>
        <div className="context-empty">
          <p>Live repository status will appear here after you select a repository.</p>
        </div>
      </aside>
    );
  }

  const remoteLabel = snapshot.remoteLastRefreshedAt
    ? new Intl.DateTimeFormat("en-NZ", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(snapshot.remoteLastRefreshedAt))
    : "Not refreshed this session";

  const upstreamLabel = snapshot.upstreamBranch
    ? snapshot.upstreamBranch
    : "No upstream configured";

  return (
    <aside className="context-panel">
      <div className="context-heading-row">
        <p className="context-heading">REPOSITORY CONTEXT</p>
        <button
          type="button"
          className="icon-button"
          onClick={() => onAction("status")}
          disabled={busy}
          aria-label="Refresh local status"
        >
          ⟳
        </button>
      </div>

      <h2>{repository.displayName}</h2>
      <p className="context-path">{repository.pathLabel}</p>

      <div className="branch-summary">
        <span>⑂ {snapshot.branch ?? "Detached HEAD"}</span>
        <strong>AHEAD {snapshot.ahead}</strong>
      </div>
      <p className="context-upstream">Upstream: {upstreamLabel}</p>

      {snapshot.writeBlockedReason && (
        <div className="blocked-banner">{snapshot.writeBlockedReason}</div>
      )}

      <p className="context-subheading">STATUS SUMMARY</p>
      <div className="status-list">
        <CountRow label="Staged changes" value={snapshot.stagedChanges.length} tone="good" />
        <CountRow label="Modified files" value={snapshot.modifiedChanges.length} tone="warning" />
        <CountRow label="Untracked files" value={snapshot.untrackedPaths.length} />
        <CountRow label="Conflicts" value={snapshot.conflicts.length} tone="danger" />
        <CountRow label="Behind remote" value={snapshot.behind} tone="warning" />
        <CountRow label="Ahead remote" value={snapshot.ahead} tone="good" />
      </div>

      <p className="remote-refresh">Remote state: {remoteLabel}</p>

      <div className="context-heading-row commits-header">
        <p className="context-subheading">RECENT COMMITS</p>
        <button
          type="button"
          className="link-button"
          onClick={() => onAction("log")}
          disabled={busy}
        >
          View all
        </button>
      </div>
      <div className="commit-list">
        {snapshot.recentCommits.length === 0 ? (
          <p className="context-empty-small">No commits found yet.</p>
        ) : (
          snapshot.recentCommits.slice(0, 4).map((commit) => (
            <div key={commit.fullHash} className="commit-row">
              <span className="commit-icon">⎇</span>
              <div>
                <p>
                  <code>{commit.shortHash}</code> {commit.subject}
                </p>
                <small>
                  {commit.author} ·{" "}
                  {new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium" }).format(
                    new Date(commit.committedAt),
                  )}
                </small>
              </div>
            </div>
          ))
        )}
      </div>

      <p className="context-subheading quick-actions-heading">QUICK ACTIONS</p>
      <div className="quick-actions">
        <button type="button" onClick={() => onAction("status")} disabled={busy}>
          ⌁ Git Status
        </button>
        <button type="button" onClick={() => onAction("diff")} disabled={busy}>
          ▤ View Diff
        </button>
        <button type="button" onClick={() => onAction("branches")} disabled={busy}>
          ⑂ Branches
        </button>
        <button type="button" onClick={() => onAction("fetch")} disabled={busy}>
          ⟳ Refresh remote
        </button>
      </div>

      {onToggleLlm && (
        <>
          <p className="context-subheading ai-heading">AI ASSISTANT</p>
          <div className="ai-toggle-row">
            <label className="ai-toggle-label" htmlFor="ai-toggle">
              <span>Allow AI for this repo</span>
              <span className="ai-toggle-hint">
                Sends repo context to the configured AI provider for unrecognised requests
              </span>
            </label>
            <button
              id="ai-toggle"
              type="button"
              role="switch"
              aria-checked={repository.externalLlmAllowed}
              className={`toggle-switch ${repository.externalLlmAllowed ? "on" : "off"}`}
              onClick={() => onToggleLlm(!repository.externalLlmAllowed)}
              disabled={busy}
            >
              {repository.externalLlmAllowed ? "ON" : "OFF"}
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
