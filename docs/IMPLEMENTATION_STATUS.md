# Implementation Status

**Last updated:** 18 July 2026  
**Current state:** Phase 7.9 cross-platform release hardening in progress. Windows is release-built; Ubuntu `.deb` packaging is verified; GitHub draft releases can be created or updated by tag; local-only repositories can be published to GitHub from the app; push/pull/merge blockers now surface guided recovery actions; merge conflicts can be resolved through preview-first local/remote/AI choices; AppImage and macOS packaging remain pending.

---

## Phases completed

### Phase 0 — Tauri shell, sidecar lifecycle, authenticated IPC

- Tauri 2 shell with React 18 / TypeScript / Vite frontend.
- Python FastAPI sidecar bundled as a single Windows executable (PyInstaller).
- Sidecar binds to `127.0.0.1:0` (OS-assigned port), emits one stdout readiness line: `TM_READY:{"port":<port>,"protocol_version":"1"}`.
- Rust generates a per-session bearer token; React never receives the port or token.
- `GET /v1/health` authenticated health check before any feature is enabled.
- Git installation detection on startup with a clear UI error if Git is missing.

### Phase 1 — Repository management and read-only actions

- Native folder picker for repository registration.
- Repository store (SQLite) — `repositories` table persists across sessions.
- Five read-only actions: `status`, `log`, `diff`, `branches`, `fetch`.
- Local intent matcher (`LocalIntentMatcher`) — regex pattern matching resolves read requests without an LLM.
- Three-pane UI: sidebar (repositories), chat (transcript), context panel (live snapshot).
- Quick Actions in the context panel run read operations directly.
- `RepositorySnapshot` streamed into the context panel on repository selection.

### Phase 2 — Plan engine and eight write commands

- Plan-then-approve flow: `POST /v1/repositories/{id}/resolve-local` creates an in-memory plan keyed by UUID; `POST /v1/repositories/{id}/execute-plan` runs only after explicit user approval.
- Local action planner (`LocalActionPlanner`) — regex-based, builds `LocalActionPlan` from intent-matched requests.
- Reviewed write commands via the plan engine:
  - `STAGE` — stage explicit file paths
  - `UNSTAGE` — remove files from the index
  - `DISCARD` — discard worktree changes (destructive, confirmed)
  - `COMMIT` — commit with a required message
  - `PUSH` — push to remote (with optional `--set-upstream`)
  - `PULL` — fast-forward pull only
  - `SWITCH_BRANCH` — check out an existing branch
  - `CREATE_BRANCH` — create and check out a new branch
  - `STASH` — stash with optional label
  - `STASH_POP` — pop the most recent stash
  - `DELETE_BRANCH` — delete a local branch
  - `CREATE_TAG` — create an annotated release tag
  - `PUSH_TAG` — push one explicit tag to a known remote
  - `DELETE_TAG` — delete a local tag
- Stale-plan recheck: the snapshot is re-read immediately before execution; the plan is rejected if the repository changed since planning.
- `PlanCard` component in the chat transcript — shows steps, approve/cancel buttons, and step-by-step status after execution.
- Pre-execution recheck guards against write operations on stale state.

### Phase 3 — LLM fallback layer and settings UI

- **Provider abstraction:** `LLMProvider` abstract base class with structured plan generation and plain-text completion, backed by five concrete provider configurations:
  - `AnthropicProvider` — uses the Anthropic SDK with tool use (`create_git_plan` tool); default model `claude-haiku-4-5`.
  - `OllamaProvider` — HTTP calls to a local Ollama instance; default model `llama3.2`, default base URL `http://localhost:11434`.
  - `OpenAICompatProvider` — shared implementation covering OpenAI (`gpt-4o-mini`), Groq (`llama-3.3-70b-versatile`, base URL `https://api.groq.com/openai/v1`), and Gemini (`gemini-3.5-flash`, base URL `https://generativelanguage.googleapis.com/v1beta/openai/`). Gemini uses Google's OpenAI-compatible endpoint — no additional SDK required.
- **LLM fallback routing:** when the local planner returns `matched=False` and the repository has `external_llm_allowed=True`, `LLMRouter` calls the configured provider, validates the returned steps, and produces a `LocalActionPlan` with `source="llm"`.
- **Structured output:** Claude uses Anthropic tool use; OpenAI/Groq/Ollama use OpenAI function calling format. The LLM returns steps in the same `LocalActionPlan` schema the local planner uses, so the approval UI is unchanged.
- **Plan validation (`validate_llm_steps`):** rejects empty plans, plans exceeding 8 steps, unknown step kinds, wildcard paths (`.`, `*`, `all`, `**`), paths not in the repository's changed files, unknown remotes, missing tag names, and commits/tags without required messages.
- **Settings storage:** `app_settings` SQLite table (key-value); `SettingsService` manages CRUD. API keys are encrypted with Windows DPAPI before storage and never returned via the settings API — only `api_key_set: bool` is exposed.
- **Settings API:** `GET /v1/settings/llm` and `PUT /v1/settings/llm`.
- **Per-repository AI toggle:** `POST /v1/repositories/{id}/set-llm`; `external_llm_allowed` column in the `repositories` table.
- **Tauri commands:** `get_llm_settings`, `update_llm_settings`, `set_repository_llm_allowed`.
- **Settings modal:** provider selector, API key field (password), model field, Ollama base URL field, and encrypted-local-storage notice.

