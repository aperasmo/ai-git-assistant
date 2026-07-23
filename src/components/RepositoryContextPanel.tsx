import { useEffect, useState } from "react";
import { platformFeatureHint, providerDetailLines, providerSummary } from "../lib/remoteProviders";
import type { AgentSession, ReadAction, Repository, RepositorySnapshot } from "../lib/types";

interface RepositoryContextPanelProps {
  repository?: Repository | null;
  snapshot?: RepositorySnapshot | null;
  collapsed?: boolean;
  agentSessions?: AgentSession[];
  busy: boolean;
  onCollapse?: () => void;
  onAction: (action: ReadAction) => void;
  onCreateAgentSession?: (task: string) => Promise<void>;
  onRefreshAgentSessions?: () => Promise<AgentSession[] | void>;
  onCompareAgentSession?: (sessionId: string) => Promise<void>;
  onMergeAgentSession?: (sessionId: string) => Promise<void>;
  onAbandonAgentSession?: (sessionId: string) => Promise<void>;
  onCleanupAgentSession?: (sessionId: string) => Promise<void>;
  activeLlm?: { provider: string; model: string } | null;
  onTestLlm?: () => Promise<{ ok: boolean; message: string }>;
  onAnalyzeChanges?: () => void;
  onSetRepositoryLlmAllowed?: (allowed: boolean) => Promise<void>;
  onCreateTeamContext?: () => Promise<void>;
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
  collapsed = false,
  agentSessions = [],
  busy,
  onCollapse,
  onAction,
  onCreateAgentSession,
  onRefreshAgentSessions,
  onCompareAgentSession,
  onMergeAgentSession,
  onAbandonAgentSession,
  onCleanupAgentSession,
  activeLlm,
  onTestLlm,
  onAnalyzeChanges,
  onSetRepositoryLlmAllowed,
  onCreateTeamContext,
}: RepositoryContextPanelProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [savingAiAllowed, setSavingAiAllowed] = useState(false);
  const [agentTask, setAgentTask] = useState("");
  const [agentBusy, setAgentBusy] = useState(false);
  const [teamContextBusy, setTeamContextBusy] = useState(false);

  useEffect(() => {
    setTestResult(null);
  }, [activeLlm?.provider, activeLlm?.model]);

  if (collapsed) {
    return (
      <aside className="context-panel-collapsed" aria-label="Repository context collapsed">
        <button
          type="button"
          className="context-expand-button"
          onClick={onCollapse}
          aria-label="Show repository context"
          title="Show repository context"
        >
          <span aria-hidden="true">&lt;</span>
          <strong>Context</strong>
        </button>
      </aside>
    );
  }

  if (!repository || !snapshot) {
    return (
      <aside className="context-panel">
        <div className="context-heading-row">
          <p className="context-heading">REPOSITORY CONTEXT</p>
          {onCollapse && (
            <button
              type="button"
              className="icon-button context-collapse-button"
              onClick={onCollapse}
            aria-label="Hide repository context"
            title="Hide repository context"
          >
              &gt;
          </button>
        )}
        </div>
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
  const changedFileCount =
    snapshot.stagedChanges.length + snapshot.modifiedChanges.length + snapshot.untrackedPaths.length;
  const remoteProviderLabel = providerSummary(snapshot);
  const remoteProviderDetails = providerDetailLines(snapshot);
  const teamContext = snapshot.teamContext ?? {
    available: false,
    path: ".ai-git-assistant/team-context.md",
    charCount: 0,
    truncated: false,
  };

  async function handleCreateTeamContext() {
    if (!onCreateTeamContext) return;
    setTeamContextBusy(true);
    try {
      await onCreateTeamContext();
    } finally {
      setTeamContextBusy(false);
    }
  }

  return (
    <aside className="context-panel">
      <div className="context-heading-row">
        <p className="context-heading">REPOSITORY CONTEXT</p>
        {onCollapse && (
          <button
            type="button"
            className="icon-button context-collapse-button"
            onClick={onCollapse}
            aria-label="Hide repository context"
            title="Hide repository context"
          >
            &gt;
          </button>
        )}
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

      <div className="remote-provider-card">
        <div className="remote-provider-header">
          <span>Remote provider</span>
          <strong>{remoteProviderLabel}</strong>
        </div>
        <div className="remote-provider-list">
          {remoteProviderDetails.map((line) => (
            <code key={line}>{line}</code>
          ))}
        </div>
        <p>{platformFeatureHint(snapshot)}</p>
      </div>

      <div className={`team-context-card ${teamContext.available ? "available" : ""}`}>
        <div className="team-context-header">
          <span>Team context</span>
          <strong>{teamContext.available ? "Active" : "Not configured"}</strong>
        </div>
        {teamContext.available ? (
          <>
            <code>{teamContext.path}</code>
            <p>
              {teamContext.charCount.toLocaleString()} characters available for AI drafts
              {teamContext.truncated ? " (trimmed for prompt size)." : "."}
            </p>
          </>
        ) : (
          <>
            <p>
              Repository convention file not found. Add the starter template, then edit it for this repo.
            </p>
            {onCreateTeamContext && (
              <button
                type="button"
                className="small-button team-context-create-button"
                onClick={handleCreateTeamContext}
                disabled={busy || teamContextBusy}
              >
                {teamContextBusy ? "Adding..." : "Add template"}
              </button>
            )}
          </>
        )}
      </div>

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
        <button type="button" onClick={() => onAction("tags")} disabled={busy}>
          # Tags
        </button>
        <button type="button" onClick={() => onAction("conflicts")} disabled={busy}>
          ! Conflicts
        </button>
        <button type="button" onClick={() => onAction("review_status")} disabled={busy}>
          Y Review status
        </button>
        <button type="button" onClick={() => onAction("fetch")} disabled={busy}>
          F Refresh remote
        </button>
      </div>

      <p className="context-subheading agent-heading">AGENT WORKTREES</p>
      <div className="agent-panel">
        <form
          className="agent-create-form"
          onSubmit={async (event) => {
            event.preventDefault();
            const task = agentTask.trim();
            if (!task || !onCreateAgentSession) return;
            setAgentBusy(true);
            try {
              await onCreateAgentSession(task);
              setAgentTask("");
            } finally {
              setAgentBusy(false);
            }
          }}
        >
          <input
            value={agentTask}
            onChange={(event) => setAgentTask(event.target.value)}
            placeholder="Describe isolated work..."
            disabled={busy || agentBusy || !onCreateAgentSession}
            maxLength={300}
          />
          <button
            type="submit"
            disabled={busy || agentBusy || !agentTask.trim() || !onCreateAgentSession}
          >
            {agentBusy ? "Creating..." : "Create"}
          </button>
        </form>
        <div className="agent-panel-header">
          <span>{agentSessions.length} session{agentSessions.length === 1 ? "" : "s"}</span>
          {onRefreshAgentSessions && (
            <button
              type="button"
              className="link-button"
              disabled={busy || agentBusy}
              onClick={async () => {
                setAgentBusy(true);
                try { await onRefreshAgentSessions(); }
                finally { setAgentBusy(false); }
              }}
            >
              Refresh
            </button>
          )}
        </div>
        <div className="agent-session-list">
          {agentSessions.length === 0 ? (
            <p className="context-empty-small">No agent worktrees yet.</p>
          ) : (
            agentSessions.map((session) => (
              <div key={session.id} className="agent-session-card">
                <div className="agent-session-title">
                  <strong>{session.task}</strong>
                  <span className={`agent-session-status ${session.status}`}>{session.status}</span>
                </div>
                <code>{session.branchName}</code>
                <small>
                  {session.commitsAhead} commit(s) ahead · {session.changedFileCount} working change(s)
                </small>
                {session.lastCommit && <small>{session.lastCommit}</small>}
                <div className="agent-session-actions">
                  <button
                    type="button"
                    disabled={busy || agentBusy}
                    onClick={() => void onCompareAgentSession?.(session.id)}
                  >
                    Compare
                  </button>
                  {session.status === "active" && (
                    <>
                      <button
                        type="button"
                        disabled={busy || agentBusy || session.commitsAhead === 0}
                        onClick={() => void onMergeAgentSession?.(session.id)}
                      >
                        Merge
                      </button>
                      <button
                        type="button"
                        disabled={busy || agentBusy}
                        onClick={() => void onAbandonAgentSession?.(session.id)}
                      >
                        Abandon
                      </button>
                    </>
                  )}
                  {session.status !== "active" && session.status !== "cleaned" && (
                    <button
                      type="button"
                      disabled={busy || agentBusy}
                      onClick={() => void onCleanupAgentSession?.(session.id)}
                    >
                      Clean
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
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
          {onSetRepositoryLlmAllowed && (
            <div className="ai-repo-toggle-row">
              <span>
                Repository AI context
                <small>Required for Generate with AI and Analyze changes</small>
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={repository.externalLlmAllowed}
                className={`toggle-switch ${repository.externalLlmAllowed ? "on" : ""}`}
                disabled={busy || savingAiAllowed}
                onClick={async () => {
                  setSavingAiAllowed(true);
                  try {
                    await onSetRepositoryLlmAllowed(!repository.externalLlmAllowed);
                  } finally {
                    setSavingAiAllowed(false);
                  }
                }}
              >
                {repository.externalLlmAllowed ? "ON" : "OFF"}
              </button>
            </div>
          )}
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
          {onAnalyzeChanges && (
            <button
              type="button"
              className="ai-test-btn ai-analyze-btn"
              disabled={busy || changedFileCount === 0 || !repository.externalLlmAllowed}
              onClick={onAnalyzeChanges}
            >
              Analyze changes
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
