# Architecture Decisions

---

## Phase 0–1 Decisions

### Trust boundary

- React talks only to named Tauri commands.
- Rust owns the sidecar endpoint and per-session token.
- FastAPI listens on `127.0.0.1` with an operating-system-selected port.
- The sidecar writes exactly one stdout readiness message:
  `AIGA_READY:{"port":<port>,"protocol_version":"1"}`
- All other sidecar output must go to stderr or controlled local logs.
- No generic proxy command exists.

### Git execution

- Use the system Git CLI, not a Git library.
- Use validated argument arrays only.
- Always use `shell=False`.
- `GIT_TERMINAL_PROMPT=0`, no interactive credential prompt from the sidecar.
- Read output is bounded. The UI receives stat summaries, not unlimited diffs.
- The Phase 0–1 tool set contains no state-changing Git operation.

### Repository registration

- A native folder picker supplies a local path to Rust.
- Rust passes the path directly to FastAPI and never exposes it to the webview.
- Store a canonical path internally; expose only a user-safe label such as `~/Projects/example`.
- Reject bare repositories, linked worktrees, and repositories with `.gitmodules`.
- Record in-progress operations and conflicts as write-blocking state for the later plan engine.

### UI

- The approved JSX mock is the visual reference.
- Production UI is split into components and uses no hard-coded demo repositories.
- Quick actions must remain read-only in Phase 1.
- Branch display is informational only until the plan engine is introduced.

---

## Phase 2 Decisions

### Plan-then-approve flow

- `resolve-local` creates a plan object stored in-memory, keyed by UUID. The plan UUID is the only identifier returned to React; the plan steps are never executed client-side.
- `execute-plan` requires the UUID. The sidecar re-reads the repository snapshot immediately before execution and rejects the plan if state has changed since planning (stale-plan guard).
- The plan object carries risk tier, step list, explanation, and `requiresConfirmation`. The UI presents the plan verbatim — no interpretation.

### Write command set

- Eleven write-capable operations implemented via the plan engine: `STAGE`, `UNSTAGE`, `DISCARD`, `COMMIT`, `PUSH`, `PULL`, `SWITCH_BRANCH`, `CREATE_BRANCH`, `STASH`, `STASH_POP`, `DELETE_BRANCH`.
- `DISCARD` is the only operation that destroys uncommitted data. It is flagged `requiresConfirmation=True` and the plan explanation uses explicit destructive language.
- No tool exists for force push, `git reset`, `git clean`, or any operation that modifies published history. These are permanent safety boundaries, not phase gaps.

### Local intent matching vs planner separation

- `LocalIntentMatcher` resolves intent from free text (returns a `PlanKind` + extracted parameters).
- `LocalActionPlanner` turns a matched intent into an executable `LocalActionPlan`.
- The two classes are separate so the matcher can eventually feed an LLM prompt as a fallback without the planner needing to know.

### camelCase serialization contract

- All Python Pydantic models use `alias_generator=to_camel` with `populate_by_name=True`.
- All Rust structs use `#[serde(rename_all = "camelCase")]`.
- TypeScript interfaces match field-for-field. This ensures the full IPC chain uses one consistent naming convention without manual field mapping.

---

## Phase 3 Decisions

### LLM fallback is opt-in at two levels

- A global provider must be configured (stored in `app_settings`).
- Each repository must have `external_llm_allowed=True` before any repository context is sent externally.
- If either condition is not met, `LLMNotConfiguredError` is caught silently and the original unmatched response is returned — the user sees the same "I can't do that" message, not a stack trace.

### Provider abstraction

- `LLMProvider` abstract base: one method `complete(system_prompt, user_message) -> list[dict]`.
- Three concrete classes covering five provider configurations:
  - `AnthropicProvider` — Anthropic SDK, tool use.
  - `OllamaProvider` — local HTTP to Ollama.
  - `OpenAICompatProvider` — OpenAI SDK, covers OpenAI, Groq, and Gemini. Gemini uses Google's OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`) — no extra SDK required.
- `LLMRouter` instantiates the correct provider from current settings; providers are not held as long-lived objects (constructed per-request to pick up settings changes without requiring a restart).
- LLM calls are synchronous. FastAPI runs sync handlers in a thread pool so blocking calls do not stall the event loop.

### Structured output via tool/function calling

- Claude uses Anthropic tool use with `tool_choice={"type":"tool","name":"create_git_plan"}` — forces exactly one tool call per request.
- OpenAI, Groq, and Ollama use OpenAI function calling format with the same schema under the `parameters` key.
- The LLM returns a `steps` array. The validator converts raw dicts into typed `ActionPlanStep` objects.
- The resulting `LocalActionPlan` has `source="llm"` and passes through the same approval UI as a locally planned request — no special-case handling needed.

### LLM plan validation

- Validation runs after every LLM response before the plan is stored. It rejects:
  - Empty step lists or more than 8 steps.
  - Unknown `kind` values (strict `StrEnum`).
  - Wildcard paths: `.`, `*`, `all`, `**`, `./`.
  - For `STAGE`/`UNSTAGE`/`DISCARD`: paths must be present in the repository's known changed files.
  - For `PUSH`/`PULL`: remote must be in the repository's known remotes.
  - For `COMMIT`: `commit_message` must be non-empty.
- If no changed files exist the path membership check is skipped (nothing to validate against).

### API key storage

- API keys are stored in plaintext in the SQLite `app_settings` table under the key `llm_api_key`.
- The settings API never returns the raw key — only `api_key_set: bool`.
- The settings modal shows a warning: "API keys are stored in plaintext in the local application database."
- **Rationale for SQLite over OS keychain:** Tauri 2's keychain plugin had unclear maintenance status at implementation time. Switching to the keychain is a one-method change in `SettingsService` with no API surface changes. SQLite plaintext is an acceptable tradeoff for a local developer tool where the threat model is remote attack, not physical access to the developer's own machine.

### `source` field on `LocalActionPlan`

- All plans carry `source: "local" | "llm"`.
- The chat panel renders "AI GIT PLAN" with a purple badge for LLM-sourced plans, "LOCAL GIT PLAN" otherwise.
- This makes it clear to the user which planning path was taken without adding a separate message type.
