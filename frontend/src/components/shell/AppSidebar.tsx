"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  CircleHelp,
  LogOut,
  MessageSquareWarning,
  PanelLeft,
  PanelLeftClose,
  X,
} from "lucide-react";
import BilunWordmark from "@/components/brand/BilunWordmark";
import { SyntheticDemoChip } from "@/components/sut/SyntheticDemoProvenance";
import LocaleSwitcher from "@/components/shell/LocaleSwitcher";
import RoleSwitcher from "@/components/shell/RoleSwitcher";
import { useConfig } from "@/lib/configContext";
import { cn } from "@/lib/cn";
import {
  buildSutHomeHref,
  parseSutHomeTab,
  SUT_HOME_TABS,
  type SutHomeTab,
} from "@/lib/constants";
import { useT } from "@/lib/i18n/useTranslations";
import {
  useNavigationStoreApi,
  useSetShowHowItWorks,
  useSetShowReportProblem,
} from "@/stores/index";
import { getMedulaRejectionIngestStatus } from "@/lib/api/sut";
import { useSessionIdentity, useUserRole } from "@/components/shell/RoleProvider";
import { endSession } from "@/lib/api/auth";
import { announceSessionChange, clearProtectedBrowserState } from "@/lib/authBrowser";
import { readChatDock } from "@/lib/chatDockPreference";
import {
  readSidebarCollapsed,
  sidebarWidthPx,
  writeSidebarCollapsed,
} from "@/lib/shellSidebar";
import { MAIN_SECTION_ICONS, tabMessageKey } from "@/lib/workspaceSubtabs";
import { usePhoneOverlayFocus } from "@/lib/usePhoneOverlayFocus";

interface AppSidebarProps {
  /** Optional override; defaults to wiring the global `showHowItWorks` store. */
  onOpenHowItWorks?: () => void;
  className?: string;
}

function useActiveHomeTab(): SutHomeTab {
  const searchParams = useSearchParams();
  return parseSutHomeTab(searchParams.get("tab"));
}

