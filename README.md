# AI Git Assistant

**Use plain English to manage your Git projects - no commands to memorise.**

AI Git Assistant is a Windows desktop app that turns what you want to do into the exact Git steps needed. Type something like *"commit all my changes with message 'Fix login bug'"* and the app shows you exactly what it will run - before running anything. You review, you approve, it executes.

---

## Current release

**0.4.4 - Phase D.4** is the current AI-native Git workflow release. It includes everything from Phase C plus premium AI commit-message generation, AI change summaries, logical commit suggestions, PR-ready summaries, plan risk scoring, privacy receipts for AI context, GitHub draft release publishing with installer asset upload, repository remote provider awareness, and richer commit-message style controls.

Versioning follows the product phase: Phase A = `0.1.x`, Phase B = `0.2.x`, Phase C = `0.3.x`, Phase D = `0.4.x`. Sub-phase improvements stay inside the same phase line, so Phase D.4 uses `0.4.4`.

See [release notes](docs/RELEASE_NOTES.md) for the shipped feature list and Phase B hardening notes.

---

## What it does

- **Understands plain English** - type what you want, not `git add -A && git commit -m "..."`
- **Shows every step before running** - nothing happens without your approval
- **Works with any Git repository** on your machine
- **Gives you Git-client visibility** - inspect diffs, history, blame, branches, stashes, remotes, tags, and conflicts
- **Detects repository providers** - the right panel labels GitHub, GitLab, Bitbucket, Azure DevOps, local-only, and mixed-provider remotes
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

