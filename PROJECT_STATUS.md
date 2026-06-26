# AI Git Assistant — Project Status

> A desktop Git client where you describe what you want in plain English,
> review an exact plan of Git commands, and approve before anything changes.

---

## What the app can do today

### Architecture

| Layer | Technology |
|---|---|
| Desktop shell | Tauri 2 (Rust) |
| UI | React 18 + TypeScript + Vite |
| Backend service | Python 3.12 FastAPI sidecar (bundled via PyInstaller) |
| Persistence | SQLite — repositories survive app restarts |
| Git execution | System Git CLI via subprocess (no Git libraries) |
| Security | Session token per launch; React never touches the sidecar port directly |

---

### Repository management

- **Add an existing repo** — browse to any local Git working tree; it is registered and remembered.
- **Add a nested folder** — the app detects the parent repository root and registers that instead.
- **Initialise a new repo** — browse to a plain folder; the app offers to run `git init` with confirmation.
- All repositories are listed in the left sidebar and persist across sessions.

---

### Read operations (no approval needed, run instantly)

Type any of these in the chat input or use the quick-action buttons in the right panel:

| What you type | What the app runs |
|---|---|
| `what changed?` / `git status` | `git status` — staged, modified, untracked, conflicts |
| `show branches` | `git branch` — all local branches with upstream links |
| `last 5 commits` / `show log` | `git log -n5` — hash, author, date, subject |
| `show diff` / `show me the diff` | `git diff HEAD --stat` |
| `refresh remote status` / `fetch` | `git fetch --prune` — updates ahead/behind counts |

The right-hand context panel also shows live branch, ahead/behind, and recent commits at all times.

---

### Write operations (plan shown first, runs only after you click Approve)

Every write operation follows the same flow:

1. You describe what you want.
2. The app shows you an exact plan — the specific Git commands it will run, the files involved, the commit message.
3. Nothing changes until you click **Approve and execute**.
4. You can **Cancel** at any point before approval.

#### Stage files

```
stage src/login.py
stage src/login.py and src/auth.py
add frontend/src/Login.tsx
```

Runs: `git add -- <file> [<file> ...]`

Only files you name are staged. `git add .` and `all files` are blocked. Short filenames (`login.py`) resolve automatically to the full repository-relative path.

#### Commit

```
commit src/login.py with message "Add login validation"
commit Login.jsx and ResearchResults.jsx with message "Fix layout"
commit my changes with message "Fix layout"
commit all modified files with message "Fix layout"
commit staged changes with message "Fix edge case in token refresh"
```

`commit my changes` / `commit all modified files` stages every modified and untracked file automatically — no need to name them individually. All staged paths appear in the plan before anything runs.

#### Push

```
push
push current branch
push to main
```

Non-force only. For a branch with no upstream yet, the app automatically uses `--set-upstream` so tracking is configured for future pushes.

#### Commit then push in one step

```
commit Login.jsx with message "Hide LLM toggle", then push
commit my changes with message "Deploy hotfix", then push
```

Stage → commit → push as a single reviewed plan.

#### Pull

```
pull
sync with remote
git pull
```

Runs: `git pull --ff-only` — fast-forward only, never creates a merge commit. Blocked if the branch has diverged (ahead and behind at the same time). Shows INFO if already up to date.

#### Unstage files

```
unstage src/login.py
unstage login.py and auth.py
remove login.py from staging
```

Runs: `git restore --staged -- <files>` — moves files back out of the staging area without discarding the changes.

#### Discard changes

```
discard login.py
discard changes in login.py
```

Runs: `git restore -- <files>` — reverts the file to its last committed state. The plan displays a **DESTRUCTIVE** warning before you approve.

#### Switch branch

```
switch to main
checkout dev_1
switch to feature/auth
```

Runs: `git switch <branch>`. Blocked if there are staged or modified changes — stash or commit them first.

#### Create branch

```
create branch feature/auth
new branch feature/auth
```

Runs: `git switch -c <name>` — creates the branch from current HEAD and checks it out immediately.

#### Stash

