"use client";

import { useEffect, useState } from "react";
import { getSutPatients } from "@/lib/api/sut";
import type { PatientMeta } from "@/lib/domains/patient";
import CohortFilterBar from "@/components/cohort/CohortFilterBar";
import { useCohortPatientIds } from "@/hooks/useCohortFilter";
import { SUTRevenueTab } from "./sut/optimizer/SUTOptimizerTab";

export default function SUTRevenue() {
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
    <div className="space-y-6">
      <CohortFilterBar
        matchedCount={cohort.count}
        totalCount={patientMeta.length}
        patients={patientMeta}
      />
      <SUTRevenueTab
        cohortPatientIds={cohort.ids}
        cohortFilterActive={cohort.isActive}
      />
    </div>
  );
}
