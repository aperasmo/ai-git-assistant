import { invoke } from "@tauri-apps/api/core";
import type {
  ActionExecutionResult,
  ApplyConflictResolutionRequest,
  ApplyConflictResolutionResponse,
  ActionPlanStep,
  AgentSession,
  AgentSessionActionResponse,
  AgentSessionComparisonResponse,
  BootstrapStatus,
  CancelActionPlanResponse,
  ConflictResolutionPreviewRequest,
  ConflictResolutionPreviewResponse,
  DiagnosticsStatus,
  DraftGitLabMergeRequestRequest,
  DraftGitLabMergeRequestResponse,
  DraftGitHubPullRequestRequest,
  DraftGitHubPullRequestResponse,
  DraftGitHubReleaseRequest,
  DraftGitHubReleaseResponse,
  FolderClassification,
  GenerateChangeSummaryResponse,
  GenerateCommitMessageResponse,
  GeneratePullRequestDraftResponse,
  GitInstallationStatus,
  GitHubSettings,
  GitHubDraftReleaseDetailsRequest,
  GitHubDraftReleaseDetailsResponse,
  GitIdentitySettings,
  GitLabSettings,
  LLMSettings,
  LocalActionPlan,
  PublishGitHubRepositoryRequest,
  PublishGitHubRepositoryResponse,
  ReadActionRequest,
  ReadActionResult,
  Repository,
  RepositorySnapshot,
  UpdateGitHubSettingsRequest,
  UpdateGitIdentityRequest,
  UpdateGitLabSettingsRequest,
  UpdateLLMSettingsRequest,
} from "./types";

