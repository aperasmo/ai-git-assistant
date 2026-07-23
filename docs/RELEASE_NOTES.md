# Release Notes

## 0.9.0 - Phase 9

Starts the team context and conventions phase.

- Adds optional repo-local team context at `.ai-git-assistant/team-context.md`.
- Surfaces Team Context status in the repository context panel.
- Includes team context in AI-generated commit-message prompts when present.
- Includes team context in AI-generated PR/MR draft prompts when present.
- Lists repository team context in the privacy receipt whenever it is sent to the configured AI provider.
- Clips large team-context files before prompt assembly and marks the receipt as truncated.
- Adds a public-safe `docs/TEAM_CONTEXT_TEMPLATE.md` with real-world defaults for commit, PR/MR, validation, review, documentation, branch, and release guidance.
- Uses the same template in the sidecar regression test so unit coverage reflects the recommended team-context shape.
- Adds one-click **Add template** onboarding from the repository context panel when a repo has no team context file.
- Clarifies that the selected commit-message style takes priority over team context guidance.
- Adds tooltips for the **Detailed**, **Concise**, **Conventional**, and **Release** commit-message style buttons.
- Remembers generated commit-message drafts per style so users can switch between styles without losing the previous wording.
- Fixes the Tauri bridge model so `teamContext` is preserved from the sidecar snapshot instead of causing a blank renderer on upgrade.
- Public docs and version metadata updated to `0.9.0`.

Validation:

- focused team-context sidecar regression test
- frontend build verification

## 0.8.0 - Phase 8

Starts the UI responsiveness and workflow-polish phase.

- Reworked the bottom command bar into an adaptive command dock.
- Keeps high-frequency actions visible by default: status, diff, recent commits, commit and push, pull latest, and connect remote.
- Moves the full read/write command set behind **More** so smaller Linux VM and laptop resolutions have more room for the main conversation.
- Adds an expanded command drawer with grouped read and write actions.
- Adds a collapsible repository context panel that shrinks to a slim restore rail.
- Adds context-aware command visibility so local-only, remote-connected, conflicted, GitHub, and GitLab repositories surface the right actions first.
- Adds a top-bar dark/light theme toggle with local theme persistence.
- Updates walkthrough targets and copy for the new command dock.
- Public docs and version metadata updated to `0.8.0`.

Validation:

- frontend build verification

## 0.7.9 - Phase 7.9

Adds a guided Conflict Resolver for merge conflicts.

- Merge-conflict recovery now offers deterministic **Keep local version** and **Keep remote version** actions.
- Repositories with AI context enabled can request an **Auto-resolve with AI** proposal.
- Resolution is preview-first: the app shows the files, strategy, summary, and resolved content before writing anything.
- Applying a preview writes the resolved files, validates that conflict markers are gone, marks the files resolved through Git, and guides the user to continue the merge.
- Continue-merge planning now supports clean no-diff resolutions, such as keeping the current local file when Git has no staged diff to show.
- GitHub HTTPS pull, push, fetch, tag push, and branch-visibility checks can use the stored GitHub token non-interactively instead of sending users back to the terminal.
- Public docs and version metadata updated to `0.7.9`.

Validation:

- focused conflict resolver regression test
- focused GitHub HTTPS token handoff regression test
- frontend build verification
- Rust Tauri command bridge check

## 0.7.8 - Phase 7.8

Adds a guided Publish GitHub flow for local-only repositories and improves recovery for cross-machine push/pull failures.

- New **Publish GitHub** WRITE action creates a GitHub repository from a local project.
- The wizard collects selected files, commit message, repository name, description, and visibility before execution.
- On approval, the app commits selected files when needed, renames the branch to `main`, adds `origin`, and pushes with upstream tracking.
- Already-connected repositories are guarded with next-step guidance so users use Pull latest or Commit & push instead.
- Push rejections caused by newer remote commits now explain that the local commit exists and offer fetch, pull latest, or diff review.
- Merge conflict failures now offer Show conflicts, Continue merge, and Abort merge directly from the recovery card.
- Git error parsing now prefers actionable `fatal:` / `error:` lines over transfer noise such as `From <remote>`.
- Public docs and version metadata updated to `0.7.8`.

Validation:

- focused publish-to-GitHub sidecar tests for successful create/add-remote/push and already-remote blocking
- focused regression tests for actionable Git error parsing and merge-conflict guidance
- full sidecar test suite: 135 passed
- frontend build verification

## 0.7.7 - Phase 7.7

Adds Release Manager behavior for assembling one GitHub release from multiple platform machines.

