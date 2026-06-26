# AI Git Assistant — Command Reference

There are two ways to interact with the app:

- **UI actions** — buttons and dialogs in the sidebar/panels. These handle repository lifecycle (adding, initialising). Documented in the first section below.
- **Chat commands** — text you type in the chat input. These handle all read and write Git operations. Documented in the remaining sections.

---

## UI actions (sidebar and panels)

These are triggered by clicking, not by typing in the chat.

### ✅ Add an existing repository

Click **+ Add repository** in the left sidebar → browse to any folder that is already a Git working tree → the app registers it and adds it to the sidebar.

Supported repository types: standard non-bare working trees, including repos with a remote and repos that have never been pushed.

Not supported: bare repos, repos with submodules, linked worktrees.

---

### ✅ Initialise a new repository — `git init`

Click **+ Add repository** → browse to a **plain folder** (not yet a Git repo) → the app detects it is not a Git repo and shows a confirmation dialog → click **Initialise** → the app runs:

```bash
git init -b main
```

The folder is then registered and added to the sidebar. The initial branch name is always `main`.

> This is the only place `git init` happens in the app. You cannot trigger it from the chat.

---

### ✅ Add a nested folder (parent repo auto-detected)

Click **+ Add repository** → browse to a **subfolder** inside an existing repo → the app detects the parent repository root and asks if you want to add that root instead → confirm → the root is registered.

---

### 📋 Remove a repository from the sidebar

A "Remove" option on each sidebar entry that deregisters the repo (does not delete any files).

---

### 📋 Rename / re-label a repository

Override the display name shown in the sidebar.

---

### 📋 Repository settings panel

Per-repository settings: toggle LLM access, view the database path, see remote URLs.

---

---

## Chat commands

Every request you type goes through two stages:

1. **Local planner** — a fast, offline regex matcher that recognises a bounded grammar of safe Git operations. No AI involved; deterministic and instant.
2. **LLM fallback** *(Phase 3, not yet built)* — when the local planner does not recognise the request, it will be sent to an LLM that returns a structured plan in the same format. The same approval UI handles both paths.

---

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Supported now — handled by the local planner |
| 🤖 | Next — requires LLM fallback |
| 📋 | Future — further planned work |

---

## Read commands

Read commands never modify the repository. They run immediately — no plan shown, no approval required.

### ✅ Repository status

Shows staged files, modified files, untracked files, conflicts, ahead/behind counts.

**Accepted phrases:**

```
status
git status
what changed?
what's changed?
```

**Equivalent Git command:**
```bash
git status --porcelain=v2 --branch
```

---

### ✅ Diff summary

Shows a stat summary of what has changed — file names and line counts.

**Accepted phrases:**

```
show diff
show me the diff
what's different?
diff
```

**Equivalent Git command:**
```bash
git diff HEAD --no-ext-diff --stat
```

> **Note:** v1 shows the stat summary only (file names and ±lines). Full patch diff output is a Phase 2 improvement.

---

### ✅ Commit history / log

Shows recent commits: short hash, subject, author, date.

**Accepted phrases:**

```
log
git log
show commits
recent commits
last 5 commits
last 10 commits
```

The number in `last N commits` is honoured (max 50).

**Equivalent Git command:**
```bash
git log -n5 --format="%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e"
```

---

### ✅ Branch list

Lists all local branches with their upstream tracking references.

**Accepted phrases:**

```
show branches
list branches
what branches?
which branches?
```

**Equivalent Git command:**
```bash
git branch --format="%(HEAD)%(refname:short)%(upstream:short)"
```

---

### ✅ Fetch / refresh remote status

Fetches remote tracking references and updates ahead/behind counts. Does not merge or modify the working tree.

**Accepted phrases:**

```
fetch
refresh remote status
update remote status
```

**Equivalent Git command:**
```bash
git fetch --prune
```

---

### 🤖 Full patch diff — Phase 3

Show the actual line-by-line diff, not just the stat summary.

**Planned phrases:**
```
show full diff
show patch
diff src/login.py
```

---

### 🤖 Diff for a specific file — Phase 3

```
diff src/login.py
show changes in src/login.py
what changed in src/login.py?
```

---

### 🤖 Explain a commit — Phase 3

```
what does the last commit do?
explain commit a3f9c12
summarise the changes in the last 3 commits
```

Requires an LLM to read the diff and generate a plain-English explanation.

---

### 🤖 Search commit history — Phase 3

```
when was src/login.py last changed?
find commits that mention "auth"
who last touched the payments module?
```

---

## Write commands

Write commands always show a **plan** first — the exact Git commands, files involved, and commit message. Nothing changes until you click **Approve and execute**.

---

