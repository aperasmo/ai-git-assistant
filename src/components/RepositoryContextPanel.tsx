import { useEffect, useState } from "react";
import type { ReadAction, Repository, RepositorySnapshot } from "../lib/types";

interface RepositoryContextPanelProps {
  repository?: Repository | null;
  snapshot?: RepositorySnapshot | null;
  busy: boolean;
  onAction: (action: ReadAction) => void;
  activeLlm?: { provider: string; model: string } | null;
  onTestLlm?: () => Promise<{ ok: boolean; message: string }>;
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
  activeLlm,
  onTestLlm,
}: RepositoryContextPanelProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    setTestResult(null);
  }, [activeLlm?.provider, activeLlm?.model]);
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
          S Git Status
        </button>
        <button type="button" onClick={() => onAction("diff")} disabled={busy}>
          D View Diff
        </button>
        <button type="button" onClick={() => onAction("graph")} disabled={busy}>
          G Commit graph
        </button>
        <button type="button" onClick={() => onAction("branches")} disabled={busy}>
          B Branches
        </button>
        <button type="button" onClick={() => onAction("stashes")} disabled={busy}>
          T Stashes
        </button>
        <button type="button" onClick={() => onAction("remotes")} disabled={busy}>
          R Remotes
        </button>
        <button type="button" onClick={() => onAction("conflicts")} disabled={busy}>
          ! Conflicts
        </button>
        <button type="button" onClick={() => onAction("fetch")} disabled={busy}>
          F Refresh remote
        </button>
      </div>

      <p className="context-subheading ai-heading">AI ASSISTANT</p>
      {activeLlm ? (
        <div className="ai-status-panel">
          <div className="ai-status-row">
            <span className="ai-status-dot active" />
            <span className="ai-status-label">
              {activeLlm.provider}
              <span className="ai-status-model"> · {activeLlm.model}</span>
            </span>
          </div>
          {onTestLlm && (
            <button
              type="button"
              className="ai-test-btn"
              disabled={testing || busy}
              onClick={async () => {
                setTesting(true);
                setTestResult(null);
                try { setTestResult(await onTestLlm()); }
                finally { setTesting(false); }
              }}
            >
              {testing ? "Testing…" : "Test connection"}
            </button>
          )}
          {testResult && (
            <p className={testResult.ok ? "ai-test-ok" : "ai-test-fail"}>
              {testResult.ok ? "✓ " : "✗ "}{testResult.message}
            </p>
          )}
        </div>
      ) : (
        <p className="ai-unconfigured">
          No AI provider configured. Open <strong>Settings</strong> to add one — unrecognised
          requests will be handled automatically.
        </p>
      )}
    </aside>
  );
}
