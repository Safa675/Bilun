"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { CircleHelp, LogOut } from "lucide-react";
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
import { useSetShowHowItWorks } from "@/stores/index";
import { getMedulaRejectionIngestStatus } from "@/lib/api/sut";
import { useUserRole } from "@/components/shell/RoleProvider";

interface AppTopBarProps {
  /** Optional override; defaults to wiring the global `showHowItWorks` store. */
  onOpenHowItWorks?: () => void;
  className?: string;
}

function useActiveHomeTab(): SutHomeTab {
  const searchParams = useSearchParams();
  return parseSutHomeTab(searchParams.get("tab"));
}

export default function AppTopBar({ onOpenHowItWorks, className }: AppTopBarProps) {
  const t = useT();
  const router = useRouter();
  const setShowHowItWorks = useSetShowHowItWorks();
  const config = useConfig();
  const searchParams = useSearchParams();
  const sutDataSource = config.sut_data_source ?? config.sutDataSource ?? null;
  const activeTab = useActiveHomeTab();
  const userRole = useUserRole();
  const [medulaIngestAvailable, setMedulaIngestAvailable] = useState<boolean | null>(null);

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      // Even if the network call fails, clear the session locally and leave.
    }
    router.replace("/login");
    router.refresh();
  }

  useEffect(() => {
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
    // Poll so the Operations tab appears if ingest becomes available after
    // mount (e.g. the parquet lands while the user is on another tab).
    const timer = window.setInterval(poll, 30_000);
    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

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

  return (
    <header
      className={cn(
        "sut-app-top-bar flex h-14 w-full items-center justify-between gap-8 px-8",
        "border-b border-[var(--border-subtle)] bg-[var(--surface-base)]",
        className,
      )}
      data-sut-topbar
      aria-label={t("shell.appTopBar.ariaApplicationBar")}
    >
      {/* Zone 1: Brand + Navigation */}
      <div className="flex items-center gap-8">
        <Link href="/" className="inline-flex items-center">
          <BilunWordmark size={20} />
        </Link>

        <SyntheticDemoChip dataSource={sutDataSource} />

        <nav className="flex items-center gap-1" aria-label={t("shell.appTopBar.ariaHomeTabs")}>
          {visibleTabs.map((tab) => {
            const isActive = activeTab === tab.id;
            const tabKey =
              tab.id === "reference-tools"
                ? "referenceTools"
                : tab.id === "rule-database"
                  ? "ruleDatabase"
                  : tab.id;
            return (
              <Link
                key={tab.id}
                href={buildSutHomeHref(tab.id, searchParams)}
                scroll={false}
                title={t(`constants.homeTabs.${tabKey}.subtitle`)}
                className={cn(
                  "relative inline-flex items-center px-3 py-1.5 text-[13px] font-medium transition-colors",
                  isActive
                    ? "text-[var(--text-primary)] after:absolute after:bottom-[-13px] after:left-3 after:right-3 after:h-[2px] after:rounded-full after:bg-[var(--gold)] after:content-[''] "
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
                )}
                aria-current={isActive ? "page" : undefined}
              >
                {t(`constants.homeTabs.${tabKey}.label`)}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Zone 2: Utility actions */}
      <div className="flex items-center gap-3">
        <LocaleSwitcher />

        <RoleSwitcher />

        <div className="mx-1 h-4 w-px bg-[var(--border-subtle)]" aria-hidden="true" />

        <button
          type="button"
          onClick={handleOpenHowItWorks}
          className={cn(
            "inline-flex items-center gap-1.5 text-[11px] font-medium",
            "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
            "transition-colors duration-150",
          )}
        >
          <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
          {t("shell.appTopBar.howItWorks")}
        </button>

        <button
          type="button"
          onClick={handleLogout}
          className={cn(
            "inline-flex items-center gap-1.5 text-[11px] font-medium",
            "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
            "transition-colors duration-150",
          )}
          aria-label={t("auth.logout.button")}
        >
          <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
          {t("auth.logout.button")}
        </button>
      </div>
    </header>
  );
}
