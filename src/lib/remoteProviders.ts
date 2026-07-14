import type { RemoteProviderInfo, RepositorySnapshot } from "./types";

export function providerSummary(snapshot?: RepositorySnapshot | null): string {
  const providers = snapshot?.remoteProviders ?? [];
  if (providers.length === 0) return "Local only";

  const knownLabels = Array.from(
    new Set(providers.filter((item) => item.provider !== "unknown").map((item) => item.label)),
  );
  if (knownLabels.length === 0) return "Unknown provider";
  if (knownLabels.length === 1) return knownLabels[0];
  return knownLabels.join(" + ");
}

export function githubRemote(snapshot?: RepositorySnapshot | null): RemoteProviderInfo | null {
  return (snapshot?.remoteProviders ?? []).find((item) => item.provider === "github") ?? null;
}

export function gitlabRemote(snapshot?: RepositorySnapshot | null): RemoteProviderInfo | null {
  return (snapshot?.remoteProviders ?? []).find((item) => item.provider === "gitlab") ?? null;
}

export function providerDetailLines(snapshot?: RepositorySnapshot | null): string[] {
  const providers = snapshot?.remoteProviders ?? [];
  if (providers.length === 0) return ["No remote configured."];
  return providers.map((item) => {
    const host = item.host ? ` (${item.host})` : "";
    return `${item.remote}: ${item.label}${host}`;
  });
}

export function platformFeatureHint(snapshot?: RepositorySnapshot | null): string {
  const providers = snapshot?.remoteProviders ?? [];
  if (providers.length === 0) {
    return "Platform actions are unavailable until a remote is configured.";
  }

  const labels = Array.from(new Set(providers.map((item) => item.label))).join(", ");
  const hasGitHub = providers.some((item) => item.provider === "github");
  const hasGitLab = providers.some((item) => item.provider === "gitlab");
  if (hasGitHub && hasGitLab) {
    return "GitHub draft releases, GitHub draft pull requests, and GitLab draft merge requests are available.";
  }
  if (hasGitHub) {
    return "GitHub draft releases and draft pull requests are available.";
  }
  if (hasGitLab) {
    return "GitLab draft merge requests are available. GitHub draft releases require a GitHub remote.";
  }
  return `${labels} platform actions are planned. Local Git actions still work.`;
}
