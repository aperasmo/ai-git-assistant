export type TooltipSide = "top" | "bottom" | "left" | "right" | "center";

export interface WalkthroughStep {
  target: string | null;
  title: string;
  body: string;
  side: TooltipSide;
  padding?: number;
}

export const WALKTHROUGH_STEPS: WalkthroughStep[] = [
  {
    target: null,
    title: "Welcome to AI Git Assistant",
    body: "This quick tour covers the essentials — adding a repository, running Git commands, and connecting to GitHub. Takes about 2 minutes.",
    side: "center",
  },
  {
    target: '[data-tour="add-repo"]',
    title: "Add your first repository",
    body: "Click + Add to open a local folder. If it isn't a Git repo yet, the app will offer to initialize one for you. You can also Clone from a remote URL.",
    side: "right",
    padding: 8,
  },
  {
    target: '[data-tour="repo-list"]',
    title: "Switch between projects",
    body: "All your repositories live here. Click any to switch instantly — each one keeps its own command history for the session.",
    side: "right",
    padding: 8,
  },
  {
    target: '[data-tour="command-read"]',
    title: "Read commands",
    body: "These show you what's happening — status, recent commits, file diffs, and branches — without changing anything in your repository.",
    side: "top",
    padding: 8,
  },
  {
    target: '[data-tour="command-write"]',
    title: "Write commands",
    body: "These make changes. Every write operation previews the exact Git commands it will run and asks for your confirmation before executing.",
    side: "top",
    padding: 8,
  },
  {
    target: '[data-tour="connect-remote"]',
    title: "Connect to GitHub or GitLab",
    body: "Starting a new project? Connect remote links your local repo to a remote URL so you can push and pull. It runs git remote add, renames your branch to main, and pushes — all in one step.",
    side: "top",
    padding: 8,
  },
  {
    target: null,
    title: "You're all set",
    body: "Start by adding a repository from the left sidebar. Use the ? button in the top bar to replay this tour at any time.",
    side: "center",
  },
];
