import { invoke } from "@tauri-apps/api/core";
import type {
  ActionExecutionResult,
  ActionPlanStep,
  BootstrapStatus,
  CancelActionPlanResponse,
  DiagnosticsStatus,
  FolderClassification,
  GitInstallationStatus,
  LLMSettings,
  LocalActionPlan,
  ReadActionRequest,
  ReadActionResult,
  Repository,
  RepositorySnapshot,
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

  runReadAction: (repositoryId: string, request: ReadActionRequest) =>
    invoke<ReadActionResult>("run_read_action", { repositoryId, request }),

  planLocalRequest: (repositoryId: string, message: string) =>
    invoke<LocalActionPlan>("resolve_local_request", { repositoryId, message }),

  executeActionPlan: (repositoryId: string, planId: string) =>
    invoke<ActionExecutionResult>("execute_action_plan", { repositoryId, planId }),

  cancelActionPlan: (repositoryId: string, planId: string) =>
    invoke<CancelActionPlanResponse>("cancel_action_plan", { repositoryId, planId }),

  submitActionPlan: (repositoryId: string, steps: ActionPlanStep[]) =>
    invoke<{ planId: string }>("submit_action_plan", { repositoryId, steps }),

  addToGitignore: (repositoryId: string, paths: string[]) =>
    invoke<{ ok: boolean }>("add_to_gitignore", { repositoryId, paths }),

  removeRepository: (repositoryId: string) =>
    invoke<void>("remove_repository", { repositoryId }),

  pickCloneTarget: () => invoke<string | null>("pick_clone_target"),

  cloneRepository: (url: string, parentPath: string, folderName?: string) =>
    invoke<Repository>("clone_repository", { url, parentPath, folderName }),

  getLlmSettings: () => invoke<LLMSettings>("get_llm_settings"),

  updateLlmSettings: (request: UpdateLLMSettingsRequest) =>
    invoke<LLMSettings>("update_llm_settings", { request }),

  testLlmConnection: () =>
    invoke<{ ok: boolean; message: string }>("test_llm_connection"),

  setRepositoryLlmAllowed: (repositoryId: string, allowed: boolean) =>
    invoke<Repository>("set_repository_llm_allowed", { repositoryId, allowed }),
};