### Phase D — AI-native Git workflows

- **Version line:** Phase D builds use `0.4.x`; the first Phase D build is `0.4.0`.
- **AI commit-message generation:** the commit wizard can request one concise commit subject from the configured provider using only the selected files.
- **AI change summaries:** the context panel can analyze selected working-tree changes and return branch/file summaries, PR title/body, and logical commit suggestions.
- **Risk scoring:** pending write plans include deterministic low/medium/high risk metadata before approval.
- **Privacy receipts:** external-AI calls return provider/model, context item types, exact context sent, file count, character count, and truncation status.
- **Repository provider awareness:** snapshots classify configured remotes as GitHub, GitLab, Bitbucket, Azure DevOps, unknown, local-only, or mixed-provider so platform-specific features can explain what is available for the selected repository.
- **Provider-aware release guard:** GitHub draft release publishing runs only for GitHub-backed repositories. GitLab, Bitbucket, Azure DevOps, local-only, and unknown remotes receive a clear unsupported-platform message while normal Git workflows remain available.
- **Repository AI opt-in enforced:** commit-message generation is blocked unless `external_llm_allowed=True` for that repository.
- **Diff context bounds:** selected tracked paths use `git diff HEAD --patch -- <paths>`; selected untracked files include bounded file snippets; total context is capped before provider calls.
- **Provider reuse:** Anthropic, OpenAI-compatible providers, and Ollama all support the same `complete_text` provider method.
- **AI toggle in the context panel:** per-repository switch with `role="switch"` / `aria-checked`.
- **AI badge on plan cards:** plans generated by the LLM show "AI GIT PLAN" with a purple `AI` badge.
- **`source` field on `LocalActionPlan`:** `"local"` or `"llm"` to distinguish plan origin.

### Phase 6 - PR/MR workflow

- **GitHub draft PRs:** the Draft PR wizard creates GitHub draft pull requests from the current branch after provider, branch, conflict, push, and remote-visibility checks.
- **GitLab draft MRs:** the same Draft PR wizard creates GitLab draft merge requests for GitLab-backed repositories using an encrypted GitLab token and optional self-managed base URL.
- **AI PR/MR drafts:** title, body, and checklist suggestions are generated from base/head branches, commit range, changed files, diff stats, and recent commit subjects.
- **Provider-specific credentials:** Settings stores GitHub and GitLab tokens separately with local encryption.
- **Version badge:** the top bar displays the runtime app version from Tauri metadata instead of a hardcoded phase label.
- **Review status:** the app can read the current branch's GitHub Pull Request or GitLab Merge Request, including CI/check status, draft state, review summary, comment count, and recent comments.

### Phase 7 - Cross-platform release foundation

