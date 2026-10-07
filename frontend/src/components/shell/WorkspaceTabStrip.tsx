"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, Columns2, MessageSquareWarning, Search, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import { motionScrollBehavior } from "@/lib/motion";
import {
  WORKSPACE_TAB_MAX_PX,
  WORKSPACE_TAB_MIN_PX,
  workspaceTabHref,
  type WorkspaceTab,
} from "@/lib/workspaceTabs";
import { resolveTabInfo } from "@/lib/workspaceSubtabs";
import { useSetShowReportProblem } from "@/stores/index";
import {
  useWorkspaceActiveTabId,
  useWorkspaceStoreApi,
  useWorkspaceTabs,
} from "@/stores/workspaceContext";

function tabDisplay(tab: WorkspaceTab, t: ReturnType<typeof useT>) {
  return resolveTabInfo(tab, (key) => t(key as any));
}

function TabIcon({ tab, t }: { tab: WorkspaceTab; t: ReturnType<typeof useT> }) {
  const { Icon } = tabDisplay(tab, t);
  return <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
}

function scrollTabIntoTrack(track: HTMLElement, tabEl: HTMLElement) {
  const trackBox = track.getBoundingClientRect();
  const tabBox = tabEl.getBoundingClientRect();
  if (tabBox.left < trackBox.left) {
    track.scrollLeft -= trackBox.left - tabBox.left;
  } else if (tabBox.right > trackBox.right) {
    track.scrollLeft += tabBox.right - trackBox.right;
  }
}

