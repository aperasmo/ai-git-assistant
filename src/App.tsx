import { useCallback, useEffect, useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { CloneRepositoryModal } from "./components/CloneRepositoryModal";
import { DiagnosticsModal } from "./components/DiagnosticsModal";
import { HelpModal } from "./components/HelpModal";
import { Walkthrough } from "./components/Walkthrough";
import { RepositoryContextPanel } from "./components/RepositoryContextPanel";
import { RepositoryDecisionDialog } from "./components/RepositoryDecisionDialog";
import { RepositorySidebar } from "./components/RepositorySidebar";
import { SettingsModal } from "./components/SettingsModal";
import { StartupScreen } from "./components/StartupScreen";
import { TopBar } from "./components/TopBar";
import { desktopApi } from "./lib/api";
import {
  FLOW_LABELS,
  FLOW_READ_ACTIONS,
  type WizardData,
  type WizardFlowId,
  type WizardState,
} from "./lib/flows";
import type {
  ActionPlanStep,
  BootstrapStatus,
  ChatTranscriptEntry,
  FolderClassification,
  GitInstallationStatus,
  LocalActionPlan,
  ReadAction,
  Repository,
  RepositorySnapshot,
} from "./lib/types";

const QUICK_ACTION_MESSAGES: Record<ReadAction, string> = {
  status: "Git status",
  log: "Show recent commits",
  diff: "Show me the diff",
  branches: "Show branches",
  fetch: "Refresh remote status",
  graph: "Show commit graph",
  stashes: "Show stashes",
  stash_show: "Inspect stash",
  remotes: "Show remotes",
  file_history: "Show file history",
  blame: "Show file blame",
  conflicts: "Show conflicts",
};

// Windows reserved device names that git can report in status but cannot stage/read on Windows.
const WINDOWS_RESERVED = /^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])$/i;
function isWindowsReservedPath(filePath: string): boolean {
  const base = filePath.split(/[/\\]/).pop() ?? filePath;
  return WINDOWS_RESERVED.test(base);
}

function createTranscriptId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function findPendingPlan(entries: ChatTranscriptEntry[]): LocalActionPlan | null {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    if (entry.kind === "plan" && entry.status === "pending") {
      return entry.plan;
    }
  }
  return null;
}

function toErrorMessage(cause: unknown, fallback: string): string {
  if (cause instanceof Error) return cause.message;
  if (typeof cause === "string") return cause;
  return fallback;
}

