"use client";

import { useCallback, useEffect, useState } from "react";

type SutPhase = {
  number: string;
  title: string;
  description: string;
  details: string[];
  feedsInto: string;
};

const SUT_PHASES: SutPhase[] = [
  {
    number: "01",
    title: "Gazette catalog assembly",
    description:
      "ILAY SUT reads the curated gazette schedules that back current procedure pricing, DRG package pricing, and normative SUT controls.",
    details: [
      "Canonical SUT pricing uses dated gazette catalog lookups.",
      "Procedure, DRG, material, and checkup references stay within SUT-owned routes.",
      "Historical package availability is preserved instead of silently falling forward.",
    ],
    feedsInto: "SUT reference tools, pricing APIs, and billing review",
  },
  {
    number: "02",
    title: "Patient SUT rule assembly",
    description:
      "The patient workspace composes SUT outcome and optimization data to show cost, rule-calculation status, and exactness-aware patient findings.",
    details: [
      "Outcome data provides cost, DRG summary, and claim-line rule context.",
      "Optimization data provides copay exemption and exactness-aware rule findings.",
      "Home patient search now routes into the dedicated patient workspace.",
    ],
    feedsInto: "Patient workspace and billing handoff",
  },
  {
    number: "03",
    title: "Exactness-first optimization",
    description:
      "Unavailable optimization surfaces stay unavailable until the exact billed inputs exist, rather than being shown as low risk or zero impact.",
    details: [
      "Copay exemptions stay actionable when exact.",
      "Surcharge, copay-rate, and DRG-unbundling findings respect missing exact inputs.",
      "The patient workspace and optimizer share the same exactness semantics.",
    ],
    feedsInto: "Optimizer alerts and revenue recovery review",
  },
  {
    number: "04",
    title: "Dedicated billing handoff",
    description:
      "Patient-level financial review stays split across a high-level patient workspace and the deeper billing route, instead of pushing everything into home.",
    details: [
      "The new `/patient/[id]` page becomes the main patient shell.",
      "Detailed section-by-section billing remains on `/patient/[id]/billing`.",
      "The handoff keeps ownership and routing clear inside the split app.",
    ],
    feedsInto: "Patient route and dedicated billing route",
  },
  {
    number: "05",
    title: "Product-owned SUT assistant",
    description:
      "The restored chatbot is wired to SUT-only context so it can explain exposure, optimization, and patient SUT rule state without depending on IHP cache readiness.",
    details: [
      "Frontend chat requests use `/api/chat`.",
      "Context assembly stays inside SUT exposure, optimization, and patient routes.",
      "Unavailable exactness states are explained, not converted into fake numerics.",
    ],
    feedsInto: "SUT-owned assistant context",
  },
];

export default function SutHowItWorksModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const handleClose = useCallback(() => {
    setActiveIndex(0);
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleClose, open]);

  if (!open) {
    return null;
  }

  const phase = SUT_PHASES[activeIndex];

  return (
    <div
      className="how-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="How ILAY SUT works"
      onClick={handleClose}
    >
      <div
        className="how-modal frost-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="how-modal-head">
          <div className="how-modal-title-block">
            <span className="how-modal-kicker">
              ILAY SUT
            </span>
            <h2>How the SUT workspace works</h2>
            <p className="how-modal-intro">
              The split SUT app focuses on billing rule analytics, exactness-aware optimization,
              and patient financial review without reaching back into mixed legacy IHP surfaces.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="how-phase-counter">
              {activeIndex + 1} / {SUT_PHASES.length}
            </div>
            <button
              type="button"
              onClick={handleClose}
              aria-label="Close how it works modal"
              className="how-modal-close"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="how-modal-content">
          <div className="how-stepper-layout">
            <nav className="how-phase-nav" aria-label="SUT methodology phases">
              {SUT_PHASES.map((entry, index) => (
                <button
                  key={entry.number}
                  type="button"
                  onClick={() => setActiveIndex(index)}
                  className={`how-phase-nav-item ${index === activeIndex ? "is-active" : ""} ${index < activeIndex ? "is-past" : ""}`}
                  aria-current={index === activeIndex ? "step" : undefined}
                >
                  <span className="how-phase-dot">{entry.number}</span>
                  <span className="how-phase-nav-label">{entry.title}</span>
                </button>
              ))}
              <div className="how-phase-line" aria-hidden="true" />
            </nav>

            <section className="how-phase-detail" key={activeIndex} aria-live="polite">
              <div className="how-phase-header">
                <span className="how-phase-badge">
                  Phase {phase.number}
                </span>
                <h3 className="how-phase-title">{phase.title}</h3>
              </div>

              <p className="how-phase-description">{phase.description}</p>

              <div className="how-phase-details-grid">
                {phase.details.map((detail) => (
                  <div key={detail} className="how-phase-detail-item">
                    <span className="how-phase-detail-bullet" aria-hidden="true" />
                    <span>{detail}</span>
                  </div>
                ))}
              </div>

              <div className="how-phase-feeds">
                <span className="how-phase-feeds-label">Powers</span>
                <span className="how-phase-feeds-value">{phase.feedsInto}</span>
              </div>

              <div className="how-phase-nav-buttons">
                <button
                  type="button"
                  onClick={() => setActiveIndex((current) => Math.max(0, current - 1))}
                  disabled={activeIndex === 0}
                  className="how-phase-btn"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (activeIndex < SUT_PHASES.length - 1) {
                      setActiveIndex((current) => current + 1);
                      return;
                    }
                    handleClose();
                  }}
                  className="how-phase-btn how-phase-btn-primary"
                >
                  {activeIndex < SUT_PHASES.length - 1 ? "Next Phase" : "Got It"}
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