export default function AppSidebar({ onOpenHowItWorks, className }: AppSidebarProps) {
  const t = useT();
  const pathname = usePathname();
  const setShowHowItWorks = useSetShowHowItWorks();
  const setShowReportProblem = useSetShowReportProblem();
  const config = useConfig();
  const searchParams = useSearchParams();
  const sutDataSource = config.sut_data_source ?? config.sutDataSource ?? null;
  const activeTab = useActiveHomeTab();
  const userRole = useUserRole();
  const identity = useSessionIdentity();
  const [logoutError, setLogoutError] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [medulaIngestAvailable, setMedulaIngestAvailable] = useState<boolean | null>(null);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [narrowScreen, setNarrowScreen] = useState(false);
  const navigationKey = `${pathname}?${searchParams.toString()}`;
  const [mobileNavigation, setMobileNavigation] = useState<string | null>(null);
  const mobileExpanded = mobileNavigation === navigationKey;
  const collapsed = narrowScreen ? false : desktopCollapsed;
  const hideShell = pathname === "/login";
  const navigationStore = useNavigationStoreApi();
  const sidebarRef = useRef<HTMLElement>(null);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);
  const skipInitialPreferenceWrite = useRef(true);
  usePhoneOverlayFocus(narrowScreen && mobileExpanded, sidebarRef, () => setMobileNavigation(null), () => mobileTriggerRef.current);

  useEffect(() => {
    if (hideShell) return;
    return navigationStore.subscribe((state, prevState) => {
      if (state.aiDockPosition === "right" && prevState.aiDockPosition !== "right") {
        setDesktopCollapsed(true);
        setMobileNavigation(null);
      }
    });
  }, [hideShell, navigationStore]);

  // Mount-only read; synchronously initialize sidebar state and width before paint.
  useLayoutEffect(() => {
    const initiallyNarrow = window.matchMedia("(max-width: 640px)").matches;
    // The saved dock is read directly: the provider applies it to the store in a later layout effect.
    const initialDesktopCollapsed = readSidebarCollapsed() || readChatDock() === "right";
    setNarrowScreen(initiallyNarrow);
    setDesktopCollapsed(initialDesktopCollapsed);
    if (!hideShell) {
      document.documentElement.style.setProperty(
        "--shell-sidebar-width",
        initiallyNarrow ? "0px" : `${sidebarWidthPx(initialDesktopCollapsed)}px`,
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional mount-only read
  }, []);

  useEffect(() => {
    const narrowScreen = window.matchMedia("(max-width: 640px)");
    const updateNarrowScreen = (event: MediaQueryListEvent) => {
      setNarrowScreen(event.matches);
      if (event.matches) setMobileNavigation(null);
    };
    narrowScreen.addEventListener("change", updateNarrowScreen);
    return () => narrowScreen.removeEventListener("change", updateNarrowScreen);
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    if (hideShell) {
      root.style.setProperty("--shell-sidebar-width", "0px");
      return;
    }
    const phone = narrowScreen || window.matchMedia("(max-width: 640px)").matches;
    const width = phone ? "0px" : `${sidebarWidthPx(collapsed)}px`;
    root.style.setProperty("--shell-sidebar-width", width);
  }, [collapsed, hideShell, narrowScreen]);

  useEffect(() => {
    if (hideShell) return;
    if (skipInitialPreferenceWrite.current) {
      skipInitialPreferenceWrite.current = false;
      return;
    }
    writeSidebarCollapsed(desktopCollapsed);
  }, [desktopCollapsed, hideShell]);

  useEffect(() => {
    if (hideShell) return;
    const controller = new AbortController();
    let cancelled = false;

    const poll = () => {
      getMedulaRejectionIngestStatus()
        .then((status) => {
          if (!cancelled) {
            setMedulaIngestAvailable(status.ingest_available);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setMedulaIngestAvailable(false);
          }
        });
    };

    poll();
    const timer = window.setInterval(poll, 30_000);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(timer);
    };
  }, [hideShell]);

  if (hideShell) {
    return null;
  }

  const visibleTabs = SUT_HOME_TABS.filter((tab) => {
    if (tab.id !== "operations") return true;
    if (activeTab === "operations") return true;
    return medulaIngestAvailable === true;
  }).filter((tab) => {
    if (!tab.requiredRole) return true;
    return tab.requiredRole.includes(userRole);
  });

  const handleOpenHowItWorks = () => {
    if (onOpenHowItWorks) {
      onOpenHowItWorks();
      return;
    }
    setShowHowItWorks(true);
  };

  async function handleLogout() {
    setLogoutError(false);
    setLoggingOut(true);
    try {
      const next = await endSession();
      clearProtectedBrowserState();
      announceSessionChange();
      window.location.replace(next.public_billing_enabled ? "/" : "/login");
    } catch {
      setLogoutError(true);
      setLoggingOut(false);
    }
  }

  const CollapseIcon = narrowScreen ? X : collapsed ? PanelLeft : PanelLeftClose;

  return (
    <>
      {narrowScreen && <header className="sut-phone-navigation sticky top-0 z-40 flex h-12 items-center gap-3 border-b border-[var(--border-subtle)] bg-[var(--surface-base)] px-3" data-phone-navigation>
        <button ref={mobileTriggerRef} type="button" onClick={() => setMobileNavigation(navigationKey)} aria-label={t("shell.appSidebar.expand")} title={t("shell.appSidebar.expand")} aria-expanded={mobileExpanded} aria-controls="phone-navigation" className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--r-md)] text-[var(--text-primary)]">
          <PanelLeft className="h-5 w-5" aria-hidden="true" />
        </button>
        <BilunWordmark size={28} />
      </header>}
      {narrowScreen && mobileExpanded && <button type="button" tabIndex={-1} aria-label={t("shell.appSidebar.collapse")} onClick={() => setMobileNavigation(null)} className="fixed inset-0 z-[70] bg-black/40" data-phone-sidebar-backdrop />}
    <aside
      ref={sidebarRef}
      id={narrowScreen ? "phone-navigation" : undefined}
      hidden={narrowScreen && !mobileExpanded}
      role={narrowScreen ? "dialog" : undefined}
      aria-modal={narrowScreen && mobileExpanded ? true : undefined}
      tabIndex={narrowScreen ? -1 : undefined}
      className={cn(
        "sut-app-sidebar fixed inset-y-0 left-0 flex flex-col",
        "border-r border-[var(--border-subtle)] bg-[var(--surface-base)]",
        narrowScreen ? "z-[80]" : "z-40",
        className,
      )}
      style={{ width: narrowScreen ? "min(20rem, calc(100vw - 3rem))" : sidebarWidthPx(collapsed) }}
      data-sut-sidebar
      data-mobile-open={narrowScreen && mobileExpanded ? "true" : undefined}
      data-collapsed={collapsed ? "true" : "false"}
      aria-label={t("shell.appSidebar.ariaNavigation")}
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-3",
          collapsed ? "flex-col" : "justify-between",
        )}
      >
        <Link
          href="/"
          className={cn(
            "inline-flex min-w-0 items-center overflow-hidden",
            collapsed && "justify-center",
          )}
          aria-label={t("shell.appSidebar.logoAlt")}
        >
          {collapsed ? (
            // eslint-disable-next-line @next/next/no-img-element -- static brand asset; no next/image in app yet
            <img
              src="/brand/nameless.png"
              alt=""
              width={27}
              height={32}
              className="block h-8 w-auto"
              aria-hidden="true"
            />
          ) : (
            <BilunWordmark size={40} />
          )}
        </Link>

        <button
          type="button"
          onClick={() => narrowScreen
            ? setMobileNavigation(mobileExpanded ? null : navigationKey)
            : setDesktopCollapsed((value) => !value)}
          className={cn(
            "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--r-md)]",
            "text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)]",
            "transition-colors",
          )}
          aria-expanded={!collapsed}
          aria-label={
            collapsed
              ? t("shell.appSidebar.expand")
              : t("shell.appSidebar.collapse")
          }
          title={
            collapsed
              ? t("shell.appSidebar.expand")
              : t("shell.appSidebar.collapse")
          }
        >
          <CollapseIcon className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {!collapsed && (
        <div className="px-3 pt-3">
          <SyntheticDemoChip dataSource={sutDataSource} />
        </div>
      )}

      <nav
        className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3"
        aria-label={t("shell.appSidebar.ariaHomeTabs")}
      >
        {visibleTabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const key = tabMessageKey(tab.id);
          const Icon = MAIN_SECTION_ICONS[tab.id];
          const label = t(`constants.homeTabs.${key}.label`);
          const subtitle = t(`constants.homeTabs.${key}.subtitle`);
          return (
            <Link
              key={tab.id}
              href={buildSutHomeHref(tab.id, searchParams)}
              onClick={() => setMobileNavigation(null)}
              scroll={false}
              title={subtitle}
              className={cn(
                "group relative flex items-center gap-3 rounded-[var(--r-md)] px-2.5 py-2 text-sm font-medium transition-colors",
                collapsed && "justify-center px-0",
                isActive
                  ? "bg-[var(--gold-subtle)] text-[var(--text-primary)]"
                  : "text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-primary)]",
              )}
              aria-current={isActive ? "page" : undefined}
            >
              {isActive && (
                <span
                  className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-[var(--gold)]"
                  aria-hidden="true"
                />
              )}
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {!collapsed && <span className="truncate">{label}</span>}
              {collapsed && <span className="sr-only">{label}</span>}
            </Link>
          );
        })}
      </nav>

      <div
        className={cn(
          "mt-auto flex flex-col gap-2 border-t border-[var(--border-subtle)] px-2 py-3",
          collapsed && "items-center",
        )}
      >
        <LocaleSwitcher compact={collapsed} />
        <RoleSwitcher compact={collapsed} />

        <button
          type="button"
          onClick={() => { setMobileNavigation(null); setShowReportProblem(true); }}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-xs font-medium",
            "text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]",
            "transition-colors",
            collapsed && "justify-center px-0",
          )}
          title={t("shell.appSidebar.reportProblem")}
          aria-label={t("shell.appSidebar.reportProblem")}
        >
          <MessageSquareWarning className="h-3.5 w-3.5 shrink-0 text-[var(--gold)]" aria-hidden="true" />
          {!collapsed && <span>{t("shell.appSidebar.reportProblem")}</span>}
        </button>

        <button
          type="button"
          onClick={() => { setMobileNavigation(null); handleOpenHowItWorks(); }}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-xs font-medium",
            "text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]",
            "transition-colors",
            collapsed && "justify-center px-0",
          )}
          title={t("shell.appSidebar.howItWorks")}
          aria-label={t("shell.appSidebar.howItWorks")}
        >
          <CircleHelp className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>{t("shell.appSidebar.howItWorks")}</span>}
        </button>

        {identity.authenticated && <button
          type="button"
          onClick={handleLogout}
          disabled={loggingOut}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-xs font-medium",
            "text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]",
            "transition-colors",
            collapsed && "justify-center px-0",
          )}
          aria-label={t("auth.logout.button")}
          title={t("auth.logout.button")}
        >
          <LogOut className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {!collapsed && <span>{t("auth.logout.button")}</span>}
        </button>}
        {logoutError && <p role="alert" className="px-2 text-xs text-[var(--danger)]">{t("auth.logout.error")}</p>}
      </div>
    </aside>
    </>
  );
}
