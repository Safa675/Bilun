"use client";

import { Suspense, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import SutInlineAIPanel, { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import SutHealthPanel from "@/components/admin/SutHealthPanel";
import SutHowItWorksModal from "@/components/modals/SutHowItWorksModal";
import SutWorkspaceHeader from "@/components/shell/SutWorkspaceHeader";
import {
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
} from "@/lib/constants";
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

const SUTAnalytics = dynamic(() => import("@/components/tabs/SUTAnalytics"), {
  loading: () => <SutAnalyticsShellSkeleton />,
});
const SUTOptimizer = dynamic(() => import("@/components/tabs/SUTOptimizer"), {
  loading: () => <SutOptimizerShellSkeleton />,
});
const SUTReferenceTools = dynamic(() => import("@/components/tabs/SUTReferenceTools"), {
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
  const chatSessionKey = `home:${activeMeta.label}`;
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const shouldRenderChat = isWorkspaceMode;
  const CHAT_DOCK_MARGIN = 32;
  const dockOffset = SUT_INLINE_CHAT_PANEL_WIDTH + CHAT_DOCK_MARGIN;
  const isDocked = shouldRenderChat && chatDock !== "center";
  const dockPadding = isDocked
    ? chatDock === "left"
      ? { paddingLeft: `${dockOffset}px`, paddingRight: "1.5rem" }
      : { paddingRight: `${dockOffset}px`, paddingLeft: "1.5rem" }
    : undefined;
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
      <main id="main-content" className="sut-app-main" style={dockPadding}>
        <section className={sectionClass}>
            <>
              <SutWorkspaceHeader />

              {showAdmin && (
                <SutHealthPanel healthStatus={healthStatus} />
              )}

              {chatDock === "center" && (
                <SutInlineAIPanel
                  activeTab={activeMeta.label}
                  dock={chatDock}
                  onDockChange={setChatDock}
                  chatState={chatState}
                  onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
                />
              )}

              {activeTab === "analytics" ? (
                <SUTAnalytics
                  data={null}
                  error={null}
                  loading={false}
                  selectedPatientId={null}
                  onPatientSelect={handlePatientSelect}
                  onRetryOutcome={() => undefined}
                />
              ) : activeTab === "reference-tools" ? (
                <SUTReferenceTools />
              ) : (
                <SUTOptimizer />
              )}
            </>
          </section>
      </main>
      <SutHowItWorksModal open={showHowItWorks} onClose={() => setShowHowItWorks(false)} />
      {shouldRenderChat && chatDock !== "center" && (
        <SutInlineAIPanel
          activeTab={activeMeta.label}
          dock={chatDock}
          onDockChange={setChatDock}
          chatState={chatState}
          onChatStateChange={(state) => setChatSession(chatSessionKey, state)}
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
