"use client";

import type { SutPatientOutcomeData } from "@/lib/domains/sut";
import useStaggeredReveal from "@/hooks/useStaggeredReveal";
import { PatientSUTContent } from "./PatientSection";

export interface SUTAnalyticsProps {
  data: SutPatientOutcomeData | null;
  error: string | null;
  loading: boolean;
  selectedPatientId: string | null;
  onPatientSelect: (patientId: string) => void;
  onRetryOutcome: () => void;
}

export default function SUTAnalyticsShell({
  data,
  error,
  loading,
  selectedPatientId,
  onPatientSelect,
  onRetryOutcome,
}: SUTAnalyticsProps) {
  const reveal = useStaggeredReveal(5, { baseDelayMs: 40, stepMs: 140, threshold: 0.15 });

  return (
    <div className="relative space-y-6">
      <PatientSUTContent
        data={data}
        error={error}
        loading={loading}
        reveal={reveal}
        selectedPatientId={selectedPatientId}
        onPatientSelect={onPatientSelect}
        onRetry={onRetryOutcome}
      />
    </div>
  );
}
