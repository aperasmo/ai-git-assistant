import React, { useState } from "react";

// ---- design tokens ----
const c = {
  bg: "#0B0D10",
  panel: "#14171C",
  panelAlt: "#1A1E24",
  panelRaised: "#1F242B",
  border: "#252A32",
  borderLight: "#2E343D",
  text: "#E8EAED",
  textMuted: "#8A92A0",
  textFaint: "#565D68",
  accent: "#34D399",
  accentDim: "rgba(52,211,153,0.12)",
  blue: "#3B82F6",
  blueDim: "#2C5BB8",
  warn: "#F2A93B",
  warnDim: "rgba(242,169,59,0.14)",
  danger: "#EF6E5B",
  dangerDim: "rgba(239,110,91,0.14)",
  success: "#34D399",
  successDim: "rgba(52,211,153,0.10)",
};

const mono = '"JetBrains Mono","SF Mono","Fira Code",ui-monospace,monospace';
const sans = '"Inter",-apple-system,"Segoe UI",sans-serif';

const REPOS = [
  { id: "glaucoma", name: "GlaucomaAI", path: "~/Projects/GlaucomaAI", branch: "feature/reports", color: "#8B5CF6", letter: "G", active: true },
  { id: "gitassist", name: "AI Git Assistant", path: "~/Projects/AI-Git-Assistant", branch: "main", color: "#34D399", letter: "A", active: false },
  { id: "website", name: "Personal Website", path: "~/Projects/Personal-Website", branch: "main", color: "#22C55E", letter: "P", active: false },
  { id: "devops", name: "DevOps Scripts", path: "~/Projects/DevOps-Scripts", branch: "dev", color: "#EC4899", letter: "D", active: false },
];

const CONVERSATIONS = [
  { title: "Commit and push feature/reports", time: "2m ago", active: true },
  { title: "What changed in last 3 commits?", time: "1h ago" },
  { title: "Show me the diff", time: "Yesterday" },
  { title: "Switch to develop branch", time: "2 days ago" },
  { title: "Stash my changes", time: "2 days ago" },
];

const RECENT_COMMITS = [
  { hash: "7f3a2c1", msg: "Update report generation logic", who: "Allan P.", when: "2 hours ago" },
  { hash: "a1b2c3d", msg: "Fix data mapping issues", who: "Allan P.", when: "5 hours ago" },
  { hash: "c4d5e6f", msg: "Add new visualizations", who: "Allan P.", when: "Yesterday" },
  { hash: "d7e8f9a", msg: "Improve model evaluation", who: "Allan P.", when: "2 days ago" },
];

function RiskBadge({ level }) {
  const map = {
    SAFE: { bg: c.successDim, fg: c.success },
    LOW: { bg: c.successDim, fg: c.success },
    MEDIUM: { bg: c.warnDim, fg: c.warn },
    HIGH: { bg: c.dangerDim, fg: c.danger },
  };
  const s = map[level] || map.MEDIUM;
  return (
    <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: "0.04em", background: s.bg, color: s.fg, padding: "3px 9px", borderRadius: 5 }}>
      {level}
    </span>
  );
}

function StatRow({ icon, label, value, tone }) {
  const toneColor = tone === "warn" ? c.warn : tone === "danger" ? c.danger : tone === "accent" ? c.accent : c.textMuted;
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: c.textMuted }}>
        <span style={{ width: 14, textAlign: "center", fontSize: 12 }}>{icon}</span>
        {label}
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color: toneColor, background: c.panelRaised, padding: "1px 8px", borderRadius: 10, minWidth: 20, textAlign: "center" }}>
        {value}
      </span>
    </div>
  );
}

