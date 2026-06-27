import type { GitInstallationStatus, Repository } from "../lib/types";
import { BrandMark } from "./BrandMark";

interface TopBarProps {
  repository?: Repository | null;
  gitStatus?: GitInstallationStatus | null;
  onOpenSettings: () => void;
  onOpenTour: () => void;
}

export function TopBar({ repository, gitStatus, onOpenSettings, onOpenTour }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <BrandMark />
        <strong>AI Git Assistant</strong>
        <span className="beta-tag">PHASE 3</span>
      </div>

      <div className="topbar-context">
        {repository ? (
          <>
            <span className="repository-pill">
              <span className="repository-initial">
                {repository.displayName.slice(0, 1).toUpperCase()}
              </span>
              {repository.displayName}
            </span>
            <span className="branch-pill">
              <span aria-hidden="true">⑂</span>
              {repository.currentBranch ?? "No branch"}
            </span>
          </>
        ) : (
          <span className="repository-pill muted">No repository selected</span>
        )}
      </div>

      <div className="topbar-actions">
        <span className={gitStatus?.status === "available" ? "git-ready" : "git-warning"}>
          {gitStatus?.status === "available" ? "Git ready" : "Git check pending"}
        </span>
        <button type="button" className="tour-button" onClick={onOpenTour} title="Take a tour">
          ?
        </button>
        <button type="button" className="text-button" onClick={onOpenSettings}>
          Settings
        </button>
      </div>
    </header>
  );
}
