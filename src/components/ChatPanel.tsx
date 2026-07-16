import { FormEvent, useEffect, useRef, useState } from "react";
import type {
  ChatTranscriptEntry,
  GenerateCommitMessageResponse,
  GeneratePullRequestDraftResponse,
  CommitMessageStyle,
  LocalActionPlan,
  RecoveryOption,
} from "../lib/types";
import type { WizardData, WizardFlowId } from "../lib/flows";
import { CommandBar } from "./CommandBar";
import { WizardStep } from "./WizardStep";

interface ChatPanelProps {
  repositorySelected: boolean;
  busy: boolean;
  transcript: ChatTranscriptEntry[];
  pendingPlanId?: string | null;
  applicationError?: string | null;
  onSubmit: (message: string) => Promise<void>;
  onApprovePlan: (planId: string) => Promise<void>;
  onCancelPlan: (planId: string) => Promise<void>;
  onWizardSelect: (flowId: WizardFlowId) => void;
  onWizardNext: (choiceLabel: string, data: Partial<WizardData>) => void;
  onWizardConfirm: () => void;
  onWizardCancel: () => void;
  onAddToGitignore: (paths: string[]) => Promise<string[]>;
  onGenerateCommitMessage: (paths: string[], style?: CommitMessageStyle) => Promise<GenerateCommitMessageResponse>;
  onGeneratePullRequestDraft: (baseBranch: string) => Promise<GeneratePullRequestDraftResponse>;
  onPickReleaseAsset: () => Promise<string[]>;
  onRecoveryAction: (option: RecoveryOption) => void;
}

function statusLabel(status: "pending" | "executed" | "cancelled" | "failed") {
  switch (status) {
    case "pending":
      return "AWAITING APPROVAL";
    case "executed":
      return "EXECUTED";
    case "cancelled":
      return "CANCELLED";
    case "failed":
      return "FAILED";
  }
}

function diffLineClass(line: string) {
  if (line.startsWith("diff --git")) return "diff-line diff-line-file";
  if (line.startsWith("@@")) return "diff-line diff-line-hunk";
  if (line.startsWith("+++") || line.startsWith("---")) return "diff-line diff-line-meta";
  if (line.startsWith("+")) return "diff-line diff-line-add";
  if (line.startsWith("-")) return "diff-line diff-line-delete";
  return "diff-line";
}

function ResultBody({
  content,
  contentKind,
}: {
  content: string;
  contentKind?: "text" | "diff" | "graph";
}) {
  if (contentKind === "diff") {
    return (
      <pre className="result-diff" aria-label="Patch diff">
        {(content || "No output returned.").split("\n").map((line, index) => (
          <code key={`${index}-${line}`} className={diffLineClass(line)}>
            {line || " "}
          </code>
        ))}
      </pre>
    );
  }

  if (contentKind === "graph") {
    return <pre className="result-graph">{content || "No output returned."}</pre>;
  }

  return <pre>{content || "No output returned."}</pre>;
}

