"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import SutPatientWorkspace from "@/components/patient/SutPatientWorkspace";
import {
  BillingSummary,
  LabOptimizationSection,
  DrugOptimizationSection,
  CopayOptimizationSection,
  BillingStrategySection,
  MaterialsPreCheckSection,
  SutOptimizationSection,
} from "@/components/patient/SutBillingReportSections";
import { Eyebrow, Surface } from "@/components/primitives";
import { SutPatientAnalyticsSkeleton } from "@/components/skeletons/SutSkeletons";
import PatientSearch from "@/components/ui/PatientSearch";
import {
  getPatientBillingReport,
  getPatientOptimization,
  getSutPatientOutcome,
  searchSutPatients,
} from "@/lib/api/sut";
import { buildSutHomeHref, buildSutPatientHref } from "@/lib/constants";
import { recordRecent } from "@/lib/recents";
import type {
  BillingActionReport,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
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
  const [billingReport, setBillingReport] = useState<BillingActionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  const outcomeControllerRef = useRef<AbortController | null>(null);
  const optimizationControllerRef = useRef<AbortController | null>(null);
  const billingControllerRef = useRef<AbortController | null>(null);

  const loadWorkspace = useCallback((nextPatientId: string) => {
    outcomeControllerRef.current?.abort();
    optimizationControllerRef.current?.abort();
    billingControllerRef.current?.abort();

    const outcomeController = new AbortController();
    const optimizationController = new AbortController();
    const billingController = new AbortController();
    outcomeControllerRef.current = outcomeController;
    optimizationControllerRef.current = optimizationController;
    billingControllerRef.current = billingController;

    setLoading(true);
    setOutcome(null);
    setOptimization(null);
    setBillingReport(null);
    setOutcomeError(null);
    setOptimizationError(null);
    setBillingError(null);

    const outcomePromise = getSutPatientOutcome(nextPatientId, {
      signal: outcomeController.signal,
    });
    const optimizationPromise = getPatientOptimization(nextPatientId, {
      signal: optimizationController.signal,
    });
    const billingPromise = getPatientBillingReport(nextPatientId, {
      signal: billingController.signal,
    });

    void Promise.allSettled([outcomePromise, optimizationPromise, billingPromise]).then(
      ([outcomeResult, optimizationResult, billingResult]) => {
        if (
          outcomeController.signal.aborted ||
          optimizationController.signal.aborted ||
          billingController.signal.aborted
        ) {
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

        if (billingResult.status === "fulfilled") {
          setBillingReport(billingResult.value);
        } else {
          setBillingError(
            billingResult.reason instanceof Error
              ? billingResult.reason.message
              : "Failed to load patient billing report.",
          );
        }

        setLoading(false);
        outcomeControllerRef.current = null;
        optimizationControllerRef.current = null;
        billingControllerRef.current = null;
      },
    );
  }, []);

  useEffect(() => {
    if (!patientId) {
      return;
    }
    recordRecent("patient", patientId);
    const timeoutId = window.setTimeout(() => {
      loadWorkspace(patientId);
    }, 0);
    return () => {
      window.clearTimeout(timeoutId);
      outcomeControllerRef.current?.abort();
      optimizationControllerRef.current?.abort();
      billingControllerRef.current?.abort();
    };
  }, [loadWorkspace, patientId]);

  const handlePatientSelect = useCallback((selectedPatientId: string) => {
    router.push(buildSutPatientHref(selectedPatientId));
  }, [router]);

  const hasAnyData = Boolean(outcome) || Boolean(optimization) || Boolean(billingReport);
  const hasAnyError = Boolean(outcomeError) || Boolean(optimizationError) || Boolean(billingError);
  const allFailed = hasAnyError && !hasAnyData;
  const pageError = allFailed
    ? [outcomeError, optimizationError, billingError].filter(Boolean).join(" ")
    : null;

  const chatSessionKey = useMemo(() => `patient:${patientId}`, [patientId]);
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const shouldRenderChat = !loading && !allFailed;
  const isDocked = shouldRenderChat && chatDock !== "center";
  const sectionClass = isDocked
    ? "w-full space-y-6"
    : "mx-auto max-w-7xl space-y-6";

  return (
    <>
      <main id="main-content" className="sut-app-main">
        <section className={sectionClass}>
            <Surface variant="base" padding="lg">
              <nav
                aria-label="SUT patient breadcrumb"
                className="mb-4 flex flex-wrap items-center gap-2 text-xs font-medium text-[var(--text-muted)]"
              >
                <Link
                  href={buildSutHomeHref("analytics")}
                  className="text-[var(--text-secondary)] transition-colors hover:text-[var(--gold-hover)]"
                >
                  SUT workspace
                </Link>
                <span aria-hidden="true" className="text-[var(--border-strong)]">
                  /
                </span>
                <span className="text-[var(--text-primary)]">Patient {patientId || "unknown"}</span>
              </nav>
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-end">
                <div>
                  <Eyebrow className="mb-2">Patient search</Eyebrow>
                  <PatientSearch
                    id="sut-patient-workspace-search"
                    selectedPatientId={patientId || null}
                    onSelect={handlePatientSelect}
                    placeholder="Jump to a different patient workspace..."
                    searchFn={searchSutPatients}
                  />
                </div>
                <p className="text-sm leading-snug text-[var(--text-secondary)]">
                  Patient selection routes into the dedicated SUT workspace instead of loading inline on
                  home.
                </p>
              </div>
            </Surface>

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
            ) : allFailed ? (
              <Surface variant="base" padding="lg">
                <Eyebrow tone="primary" as="h1" className="text-base normal-case tracking-normal">
                  Billing Report unavailable
                </Eyebrow>
                <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{pageError}</p>
              </Surface>
            ) : (
              <>
                {hasAnyError && (
                  <Surface variant="soft" padding="md" className="text-sm text-[var(--text-secondary)]">
                    {outcomeError && <p>{outcomeError}</p>}
                    {optimizationError && <p>{optimizationError}</p>}
                    {billingError && <p>{billingError}</p>}
                  </Surface>
                )}
                <SutPatientWorkspace
                  patientId={patientId}
                  outcome={outcome}
                  optimization={optimization}
                />
                {billingReport && (
                  <>
                    <BillingSummary billingReport={billingReport} />
                    <LabOptimizationSection labData={billingReport.lab} />
                    <DrugOptimizationSection drugData={billingReport.drug} />
                    <CopayOptimizationSection copayData={billingReport.copay} />
                    <BillingStrategySection strategyData={billingReport.billing_strategy} />
                    <MaterialsPreCheckSection materialsData={billingReport.materials} />
                    {optimization && <SutOptimizationSection optimization={optimization} />}
                    <p className="py-2 text-center text-xs text-[var(--text-muted)]">
                      Normative analysis based on official SUT gazette rule references (EK-1A, EK-2B,
                      EK-2C, EK-4A)
                    </p>
                  </>
                )}
              </>
            )}
          </section>
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
