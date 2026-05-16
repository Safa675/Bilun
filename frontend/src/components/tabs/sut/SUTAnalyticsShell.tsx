"use client";

import { useState } from "react";
import { BookOpenText, Users } from "lucide-react";
import type { SutPatientOutcomeData } from "@/lib/domains/sut";
import useStaggeredReveal from "@/hooks/useStaggeredReveal";
import { PatientSUTContent } from "./PatientSection";
import { ReferenceToolsContent } from "./ToolsSection";

export interface SUTAnalyticsProps {
  data: SutPatientOutcomeData | null;
  error: string | null;
  loading: boolean;
  selectedPatientId: string | null;
  onPatientSelect: (patientId: string) => void;
  onRetryOutcome: () => void;
}

type SubtabId = "patient" | "tools";

const SUBTAB_META: { id: SubtabId; label: string; Icon: typeof Users }[] = [
  { id: "patient", label: "Patient SUT", Icon: Users },
  { id: "tools", label: "Reference Tools", Icon: BookOpenText },
];

export default function SUTAnalyticsShell({
  data,
  error,
  loading,
  selectedPatientId,
  onPatientSelect,
  onRetryOutcome,
}: SUTAnalyticsProps) {
  const [activeSubtab, setActiveSubtab] = useState<SubtabId>("patient");
  const reveal = useStaggeredReveal(5, { baseDelayMs: 40, stepMs: 140, threshold: 0.15 });

  return (
    <div className="relative space-y-6">
      <div className="sut-section-bar">
        {SUBTAB_META.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveSubtab(tab.id)}
            className={`sut-section-btn ${activeSubtab === tab.id ? "sut-section-btn-active" : ""}`}
          >
            <tab.Icon className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden="true" />
            <span className="text-sm font-semibold">{tab.label}</span>
          </button>
        ))}
      </div>

      {activeSubtab === "patient" && (
        <PatientSUTContent
          data={data}
          error={error}
          loading={loading}
          reveal={reveal}
          selectedPatientId={selectedPatientId}
          onPatientSelect={onPatientSelect}
          onRetry={onRetryOutcome}
        />
      )}
      {activeSubtab === "tools" && <ReferenceToolsContent />}
    </div>
  );
}
