"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import SutInlineAIPanel, { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import SutPatientWorkspace from "@/components/patient/SutPatientWorkspace";
import { SutPatientAnalyticsSkeleton } from "@/components/skeletons/SutSkeletons";
import PatientSearch from "@/components/ui/PatientSearch";
import { getPatientOptimization, getSutPatientOutcome, searchSutPatients } from "@/lib/api/sut";
import { buildSutHomeHref, buildSutPatientHref } from "@/lib/constants";
import type { PatientOptimization, SutPatientOutcomeData } from "@/lib/domains/sut";
import {
  useAiDockPosition,
  useSetAiDockPosition,
  useSetSutChatSession,
  useSutChatSession,
} from "@/stores/index";

export default function SutPatientPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const patientId = useMemo(
    () => decodeURIComponent(Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""),
    [params],
  );

  const [outcome, setOutcome] = useState<SutPatientOutcomeData | null>(null);
  const [optimization, setOptimization] = useState<PatientOptimization | null>(null);
  const [loading, setLoading] = useState(true);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  const outcomeControllerRef = useRef<AbortController | null>(null);
  const optimizationControllerRef = useRef<AbortController | null>(null);

  const loadWorkspace = useCallback((nextPatientId: string) => {
    outcomeControllerRef.current?.abort();
    optimizationControllerRef.current?.abort();

    const outcomeController = new AbortController();
    const optimizationController = new AbortController();
    outcomeControllerRef.current = outcomeController;
    optimizationControllerRef.current = optimizationController;

    setLoading(true);
    setOutcome(null);
    setOptimization(null);
    setOutcomeError(null);
    setOptimizationError(null);

    const outcomePromise = getSutPatientOutcome(nextPatientId, {
      signal: outcomeController.signal,
    });
    const optimizationPromise = getPatientOptimization(nextPatientId, {
      signal: optimizationController.signal,
    });

    void Promise.allSettled([outcomePromise, optimizationPromise]).then(([outcomeResult, optimizationResult]) => {
      if (outcomeController.signal.aborted || optimizationController.signal.aborted) {
        return;
      }

      if (outcomeResult.status === "fulfilled") {
        setOutcome(outcomeResult.value);
      } else {
        setOutcomeError(
          outcomeResult.reason instanceof Error
            ? outcomeResult.reason.message
            : "Failed to load patient SUT outcome.",
        );
      }

      if (optimizationResult.status === "fulfilled") {
        setOptimization(optimizationResult.value);
      } else {
        setOptimizationError(
          optimizationResult.reason instanceof Error
            ? optimizationResult.reason.message
            : "Failed to load patient optimization.",
        );
      }

      setLoading(false);
      outcomeControllerRef.current = null;
      optimizationControllerRef.current = null;
    });
  }, []);

  useEffect(() => {
    if (!patientId) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      loadWorkspace(patientId);
    }, 0);
    return () => {
      window.clearTimeout(timeoutId);
      outcomeControllerRef.current?.abort();
      optimizationControllerRef.current?.abort();
    };
  }, [loadWorkspace, patientId]);

  const handlePatientSelect = useCallback((selectedPatientId: string) => {
    router.push(buildSutPatientHref(selectedPatientId));
  }, [router]);

  const pageError = outcomeError && optimizationError
    ? `${outcomeError} ${optimizationError}`
    : outcomeError ?? optimizationError;
  const chatSessionKey = useMemo(() => `patient:${patientId}`, [patientId]);
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const shouldRenderChat = !loading && !(pageError && !outcome && !optimization);
  const chatShiftX = shouldRenderChat && chatDock !== "center"
    ? (chatDock === "left" ? SUT_INLINE_CHAT_PANEL_WIDTH / 2 : -(SUT_INLINE_CHAT_PANEL_WIDTH / 2))
    : 0;

  const dockPadding = shouldRenderChat && chatDock !== "center"
    ? { paddingLeft: `${SUT_INLINE_CHAT_PANEL_WIDTH / 2}px`, paddingRight: `${SUT_INLINE_CHAT_PANEL_WIDTH / 2}px` }
    : undefined;

  return (
    <>
      <main id="main-content" className="sut-app-main" style={dockPadding}>
        <div
          style={{
            transform: `translateX(${chatShiftX}px)`,
            transition: "transform 0.25s ease",
          }}
        >
          <section className="mx-auto max-w-7xl space-y-6">
            <div className="frost-panel sut-premium-glass sut-route-search-panel">
              <nav className="sut-breadcrumb mb-4" aria-label="SUT patient breadcrumb">
                <Link href={buildSutHomeHref("analytics")} className="sut-breadcrumb-link">
                  SUT workspace
                </Link>
                <span className="sut-breadcrumb-separator" aria-hidden="true">/</span>
                <span className="sut-breadcrumb-current">Patient {patientId || "unknown"}</span>
              </nav>
              <div className="sut-route-search-grid">
                <div className="sut-route-search-control">
                  <p className="sut-muted-label mb-2">
                    Patient search
                  </p>
                  <PatientSearch
                    id="sut-patient-workspace-search"
                    selectedPatientId={patientId || null}
                    onSelect={handlePatientSelect}
                    placeholder="Jump to a different patient workspace..."
                    searchFn={searchSutPatients}
                  />
                </div>
                <p className="sut-section-description max-w-2xl">
                  Patient selection now routes into the dedicated SUT workspace instead of loading inline on home.
                </p>
              </div>
            </div>

            {shouldRenderChat && chatDock === "center" && (
                <SutInlineAIPanel
                  patientId={patientId}
                  activeTab="SUT Patient Workspace"
                  dock={chatDock}
                  onDockChange={setChatDock}
                  chatState={chatState}
                  onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
                />
              )}

            {loading ? (
              <SutPatientAnalyticsSkeleton patientId={patientId} />
            ) : pageError && !outcome && !optimization ? (
              <div className="frost-panel sut-premium-error rounded-2xl p-6">
                <h1 className="sut-premium-error-title text-xl font-semibold">Patient workspace unavailable</h1>
                <p className="sut-premium-error-hint mt-3 text-sm leading-6">{pageError}</p>
              </div>
            ) : (
              <>
                {outcomeError && (
                  <div className="sut-premium-warn rounded-2xl px-4 py-3 text-sm">
                    {outcomeError}
                  </div>
                )}
                {optimizationError && (
                  <div className="sut-premium-warn rounded-2xl px-4 py-3 text-sm">
                    {optimizationError}
                  </div>
                )}
                <SutPatientWorkspace
                  patientId={patientId}
                  outcome={outcome}
                  optimization={optimization}
                />
              </>
            )}
          </section>
        </div>
      </main>
      {shouldRenderChat && chatDock !== "center" && (
        <SutInlineAIPanel
          patientId={patientId}
          activeTab="SUT Patient Workspace"
          dock={chatDock}
          onDockChange={setChatDock}
          chatState={chatState}
          onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
        />
      )}
    </>
  );
}
