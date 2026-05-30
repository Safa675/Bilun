"use client";

import { useEffect, useMemo, useState } from "react";
import { Filter } from "lucide-react";
import { Chip, Eyebrow, Surface } from "@/components/primitives";
import { useCohortFilter } from "@/hooks/useCohortFilter";
import { fmtNum } from "@/components/tabs/sut/shared";
import {
  formatAgeRangeDisplay,
  formatPatientFilterLabel,
  parseAgeRangeInput,
} from "@/lib/cohortFilter";
import type { PatientMeta } from "@/lib/domains/patient";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";

interface CohortFilterBarProps {
  matchedCount: number | null;
  totalCount: number | null;
  patients?: PatientMeta[];
  className?: string;
}

export default function CohortFilterBar({
  matchedCount,
  totalCount,
  patients = [],
  className,
}: CohortFilterBarProps) {
  const t = useT();
  const { filter, isActive, setFilter, clearFilter } = useCohortFilter();
  const [doctorDraft, setDoctorDraft] = useState(filter.doctor);
  const [ageDraft, setAgeDraft] = useState(formatAgeRangeDisplay(filter));

  const sortedPatients = useMemo(
    () =>
      [...patients].sort((a, b) =>
        a.patient_id.localeCompare(b.patient_id, undefined, { numeric: true }),
      ),
    [patients],
  );

  const selectedPatientInList = sortedPatients.some(
    (patient) => patient.patient_id === filter.q,
  );

  useEffect(() => {
    setDoctorDraft(filter.doctor);
    setAgeDraft(formatAgeRangeDisplay(filter));
  }, [filter]);

  function commitAgeRange() {
    setFilter(parseAgeRangeInput(ageDraft));
  }

  return (
    <Surface variant="base" padding="md" className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow tone="muted" className="inline-flex items-center gap-1.5">
            <Filter className="h-3.5 w-3.5" aria-hidden="true" />
            {t("cohort.filterBar.eyebrow")}
          </Eyebrow>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {t("cohort.filterBar.description")}
          </p>
        </div>
        {matchedCount !== null && totalCount !== null && (
          <Chip variant={isActive ? "gold" : "neutral"}>
            {t("cohort.filterBar.matchedCount", {
              matched: fmtNum(matchedCount),
              total: fmtNum(totalCount),
            })}
          </Chip>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex min-w-[220px] flex-1 flex-col gap-1">
          <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            {t("cohort.filterBar.patientLabel")}
          </span>
          <select
            value={filter.q && (selectedPatientInList || filter.q) ? filter.q : ""}
            onChange={(event) => setFilter({ q: event.target.value })}
            disabled={sortedPatients.length === 0}
            className="sut-input app-select"
          >
            <option value="">
              {sortedPatients.length === 0
                ? t("cohort.filterBar.loadingPatients")
                : t("cohort.filterBar.allPatients")}
            </option>
            {filter.q && !selectedPatientInList && (
              <option value={filter.q}>{filter.q}</option>
            )}
            {sortedPatients.map((patient) => (
              <option key={patient.patient_id} value={patient.patient_id}>
                {formatPatientFilterLabel(patient)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex w-[120px] flex-col gap-1">
          <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            {t("cohort.filterBar.sexLabel")}
          </span>
          <select
            value={filter.sex}
            onChange={(event) =>
              setFilter({ sex: event.target.value as "" | "E" | "K" })
            }
            className="sut-input app-select"
          >
            <option value="">{t("cohort.filterBar.sexAll")}</option>
            <option value="E">{t("cohort.filterBar.sexE")}</option>
            <option value="K">{t("cohort.filterBar.sexK")}</option>
          </select>
        </label>

        <label className="flex w-[132px] flex-col gap-1">
          <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            {t("cohort.filterBar.ageLabel")}
          </span>
          <input
            type="text"
            inputMode="numeric"
            value={ageDraft}
            onChange={(event) => setAgeDraft(event.target.value)}
            onBlur={commitAgeRange}
            onKeyDown={(event) => {
              if (event.key === "Enter") commitAgeRange();
            }}
            placeholder={t("cohort.filterBar.agePlaceholder")}
            className="sut-input tabular-nums"
          />
        </label>

        <label className="flex min-w-[140px] flex-1 flex-col gap-1">
          <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            {t("cohort.filterBar.doctorCodeLabel")}
          </span>
          <input
            type="search"
            value={doctorDraft}
            onChange={(event) => setDoctorDraft(event.target.value)}
            onBlur={() => setFilter({ doctor: doctorDraft.trim() })}
            onKeyDown={(event) => {
              if (event.key === "Enter") setFilter({ doctor: doctorDraft.trim() });
            }}
            placeholder={t("cohort.filterBar.doctorPlaceholder")}
            className="sut-input"
          />
        </label>

        {isActive && (
          <button
            type="button"
            onClick={clearFilter}
            className="sut-section-btn sut-section-btn-compact mb-0.5"
          >
            {t("cohort.filterBar.clearFilters")}
          </button>
        )}
      </div>
    </Surface>
  );
}
