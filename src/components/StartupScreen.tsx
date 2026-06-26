import type { GitInstallationStatus } from "../lib/types";
import { BrandMark } from "./BrandMark";

interface StartupScreenProps {
  message: string;
  gitStatus?: GitInstallationStatus | null;
  failure?: boolean;
}

export function StartupScreen({
  message,
  gitStatus,
  failure = false,
}: StartupScreenProps) {
  return (
    <main className="startup-screen">
      <section className="startup-card">
        <BrandMark />
        <h1>AI Git Assistant</h1>
        <p className={failure ? "startup-error" : "startup-message"}>{message}</p>
        {!failure && <div className="progress-line" aria-label="Starting application" />}
        {gitStatus && (
          <p className="startup-detail">
            Git: {gitStatus.status === "available" ? gitStatus.version : gitStatus.message}
          </p>
        )}
      </section>
    </main>
  );
}
