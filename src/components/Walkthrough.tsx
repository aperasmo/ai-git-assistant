import { useEffect, useLayoutEffect, useState } from "react";
import { WALKTHROUGH_STEPS } from "../lib/walkthroughSteps";

interface WalkthroughProps {
  open: boolean;
  step: number;
  onNext: () => void;
  onBack: () => void;
  onClose: () => void;
}

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const TOOLTIP_WIDTH = 320;
const TOOLTIP_GAP = 14;

export function Walkthrough({ open, step, onNext, onBack, onClose }: WalkthroughProps) {
  const [spotlightRect, setSpotlightRect] = useState<SpotlightRect | null>(null);
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({
    position: "fixed",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    width: TOOLTIP_WIDTH,
  });

  const currentStep = WALKTHROUGH_STEPS[step];
  const total = WALKTHROUGH_STEPS.length;
  const isFirst = step === 0;
  const isLast = step === total - 1;

  // useLayoutEffect so positions are computed before the browser paints — no flash.
  useLayoutEffect(() => {
    if (!open || !currentStep) return;

    if (!currentStep.target) {
      setSpotlightRect(null);
      setTooltipStyle({
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: TOOLTIP_WIDTH,
      });
      return;
    }

    const el = document.querySelector(currentStep.target);
    if (!el) {
      // Target not in DOM (e.g. command bar before a repo is selected) — center fallback.
      setSpotlightRect(null);
      setTooltipStyle({
        position: "fixed",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: TOOLTIP_WIDTH,
      });
      return;
    }

    const pad = currentStep.padding ?? 10;
    const r = el.getBoundingClientRect();
    const spotlight: SpotlightRect = {
      top: r.top - pad,
      left: r.left - pad,
      width: r.width + pad * 2,
      height: r.height + pad * 2,
    };
    setSpotlightRect(spotlight);

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const style: React.CSSProperties = { position: "fixed", width: TOOLTIP_WIDTH };

    switch (currentStep.side) {
      case "right":
        style.left = Math.min(spotlight.left + spotlight.width + TOOLTIP_GAP, vw - TOOLTIP_WIDTH - 16);
        style.top = Math.max(8, Math.min(spotlight.top + spotlight.height / 2 - 100, vh - 220));
        break;
      case "left":
        style.left = Math.max(8, spotlight.left - TOOLTIP_WIDTH - TOOLTIP_GAP);
        style.top = Math.max(8, Math.min(spotlight.top + spotlight.height / 2 - 100, vh - 220));
        break;
      case "bottom":
        style.left = Math.max(8, Math.min(spotlight.left + spotlight.width / 2 - TOOLTIP_WIDTH / 2, vw - TOOLTIP_WIDTH - 16));
        style.top = Math.min(spotlight.top + spotlight.height + TOOLTIP_GAP, vh - 220);
        break;
      case "top":
      default:
        style.left = Math.max(8, Math.min(spotlight.left + spotlight.width / 2 - TOOLTIP_WIDTH / 2, vw - TOOLTIP_WIDTH - 16));
        style.top = Math.max(8, spotlight.top - 190 - TOOLTIP_GAP);
        break;
    }

    setTooltipStyle(style);
  }, [open, step, currentStep]);

  // Escape key skips the tour.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !currentStep) return null;

  const isCentered = currentStep.side === "center" || !spotlightRect;

  return (
    <div className={`walkthrough-overlay${isCentered ? " walkthrough-overlay-dim" : ""}`}>
      {spotlightRect && (
        <div
          className="walkthrough-spotlight"
          style={{
            top: spotlightRect.top,
            left: spotlightRect.left,
            width: spotlightRect.width,
            height: spotlightRect.height,
          }}
        />
      )}

      <div
        className="walkthrough-tooltip"
        style={tooltipStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="walkthrough-tooltip-meta">
          <span className="walkthrough-step-badge">{step + 1} / {total}</span>
          <button type="button" className="walkthrough-x" onClick={onClose} title="Close tour">✕</button>
        </div>

        <h3 className="walkthrough-title">{currentStep.title}</h3>
        <p className="walkthrough-body">{currentStep.body}</p>

        <div className="walkthrough-actions">
          {!isFirst && (
            <button type="button" className="walkthrough-btn walkthrough-back" onClick={onBack}>
              ← Back
            </button>
          )}
          <button
            type="button"
            className={`walkthrough-btn ${isLast ? "walkthrough-finish" : "walkthrough-next"}`}
            onClick={isLast ? onClose : onNext}
          >
            {isLast ? "Start exploring →" : "Next →"}
          </button>
          {!isLast && (
            <button type="button" className="walkthrough-btn walkthrough-skip" onClick={onClose}>
              Skip
            </button>
          )}
        </div>

        {/* Progress dots */}
        <div className="walkthrough-dots">
          {WALKTHROUGH_STEPS.map((_, i) => (
            <span
              key={i}
              className={`walkthrough-dot${i === step ? " walkthrough-dot-active" : ""}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
