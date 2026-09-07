import type { ConflictResolvedFile, ConflictResolutionStrategy, ReadAction } from "./types";

export type WizardFlowId =
  | "status"
  | "log"
  | "diff"
  | "graph"
  | "branches"
  | "stashes"
  | "remotes"
  | "tags"
  | "conflicts"
  | "review_status"
  | "fetch"
  | "commit_push"
  | "stage_only"
  | "switch_branch"
  | "pull"
  | "stash"
  | "discard"
  | "revert"
  | "connect_remote"
  | "publish_github"
  | "resolve_conflict"
  | "draft_release"
  | "draft_pr";

export interface FlowDef {
  id: WizardFlowId;
  label: string;
  icon: string;
  description: string;
  category: "read" | "write";
}

export const FLOWS: FlowDef[] = [
  { id: "status", label: "What changed?", icon: "S", description: "Working tree status", category: "read" },
  { id: "log", label: "Recent commits", icon: "L", description: "View commit history", category: "read" },
  { id: "diff", label: "View differences", icon: "D", description: "Show patch diff", category: "read" },
  { id: "graph", label: "Commit graph", icon: "G", description: "Visual branch history", category: "read" },
  { id: "branches", label: "All branches", icon: "B", description: "List local branches", category: "read" },
  { id: "stashes", label: "Stashes", icon: "T", description: "Inspect saved work", category: "read" },
  { id: "remotes", label: "Remotes", icon: "R", description: "Show remote URLs", category: "read" },
  { id: "tags", label: "Tags", icon: "#", description: "List release tags", category: "read" },
  { id: "conflicts", label: "Conflicts", icon: "!", description: "Guided conflict status", category: "read" },
  { id: "review_status", label: "Review status", icon: "Y", description: "PR/MR reviews and CI", category: "read" },
  { id: "fetch", label: "Fetch remote", icon: "F", description: "Refresh remote status", category: "read" },
  { id: "commit_push", label: "Commit & push", icon: "P", description: "Stage, commit and push", category: "write" },
  { id: "stage_only", label: "Stage & commit", icon: "C", description: "Stage files and commit", category: "write" },
  { id: "switch_branch", label: "Switch branch", icon: "W", description: "Checkout another branch", category: "write" },
  { id: "pull", label: "Pull latest", icon: "U", description: "Pull from remote", category: "write" },
  { id: "stash", label: "Stash changes", icon: "H", description: "Save work in progress", category: "write" },
  { id: "discard", label: "Discard changes", icon: "X", description: "Revert file changes", category: "write" },
  { id: "revert", label: "Revert commit", icon: "Z", description: "Undo a commit with a new commit", category: "write" },
  { id: "connect_remote", label: "Connect remote", icon: "@", description: "Add GitHub/GitLab origin", category: "write" },
  { id: "publish_github", label: "Publish GitHub", icon: "O", description: "Create GitHub repo and push", category: "write" },
  { id: "draft_release", label: "Release manager", icon: "V", description: "Create or update a GitHub draft release", category: "write" },
  { id: "draft_pr", label: "Draft PR", icon: "Q", description: "Create a GitHub PR or GitLab MR", category: "write" },
];

export const FLOW_LABELS: Record<WizardFlowId, string> = Object.fromEntries(
  FLOWS.map((f) => [f.id, f.label]),
) as Record<WizardFlowId, string>;

export interface WizardData {
  files?: string[];
  message?: string;
  remote?: string;
  branch?: string;
  tagName?: string;
  releaseMode?: "create" | "edit";
  existingReleaseTitle?: string;
  existingReleaseBody?: string;
  releaseTitle?: string;
  releaseBody?: string;
  existingReleaseUrl?: string;
  existingReleaseAssets?: string[];
  assetPath?: string;
  assetPaths?: string[];
  prerelease?: boolean;
  githubRepoName?: string;
  githubRepoDescription?: string;
  githubPrivate?: boolean;
  publishStage?: "commit_message" | "repo_name" | "description" | "visibility";
  conflictStrategy?: ConflictResolutionStrategy;
  conflictResolvedFiles?: ConflictResolvedFile[];
  prBaseBranch?: string;
  prTitle?: string;
  prBody?: string;
  prProvider?: "github" | "gitlab";
  commitHash?: string;
}

export interface WizardState {
  flowId: WizardFlowId;
  currentStepId: string;
  currentStepKind: "file_pick" | "text_input" | "asset_pick" | "option_select" | "confirm";
  data: WizardData;
}

export const FLOW_READ_ACTIONS: Partial<Record<WizardFlowId, ReadAction>> = {
  status: "status",
  log: "log",
  diff: "diff",
  graph: "graph",
  branches: "branches",
  stashes: "stashes",
  remotes: "remotes",
  tags: "tags",
  conflicts: "conflicts",
  review_status: "review_status",
  fetch: "fetch",
};