```
stash
stash my changes
stash changes
stash with message "WIP login form"
```

Runs: `git stash push` — saves all staged and modified changes to the stash and restores the working tree to HEAD. Blocked if there is nothing to stash.

#### Pop stash

```
stash pop
restore stash
apply stash
```

Runs: `git stash pop` — restores the most recent stash entry and removes it from the stash list. Fails clearly if the stash is empty or applying would cause conflicts.

#### Delete branch

```
delete branch old-feature
remove branch old-feature
```

Runs: `git branch -d <name>` — safe delete only; fails if the branch has unmerged commits. Blocked if the target is the currently checked-out branch.

---

### Safety model

- **No force push.** The app never runs `git push --force`.
- **No cross-branch push.** You cannot push `main` to `dev_1` silently.
- **No `.`, `*`, or `all files`.** Every staged path must be named explicitly.
- **Fingerprint check.** If the repository state changes between when the plan was created and when you click Approve, the plan is rejected and you must request a new one.
- **No credential storage.** The app calls your system Git; Windows Git Credential Manager and SSH keys that already work in your terminal continue to work here.
- **No arbitrary shell access.** All Git calls are parameterised arrays — no shell string concatenation.

---

## What is not supported yet

| Not supported | Why deferred |
|---|---|
| `git merge` | Conflict resolution needs its own UI |
| `git rebase`, `cherry-pick` | Complex multi-step operations; Phase 3 scope |
| `git reset` | Destructive history rewrite; intentionally blocked |
| Force push | Intentionally blocked |
| Repos with submodules | Not supported |
| Bare repositories | Not supported |
| Linked worktrees | Not supported |

---

## Next tasks — planned work

### Next · LLM fallback for natural language

When the local regex planner does not recognise a request, fall back to an LLM that returns a structured plan — the same JSON shape the local planner produces — so the same approval UI works without changes.

- [ ] Provider abstraction layer (`LocalPlanner → LLMRouter`)
- [ ] **Claude (Anthropic)** integration — structured output via tool use
- [ ] **Ollama** integration — local model, no API key required
- [ ] **Groq** integration — fast cloud inference
- [ ] **OpenAI** integration
- [ ] Settings panel — pick provider, enter API key, stored via Tauri Stronghold (encrypted on disk)
- [ ] Prompt engineering — system prompt that explains the repo context (branch, changed files, recent commits) and constrains the model to return only safe, reviewable Git plans
- [ ] `externalLlmAllowed` toggle per repository — opt-in to sending repo context to external services

---

### Conversation history and context

- [ ] Persist chat transcripts to SQLite so history survives app restarts
- [ ] Show previous sessions in the sidebar
- [ ] Pass recent conversation turns as context when calling an LLM

---

### UI polish and packaging

- [ ] Clickable files in the context panel — click a modified file to append it to the chat input
- [ ] Keyboard shortcut to submit (Cmd/Ctrl + Enter)
- [ ] Copy button on command previews
- [ ] Full patch diff (line-by-line, not just stat summary)
- [ ] Syntax highlighting for diff output
- [ ] Sidecar log / diagnostic viewer (accessible from a menu)
- [ ] Windows NSIS installer signing
- [ ] macOS build and notarisation
- [ ] Linux AppImage build

---

## Running the app

```powershell
# First time or after changing Python source
npm run sidecar:build

# Run tests
npm run sidecar:test

# Start in development mode
npm run tauri:dev
```

Requirements: Node 20+, Rust stable, Python 3.12+, Git 2.39+.

---

## Test coverage

| Suite | Tests | What is covered |
|---|---|---|
| `test_action_planner.py` | 33 | Plan creation for all write commands; all Phase 2 commands; set-upstream; no-remote/multi-remote errors; short filename resolution; "commit my changes" path |
| `test_repository_flow.py` | 16 | Registration, classification, read actions, execute-plan end-to-end for commit+push (upstream and set-upstream), standalone push, pull, create+switch branch, plan cancel |

Run with `npm run sidecar:test` (installs dependencies and runs pytest automatically).
