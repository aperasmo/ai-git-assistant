export type LLMProviderKind = "anthropic" | "gemini" | "ollama" | "openai" | "groq";

export interface LLMSettings {
  provider?: LLMProviderKind | null;
  apiKeySet: boolean;
  model?: string | null;
  baseUrl?: string | null;
}

export interface UpdateLLMSettingsRequest {
  provider?: LLMProviderKind | null;
  apiKey?: string | null;
  model?: string | null;
  baseUrl?: string | null;
}

export interface GitHubSettings {
  tokenSet: boolean;
}

export interface UpdateGitHubSettingsRequest {
  token?: string | null;
}

export type SidecarStatus = "starting" | "ready" | "failed" | "stopped";
export type GitStatusKind = "checking" | "available" | "missing" | "failed";

export type ReadAction =
  | "status"
  | "log"
  | "diff"
  | "branches"
  | "fetch"
  | "graph"
  | "stashes"
  | "stash_show"
  | "remotes"
  | "file_history"
  | "blame"
  | "conflicts"
  | "tags"
  | "tag_show";
export type PlanKind = "read" | "write" | "info";
export type PlanStepKind =
  | "read"
  | "stage"
  | "commit"
  | "push"
  | "pull"
  | "unstage"
  | "discard"
  | "switch"
  | "create_branch"
  | "stash"
  | "stash_pop"
  | "stash_apply"
  | "stash_drop"
  | "merge"
  | "merge_abort"
  | "merge_commit"
  | "create_tag"
  | "delete_tag"
  | "push_tag"
  | "delete_branch"
  | "add_remote"
  | "rename_branch";

export interface BootstrapStatus {
  sidecarStatus: SidecarStatus;
  message: string;
  protocolVersion?: string | null;
}

export interface GitInstallationStatus {
  status: GitStatusKind;
  version?: string | null;
  message: string;
}

export interface DiagnosticsStatus {
  appVersion: string;
  environment: string;
  protocolVersion: string;
  databasePath: string;
  databaseExists: boolean;
  repositoryCount: number;
  gitStatus: string;
  gitVersion?: string | null;
  llmProvider?: string | null;
  llmModel?: string | null;
  llmApiKeySet: boolean;
  apiKeyStorage: string;
  generatedAt: string;
  recentSidecarMessages: string[];
}

export interface Repository {
  id: string;
  displayName: string;
  pathLabel: string;
  currentBranch?: string | null;
  externalLlmAllowed: boolean;
  lastOpenedAt: string;
  lastRemoteRefreshAt?: string | null;
}

export type FolderClassificationKind =
  | "existing_repository"
  | "nested_repository"
  | "initialisation_required"
  | "unsupported_repository";

export interface FolderClassification {
  kind: FolderClassificationKind;
  selectedPath: string;
  repositoryRoot?: string | null;
  canInitialise: boolean;
  message?: string | null;
}

export interface ChangedPath {
  path: string;
  indexStatus: string;
  worktreeStatus: string;
  kind: "staged" | "modified" | "untracked" | "conflict";
}

export interface RecentCommit {
  fullHash: string;
  shortHash: string;
  author: string;
  committedAt: string;
  subject: string;
}

export interface BranchInfo {
  name: string;
  isCurrent: boolean;
  upstream?: string | null;
}

export type RemoteProviderKind = "github" | "gitlab" | "bitbucket" | "azure_devops" | "unknown";

export interface RemoteProviderInfo {
  remote: string;
  provider: RemoteProviderKind;
  label: string;
  host?: string | null;
  url?: string | null;
}

export interface RepositorySnapshot {
  repositoryId: string;
  branch?: string | null;
  headCommit?: string | null;
  upstreamRemote?: string | null;
  upstreamBranch?: string | null;
  stagedChanges: ChangedPath[];
  modifiedChanges: ChangedPath[];
  untrackedPaths: ChangedPath[];
  conflicts: ChangedPath[];
  ahead: number;
  behind: number;
  remoteLastRefreshedAt?: string | null;
  writeBlockedReason?: string | null;
  fingerprint: string;
  recentCommits: RecentCommit[];
  remoteNames: string[];
  remoteUrls: Record<string, string>;
  remoteProviders: RemoteProviderInfo[];
  localBranches: BranchInfo[];
}

