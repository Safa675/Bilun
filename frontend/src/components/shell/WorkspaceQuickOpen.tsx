"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useStore } from "zustand";
import { Search } from "lucide-react";
import { searchSutPatients } from "@/lib/api/sut";
import { buildSutPatientHref } from "@/lib/constants";
import { cn } from "@/lib/cn";
import type { PatientSearchResult } from "@/lib/domains/patient";
import { isBackgroundTabPointer } from "@/lib/patientTabOpen";
import { useT } from "@/lib/i18n/useTranslations";
import { useWorkspaceStoreApi } from "@/stores/workspaceContext";
import {
  PatientTabContextMenu,
  useOpenPatientBackground,
} from "@/components/shell/PatientTabLink";

/** Ctrl+K patient quick-open: search by id, open result as a tab. */
export default function WorkspaceQuickOpen() {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const store = useWorkspaceStoreApi();
  const open = useStore(store, (state) => state.quickOpen);
  const setQuickOpen = useStore(store, (state) => state.setQuickOpen);
  const openBackground = useOpenPatientBackground();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [tabMenu, setTabMenu] = useState<{ x: number; y: number; patientId: string } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (pathname !== "/login") setQuickOpen(!store.getState().quickOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pathname, setQuickOpen, store]);

  useEffect(() => {
    if (pathname === "/login") setQuickOpen(false);
  }, [pathname, setQuickOpen]);

  // Reset on open via subscription callback (event-driven, not effect-body).
  useEffect(() => {
    return store.subscribe((state, prev) => {
      if (state.quickOpen && !prev.quickOpen) {
        setQuery("");
        setResults([]);
        setActiveIndex(0);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      }
    });
  }, [store]);

  useEffect(() => {
    if (!open || query.trim().length === 0) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchSutPatients(query.trim(), 8, { signal: controller.signal })
        .then((response) => {
          setResults(response.results ?? []);
          setActiveIndex(0);
        })
        .catch(() => {
          // Aborted or failed: keep the previous results.
        });
    }, 150);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [open, query]);

  const shownResults = query.trim().length === 0 ? [] : results;

  const openPatient = (patientId: string, background = false) => {
    if (background) {
      openBackground(patientId);
      return;
    }
    setQuickOpen(false);
    router.push(buildSutPatientHref(patientId));
  };

  const handleInputKey = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setQuickOpen(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, shownResults.length - 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const selected = shownResults[activeIndex];
      if (selected) openPatient(selected.patient_id, event.metaKey || event.ctrlKey);
    }
  };

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        className="fixed inset-0 z-40 cursor-default"
        onClick={() => setQuickOpen(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("shell.quickOpen.ariaLabel")}
        data-quick-open
        className="fixed left-1/2 top-24 z-50 w-full max-w-lg -translate-x-1/2 rounded-[var(--r-lg)] border border-[var(--border-subtle)] bg-[var(--surface-base)] shadow-[var(--shadow-2)]"
      >
        <div className="flex items-center gap-2 border-b border-[var(--border-subtle)] px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleInputKey}
            placeholder={t("shell.quickOpen.placeholder")}
            aria-label={t("shell.quickOpen.ariaLabel")}
            data-quick-open-input
            className="w-full bg-transparent text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)]"
          />
        </div>
        <ul className="max-h-80 overflow-y-auto p-1">
          {shownResults.map((result, index) => (
            <li key={result.patient_id}>
              <button
                type="button"
                onClick={(event) => {
                  if (isBackgroundTabPointer(event)) {
                    event.preventDefault();
                    openPatient(result.patient_id, true);
                    return;
                  }
                  openPatient(result.patient_id);
                }}
                onAuxClick={(event) => {
                  if (event.button !== 1) return;
                  event.preventDefault();
                  openPatient(result.patient_id, true);
                }}
                onContextMenu={(event) => {
                  event.preventDefault();
                  setTabMenu({ x: event.clientX, y: event.clientY, patientId: result.patient_id });
                }}
                onMouseEnter={() => setActiveIndex(index)}
                data-quick-open-result={result.patient_id}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-[var(--r-md)] px-2.5 py-1.5 text-left",
                  index === activeIndex
                    ? "bg-[var(--surface-tint)] text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)]",
                )}
              >
                <span className="font-mono text-xs font-medium">{result.patient_id}</span>
                <span className="text-xs text-[var(--text-muted)]">
                  {result.age ?? "—"} · {result.sex ?? "—"}
                </span>
              </button>
            </li>
          ))}
          {query.trim().length > 0 && shownResults.length === 0 && (
            <li className="px-2.5 py-2 text-xs text-[var(--text-muted)]">
              {t("shell.quickOpen.empty")}
            </li>
          )}
        </ul>
      </div>
      {tabMenu ? (
        <PatientTabContextMenu
          x={tabMenu.x}
          y={tabMenu.y}
          onOpen={() => {
            openPatient(tabMenu.patientId, true);
          }}
          onDismiss={() => setTabMenu(null)}
        />
      ) : null}
    </>
  );
}