### Shipped

- Release Manager now starts with explicit **Create new draft** and **Edit existing draft** choices.
- Edit mode retrieves the current draft release title, notes, URL, and uploaded assets before asking for changes.
- The release asset picker now shows already-attached assets before selecting additional installer files.
- Draft release flow creates a new draft or updates the existing draft for the selected tag.
- Missing GitHub tag refs are created before the draft release is saved, so the release also appears in GitHub's Tags view.
- Windows and Linux installers can be uploaded to the same draft release from their own machines.
- Existing asset filenames are detected and reported as already present instead of being replaced silently.
- Release Manager wording now appears in the write command bar and confirmation step.
- Public docs and version metadata updated to `0.7.7`.

### Verification

- `npm run build`
- `cargo check --locked`
- `npm run sidecar:test` - 127 passed
- focused release flow tests for single, multiple, and existing-draft GitHub release assets

## 0.7.6 - Phase 7.6

Improves Guided Recovery for cross-machine divergent branches found during Linux verification and polishes the release publishing flow for multi-platform assets.

### Shipped

- Added a **Branch has diverged** recovery card when fast-forward pull is blocked.
- Recovery can fetch remote state, show differences, or prepare a reviewed merge of the upstream branch.
- Merge planning now accepts remote-tracking branches such as `origin/main`.
- The app keeps fast-forward-only pull as the default, so merge commits remain explicit and reviewed.
- Added `npm run installer` as a one-command native installer build wrapper for the current host OS.
- Draft releases can select an existing local tag or type a new tag before release details.
- Release descriptions now use a larger markdown-friendly editor.
- Draft releases can attach multiple installer assets, such as Windows `.exe` and Linux `.deb`, in one release.

### Verification

- `npm run build`
- `cargo check`
- focused release flow tests for single and multiple GitHub release assets

## 0.7.5 - Phase 7.5

Improves Guided Recovery for GitHub push authentication failures found during Linux verification.

### Shipped

- Added a **GitHub rejected the push** recovery card for write/auth failures during push.
- Recovery explains that fine-grained GitHub tokens need repository access and **Contents: Read and write**.
- Added a **Retry push** recovery action that pushes the current branch without creating another commit.
- Updated Settings copy so GitHub token guidance matches the failure users see in real workflows.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test`

## 0.7.4 - Phase 7.4

Adds Guided Recovery for common Git setup walls found during Linux verification.

### Shipped

- Added a **Next Step Assistant** transcript card for recoverable Git blockers.
- Pulling without upstream now recommends setting upstream before retrying pull.
- Existing-remotes flow now recommends pull, remote inspection, or intentionally adding another remote.
- Missing Git author identity errors now point users directly to Settings.
- Added a reviewed `set_upstream` plan so users can run `git branch --set-upstream-to origin/main main` from the app.
- Status on the app data folder can recommend switching to the real source repository when both are registered.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test`

## 0.7.3 - Phase 7.3

Adds Git author identity setup and improves Settings usability on shorter Linux VM screens.

### Shipped

