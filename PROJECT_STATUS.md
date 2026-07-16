# AI Git Assistant — Project Status

> A desktop Git client where you describe what you want in plain English,
> review an exact plan of Git commands, and approve before anything changes.

Last updated: 17/07/2026

---

## What the app can do today

### Versioning policy

Versions track the active product phase so releases are easy to understand:

| Phase | Version line | Meaning |
|---|---|---|
| Phase 1 | `0.1.x` | MVP local Git assistant |
| Phase 2 | `0.2.x` | Release hardening and installer reliability |
| Phase 3 | `0.3.x` | Git client parity |
| Phase 4 | `0.4.x` | AI-native Git workflows |
| Phase 5 | `0.5.x` | Workflow polish and agent worktree control plane |
| Phase 6 | `0.6.x` | PR and review workflow |
| Phase 7 | `0.7.x` | Cross-platform release |
| Phase 8 | `0.8.x` | Team context and conventions |

The first release in a phase uses `.0`; sub-phase improvements stay inside the same phase line, so Phase 6 starts at `0.6.0`.

### Dated phase history

These dates mark when the phase or feature set was first added to the project history.

#### Phase 1 - 27/06/2026

1. Added the MVP local Git assistant with repository registration and reviewed Git actions.
2. Added onboarding, command bar flow, command help, and LLM integration/testing.
3. Published the initial Windows installer line for Phase 1.

#### Phase 2 - 30/06/2026

1. Completed release hardening for repeatable sidecar, frontend, and Tauri installer builds.
2. Added encrypted local secret storage, diagnostics, and support logging.
3. Stabilized Windows test/build workflows and updated public release docs.

#### Phase 3 - 30/06/2026

1. Added Git client parity features: commit graph, full diff, file history, blame, stash, remotes, merge/conflict guidance, and tags.
2. Added guided conflict resolution flows for continue/abort merge.
3. Updated command references and status docs for the Git client parity release.

#### Phase 4 - 03/07/2026

1. Started AI-native Git workflows and updated the app phase label.
2. Added release tag workflow support and repository provider awareness foundations.
3. Added GitHub release publishing flow with provider-specific gating.

#### Phase 4.4 - 04/07/2026

1. Added premium AI commit-message composer styles: Detailed, Concise, Conventional, and Release.
2. Added richer grouped diff context, detected scope, confidence, and alternate subjects.
3. Updated tests, docs, and installer metadata for the commit composer release.

#### Phase 5 - 07/07/2026

1. Added the agent worktree control plane.
2. Added session tracking, compare, merge, abandon, and cleanup controls.
3. Added workflow-style Help and stronger read-only request guarding.

#### Phase 6 - 10/07/2026

1. Added GitHub draft pull request creation from the current branch.
2. Added GitLab draft merge request creation from the current branch.
3. Added AI-generated PR/MR title, body, and checklist drafts from branch comparison context.
4. Added provider, branch, conflict, push, and remote-visibility readiness checks.
5. Updated GitHub and GitLab token guidance.

#### Phase 6.2 - 13/07/2026

1. Added Review status as a read-only PR/MR visibility command.
2. Added GitHub PR and GitLab MR CI/check status, review summary, comment count, and recent comment display.
3. Guarded review-status requests so they resolve locally as read actions instead of falling through to write-plan AI fallback.

#### Phase 7 - 14/07/2026

1. Started the cross-platform release line at `0.7.0`.
2. Replaced Windows-only npm sidecar build/test commands with portable Node scripts.
3. Added platform-aware sidecar binary naming and explicit Windows/macOS/Linux Tauri bundle commands.
4. Added non-Windows sidecar shutdown handling through the Tauri shell child process.

#### Phase 7.1 - 15/07/2026

1. Added Ubuntu 20.04 compatibility for Git versions that do not support `git init -b`.
2. Fixed repository common-dir resolution on older Git so normal repositories are not mistaken for linked worktrees.
3. Added non-Windows portable local secret storage for AI and provider tokens.
4. Added Python command autodetection for sidecar build/test scripts.

#### Phase 7.2 - 15/07/2026

