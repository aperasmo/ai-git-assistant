import { FLOWS, type WizardFlowId } from "../lib/flows";

interface WizardMenuProps {
  onSelect: (flowId: WizardFlowId) => void;
  busy: boolean;
  compact?: boolean;
}

export function WizardMenu({ onSelect, busy, compact = false }: WizardMenuProps) {
  const readFlows = FLOWS.filter((f) => f.category === "read");
  const writeFlows = FLOWS.filter((f) => f.category === "write");

  return (
    <div className={compact ? "wizard-menu wizard-menu-compact" : "wizard-menu"}>
      {compact ? (
        <p className="wizard-menu-next-label">Choose another operation:</p>
      ) : (
        <div className="assistant-intro">
          <div className="assistant-avatar">⌘</div>
          <div>
            <h2>What would you like to do?</h2>
            <p>Choose a Git operation below, or describe what you want in the text box.</p>
          </div>
        </div>
      )}

      <div className="wizard-menu-section">
        <p className="wizard-section-label">READ</p>
        <div className="wizard-menu-grid">
          {readFlows.map((flow) => (
            <button
              key={flow.id}
              type="button"
              className="wizard-menu-item"
              onClick={() => onSelect(flow.id)}
              disabled={busy}
            >
              <span className="wizard-item-icon">{flow.icon}</span>
              <span className="wizard-item-label">{flow.label}</span>
              <small className="wizard-item-desc">{flow.description}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="wizard-menu-section">
        <p className="wizard-section-label">WRITE</p>
        <div className="wizard-menu-grid">
          {writeFlows.map((flow) => (
            <button
              key={flow.id}
              type="button"
              className="wizard-menu-item wizard-item-write"
              onClick={() => onSelect(flow.id)}
              disabled={busy}
            >
              <span className="wizard-item-icon">{flow.icon}</span>
              <span className="wizard-item-label">{flow.label}</span>
              <small className="wizard-item-desc">{flow.description}</small>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