### ✅ Stage specific files

Add named files to the Git staging area.

**Accepted phrases:**

```
stage src/login.py
add src/login.py
stage src/login.py and src/auth.py
stage src/login.py, src/auth.py, tests/test_login.py
```

Files are resolved against the current snapshot of changed files. Using `all`, `*`, or `.` is intentionally blocked.

**Plan steps:**
1. Stage `N` selected files

**Equivalent Git command:**
```bash
git add -- src/login.py src/auth.py
```

---

### ✅ Commit selected files

Stage and commit specific files in one step with a quoted message. Short filenames are resolved automatically.

**Accepted phrases:**

```
commit src/login.py with message "Add login validation"
commit login.py and auth.py with message "Refactor auth layer"
commit src/login.py, src/auth.py with message "Fix token expiry bug"
```

The commit message **must be in quotes** (single or double). If other unrelated files are already staged, the app refuses — it will not silently bundle them into your commit.

**Plan steps:**
1. Stage selected files
2. Create commit

**Equivalent Git commands:**
```bash
git add -- src/login.py src/auth.py
git commit -m "Refactor auth layer"
```

---

### ✅ Commit all modified files

Stage every modified and untracked file and commit them in one step. Useful when you want to commit everything without naming individual files.

**Accepted phrases:**

```
commit my changes with message "Fix layout"
commit all modified files with message "Fix layout"
commit everything with message "Fix layout"
commit changes with message "Fix layout"
```

**Plan steps:**
1. Stage all modified and untracked files *(all paths shown in the plan before you approve)*
2. Create commit

---

### ✅ Commit all staged changes

Commit whatever is already in the staging area.

**Accepted phrases:**

```
commit staged changes with message "Fix edge case in token refresh"
commit staged files with message "Update dependencies"
commit all staged changes with message "WIP checkpoint"
```

**Plan steps:**
1. Create commit (no staging step — uses what is already staged)

**Equivalent Git command:**
```bash
git commit -m "Fix edge case in token refresh"
```

---

### ✅ Push (branch has upstream tracking)

Push the currently checked-out branch to its configured upstream. Non-force only.

**Accepted phrases:**

```
push
push current branch
push to main
push to dev_1
```

`push to dev_1` is only accepted when `dev_1` is the **currently checked-out branch** — the app will not silently push `main` to a different branch name.

**Blocked if:** the branch is behind its upstream. You must fetch and integrate remote changes first.

**Plan steps:**
1. Push current branch → `origin/branch`

**Equivalent Git command:**
```bash
git push origin main
```

---

### ✅ Push new branch (no upstream yet)

When the checked-out branch has never been pushed before, the app automatically uses `--set-upstream` so the tracking reference is created. You do not need to do anything differently — just type `push`.

**Plan steps:**
1. Push and set upstream → `origin/branch`

**Equivalent Git command:**
```bash
git push --set-upstream origin dev_1
```

After this push, future pushes use the normal path above.

---

### ✅ Commit then push in one step

Stage, commit, and push in a single request. All three steps appear in the plan for review before anything runs.

**Accepted phrases:**

```
commit src/login.py with message "Add login validation", then push
commit src/login.py with message "Add login validation", then push to main
commit staged changes with message "Deploy hotfix" then push
commit staged changes with message "Deploy hotfix", then push to dev_1
```

**Plan steps:**
1. Stage selected files *(only for explicit-file variant)*
2. Create commit
3. Push current branch (or push and set upstream if branch is new)

**Equivalent Git commands:**
```bash
git add -- src/login.py
git commit -m "Add login validation"
git push origin main
```

---

### ✅ Pull

Fast-forward the current branch from its upstream. Never creates a merge commit.

**Accepted phrases:**

```
pull
git pull
sync with remote
pull from origin
```

**Blocked if:** the branch has diverged (ahead AND behind) — fast-forward is impossible. Shows INFO if already up to date or if no upstream is configured.

**Plan steps:**
1. Pull `N` commit(s) from remote

**Equivalent Git command:**
```bash
git pull --ff-only
```

---

### ✅ Unstage files

Move files back out of the staging area without discarding the changes.

**Accepted phrases:**

```
unstage src/login.py
unstage login.py and auth.py
remove login.py from staging area
```

Short filenames are resolved automatically (`login.py` → `backend/app/routes/login.py`).

**Plan steps:**
1. Unstage `N` selected files

**Equivalent Git command:**
```bash
git restore --staged -- src/login.py
```

---

### ✅ Discard file changes

Revert a file to its last committed state. Only works on modified (tracked) files — not untracked files.

**Accepted phrases:**

```
discard login.py
discard changes in login.py
```