- Added **Git Author Identity** fields in Settings for global `user.name` and `user.email`.
- Saved Git identity through Tauri using `git config --global`, matching the standard CLI setup.
- Settings now uses a wider two-column layout when space allows and a scrollable single-column layout on smaller screens.
- The Gitignore Assistant file picker auto-closes when all selected untracked files have been ignored and no changed files remain.
- Public docs now call out Git identity setup as part of first-machine onboarding.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test`

## 0.7.2 - Phase 7.2

Adds a Gitignore Assistant slice and confirms the first Ubuntu Linux package build.

### Shipped

- Visible **Ignore selected** action in file-pick wizard steps.
- Ignore action is limited to selected untracked files so modified source files are not accidentally added to `.gitignore`.
- Exact `.gitignore` entries are appended under the AI Git Assistant section and de-duplicated across existing entries and the current request.
- Session filtering keeps newly ignored files out of the current wizard flow after the `.gitignore` write succeeds.
- Local confirmation result lists the exact entries written.
- Repository `.gitignore` now excludes SQLite WAL companion files (`*.db-shm`, `*.db-wal`) in addition to `*.db`.

### Verification

- `npm run build`
- `python -m pytest sidecar/tests/test_repository_flow.py::test_add_to_gitignore_appends_exact_untracked_paths -q --basetemp .pytest-tmp-gitignore -p no:cacheprovider`
- Ubuntu 22.04: `npm run sidecar:test`
- Ubuntu 22.04: `npm run sidecar:build`
- Ubuntu 22.04: `npx tauri build --bundles deb`

## 0.7.1 - Phase 7.1

Hardens the cross-platform release line after the first Ubuntu verification pass.

### Shipped

- Git 2.25-compatible repository initialization for Ubuntu 20.04 and other older Git hosts.
- Older-Git repository validation fix so normal `.git` directories are not mistaken for linked worktrees.
- Non-Windows portable local secret storage for AI provider keys, GitHub tokens, and GitLab tokens.
- `python` / `python3` autodetection for portable sidecar build and test scripts.
- Linux test fixture compatibility for older Git versions that do not support `git init -b`.

### Verification

- `npm run sidecar:test -- -- tests/test_settings_service.py tests/test_repository_flow.py::test_register_and_read_status tests/test_repository_flow.py::test_initialise_and_register_plain_folder_after_confirmation tests/test_repository_flow.py::test_register_nested_folder_uses_repository_root`

## 0.7.0 - Phase 7

Starts the cross-platform release line.

### Shipped

- Portable Node-based `sidecar:build` script replacing the Windows-only npm PowerShell path.
- Portable Node-based `sidecar:test` script with the same isolated project-local pytest temp behavior.
- Platform-aware sidecar output naming: `.exe` for Windows target triples, extensionless binaries for macOS/Linux target triples.
- Explicit Tauri bundle commands for Windows, macOS, and Linux host builds.
- macOS/Linux sidecar shutdown handling through Tauri's shell child process.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test`
- `npm run sidecar:build`
- `npm run tauri:build:windows`

## 0.6.2 - Phase 6

Adds PR/MR review visibility for the current branch.

### Shipped

- Review status read action in the command bar and right-panel quick actions.
- GitHub Pull Request status lookup for the current branch.
- GitLab Merge Request status lookup for the current branch.
- CI/check status, draft state, base/head branches, review summary, comment count, and recent comments in the result card.
- Local matcher guard so `review status`, `PR status`, `MR status`, and `CI status` resolve as read-only actions instead of falling through to AI write planning.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test` - 121 passing tests

## 0.6.1 - Phase 6

Completes the first PR/MR workflow line.

### Shipped

- GitHub draft pull request creation from the current branch.
- GitLab draft merge request creation from the current branch.
- AI-generated PR/MR title, body, and checklist drafts from branch comparison context.
- Provider-aware readiness checks for branch name, base branch, conflicts, pushed commits, and remote branch visibility.
- GitHub and GitLab token settings stored with local encryption.
- Runtime app version badge in the header instead of a manually maintained phase label.
- Agent worktree compare now uses the worktree `HEAD` consistently for committed file/stat comparisons.

### Verification

- `npm run build`
- `cargo check`
- `npm run sidecar:test` - 118 passing tests

## 0.1.0 - Phase A

Initial Windows installer release.

### Shipped

- Tauri 2 desktop app with React/TypeScript UI and Python FastAPI sidecar.
- Bundled sidecar binary, so end users do not need Python, Node.js, or Rust.
- Repository registration, nested-folder detection, plain-folder `git init`, and remote clone flow.
- Read actions: status, recent commits, diff summary, branches, and fetch.
- Plan-before-approval write actions: stage, unstage, discard, commit, push, pull, switch branch, create branch, stash, stash pop, and delete branch.
- LLM fallback for natural-language requests that the local planner cannot recognise.
- Provider support for Anthropic, Gemini, OpenAI, Groq, and Ollama.
- Per-repository opt-in before sending repository context to external AI providers.
- Settings UI, AI connection test, command wizard, walkthrough, help modal, and `.gitignore` helper.

### Safety Boundaries

- No force push.
- No hard reset.
- No arbitrary shell execution.
- No write operation runs without explicit approval.
- Plans are rejected if repository state changes before approval.

### Phase B Hardening Completed After Initial Release

- API keys are encrypted with Windows DPAPI before being stored locally.
- Existing plaintext API keys are migrated to encrypted storage on first read or update.
- Diagnostics modal added with app, sidecar, Git, repository, provider, database, and recent sidecar-message details.
- Official sidecar test command now uses isolated project-local temp directories and passes the full integration suite.
- Installer signing decision documented in `docs/INSTALLER_SIGNING.md`.

### Phase B Build Verification

- Installer: `AI Git Assistant_0.1.0_x64-setup.exe`
- SHA256: `B9643CCC1657D814A96E51B6777BB3DB29DCBE44C5500071A7429E8998A1BE7C`
