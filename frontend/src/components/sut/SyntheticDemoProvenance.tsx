"use client";

import { Chip } from "@/components/primitives";
import type { SUTDataSourceCarrier, SUTDataSourceMetadata } from "@/lib/domains/sut";
import enMessages from "@/messages/en/index";
import { useT } from "@/lib/i18n/useTranslations";
import { translate } from "@/lib/i18n/translate";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import trMessages from "@/messages/tr/index";

/** @deprecated Use synthetic.defaultNotice via i18n — kept for tests */
export const SYNTHETIC_DEMO_COPY = enMessages.synthetic.defaultNotice;

type ProvenanceInput =
  | SUTDataSourceMetadata
  | SUTDataSourceCarrier
  | null
  | undefined;

export function getSutDataSource(input: ProvenanceInput): SUTDataSourceMetadata | null {
  if (!input) return null;
  if ("mode" in input) return input;
  return input.data_source ?? input.dataSource ?? null;
}

export function isSyntheticDemoDataSource(
  input: ProvenanceInput,
): input is SUTDataSourceMetadata | SUTDataSourceCarrier {
  const dataSource = getSutDataSource(input);
  return dataSource?.mode === "synthetic_demo" || dataSource?.is_synthetic === true;
}

function localizedDefaultNotice(): string {
  const messages = getModuleLocale() === "tr" ? trMessages : enMessages;
  return translate(messages, "synthetic.defaultNotice");
}

function resolveSyntheticNotice(input: ProvenanceInput): string | null {
  const dataSource = getSutDataSource(input);
  if (!isSyntheticDemoDataSource(dataSource)) return null;
  const notice = dataSource.notice?.trim();
  if (!notice) return localizedDefaultNotice();
  if (
    notice === enMessages.synthetic.defaultNotice
    || notice === trMessages.synthetic.defaultNotice
  ) {
    return localizedDefaultNotice();
  }
  return notice;
}

/** Compact top-bar chip — Phase 6 replaces inline page banners. */
export function SyntheticDemoChip({
  dataSource,
  title,
  className,
}: {
  dataSource?: ProvenanceInput;
  title?: string;
  className?: string;
}) {
  const t = useT();
  const notice = resolveSyntheticNotice(dataSource);
  if (!notice) return null;

  return (
    <Chip
      variant="outline"
      className={className}
      title={title ?? notice}
      aria-label={t("synthetic.chipAria")}
    >
      {t("synthetic.chipLabel")}
    </Chip>
  );
}

/**
 * @deprecated Phase 6 — use `SyntheticDemoChip` in `AppTopBar` instead of inline banners.
 * Kept for tests and gradual removal.
 */
export function SyntheticDemoProvenance({
  dataSource,
  dataSources,
  compact = false,
  className = "",
}: {
  dataSource?: ProvenanceInput;
  dataSources?: ProvenanceInput[];
  compact?: boolean;
  className?: string;
}) {
  const t = useT();
  const inputs = [dataSource, ...(dataSources ?? [])];
  const notice = inputs.map(resolveSyntheticNotice).find(Boolean);
  if (!notice) return null;

  if (compact) {
    return <SyntheticDemoChip dataSource={dataSource ?? dataSources?.[0]} className={className} />;
  }

  return (
    <div
      className={[
        "rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]",
        className,
      ].filter(Boolean).join(" ")}
      role="note"
      aria-label={t("synthetic.bannerAria")}
    >
      <span className="font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
        {t("synthetic.bannerTitle")}
      </span>
      <span className="ml-2 font-medium text-[var(--text-primary)]">{notice}</span>
    </div>
  );
}
