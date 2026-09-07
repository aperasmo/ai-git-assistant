# Claude Cowork Implementation Prompt — AI Git Assistant Phase 0–1

> **Note:** This prompt was used to implement Phase 0–1. Phases 0–3 are now complete. See `IMPLEMENTATION_STATUS.md` for the current state.

---

You are working inside a Windows-first desktop application repository named **AI Git Assistant**. Your task is to review, repair where necessary, and complete the Phase 0–1 foundation only. Do not broaden scope.

## Read these files before making changes

1. `docs/AI Git Assistant_v1_MVP_Build_Plan.md`
2. `docs/AI Git Assistant_System_Design_v1_Implementation_Baseline.md`
3. `docs/DECISIONS.md`
4. `docs/IMPLEMENTATION_STATUS.md`
5. `ai-git-assistant-mockup-v2.jsx` (visual reference only)

## Scope authority

- The MVP Build Plan is authoritative for v1 scope, implementation order, and acceptance criteria.
- The Implementation Baseline remains authoritative for security and architecture unless the MVP plan explicitly overrides it.
- Do not add requirements that are not necessary for Phase 0–1.

## Required Phase 0–1 outcome

Build and verify this exact vertical slice:

```text
React UI
  -> typed Tauri invoke command
  -> Rust proxy
  -> authenticated FastAPI sidecar
  -> system Git CLI

Launch app
  -> sidecar starts on 127.0.0.1:0
  -> sidecar reports a single validated readiness line
  -> Rust owns the port and session token
  -> Rust completes authenticated GET /v1/health
  -> application checks git --version
  -> user picks a local repository through native folder picker
  -> app shows live Git status in the three-pane UI
  -> "what changed?" resolves locally to git_status
```

## Non-negotiable security rules

1. React must never receive:
   - FastAPI port
   - session token
   - API keys
   - raw canonical repository path
   - arbitrary HTTP routing ability
   - arbitrary Git command or shell access
2. FastAPI must bind only to `127.0.0.1` on port `0`.
3. Rust must generate a unique random session token in memory and pass it only through the sidecar process environment.
4. The sidecar must print one and only one stdout readiness event:
   `TM_READY:{"port":<port>,"protocol_version":"1"}`
5. Sidecar logs must not go to stdout after readiness. Use stderr or a controlled local log.
6. Every FastAPI endpoint must require `Authorization: Bearer <session-token>`.
7. The frontend may call only typed, named Tauri commands. Do not build a generic `proxy_request` command.
8. All Git commands must use argument arrays, `shell=False`, a registered repository cwd, a timeout, and non-interactive environment variables including `GIT_TERMINAL_PROMPT=0`.
9. There is no LLM, cloud provider, API key, external-sharing setting, write plan, or write-capable Git command in this phase.

## Required current tool set

Implement only read-only actions:

- `git_status`
- `git_log` with a maximum of 50 entries
- `git_diff --stat` only; no full unbounded diff
- `git branch --format=...`
- explicit `git fetch --prune`

`git fetch` must never run automatically. It is a user-triggered “Refresh Remote Status” action. Ahead/behind must be labelled as cached until an explicit fetch occurs.

## Repository registration rules

At add/repository registration time:

- Use the native Tauri folder picker.
- Canonicalise the selected path in the FastAPI sidecar.
- Confirm it is a standard Git working tree.
- Reject:
  - bare repositories
  - linked worktrees
  - repositories containing `.gitmodules`
- Detect conflicts, merge, rebase, cherry-pick, revert, and bisect states.
- Read actions continue to work in those states, but expose `writeBlockedReason` for the future plan engine.
- Store raw canonical path only server-side. Return a safe path label to React, preferably a home-relative label.

## UI direction

Use `ai-git-assistant-mockup-v2.jsx` as the visual and interaction baseline:

- left: repositories, future conversation area, local provider indicator
- centre: chat and local result cards
- right: live repository status, recent commits, read-only quick actions
- top bar: active repository and branch display

Do not retain fake repositories, paths, commits, branch names, changed-file counts, or static status indicators.

For this phase:
- Branch display is read-only.
- Quick actions are only `Git Status`, `View Diff`, `Branches`, and `Refresh Remote Status`.
- No “Stash Changes” quick action.
- Do not use the mock’s local `useState` approval as execution logic. The later plan engine will make backend decisions.

## Architecture expectations

Maintain or repair this file organisation:

```text
src/                          React/TypeScript
src-tauri/                    Rust shell/proxy/lifecycle
sidecar/                      Python FastAPI
scripts/                      PowerShell development/build scripts
docs/                         architecture and handoff docs
```

Suggested Rust separation:
- `app_state.rs`: opaque sidecar runtime data
- `sidecar.rs`: launch/readiness/shutdown
- `sidecar_proxy.rs`: authenticated Rust-to-sidecar calls
- `commands/bootstrap.rs`: only startup / Git status data
- `commands/repositories.rs`: named repository/read-action commands

Suggested Python separation:
- `config.py`, `auth.py`, `errors.py`
- `git/client.py`, `git/repository_inspector.py`, `git/status_parser.py`
- `services/repository_store.py`, `services/repository_service.py`
- `intent/local_matcher.py`
- typed Pydantic schemas and thin routes

## First commands to run

Use PowerShell on Windows:

```powershell
.\scripts\check-prerequisites.ps1
npm install
.\scripts\build-sidecar.ps1
.\scripts\test-sidecar.ps1
npm run tauri dev
```

Before changing code, run:
- Python sidecar tests
- `cargo check` from `src-tauri`
- TypeScript check/build
- `npm run tauri dev` against a disposable Git repository

## Required verification

1. Bad/no auth token to FastAPI returns `401`.
2. Sidecar fails safely if readiness event is malformed or the health response is wrong.
3. Sidecar runs on a random loopback port, not a hard-coded port.
4. Webview does not receive port/token via a Tauri result, JS global, app state, log, or rendered UI.
5. Git missing produces a clear UI error.
6. A real repository can be registered and its live status shown.
7. Local input:
   - `what changed?`
   - `show branches`
   - `last 5 commits`
   - `show diff`
   - `refresh remote status`
   must resolve without an LLM.
8. Tests use disposable repositories; do not use a personal project as test fixture.
9. Build a Windows sidecar binary with the target-triple filename expected by Tauri.
10. Document any source changes and test commands/results in `docs/IMPLEMENTATION_STATUS.md`.

## Explicitly forbidden

- `shell=True`
- arbitrary shell commands
- generic frontend-to-sidecar HTTP calls
- exposing sidecar token/port to React
- automatically calling cloud or Ollama
- sending repo data externally
- generic Git command text generated by an LLM
- Git write operations: add, stash, switch, branch create, commit, pull, push
- force push, reset, clean, branch deletion
- hard-coded repositories, personal paths, commits, or credentials
- replacing the three-pane layout with a generic dashboard
- broad refactoring unrelated to Phase 0–1

## Output required from you

At the end, provide:

1. Files added or changed.
2. Exact commands run.
3. Test/build results.
4. Any remaining compiler/runtime issue, stated plainly.
5. A concise next-step recommendation: only the next smallest safe milestone.

Do not claim a build, package, or test passed unless you actually ran it successfully.
