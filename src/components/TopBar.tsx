import { getVersion } from "@tauri-apps/api/app";
import { useEffect, useState } from "react";
import type { GitInstallationStatus, Repository } from "../lib/types";
import { BrandMark } from "./BrandMark";

interface TopBarProps {
  repository?: Repository | null;
  gitStatus?: GitInstallationStatus | null;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onOpenDiagnostics: () => void;
  onOpenTour: () => void;
  onOpenHelp: () => void;
}

export function TopBar({
  repository,
  gitStatus,
  theme,
  onToggleTheme,
  onOpenSettings,
  onOpenDiagnostics,
  onOpenTour,
  onOpenHelp,
}: TopBarProps) {
  const [appVersion, setAppVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getVersion()
      .then((version) => {
        if (!cancelled) {
          setAppVersion(formatFileVersion(version));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAppVersion(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="topbar">
      <div className="topbar-title">
        <BrandMark />
        <strong>AI Git Assistant</strong>
        {appVersion && (
          <span className="beta-tag" title={`App version ${appVersion}`}>
            v{appVersion}
          </span>
        )}
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
        <button
          type="button"
          className="theme-toggle-button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          <span aria-hidden="true">{theme === "dark" ? "☾" : "☀"}</span>
        </button>
        <button type="button" className="tour-button" onClick={onOpenTour} title="Take a tour">
          ?
        </button>
        <button type="button" className="text-button" onClick={onOpenHelp}>
          Help
        </button>
        <button type="button" className="text-button" onClick={onOpenDiagnostics}>
          Diagnostics
        </button>
        <button type="button" className="text-button" onClick={onOpenSettings}>
          Settings
        </button>
      </div>
    </header>
  );
}

function formatFileVersion(version: string): string {
  const [coreVersion, suffix] = version.split(/[-+]/, 2);
  const parts = coreVersion.split(".");
  const displayVersion = parts.length === 3 ? `${coreVersion}.0` : coreVersion;

  return suffix ? `${displayVersion}-${suffix}` : displayVersion;
}
