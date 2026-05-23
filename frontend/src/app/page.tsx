"use client";

import { Suspense, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import { Info } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import SutInlineAIPanel, { SUT_INLINE_CHAT_PANEL_WIDTH } from "@/components/chat/SutInlineAIPanel";
import SutHealthPanel from "@/components/admin/SutHealthPanel";
import SutLandingHero from "@/components/home/SutLandingHero";
import SutHowItWorksModal from "@/components/modals/SutHowItWorksModal";
import {
  buildSutHomeHref,
  buildSutPatientHref,
  parseSutHomeTab,
  SUT_BRAND,
  SUT_HOME_TABS,
  type SutHomeTab,
} from "@/lib/constants";
import { shouldEnterSutWorkspace, SUT_WORKSPACE_STORAGE_KEY } from "@/lib/sutHomeShell";
import {
  SutAnalyticsShellSkeleton,
  SutOptimizerShellSkeleton,
} from "@/components/skeletons/SutSkeletons";
import { SyntheticDemoProvenance } from "@/components/sut/SyntheticDemoProvenance";
import { getHealthStatus } from "@/lib/api/health";
import { useConfig } from "@/lib/configContext";
import { isSutAdminEnabled } from "@/lib/sutAdmin";
import {
  useAiDockPosition,
  useHealthStatus,
  useSetAiDockPosition,
  useSetHealthStatus,
  useSetShowAdmin,
  useSetShowHowItWorks,
  useSetSutChatSession,
  useSetWorkspaceEntered,
  useShowAdmin,
  useShowHowItWorks,
  useSutChatSession,
  useWorkspaceEntered,
} from "@/stores/index";

const SUTAnalytics = dynamic(() => import("@/components/tabs/SUTAnalytics"), {
  loading: () => <SutAnalyticsShellSkeleton />,
});
const SUTOptimizer = dynamic(() => import("@/components/tabs/SUTOptimizer"), {
  loading: () => <SutOptimizerShellSkeleton />,
});

function SutHomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeTab = parseSutHomeTab(searchParams.get("tab"));
  const enteredWorkspace = useWorkspaceEntered();
  const setWorkspaceEntered = useSetWorkspaceEntered();
  const showHowItWorks = useShowHowItWorks();
  const setShowHowItWorks = useSetShowHowItWorks();
  const chatDock = useAiDockPosition();
  const setChatDock = useSetAiDockPosition();
  const showAdmin = useShowAdmin();
  const setShowAdmin = useSetShowAdmin();
  const healthStatus = useHealthStatus();
  const setHealthStatus = useSetHealthStatus();
  const config = useConfig();
  const sutDataSource = config.sut_data_source ?? config.sutDataSource ?? null;

  const navigateToTab = useCallback((tabId: SutHomeTab) => {
    router.push(buildSutHomeHref(tabId), { scroll: false });
  }, [router]);

  const handlePatientSelect = useCallback((patientId: string) => {
    router.push(buildSutPatientHref(patientId));
  }, [router]);

  const handleTabChange = useCallback((tabId: SutHomeTab) => {
    navigateToTab(tabId);
  }, [navigateToTab]);

  useEffect(() => {
    setShowAdmin(isSutAdminEnabled(searchParams.get("admin")));
  }, [searchParams, setShowAdmin]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const frameId = window.requestAnimationFrame(() => {
      setWorkspaceEntered(
        shouldEnterSutWorkspace(
          searchParams.get("tab"),
          window.localStorage.getItem(SUT_WORKSPACE_STORAGE_KEY),
        ),
      );
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [searchParams, setWorkspaceEntered]);

  const enterWorkspace = useCallback(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SUT_WORKSPACE_STORAGE_KEY, "1");
    }
    setWorkspaceEntered(true);
    navigateToTab(activeTab);
  }, [activeTab, navigateToTab, setWorkspaceEntered]);

  const activeMeta = SUT_HOME_TABS.find((tab) => tab.id === activeTab) ?? SUT_HOME_TABS[0];
  const chatSessionKey = `home:${activeMeta.label}`;
  const chatState = useSutChatSession(chatSessionKey);
  const setChatSession = useSetSutChatSession();
  const shouldRenderChat = enteredWorkspace;
  const chatShiftX = shouldRenderChat && chatDock !== "center"
    ? (chatDock === "left" ? SUT_INLINE_CHAT_PANEL_WIDTH / 2 : -(SUT_INLINE_CHAT_PANEL_WIDTH / 2))
    : 0;

  const dockPadding = shouldRenderChat && chatDock !== "center"
    ? { paddingLeft: `${SUT_INLINE_CHAT_PANEL_WIDTH / 2}px`, paddingRight: `${SUT_INLINE_CHAT_PANEL_WIDTH / 2}px` }
    : undefined;

  useEffect(() => {
    if (!enteredWorkspace || !showAdmin) {
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
  }, [enteredWorkspace, setHealthStatus, showAdmin]);

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
            {!enteredWorkspace ? (
              <SutLandingHero
                onEnter={enterWorkspace}
                onOpenHowItWorks={() => setShowHowItWorks(true)}
                dataSource={sutDataSource}
              />
            ) : (
              <>
                <header className="frost-panel sut-premium-panel sut-home-header sut-premium-enter">
                  <div className="sut-home-header-layout">
                    <div className="sut-home-header-copy">
                      <p className="sut-premium-eyebrow">
                        {SUT_BRAND.moduleLabel}
                      </p>
                      <h1 className="sut-app-title mt-3">{SUT_BRAND.heroTitle}</h1>
                      <p className="sut-premium-subtitle mt-2 max-w-3xl">
                        {SUT_BRAND.heroDescription}
                      </p>
                      <SyntheticDemoProvenance dataSource={sutDataSource} className="mt-4" />
                    </div>
                    <div className="sut-home-nav-shell">
                      <div className="sut-home-nav-tabs" role="tablist" aria-label="SUT workspace tabs">
                        {SUT_HOME_TABS.map((tab) => (
                          <button
                            key={tab.id}
                            type="button"
                            onClick={() => handleTabChange(tab.id)}
                            role="tab"
                            aria-selected={activeTab === tab.id}
                            className={`sut-home-nav-tab ${activeTab === tab.id ? "sut-home-nav-tab-active" : ""}`}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowHowItWorks(true)}
                        className="sut-home-info-link"
                      >
                        <Info className="h-3.5 w-3.5" aria-hidden="true" />
                        How It Works
                      </button>
                    </div>
                  </div>
                  <div className="sut-home-tab-context">
                    <p className="sut-muted-label">{activeMeta.label}</p>
                    <p className="sut-section-description mt-1">{activeMeta.subtitle}</p>
                  </div>
                </header>

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
                ) : (
                  <SUTOptimizer />
                )}
              </>
            )}
          </section>
        </div>
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
        <header className="frost-panel sut-premium-panel sut-home-header">
          <p className="sut-premium-eyebrow">
            {SUT_BRAND.moduleLabel}
          </p>
          <div className="mt-3">
            <h1 className="sut-app-title">{SUT_BRAND.heroTitle}</h1>
            <p className="sut-premium-subtitle mt-2 max-w-3xl">
              {SUT_BRAND.heroDescription}
            </p>
          </div>
          <div className="sut-home-tab-context">
            <p className="sut-muted-label">
            {SUT_HOME_TABS[0].label}
            </p>
            <p className="sut-section-description mt-1">{SUT_HOME_TABS[0].subtitle}</p>
          </div>
        </header>
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