**Plan steps:**
1. Discard changes in `N` files *(plan detail shows **DESTRUCTIVE** warning)*

**Equivalent Git command:**
```bash
git restore -- src/login.py
```

> The plan explicitly labels this DESTRUCTIVE. All local modifications to the named files will be permanently lost once you approve.

---

### ✅ Switch branch

Check out an existing local branch.

**Accepted phrases:**

```
switch to main
checkout dev_1
switch to feature/login
```

**Blocked if:** there are staged or modified changes — stash or commit them first. Shows INFO if you are already on the requested branch.

**Plan steps:**
1. Switch to `<branch>`

**Equivalent Git command:**
```bash
git switch main
```

---

### ✅ Create and switch to new branch

Create a new branch from the current HEAD and check it out immediately.

**Accepted phrases:**

```
create branch feature/login
new branch feature/login
```

**Plan steps:**
1. Create branch `<name>`

**Equivalent Git command:**
```bash
git switch -c feature/login
```

---

### ✅ Stash changes

Save all staged and modified changes to the stash and restore the working tree to HEAD.

**Accepted phrases:**

```
stash
stash my changes
stash changes
stash with message "WIP login form"
```

**Blocked if:** there are no local changes to stash.

**Plan steps:**
1. Stash local changes *(optional label shown in plan)*

**Equivalent Git command:**
```bash
git stash push
git stash push -m "WIP login form"
```

---

### ✅ Pop stash

Restore the most recent stash entry and remove it from the stash list.

**Accepted phrases:**

```
stash pop
restore stash
apply stash
```

**Fails at execution if:** the stash is empty, or applying the stash would cause conflicts.

**Plan steps:**
1. Apply stash

**Equivalent Git command:**
```bash
git stash pop
```

---

### ✅ Delete a local branch

Delete a local branch. Safe delete only — fails if the branch has commits not merged into any other branch.

**Accepted phrases:**

```
delete branch old-feature
remove branch old-feature
```

**Blocked if:** the target branch is the currently checked-out branch. Force delete (`-D`) is never used.

**Plan steps:**
1. Delete branch `<name>`

**Equivalent Git command:**
```bash
git branch -d old-feature
```

---

### 🤖 Create a commit message suggestion

```
suggest a commit message for these changes
what should I call this commit?
```

Requires an LLM to read the diff and propose a message.

---

### 🤖 Merge

```
merge dev into main
merge feature/login
```

Merging introduces conflict resolution complexity. A plan will show what will happen; conflicts will halt execution and report clearly.

---

### 🤖 Cherry-pick

```
cherry-pick a3f9c12
apply commit a3f9c12 to this branch
```

---

### 🤖 Rebase

```
rebase onto main
rebase feature/login onto main
```

Interactive rebase is out of scope even for Phase 3.

---

### 🤖 Tag

```
tag this commit as v1.0.0
create tag v2.3.1 with message "Release 2.3.1"
```

---

### 🤖 Amend last commit

```
amend the last commit message to "Fix login validation edge case"
```

Only safe to amend if the commit has not been pushed. The LLM plan will block it otherwise.

---

## Blocked operations — intentionally never supported

These will not be added at any phase. They are too destructive, too ambiguous, or require interactive UI that cannot be safely planned in a chat interface.

| Command | Reason blocked |
|---|---|
| `git push --force` | Risk of destroying remote history. Use `--force-with-lease` via terminal if you genuinely need it. |
| `git reset --hard` | Irreversible local destruction; no safe planning model. |
| `git clean -f` | Deletes untracked files permanently. |
| `git rebase -i` (interactive) | Requires a step-by-step interactive editor; cannot be expressed as a pre-reviewable plan. |
| `git push <remote> <local>:<remote-branch>` (cross-branch) | The app never pushes your current branch to a differently named remote branch. |
| `git add .` / `git add *` / `git add --all` | Every path must be named explicitly. Bulk adds hide accidental inclusions. |
| Submodule operations | Submodule repositories are not supported in v1. |

---

## How the safety model works

Every write command goes through this chain before anything runs:

```
Your message
    │
    ▼
Local planner (regex)
    │  ← matches grammar, resolves file paths against snapshot, validates branch/remote rules
    ▼
Plan created  ← fingerprinted against current repo state
    │
    ▼
You review the plan  ← exact commands, files, message shown
    │
    ▼
You click Approve
    │
    ▼
Fingerprint re-checked  ← if repo changed since plan was made, execution is rejected
    │
    ▼
Git commands run sequentially
    │
    ▼
Snapshot refreshed and shown in UI
```

If any step fails — bad credentials, network error, non-fast-forward push, etc. — the error message from Git is surfaced directly in the chat. Steps already completed before the failure are reported so you know the partial state.