export default function App() {
  const [bootstrap, setBootstrap] = useState<BootstrapStatus | null>(null);
  const [gitStatus, setGitStatus] = useState<GitInstallationStatus | null>(null);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [activeRepositoryId, setActiveRepositoryId] = useState<string | null>(null);
  const activeRepositoryIdRef = useRef<string | null>(null);
  const [snapshot, setSnapshot] = useState<RepositorySnapshot | null>(null);
  const [transcripts, setTranscripts] = useState<Record<string, ChatTranscriptEntry[]>>({});
  const [busy, setBusy] = useState(false);
  const [applicationError, setApplicationError] = useState<string | null>(null);
  const [pendingClassification, setPendingClassification] =
    useState<FolderClassification | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [cloneOpen, setCloneOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [activeLlm, setActiveLlm] = useState<{ provider: string; model: string } | null>(null);
  const [tourOpen, setTourOpen] = useState(false);
  const [tourStep, setTourStep] = useState(0);
  const activeWizardRef = useRef<WizardState | null>(null);
  // Paths the user has requested to gitignore this session, keyed by repositoryId.
  // These are filtered out of every wizard file-pick run so they don't reappear.
  const [sessionGitignored, setSessionGitignored] = useState<Record<string, string[]>>({});

  const activeRepository =
    repositories.find((repository) => repository.id === activeRepositoryId) ?? null;
  const activeTranscript = activeRepositoryId ? transcripts[activeRepositoryId] ?? [] : [];
  const activePendingPlan = findPendingPlan(activeTranscript);
  const interactionLocked = busy || Boolean(activePendingPlan);

  const appendTranscriptEntry = useCallback(
    (repositoryId: string, entry: ChatTranscriptEntry) => {
      setTranscripts((current) => ({
        ...current,
        [repositoryId]: [...(current[repositoryId] ?? []), entry],
      }));
    },
    [],
  );

  const markWizardStepDone = useCallback(
    (repositoryId: string, stepId: string, chosenLabel: string) => {
      setTranscripts((current) => ({
        ...current,
        [repositoryId]: (current[repositoryId] ?? []).map((entry) =>
          entry.id === stepId && entry.kind === "wizard_step"
            ? { ...entry, status: "done" as const, chosenLabel }
            : entry,
        ),
      }));
    },
    [],
  );

  const updatePlanStatus = useCallback(
    (
      repositoryId: string,
      planId: string,
      status: "executed" | "cancelled" | "failed",
    ) => {
      setTranscripts((current) => ({
        ...current,
        [repositoryId]: (current[repositoryId] ?? []).map((entry) => {
          if (entry.kind !== "plan" || entry.plan.planId !== planId) {
            return entry;
          }
          return { ...entry, status };
        }),
      }));
    },
    [],
  );

  const selectRepository = useCallback((repositoryId: string | null) => {
    activeRepositoryIdRef.current = repositoryId;
    setSnapshot(null);
    setApplicationError(null);
    setActiveRepositoryId(repositoryId);
    if (repositoryId) {
      setTranscripts((current) => {
        if ((current[repositoryId] ?? []).length > 0) return current;
        return {
          ...current,
          [repositoryId]: [{ id: createTranscriptId(), kind: "wizard_menu", variant: "full" }],
        };
      });
    }
  }, []);

  const loadRepositories = useCallback(async () => {
    const loaded = await desktopApi.listRepositories();
    setRepositories(loaded);
    return loaded;
  }, []);

  useEffect(() => {
    let cancelled = false;

    const interval = window.setInterval(async () => {
      try {
        const status = await desktopApi.getBootstrapStatus();
        if (cancelled) return;

        setBootstrap(status);

        if (status.sidecarStatus === "ready" || status.sidecarStatus === "failed") {
          window.clearInterval(interval);

          if (status.sidecarStatus === "ready") {
            const [git, loaded] = await Promise.all([
              desktopApi.getGitInstallationStatus(),
              loadRepositories(),
            ]);

            if (cancelled) return;

            setGitStatus(git);
            if (loaded.length > 0 && activeRepositoryIdRef.current === null) {
              selectRepository(loaded[0].id);
            }
            desktopApi.getLlmSettings().then((s) => {
              if (s.provider) setActiveLlm({ provider: s.provider, model: s.model ?? "" });
            }).catch(() => {});
          }
        }
      } catch (cause) {
        if (!cancelled) {
          setBootstrap({
            sidecarStatus: "failed",
            message: toErrorMessage(cause, "Unable to start local service."),
          });
          window.clearInterval(interval);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [loadRepositories, selectRepository]);

  useEffect(() => {
    if (!activeRepositoryId || bootstrap?.sidecarStatus !== "ready") {
      setSnapshot(null);
      return;
    }

    const repositoryId = activeRepositoryId;
    let cancelled = false;

    setSnapshot(null);

    void desktopApi
      .getRepositorySnapshot(repositoryId)
      .then((nextSnapshot) => {
        if (!cancelled && activeRepositoryIdRef.current === repositoryId) {
          setSnapshot(nextSnapshot);
        }
      })
      .catch((cause) => {
        if (!cancelled && activeRepositoryIdRef.current === repositoryId) {
          setApplicationError(toErrorMessage(cause, "Unable to inspect repository."));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeRepositoryId, bootstrap?.sidecarStatus]);

  async function finishRepositoryRegistration(repository: Repository) {
    await loadRepositories();
    selectRepository(repository.id);
  }

  async function addRepository() {
    try {
      setBusy(true);
      setApplicationError(null);

      const classification = await desktopApi.pickAndClassifyRepository();
      if (!classification) return;

      switch (classification.kind) {
        case "existing_repository": {
          const repository = await desktopApi.registerRepository(
            classification.repositoryRoot ?? classification.selectedPath,
          );
          await finishRepositoryRegistration(repository);
          return;
        }

        case "nested_repository":
        case "initialisation_required":
          setPendingClassification(classification);
          return;

        case "unsupported_repository":
          setApplicationError(
            classification.message ??
              "This folder cannot be added because its Git state is unsupported.",
          );
          return;
      }
    } catch (cause) {
      setApplicationError(toErrorMessage(cause, "Repository could not be added."));
    } finally {
      setBusy(false);
    }
  }

  async function removeRepository(repositoryId: string) {
    try {
      await desktopApi.removeRepository(repositoryId);
      const remaining = await loadRepositories();
      if (activeRepositoryId === repositoryId) {
        selectRepository(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (cause) {
      setApplicationError(toErrorMessage(cause, "Repository could not be removed."));
    }
  }

  async function confirmRepositoryDecision() {
    const classification = pendingClassification;
    if (!classification) return;

    try {
      setBusy(true);
      setApplicationError(null);

      let repository: Repository;

      if (classification.kind === "nested_repository") {
        if (!classification.repositoryRoot) {
          throw new Error("The parent repository root is unavailable.");
        }
        repository = await desktopApi.registerRepository(classification.repositoryRoot);
      } else if (classification.kind === "initialisation_required") {
        repository = await desktopApi.initialiseAndRegisterRepository(
          classification.selectedPath,
        );
      } else {
        return;
      }

      setPendingClassification(null);
      await finishRepositoryRegistration(repository);
    } catch (cause) {
      setPendingClassification(null);
      setApplicationError(toErrorMessage(cause, "Repository setup could not be completed."));
    } finally {
      setBusy(false);
    }
  }

  function cancelRepositoryDecision() {
    if (!busy) {
      setPendingClassification(null);
    }
  }

  async function runAction(action: ReadAction) {
    const repositoryId = activeRepositoryId;
    if (!repositoryId || findPendingPlan(transcripts[repositoryId] ?? [])) return;

    const message = QUICK_ACTION_MESSAGES[action];
    appendTranscriptEntry(repositoryId, {
      id: createTranscriptId(),
      kind: "user",
      message,
    });

    try {
      setBusy(true);
      setApplicationError(null);

      const nextResult = await desktopApi.runReadAction(repositoryId, { action });
      if (activeRepositoryIdRef.current !== repositoryId) return;

      setSnapshot(nextResult.snapshot);
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "result",
        title: nextResult.title,
        summary: nextResult.summary,
        content: nextResult.content,
        contentKind: nextResult.contentKind,
      });

      await loadRepositories();
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(cause, "Git request could not be completed."),
        });
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitMessage(message: string) {
    const repositoryId = activeRepositoryId;
    if (!repositoryId || findPendingPlan(transcripts[repositoryId] ?? [])) return;

    appendTranscriptEntry(repositoryId, {
      id: createTranscriptId(),
      kind: "user",
      message,
    });

    try {
      setBusy(true);
      setApplicationError(null);

      const plan = await desktopApi.planLocalRequest(repositoryId, message);
      if (activeRepositoryIdRef.current !== repositoryId) return;

      if (!plan.matched) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: plan.explanation,
        });
        return;
      }

      if (plan.requiresConfirmation) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "plan",
          plan,
          status: "pending",
        });
        return;
      }
      if (plan.planKind === "info") {
        const infoStep = plan.steps[0];

        const content = [
          infoStep?.branch ? `Branch: ${infoStep.branch}` : null,
          infoStep?.remote && infoStep?.branch
            ? `Upstream: ${infoStep.remote}/${infoStep.branch}`
            : null,
          infoStep?.ahead !== null && infoStep?.ahead !== undefined
            ? `Ahead: ${infoStep.ahead}`
            : null,
          infoStep?.behind !== null && infoStep?.behind !== undefined
            ? `Behind: ${infoStep.behind}`
            : null,
          infoStep?.force !== null && infoStep?.force !== undefined
            ? `Force: ${infoStep.force ? "true" : "false"}`
            : null,
          infoStep?.commandPreview
            ? `\nEquivalent Git command:\n${infoStep.commandPreview}`
            : null,
        ]
          .filter(Boolean)
          .join("\n");

        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "result",
          title: infoStep?.title ?? "Information",
          summary: plan.explanation,
          content,
        });

        return;
      }
      if (!plan.readAction) {
        throw new Error("The local planner returned no executable read action.");
      }

      const nextResult = await desktopApi.runReadAction(repositoryId, {
        action: plan.readAction,
        params: plan.readParams,
      });
      if (activeRepositoryIdRef.current !== repositoryId) return;

      setSnapshot(nextResult.snapshot);
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "result",
        title: nextResult.title,
        summary: nextResult.summary,
        content: nextResult.content,
        contentKind: nextResult.contentKind,
      });

      await loadRepositories();
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(cause, "Git request could not be completed."),
        });
      }
    } finally {
      setBusy(false);
    }
  }

  async function approvePlan(planId: string) {
    const repositoryId = activeRepositoryId;
    if (!repositoryId) return;

    try {
      setBusy(true);
      setApplicationError(null);

      const execution = await desktopApi.executeActionPlan(repositoryId, planId);
      if (activeRepositoryIdRef.current !== repositoryId) return;

      updatePlanStatus(repositoryId, planId, "executed");
      setSnapshot(execution.snapshot);
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "result",
        title: execution.title,
        summary: execution.summary,
        content: execution.content,
      });

      await loadRepositories();
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        updatePlanStatus(repositoryId, planId, "failed");
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(
            cause,
            "The approved Git plan could not be completed. Review the repository status before trying again.",
          ),
        });
      }
    } finally {
      setBusy(false);
    }
  }

  async function cancelPlan(planId: string) {
    const repositoryId = activeRepositoryId;
    if (!repositoryId) return;

    try {
      setBusy(true);
      const response = await desktopApi.cancelActionPlan(repositoryId, planId);
      if (activeRepositoryIdRef.current !== repositoryId) return;

      if (!response.cancelled) {
        throw new Error("The action plan was no longer available to cancel.");
      }

      updatePlanStatus(repositoryId, planId, "cancelled");
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(cause, "The action plan could not be cancelled."),
        });
      }
    } finally {
      setBusy(false);
    }
  }

  async function runWizardFlow(flowId: WizardFlowId) {
    const repositoryId = activeRepositoryId;
    if (!repositoryId || busy || activePendingPlan) return;

    // Remove any existing menu entries so menu 1 disappears before menu 2 appears
    setTranscripts((current) => ({
      ...current,
      [repositoryId]: (current[repositoryId] ?? []).filter((e) => e.kind !== "wizard_menu"),
    }));

    appendTranscriptEntry(repositoryId, {
      id: createTranscriptId(),
      kind: "user",
      message: FLOW_LABELS[flowId],
    });

    const readAction = FLOW_READ_ACTIONS[flowId] as ReadAction | undefined;

    if (readAction) {
      try {
        setBusy(true);
        setApplicationError(null);
        const result = await desktopApi.runReadAction(repositoryId, { action: readAction });
        if (activeRepositoryIdRef.current !== repositoryId) return;
        setSnapshot(result.snapshot);
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "result",
          title: result.title,
          summary: result.summary,
          content: result.content,
          contentKind: result.contentKind,
        });
        await loadRepositories();
      } catch (cause) {
        if (activeRepositoryIdRef.current === repositoryId) {
          appendTranscriptEntry(repositoryId, {
            id: createTranscriptId(),
            kind: "error",
            message: toErrorMessage(cause, "Git request could not be completed."),
          });
        }
      } finally {
        setBusy(false);
        if (activeRepositoryIdRef.current === repositoryId) {
          appendTranscriptEntry(repositoryId, {
            id: createTranscriptId(),
            kind: "wizard_menu",
            variant: "compact",
          });
        }
      }
    } else if (flowId === "commit_push" || flowId === "stage_only") {
      startWriteWizard(repositoryId, flowId);
    } else if (flowId === "discard") {
      startDiscardWizard(repositoryId);
    } else if (flowId === "switch_branch") {
      startSwitchBranchWizard(repositoryId);
    } else if (flowId === "pull") {
      startPullWizard(repositoryId);
    } else if (flowId === "stash") {
      startStashWizard(repositoryId);
    } else if (flowId === "connect_remote") {
      startConnectRemoteWizard();
    }
  }

  function startWriteWizard(repositoryId: string, flowId: "commit_push" | "stage_only") {
    const ignored = new Set(sessionGitignored[repositoryId] ?? []);
    const allFiles = [
      ...(snapshot?.stagedChanges ?? []).map((c) => c.path),
      ...(snapshot?.modifiedChanges ?? []).map((c) => c.path),
      ...(snapshot?.untrackedPaths ?? []).map((c) => c.path),
    ]
      .filter((f, i, arr) => arr.indexOf(f) === i)
      .filter((f) => !ignored.has(f))
      .filter((f) => !isWindowsReservedPath(f));

    if (allFiles.length === 0) {
      // Clean tree + commit_push + remote configured → offer push-only (no stage/commit needed).
      if (flowId === "commit_push" && (snapshot?.remoteNames ?? []).length > 0) {
        const remote = snapshot?.remoteNames?.[0] ?? "origin";
        const branch = snapshot?.branch ?? "main";
        const stepId = createTranscriptId();
        activeWizardRef.current = {
          flowId: "commit_push",
          currentStepId: stepId,
          currentStepKind: "confirm",
          data: { remote, branch },
        };
        appendTranscriptEntry(repositoryId, {
          id: stepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Push commits to remote",
          status: "active",
          confirmLines: [
            `Remote: ${remote} (${snapshot?.remoteUrls?.[remote] ?? "—"}) / ${branch}`,
            ...gitCmds(`git push ${remote} ${branch}`),
          ],
        });
        return;
      }
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "error",
        message: "No files to commit. The working tree is clean.",
      });
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "wizard_menu",
        variant: "compact",
      });
      return;
    }

    const stepId = createTranscriptId();
    const wizardState: WizardState = {
      flowId,
      currentStepId: stepId,
      currentStepKind: "file_pick",
      data: {},
    };
    activeWizardRef.current = wizardState;

    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "file_pick",
      prompt: "Which files do you want to include?",
      status: "active",
      choices: allFiles,
    });
  }

  function startDiscardWizard(repositoryId: string) {
    const allFiles = [
      ...(snapshot?.modifiedChanges ?? []).map((c) => c.path),
      ...(snapshot?.untrackedPaths ?? []).map((c) => c.path),
    ].filter((f, i, arr) => arr.indexOf(f) === i).filter((f) => !isWindowsReservedPath(f));

    if (allFiles.length === 0) {
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "error",
        message: "No changed files to discard. The working tree is clean.",
      });
      appendTranscriptEntry(repositoryId, { id: createTranscriptId(), kind: "wizard_menu", variant: "compact" });
      return;
    }

    const stepId = createTranscriptId();
    activeWizardRef.current = { flowId: "discard", currentStepId: stepId, currentStepKind: "file_pick", data: {} };
    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "file_pick",
      prompt: "Which files do you want to discard changes in?",
      status: "active",
      choices: allFiles,
    });
  }

  function startSwitchBranchWizard(repositoryId: string) {
    const otherBranches = (snapshot?.localBranches ?? [])
      .filter((b) => !b.isCurrent)
      .map((b) => b.name);

    if (otherBranches.length === 0) {
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "error",
        message: "No other branches found. Create a branch first.",
      });
      appendTranscriptEntry(repositoryId, { id: createTranscriptId(), kind: "wizard_menu", variant: "compact" });
      return;
    }

    const stepId = createTranscriptId();
    activeWizardRef.current = { flowId: "switch_branch", currentStepId: stepId, currentStepKind: "option_select", data: {} };
    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "option_select",
      prompt: "Switch to which branch?",
      status: "active",
      choices: otherBranches,
    });
  }

  function startPullWizard(repositoryId: string) {
    const remote = snapshot?.upstreamRemote ?? snapshot?.remoteNames?.[0] ?? "origin";
    const branch = snapshot?.branch ?? "main";
    const stepId = createTranscriptId();
    activeWizardRef.current = { flowId: "pull", currentStepId: stepId, currentStepKind: "confirm", data: { remote, branch } };
    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "confirm",
      prompt: "Pull latest",
      status: "active",
      confirmLines: [
        `From: ${remote}/${branch}`,
        `Current branch: ${branch}`,
        ...gitCmds("git pull --ff-only"),
      ],
    });
  }

  function startStashWizard(repositoryId: string) {
    const hasChanges =
      (snapshot?.modifiedChanges ?? []).length > 0 ||
      (snapshot?.stagedChanges ?? []).length > 0 ||
      (snapshot?.untrackedPaths ?? []).length > 0;

    if (!hasChanges) {
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "error",
        message: "Nothing to stash. The working tree is clean.",
      });
      appendTranscriptEntry(repositoryId, { id: createTranscriptId(), kind: "wizard_menu", variant: "compact" });
      return;
    }

    const stepId = createTranscriptId();
    activeWizardRef.current = { flowId: "stash", currentStepId: stepId, currentStepKind: "confirm", data: {} };
    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "confirm",
      prompt: "Stash changes",
      status: "active",
      confirmLines: [
        `Staged: ${(snapshot?.stagedChanges ?? []).length} file(s)`,
        `Modified: ${(snapshot?.modifiedChanges ?? []).length} file(s)`,
        `Untracked: ${(snapshot?.untrackedPaths ?? []).length} file(s)`,
        ...gitCmds("git stash push --include-untracked"),
      ],
    });
  }

  function gitCmds(...cmds: string[]): string[] {
    return ["", ...cmds.map((c) => `$ ${c}`)];
  }

  function startConnectRemoteWizard() {
    const repositoryId = activeRepositoryId;
    if (!repositoryId) return;
    const stepId = createTranscriptId();
    activeWizardRef.current = { flowId: "connect_remote", currentStepId: stepId, currentStepKind: "text_input", data: {} };
    appendTranscriptEntry(repositoryId, {
      id: stepId,
      kind: "wizard_step",
      stepKind: "text_input",
      prompt: "Paste the GitHub / GitLab remote URL",
      status: "active",
    });
  }

  function onWizardNext(choiceLabel: string, choiceData: Partial<WizardData>) {
    const repositoryId = activeRepositoryId;
    const wizard = activeWizardRef.current;
    if (!repositoryId || !wizard) return;

    markWizardStepDone(repositoryId, wizard.currentStepId, choiceLabel);
    const updatedData: WizardData = { ...wizard.data, ...choiceData };
    const nextStepId = createTranscriptId();

    if (wizard.currentStepKind === "file_pick") {
      if (wizard.flowId === "discard") {
        const next: WizardState = { ...wizard, currentStepId: nextStepId, currentStepKind: "confirm", data: updatedData };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Discard changes — this cannot be undone",
          status: "active",
          confirmLines: [
            `Files (${(updatedData.files ?? []).length}): ${(updatedData.files ?? []).join(", ")}`,
            ...gitCmds(`git restore -- (${(updatedData.files ?? []).length} files)`),
          ],
          danger: true,
        });
      } else {
        const next: WizardState = { ...wizard, currentStepId: nextStepId, currentStepKind: "text_input", data: updatedData };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "text_input",
          prompt: "Commit message",
          status: "active",
        });
      }
    } else if (wizard.currentStepKind === "text_input") {
      if (wizard.flowId === "connect_remote") {
        const url = updatedData.message ?? "";
        const remoteName = "origin";
        const currentBranch = snapshot?.branch ?? "main";
        const needsRename = currentBranch !== "main";
        const hasCommits = (snapshot?.recentCommits?.length ?? 0) > 0;
        const next: WizardState = { ...wizard, currentStepId: nextStepId, currentStepKind: "confirm", data: { ...updatedData, remote: remoteName } };
        activeWizardRef.current = next;
        const confirmLines: string[] = [`1. Add remote: ${remoteName} (${url})`];
        let step = 2;
        if (needsRename) confirmLines.push(`${step++}. Rename branch: ${currentBranch} → main`);
        if (hasCommits) {
          confirmLines.push(`${step}. Push: origin/main (first push)`);
        } else {
          confirmLines.push(
            "",
            "No commits yet — push will be skipped.",
            "After this, follow these steps:",
            `${step}. Choose 'Stage & commit' → select files → write message`,
            `${step + 1}. Choose 'Commit & push' for any future changes`,
          );
        }
        const cmds: string[] = [`git remote add ${remoteName} ${url}`];
        if (needsRename) cmds.push("git branch -M main");
        if (hasCommits) cmds.push(`git push -u ${remoteName} main`);
        confirmLines.push(...gitCmds(...cmds));
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Connect & push to GitHub",
          status: "active",
          confirmLines,
        });
      } else if (wizard.flowId === "stage_only") {
        const next: WizardState = {
          ...wizard,
          currentStepId: nextStepId,
          currentStepKind: "confirm",
          data: updatedData,
        };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Ready to commit",
          status: "active",
          confirmLines: [
            `Files (${(updatedData.files ?? []).length}): ${(updatedData.files ?? []).join(", ")}`,
            `Message: "${updatedData.message}"`,
            ...gitCmds(
              `git add -- (${(updatedData.files ?? []).length} files)`,
              `git commit -m "${updatedData.message}"`,
            ),
          ],
        });
      } else {
        const remotes = (snapshot?.remoteNames ?? []).length > 0
          ? (snapshot?.remoteNames ?? [])
          : ["origin"];
        const next: WizardState = {
          ...wizard,
          currentStepId: nextStepId,
          currentStepKind: "option_select",
          data: updatedData,
        };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "option_select",
          prompt: "Push to which remote?",
          status: "active",
          choices: remotes,
        });
      }
    } else if (wizard.currentStepKind === "option_select") {
      if (wizard.flowId === "switch_branch") {
        // OptionSelectStep sends { remote: choice } — move it to branch
        const targetBranch = updatedData.remote ?? choiceLabel;
        const branchData: WizardData = { ...updatedData, branch: targetBranch };
        const next: WizardState = { ...wizard, currentStepId: nextStepId, currentStepKind: "confirm", data: branchData };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Switch branch",
          status: "active",
          confirmLines: [
            `Target: ${targetBranch}`,
            `Current: ${snapshot?.branch ?? "unknown"}`,
            ...gitCmds(`git switch ${targetBranch}`),
          ],
        });
      } else {
        const currentBranch = snapshot?.branch ?? "main";
        const next: WizardState = { ...wizard, currentStepId: nextStepId, currentStepKind: "confirm", data: updatedData };
        activeWizardRef.current = next;
        appendTranscriptEntry(repositoryId, {
          id: nextStepId,
          kind: "wizard_step",
          stepKind: "confirm",
          prompt: "Ready to commit & push",
          status: "active",
          confirmLines: [
            `Files (${(updatedData.files ?? []).length}): ${(updatedData.files ?? []).join(", ")}`,
            `Message: "${updatedData.message}"`,
            `Remote: ${updatedData.remote} (${snapshot?.remoteUrls?.[updatedData.remote ?? ""] ?? "—"}) / ${currentBranch}`,
            ...gitCmds(
              `git add -- (${(updatedData.files ?? []).length} files)`,
              `git commit -m "${updatedData.message}"`,
              `git push ${updatedData.remote} ${currentBranch}`,
            ),
          ],
        });
      }
    }
  }

  async function onWizardConfirm() {
    const repositoryId = activeRepositoryId;
    const wizard = activeWizardRef.current;
    if (!repositoryId || !wizard) return;

    markWizardStepDone(repositoryId, wizard.currentStepId, "Executing...");

    try {
      setBusy(true);
      setApplicationError(null);

      const { files = [], message = "", remote = "origin" } = wizard.data;
      const currentBranch = snapshot?.branch ?? "main";
      const targetBranch = wizard.data.branch ?? message;

      const steps: ActionPlanStep[] = [];

      if (wizard.flowId === "pull") {
        steps.push({ kind: "pull", title: "Pull latest", detail: `${remote}/${currentBranch}`, paths: [], remote, branch: currentBranch });
      } else if (wizard.flowId === "stash") {
        steps.push({ kind: "stash", title: "Stash changes", detail: "Save work in progress", paths: [] });
      } else if (wizard.flowId === "switch_branch") {
        steps.push({ kind: "switch", title: `Switch to ${targetBranch}`, detail: `git switch ${targetBranch}`, paths: [], branch: targetBranch });
      } else if (wizard.flowId === "discard") {
        steps.push({ kind: "discard", title: "Discard changes", detail: `${files.length} file(s)`, paths: files });
      } else if (wizard.flowId === "connect_remote") {
        const remoteUrl = wizard.data.message ?? "";
        const remoteName = wizard.data.remote ?? "origin";
        const currentBranch = snapshot?.branch ?? "main";
        const targetBranch = "main";
        const hasCommits = (snapshot?.recentCommits?.length ?? 0) > 0;
        steps.push({ kind: "add_remote", title: `Add remote "${remoteName}"`, detail: `${remoteName} → ${remoteUrl}`, paths: [], remote: remoteName, remoteUrl });
        if (currentBranch !== targetBranch) {
          steps.push({ kind: "rename_branch", title: `Rename branch to ${targetBranch}`, detail: `git branch -M ${targetBranch}`, paths: [], branch: targetBranch });
        }
        if (hasCommits) {
          steps.push({ kind: "push", title: `Push to ${remoteName}/${targetBranch}`, detail: "First push with upstream tracking", paths: [], remote: remoteName, branch: targetBranch, setUpstream: true });
        }
      } else {
        if (files.length > 0) {
          steps.push({ kind: "stage", title: "Stage files", detail: `${files.length} file(s)`, paths: files });
        }
        if (message) {
          steps.push({ kind: "commit", title: "Commit", detail: `"${message}"`, paths: [], commitMessage: message });
        }
        if (wizard.flowId === "commit_push") {
          const setUpstream = !snapshot?.upstreamRemote;
          steps.push({ kind: "push", title: "Push", detail: `${remote}/${currentBranch}`, paths: [], remote, branch: currentBranch, setUpstream });
        }
      }

      const { planId } = await desktopApi.submitActionPlan(repositoryId, steps);
      const execution = await desktopApi.executeActionPlan(repositoryId, planId);
      if (activeRepositoryIdRef.current !== repositoryId) return;

      setSnapshot(execution.snapshot);
      appendTranscriptEntry(repositoryId, {
        id: createTranscriptId(),
        kind: "result",
        title: execution.title,
        summary: execution.summary,
        content: execution.content,
      });
      await loadRepositories();
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(cause, "Wizard execution failed."),
        });
      }
    } finally {
      setBusy(false);
      activeWizardRef.current = null;
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "wizard_menu",
          variant: "compact",
        });
      }
    }
  }

  async function onAddToGitignore(paths: string[]) {
    const repositoryId = activeRepositoryId;
    const stepId = activeWizardRef.current?.currentStepId;
    if (!repositoryId) return;

    // Persist in session set so future wizard runs filter these files out.
    setSessionGitignored((current) => {
      const next = new Set(current[repositoryId] ?? []);
      paths.forEach((p) => next.add(p));
      return { ...current, [repositoryId]: Array.from(next) };
    });

    // Also remove from the live transcript entry so a remounted FilePickStep
    // re-initialises without them.
    if (stepId) {
      setTranscripts((current) => ({
        ...current,
        [repositoryId]: (current[repositoryId] ?? []).map((e) =>
          e.id === stepId && e.kind === "wizard_step"
            ? { ...e, choices: (e.choices ?? []).filter((c) => !paths.includes(c)) }
            : e,
        ),
      }));
    }

    try {
      await desktopApi.addToGitignore(repositoryId, paths);
      const fresh = await desktopApi.getRepositorySnapshot(repositoryId);
      if (activeRepositoryIdRef.current === repositoryId) setSnapshot(fresh);
    } catch (cause) {
      if (activeRepositoryIdRef.current === repositoryId) {
        appendTranscriptEntry(repositoryId, {
          id: createTranscriptId(),
          kind: "error",
          message: toErrorMessage(cause, "Could not write to .gitignore. The file list was updated locally only."),
        });
      }
    }
  }

  function onWizardCancel() {
    const repositoryId = activeRepositoryId;
    if (!repositoryId) return;
    activeWizardRef.current = null;
    // Remove all active wizard steps so the command bar re-enables immediately.
    setTranscripts((current) => ({
      ...current,
      [repositoryId]: (current[repositoryId] ?? []).filter(
        (e) => !(e.kind === "wizard_step" && e.status === "active"),
      ),
    }));
  }

  // Auto-launch tour on first visit; skip during startup.
  useEffect(() => {
    if (bootstrap?.sidecarStatus === "ready" && !localStorage.getItem("aga-tour-v1")) {
      setTourOpen(true);
    }
  }, [bootstrap?.sidecarStatus]);

  function openTour() {
    setTourStep(0);
    setTourOpen(true);
  }

  function closeTour() {
    setTourOpen(false);
    localStorage.setItem("aga-tour-v1", "done");
  }

  function nextTourStep() {
    setTourStep((s) => s + 1);
  }

  function prevTourStep() {
    setTourStep((s) => Math.max(0, s - 1));
  }


  if (!bootstrap || bootstrap.sidecarStatus === "starting") {
    return (
      <StartupScreen message={bootstrap?.message ?? "Starting secure local service..."} />
    );
  }

  if (bootstrap.sidecarStatus === "failed") {
    return <StartupScreen message={bootstrap.message} failure />;
  }

  if (!gitStatus || gitStatus.status !== "available") {
    return (
      <StartupScreen
        message={gitStatus?.message ?? "Checking Git installationâ€¦"}
        gitStatus={gitStatus}
        failure={Boolean(gitStatus && gitStatus.status !== "checking")}
      />
    );
  }

  return (
    <div className="app-shell">
      <TopBar
        repository={activeRepository}
        gitStatus={gitStatus}
        activeLlm={activeLlm}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenDiagnostics={() => setDiagnosticsOpen(true)}
        onOpenTour={openTour}
        onOpenHelp={() => setHelpOpen(true)}
      />

      <div className="app-body">
        <RepositorySidebar
          repositories={repositories}
          activeRepositoryId={activeRepositoryId}
          onSelect={selectRepository}
          onAdd={() => void addRepository()}
          onClone={() => setCloneOpen(true)}
          onRemove={(id) => void removeRepository(id)}
          isBusy={interactionLocked}
        />

        <ChatPanel
          repositorySelected={Boolean(activeRepository)}
          busy={busy}
          transcript={activeTranscript}
          pendingPlanId={activePendingPlan?.planId}
          applicationError={applicationError}
          onSubmit={submitMessage}
          onApprovePlan={approvePlan}
          onCancelPlan={cancelPlan}
          onWizardSelect={(flowId) => void runWizardFlow(flowId)}
          onWizardNext={onWizardNext}
          onWizardConfirm={() => void onWizardConfirm()}
          onWizardCancel={onWizardCancel}
          onAddToGitignore={onAddToGitignore}
        />

        <RepositoryContextPanel
          repository={activeRepository}
          snapshot={snapshot}
          busy={interactionLocked}
          onAction={(action) => void runAction(action)}
          activeLlm={activeLlm}
          onTestLlm={() => desktopApi.testLlmConnection()}
        />
      </div>

      {pendingClassification && (
        <RepositoryDecisionDialog
          classification={pendingClassification}
          busy={busy}
          onCancel={cancelRepositoryDecision}
          onConfirm={() => void confirmRepositoryDecision()}
        />
      )}

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={(provider, model) => setActiveLlm({ provider, model })}
      />
      <DiagnosticsModal open={diagnosticsOpen} onClose={() => setDiagnosticsOpen(false)} />
      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />

      <Walkthrough
        open={tourOpen}
        step={tourStep}
        onNext={nextTourStep}
        onBack={prevTourStep}
        onClose={closeTour}
      />

      {cloneOpen && (
        <CloneRepositoryModal
          onCloned={async (repo) => {
            setCloneOpen(false);
            await loadRepositories();
            selectRepository(repo.id);
          }}
          onCancel={() => setCloneOpen(false)}
        />
      )}
    </div>
  );
}