1. Added a visible Gitignore Assistant action for selected untracked files in file-pick wizard steps.
2. Limited ignore writes to untracked files and listed the exact `.gitignore` entries written.
3. De-duplicated `.gitignore` entries across existing file content and the current request.
4. Verified Ubuntu 22.04 Linux `.deb` packaging after sidecar tests and sidecar build passed.

#### Phase 7.3 - 16/07/2026

1. Added Git Author Identity settings for global Git `user.name` and `user.email`.
2. Improved Settings with a wider two-column layout and scrollable small-screen behavior for Linux VMs.
3. Auto-closes the ignore-file wizard step when ignored files leave no remaining changed files to choose.
4. Updated public docs and metadata for `0.7.3`.

#### Phase 7.4 - 16/07/2026

1. Added Guided Recovery / Next Step Assistant cards for common Git blockers.
2. Added a reviewed `set_upstream` plan so branches can track `origin/main` or the current branch remote from inside the app.
3. Added recovery guidance for no upstream, existing remote setup, missing Git author identity, and accidentally selecting the app data repository.
4. Updated public docs and metadata for `0.7.4`.

#### Phase 7.5 - 16/07/2026

1. Added GitHub push-auth recovery when the remote rejects a push because the token lacks repository write permission.
2. Added a push-only retry action so an already-created local commit can be pushed without creating another commit.
3. Updated Settings guidance to call out fine-grained GitHub token repository access and `Contents: Read and write`.
4. Updated public docs and metadata for `0.7.5`.

#### Phase 7.6 - 16/07/2026

1. Added Guided Recovery for fast-forward pull failures when local and remote branches have diverged.
2. Added recovery actions to fetch remote state, view differences, or merge the upstream branch deliberately.
3. Allowed reviewed merge plans for remote-tracking branches such as `origin/main`.
4. Added a one-command installer build wrapper for the current host OS.
5. Improved the GitHub draft release flow with existing-tag selection, create-new-tag entry, a larger markdown release description editor, and multiple installer assets.
6. Updated public docs and metadata for `0.7.6`.

#### Phase 8 - target TBD

1. Planned team context and conventions.
2. Planned repo-local style profiles and AI context receipts.
3. Planned team-aware commit messages, PR summaries, release notes, and branch naming.

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
| `show tags` / `show tag v0.3.0` | `git tag --list` / `git show --stat <tag>` |
| `history README.md` / `blame README.md` | `git log --follow` / `git blame` for one file |
| `show conflicts` | Conflicted files, conflict marker snippets, and next-step guidance |
| `review status` / `PR status` / `MR status` | GitHub/GitLab provider API read for current branch PR/MR CI, reviews, and comments |
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

#### Release tags

```
show tags
show tag v0.3.0
create tag v0.3.0 with message "Release v0.3.0"
push tag v0.3.0
delete tag v0.3.0
```

Tag reads run instantly. Tag writes use the normal reviewed plan flow: create annotated local tags, push one explicit tag to a known remote, or delete a local tag with a **DESTRUCTIVE** warning.

### LLM fallback and settings

Phase 1 includes the AI fallback layer. If the local planner cannot recognise a request, and the selected repository has external AI enabled, the app can call a configured provider and validate the returned structured Git plan before showing the same approval UI.

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
| `git revert <commit>` | Safe undo-by-new-commit workflow; planned for a future reviewed app flow |
| `git reset` | Destructive history rewrite; intentionally blocked |
| Force push | Intentionally blocked |
| Repos with submodules | Not supported |
| Bare repositories | Not supported |
| Linked worktrees | Not supported |

---

## Phase 2 release hardening - complete (30/06/2026)

Phase 1 is complete and has already been published as a Windows installer. Phase 2 makes future releases repeatable, trustworthy, and easier to support.

- [x] Produce a repeatable Windows release build: sidecar binary, frontend build, Tauri NSIS installer.
- [x] Verify clean install on a Windows machine without Python, Node.js, or Rust.
- [x] Fix the Windows pytest temp/cache permission issue so integration tests can run reliably.
- [x] Move API key storage from plaintext SQLite to OS keychain or another encrypted local secret store.
- [x] Add an in-app diagnostics view: sidecar status, Git version, DB path, provider status, and recent local errors.
- [x] Add a local sidecar log viewer/export for bug reports.
- [x] Reconcile public docs and release notes with Phase 1 reality: LLM fallback is shipped, packaging exists, and remaining work is Phase 2+.
- [x] Decide whether to sign the Windows installer before the next public release.

