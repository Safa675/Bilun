"use client";

import { Suspense, useCallback, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import SutHealthPanel from "@/components/admin/SutHealthPanel";
import SutHowItWorksModal from "@/components/modals/SutHowItWorksModal";
import ReportProblemModal from "@/components/feedback/ReportProblemModal";
import {
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
} from "@/lib/constants";
import { buildHomePageContext } from "@/lib/sutChatPageContext";
import { sutWorkspaceChatSessionKey } from "@/lib/sutChatSession";
import {
  SutAnalyticsShellSkeleton,
  SutOptimizerShellSkeleton,
} from "@/components/skeletons/SutSkeletons";
import { useHealthPolling } from "@/components/admin/useHealthPolling";
import { isSutAdminEnabled } from "@/lib/sutAdmin";
import {
  useAiDockPosition,
  useHealthStatus,
  useSetAiDockPosition,
  useSetHealthStatus,
  useSetShowAdmin,
  useSetShowHowItWorks,
  useSetShowReportProblem,
  useSetSutChatSession,
  useShowAdmin,
  useShowHowItWorks,
  useShowReportProblem,
  useSutChatSession,
  useWorkspacePaneBTabId,
} from "@/stores/index";
import { useT } from "@/lib/i18n";
import { useSessionIdentity } from "@/components/shell/RoleProvider";
import { canUseDeveloper, requestsDeveloper } from "@/lib/auth";

const SUTPatients = dynamic(() => import("@/components/tabs/SUTPatients"), {
  loading: () => <SutAnalyticsShellSkeleton />,
});
const SUTCompliance = dynamic(() => import("@/components/tabs/SUTCompliance"), {
  loading: () => <SutOptimizerShellSkeleton />,
});
const SUTRevenue = dynamic(() => import("@/components/tabs/SUTRevenue"), {
  loading: () => <SutOptimizerShellSkeleton />,
});
const SUTOperations = dynamic(() => import("@/components/tabs/sut/operations/SUTOperationsTab"), {
  loading: () => <SutOptimizerShellSkeleton />,
});
const SUTReferenceTools = dynamic(() => import("@/components/tabs/SUTReferenceTools"), {
  loading: () => <SutOptimizerShellSkeleton />,
});
const SUTRuleDatabase = dynamic(() => import("@/components/tabs/SUTRuleDatabase"), {
  loading: () => <SutOptimizerShellSkeleton />,
});

function SutHomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const t = useT();
  const developer = canUseDeveloper(useSessionIdentity());
  const denied = requestsDeveloper("/", searchParams) && !developer;
  const activeTab = parseSutHomeTab(searchParams.get("tab"));
  const isWorkspaceMode = true;
  const showHowItWorks = useShowHowItWorks();
  const setShowHowItWorks = useSetShowHowItWorks();
  const showReportProblem = useShowReportProblem();
  const setShowReportProblem = useSetShowReportProblem();
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  // Split view disables chat docking (v1 scope).
  const splitActive = useWorkspacePaneBTabId() !== null;
  const dockChange = splitActive ? undefined : setChatDock;
  const showAdmin = useShowAdmin();
  const setShowAdmin = useSetShowAdmin();
  const healthStatus = useHealthStatus();
  const setHealthStatus = useSetHealthStatus();

  const handlePatientSelect = useCallback((patientId: string) => {
    router.push(buildSutPatientHref(patientId));
  }, [router]);

  useEffect(() => {
    setShowAdmin(isSutAdminEnabled(searchParams.get("admin"), developer));
    if (denied) router.replace("/login?access=developer");
  }, [searchParams, setShowAdmin, developer, denied, router]);

  const activeMeta = SUT_HOME_TABS.find((tab) => tab.id === activeTab) ?? SUT_HOME_TABS[0];
  const activeTabCatalogKey =
    activeMeta.id === "reference-tools"
      ? "referenceTools"
      : activeMeta.id === "rule-database"
        ? "ruleDatabase"
        : activeMeta.id;
  const activeTabLabel = t(`constants.homeTabs.${activeTabCatalogKey}.label`);
  const chatSessionKey = sutWorkspaceChatSessionKey(activeTab);
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const handleChatStateChange = useCallback(
    (state: Parameters<typeof setChatSession>[1]) => {
      setChatSession(chatSessionKey, state);
    },
    [chatSessionKey, setChatSession],
  );
  const shouldRenderChat = isWorkspaceMode;
  const chatPageContext = useMemo(() => buildHomePageContext(activeTab), [activeTab]);
  const isDocked = shouldRenderChat && chatDock !== "center";
  const sectionClass = isDocked
    ? "w-full space-y-6"
    : "mx-auto max-w-7xl space-y-6";

  useHealthPolling(isWorkspaceMode && showAdmin && developer, setHealthStatus);

  if (denied) return null;

  return (
    <>
      <main id="main-content" className="sut-app-main">
        <section className={sectionClass}>
            <>
              {developer && showAdmin && (
                <SutHealthPanel healthStatus={healthStatus} />
              )}

              {chatDock === "center" && (
                <SutInlineAIPanel
                  activeTab={activeTabLabel}
                  pageContext={chatPageContext}
                  dock={chatDock}
                  onDockChange={dockChange}
                  chatState={chatState}
                  onChatStateChange={handleChatStateChange}
                />
              )}

              {activeTab === "patients" ? (
                <SUTPatients
                  data={null}
                  error={null}
                  loading={false}
                  selectedPatientId={null}
                  onPatientSelect={handlePatientSelect}
                  onRetryOutcome={() => undefined}
                />
              ) : activeTab === "compliance" ? (
                <SUTCompliance />
              ) : activeTab === "revenue" ? (
                <SUTRevenue />
              ) : activeTab === "operations" ? (
                <SUTOperations />
              ) : activeTab === "reference-tools" ? (
                <SUTReferenceTools />
              ) : (
                <SUTRuleDatabase />
              )}
            </>
          </section>
      </main>
      <SutHowItWorksModal open={showHowItWorks} onClose={() => setShowHowItWorks(false)} />
      <ReportProblemModal open={showReportProblem} onClose={() => setShowReportProblem(false)} />
      {shouldRenderChat && chatDock !== "center" && (
        <SutInlineAIPanel
          activeTab={activeTabLabel}
          pageContext={chatPageContext}
          dock={chatDock}
          onDockChange={dockChange}
          chatState={chatState}
          onChatStateChange={handleChatStateChange}
        />
      )}
    </>
  );
}

function SutHomeFallback() {
  return (
    <main id="main-content" className="sut-app-main">
      <section className="mx-auto max-w-7xl space-y-6">
        <SutAnalyticsShellSkeleton />
      </section>
    </main>
  );
}

export default function SutHome() {
  return (
    <Suspense fallback={<SutHomeFallback />}>
      <SutHomeContent />
    </Suspense>
  );
}
