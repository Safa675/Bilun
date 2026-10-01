"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  CircleHelp,
  LogOut,
  MessageSquareWarning,
  PanelLeft,
  PanelLeftClose,
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
  useAiDockPosition,
  useNavigationStoreApi,
  useSetShowHowItWorks,
  useSetShowReportProblem,
} from "@/stores/index";
import { getMedulaRejectionIngestStatus } from "@/lib/api/sut";
import { useSessionIdentity, useUserRole } from "@/components/shell/RoleProvider";
import { endSession } from "@/lib/api/auth";
import { announceSessionChange, clearProtectedBrowserState } from "@/lib/authBrowser";
import {
  readSidebarCollapsed,
  sidebarWidthPx,
  writeSidebarCollapsed,
} from "@/lib/shellSidebar";
import { MAIN_SECTION_ICONS, tabMessageKey } from "@/lib/workspaceSubtabs";

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
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const collapsed = narrowScreen ? !mobileExpanded : desktopCollapsed;
  const hideShell = pathname === "/login";
  const chatDock = useAiDockPosition();
  const navigationStore = useNavigationStoreApi();

  useEffect(() => {
    if (hideShell) return;
    return navigationStore.subscribe((state, prevState) => {
      if (state.aiDockPosition === "right" && prevState.aiDockPosition !== "right") {
        setDesktopCollapsed(true);
        setMobileExpanded(false);
      }
    });
  }, [hideShell, navigationStore]);

  // Mount-only read; synchronously initialize sidebar state and width before paint.
  useLayoutEffect(() => {
    const initiallyNarrow = window.matchMedia("(max-width: 640px)").matches;
    const initialDesktopCollapsed = readSidebarCollapsed() || chatDock === "right";
    setNarrowScreen(initiallyNarrow);
    setDesktopCollapsed(initialDesktopCollapsed);
    if (!hideShell) {
      document.documentElement.style.setProperty(
        "--shell-sidebar-width",
        `${sidebarWidthPx(initiallyNarrow || initialDesktopCollapsed)}px`,
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional mount-only read
  }, []);

  useEffect(() => {
    const narrowScreen = window.matchMedia("(max-width: 640px)");
    const updateNarrowScreen = (event: MediaQueryListEvent) => {
      setNarrowScreen(event.matches);
      if (event.matches) setMobileExpanded(false);
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
    const width = `${sidebarWidthPx(collapsed)}px`;
    root.style.setProperty("--shell-sidebar-width", width);
  }, [collapsed, hideShell]);

  useEffect(() => {
    if (hideShell) return;
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

  const CollapseIcon = collapsed ? PanelLeft : PanelLeftClose;

  return (
    <aside
      className={cn(
        "sut-app-sidebar fixed inset-y-0 left-0 z-40 flex flex-col",
        "border-r border-[var(--border-subtle)] bg-[var(--surface-base)]",
        "transition-[width] duration-200 ease-out",
        className,
      )}
      style={{ width: sidebarWidthPx(collapsed) }}
      data-sut-sidebar
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
              width={20}
              height={24}
              className="block h-6 w-auto"
              aria-hidden="true"
            />
          ) : (
            <BilunWordmark size={20} />
          )}
        </Link>

        <button
          type="button"
          onClick={() => narrowScreen
            ? setMobileExpanded((value) => !value)
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
              scroll={false}
              title={subtitle}
              className={cn(
                "group relative flex items-center gap-3 rounded-[var(--r-md)] px-2.5 py-2 text-[13px] font-medium transition-colors",
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
          onClick={() => setShowReportProblem(true)}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-[11px] font-medium",
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
          onClick={handleOpenHowItWorks}
          className={cn(
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-[11px] font-medium",
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
            "inline-flex items-center gap-2 rounded-[var(--r-md)] px-2.5 py-2 text-[11px] font-medium",
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
  );
}
