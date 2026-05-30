"use client";

import { useCallback } from "react";
import { CircleHelp } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { SyntheticDemoChip } from "@/components/sut/SyntheticDemoProvenance";
import { useConfig } from "@/lib/configContext";
import { cn } from "@/lib/cn";
import { SUT_HOME_TABS, type SutHomeTab } from "@/lib/constants";
import { useSetShowHowItWorks } from "@/stores/index";

interface AppTopBarProps {
  /** Optional override; defaults to wiring the global `showHowItWorks` store. */
  onOpenHowItWorks?: () => void;
  className?: string;
}

function useActiveHomeTab(): SutHomeTab {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  if (pathname !== "/") return "analytics";
  const tab = searchParams.get("tab");
  if (tab === "optimizer") return "optimizer";
  if (tab === "reference-tools") return "reference-tools";
  return "analytics";
}

export default function AppTopBar({ onOpenHowItWorks, className }: AppTopBarProps) {
  const setShowHowItWorks = useSetShowHowItWorks();
  const config = useConfig();
  const sutDataSource = config.sut_data_source ?? config.sutDataSource ?? null;
  const activeTab = useActiveHomeTab();
  const handleOpenHowItWorks = useCallback(() => {
    if (onOpenHowItWorks) {
      onOpenHowItWorks();
      return;
    }
    setShowHowItWorks(true);
  }, [onOpenHowItWorks, setShowHowItWorks]);

  return (
    <header
      className={cn(
        "sut-app-top-bar flex w-full items-center justify-between gap-4 px-6 py-3",
        "border-b border-[var(--border-subtle)] bg-[var(--surface-base)]",
        className,
      )}
      aria-label="BILUN application bar"
    >
      <Image
        src="/bilun-logo.png"
        alt="BILUN"
        width={2836}
        height={1504}
        className="h-12 w-auto object-contain"
        priority
      />

      <div className="flex items-center gap-4">
        <SyntheticDemoChip dataSource={sutDataSource} />

        <nav className="flex items-center gap-1" aria-label="SUT home tabs">
          {SUT_HOME_TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <Link
                key={tab.id}
                href={`/?tab=${tab.id}`}
                scroll={false}
                title={tab.subtitle}
                className={cn(
                  "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  isActive
                    ? "bg-[var(--surface-tint)] text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-tint)]/50",
                )}
                aria-current={isActive ? "page" : undefined}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={handleOpenHowItWorks}
          className={cn(
            "inline-flex items-center gap-1.5 text-xs font-medium",
            "text-[var(--text-secondary)] hover:text-[var(--gold-hover)]",
            "transition-colors duration-150",
          )}
        >
          <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
          How it works
        </button>
      </div>
    </header>
  );
}
