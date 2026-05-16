"use client";

import type { ReactNode } from "react";
import { Bot, CircleHelp, ReceiptText, ShieldCheck, Stethoscope } from "lucide-react";
import { SUT_BRAND } from "@/lib/constants";
import { SyntheticDemoProvenance } from "@/components/sut/SyntheticDemoProvenance";
import type { SUTDataSourceMetadata } from "@/lib/domains/sut";

type LandingCard = {
  icon: ReactNode;
  title: string;
  body: string;
};

const ICON_PROPS = { size: 18, "aria-hidden": true };

const LANDING_CARDS: LandingCard[] = [
  {
    icon: <ReceiptText {...ICON_PROPS} />,
    title: "Exact SUT rule visibility",
    body: "Track SUT-based patient cost and DRG package pricing without falling back to mixed legacy patient views.",
  },
  {
    icon: <ShieldCheck {...ICON_PROPS} />,
    title: "Exactness-aware optimization",
    body: "Keep unavailable compliance surfaces explicitly unavailable until the underlying claim inputs are exact.",
  },
  {
    icon: <Bot {...ICON_PROPS} />,
    title: "Product-owned SUT assistant",
    body: "Use the restored chatbot for SUT analytics, optimizer context, and patient financial workspace guidance without depending on IHP cache state.",
  },
  {
    icon: <Stethoscope {...ICON_PROPS} />,
    title: "Patient-first workspace",
    body: "Route from cohort search into a dedicated patient workspace, then hand off cleanly into the detailed billing review when needed.",
  },
];

export default function SutLandingHero({
  onEnter,
  onOpenHowItWorks,
  dataSource,
}: {
  onEnter: () => void;
  onOpenHowItWorks: () => void;
  dataSource?: SUTDataSourceMetadata | null;
}) {
  return (
    <section className="frost-panel sut-premium-panel sut-landing-hero sut-premium-enter">
      <div className="sut-landing-grid">
        <div className="space-y-5">
          <div className="sut-hero-badges">
            <span className="sut-premium-pill">
              {SUT_BRAND.moduleLabel}
            </span>
            <span className="sut-premium-pill sut-premium-pill-muted">
              Split workspace
            </span>
          </div>
          <SyntheticDemoProvenance dataSource={dataSource} compact />

          <div className="space-y-3">
            <h1 className="sut-premium-title max-w-3xl">
              Restore the SUT shell around exact claim-line rule work.
            </h1>
            <p className="sut-premium-subtitle max-w-3xl">
              {SUT_BRAND.heroDescription} Start from the SUT landing surface, move into
               analytics or optimizer workflows, and jump into an exactness-aware patient
              workspace when you need patient-level SUT rule review.
            </p>
          </div>

          <div className="sut-landing-actions">
            <button
              type="button"
              onClick={onEnter}
              className="sut-btn-primary"
            >
              Enter SUT workspace
            </button>
            <button
              type="button"
              onClick={onOpenHowItWorks}
              className="sut-btn-secondary inline-flex items-center gap-2"
            >
              <CircleHelp className="h-4 w-4" aria-hidden="true" />
              How it works
            </button>
          </div>
        </div>

        <div className="sut-landing-card-grid">
          {LANDING_CARDS.map((card) => (
            <article
              key={card.title}
              className="sut-landing-card"
            >
              <div className="sut-landing-icon">
                {card.icon}
              </div>
              <h2 className="sut-landing-card-title">{card.title}</h2>
              <p className="sut-landing-card-body">{card.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