export default function WorkspaceTabStrip() {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const tabs = useWorkspaceTabs();
  const activeTabId = useWorkspaceActiveTabId();
  const store = useWorkspaceStoreApi();
  const setShowReportProblem = useSetShowReportProblem();
  const trackRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollAffordance = useCallback(() => {
    const el = trackRef.current;
    if (!el) {
      setCanScrollLeft(false);
      setCanScrollRight(false);
      return;
    }
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setCanScrollLeft(left);
    setCanScrollRight(right);
  }, []);

  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    updateScrollAffordance();
    const observer = new ResizeObserver(updateScrollAffordance);
    observer.observe(el);
    el.addEventListener("scroll", updateScrollAffordance, { passive: true });
    return () => {
      observer.disconnect();
      el.removeEventListener("scroll", updateScrollAffordance);
    };
  }, [tabs, updateScrollAffordance]);

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track || !activeTabId) return;
    const tabEl = Array.from(
      track.querySelectorAll<HTMLElement>("[data-workspace-tab]"),
    ).find((el) => el.getAttribute("data-workspace-tab") === activeTabId);
    if (!tabEl) return;
    scrollTabIntoTrack(track, tabEl);
    updateScrollAffordance();
  }, [activeTabId, tabs, updateScrollAffordance]);

  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey) return;
      if (el.scrollWidth <= el.clientWidth) return;
      const delta =
        Math.abs(event.deltaY) > Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
      if (delta === 0) return;
      event.preventDefault();
      el.scrollLeft += delta;
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [tabs]);

  if (pathname === "/login" || tabs.length === 0) {
    return null;
  }

  const handleClose = (tabId: string) => {
    const navigateTo = store.getState().closeTab(tabId);
    if (navigateTo) router.push(navigateTo);
  };

  const handleSplit = (tab: WorkspaceTab) => {
    store.getState().openSplit({ kind: tab.kind, refId: tab.refId });
  };

  const scrollByPage = (direction: -1 | 1) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollBy({ left: direction * Math.max(el.clientWidth * 0.6, 120), behavior: motionScrollBehavior() });
  };

  return (
    <div
      className="sticky top-0 z-30 flex h-10 items-end gap-1 border-b border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 pt-1"
      style={{ paddingRight: "calc(var(--chat-dock-inset-right, 0px) + 0.5rem)" }}
      role="navigation"
      aria-label={t("shell.workspaceTabs.ariaLabel")}
      data-workspace-tabstrip
    >
      <div className="relative min-w-0 flex-1">
        {canScrollLeft && (
          <button
            type="button"
            onClick={() => scrollByPage(-1)}
            aria-label={t("shell.workspaceTabs.scrollLeft")}
            title={t("shell.workspaceTabs.scrollLeft")}
            className="absolute bottom-0 left-0 z-10 flex h-full w-7 items-end justify-center bg-gradient-to-r from-[var(--surface-base)] from-50% to-transparent pb-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            <ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
        <div
          ref={trackRef}
          data-workspace-tab-track
          className="flex h-full min-w-0 flex-nowrap items-end gap-1 overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        >
          {tabs.map((tab) => {
            const isActive = tab.id === activeTabId;
            const { label, fullTitle } = tabDisplay(tab, t);
            return (
              <div
                key={tab.id}
                data-workspace-tab={tab.id}
                data-active={isActive ? "true" : "false"}
                className={cn(
                  "group relative flex flex-1 items-center overflow-hidden rounded-t-[var(--r-md)] border border-b-0",
                  isActive
                    ? "border-[var(--border-subtle)] bg-[var(--surface-tint)] text-[var(--text-primary)]"
                    : "border-transparent text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]",
                )}
                style={{ minWidth: WORKSPACE_TAB_MIN_PX, maxWidth: WORKSPACE_TAB_MAX_PX }}
              >
                <Link
                  href={workspaceTabHref(tab)}
                  scroll={false}
                  className={cn(
                    "flex min-w-0 flex-1 items-center gap-1.5 py-1.5 pl-2.5 pr-2 text-xs font-medium",
                    "group-hover:pr-8 group-focus-within:pr-8",
                    tab.kind === "patient" && "group-hover:pr-14 group-focus-within:pr-14",
                  )}
                  title={fullTitle}
                >
                  <TabIcon tab={tab} t={t} />
                  <span className={cn("truncate", tab.kind === "patient" && "font-mono text-[11px]")}>
                    {label}
                  </span>
                </Link>
                <div className="absolute top-1/2 right-0.5 flex -translate-y-1/2 items-center opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                  {tab.kind === "patient" ? (
                    <button
                      type="button"
                      onClick={() => handleSplit(tab)}
                      aria-label={`${t("shell.workspaceTabs.openSideBySide")}: ${label}`}
                      title={t("shell.workspaceTabs.openSideBySide")}
                      className="inline-flex h-5 w-5 items-center justify-center rounded text-[var(--text-muted)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)]"
                    >
                      <Columns2 className="h-3 w-3" aria-hidden="true" />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => handleClose(tab.id)}
                    aria-label={`${t("shell.workspaceTabs.close")}: ${label}`}
                    title={t("shell.workspaceTabs.close")}
                    className="inline-flex h-5 w-5 items-center justify-center rounded text-[var(--text-muted)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)]"
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        {canScrollRight && (
          <button
            type="button"
            onClick={() => scrollByPage(1)}
            aria-label={t("shell.workspaceTabs.scrollRight")}
            title={t("shell.workspaceTabs.scrollRight")}
            className="absolute right-0 bottom-0 z-10 flex h-full w-7 items-end justify-center bg-gradient-to-l from-[var(--surface-base)] from-50% to-transparent pb-1.5 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
          >
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
      <div className="mb-0.5 flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={() => setShowReportProblem(true)}
          aria-label={t("shell.feedback.button")}
          title={`${t("shell.feedback.button")} (safaoksuz@bilun.tech)`}
          data-feedback-trigger
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-tint)] hover:text-[var(--gold)]"
        >
          <MessageSquareWarning className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={() => store.getState().setQuickOpen(true)}
          aria-label={t("shell.quickOpen.ariaLabel")}
          title={`${t("shell.quickOpen.ariaLabel")} (Ctrl+K)`}
          data-quick-open-trigger
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]"
        >
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
