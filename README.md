# AI Git Assistant

**Use plain English to manage your Git projects - no commands to memorise.**

AI Git Assistant is a cross-platform desktop app that turns what you want to do into the exact Git steps needed. Type something like *"commit all my changes with message 'Fix login bug'"* and the app shows you exactly what it will run - before running anything. You review, you approve, it executes.

---

## Current release

**0.7.9 - Phase 7.9** adds a guided **Conflict Resolver** for merge conflicts. It includes everything from Phase 7.8 plus recovery cards that can preview a resolution by keeping the local version, keeping the incoming remote version, or asking AI for a proposed merge. Nothing is written until you approve the preview, then the app applies the resolved content, marks the files resolved, and guides you to continue the merge.

It also lets GitHub HTTPS Git operations reuse the saved GitHub token for pull, push, fetch, tag push, and branch visibility checks, so Linux and fresh machines do not fall back to terminal password prompts when the app already has a valid token.

Versioning follows the product phase number: Phase 1 = `0.1.x`, Phase 2 = `0.2.x`, Phase 3 = `0.3.x`, Phase 4 = `0.4.x`, Phase 5 = `0.5.x`, Phase 6 = `0.6.x`, Phase 7 = `0.7.x`. The first release in a phase uses `.0`, so Phase 7 starts at `0.7.0`.

See [release notes](docs/RELEASE_NOTES.md) for the shipped feature list and Phase 2 hardening notes.

---

## What it does

- **Understands plain English** - type what you want, not `git add -A && git commit -m "..."`
- **Shows every step before running** - nothing happens without your approval
- **Works with any Git repository** on your machine
- **Gives you Git-client visibility** - inspect diffs, history, blame, branches, stashes, remotes, tags, and conflicts
- **Detects repository providers** - the right panel labels GitHub, GitLab, Bitbucket, Azure DevOps, local-only, and mixed-provider remotes
- **Helps ignore local noise** - selected untracked runtime files can be added to `.gitignore` from the file picker
- **Sets Git author identity** - configure global `user.name` and `user.email` from Settings before your first commit on a machine
- **Reuses your GitHub token for HTTPS Git** - GitHub pull, push, fetch, tag push, and branch checks can use the saved token without exposing it in the command line
- **Publishes local projects to GitHub** - create the remote repository, connect `origin`, and push the first `main` branch from inside the app
- **Guides blocked workflows** - when Git needs upstream tracking, author identity, GitHub push permission, divergent-branch handling, merge conflict resolution, or a better repository selection, the app recommends the next step
- **Connects to an AI provider** (optional) so it can understand requests the built-in patterns don't cover
- **Safe by design** - no force pushes, no hard resets, no surprises

---

## How it compares

| | AI Git Assistant | GitKraken | gut | GitHub Copilot |
|---|:---:|:---:|:---:|:---:|
| Desktop GUI | Yes | Yes | CLI only | CLI only |
| Plain English input | Yes | Partial | Yes | Yes |
| Shows plan before running | Yes, always | No | Partial | No |
| Works offline (Ollama) | Yes | Yes | No | No |
| Free - no subscription | Yes | No | Yes | No |
| No account needed | Yes | No | No | No |
| Built-in local planner (no API cost) | Yes | No | No | No |
| Approval gate before writes | Yes | No | Partial | No |
| Guided conflict workflow | Yes | Yes | No | No |

---

## Requirements


AI Git Assistant is packaged as a desktop app, so end users only need Git installed.

- **Windows:** Windows 10/11, 64-bit, with Git for Windows
- **Linux:** Ubuntu 22.04+, 64-bit, with Git
- **macOS:** Build path planned; public installer not released yet

No Python, Node.js, or Rust setup is required to use the installed app.

---

## Installation

