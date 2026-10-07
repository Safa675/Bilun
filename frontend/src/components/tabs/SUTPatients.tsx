"use client";

import { useEffect, useState } from "react";
import { getSutPatients } from "@/lib/api/sut";
import type { PatientMeta } from "@/lib/domains/patient";
import CohortFilterBar from "@/components/cohort/CohortFilterBar";
import { useCohortPatientIds } from "@/hooks/useCohortFilter";
import SUTAnalyticsShell, { type SUTAnalyticsProps } from "./sut/SUTAnalyticsShell";

export type SUTPatientsProps = SUTAnalyticsProps;

export default function SUTPatients(props: SUTPatientsProps) {
  const [patientMeta, setPatientMeta] = useState<PatientMeta[]>([]);

  useEffect(() => {
    let cancelled = false;
    getSutPatients()
      .then((data) => {
        if (!cancelled) setPatientMeta(data.patient_meta ?? []);
      })
      .catch(() => {
        if (!cancelled) setPatientMeta([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const cohort = useCohortPatientIds(patientMeta);

  return (
    <div className="space-y-4">
      <CohortFilterBar
        matchedCount={cohort.count}
        totalCount={patientMeta.length}
        patients={patientMeta}
      />
      <SUTAnalyticsShell
        {...props}
        cohortPatientIds={cohort.ids}
        cohortFilterActive={cohort.isActive}
      />
    </div>
  );
}
