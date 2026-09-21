"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import SutHowItWorksModal from "@/components/modals/SutHowItWorksModal";
import ReportProblemModal from "@/components/feedback/ReportProblemModal";
import SutPatientWorkspace from "@/components/patient/SutPatientWorkspace";
import {
  BillingSummary,
  SutOptimizationSection,
} from "@/components/patient/SutBillingReportSections";
import PatientWorkspaceViews from "@/components/patient/views/PatientWorkspaceViews";
import { SutClauseDrawer } from "@/components/sut/SutClauseDrawer";
import BillPicker from "@/components/patient/BillPicker";
import { BillingReportGroup } from "@/components/patient/BillingReportGroup";
import OriginalBillView, { type HighlightCodeSet } from "@/components/patient/OriginalBillView";
import { Eyebrow, Surface } from "@/components/primitives";
import { SutPatientAnalyticsSkeleton } from "@/components/skeletons/SutSkeletons";
import PatientSearch from "@/components/ui/PatientSearch";
import {
  getBillBillingReport,
  getBillOptimization,
  getPatientBillingReport,
  getPatientClaimDetail,
  getPatientClaims,
  getPatientOptimization,
  getSutPatientOutcome,
  searchSutPatients,
} from "@/lib/api/sut";
import { buildSutHomeHref, buildSutPatientHref } from "@/lib/constants";
import {
  parsePatientWorkspaceQuery,
  resolvePatientScrollTarget,
} from "@/lib/patientRoute";
import {
  getRecommendedActions,
  recommendedActionLineCodes,
  recommendedActionSectionId,
  type RecommendedActionItem,
} from "@/lib/recommendedActions";
import { cn } from "@/lib/cn";
import { buildPatientWorkspacePageContext } from "@/lib/sutChatPageContext";
import { sutPatientChatSessionKey } from "@/lib/sutChatSession";
import { recordRecent } from "@/lib/recents";
import type {
  BillingActionReport,
  PatientClaimDetail,
  PatientClaimSummary,
  PatientOptimization,
  SutPatientOutcomeData,
} from "@/lib/domains/sut";
import {
  useAiDockPosition,
  useSetAiDockPosition,
  useSetShowHowItWorks,
  useSetShowReportProblem,
  useSetSutChatSession,
  useShowHowItWorks,
  useShowReportProblem,
  useSutChatSession,
  useWorkspacePaneBTabId,
} from "@/stores/index";
import { useT } from "@/lib/i18n/useTranslations";