1. Download the latest installer from the [Releases](https://github.com/aperasmo/ai-git-assistant-app/releases) page: **`.exe`** for Windows or **`.deb`** for Ubuntu Linux
2. Double-click the installer and follow the prompts
3. Launch **AI Git Assistant** from your Start menu or desktop shortcut

> Your settings and repositories are saved in your user profile's `.ai-git-assistant` folder and survive reinstalls and updates.

---

## Quick start (5 minutes)

### 1 - Add your repository

Click **+ Add** in the left sidebar and select your project folder.
The app automatically reads your branches, changed files, and remote connections.

### 2 - Set your Git author identity

Open **Settings** and fill in **Git Author Identity** once per machine. This saves the same global Git values as:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Git requires these values before the app can create commits.

### 3 - Run a command using the command bar

The bar at the bottom has two rows of buttons:

| Row | What it does |
|-----|-------------|
| **READ** | View status, diffs, commits, graph, branches, stashes, remotes, history, blame, conflicts |
| **WRITE** | Commit, push, pull, switch branch, stash, merge, tags, GitHub publish, release drafts, and more |

Click any button and the app walks you through it step by step.

### 4 - Or just type what you want

Use the text box at the very bottom. Examples that work right away:

```text
what changed?
show recent commits
show diff
show commit graph
history README.md
blame README.md
show stashes
show remotes
show tags
show tag v0.7.7
show conflicts
review status
set upstream to origin/main
commit all my changes with message "Fix login bug"
push and commit everything with message "Add dark mode"
stage changes then commit and push with message "Update readme"
switch to main
create branch feature/new-login
stash my changes
merge feature/new-login
create tag v0.7.7 with message "Release v0.7.7"
push tag v0.7.7
```

The app turns your sentence into a Git plan and shows it to you before doing anything.

---

## Setting up AI (optional but recommended)

The built-in planner handles most common requests. For everything else - unusual phrasing, complex multi-step tasks - you can connect an AI provider and the app becomes fully conversational.

### Step 1 - Get an API key

Choose one provider:

| Provider | Sign up | Best for |
|----------|---------|----------|
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com) | Most accurate |
| **Groq** | [console.groq.com](https://console.groq.com) | Fastest, generous free tier |
| **Google Gemini** | [aistudio.google.com](https://aistudio.google.com) | Free tier |
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Widely known |
| **Ollama** | [ollama.com](https://ollama.com) | 100% local, no key needed, requires separate install |

### Step 2 - Add it to the app

1. Click **Settings** in the top-right corner
2. Choose your provider from the dropdown
3. Paste your API key
4. Click **Save**
5. Click **Test connection** to confirm it works

### Step 3 - That's it

From now on, any request the app doesn't recognise locally is automatically sent to your AI provider. You still see and approve every step - the AI just figures out what steps to take.

In the commit wizard, enable AI for the repository and choose a commit-message style: **Detailed**, **Concise**, **Conventional**, or **Release**. Click **Generate with AI** to draft one consolidated commit message from the selected files. For multi-file changes, the app sends an organized in-memory context pack first - grouped paths, change status, diff stats, detected domains, recent commit subjects, and concise file hints - then the selected diff/file snippets, so the AI can produce a broader subject plus useful body bullets instead of overfitting to one file.

---

## GitHub platform actions

Add a fine-grained GitHub token in **Settings** for the target repository with **Repository permissions -> Contents -> Read and write** and **Pull requests -> Read and write**.

Phase 7.7 includes a guided **Release manager** flow in the WRITE command bar. Choose **Release manager**, then select **Create new draft** or **Edit existing draft**, select an existing tag or type a new one, enter the title, write markdown release notes in the larger description editor, and attach one or more installer assets.

The app creates a new GitHub draft release if the tag has no draft yet. If you choose **Edit existing draft**, the app retrieves the existing draft title, release notes, release URL, and uploaded assets from GitHub before you continue. The asset picker shows what is already attached before you browse for new installers. On confirmation, it updates that draft and uploads only the new selected assets. Existing asset filenames are reported and skipped instead of being replaced silently.

When a new draft is created for a tag that does not exist yet, the app also creates the missing GitHub tag ref first so the release appears in both GitHub **Releases** and **Tags**.

Phase 7.8 adds **Publish GitHub** for local-only repositories. Choose **Publish GitHub**, select the files for the first publish commit if needed, enter the commit message, repository name, description, and visibility, then confirm. The app creates the GitHub repo, commits selected files, renames the branch to `main`, adds `origin`, and pushes with upstream tracking.

Phase 7.8 also improves recovery when local and remote history do not line up. If a push is rejected because the remote has newer commits, the app explains that the local commit was created and offers to fetch, pull latest, or view differences.

Phase 7.9 adds a guided **Conflict Resolver** when a merge stops on conflicts. The recovery card can show conflicts, continue or abort the merge, or preview an automated resolution. Deterministic options keep either the local or incoming version. The AI option uses the configured provider only after repository AI context is enabled, returns a preview first, and still requires your approval before the app writes resolved files.

Phase 6.1 adds a guided **Draft PR** flow in the WRITE command bar. Choose **Draft PR**, enter the base branch, optionally generate the title/body/checklist with AI, review or edit the text, then confirm the readiness summary. GitHub repositories create draft Pull Requests. GitLab repositories create draft Merge Requests. The app checks that the branch is named, the base differs from the current branch, conflicts are resolved, local commits are pushed, and the provider can see the head branch.

Phase 6.2 adds **Review status** in the READ command bar and right-panel quick actions. It finds the open GitHub Pull Request or GitLab Merge Request for the current branch, then shows CI/check status, draft state, base/head branches, review summary, comment count, and recent comments.

Phase 4.3 adds provider awareness before platform actions run. If the selected repository is Bitbucket, Azure DevOps, local-only, or unknown, the app explains which platform actions are not available for that repository while confirming local Git workflows still work.

If GitHub rejects release, PR, or push requests with a token permission error, create or update a fine-grained token for that exact repository, enable **Contents: Read and write** and **Pull requests: Read and write**, save it again in Settings, then retry. To create brand-new GitHub repositories from **Publish GitHub**, use a token that is allowed to create repositories for your account or organization.

---

## GitLab and other providers

AI Git Assistant works with GitLab, Bitbucket, Azure DevOps, and self-hosted remotes as a normal Git client today. Status, staging, commits, push, pull, fetch, logs, diffs, branches, stashes, merges, tags, and AI summaries use standard Git and are provider-neutral.

Provider-specific platform features are guarded by the selected repository's remotes:

- **GitHub:** draft release publishing and draft pull request creation are available now
- **GitLab:** draft merge request creation is available now; release publishing is planned
- **Bitbucket:** normal Git workflows work now; pull requests are planned
- **Azure DevOps:** normal Git workflows work now; platform integrations are planned
- **Local only / unknown:** local Git workflows work now; platform actions stay disabled

---

## Cross-platform status

Phase 7.9 continues Mac and Linux support by removing Windows-only build assumptions from the project scripts, fixing Ubuntu verification blockers, confirming Ubuntu `.deb` packaging, adding Git author identity setup in Settings for new machines, and turning common setup blockers into guided next steps. It also adds GitHub push-auth recovery, divergent-branch recovery when fast-forward pull is blocked, push-rejected recovery when the remote has newer commits, guided merge-conflict recovery with preview/apply resolution choices, a Release Manager path for one release with Windows/Linux assets, and a Publish GitHub flow for local-only repositories.

| Host OS | Status |
|---|---|
| Windows | Supported and release-built with NSIS |
| macOS | Build path prepared; signed/notarized release still pending |
| Linux | Ubuntu 22.04 `.deb` packaging verified; AppImage still pending because the downloader timed out |

One-command installer builds:

```powershell
npm run installer
```

`npm run installer` runs the sidecar tests, builds the sidecar binary, then builds the native installer for the host OS. The explicit variants are available when you want to be clear:

```powershell
npm run installer:windows
npm run installer:linux
npm run installer:mac
```

Current bundle defaults are Windows NSIS, Linux `.deb`, and macOS `.dmg`. Each OS still needs to build on its own host or CI runner because Tauri, PyInstaller, WebView dependencies, signing, and installer tooling are platform-specific.

Advanced lower-level commands are still available:

```powershell
npm run sidecar:test
npm run sidecar:build
npm run tauri:build:windows
npm run tauri:build:mac
npm run tauri:build:linux
```

Source builds require Node 20+, Rust stable, Python 3.12+, and Git 2.25+.

---

## The approval screen

Every write operation (commit, push, branch, etc.) shows a plan like this before running:

```text
1. Stage 3 files
   git add -- src/App.tsx src/login.py README.md

2. Create commit
   git commit -m "Fix login bug"

3. Push to origin
   git push origin main
```

Click **Approve and execute** to run it, or **Cancel** to go back. Nothing ever runs without your explicit approval.

---

## Supported commands

### Read (instant, no approval needed)

| What to type | What it does |
|---|---|
| `what changed?` | Show modified, staged, and untracked files |
| `show recent commits` | Last 10 commits with hash and message |
| `show diff` | Line-by-line changes in modified files |
| `show commit graph` | Visual branch and commit graph |
| `show stashes` | Local stash entries |
| `inspect stash@{0}` | Patch for one stash entry |
| `show remotes` | Configured remote URLs |
| `show tags` | Local release tags |
| `show tag v0.7.7` | Inspect one tag |
| `history README.md` | File-specific commit history |
| `blame README.md` | Line authorship for one file |
| `show conflicts` | Conflict files and resolution guidance |
| `review status` | Current branch PR/MR CI, reviews, and comments |
| `list branches` | All local and remote branches |
| `fetch` | Refresh remote status and ahead/behind counts |

### Write (always shows a plan first)

| What to type | What it does |
|---|---|
| `commit all my changes with message "..."` | Stage everything and commit |
| `commit and push with message "..."` | Stage, commit, and push |
| `push` | Push current branch to remote |
| `pull` | Fast-forward pull from remote |
| `switch to main` | Checkout branch |
| `create branch feature/name` | New branch from HEAD |
| `delete branch feature/name` | Safely delete a merged local branch |
| `stash my changes` | Save work in progress |
| `stash pop` | Restore last stash |
| `apply stash stash@{0}` | Apply a specific stash without dropping it |
| `drop stash stash@{0}` | Delete a specific stash after approval |
| `merge feature/name` | Merge a local branch with guided conflict handling |
| `continue merge` | Commit a resolved merge |
| `abort merge` | Abort an in-progress merge |
| `create tag v0.7.7 with message "Release v0.7.7"` | Create an annotated local tag |
| `push tag v0.7.7` | Push one explicit tag to the remote |
| `delete tag v0.7.7` | Delete a local tag after approval |
| `publish github` | Create a GitHub repository for a local-only project and push `main` |
| `release manager` / `draft release` | Create or update a GitHub draft release and upload installer assets |
| `draft PR` | Create a GitHub draft PR or GitLab draft MR from the current branch |
| `unstage login.py` | Remove file from staging |
| `discard changes in login.py` | Revert file to last commit |

Or click any button in the command bar for a guided step-by-step wizard.

---

## 20 common Git functions coverage

> **18/20 available in app.** AI Git Assistant already covers the day-to-day Git workflow from the common "20 important Git functions" list. The remaining two are intentionally treated carefully: `git revert` is safe and planned for a reviewed app workflow; `git reset --hard` is destructive and intentionally blocked.

| # | Function | App status |
|---|---|---|
| 1 | Initialize repository | Available |
| 2 | Clone repository | Available |
| 3 | Check status | Available |
| 4 | Add/stage files | Available |
| 5 | Commit changes | Available |
| 6 | View commit history | Available |
| 7 | Short log view | Available |
| 8 | Create branch | Available |
| 9 | Switch branch | Available |
| 10 | Create and switch branch | Available |
| 11 | Merge branch | Available |
| 12 | Delete branch | Available |
| 13 | Push changes | Available |
| 14 | Pull changes | Available, fast-forward only |
| 15 | Fetch changes | Available |
| 16 | Check differences | Available |
| 17 | Undo staging | Available |
| 18 | Revert commit | Planned |
| 19 | Reset to previous state | Blocked by design |
| 20 | Stash changes | Available |

**Why the two exceptions?** `git revert <commit>` creates a new commit that undoes an older commit, so it preserves history and is safe for shared branches. `git reset --hard <commit>` rewrites the current state and can permanently discard local work, so the app does not expose it as a normal workflow.

---

## Git visibility features

AI Git Assistant is not just a chat box. It also gives you the day-to-day Git views people expect from a desktop client:

- **Status view** - staged, modified, untracked, and conflicted files
- **Full patch diff** - line-by-line additions and removals
- **Commit graph** - visual history across branches
- **File history** - follow changes to a specific file
- **Blame** - see who last changed each line
- **Stash tools** - list, inspect, apply, pop, and drop stashes
- **Remote view** - see configured remotes and refresh ahead/behind counts
- **Remote provider awareness** - label GitHub, GitLab, Bitbucket, Azure DevOps, unknown, local-only, and mixed-provider remotes
- **Review status** - read current branch GitHub PR or GitLab MR CI/check status, reviews, and comments
- **Release tags** - list, inspect, create, push, and delete explicit tags
- **Conflict resolver** - list conflicted files, preview local/remote/AI resolutions, apply after approval, then continue or abort

---

## Agent worktrees

Phase 5 adds an **Agent worktrees** section in the right panel. It lets you create an isolated Git worktree from the selected repository for a task, then track the session from inside the app.

Current Phase 5 controls:

- **Create** an isolated worktree and generated `agent/...` branch for a task
- **Refresh** active sessions with branch, status, working changes, commits ahead, and latest commit
- **Compare** the session against its base branch, including commits, changed files, diff stat, and working-tree status
- **Merge** an active session back into the selected repository after the agent branch has commits and the main repository is clean
- **Abandon** an active session by removing the worktree and deleting its generated branch
- **Clean** merged or abandoned session files while keeping the session record

This is the first control-plane slice. The app creates and manages the isolated worktree; the actual coding agent or editor can work inside that worktree, commit to the agent branch, then return to AI Git Assistant for compare and merge.

---

## Walkthrough tour

New to the app? Click the **?** button in the top-right corner to launch a guided tour that highlights every part of the interface.

---

## Git command reference

Click **Help** in the top-right corner for a workflow cheat sheet of supported commands - grouped by setup, stage/snapshot, branch/merge, share/release, inspect/compare, and advanced safety. Each card shows app phrases, the matching Git command, and whether the action is available in-app, planned, terminal-only, or blocked.

---

## Troubleshooting

**"Git check pending" in the top bar**
Git for Windows is not installed or not on your PATH.
Download it from [git-scm.com/download/win](https://git-scm.com/download/win) and restart the app.

**"The local planner did not recognise this request"**
Either rephrase your request, or set up an AI provider in Settings - it will handle anything the built-in patterns miss.

**Test connection shows an error**
Double-check your API key. Make sure you clicked **Save** before clicking **Test connection**.

**GitHub platform action is rejected**
Create or update a fine-grained GitHub token for the exact repository and set **Repository permissions -> Contents -> Read and write** and **Pull requests -> Read and write**. Save the token again in Settings, then retry.

**Ollama: connection failed**
Ollama must be running before the app can use it. Open a terminal and run `ollama serve`, then try again.
Also make sure you have pulled a model first: `ollama pull deepseek-r1:8b`

**Something failed and you want to report it**
Open the diagnostics panel and export the local logs. The log export is designed for bug reports and support.

**The app remembered my repositories from a previous install**
Settings and repo list are stored in your user profile's `.ai-git-assistant/ai-git-assistant.db`.
Delete that file for a completely clean start.

---

## Privacy

- Your code and file contents are **never sent anywhere automatically**
- Only the **names of changed files**, current **branch**, and your **typed request** are sent to the AI provider when the AI fallback is used
- If you click **Generate with AI** for a commit message, grouped selected-file context, diff stats, recent commit subjects, and the selected diff/file snippets are sent to your configured provider
- If you click **Analyze changes**, the receipt shows the exact selected diff context sent to the configured AI provider
- If you publish or update a GitHub draft release, the tag, title, description, and selected assets are sent to GitHub using your saved token
- If you publish a local repository to GitHub, the repository name, description, visibility, branch, commit, and selected files are sent to GitHub through standard Git/GitHub APIs
- If you generate PR/MR text with AI, the base/head branches, commits, changed-file list, diff stats, and recent commit subjects are sent to your configured provider
- If you create a GitHub draft pull request, the base branch, current branch, title, and description are sent to GitHub using your saved token
- If you create a GitLab draft merge request, the base branch, current branch, title, and description are sent to GitLab using your saved token
- If you use **Review status**, the current branch and repository identity are sent to GitHub or GitLab using your saved token so the app can read PR/MR metadata, CI/check status, reviews, and comments
- API keys, GitHub tokens, and GitLab tokens are stored locally with Windows DPAPI on Windows and portable local encryption on macOS/Linux
- If you use Ollama, everything stays on your machine - nothing leaves your computer

---

## Roadmap

- **Phase 5:** Agent worktree control plane
- **Phase 6:** PR and review workflow
- **Phase 7:** Mac and Linux release support
- **Phase 8:** Team context and conventions

---

## Feedback

Found a bug or have a suggestion? Open an issue on this repository and describe what happened.

---

*Built with [Tauri](https://tauri.app) · [React](https://react.dev) · Python FastAPI · Phase 7*
