import { useState } from "react";
import { FLOWS, type FlowDef, type WizardFlowId } from "../lib/flows";
import type { RepositorySnapshot } from "../lib/types";

interface CommandBarProps {
  onSelect: (flowId: WizardFlowId) => void;
  disabled: boolean;
  snapshot?: RepositorySnapshot | null;
}

interface FlowAvailability {
  enabled: boolean;
  reason?: string;
}

function snapshotStats(snapshot?: RepositorySnapshot | null) {
  const changedCount =
    (snapshot?.stagedChanges.length ?? 0) +
    (snapshot?.modifiedChanges.length ?? 0) +
    (snapshot?.untrackedPaths.length ?? 0);
  const conflictCount = snapshot?.conflicts.length ?? 0;
  const hasRemote = (snapshot?.remoteNames.length ?? 0) > 0;
  const hasGitHub = (snapshot?.remoteProviders ?? []).some((remote) => remote.provider === "github");
  const hasGitLab = (snapshot?.remoteProviders ?? []).some((remote) => remote.provider === "gitlab");
  return {
    changedCount,
    conflictCount,
    hasRemote,
    hasGitHub,
    hasGitLab,
    hasProviderPr: hasGitHub || hasGitLab,
    hasUpstream: Boolean(snapshot?.upstreamRemote && snapshot.upstreamBranch),
    ahead: snapshot?.ahead ?? 0,
    localBranchCount: snapshot?.localBranches.length ?? 0,
  };
}

function availabilityFor(flowId: WizardFlowId, snapshot?: RepositorySnapshot | null): FlowAvailability {
  if (!snapshot) return { enabled: false, reason: "Repository context is still loading." };
  const stats = snapshotStats(snapshot);

  if (flowId === "conflicts") {
    return stats.conflictCount > 0
      ? { enabled: true }
      : { enabled: false, reason: "No unresolved conflicts right now." };
  }

  if (stats.conflictCount > 0 && [
    "commit_push",
    "stage_only",
    "pull",
    "stash",
    "discard",
    "revert",
    "switch_branch",
    "draft_pr",
    "draft_release",
  ].includes(flowId)) {
    return { enabled: false, reason: "Resolve merge conflicts before running write actions." };
  }

  switch (flowId) {
    case "fetch":
      return stats.hasRemote ? { enabled: true } : { enabled: false, reason: "Add a remote before fetching." };
    case "pull":
      return stats.hasRemote ? { enabled: true } : { enabled: false, reason: "Add a remote before pulling." };
    case "commit_push":
      return stats.changedCount > 0 || stats.ahead > 0
        ? { enabled: true }
        : { enabled: false, reason: "No local changes or commits need pushing." };
    case "stage_only":
      return stats.changedCount > 0
        ? { enabled: true }
        : { enabled: false, reason: "No changed files to stage or commit." };
    case "stash":
      return stats.changedCount > 0
        ? { enabled: true }
        : { enabled: false, reason: "No local changes to stash." };
    case "discard":
      return stats.changedCount > 0
        ? { enabled: true }
        : { enabled: false, reason: "No local changes to discard." };
    case "revert":
      if (stats.changedCount > 0) return { enabled: false, reason: "Commit or stash local changes before reverting." };
      return (snapshot.recentCommits?.length ?? 0) > 0
        ? { enabled: true }
        : { enabled: false, reason: "No commits are available to revert." };
    case "switch_branch":
      return stats.localBranchCount > 1
        ? { enabled: true }
        : { enabled: false, reason: "No other local branches are available." };
    case "connect_remote":
      return stats.hasRemote
        ? { enabled: false, reason: "This repository already has a remote." }
        : { enabled: true };
    case "publish_github":
      return stats.hasRemote
        ? { enabled: false, reason: "Use Publish GitHub only for local repos without a remote." }
        : { enabled: true };
    case "draft_release":
      return stats.hasGitHub
        ? { enabled: true }
        : { enabled: false, reason: "GitHub draft releases require a GitHub remote." };
    case "draft_pr":
      return stats.hasProviderPr
        ? { enabled: true }
        : { enabled: false, reason: "Draft PR/MR requires a GitHub or GitLab remote." };
    default:
      return { enabled: true };
  }
}

function primaryFlowIdsFor(snapshot?: RepositorySnapshot | null): WizardFlowId[] {
  const stats = snapshotStats(snapshot);
  const ids: WizardFlowId[] = ["status", "diff", "log"];

  if (stats.conflictCount > 0) {
    ids.push("conflicts");
    return ids;
  }

  if (stats.changedCount > 0 || stats.ahead > 0) ids.push("commit_push");
  if (stats.hasRemote) {
    ids.push("pull", "fetch");
    if (stats.hasProviderPr) ids.push("draft_pr");
    if (stats.hasGitHub) ids.push("draft_release");
  } else {
    ids.push("connect_remote", "publish_github");
  }

  return ids.slice(0, 7);
}

export function CommandBar({ onSelect, disabled, snapshot }: CommandBarProps) {
  const [expanded, setExpanded] = useState(false);
  const readFlows = FLOWS.filter((f) => f.category === "read");
  const writeFlows = FLOWS.filter((f) => f.category === "write");
  const primaryFlowIds = primaryFlowIdsFor(snapshot);
  const primaryFlows = primaryFlowIds
    .map((id) => FLOWS.find((flow) => flow.id === id))
    .filter((flow): flow is FlowDef => Boolean(flow));

  function selectFlow(flowId: WizardFlowId) {
    setExpanded(false);
    onSelect(flowId);
  }

  function renderFlowButton(flow: FlowDef, variant: "read" | "write" | "primary") {
    const availability = availabilityFor(flow.id, snapshot);
    const isDisabled = disabled || !availability.enabled;
    const categoryClass = flow.category === "read" ? "command-pill-read" : "command-pill-write";
    return (
      <button
        key={flow.id}
        type="button"
        className={`command-pill ${categoryClass} command-pill-${variant} ${availability.enabled ? "" : "command-pill-unavailable"}`}
        disabled={isDisabled}
        onClick={() => selectFlow(flow.id)}
        title={availability.enabled ? flow.description : availability.reason}
        data-tour={flow.id === "connect_remote" ? "connect-remote" : undefined}
      >
        <span className="command-pill-icon">{flow.icon}</span>
        {flow.label}
      </button>
    );
  }

  return (
    <div className={`command-bar ${expanded ? "command-bar-expanded" : ""}`}>
      {expanded && (
        <div className="command-drawer">
          <div className="command-drawer-section" data-tour="command-read">
            <span className="command-bar-section-label">READ</span>
            <div className="command-drawer-actions">
              {readFlows.map((flow) => renderFlowButton(flow, "read"))}
            </div>
          </div>
          <div className="command-drawer-section" data-tour="command-write">
            <span className="command-bar-section-label">WRITE</span>
            <div className="command-drawer-actions">
              {writeFlows.map((flow) => renderFlowButton(flow, "write"))}
            </div>
          </div>
        </div>
      )}

      <div className="command-primary-row" data-tour="command-primary">
        <span className="command-bar-section-label">ACTIONS</span>
        <div className="command-primary-actions">
          {primaryFlows.map((flow) => renderFlowButton(flow, "primary"))}
        </div>
        <button
          type="button"
          className="command-pill command-pill-more"
          disabled={disabled}
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={expanded}
          title={expanded ? "Hide command drawer" : "Show all commands"}
        >
          <span className="command-pill-icon">{expanded ? "−" : "+"}</span>
          {expanded ? "Less" : "More"}
        </button>
      </div>
    </div>
  );
}
