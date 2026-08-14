"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, Columns2, Search, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/useTranslations";
import {
  WORKSPACE_INLINE_TABS,
  workspaceTabHref,
  type WorkspaceTab,
} from "@/lib/workspaceTabs";
import { resolveTabInfo } from "@/lib/workspaceSubtabs";
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

export default function WorkspaceTabStrip() {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const tabs = useWorkspaceTabs();
  const activeTabId = useWorkspaceActiveTabId();
  const store = useWorkspaceStoreApi();
  const [overflowOpen, setOverflowOpen] = useState(false);

  if (pathname === "/login" || tabs.length === 0) {
    return null;
  }

  const inlineTabs = tabs.slice(0, WORKSPACE_INLINE_TABS);
  const overflowTabs = tabs.slice(WORKSPACE_INLINE_TABS);

  const handleClose = (tabId: string) => {
    const navigateTo = store.getState().closeTab(tabId);
    if (navigateTo) router.push(navigateTo);
  };

  const handleSplit = (tab: WorkspaceTab) => {
    store.getState().openSplit({ kind: tab.kind, refId: tab.refId });
  };

  const splitButton = (tab: WorkspaceTab, alwaysVisible: boolean) => {
    const { label } = tabDisplay(tab, t);
    return tab.kind === "patient" ? (
      <button
        type="button"
        onClick={() => handleSplit(tab)}
        aria-label={`${t("shell.workspaceTabs.openSideBySide")}: ${label}`}
        title={t("shell.workspaceTabs.openSideBySide")}
        className={cn(
          "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--text-muted)] transition-opacity hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)]",
          !alwaysVisible &&
            "opacity-0 focus-visible:opacity-100 group-hover:opacity-100",
        )}
      >
        <Columns2 className="h-3 w-3" aria-hidden="true" />
      </button>
    ) : null;
  };

  const renderTab = (tab: WorkspaceTab) => {
    const isActive = tab.id === activeTabId;
    const { label, fullTitle } = tabDisplay(tab, t);
    return (
      <div
        key={tab.id}
        data-workspace-tab={tab.id}
        data-active={isActive ? "true" : "false"}
        className={cn(
          "group flex min-w-0 max-w-52 items-center rounded-t-[var(--r-md)] border border-b-0",
          isActive
            ? "border-[var(--border-subtle)] bg-[var(--surface-tint)] text-[var(--text-primary)]"
            : "border-transparent text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]",
        )}
      >
        <Link
          href={workspaceTabHref(tab)}
          scroll={false}
          className="flex min-w-0 flex-1 items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium"
          title={fullTitle}
        >
          <TabIcon tab={tab} t={t} />
          <span className={cn("truncate", tab.kind === "patient" && "font-mono text-[11px]")}>
            {label}
          </span>
        </Link>
        {splitButton(tab, false)}
        <button
          type="button"
          onClick={() => handleClose(tab.id)}
          aria-label={`${t("shell.workspaceTabs.close")}: ${label}`}
          title={t("shell.workspaceTabs.close")}
          className="mr-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--text-muted)] opacity-0 transition-opacity hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)] focus-visible:opacity-100 group-hover:opacity-100"
        >
          <X className="h-3 w-3" aria-hidden="true" />
        </button>
      </div>
    );
  };

  return (
    <div
      className="sticky top-0 z-30 flex h-10 items-end gap-1 border-b border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 pt-1"
      style={{ paddingRight: "calc(var(--chat-dock-inset-right, 0px) + 0.5rem)" }}
      role="navigation"
      aria-label={t("shell.workspaceTabs.ariaLabel")}
      data-workspace-tabstrip
    >
      {inlineTabs.map(renderTab)}
      {overflowTabs.length > 0 && (
        <div className="relative">
          <button
            type="button"
            onClick={() => setOverflowOpen((open) => !open)}
            aria-expanded={overflowOpen}
            aria-label={t("shell.workspaceTabs.overflow")}
            title={t("shell.workspaceTabs.overflow")}
            className="inline-flex items-center gap-1 rounded-t-[var(--r-md)] px-2 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)]"
          >
            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            +{overflowTabs.length}
          </button>
          {overflowOpen && (
            <>
              <button
                type="button"
                aria-hidden="true"
                tabIndex={-1}
                className="fixed inset-0 z-30 cursor-default"
                onClick={() => setOverflowOpen(false)}
              />
              <div className="absolute left-0 top-full z-40 mt-1 flex w-56 flex-col gap-0.5 rounded-[var(--r-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] p-1 shadow-[var(--shadow-2)]">
                {overflowTabs.map((tab) => {
                  const { label, fullTitle } = tabDisplay(tab, t);
                  return (
                    <div
                      key={tab.id}
                      data-workspace-tab={tab.id}
                      className={cn(
                        "group flex items-center rounded-[var(--r-md)]",
                        tab.id === activeTabId
                          ? "bg-[var(--surface-tint)] text-[var(--text-primary)]"
                          : "text-[var(--text-muted)] hover:bg-[var(--surface-tint)]",
                      )}
                    >
                      <Link
                        href={workspaceTabHref(tab)}
                        scroll={false}
                        onClick={() => setOverflowOpen(false)}
                        className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1.5 text-xs font-medium"
                        title={fullTitle}
                      >
                        <TabIcon tab={tab} t={t} />
                        <span className={cn("truncate", tab.kind === "patient" && "font-mono text-[11px]")}>
                          {label}
                        </span>
                      </Link>
                      {splitButton(tab, true)}
                      <button
                        type="button"
                        onClick={() => handleClose(tab.id)}
                        aria-label={`${t("shell.workspaceTabs.close")}: ${label}`}
                        className="mr-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      >
                        <X className="h-3 w-3" aria-hidden="true" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
      <button
        type="button"
        onClick={() => store.getState().setQuickOpen(true)}
        aria-label={t("shell.quickOpen.ariaLabel")}
        title={`${t("shell.quickOpen.ariaLabel")} (Ctrl+K)`}
        data-quick-open-trigger
        className="ml-auto mb-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--r-md)] text-[var(--text-muted)] hover:bg-[var(--surface-tint)] hover:text-[var(--text-secondary)] transition-colors"
      >
        <Search className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}
