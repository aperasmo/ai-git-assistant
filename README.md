# AI Git Assistant

A local-first desktop application for performing common Git workflows through natural-language chat. Built with Tauri 2, React 18, TypeScript, and a Python FastAPI sidecar.

---

## What it does

Type plain English. The app figures out the Git operation, shows you exactly what will happen, and waits for your approval before changing anything.

```text
What changed?
show branches
last 10 commits
show me the diff

stage src/login.py and tests/test_login.py

commit staged changes with message "Add login validation"

commit src/routes/login.py with message "Fix redirect" then push

push current branch

pull

switch to feature/login
create branch feature/payments

stash my changes
pop stash

unstage src/login.py
discard changes to src/login.py

delete branch old-feature
```

Requests the local planner can't recognise are forwarded to the configured AI provider (Anthropic, OpenAI, Groq, or Ollama), which returns the same structured plan — so the approval step is unchanged regardless of how the plan was created.

---

## Key design properties

**Plan-then-approve** — every write operation builds a plan first. You review the steps, then click Approve. Nothing runs until you say so.

**Local-first** — read operations and common write patterns resolve entirely on-device with a regex planner. No network, no tokens consumed.

**LLM fallback is opt-in** — you configure a provider in Settings and explicitly enable AI for each repository. The app never sends repository context to an external service without your consent.

**Constrained execution** — no arbitrary shell access. The sidecar runs a fixed set of Git commands with validated argument arrays and `shell=False`.

**No credential storage** — the app calls your system Git, which uses Windows Credential Manager or your existing SSH configuration. Your GitHub tokens never touch this app.

---

## Architecture

```
React UI
  ↓ Tauri named commands (never raw HTTP)
Rust IPC proxy
  ↓ authenticated loopback HTTP (per-session bearer token)
Python FastAPI sidecar (127.0.0.1, OS-assigned port)
  ↓ subprocess with validated argument arrays, shell=False
System Git CLI
```

React never sees the sidecar port or bearer token. The sidecar never accepts connections from outside the loopback interface.

---

## AI providers

| Provider | Type | Default model | Setup |
|---|---|---|---|
| Anthropic (Claude) | Cloud | `claude-haiku-4-5-20251001` | API key in Settings |
| Google Gemini | Cloud | `gemini-3.5-flash` | API key from [Google AI Studio](https://aistudio.google.com/) |
| OpenAI | Cloud | `gpt-4o-mini` | API key in Settings |
| Groq | Cloud (free tier) | `llama-3.3-70b-versatile` | API key in Settings |
| Ollama | Local | `llama3.2` | No key required; Ollama must be running |

API keys are stored in the local SQLite database. The raw key is never returned by the settings API.

---

## Operations

### Read (automatic, no approval needed)

| Command | Example |
|---|---|
| Status | `what changed?` / `git status` |
| Log | `last 10 commits` / `show recent commits` |
| Diff | `show me the diff` |
| Branches | `show branches` |
| Fetch | `refresh remote status` |

### Write (plan preview + approval required)

| Command | Example |
|---|---|
| Stage | `stage src/login.py` |
| Unstage | `unstage src/login.py` |
| Discard | `discard changes to src/login.py` |
| Commit | `commit staged changes with message "Fix login"` |
| Commit + push | `commit src/login.py with message "Fix login" then push` |
| Push | `push current branch` |
| Pull | `pull` |
| Switch branch | `switch to feature/login` |
| Create branch | `create branch feature/payments` |
| Stash | `stash my changes` |
| Stash pop | `pop stash` |
| Delete branch | `delete branch old-feature` |

### Not supported (permanent safety boundaries)

- Force push
- `git reset`
- `git clean`
- Any operation that modifies published history

---

## Getting started

### Prerequisites

- [Node.js](https://nodejs.org/) 18+
- [Rust](https://rustup.rs/) (for Tauri)
- [Python](https://www.python.org/) 3.12+
- [Git](https://git-scm.com/)

### Development

```powershell
npm install
pip install -e "sidecar/.[dev]"
npm run tauri dev
```

### Build sidecar binary

The Tauri app launches a bundled sidecar executable, not the raw Python source. Rebuild after any Python changes:

```powershell
npm run sidecar:build
```

### Run tests

```powershell
cd sidecar
python -m pytest tests/test_action_planner.py tests/test_settings_service.py tests/test_llm_validator.py
```

### Type-check frontend

```powershell
npx tsc --noEmit
```

---

## Project structure

```text
ai-git-assistant/
├── src/                          React/TypeScript UI
│   ├── components/               ChatPanel, ContextPanel, SettingsModal, ...
│   └── lib/                      api.ts, types.ts
├── src-tauri/                    Rust shell
│   └── src/
│       ├── commands/             bootstrap, repositories, settings
│       ├── models/               typed structs matching Python schemas
│       ├── sidecar.rs            process lifecycle
│       └── sidecar_proxy.rs      authenticated HTTP to sidecar
├── sidecar/                      Python FastAPI service
│   └── app/
│       ├── api/                  routes: repositories, settings
│       ├── git/                  client, inspector, parser
│       ├── intent/               local_matcher, action_planner
│       ├── llm/                  base, router, providers, validator, prompt
│       ├── schemas/              repositories, settings
│       └── services/             repository_service, repository_store, settings_service
└── docs/                         architecture and decision records
```

---

## Security notes

- The webview cannot reach the sidecar directly.
- The sidecar port and session token are never exposed to JavaScript.
- All Git commands use argument arrays (`shell=False`).
- AI providers only receive repository context (branch, file counts, recent commit messages) — never file contents or credentials.
- Per-repository AI access must be explicitly enabled before any data is sent to a provider.
- API keys are stored in plaintext SQLite (see `docs/DECISIONS.md` for the tradeoff reasoning).