---

## Next product phases

### Phase 3 - Git client parity - complete (30/06/2026)

- [x] Visual commit graph.
- [x] Full patch diff with syntax highlighting.
- [x] File history and blame.
- [x] Stash list with inspect/apply/drop actions.
- [x] Remote management UI.
- [x] Merge/conflict detection and guided conflict workflow.
- [x] Release tag list/inspect/create/delete/push workflow.

### Phase 4 - AI-native Git workflows - complete (03/07/2026)

- [x] AI commit message generation from selected commit wizard diff, including consolidated subject/body drafts for multi-file changes.
- [x] AI commit composer that splits mixed work into logical commits.
- [x] Branch, file, and PR-ready change summaries.
- [x] Risk scoring before approval.
- [x] Privacy receipt showing exactly what context was sent to an external provider.

### Phase 4.1 - GitHub release publisher - complete (03/07/2026)

- [x] Store a GitHub release token encrypted in local settings.
- [x] Detect GitHub owner/repo from the configured remote URL.
- [x] Guide the user through tag, title, description, asset selection, and final confirmation.
- [x] Create a GitHub draft release and upload one installer asset after explicit approval.
- [x] Return release URL, asset URL, and SHA-256 checksum in the transcript.

### Phase 4.3 - Repository provider awareness - complete (03/07/2026)

- [x] Detect remote providers per selected repository from configured remote URLs.
- [x] Label GitHub, GitLab, Bitbucket, Azure DevOps, unknown, local-only, and mixed-provider repositories in the right panel.
- [x] Keep standard Git workflows provider-neutral for GitHub, GitLab, Bitbucket, Azure DevOps, self-hosted, and local remotes.
- [x] Guard GitHub-only draft release publishing with a provider-specific message when the selected repo is not GitHub-backed.
- [x] Use provider awareness as the foundation for Phase 6 multi-provider PR/MR work.

### Phase 4.4 - Premium commit message composer - complete (04/07/2026)

- [x] Add commit-message style modes: Detailed, Concise, Conventional, and Release.
- [x] Enrich AI commit context with grouped paths, file status, diff stats, detected domains, and recent commit subjects.
- [x] Return confidence, detected scope, and alternate subjects with the generated commit draft.
- [x] Show richer commit draft controls in the wizard while keeping the final commit message editable.

### Phase 5 - Agent worktree control plane (07/07/2026)

- [x] Show execution feedback while approved plans are running.
- [x] Replace the flat command reference with a workflow-style Git cheat sheet grouped by setup, snapshot, branch, sharing, inspect, and advanced safety workflows.
- [x] Prevent read-shaped requests such as `git logs last 5` from falling through into AI-generated write plans.
- [x] Create isolated worktrees for agent tasks.
- [x] Track agent sessions by branch, worktree, changed files, commits ahead, latest commit, and status.
- [x] Compare agent outputs against the base branch with commits, changed files, diff stat, and worktree status.
- [x] Review, merge, abandon, or clean up agent work from the app.

### Phase 6 - Multi-provider PR/MR and review workflow (10/07/2026)

- [x] Create GitHub draft Pull Requests from the current branch.
- [x] Guard draft PR creation with provider, branch, conflict, push, and remote-visibility readiness checks.
- [x] Reuse encrypted GitHub token settings with Pull requests read/write permission guidance.
- [x] Show the runtime app version in the header badge instead of a manually maintained phase label.
- [x] Create GitLab Merge Requests from the current branch.
- [x] AI-generated PR title/body/checklist from commits and diff.
- [x] Add provider adapters for GitHub first, then GitLab.
- [x] CI status and review comment display.
- [ ] Add provider adapters for Bitbucket and Azure DevOps.
- [ ] Review-response workflow.

### Phase 7 - Cross-platform release (14/07/2026)