export default function GitAssistantMockupV2() {
  const [actionApproved, setActionApproved] = useState(false);
  const [actionCancelled, setActionCancelled] = useState(false);
  const [input, setInput] = useState("");
  const [repoPickerOpen, setRepoPickerOpen] = useState(false);
  const [branchPickerOpen, setBranchPickerOpen] = useState(false);
  const [activeRepoId, setActiveRepoId] = useState("glaucoma");
  const activeRepo = REPOS.find((r) => r.id === activeRepoId);

  return (
    <div style={{ background: c.bg, color: c.text, fontFamily: sans, height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Top bar */}
      <div style={{ display: "flex", alignItems: "center", padding: "12px 18px", borderBottom: `1px solid ${c.border}`, gap: 14, flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 6, marginRight: 4 }}>
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#EF6E5B" }} />
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#F2A93B" }} />
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#34D399" }} />
        </div>
        <div style={{ fontSize: 15, fontWeight: 700 }}>AI Git Assistant</div>
        <span style={{ fontSize: 10, fontWeight: 700, color: c.textFaint, border: `1px solid ${c.border}`, borderRadius: 5, padding: "2px 7px" }}>BETA</span>

        {/* repo picker */}
        <div style={{ position: "relative", marginLeft: 18 }}>
          <button
            onClick={() => { setRepoPickerOpen((v) => !v); setBranchPickerOpen(false); }}
            style={{ display: "flex", alignItems: "center", gap: 8, background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 8, padding: "7px 12px", color: c.text, fontSize: 13, cursor: "pointer" }}
          >
            <span style={{ width: 18, height: 18, borderRadius: 5, background: activeRepo.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800 }}>{activeRepo.letter}</span>
            {activeRepo.name}
            <span style={{ color: c.textFaint, fontSize: 9 }}>▼</span>
          </button>
          {repoPickerOpen && (
            <div style={{ position: "absolute", top: "110%", left: 0, width: 230, background: c.panelRaised, border: `1px solid ${c.borderLight}`, borderRadius: 8, zIndex: 20, boxShadow: "0 12px 28px rgba(0,0,0,0.5)", overflow: "hidden" }}>
              {REPOS.map((r) => (
                <div key={r.id} onClick={() => { setActiveRepoId(r.id); setRepoPickerOpen(false); }}
                  style={{ display: "flex", alignItems: "center", gap: 9, padding: "9px 12px", cursor: "pointer", background: r.id === activeRepoId ? c.accentDim : "transparent", borderBottom: `1px solid ${c.border}` }}>
                  <span style={{ width: 16, height: 16, borderRadius: 4, background: r.color, flexShrink: 0 }} />
                  <span style={{ fontSize: 12.5 }}>{r.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* branch picker */}
        <div style={{ position: "relative" }}>
          <button
            onClick={() => { setBranchPickerOpen((v) => !v); setRepoPickerOpen(false); }}
            style={{ display: "flex", alignItems: "center", gap: 7, background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 8, padding: "7px 12px", color: c.text, fontSize: 13, fontFamily: mono, cursor: "pointer" }}
          >
            🌿 {activeRepo.branch}
            <span style={{ color: c.textFaint, fontSize: 9 }}>▼</span>
          </button>
          {branchPickerOpen && (
            <div style={{ position: "absolute", top: "110%", left: 0, width: 180, background: c.panelRaised, border: `1px solid ${c.borderLight}`, borderRadius: 8, zIndex: 20, boxShadow: "0 12px 28px rgba(0,0,0,0.5)" }}>
              {["feature/reports", "main", "develop"].map((b) => (
                <div key={b} style={{ padding: "8px 12px", fontSize: 12, fontFamily: mono, cursor: "pointer", color: b === activeRepo.branch ? c.accent : c.text }}>{b}</div>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
          <button style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", color: c.textMuted, fontSize: 13, cursor: "pointer" }}>
            ＋ New Chat
          </button>
          <button style={{ display: "flex", alignItems: "center", gap: 6, background: "transparent", border: "none", color: c.textMuted, fontSize: 13, cursor: "pointer" }}>
            ⚙ Settings
          </button>
          <span style={{ width: 30, height: 30, borderRadius: "50%", background: c.blueDim, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>AP</span>
        </div>
      </div>

      {/* Body: 3 panes */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* LEFT: repositories + conversations */}
        <div style={{ width: 270, borderRight: `1px solid ${c.border}`, display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ padding: "16px 16px 10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint }}>REPOSITORIES</span>
              <button style={{ fontSize: 11, color: c.textMuted, background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 6, padding: "3px 9px", cursor: "pointer" }}>+ Add</button>
            </div>
            <input placeholder="Filter repositories..." style={{ width: "100%", background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 7, padding: "7px 10px", fontSize: 12.5, color: c.text, outline: "none", boxSizing: "border-box" }} />
          </div>

          <div style={{ padding: "4px 10px", overflowY: "auto" }}>
            {REPOS.map((r) => (
              <div key={r.id} onClick={() => setActiveRepoId(r.id)}
                style={{ display: "flex", gap: 10, padding: "9px 8px", borderRadius: 8, cursor: "pointer", marginBottom: 2, background: r.id === activeRepoId ? c.panelAlt : "transparent", border: `1px solid ${r.id === activeRepoId ? c.borderLight : "transparent"}` }}>
                <span style={{ width: 30, height: 30, borderRadius: 7, background: r.color + "26", color: r.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, flexShrink: 0 }}>{r.letter}</span>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.name}</div>
                  <div style={{ fontSize: 10.5, color: c.textFaint, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.path}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 3 }}>
                    <span style={{ fontSize: 10, color: c.textMuted, fontFamily: mono }}>🌿 {r.branch}</span>
                    {r.id === activeRepoId && <span style={{ width: 5, height: 5, borderRadius: "50%", background: c.accent, marginLeft: "auto" }} />}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ padding: "16px 16px 8px", borderTop: `1px solid ${c.border}`, marginTop: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint }}>RECENT CONVERSATIONS</span>
          </div>
          <div style={{ padding: "0 10px", overflowY: "auto", flex: 1 }}>
            {CONVERSATIONS.map((conv, i) => (
              <div key={i} style={{ padding: "9px 10px", borderRadius: 8, cursor: "pointer", background: conv.active ? c.accentDim : "transparent", marginBottom: 2 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 12, color: conv.active ? c.text : c.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{conv.title}</span>
                </div>
                <span style={{ fontSize: 10, color: c.textFaint }}>{conv.time}</span>
              </div>
            ))}
          </div>

          <div style={{ padding: 14, borderTop: `1px solid ${c.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: c.accent }} />
              <span style={{ fontSize: 12, color: c.textMuted }}>Ollama (Local)</span>
            </div>
            <span style={{ fontSize: 13, color: c.textFaint, cursor: "pointer" }}>⚙</span>
          </div>
        </div>

        {/* CENTER: chat */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={{ flex: 1, overflowY: "auto", padding: "22px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
            {/* user message */}
            <div style={{ alignSelf: "flex-end", maxWidth: "62%" }}>
              <div style={{ background: c.blue, color: "#fff", padding: "10px 14px", borderRadius: "12px 12px 2px 12px", fontSize: 13.5 }}>
                Commit my staged files and push to origin.
              </div>
              <div style={{ textAlign: "right", fontSize: 10, color: c.textFaint, marginTop: 4 }}>10:24 AM ✓</div>
            </div>

            {/* assistant analysis */}
            <div style={{ alignSelf: "flex-start", maxWidth: "82%", display: "flex", gap: 10 }}>
              <span style={{ width: 26, height: 26, borderRadius: "50%", background: c.panelRaised, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0 }}>🤖</span>
              <div>
                <p style={{ margin: "2px 0 10px", fontSize: 13.5, lineHeight: 1.6 }}>
                  I'll commit your staged files and push them to the remote repository.<br />Here's what I found:
                </p>
                <div style={{ background: c.panel, border: `1px solid ${c.border}`, borderRadius: 10, padding: "12px 14px", fontSize: 12.5, lineHeight: 1.9, color: c.textMuted, fontFamily: mono }}>
                  <div><b style={{ color: c.text }}>Repository:</b> {activeRepo.name}</div>
                  <div><b style={{ color: c.text }}>Current Branch:</b> {activeRepo.branch}</div>
                  <div><b style={{ color: c.text }}>Staged Files:</b> 3</div>
                  <div><b style={{ color: c.text }}>Remote:</b> origin/{activeRepo.branch}</div>
                  <div><b style={{ color: c.text }}>Status:</b> 2 commits ahead of origin/{activeRepo.branch}</div>
                </div>
                <p style={{ fontSize: 13.5, margin: "10px 0" }}>I'll proceed with committing your staged files, then pushing to origin.</p>

                {/* Planned Actions card */}
                <div style={{ background: c.panel, border: `1px solid ${c.border}`, borderRadius: 10, overflow: "hidden" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderBottom: `1px solid ${c.border}`, background: c.panelAlt, fontSize: 12.5, fontWeight: 700 }}>
                    📋 Planned Actions
                  </div>
                  <div style={{ padding: "12px 14px", display: "flex", flexDirection: "column", gap: 14 }}>
                    <div style={{ display: "flex", gap: 12 }}>
                      <span style={{ width: 20, height: 20, borderRadius: "50%", background: c.panelRaised, fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>1</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontFamily: mono, fontSize: 12.5, color: c.accent }}>git_commit</span>
                          <RiskBadge level="MEDIUM" />
                        </div>
                        <div style={{ fontSize: 12, color: c.textMuted, marginTop: 4 }}>
                          Message: "Update report generation logic and fix data mappings"<br />Files: 3 staged files
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 12 }}>
                      <span style={{ width: 20, height: 20, borderRadius: "50%", background: c.panelRaised, fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>2</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontFamily: mono, fontSize: 12.5, color: c.accent }}>git_push</span>
                          <RiskBadge level="HIGH" />
                        </div>
                        <div style={{ fontSize: 12, color: c.textMuted, marginTop: 4 }}>
                          Remote: origin · Branch: {activeRepo.branch} · Force: false
                        </div>
                      </div>
                    </div>
                  </div>

                  {!actionApproved && !actionCancelled && (
                    <div style={{ display: "flex", gap: 8, padding: "12px 14px 14px" }}>
                      <button onClick={() => setActionApproved(true)} style={{ flex: 1, background: c.accent, border: "none", color: "#06140F", fontWeight: 700, fontSize: 12.5, padding: "9px 0", borderRadius: 7, cursor: "pointer" }}>✓ Approve & Execute</button>
                      <button style={{ background: c.panelAlt, border: `1px solid ${c.border}`, color: c.textMuted, fontSize: 12.5, padding: "9px 14px", borderRadius: 7, cursor: "pointer" }}>✎ Edit</button>
                      <button onClick={() => setActionCancelled(true)} style={{ background: c.panelAlt, border: `1px solid ${c.danger}55`, color: c.danger, fontSize: 12.5, padding: "9px 14px", borderRadius: 7, cursor: "pointer" }}>✕ Cancel</button>
                    </div>
                  )}
                </div>

                {!actionApproved && !actionCancelled && (
                  <p style={{ fontSize: 13, color: c.textMuted, margin: "10px 0 0" }}>Should I proceed with these actions? <span style={{ fontSize: 10, color: c.textFaint }}>10:24 AM</span></p>
                )}
              </div>
            </div>

            {actionApproved && (
              <>
                <div style={{ alignSelf: "flex-end", maxWidth: "40%" }}>
                  <div style={{ background: c.blue, color: "#fff", padding: "9px 14px", borderRadius: "12px 12px 2px 12px", fontSize: 13.5 }}>Yes, proceed.</div>
                </div>
                <div style={{ alignSelf: "flex-start", maxWidth: "82%", display: "flex", gap: 10 }}>
                  <span style={{ width: 26, height: 26, borderRadius: "50%", background: c.panelRaised, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0 }}>🤖</span>
                  <div style={{ background: c.successDim, border: `1px solid ${c.accent}40`, borderRadius: 10, padding: "12px 14px", fontSize: 13 }}>
                    <div style={{ color: c.accent, fontWeight: 700, marginBottom: 6 }}>✓ Success</div>
                    <div style={{ color: c.textMuted, marginBottom: 6 }}>All actions completed successfully.</div>
                    <div style={{ fontFamily: mono, fontSize: 12, color: c.textMuted, lineHeight: 1.7 }}>
                      • Commit: 7f3a2c1 — Update report generation logic<br />
                      • Push: {activeRepo.branch} → origin/{activeRepo.branch} (2 commits pushed)
                    </div>
                  </div>
                </div>
              </>
            )}

            {actionCancelled && (
              <div style={{ alignSelf: "flex-start", maxWidth: "82%", display: "flex", gap: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: "50%", background: c.panelRaised, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0 }}>🤖</span>
                <div style={{ background: c.panel, border: `1px solid ${c.border}`, borderRadius: 10, padding: "10px 14px", fontSize: 13, color: c.textMuted }}>
                  Cancelled. No changes made.
                </div>
              </div>
            )}
          </div>

          <div style={{ padding: "12px 24px 10px", borderTop: `1px solid ${c.border}` }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center", background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 10, padding: "8px 8px 8px 14px" }}>
              <span style={{ color: c.textFaint, fontSize: 14 }}>+</span>
              <span style={{ color: c.textFaint, fontSize: 14 }}>📎</span>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask me anything about your Git repository..."
                style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: c.text, fontSize: 13.5 }}
              />
              <button style={{ background: c.blue, border: "none", color: "#fff", width: 32, height: 32, borderRadius: 8, cursor: "pointer", fontSize: 14 }}>➤</button>
            </div>
            <div style={{ textAlign: "center", fontSize: 10.5, color: c.textFaint, marginTop: 8 }}>
              Tip: Try "show last 5 commits" or "what changed?"
            </div>
          </div>
        </div>

        {/* RIGHT: repository context */}
        <div style={{ width: 280, borderLeft: `1px solid ${c.border}`, padding: "16px 16px", overflowY: "auto", flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint }}>REPOSITORY CONTEXT</span>
            <span style={{ color: c.textFaint, fontSize: 13, cursor: "pointer" }}>⟳</span>
          </div>

          <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 2 }}>{activeRepo.name}</div>
          <div style={{ fontSize: 11, color: c.textFaint, fontFamily: mono, marginBottom: 10 }}>{activeRepo.path}</div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 8, padding: "8px 10px", marginBottom: 18 }}>
            <span style={{ fontFamily: mono, fontSize: 12, color: c.text }}>🌿 {activeRepo.branch}</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: c.success, background: c.successDim, padding: "2px 8px", borderRadius: 5 }}>AHEAD 2</span>
          </div>

          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint, marginBottom: 4 }}>STATUS SUMMARY</div>
          <div style={{ borderTop: `1px solid ${c.border}` }}>
            <StatRow icon="◧" label="Staged Changes" value={3} tone="accent" />
            <StatRow icon="✎" label="Modified Files" value={4} tone="warn" />
            <StatRow icon="↑" label="Untracked Files" value={1} />
            <StatRow icon="⚠" label="Conflicts" value={0} />
            <StatRow icon="↓" label="Behind Remote" value={0} />
            <StatRow icon="↓" label="Ahead Remote" value={2} tone="accent" />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "18px 0 4px" }}>
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint }}>RECENT COMMITS</span>
            <span style={{ fontSize: 11, color: c.blue, cursor: "pointer" }}>View all</span>
          </div>
          <div style={{ borderTop: `1px solid ${c.border}` }}>
            {RECENT_COMMITS.map((commit, i) => (
              <div key={i} style={{ display: "flex", gap: 8, padding: "9px 0", borderBottom: i < RECENT_COMMITS.length - 1 ? `1px solid ${c.border}` : "none" }}>
                <span style={{ fontSize: 11, marginTop: 1 }}>🔗</span>
                <div>
                  <div style={{ fontSize: 11.5 }}><span style={{ fontFamily: mono, color: c.accent }}>{commit.hash}</span> <span style={{ color: c.text }}>{commit.msg}</span></div>
                  <div style={{ fontSize: 10, color: c.textFaint }}>{commit.who} · {commit.when}</div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", color: c.textFaint, margin: "18px 0 8px" }}>QUICK ACTIONS</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[["⚡", "Git Status"], ["📄", "View Diff"], ["🌿", "Branches"], ["📦", "Stash Changes"]].map(([icon, label]) => (
              <button key={label} style={{ display: "flex", alignItems: "center", gap: 6, background: c.panelAlt, border: `1px solid ${c.border}`, borderRadius: 8, padding: "9px 10px", color: c.textMuted, fontSize: 11.5, cursor: "pointer" }}>
                <span style={{ fontSize: 12 }}>{icon}</span>{label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
