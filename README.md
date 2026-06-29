# AI Git Assistant

**Use plain English to manage your Git projects — no commands to memorise.**

AI Git Assistant is a Windows desktop app that turns what you want to do into the exact Git steps needed. Type something like *"commit all my changes with message 'Fix login bug'"* and the app shows you exactly what it will run — before running anything. You review, you approve, it executes.

---

## What it does

- **Understands plain English** — type what you want, not `git add -A && git commit -m "…"`
- **Shows every step before running** — nothing happens without your approval
- **Works with any Git repository** on your machine
- **Connects to an AI provider** (optional) so it can understand requests the built-in patterns don't cover
- **Safe by design** — no force pushes, no hard resets, no surprises

---

## How it compares

| | AI Git Assistant | GitKraken | gut | GitHub Copilot |
|---|:---:|:---:|:---:|:---:|
| Desktop GUI | ✅ | ✅ | ❌ CLI only | ❌ CLI only |
| Plain English input | ✅ | ❌ partial | ✅ | ✅ |
| Shows plan before running | ✅ always | ❌ | partial | ❌ |
| Works offline (Ollama) | ✅ | ✅ | ❌ | ❌ |
| Free — no subscription | ✅ | ❌ | ✅ | ❌ |
| No account needed | ✅ | ❌ | ❌ | ❌ |
| Built-in local planner (no API cost) | ✅ | ❌ | ❌ | ❌ |

---

## Requirements

- Windows 10 or 11 (64-bit)
- [Git for Windows](https://git-scm.com/download/win) installed

That's it. No Python, no Node.js, nothing else to install.

---

## Installation

1. Download **`AI Git Assistant_0.1.0_x64-setup.exe`** from the [Releases](https://github.com/aperasmo/ai-git-assistant-app/releases) page
2. Double-click the installer and follow the prompts
3. Launch **AI Git Assistant** from your Start menu or desktop shortcut

> Your settings and repositories are saved in `C:\Users\<you>\.ai-git-assistant\` and survive reinstalls and updates.

---

## Quick start (5 minutes)

### 1 — Add your repository

Click **+ Add** in the left sidebar and select your project folder.
The app automatically reads your branches, changed files, and remote connections.

### 2 — Run a command using the command bar

The bar at the bottom has two rows of buttons:

| Row | What it does |
|-----|-------------|
| **READ** | View status, recent commits, file differences, branches |
| **WRITE** | Commit, push, pull, switch branch, stash, and more |

Click any button and the app walks you through it step by step.

### 3 — Or just type what you want

Use the text box at the very bottom. Examples that work right away:

```
what changed?
show recent commits
commit all my changes with message "Fix login bug"
push and commit everything with message "Add dark mode"
stage changes then commit and push with message "Update readme"
switch to main
create branch feature/new-login
stash my changes
```

The app turns your sentence into a Git plan and shows it to you before doing anything.

---

## Setting up AI (optional but recommended)

The built-in planner handles most common requests. For everything else — unusual phrasing, complex multi-step tasks — you can connect an AI provider and the app becomes fully conversational.

### Step 1 — Get an API key

Choose one provider (all have free tiers or cheap pay-as-you-go):

| Provider | Sign up | Best for |
|----------|---------|----------|
| **Anthropic (Claude)** | [console.anthropic.com](https://console.anthropic.com) | Most accurate |
| **Groq** | [console.groq.com](https://console.groq.com) | Fastest, generous free tier |
| **Google Gemini** | [aistudio.google.com](https://aistudio.google.com) | Free tier |
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Widely known |
| **Ollama** | [ollama.com](https://ollama.com) | 100% local, no key needed, requires separate install |

### Step 2 — Add it to the app

1. Click **Settings** in the top-right corner
2. Choose your provider from the dropdown
3. Paste your API key
4. Click **Save**
5. Click **Test connection** to confirm it works

### Step 3 — That's it

From now on, any request the app doesn't recognise locally is automatically sent to your AI provider. You still see and approve every step — the AI just figures out what steps to take.

---

## The approval screen

Every write operation (commit, push, branch, etc.) shows a plan like this before running:

```
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
| `list branches` | All local and remote branches |
| `fetch` | Refresh remote status (ahead/behind counts) |

### Write (always shows a plan first)
| What to type | What it does |
|---|---|
| `commit all my changes with message "..."` | Stage everything + commit |
| `commit and push with message "..."` | Stage + commit + push |
| `push` | Push current branch to remote |
| `pull` | Fast-forward pull from remote |
| `switch to main` | Checkout branch |
| `create branch feature/name` | New branch from HEAD |
| `stash my changes` | Save work in progress |
| `stash pop` | Restore last stash |
| `unstage login.py` | Remove file from staging |
| `discard changes in login.py` | Revert file to last commit |

Or click any button in the command bar for a guided step-by-step wizard.

---

## Walkthrough tour

New to the app? Click the **?** button in the top-right corner to launch a guided tour that highlights every part of the interface.

---

## Git command reference

Click **Help** in the top-right corner for a full reference of every supported command — including syntax, examples, and which ones require a terminal.

---

## Troubleshooting

**"Git check pending" in the top bar**
Git for Windows is not installed or not on your PATH.
Download it from [git-scm.com/download/win](https://git-scm.com/download/win) and restart the app.

**"The local planner did not recognise this request"**
Either rephrase your request, or set up an AI provider in Settings — it will handle anything the built-in patterns miss.

**Test connection shows an error**
Double-check your API key. Make sure you clicked **Save** before clicking **Test connection**.

**Ollama: connection failed**
Ollama must be running before the app can use it. Open a terminal and run `ollama serve`, then try again.
Also make sure you have pulled a model first: `ollama pull deepseek-r1:8b`

**The app remembered my repositories from a previous install**
Settings and repo list are stored in `C:\Users\<you>\.ai-git-assistant\ai-git-assistant.db`.
Delete that file for a completely clean start.

---

## Privacy

- Your code and file contents are **never sent anywhere**
- Only the **names of changed files**, current **branch**, and your **typed request** are sent to the AI provider when the AI fallback is used
- If you use Ollama, everything stays on your machine — nothing leaves your computer

---

## Feedback

Found a bug or have a suggestion? Open an issue on this repository and describe what happened.

---

*Built with [Tauri](https://tauri.app) · [React](https://react.dev) · Python FastAPI · Phase A*
