import { useState } from "react";
import { FLOWS, type FlowDef, type WizardFlowId } from "../lib/flows";

interface CommandBarProps {
  onSelect: (flowId: WizardFlowId) => void;
  disabled: boolean;
}

export function CommandBar({ onSelect, disabled }: CommandBarProps) {
  const [expanded, setExpanded] = useState(false);
  const readFlows = FLOWS.filter((f) => f.category === "read");
  const writeFlows = FLOWS.filter((f) => f.category === "write");
  const primaryFlowIds: WizardFlowId[] = [
    "status",
    "diff",
    "log",
    "commit_push",
    "pull",
    "connect_remote",
  ];
  const primaryFlows = primaryFlowIds
    .map((id) => FLOWS.find((flow) => flow.id === id))
    .filter((flow): flow is FlowDef => Boolean(flow));

  function selectFlow(flowId: WizardFlowId) {
    setExpanded(false);
    onSelect(flowId);
  }

  function renderFlowButton(flow: FlowDef, variant: "read" | "write" | "primary") {
    const categoryClass = flow.category === "read" ? "command-pill-read" : "command-pill-write";
    return (
      <button
        key={flow.id}
        type="button"
        className={`command-pill ${categoryClass} command-pill-${variant}`}
        disabled={disabled}
        onClick={() => selectFlow(flow.id)}
        title={flow.description}
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
