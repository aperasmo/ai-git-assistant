# Release Notes

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
