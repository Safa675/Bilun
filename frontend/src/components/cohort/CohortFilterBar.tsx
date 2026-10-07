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
      <label className="flex w-[250px] shrink-0 flex-col gap-1">
        <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          {t("cohort.filterBar.patientLabel")}
        </span>
        <select
          value={filter.q && (selectedPatientInList || filter.q) ? filter.q : ""}
          onChange={(event) => setFilter({ q: event.target.value })}
          disabled={sortedPatients.length === 0}
          className={cn(selectClass)}
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

      <label className="flex w-[148px] shrink-0 flex-col gap-1">
        <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
          {t("cohort.filterBar.sexLabel")}
        </span>
        <select
          value={filter.sex}
          onChange={(event) =>
            setFilter({ sex: event.target.value as "" | "E" | "K" })
          }
          className={cn(selectClass)}
        >
          <option value="">{t("cohort.filterBar.sexAll")}</option>
          <option value="E">{t("cohort.filterBar.sexE")}</option>
          <option value="K">{t("cohort.filterBar.sexK")}</option>
        </select>
      </label>

      <label className="flex w-[132px] shrink-0 flex-col gap-1">
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
          className={cn(inputClass, "tabular-nums")}
        />
      </label>

      <label className="flex w-[140px] shrink-0 flex-col gap-1">
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
          className={inputClass}
        />
      </label>

    </Toolbar>
  );
}