export const desktopApi = {
  getBootstrapStatus: () => invoke<BootstrapStatus>("get_bootstrap_status"),

  getGitInstallationStatus: () =>
    invoke<GitInstallationStatus>("get_git_installation_status"),

  getDiagnosticsStatus: () =>
    invoke<DiagnosticsStatus>("get_diagnostics_status"),

  listRepositories: () => invoke<Repository[]>("list_repositories"),

  pickAndClassifyRepository: () =>
    invoke<FolderClassification | null>("pick_and_classify_repository"),

  registerRepository: (path: string) =>
    invoke<Repository>("register_repository", { path }),

  initialiseAndRegisterRepository: (path: string) =>
    invoke<Repository>("initialise_and_register_repository", { path }),

  getRepositorySnapshot: (repositoryId: string) =>
    invoke<RepositorySnapshot>("get_repository_snapshot", { repositoryId }),

  listAgentSessions: (repositoryId: string) =>
    invoke<AgentSession[]>("list_agent_sessions", { repositoryId }),

  createAgentSession: (
    repositoryId: string,
    task: string,
    branchName?: string | null,
    baseBranch?: string | null,
  ) =>
    invoke<AgentSession>("create_agent_session", {
      repositoryId,
      task,
      branchName,
      baseBranch,
    }),

  compareAgentSession: (repositoryId: string, sessionId: string) =>
    invoke<AgentSessionComparisonResponse>("compare_agent_session", { repositoryId, sessionId }),

  mergeAgentSession: (repositoryId: string, sessionId: string) =>
    invoke<AgentSessionActionResponse>("merge_agent_session", { repositoryId, sessionId }),

  abandonAgentSession: (repositoryId: string, sessionId: string) =>
    invoke<AgentSessionActionResponse>("abandon_agent_session", { repositoryId, sessionId }),

  cleanupAgentSession: (repositoryId: string, sessionId: string) =>
    invoke<AgentSessionActionResponse>("cleanup_agent_session", { repositoryId, sessionId }),

  runReadAction: (repositoryId: string, request: ReadActionRequest) =>
    invoke<ReadActionResult>("run_read_action", { repositoryId, request }),

  previewConflictResolution: (repositoryId: string, request: ConflictResolutionPreviewRequest) =>
    invoke<ConflictResolutionPreviewResponse>("preview_conflict_resolution", { repositoryId, request }),

  applyConflictResolution: (repositoryId: string, request: ApplyConflictResolutionRequest) =>
    invoke<ApplyConflictResolutionResponse>("apply_conflict_resolution", { repositoryId, request }),

  planLocalRequest: (repositoryId: string, message: string) =>
    invoke<LocalActionPlan>("resolve_local_request", { repositoryId, message }),

  executeActionPlan: (repositoryId: string, planId: string) =>
    invoke<ActionExecutionResult>("execute_action_plan", { repositoryId, planId }),

  cancelActionPlan: (repositoryId: string, planId: string) =>
    invoke<CancelActionPlanResponse>("cancel_action_plan", { repositoryId, planId }),

  submitActionPlan: (repositoryId: string, steps: ActionPlanStep[]) =>
    invoke<{ planId: string }>("submit_action_plan", { repositoryId, steps }),

  generateCommitMessage: (repositoryId: string, paths: string[], style = "detailed") =>
    invoke<GenerateCommitMessageResponse>("generate_commit_message", { repositoryId, paths, style }),

  generateChangeSummary: (repositoryId: string, paths: string[]) =>
    invoke<GenerateChangeSummaryResponse>("generate_change_summary", { repositoryId, paths }),

  generatePullRequestDraft: (repositoryId: string, baseBranch: string) =>
    invoke<GeneratePullRequestDraftResponse>("generate_pull_request_draft", { repositoryId, baseBranch }),

  draftGithubRelease: (repositoryId: string, request: DraftGitHubReleaseRequest) =>
    invoke<DraftGitHubReleaseResponse>("draft_github_release", { repositoryId, request }),

  getGithubDraftRelease: (repositoryId: string, request: GitHubDraftReleaseDetailsRequest) =>
    invoke<GitHubDraftReleaseDetailsResponse>("get_github_draft_release", { repositoryId, request }),

  publishGithubRepository: (repositoryId: string, request: PublishGitHubRepositoryRequest) =>
    invoke<PublishGitHubRepositoryResponse>("publish_github_repository", { repositoryId, request }),

  draftGithubPullRequest: (repositoryId: string, request: DraftGitHubPullRequestRequest) =>
    invoke<DraftGitHubPullRequestResponse>("draft_github_pull_request", { repositoryId, request }),

  draftGitlabMergeRequest: (repositoryId: string, request: DraftGitLabMergeRequestRequest) =>
    invoke<DraftGitLabMergeRequestResponse>("draft_gitlab_merge_request", { repositoryId, request }),

  addToGitignore: (repositoryId: string, paths: string[]) =>
    invoke<{ ok: boolean }>("add_to_gitignore", { repositoryId, paths }),

  removeRepository: (repositoryId: string) =>
    invoke<void>("remove_repository", { repositoryId }),

  pickCloneTarget: () => invoke<string | null>("pick_clone_target"),

  pickReleaseAsset: () => invoke<string[]>("pick_release_asset"),

  cloneRepository: (url: string, parentPath: string, folderName?: string) =>
    invoke<Repository>("clone_repository", { url, parentPath, folderName }),

  getLlmSettings: () => invoke<LLMSettings>("get_llm_settings"),

  updateLlmSettings: (request: UpdateLLMSettingsRequest) =>
    invoke<LLMSettings>("update_llm_settings", { request }),

  getGithubSettings: () => invoke<GitHubSettings>("get_github_settings"),

  updateGithubSettings: (request: UpdateGitHubSettingsRequest) =>
    invoke<GitHubSettings>("update_github_settings", { request }),

  getGitIdentitySettings: () => invoke<GitIdentitySettings>("get_git_identity_settings"),

  updateGitIdentitySettings: (request: UpdateGitIdentityRequest) =>
    invoke<GitIdentitySettings>("update_git_identity_settings", { request }),

  getGitlabSettings: () => invoke<GitLabSettings>("get_gitlab_settings"),

  updateGitlabSettings: (request: UpdateGitLabSettingsRequest) =>
    invoke<GitLabSettings>("update_gitlab_settings", { request }),

  testLlmConnection: () =>
    invoke<{ ok: boolean; message: string }>("test_llm_connection"),

  setRepositoryLlmAllowed: (repositoryId: string, allowed: boolean) =>
    invoke<Repository>("set_repository_llm_allowed", { repositoryId, allowed }),
};