- [x] Replace Windows-only PowerShell sidecar build/test npm commands with cross-platform Node scripts.
- [x] Generate platform-aware sidecar binary names for Tauri sidecar discovery.
- [x] Add explicit Windows, macOS, and Linux Tauri bundle commands.
- [x] Terminate the sidecar child process on macOS/Linux during app shutdown.
- [x] Add Ubuntu 20.04 Git compatibility for plain-folder init and test repositories.
- [x] Resolve normal repository `.git` directories correctly on older Git versions.
- [x] Replace Windows-only secret assumptions with non-Windows portable local secret storage.
- [x] Auto-detect `python` / `python3` for sidecar build and test scripts.
- [x] Add Gitignore Assistant support for selected untracked runtime files.
- [x] Build and verify Linux `.deb` packaging on Ubuntu 22.04.
- [x] Add Settings support for global Git author identity on new machines.
- [x] Make Settings usable on shorter Linux VM screens with scrollable responsive layout.
- [ ] Build and verify macOS `.app` / `.dmg` packaging.
- [ ] Add Apple code signing and notarization path.
- [ ] Build and verify Linux AppImage packaging.
- [ ] Upgrade macOS/Linux secrets to native Keychain / Secret Service storage.
- [ ] Verify bundled sidecar startup, Git discovery, file pickers, and installer/update behavior on macOS and Linux.
- [ ] Document platform-specific install and troubleshooting steps.

### Phase 8 - Team context and conventions (target TBD)

- [ ] Add repo-local team context, for example `.ai-git-assistant/team-context.md`.
- [ ] Import team conventions from `CONTRIBUTING.md`, PR templates, changelog rules, and recent commit history.
- [ ] Let AI commit messages, PR summaries, release notes, branch names, and logical commit splits follow team style.
- [ ] Add shared convention profiles that can be checked into the repository without storing secrets.
- [ ] Show a context receipt explaining which team rules influenced an AI suggestion.
- [ ] Keep team context optional and reviewable so single-user local workflows stay lightweight.

---

## Running the app

```powershell
# Build the installer for the current host OS
npm run installer

# Explicit native installer builds
npm run installer:windows
npm run installer:linux
npm run installer:mac

# First time or after changing Python source
npm run sidecar:build

# Run tests after dependencies are installed
npm run sidecar:test

# First-time test dependency install, if needed
npm run sidecar:test:install

# Build a platform bundle on the matching host OS
npm run tauri:build:windows
npm run tauri:build:mac
npm run tauri:build:linux

# Start in development mode
npm run tauri:dev
```

`npm run installer` runs sidecar tests, builds the sidecar binary, and then builds the native installer package for the host OS. Windows emits NSIS, Linux emits `.deb`, and macOS emits `.dmg`.

Requirements: Node 20+, Rust stable, Python 3.12+, Git 2.25+.

---

## Test coverage

| Suite | Tests | What is covered |
|---|---|---|
| `test_action_planner.py` | 44 | Local plan creation for read/write commands; push safety; short filename resolution; selected/all/staged commit paths; Phase 3 stash/read/merge/tag commands |
| `test_settings_service.py` | 11 | LLM/GitHub/GitLab settings defaults, updates, encrypted secret persistence, and secret redaction |
| `test_llm_validator.py` | 12 | LLM step validation, safe path checks, remote validation, supported action kinds |
| `test_health.py` | 3 | Authenticated sidecar health checks, protocol version, and diagnostics metadata |
| `test_repository_flow.py` | 42 | Repository registration/classification, read actions, execute-plan flows, push/pull, branch creation, plan cancel, Phase 3 diff/graph/stash/remote/history/blame/merge/tag flows, Phase 4 premium commit-message generation, large selections, change summaries, risk, privacy receipts, Phase 4.1 GitHub draft releases, Phase 4.3 provider awareness, Phase 5 commit style modes, agent worktree session lifecycle, Phase 6 GitHub draft PR / GitLab draft MR flow, and Phase 6.2 PR/MR review status |
| `test_remote_provider.py` | 9 | Remote provider detection for GitHub, GitLab, Bitbucket, Azure DevOps, SSH, HTTPS, and local path remotes |

Current verified sidecar suite: 121 passing tests via `npm run sidecar:test` on Windows; Ubuntu 20.04 verification is in progress.