- **Portable sidecar scripts:** `npm run sidecar:build` and `npm run sidecar:test` now use Node scripts instead of Windows-only PowerShell entry points.
- **Platform-aware sidecar binaries:** sidecar output is copied to Tauri's `src-tauri/binaries` folder using the host target triple and the correct executable suffix for Windows versus macOS/Linux.
- **Host-specific Tauri bundle commands:** Windows, macOS, and Linux bundle commands are exposed separately so each platform can be built on its matching host or CI runner.
- **Non-Windows shutdown:** macOS/Linux hosts terminate the sidecar through Tauri's shell child process instead of relying on the Windows-only `taskkill` path.
- **Ubuntu 20.04 Git compatibility:** repository initialization and test fixtures work with Git versions that do not support `git init -b`.
- **Older-Git repository validation:** normal `.git` common directories are resolved relative to the repository root so they are not mistaken for linked worktrees.
- **Non-Windows secrets:** Linux/macOS can store AI provider keys, GitHub tokens, and GitLab tokens with portable local encryption while native keychain integration remains planned.
- **Python command autodetection:** sidecar build/test scripts detect `python` or `python3`, while still allowing explicit `--python`.
- **Gitignore Assistant:** file-pick wizard steps can add selected untracked files to `.gitignore`, de-duplicate exact entries, refresh the snapshot, and list the written entries in the transcript.
- **Git identity setup:** Settings can read and save global Git `user.name` and `user.email` through the standard `git config --global` path before commit workflows run.
- **Settings usability:** Settings uses a wider two-column layout where possible and scrolls on shorter Linux VM screens.
- **Linux `.deb` packaging:** Ubuntu 22.04 builds the frontend, passes sidecar tests, builds the sidecar binary, and bundles the Debian package line.
- **GitHub push-auth recovery:** GitHub write-permission failures now explain the fine-grained token requirement and offer a push-only retry so an existing local commit is not duplicated.
- **Divergent-branch recovery:** Fast-forward pull failures now explain the cross-machine divergence and offer fetch, diff, or a reviewed upstream merge.
- **One-command installer builds:** `npm run installer` runs sidecar tests, builds the sidecar binary, and builds the native installer for the current host OS.
- **Release Manager draft releases:** GitHub draft releases can select an existing tag or enter a new tag, create the missing GitHub tag ref before saving a new draft, use a larger markdown description editor, retrieve existing draft title/body/assets in Edit mode, show already-attached assets in the asset picker, create a new draft or update an existing draft for that tag, upload multiple installer assets, and report duplicate asset filenames without silently replacing them.
- **Publish GitHub:** Local-only repositories can create a GitHub repository, commit selected files when needed, rename the branch to `main`, add `origin`, and push with upstream tracking after explicit approval.
- **Push/pull/merge recovery:** Push rejections caused by newer remote commits now explain that the local commit exists and offer fetch, pull latest, or diff review. Merge conflicts now offer show conflicts, continue merge, abort merge, and preview-first conflict resolution from the recovery card. Git error parsing prefers actionable `fatal:` / `error:` lines over transfer noise.
- **Guided Conflict Resolver:** Conflict recovery can preview keep-local, keep-remote, or AI-proposed resolutions, then apply the resolved content only after explicit user approval.

### Post-launch fixes

- **Rust unused import:** Removed unused `use serde_json::json;` from `src-tauri/src/commands/settings.rs`.
- **Local matcher — "logs" not matched:** Log regex `commits?` was extended to `(?:commits?|logs?)` so phrases like "show me last 5 logs" resolve locally without hitting the LLM. Added "show log" / "show logs" to the exact-match set.
- **Gemini provider added:** Five providers now supported. Gemini uses Google's OpenAI-compatible REST endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`) — handled by `OpenAICompatProvider`, no extra SDK needed. Default model `gemini-3.5-flash`. Get an API key from Google AI Studio.

---

## Test results

| Suite | Tests | Result |
|---|---|---|
| `test_action_planner.py` | 30 | Pass |
| `test_settings_service.py` | 7 | Pass |
| `test_llm_validator.py` | 12 | Pass |
| `test_repository_flow.py` | 135 | Pass |
| **Total** | **184** | **All pass** |

Integration tests (`test_repository_flow.py`) use disposable Git repositories and pass when pytest's base temp directory is controlled by the project test wrapper.

TypeScript: `npx tsc --noEmit` — no errors.  
Sidecar binary: built with PyInstaller at `src-tauri/binaries/ai-git-sidecar-x86_64-pc-windows-msvc.exe`.

---

## Known divergences from the MVP build plan

| Plan | Actual | Reason |
|---|---|---|
| OS keychain for API key storage | Windows DPAPI-encrypted SQLite value | Tauri keychain plugin had unclear v2 support at the time of implementation. Phase B uses Windows account protection through DPAPI while preserving the existing API surface. |
| Two providers at launch (Ollama + Groq) | Five providers (Anthropic, Gemini, OpenAI, Groq, Ollama) | Adding Claude and OpenAI was mechanical once the abstraction was in place; Gemini uses Google's OpenAI-compatible endpoint so it required no new SDK. |
| Phase 3 included packaging spike and README | Packaging spike deferred | The Windows NSIS installer is the remaining Phase 3 item. The app runs correctly under `npm run tauri dev`. |

---

## Remaining work

- Installer signing is deferred for early releases; see `docs/INSTALLER_SIGNING.md`.
- Phase C Git client parity is implemented: visual commit graph, full patch diff, file history/blame, stash inspect/apply/drop, remote listing, release tag workflows, and guided merge conflict workflow.
- Phase D AI-native Git workflows are implemented: commit messages, change summaries, logical commit suggestions, PR-ready summaries, risk scoring, privacy receipts, GitHub release publishing, and repository provider awareness.

---

## Development commands

```powershell
# Install dependencies
npm install
pip install -e "sidecar/.[dev]"

# Run unit tests
cd sidecar
python -m pytest tests/test_action_planner.py tests/test_settings_service.py tests/test_llm_validator.py

# Rebuild sidecar binary
npm run sidecar:build

# Type-check frontend
npx tsc --noEmit

# Run in development mode
npm run tauri dev
```
