import { useEffect, useRef, useState } from "react";
import { CATEGORY_LABELS, HELP_COMMANDS, type HelpCategory } from "../lib/helpCommands";

interface HelpModalProps {
  open: boolean;
  onClose: () => void;
}

const FILTERS: { value: HelpCategory | "all"; label: string }[] = [
  { value: "all",      label: "All" },
  { value: "read",     label: "Read" },
  { value: "write",    label: "Write" },
  { value: "terminal", label: "Terminal only" },
];

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
      (cmd.appPhrases ?? []).some((p) => p.toLowerCase().includes(q))
    );
  });

  const readCmds     = filtered.filter((c) => c.category === "read");
  const writeCmds    = filtered.filter((c) => c.category === "write");
  const terminalCmds = filtered.filter((c) => c.category === "terminal");

  const allSections: { category: HelpCategory; cmds: typeof filtered }[] = [
    { category: "read",     cmds: readCmds },
    { category: "write",    cmds: writeCmds },
    { category: "terminal", cmds: terminalCmds },
  ];
  const sections = allSections.filter((s) => s.cmds.length > 0);

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Git Command Reference">
      <div className="modal-panel modal-panel-help" onClick={(e) => e.stopPropagation()}>

        <div className="modal-header">
          <h2>Git Command Reference</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="help-toolbar">
          <div className="help-search-wrap">
            <span className="help-search-icon">⌕</span>
            <input
              ref={searchRef}
              type="text"
              className="help-search"
              placeholder="Search commands..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button type="button" className="help-search-clear" onClick={() => setSearch("")}>✕</button>
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
          {filtered.length === 0 ? (
            <p className="help-empty">No commands match "{search}"</p>
          ) : (
            sections.map(({ category, cmds }) => (
              <div key={category} className="help-section">
                <div className="help-section-header">
                  <span className="help-section-label">{CATEGORY_LABELS[category]}</span>
                  {category === "terminal" && (
                    <span className="help-terminal-hint">Run these in your terminal — not yet available in app</span>
                  )}
                </div>
                <div className="help-grid">
                  {cmds.map((cmd) => (
                    <div
                      key={cmd.id}
                      className={`help-card${category === "terminal" ? " help-card-terminal" : ""}`}
                    >
                      <div className="help-card-header">
                        <span className="help-card-name">{cmd.name}</span>
                        <span className={`help-badge ${category === "terminal" ? "help-badge-terminal" : "help-badge-app"}`}>
                          {category === "terminal" ? "Terminal" : "✓ In app"}
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
