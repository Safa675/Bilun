"use client";

import { Suspense, useCallback, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import SutInlineAIPanel from "@/components/chat/SutInlineAIPanel";
import SutHealthPanel from "@/components/admin/SutHealthPanel";
import SutHowItWorksModal from "@/components/modals/SutHowItWorksModal";
import SutWorkspaceHeader from "@/components/shell/SutWorkspaceHeader";
import {
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
} from "@/lib/constants";
import { buildHomePageContext } from "@/lib/sutChatPageContext";
import { SUT_WORKSPACE_CHAT_SESSION_KEY } from "@/lib/sutChatSession";
import {
  SutAnalyticsShellSkeleton,
  SutOptimizerShellSkeleton,
} from "@/components/skeletons/SutSkeletons";
import { getHealthStatus } from "@/lib/api/health";
import { isSutAdminEnabled } from "@/lib/sutAdmin";
import {
  useAiDockPosition,
  useHealthStatus,
  useSetAiDockPosition,
  useSetHealthStatus,
  useSetShowAdmin,
  useSetShowHowItWorks,
  useSetSutChatSession,
  useShowAdmin,
  useShowHowItWorks,
  useSutChatSession,
} from "@/stores/index";

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
  const activeTab = parseSutHomeTab(searchParams.get("tab"));
  const isWorkspaceMode = true;
  const showHowItWorks = useShowHowItWorks();
  const setShowHowItWorks = useSetShowHowItWorks();
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  const showAdmin = useShowAdmin();
  const setShowAdmin = useSetShowAdmin();
  const healthStatus = useHealthStatus();
  const setHealthStatus = useSetHealthStatus();

  const handlePatientSelect = useCallback((patientId: string) => {
    router.push(buildSutPatientHref(patientId));
  }, [router]);

  useEffect(() => {
    setShowAdmin(isSutAdminEnabled(searchParams.get("admin")));
  }, [searchParams, setShowAdmin]);

  const activeMeta = SUT_HOME_TABS.find((tab) => tab.id === activeTab) ?? SUT_HOME_TABS[0];
  const chatSessionKey = SUT_WORKSPACE_CHAT_SESSION_KEY;
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

  useEffect(() => {
    if (!isWorkspaceMode || !showAdmin) {
      setHealthStatus(null);
      return;
    }

    let cancelled = false;
    const poll = () => {
      getHealthStatus()
        .then((status) => {
          if (!cancelled) {
            setHealthStatus(status);
          }
        })
        .catch((err) => {
          if (cancelled) {
            return;
          }
          console.warn("SUT health polling failed:", err);
          setHealthStatus(null);
        });
    };

    poll();
    const timer = window.setInterval(poll, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isWorkspaceMode, setHealthStatus, showAdmin]);

  return (
    <>
      <main id="main-content" className="sut-app-main">
        <section className={sectionClass}>
            <>
              <SutWorkspaceHeader />

              {showAdmin && (
                <SutHealthPanel healthStatus={healthStatus} />
              )}

              {chatDock === "center" && (
                <SutInlineAIPanel
                  activeTab={activeMeta.label}
                  pageContext={chatPageContext}
                  dock={chatDock}
                  onDockChange={setChatDock}
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
      {shouldRenderChat && chatDock !== "center" && (
        <SutInlineAIPanel
          activeTab={activeMeta.label}
          pageContext={chatPageContext}
          dock={chatDock}
          onDockChange={setChatDock}
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
        <SutWorkspaceHeader />
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
