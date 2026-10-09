"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Chip, Toolbar, inputClass, selectClass } from "@/components/primitives";
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

  const selectedPatient = sortedPatients.find(
    (patient) => patient.patient_id === filter.q,
  );
  const selectedPatientInList = selectedPatient !== undefined;

  useEffect(() => {
    setDoctorDraft(filter.doctor);
    setAgeDraft(formatAgeRangeDisplay(filter));
  }, [filter]);

  function commitAgeRange() {
    setFilter(parseAgeRangeInput(ageDraft));
  }

  // The closed select must show a chosen patient whole. Measured in Chrome (pixel compare): the widest Turkish
  // label of the synthetic cohort ("SENTETIK-HASTA-0032 · 44 yaş · K", 239 px of text) is cut below about 288 px
  // with pr-3 and below about 310 px with the default pr-8, because the native arrow reserves room of its own.
  // 310 px with pr-3 leaves about 22 px to spare. The sex, age and doctor widths are trimmed so the whole row,
  // with the clear button and the chip, still fits one line at 1280 px. Below 640 px the select takes the whole row:
  // a fixed 310 px made the page scroll sideways at 390 px (measured by the phase-1 capture, 20 states).
  return (
    <Toolbar
      role="group"
      aria-label={t("cohort.filterBar.eyebrow")}
      className={cn("py-2", className)}
      trailing={
        <>
          {isActive && (
            <Button variant="secondary" size="compact" onClick={clearFilter}>
              {t("cohort.filterBar.clearFilters")}
            </Button>
          )}
          {/* totalCount 0 is "not loaded yet" or "the list failed", never a real cohort size: no "0 of 0 patients" */}
          {matchedCount !== null && totalCount !== null && totalCount > 0 && (
            <Chip variant={isActive ? "gold" : "neutral"}>
              {t("cohort.filterBar.matchedCount", {
                matched: fmtNum(matchedCount),
                total: fmtNum(totalCount),
              })}
            </Chip>
          )}
        </>
      }
    >
      <label className="flex w-full shrink-0 flex-col gap-1 sm:w-[310px]">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          {t("cohort.filterBar.patientLabel")}
        </span>
        <select
          value={filter.q && (selectedPatientInList || filter.q) ? filter.q : ""}
          onChange={(event) => setFilter({ q: event.target.value })}
          disabled={sortedPatients.length === 0}
          title={selectedPatient ? formatPatientFilterLabel(selectedPatient) : filter.q || undefined}
          className={cn(selectClass, "pr-3")}
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

      <label className="flex w-[116px] shrink-0 flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          {t("cohort.filterBar.sexLabel")}
        </span>
        <select
          value={filter.sex}
          onChange={(event) =>
            setFilter({ sex: event.target.value as "" | "E" | "K" })
          }
          className={cn(selectClass, "min-w-0")}
        >
          <option value="">{t("cohort.filterBar.sexAll")}</option>
          <option value="E">{t("cohort.filterBar.sexE")}</option>
          <option value="K">{t("cohort.filterBar.sexK")}</option>
        </select>
      </label>

      <label className="flex w-[112px] shrink-0 flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
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
          className={cn(inputClass, "tabular-nums")}
        />
      </label>

      <label className="flex w-[120px] shrink-0 flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
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
          className={inputClass}
        />
      </label>

    </Toolbar>
  );
}
