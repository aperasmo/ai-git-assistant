import { useEffect, useRef, useState } from "react";
import { CATEGORY_LABELS, HELP_COMMANDS, type HelpCategory, type HelpCommand } from "../lib/helpCommands";

interface HelpModalProps {
  open: boolean;
  onClose: () => void;
}

const FILTERS: { value: HelpCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "read", label: "Read" },
  { value: "write", label: "Write" },
  { value: "terminal", label: "Terminal / blocked" },
];

const WORKFLOWS: {
  id: string;
  title: string;
  summary: string;
  state: string;
  commandIds: string[];
}[] = [
  {
    id: "setup",
    title: "Setup & Repositories",
    summary: "Add existing projects, clone remotes, and understand the selected repo.",
    state: "Folder -> Git repo -> workspace",
    commandIds: ["status", "connect_remote"],
  },
  {
    id: "snapshot",
    title: "Stage & Snapshot",
    summary: "Move work from the working tree into a reviewed commit.",
    state: "Working tree -> staging area -> commit",
    commandIds: ["status", "diff", "stage", "unstage", "commit", "commit_push", "discard"],
  },
  {
    id: "branching",
    title: "Branch & Merge",
    summary: "Create branches, switch context, merge work, and resolve conflicts.",
    state: "Current branch -> feature branch -> merge",
    commandIds: ["branches", "short_log", "create_branch", "switch", "merge", "delete_branch"],
  },
  {
    id: "share",
    title: "Share, Update & Release",
    summary: "Refresh remote state, pull, push, tag, and draft releases safely.",
    state: "Local commits <-> remote provider <-> tag",
    commandIds: ["fetch", "pull", "push", "tags", "tag_write"],
  },
  {
    id: "inspect",
    title: "Inspect & Compare",
    summary: "Review history, file ownership, diffs, and temporary work.",
    state: "History + file changes -> explanation",
    commandIds: ["log", "blame_terminal", "stash", "stash_pop"],
  },
  {
    id: "advanced",
    title: "Advanced Safety",
    summary: "Power commands that need extra guardrails or stay in the terminal.",
    state: "Shared history stays protected",
    commandIds: ["revert", "rebase", "cherry_pick", "reset_soft", "reset_hard", "reflog", "bisect", "tag", "blame"],
  },
];

function commandBadge(cmd: HelpCommand): string {
  if (cmd.category === "read") return "Read";
  if (cmd.category === "write") return "In app";
  if (cmd.id === "reset_hard") return "Blocked";
  if (cmd.id === "revert") return "Planned";
  return "Terminal";
}

export function HelpModal({ open, onClose }: HelpModalProps) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<HelpCategory | "all">("all");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setSearch("");
    setFilter("all");
    setTimeout(() => searchRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const q = search.toLowerCase();
  const filtered = HELP_COMMANDS.filter((cmd) => {
    if (filter !== "all" && cmd.category !== filter) return false;
    if (!q) return true;
    return (
      cmd.name.toLowerCase().includes(q) ||
      cmd.description.toLowerCase().includes(q) ||
      cmd.gitCommand.toLowerCase().includes(q) ||
      cmd.gitExample.toLowerCase().includes(q) ||
      CATEGORY_LABELS[cmd.category].toLowerCase().includes(q) ||
      (cmd.appPhrases ?? []).some((p) => p.toLowerCase().includes(q))
    );
  });

  const filteredById = new Map(filtered.map((cmd) => [cmd.id, cmd]));
  const sections = WORKFLOWS.map((workflow) => ({
    ...workflow,
    cmds: workflow.commandIds
      .map((id) => filteredById.get(id))
      .filter((cmd): cmd is HelpCommand => Boolean(cmd)),
  })).filter((workflow) => workflow.cmds.length > 0);

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Git workflow cheat sheet">
      <div className="modal-panel modal-panel-help" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Git Workflow Cheat Sheet</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">x</button>
        </div>

        <div className="help-toolbar">
          <div className="help-search-wrap">
            <span className="help-search-icon">?</span>
            <input
              ref={searchRef}
              type="text"
              className="help-search"
              placeholder="Search commands, workflows, or examples..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button type="button" className="help-search-clear" onClick={() => setSearch("")}>x</button>
            )}
          </div>
          <div className="help-filter-pills">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                className={`help-filter-pill${filter === f.value ? " active" : ""}`}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="help-body">
          <section className="help-coverage-card">
            <div>
              <span className="help-section-label">COMMON GIT COVERAGE</span>
              <h3>Workflow-first help for the common Git path</h3>
              <p>
                Start with what changed, choose files, make a snapshot, then share it.
                Advanced history rewrites are separated so normal work stays safe.
              </p>
            </div>
            <div className="help-coverage-stats">
              <span><strong>18</strong> in app</span>
              <span><strong>1</strong> planned</span>
              <span><strong>1</strong> blocked</span>
            </div>
          </section>

          {filtered.length === 0 ? (
            <p className="help-empty">No commands match "{search}"</p>
          ) : (
            sections.map(({ id, title, summary, state, cmds }) => (
              <div key={id} className="help-section">
                <div className="help-section-header">
                  <div>
                    <span className="help-section-label">{title}</span>
                    <p className="help-section-summary">{summary}</p>
                  </div>
                  <span className="help-flow-chip">{state}</span>
                </div>
                <div className="help-grid">
                  {cmds.map((cmd) => (
                    <div
                      key={cmd.id}
                      className={`help-card${cmd.category === "terminal" ? " help-card-terminal" : ""}`}
                    >
                      <div className="help-card-header">
                        <span className="help-card-name">{cmd.name}</span>
                        <span className={`help-badge ${cmd.category === "terminal" ? "help-badge-terminal" : "help-badge-app"}`}>
                          {commandBadge(cmd)}
                        </span>
                      </div>

                      <p className="help-card-desc">{cmd.description}</p>

                      {cmd.appPhrases && cmd.appPhrases.length > 0 && (
                        <div className="help-card-section">
                          <span className="help-card-section-label">Type in app</span>
                          <div className="help-phrases">
                            {cmd.appPhrases.map((phrase) => (
                              <code key={phrase} className="help-phrase">{phrase}</code>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="help-card-section">
                        <span className="help-card-section-label">Git command</span>
                        <pre className="help-git-example">{cmd.gitExample}</pre>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="modal-footer help-footer">
          <span className="help-count">{filtered.length} command{filtered.length !== 1 ? "s" : ""}</span>
          <button type="button" className="text-button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
