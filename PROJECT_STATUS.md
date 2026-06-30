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
- **Clone a remote repo** — enter a Git remote URL and choose a local parent folder; the clone is registered automatically.
- All repositories are listed in the left sidebar and persist across sessions.

---

### Read operations (no approval needed, run instantly)

Type any of these in the chat input or use the quick-action buttons in the right panel:

| What you type | What the app runs |
|---|---|
| `what changed?` / `git status` | `git status` — staged, modified, untracked, conflicts |
| `show branches` | `git branch` — all local branches with upstream links |
| `last 5 commits` / `show log` | `git log -n5` — hash, author, date, subject |
| `show diff` / `show me the diff` | `git diff HEAD --patch` - full patch diff with line highlighting |
| `show commit graph` | `git log --graph --decorate --oneline --all` |
| `show stashes` / `inspect stash@{0}` | `git stash list` / `git stash show --patch` |
| `show remotes` | `git remote -v` |
| `history README.md` / `blame README.md` | `git log --follow` / `git blame` for one file |
| `show conflicts` | Conflicted files, conflict marker snippets, and next-step guidance |
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

#### Inspect, apply, and drop stash entries

```
show stashes
inspect stash@{0}
apply stash stash@{0}
drop stash stash@{0}
```

`show stashes` and `inspect stash@{0}` are read-only. Applying or dropping a specific stash entry uses the normal reviewed plan flow. `drop stash` is shown as **DESTRUCTIVE** before approval.

#### Delete branch

```
delete branch old-feature
remove branch old-feature
```

Runs: `git branch -d <name>` — safe delete only; fails if the branch has unmerged commits. Blocked if the target is the currently checked-out branch.

---

#### Merge and resolve conflicts

```
merge feature/auth
show conflicts
stage README.md
continue merge
abort merge
```

Runs: `git merge --no-edit <branch>` from a clean working tree. If conflicts occur, the app shows conflicted files and marker snippets, allows staging resolved conflicted files, and can either complete the merge with `git commit --no-edit` or abort with `git merge --abort`.

### LLM fallback and settings

Phase A includes the AI fallback layer. If the local planner cannot recognise a request, and the selected repository has external AI enabled, the app can call a configured provider and validate the returned structured Git plan before showing the same approval UI.

- Supported provider configurations: Anthropic, Gemini, OpenAI, Groq, and Ollama.
- LLM plans reuse the same `LocalActionPlan` schema as local plans.
- LLM output is validated before approval: unknown actions, unsafe wildcard paths, invalid remotes, empty commits, and overlong plans are rejected.
- Each repository has its own external AI opt-in toggle.
- API keys are encrypted with Windows DPAPI before local storage and are never returned by the settings API.

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
| `git rebase`, `cherry-pick` | Complex multi-step operations; Phase 3 scope |
| `git reset` | Destructive history rewrite; intentionally blocked |
| Force push | Intentionally blocked |
| Repos with submodules | Not supported |
| Bare repositories | Not supported |
| Linked worktrees | Not supported |

---

## Phase B release hardening - complete

Phase A is complete and has already been published as a Windows installer. Phase B makes future releases repeatable, trustworthy, and easier to support.

- [x] Produce a repeatable Windows release build: sidecar binary, frontend build, Tauri NSIS installer.
- [x] Verify clean install on a Windows machine without Python, Node.js, or Rust.
- [x] Fix the Windows pytest temp/cache permission issue so integration tests can run reliably.
- [x] Move API key storage from plaintext SQLite to OS keychain or another encrypted local secret store.
- [x] Add an in-app diagnostics view: sidecar status, Git version, DB path, provider status, and recent local errors.
- [x] Add a local sidecar log viewer/export for bug reports.
- [x] Reconcile public docs and release notes with Phase A reality: LLM fallback is shipped, packaging exists, and remaining work is Phase B+.
- [x] Decide whether to sign the Windows installer before the next public release.

---

## Next product phases

### Phase C - Git client parity - complete

- [x] Visual commit graph.
- [x] Full patch diff with syntax highlighting.
- [x] File history and blame.
- [x] Stash list with inspect/apply/drop actions.
- [x] Remote management UI.
- [x] Merge/conflict detection and guided conflict workflow.

### Phase D - AI-native Git workflows

- [ ] AI commit message generation from staged diff.
- [ ] AI commit composer that splits mixed work into logical commits.
- [ ] Branch, file, and PR-ready change summaries.
- [ ] Risk scoring before approval.
- [ ] Privacy receipt showing exactly what context was sent to an external provider.

### Phase E - Agent worktree control plane

- [ ] Create isolated worktrees for agent tasks.
- [ ] Track agent sessions by branch, worktree, changed files, commits, tests, and status.
- [ ] Compare agent outputs side by side.
- [ ] Review, merge, abandon, or clean up agent work from the app.

### Phase F - PR and review workflow

- [ ] GitHub integration first.
- [ ] Create PRs from current branch.
- [ ] AI-generated PR title/body/checklist from commits and diff.
- [ ] CI status and review comment display.
- [ ] Review-response workflow.

---

## Running the app

```powershell
# First time or after changing Python source
npm run sidecar:build

# Run tests after dependencies are installed
npm run sidecar:test

# First-time test dependency install, if needed
npm run sidecar:test:install

# Start in development mode
npm run tauri:dev
```

Requirements: Node 20+, Rust stable, Python 3.12+, Git 2.39+.

---

## Test coverage

| Suite | Tests | What is covered |
|---|---|---|
| `test_action_planner.py` | 39 | Local plan creation for read/write commands; push safety; short filename resolution; selected/all/staged commit paths; Phase C stash/read/merge commands |
| `test_settings_service.py` | 7 | LLM settings defaults, updates, API key persistence, and API key redaction |
| `test_llm_validator.py` | 12 | LLM step validation, safe path checks, remote validation, supported action kinds |
| `test_health.py` | 2 | Authenticated sidecar health checks and protocol version |
| `test_repository_flow.py` | 22 | Repository registration/classification, read actions, execute-plan flows, push/pull, branch creation, plan cancel, Phase C diff/graph/stash/remote/history/blame/merge flows |

Current verified sidecar suite: 85 passing tests via `npm run sidecar:test`.