export interface ReadActionRequest {
  action: ReadAction;
  params?: Record<string, string | number | boolean | null>;
}

export interface ReadActionResult {
  action: ReadAction;
  title: string;
  summary: string;
  content: string;
  contentKind?: "text" | "diff" | "graph";
  snapshot: RepositorySnapshot;
}

export interface LocalResolution {
  matched: boolean;
  action?: ReadAction | null;
  params: Record<string, string | number | boolean | null>;
  explanation: string;
}

export interface ActionPlanStep {
  kind: PlanStepKind;
  title: string;
  detail: string;
  paths: string[];
  commitMessage?: string | null;
  remote?: string | null;
  branch?: string | null;
  remoteUrl?: string | null;
  stashRef?: string | null;
  tagName?: string | null;
  commandPreview?: string | null;
  ahead?: number | null;
  behind?: number | null;
  force?: boolean | null;
  setUpstream?: boolean | null;
}

export interface PlanRisk {
  level: "low" | "medium" | "high";
  score: number;
  summary: string;
  reasons: string[];
}

export interface PrivacyReceipt {
  externalProvider: boolean;
  purpose: string;
  provider?: string | null;
  model?: string | null;
  contextItems: string[];
  files: string[];
  characterCount: number;
  truncated: boolean;
  exactContext?: string | null;
}

export interface LocalActionPlan {
  matched: boolean;
  repositoryId: string;
  message: string;
  planKind?: PlanKind | null;
  requiresConfirmation: boolean;
  planId?: string | null;
  readAction?: ReadAction | null;
  readParams: Record<string, string | number | boolean | null>;
  steps: ActionPlanStep[];
  explanation: string;
  source: "local" | "llm";
  risk?: PlanRisk | null;
  privacyReceipt?: PrivacyReceipt | null;
}

export interface ActionExecutionResult {
  planId: string;
  title: string;
  summary: string;
  content: string;
  contentKind?: "text" | "diff" | "graph";
  snapshot: RepositorySnapshot;
}

export type CommitMessageStyle = "concise" | "detailed" | "conventional" | "release_ready";

export interface GenerateCommitMessageResponse {
  message: string;
  subject: string;
  body: string[];
  warning?: string | null;
  style: CommitMessageStyle;
  confidence: "low" | "medium" | "high";
  detectedScope: string[];
  alternatives: string[];
  source: "llm";
  contextSummary: string;
  privacyReceipt?: PrivacyReceipt | null;
}

export interface CommitSuggestion {
  message: string;
  files: string[];
  rationale: string;
}

export interface GenerateChangeSummaryResponse {
  branchSummary: string;
  fileSummaries: string[];
  prTitle: string;
  prBody: string;
  commitSuggestions: CommitSuggestion[];
  source: "llm";
  contextSummary: string;
  privacyReceipt?: PrivacyReceipt | null;
}

export interface DraftGitHubReleaseRequest {
  tagName: string;
  title: string;
  body: string;
  assetPath?: string | null;
  prerelease: boolean;
}

export interface DraftGitHubReleaseResponse {
  tagName: string;
  repository: string;
  releaseUrl: string;
  assetUrl?: string | null;
  assetName?: string | null;
  assetSha256?: string | null;
  title: string;
  summary: string;
  content: string;
  snapshot: RepositorySnapshot;
}

export interface CancelActionPlanResponse {
  cancelled: boolean;
}

export type ChatTranscriptEntry =
  | {
      id: string;
      kind: "user";
      message: string;
    }
  | {
      id: string;
      kind: "result";
      title: string;
      summary: string;
      content: string;
      contentKind?: "text" | "diff" | "graph";
    }
  | {
      id: string;
      kind: "error";
      message: string;
    }
  | {
      id: string;
      kind: "plan";
      plan: LocalActionPlan;
      status: "pending" | "executed" | "cancelled" | "failed";
    }
  | {
      id: string;
      kind: "wizard_menu";
      variant: "full" | "compact";
    }
  | {
      id: string;
      kind: "wizard_step";
      stepKind: "file_pick" | "text_input" | "asset_pick" | "option_select" | "confirm";
      prompt: string;
      status: "active" | "done";
      choices?: string[];
      confirmLines?: string[];
      chosenLabel?: string;
      danger?: boolean;
    };
