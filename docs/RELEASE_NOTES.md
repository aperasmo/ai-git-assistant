# Release Notes

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