- Windows 10 or 11 (64-bit)
- [Git for Windows](https://git-scm.com/download/win) installed

That's it. No Python, no Node.js, nothing else to install.

---

## Installation

1. Download the latest **`AI Git Assistant_*_x64-setup.exe`** installer from the [Releases](https://github.com/aperasmo/ai-git-assistant-app/releases) page
2. Double-click the installer and follow the prompts
3. Launch **AI Git Assistant** from your Start menu or desktop shortcut

> Your settings and repositories are saved in `C:\Users\<you>\.ai-git-assistant\` and survive reinstalls and updates.

---

## Quick start (5 minutes)

### 1 - Add your repository

Click **+ Add** in the left sidebar and select your project folder.
The app automatically reads your branches, changed files, and remote connections.

### 2 - Run a command using the command bar

The bar at the bottom has two rows of buttons:

| Row | What it does |
|-----|-------------|
| **READ** | View status, diffs, commits, graph, branches, stashes, remotes, history, blame, conflicts |
| **WRITE** | Commit, push, pull, switch branch, stash, merge, tags, release drafts, and more |

Click any button and the app walks you through it step by step.

### 3 - Or just type what you want

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
show tag v0.4.4
show conflicts
commit all my changes with message "Fix login bug"
push and commit everything with message "Add dark mode"
stage changes then commit and push with message "Update readme"
switch to main
create branch feature/new-login
stash my changes
merge feature/new-login
create tag v0.4.4 with message "Release v0.4.4"
push tag v0.4.4
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

## GitHub release publishing

Phase D.2 includes a guided **Draft release** flow in the WRITE command bar. Add a fine-grained GitHub token in **Settings** for the target repository with **Repository permissions -> Contents -> Read and write**, then choose **Draft release** to enter the tag, title, description, and installer asset.

The app creates a new GitHub draft release and uploads one asset only after you confirm the final wizard step. Updating existing releases, replacing assets, and retargeting existing tags are intentionally not part of the current flow.

Phase D.3 adds provider awareness before platform actions run. If the selected repository is GitLab, Bitbucket, Azure DevOps, local-only, or unknown, the app explains that GitHub draft releases are not available for that repository while confirming local Git workflows still work.

If GitHub rejects the request with a token permission error, create or update a fine-grained token for that exact repository, enable **Contents: Read and write**, save it again in Settings, then retry.

---

## GitLab and other providers

AI Git Assistant works with GitLab, Bitbucket, Azure DevOps, and self-hosted remotes as a normal Git client today. Status, staging, commits, push, pull, fetch, logs, diffs, branches, stashes, merges, tags, and AI summaries use standard Git and are provider-neutral.

Provider-specific platform features are guarded by the selected repository's remotes:

- **GitHub:** draft release publishing is available now
- **GitLab:** normal Git workflows work now; merge requests and releases are planned
- **Bitbucket:** normal Git workflows work now; pull requests are planned
- **Azure DevOps:** normal Git workflows work now; platform integrations are planned
- **Local only / unknown:** local Git workflows work now; platform actions stay disabled

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
| `show tag v0.4.4` | Inspect one tag |
| `history README.md` | File-specific commit history |
| `blame README.md` | Line authorship for one file |
| `show conflicts` | Conflict files and resolution guidance |
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
| `create tag v0.4.4 with message "Release v0.4.4"` | Create an annotated local tag |
| `push tag v0.4.4` | Push one explicit tag to the remote |
| `delete tag v0.4.4` | Delete a local tag after approval |
| `draft release` | Create a GitHub draft release and upload one asset |
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
- **Release tags** - list, inspect, create, push, and delete explicit tags
- **Conflict guide** - list conflicted files, show conflict marker snippets, then continue or abort

---

## Walkthrough tour

New to the app? Click the **?** button in the top-right corner to launch a guided tour that highlights every part of the interface.

---

## Git command reference

Click **Help** in the top-right corner for a full reference of every supported command - including syntax, examples, and which ones require a terminal. The help card also calls out planned and blocked commands such as `git revert <commit>` and `git reset --hard <commit>`.

---

## Troubleshooting

**"Git check pending" in the top bar**
Git for Windows is not installed or not on your PATH.
Download it from [git-scm.com/download/win](https://git-scm.com/download/win) and restart the app.

**"The local planner did not recognise this request"**
Either rephrase your request, or set up an AI provider in Settings - it will handle anything the built-in patterns miss.

**Test connection shows an error**
Double-check your API key. Make sure you clicked **Save** before clicking **Test connection**.

**GitHub release publishing is rejected**
Create or update a fine-grained GitHub token for the exact repository and set **Repository permissions -> Contents -> Read and write**. Save the token again in Settings, then retry the draft release.

**Ollama: connection failed**
Ollama must be running before the app can use it. Open a terminal and run `ollama serve`, then try again.
Also make sure you have pulled a model first: `ollama pull deepseek-r1:8b`

**Something failed and you want to report it**
Open the diagnostics panel and export the local logs. The log export is designed for bug reports and support.

**The app remembered my repositories from a previous install**
Settings and repo list are stored in `C:\Users\<you>\.ai-git-assistant\ai-git-assistant.db`.
Delete that file for a completely clean start.

---

## Privacy

- Your code and file contents are **never sent anywhere automatically**
- Only the **names of changed files**, current **branch**, and your **typed request** are sent to the AI provider when the AI fallback is used
- If you click **Generate with AI** for a commit message, grouped selected-file context, diff stats, recent commit subjects, and the selected diff/file snippets are sent to your configured provider
- If you click **Analyze changes**, the receipt shows the exact selected diff context sent to the configured AI provider
- If you publish a GitHub draft release, the tag, title, description, and selected asset are sent to GitHub using your saved token
- API keys and GitHub tokens are stored locally with Windows encryption
- If you use Ollama, everything stays on your machine - nothing leaves your computer

---

## Roadmap

- **Phase E:** Agent worktree control plane
- **Phase F:** PR and review workflow
- **Phase G:** Mac and Linux support
- **Phase H:** Team context and conventions

---

## Feedback

Found a bug or have a suggestion? Open an issue on this repository and describe what happened.

---

*Built with [Tauri](https://tauri.app) · [React](https://react.dev) · Python FastAPI · Phase D.4*
