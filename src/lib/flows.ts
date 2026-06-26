import type { ReadAction } from "./types";

export type WizardFlowId =
  | "status"
  | "log"
  | "diff"
  | "branches"
  | "commit_push"
  | "stage_only"
  | "switch_branch"
  | "pull"
  | "stash"
  | "discard"
  | "connect_remote";

export interface FlowDef {
  id: WizardFlowId;
  label: string;
  icon: string;
  description: string;
  category: "read" | "write";
}

export const FLOWS: FlowDef[] = [
  { id: "status",        label: "What changed?",    icon: "◉", description: "Working tree status",      category: "read"  },
  { id: "log",           label: "Recent commits",   icon: "⊙", description: "View commit history",      category: "read"  },
  { id: "diff",          label: "View differences", icon: "⊟", description: "Show unstaged changes",    category: "read"  },
  { id: "branches",      label: "All branches",     icon: "⑂", description: "List local & remote",      category: "read"  },
  { id: "commit_push",   label: "Commit & push",    icon: "↑", description: "Stage, commit and push",   category: "write" },
  { id: "stage_only",    label: "Stage & commit",   icon: "✔", description: "Stage files and commit",   category: "write" },
  { id: "switch_branch", label: "Switch branch",    icon: "⇄", description: "Checkout another branch",  category: "write" },
  { id: "pull",          label: "Pull latest",      icon: "↓", description: "Pull from remote",         category: "write" },
  { id: "stash",         label: "Stash changes",    icon: "◫", description: "Save work in progress",    category: "write" },
  { id: "discard",        label: "Discard changes",  icon: "↩", description: "Revert file changes",      category: "write" },
  { id: "connect_remote", label: "Connect remote",   icon: "⇡", description: "Add GitHub/GitLab origin", category: "write" },
];

export const FLOW_LABELS: Record<WizardFlowId, string> = Object.fromEntries(
  FLOWS.map((f) => [f.id, f.label]),
) as Record<WizardFlowId, string>;

export interface WizardData {
  files?: string[];
  message?: string;
  remote?: string;
  branch?: string;
}

export interface WizardState {
  flowId: WizardFlowId;
  currentStepId: string;
  currentStepKind: "file_pick" | "text_input" | "option_select" | "confirm";
  data: WizardData;
}

export const FLOW_READ_ACTIONS: Partial<Record<WizardFlowId, ReadAction>> = {
  status:   "status",
  log:      "log",
  diff:     "diff",
  branches: "branches",
  fetch:    "fetch",
};