function PlanCard({
  plan,
  status,
  busy,
  active,
  onApprove,
  onCancel,
}: {
  plan: LocalActionPlan;
  status: "pending" | "executed" | "cancelled" | "failed";
  busy: boolean;
  active: boolean;
  onApprove: (planId: string) => void;
  onCancel: (planId: string) => void;
}) {
  return (
    <section className={`plan-card plan-card-${status}`}>
      <div className="plan-card-heading">
        <div>
          <span>
            {plan.source === "llm" ? "AI GIT PLAN" : "LOCAL GIT PLAN"}
            {plan.source === "llm" && <span className="plan-ai-badge">AI</span>}
          </span>
          <strong>Review before execution</strong>
        </div>
        <em>{statusLabel(status)}</em>
      </div>

      <p className="plan-explanation">
        {status === "executed"
          ? "This approved plan was executed successfully."
          : status === "cancelled"
            ? "This plan was cancelled. No Git changes were made."
            : status === "failed"
              ? "This approved plan could not be completed."
              : plan.explanation}
      </p>

      {plan.risk && (
        <div className={`plan-risk plan-risk-${plan.risk.level}`}>
          <strong>{plan.risk.level.toUpperCase()} RISK</strong>
          <span>{plan.risk.summary}</span>
          <small>Score {plan.risk.score}/100</small>
          {plan.risk.reasons.length > 0 && (
            <ul>
              {plan.risk.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {plan.privacyReceipt && (
        <details className="plan-privacy-receipt">
          <summary>
            Privacy receipt · {plan.privacyReceipt.externalProvider ? "AI provider used" : "local only"}
          </summary>
          <p>{plan.privacyReceipt.purpose}</p>
          {plan.privacyReceipt.externalProvider && (
            <p>
              Sent to: <code>{plan.privacyReceipt.provider ?? "AI provider"}</code>
              {plan.privacyReceipt.model ? <> / <code>{plan.privacyReceipt.model}</code></> : null}
            </p>
          )}
          <p>
            Files: <code>{plan.privacyReceipt.files.length}</code> · Characters:{" "}
            <code>{plan.privacyReceipt.characterCount}</code>
            {plan.privacyReceipt.truncated ? " · truncated" : ""}
          </p>
          {plan.privacyReceipt.contextItems.length > 0 && (
            <ul>
              {plan.privacyReceipt.contextItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          {plan.privacyReceipt.exactContext && (
            <pre>{plan.privacyReceipt.exactContext}</pre>
          )}
        </details>
      )}

      <ol className="plan-step-list">
        {plan.steps.map((step, index) => (
          <li key={`${step.kind}-${index}`} className="plan-step">
            <span className="plan-step-number">{index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <p>{step.detail}</p>

              {step.paths.length > 0 && (
                <ul className="plan-path-list">
                  {step.paths.map((path) => (
                    <li key={path}>
                      <code>{path}</code>
                    </li>
                  ))}
                </ul>
              )}

              {step.commitMessage && (
                <p className="plan-commit-message">
                  Commit message: <code>{step.commitMessage}</code>
                </p>
              )}

              {step.remote && step.branch && (
                <p className="plan-push-target">
                  Target: <code>{step.branch} → {step.remote}/{step.branch}</code>
                </p>
              )}
              {step.stashRef && (
                <p className="plan-metadata">
                  Stash: <code>{step.stashRef}</code>
                </p>
              )}
              {step.tagName && (
                <p className="plan-metadata">
                  Tag: <code>{step.tagName}</code>
                </p>
              )}
              {step.branch && step.kind !== "push" && (
                <p className="plan-metadata">
                  Branch: <code>{step.branch}</code>
                </p>
              )}

              {step.kind === "commit" && step.paths.length > 0 && (
                <p className="plan-metadata">
                  Files included: <code>{step.paths.length}</code>
                </p>
              )}

              {step.ahead !== null && step.ahead !== undefined && (
                <p className="plan-metadata">
                  Ahead: <code>{step.ahead}</code>
                </p>
              )}

              {step.behind !== null && step.behind !== undefined && (
                <p className="plan-metadata">
                  Behind: <code>{step.behind}</code>
                </p>
              )}

              {step.force !== null && step.force !== undefined && (
                <p className="plan-metadata">
                  Force: <code>{step.force ? "true" : "false"}</code>
                </p>
              )}

              {step.commandPreview && (
                <div className="plan-command-preview">
                  <span>Equivalent Git command</span>
                  <code>{step.commandPreview}</code>
                </div>
              )}              
            </div>
          </li>
        ))}
      </ol>

      {status === "pending" && active && plan.planId && (
        <div className="plan-actions">
          <button
            type="button"
            className="plan-approve-button"
            disabled={busy}
            onClick={() => onApprove(plan.planId ?? "")}
          >
            {busy ? "Executing..." : "Approve and execute"}
          </button>
          <button
            type="button"
            className="plan-cancel-button"
            disabled={busy}
            onClick={() => onCancel(plan.planId ?? "")}
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}

function TranscriptItem({
  entry,
  busy,
  pendingPlanId,
  onApprovePlan,
  onCancelPlan,
  onWizardNext,
  onWizardConfirm,
  onWizardCancel,
  onAddToGitignore,
  onGenerateCommitMessage,
  onGeneratePullRequestDraft,
  onPickReleaseAsset,
  onRecoveryAction,
}: {
  entry: ChatTranscriptEntry;
  busy: boolean;
  pendingPlanId?: string | null;
  onApprovePlan: (planId: string) => void;
  onCancelPlan: (planId: string) => void;
  onWizardNext: (choiceLabel: string, data: Partial<WizardData>) => void;
  onWizardConfirm: () => void;
  onWizardCancel: () => void;
  onAddToGitignore: (paths: string[]) => Promise<string[]>;
  onGenerateCommitMessage: (paths: string[], style?: CommitMessageStyle) => Promise<GenerateCommitMessageResponse>;
  onGeneratePullRequestDraft: (baseBranch: string) => Promise<GeneratePullRequestDraftResponse>;
  onPickReleaseAsset: () => Promise<string[]>;
  onRecoveryAction: (option: RecoveryOption) => void;
}) {
  if (entry.kind === "user") {
    return (
      <section className="user-message-card">
        <span>You</span>
        <p>{entry.message}</p>
      </section>
    );
  }

  if (entry.kind === "result") {
    return (
      <section className="result-card">
        <div className="result-card-heading">
          <span>LOCAL RESULT</span>
          <strong>{entry.title}</strong>
        </div>
        <p>{entry.summary}</p>
        <ResultBody content={entry.content} contentKind={entry.contentKind} />
      </section>
    );
  }

  if (entry.kind === "error") {
    return (
      <section className="error-card">
        <strong>Request could not be completed</strong>
        <p>{entry.message}</p>
      </section>
    );
  }

  if (entry.kind === "recovery") {
    return (
      <section className="recovery-card">
        <div className="recovery-card-heading">
          <span>NEXT STEP ASSISTANT</span>
          <strong>{entry.title}</strong>
        </div>
        <p>{entry.summary}</p>
        <p>{entry.detail}</p>
        {entry.options.length > 0 && (
          <div className="recovery-actions">
            {entry.options.map((option) => (
              <button
                key={`${option.action}-${option.label}`}
                type="button"
                className={option.recommended ? "recovery-action-primary" : "recovery-action"}
                disabled={busy}
                onClick={() => onRecoveryAction(option)}
              >
                <strong>{option.label}</strong>
                <span>{option.description}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    );
  }

  if (entry.kind === "wizard_menu") {
    return null;
  }

  if (entry.kind === "wizard_step") {
    return (
      <WizardStep
        entry={entry}
        busy={busy}
        onNext={onWizardNext}
        onConfirm={onWizardConfirm}
        onCancel={onWizardCancel}
        onAddToGitignore={onAddToGitignore}
        onGenerateCommitMessage={onGenerateCommitMessage}
        onGeneratePullRequestDraft={onGeneratePullRequestDraft}
        onPickReleaseAsset={onPickReleaseAsset}
      />
    );
  }

  return (
    <PlanCard
      plan={entry.plan}
      status={entry.status}
      busy={busy}
      active={entry.plan.planId === pendingPlanId}
      onApprove={onApprovePlan}
      onCancel={onCancelPlan}
    />
  );
}

export function ChatPanel({
  repositorySelected,
  busy,
  transcript,
  pendingPlanId,
  applicationError,
  onSubmit,
  onApprovePlan,
  onCancelPlan,
  onWizardSelect,
  onWizardNext,
  onWizardConfirm,
  onWizardCancel,
  onAddToGitignore,
  onGenerateCommitMessage,
  onGeneratePullRequestDraft,
  onPickReleaseAsset,
  onRecoveryAction,
}: ChatPanelProps) {
  const [message, setMessage] = useState("");
  const endOfTranscriptRef = useRef<HTMLDivElement | null>(null);
  const hasPendingPlan = Boolean(pendingPlanId);
  const wizardActive = transcript.some(
    (e) => e.kind === "wizard_step" && e.status === "active",
  );
  const commandBarDisabled = !repositorySelected || busy || hasPendingPlan || wizardActive;
  const visibleEntries = transcript.filter((e) => e.kind !== "wizard_menu");

  useEffect(() => {
    endOfTranscriptRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript, busy]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || busy || hasPendingPlan || !repositorySelected) return;

    await onSubmit(trimmed);
    setMessage("");
  }

  return (
    <main className="chat-panel">
      <div className="chat-scroll">
        {!repositorySelected ? (
          <section className="empty-state">
            <div className="empty-state-icon">⌘</div>
            <h2>No repository selected</h2>
            <p>Add a local Git repository from the left sidebar to start.</p>
          </section>
        ) : (
          <>
            <div className="transcript-list">
              {visibleEntries.length === 0 && (
                <section className="empty-state">
                  <div className="empty-state-icon">⌘</div>
                  <h2>Ready</h2>
                  <p>Choose a command below or describe what you want in the text box.</p>
                </section>
              )}
              {visibleEntries.map((entry) => (
                <TranscriptItem
                  key={entry.id}
                  entry={entry}
                  busy={busy}
                  pendingPlanId={pendingPlanId}
                  onApprovePlan={(planId) => void onApprovePlan(planId)}
                  onCancelPlan={(planId) => void onCancelPlan(planId)}
                  onWizardNext={onWizardNext}
                  onWizardConfirm={onWizardConfirm}
                  onWizardCancel={onWizardCancel}
                  onAddToGitignore={onAddToGitignore}
                  onGenerateCommitMessage={onGenerateCommitMessage}
                  onGeneratePullRequestDraft={onGeneratePullRequestDraft}
                  onPickReleaseAsset={onPickReleaseAsset}
                  onRecoveryAction={onRecoveryAction}
                />
              ))}
            </div>

            {applicationError && (
              <section className="error-card">
                <strong>Application notice</strong>
                <p>{applicationError}</p>
              </section>
            )}

            <div ref={endOfTranscriptRef} />
          </>
        )}
      </div>

      {repositorySelected && (
        <CommandBar onSelect={onWizardSelect} disabled={commandBarDisabled} />
      )}

      <form className="chat-composer" onSubmit={submit}>
        <span className="composer-icon" aria-hidden="true">+</span>
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={
            !repositorySelected
              ? "Add a repository to begin..."
              : hasPendingPlan
                ? "Approve or cancel the current plan first..."
                : "Describe the Git action you want..."
          }
          disabled={!repositorySelected || busy || hasPendingPlan}
          aria-label="Git assistant request"
        />
        <button
          type="submit"
          disabled={!repositorySelected || busy || hasPendingPlan || !message.trim()}
        >
          {busy ? "..." : "➜"}
        </button>
      </form>
      <p className="composer-hint">
        Local Git only. Write actions are planned first, then run only after your approval.
      </p>
    </main>
  );
}