export function SutPatientPageContent({
  patientId,
  embedded = false,
}: {
  patientId: string;
  embedded?: boolean;
}) {
  const t = useT();
  // Keep the latest `t` in a ref so fetch callbacks read a fresh translator
  // without re-creating themselves (and the effects that call them) on every
  // locale switch. Fixes locale-switch churn: C2, H1, M7.
  const tRef = useRef(t);
  tRef.current = t;
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    claimId: claimQuery,
    section: sectionQuery,
    findingId: findingQuery,
  } = parsePatientWorkspaceQuery(searchParams);

  const [outcome, setOutcome] = useState<SutPatientOutcomeData | null>(null);
  const [optimization, setOptimization] = useState<PatientOptimization | null>(null);
  const [billingReport, setBillingReport] = useState<BillingActionReport | null>(null);
  const [claims, setClaims] = useState<PatientClaimSummary[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [clauseKey, setClauseKey] = useState<string | null>(null);
  const [claimDetail, setClaimDetail] = useState<PatientClaimDetail | null>(null);
  const [claimsLoading, setClaimsLoading] = useState(false);
  const [claimsError, setClaimsError] = useState<string | null>(null);
  const [claimDetailLoading, setClaimDetailLoading] = useState(false);
  const [claimDetailError, setClaimDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  const showHowItWorks = useShowHowItWorks();
  const setShowHowItWorks = useSetShowHowItWorks();
  const showReportProblem = useShowReportProblem();
  const setShowReportProblem = useSetShowReportProblem();
  const outcomeControllerRef = useRef<AbortController | null>(null);
  const optimizationControllerRef = useRef<AbortController | null>(null);
  const billingControllerRef = useRef<AbortController | null>(null);
  const claimsControllerRef = useRef<AbortController | null>(null);
  const claimDetailControllerRef = useRef<AbortController | null>(null);
  const scopedControllerRef = useRef<AbortController | null>(null);

  const [billBillingReport, setBillBillingReport] = useState<BillingActionReport | null>(null);
  const [billOptimization, setBillOptimization] = useState<PatientOptimization | null>(null);
  const [scopedLoading, setScopedLoading] = useState(false);
  const [scopedBillingError, setScopedBillingError] = useState<string | null>(null);
  const [scopedOptimizationError, setScopedOptimizationError] = useState<string | null>(null);

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
              : tRef.current("patient.page.errors.outcome"),
          );
        }

        if (optimizationResult.status === "fulfilled") {
          setOptimization(optimizationResult.value);
        } else {
          setOptimizationError(
            optimizationResult.reason instanceof Error
              ? optimizationResult.reason.message
              : tRef.current("patient.page.errors.optimization"),
          );
        }

        if (billingResult.status === "fulfilled") {
          setBillingReport(billingResult.value);
        } else {
          setBillingError(
            billingResult.reason instanceof Error
              ? billingResult.reason.message
              : tRef.current("patient.page.errors.billing"),
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

  const loadClaims = useCallback((nextPatientId: string, initialClaimId?: string | null) => {
    claimsControllerRef.current?.abort();
    const controller = new AbortController();
    claimsControllerRef.current = controller;

    setClaimsLoading(true);
    setClaimsError(null);
    setClaims([]);
    setSelectedClaimId(null);
    setClaimDetail(null);

    getPatientClaims(nextPatientId, { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        setClaims(response.claims);
        const requestedClaim = initialClaimId
          ? response.claims.find((c) => c.claim_id === initialClaimId)?.claim_id ?? null
          : null;
        setSelectedClaimId(requestedClaim ?? null);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setClaimsError(
          reason instanceof Error ? reason.message : tRef.current("patient.page.errors.claims"),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setClaimsLoading(false);
          claimsControllerRef.current = null;
        }
      });
  }, []);

  const loadClaimDetail = useCallback((nextPatientId: string, claimId: string | null) => {
    claimDetailControllerRef.current?.abort();
    const controller = new AbortController();
    claimDetailControllerRef.current = controller;

    setClaimDetailLoading(true);
    setClaimDetailError(null);
    setClaimDetail(null);

    if (!claimId) {
      setClaimDetailLoading(false);
      claimDetailControllerRef.current = null;
      return;
    }

    getPatientClaimDetail(nextPatientId, claimId, { signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return;
        setClaimDetail(response);
      })
      .catch((reason) => {
        if (controller.signal.aborted) return;
        setClaimDetailError(
          reason instanceof Error ? reason.message : tRef.current("patient.page.errors.claims"),
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setClaimDetailLoading(false);
          claimDetailControllerRef.current = null;
        }
      });
  }, []);

  useEffect(() => {
    if (!patientId) {
      return;
    }
    loadClaims(patientId, claimQuery);
    return () => {
      claimsControllerRef.current?.abort();
    };
  }, [loadClaims, patientId, claimQuery]);

  useEffect(() => {
    if (!patientId) {
      return;
    }
    loadClaimDetail(patientId, selectedClaimId);
    return () => {
      claimDetailControllerRef.current?.abort();
    };
  }, [loadClaimDetail, patientId, selectedClaimId]);

  const loadScopedReports = useCallback(
    (nextPatientId: string, claimId: string | null) => {
      scopedControllerRef.current?.abort();

      if (!claimId) {
        setBillBillingReport(null);
        setBillOptimization(null);
        setScopedLoading(false);
        setScopedBillingError(null);
        setScopedOptimizationError(null);
        scopedControllerRef.current = null;
        return;
      }

      const controller = new AbortController();
      scopedControllerRef.current = controller;
      setScopedLoading(true);
      setScopedBillingError(null);
      setScopedOptimizationError(null);

      void Promise.allSettled([
        getBillBillingReport(nextPatientId, claimId, { signal: controller.signal }),
        getBillOptimization(nextPatientId, claimId, { signal: controller.signal }),
      ]).then(([billingResult, optimizationResult]) => {
        if (controller.signal.aborted) {
          return;
        }

        if (billingResult.status === "fulfilled") {
          setBillBillingReport(billingResult.value);
        } else {
          setScopedBillingError(
            billingResult.reason instanceof Error
              ? billingResult.reason.message
              : tRef.current("patient.page.errors.billing"),
          );
        }

        if (optimizationResult.status === "fulfilled") {
          setBillOptimization(optimizationResult.value);
        } else {
          setScopedOptimizationError(
            optimizationResult.reason instanceof Error
              ? optimizationResult.reason.message
              : tRef.current("patient.page.errors.optimization"),
          );
        }

        setScopedLoading(false);
        scopedControllerRef.current = null;
      });
    },
    [],
  );

  // Scoped (bill-level) reports are independent of the workspace fetch.
  // Do NOT gate on `loading` — loadScopedReports early-returns when
  // selectedClaimId is null, and aborts the previous run on re-entry.
  useEffect(() => {
    if (!patientId) {
      return;
    }
    loadScopedReports(patientId, selectedClaimId);
    return () => {
      scopedControllerRef.current?.abort();
    };
  }, [loadScopedReports, patientId, selectedClaimId]);

  const isBillScoped = selectedClaimId !== null;
  const activeBillingReport = isBillScoped ? billBillingReport : billingReport;

  const recommendedActions = useMemo(
    () => (activeBillingReport ? getRecommendedActions(activeBillingReport) : []),
    [activeBillingReport],
  );
  const selectedAction = useMemo(
    () => recommendedActions.find((action) => action.action_id === selectedActionId) ?? null,
    [recommendedActions, selectedActionId],
  );
  const highlightCodes = useMemo<HighlightCodeSet | null>(() => {
    if (!selectedAction) return null;
    const codes = recommendedActionLineCodes(selectedAction);
    return {
      procedures: new Set(codes.procedures),
      labs: new Set(codes.labs),
      materials: new Set(codes.materials),
      drugs: new Set(codes.drugs),
    };
  }, [selectedAction]);

  useEffect(() => {
    if ((!findingQuery && !sectionQuery) || !activeBillingReport) {
      return;
    }
    // Exact finding rows win over section anchors; schedule after the
    // workspace view switch so the target row is mounted before scrolling.
    const frame = requestAnimationFrame(() => {
      const target = resolvePatientScrollTarget(document, findingQuery, sectionQuery);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  }, [findingQuery, sectionQuery, activeBillingReport]);
  const activeOptimization = isBillScoped ? billOptimization : optimization;
  const selectedClaimSummary = useMemo(
    () => claims.find((claim) => claim.claim_id === selectedClaimId) ?? null,
    [claims, selectedClaimId],
  );

  const handleSelectClaim = useCallback(
    (claimId: string | null) => {
      setSelectedClaimId(claimId);
      setSelectedActionId(null);
      router.replace(
        buildSutPatientHref(patientId, {
          claimId: claimId ?? undefined,
          section: sectionQuery ?? undefined,
        }),
        { scroll: false },
      );
    },
    [patientId, router, sectionQuery],
  );

  const handleOpenClause = useCallback((nextClauseKey: string) => {
    setClauseKey(nextClauseKey);
  }, []);

  const handleCloseClause = useCallback(() => {
    setClauseKey(null);
  }, []);

  // Selecting a recommended action highlights matching invoice lines (S1) and
  // persists `?section=` so the URL is shareable and survives reload (S2).
  const handleSelectAction = useCallback(
    (action: RecommendedActionItem) => {
      setSelectedActionId(action.action_id);
      const sectionId = recommendedActionSectionId(action.surface);
      if (sectionId) {
        router.replace(
          buildSutPatientHref(patientId, {
            claimId: selectedClaimId ?? undefined,
            section: sectionId,
          }),
          { scroll: false },
        );
      }
    },
    [patientId, router, selectedClaimId],
  );

  const handlePatientSelect = useCallback((selectedPatientId: string) => {
    router.push(buildSutPatientHref(selectedPatientId));
  }, [router]);

  const hasAnyData = Boolean(outcome) || Boolean(optimization) || Boolean(billingReport);
  const hasAnyError = Boolean(outcomeError) || Boolean(optimizationError) || Boolean(billingError);
  const allFailed = hasAnyError && !hasAnyData;
  const pageError = allFailed
    ? [outcomeError, optimizationError, billingError].filter(Boolean).join(" ")
    : null;

  const chatSessionKey = sutPatientChatSessionKey(patientId);
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const handleChatStateChange = useCallback(
    (state: Parameters<typeof setChatSession>[1]) => {
      setChatSession(chatSessionKey, state);
    },
    [chatSessionKey, setChatSession],
  );
  const chatPageContext = useMemo(
    () =>
      buildPatientWorkspacePageContext({
        patientId,
        outcome,
        optimization: activeOptimization ?? optimization,
        billingReport: activeBillingReport ?? billingReport,
      }),
    [patientId, outcome, optimization, billingReport, activeOptimization, activeBillingReport],
  );
  const shouldRenderChat = !loading && !allFailed;
  const isDocked = shouldRenderChat && chatDock !== "center";
  const sectionClass =
    isDocked || embedded ? "w-full space-y-6" : "mx-auto max-w-7xl space-y-6";
  // Split view: dock controls are disabled and pane B renders no chat panel.
  const splitActive = useWorkspacePaneBTabId() !== null;
  const dockChange = splitActive ? undefined : setChatDock;
  const ShellTag = (embedded ? "div" : "main") as "div" | "main";

  return (
    <>
      <ShellTag id={embedded ? undefined : "main-content"} className="sut-app-main">
        <section className={sectionClass}>
            {!embedded && (
            <Surface variant="base" padding="lg">
              <nav
                aria-label={t("patient.page.breadcrumbAria")}
                className="mb-4 flex flex-wrap items-center gap-2 text-xs font-medium text-[var(--text-muted)]"
              >
                <Link
                  href={buildSutHomeHref("patients")}
                  className="text-[var(--text-secondary)] transition-colors hover:text-[var(--gold-hover)]"
                >
                  {t("patient.page.workspace")}
                </Link>
                <span aria-hidden="true" className="text-[var(--border-strong)]">
                  /
                </span>
                <span className="text-[var(--text-primary)]">
                  {patientId
                    ? t("patient.page.patient", { patientId })
                    : t("patient.page.patientUnknown")}
                </span>
              </nav>
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-end">
                <div>
                  <Eyebrow className="mb-2">{t("patient.page.searchEyebrow")}</Eyebrow>
                  <PatientSearch
                    id="sut-patient-workspace-search"
                    selectedPatientId={patientId || null}
                    onSelect={handlePatientSelect}
                    placeholder={t("patient.page.searchPlaceholder")}
                    searchFn={searchSutPatients}
                  />
                </div>
                <p className="text-sm leading-snug text-[var(--text-secondary)]">
                  {t("patient.page.searchDescription")}
                </p>
              </div>
            </Surface>
            )}

            {!embedded && shouldRenderChat && chatDock === "center" && (
              <SutInlineAIPanel
                patientId={patientId}
                activeTab="SUT Patient Workspace"
                pageContext={chatPageContext}
                dock={chatDock}
                onDockChange={dockChange}
                chatState={chatState}
                onChatStateChange={handleChatStateChange}
              />
            )}

            {loading ? (
              <SutPatientAnalyticsSkeleton patientId={patientId} />
            ) : allFailed ? (
              <Surface variant="base" padding="lg">
                <Eyebrow tone="primary" as="h1" className="text-base normal-case tracking-normal">
                  {t("patient.page.billingUnavailable")}
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
                  billingReport={activeBillingReport ?? billingReport}
                  selectedClaimId={selectedClaimId}
                  claimCount={claims.length > 0 ? claims.length : undefined}
                  selectedClaimSummary={selectedClaimSummary}
                />
                {(claims.length > 0 || claimsLoading || claimsError) && (
                  <Surface variant="base" padding="md">
                    {claimsError ? (
                      <p className="text-sm text-[var(--text-secondary)]">{claimsError}</p>
                    ) : (
                      <BillPicker
                        claims={claims}
                        selectedClaimId={selectedClaimId}
                        onSelectClaim={handleSelectClaim}
                        disabled={claimsLoading}
                      />
                    )}
                  </Surface>
                )}
                {claimDetailLoading && (
                  <Surface variant="soft" padding="md">
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t("patient.claimDetail.loading")}
                    </p>
                  </Surface>
                )}
                {claimDetailError && (
                  <Surface variant="soft" padding="md">
                    <p className="text-sm text-[var(--text-secondary)]">{claimDetailError}</p>
                  </Surface>
                )}
                {claimDetail && selectedClaimId && (
                  <OriginalBillView claim={claimDetail} highlightCodes={highlightCodes} />
                )}
                {(scopedBillingError || scopedOptimizationError) && (
                  <Surface variant="soft" padding="md" className="space-y-1 text-sm text-[var(--text-secondary)]">
                    {scopedBillingError && <p>{scopedBillingError}</p>}
                    {scopedOptimizationError && <p>{scopedOptimizationError}</p>}
                  </Surface>
                )}
                {!claimsLoading && activeBillingReport && (
                  <div
                    className={cn(
                      "space-y-4 transition-opacity duration-150",
                      scopedLoading && "pointer-events-none opacity-55",
                    )}
                  >
                    <Surface variant="soft" padding="md">
                      <p className="text-sm text-[var(--text-secondary)]">
                        {isBillScoped
                          ? t("billing.summary.scopeBill", {
                              claimId: selectedClaimId ?? "",
                              date: selectedClaimSummary?.claim_start_date ?? "",
                            })
                          : t("billing.summary.scopeAllBills")}
                      </p>
                      {scopedLoading ? (
                        <p className="mt-2 text-xs text-[var(--text-muted)]">
                          {t("billing.summary.scopedLoading")}
                        </p>
                      ) : null}
                    </Surface>

                    <BillingReportGroup
                      title={t("patient.billingGroups.overview")}
                      description={t("patient.billingGroups.overviewDescription")}
                    >
                      <BillingSummary billingReport={activeBillingReport} />
                    </BillingReportGroup>

                    <PatientWorkspaceViews
                      billingReport={activeBillingReport}
                      patientId={patientId}
                      selectedActionId={selectedActionId}
                      onSelectAction={handleSelectAction}
                      onOpenClause={handleOpenClause}
                      sectionQuery={sectionQuery}
                      selectedFindingId={findingQuery}
                    />

                    {activeOptimization && <SutOptimizationSection optimization={activeOptimization} />}
                    <p className="py-2 text-center text-xs text-[var(--text-muted)]">
                      {t("patient.page.footerNormative")}
                    </p>
                  </div>
                )}
              </>
            )}
          </section>
      </ShellTag>
      {!embedded && shouldRenderChat && chatDock !== "center" && (
        <SutInlineAIPanel
          patientId={patientId}
          activeTab="SUT Patient Workspace"
          pageContext={chatPageContext}
          dock={chatDock}
          onDockChange={dockChange}
          chatState={chatState}
          onChatStateChange={handleChatStateChange}
        />
      )}
      <SutClauseDrawer clauseKey={clauseKey} onClose={handleCloseClause} />
      {!embedded && (
        <>
          <SutHowItWorksModal open={showHowItWorks} onClose={() => setShowHowItWorks(false)} />
          <ReportProblemModal open={showReportProblem} onClose={() => setShowReportProblem(false)} />
        </>
      )}
    </>
  );
}

export default function SutPatientPage() {
  const params = useParams<{ id: string }>();
  // `useParams()` returns a fresh object every render, so useMemo on it never
  // caches. Decode directly — the resulting string is stable across renders.
  const patientId = decodeURIComponent(
    Array.isArray(params?.id) ? params.id[0] : params?.id ?? "",
  );
  return <SutPatientPageContent patientId={patientId} />;
}
