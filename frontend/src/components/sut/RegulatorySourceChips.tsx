import { Chip } from "@/components/primitives";
import { translateApiText } from "@/lib/apiMessages";
import type { RegulatorySourceRef } from "@/lib/sutRegulatorySources";
import type { CopayExemptionResult, PatientAlertCopay } from "@/lib/domains/sut";
import {
  COPAY_RATE_REGULATORY_SOURCE,
  DRG_PACKAGE_EK2C_ANNEX,
  parseEkAnnexLabels,
  SURCHARGE_REGULATORY_SOURCE,
} from "@/lib/sutRegulatorySources";

export function RegulatorySourceChips({
  source,
  className,
}: {
  source: RegulatorySourceRef;
  className?: string;
}) {
  return (
    <span className={`inline-flex flex-wrap items-center gap-1 ${className ?? ""}`}>
      <Chip variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
        {source.annex}
      </Chip>
      {source.sutSection ? (
        <Chip variant="outline" className="font-mono text-[10px]">
          {source.sutSection}
        </Chip>
      ) : null}
    </span>
  );
}

export function EkAnnexChips({
  labels,
  className,
}: {
  labels: string[];
  className?: string;
}) {
  if (labels.length === 0) {
    return null;
  }

  return (
    <span className={`inline-flex flex-wrap items-center gap-1 ${className ?? ""}`}>
      {labels.map((label) => (
        <Chip
          key={label}
          variant="outline"
          className="font-mono text-[10px] uppercase tracking-wide"
        >
          {label}
        </Chip>
      ))}
    </span>
  );
}

export function ProcedureSurchargeSourceCell({
  applicable,
  emDash = "—",
}: {
  applicable: boolean;
  emDash?: string;
}) {
  if (!applicable) {
    return <span className="text-[var(--text-muted)]">{emDash}</span>;
  }
  return <RegulatorySourceChips source={SURCHARGE_REGULATORY_SOURCE} />;
}

export function ProcedureCopayRateSourceCell({
  applicable,
  emDash = "—",
}: {
  applicable: boolean;
  emDash?: string;
}) {
  if (!applicable) {
    return <span className="text-[var(--text-muted)]">{emDash}</span>;
  }
  return <RegulatorySourceChips source={COPAY_RATE_REGULATORY_SOURCE} />;
}

export function RuleSourceAttribution({
  ruleSource,
  className,
}: {
  ruleSource?: string | null;
  className?: string;
}) {
  const trimmed = ruleSource?.trim();
  if (!trimmed) {
    return null;
  }

  const labels = parseEkAnnexLabels(trimmed);

  return (
    <span
      className={`inline-flex flex-wrap items-center gap-1 ${className ?? ""}`}
      title={translateApiText(trimmed)}
    >
      {labels.length > 0 ? (
        <EkAnnexChips labels={labels} />
      ) : (
        <Chip variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
          SUT
        </Chip>
      )}
    </span>
  );
}

export function resolvePatientExemptionRuleSources(
  copay: CopayExemptionResult | PatientAlertCopay,
): { labels: string[]; tooltip: string } {
  const ruleSources = (copay.exemption_sources ?? [])
    .map((source) => source.rule_source?.trim())
    .filter((source): source is string => Boolean(source));
  const tooltip = [...new Set(ruleSources)].join(" · ");
  const labels = [
    ...new Set(ruleSources.flatMap((source) => parseEkAnnexLabels(source))),
  ];

  return { labels, tooltip };
}

export function PatientExemptionRuleSourceAttribution({
  copay,
  className,
}: {
  copay: CopayExemptionResult | PatientAlertCopay;
  className?: string;
}) {
  const { labels, tooltip } = resolvePatientExemptionRuleSources(copay);
  if (!tooltip && labels.length === 0) {
    return null;
  }

  return (
    <span
      className={`inline-flex flex-wrap items-center gap-1 ${className ?? ""}`}
      title={tooltip ? translateApiText(tooltip) : undefined}
    >
      {labels.length > 0 ? (
        <EkAnnexChips labels={labels} />
      ) : (
        <Chip variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
          SUT
        </Chip>
      )}
    </span>
  );
}

export function DrgEk2cGroupCell({
  group,
  emDash = "—",
}: {
  group?: string | null;
  emDash?: string;
}) {
  return (
    <span className="inline-flex items-center justify-center gap-1">
      <Chip variant="outline" className="font-mono text-[10px] uppercase tracking-wide">
        {DRG_PACKAGE_EK2C_ANNEX}
      </Chip>
      <span className="rounded bg-[var(--surface-tint)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
        {group?.trim() || emDash}
      </span>
    </span>
  );
}
