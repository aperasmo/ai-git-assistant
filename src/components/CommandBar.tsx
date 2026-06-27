import { FLOWS, type WizardFlowId } from "../lib/flows";

interface CommandBarProps {
  onSelect: (flowId: WizardFlowId) => void;
  disabled: boolean;
}

export function CommandBar({ onSelect, disabled }: CommandBarProps) {
  const readFlows = FLOWS.filter((f) => f.category === "read");
  const writeFlows = FLOWS.filter((f) => f.category === "write");

  return (
    <div className="command-bar">
      <div className="command-bar-row">
        <span className="command-bar-section-label">READ</span>
        {readFlows.map((flow) => (
          <button
            key={flow.id}
            type="button"
            className="command-pill command-pill-read"
            disabled={disabled}
            onClick={() => onSelect(flow.id)}
            title={flow.description}
          >
            <span className="command-pill-icon">{flow.icon}</span>
            {flow.label}
          </button>
        ))}
      </div>
      <div className="command-bar-row">
        <span className="command-bar-section-label">WRITE</span>
        {writeFlows.map((flow) => (
          <button
            key={flow.id}
            type="button"
            className="command-pill command-pill-write"
            disabled={disabled}
            onClick={() => onSelect(flow.id)}
            title={flow.description}
          >
            <span className="command-pill-icon">{flow.icon}</span>
            {flow.label}
          </button>
        ))}
      </div>
    </div>
  );
}
