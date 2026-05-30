"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useT } from "@/lib/i18n/useTranslations";

const PHASE_KEYS = ["01", "02", "03", "04", "05"] as const;

export default function SutHowItWorksModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const [activeIndex, setActiveIndex] = useState(0);

  const phases = useMemo(
    () =>
      PHASE_KEYS.map((key) => ({
        number: key,
        title: t(`app.howItWorks.phases.${key}.title`),
        description: t(`app.howItWorks.phases.${key}.description`),
        details: [
          t(`app.howItWorks.phases.${key}.detail1`),
          t(`app.howItWorks.phases.${key}.detail2`),
          t(`app.howItWorks.phases.${key}.detail3`),
        ],
        feedsInto: t(`app.howItWorks.phases.${key}.feedsInto`),
      })),
    [t],
  );

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

  const phase = phases[activeIndex];

  return (
    <div
      className="how-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t("app.howItWorks.ariaLabel")}
      onClick={handleClose}
    >
      <div
        className="how-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="how-modal-head">
          <div className="how-modal-title-block">
            <span className="how-modal-kicker">
              {t("app.howItWorks.kicker")}
            </span>
            <h2>{t("app.howItWorks.title")}</h2>
            <p className="how-modal-intro">
              {t("app.howItWorks.intro")}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="how-phase-counter">
              {activeIndex + 1} / {phases.length}
            </div>
            <button
              type="button"
              onClick={handleClose}
              aria-label={t("app.howItWorks.closeAria")}
              className="how-modal-close"
            >
              &times;
            </button>
          </div>
        </div>

        <div className="how-modal-content">
          <div className="how-stepper-layout">
            <nav className="how-phase-nav" aria-label={t("app.howItWorks.phaseNavAria")}>
              {phases.map((entry, index) => (
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
                  {t("app.howItWorks.phaseBadge", { number: phase.number })}
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
                <span className="how-phase-feeds-label">{t("app.howItWorks.powersLabel")}</span>
                <span className="how-phase-feeds-value">{phase.feedsInto}</span>
              </div>

              <div className="how-phase-nav-buttons">
                <button
                  type="button"
                  onClick={() => setActiveIndex((current) => Math.max(0, current - 1))}
                  disabled={activeIndex === 0}
                  className="how-phase-btn"
                >
                  {t("app.howItWorks.previous")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (activeIndex < phases.length - 1) {
                      setActiveIndex((current) => current + 1);
                      return;
                    }
                    handleClose();
                  }}
                  className="how-phase-btn how-phase-btn-primary"
                >
                  {activeIndex < phases.length - 1
                    ? t("app.howItWorks.nextPhase")
                    : t("app.howItWorks.gotIt")}
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
