"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { Button, buttonActiveClass, inputClass } from "@/components/primitives";
import { cn } from "@/lib/cn";
import { theme } from "@/lib/theme";
import type { PatientSearchResponse, PatientSearchResult } from "@/lib/domains/patient";
import { useT } from "@/lib/i18n/useTranslations";

type PatientSearchFn = (
  q: string,
  limit?: number,
  options?: RequestInit,
) => Promise<PatientSearchResponse>;

interface Props {
  selectedPatientId: string | null;
  onSelect: (patientId: string) => void;
  disabled?: boolean;
  id?: string;
  placeholder?: string;
  searchFn: PatientSearchFn;
}

/**
 * Search-as-you-type combobox for patient IDs.
 * Receives a product-owned search function so split apps do not depend on legacy patient clients.
 */
export default function PatientSearch({
  selectedPatientId,
  onSelect,
  disabled = false,
  id = "patient-search",
  placeholder,
  searchFn,
}: Props) {
  const t = useT();
  const resolvedPlaceholder = placeholder ?? t("cohort.patientSearch.defaultPlaceholder");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PatientSearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const searchFnRef = useRef<PatientSearchFn>(searchFn);
  const requestSeqRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    searchFnRef.current = searchFn;
  }, [searchFn]);

  const doSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        const requestId = requestSeqRef.current + 1;
        requestSeqRef.current = requestId;

        activeControllerRef.current?.abort();
        const controller = new AbortController();
        activeControllerRef.current = controller;

        setLoading(true);
        setError(null);
        try {
          const res = await searchFnRef.current(q, 20, { signal: controller.signal });
          if (controller.signal.aborted || requestId !== requestSeqRef.current) return;
          setResults(res.results);
          setIsOpen(true);
          setHighlightIdx(-1);
        } catch (err) {
          if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
          setResults([]);
          setError(err instanceof Error ? err.message : t("cohort.patientSearch.searchFailed"));
          setIsOpen(true);
        } finally {
          if (activeControllerRef.current === controller) {
            setLoading(false);
          }
        }
      }, 200);
    },
    [t],
  );

  const retrySearch = useCallback(() => {
    doSearch(query);
  }, [doSearch, query]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    doSearch(val);
  };

  const handleSelect = (pid: string) => {
    setQuery("");
    setIsOpen(false);
    setHighlightIdx(-1);
    onSelect(pid);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || results.length === 0) {
      if (e.key === "ArrowDown" || e.key === "Enter") {
        doSearch(query);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIdx((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIdx((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter" && highlightIdx >= 0) {
      e.preventDefault();
      handleSelect(results[highlightIdx].patient_id);
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setHighlightIdx(-1);
    }
  };

  useEffect(() => {
    if (highlightIdx >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll("li");
      items[highlightIdx]?.scrollIntoView({ block: "nearest" });
    }
  }, [highlightIdx]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      activeControllerRef.current?.abort();
      activeControllerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const displayValue = selectedPatientId
    ? t("cohort.patientSearch.selectedLabel", { patientId: selectedPatientId })
    : "";

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <div style={{ position: "relative" }}>
        <Search
          style={{
            position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)",
            width: 16, height: 16, color: "#A1A1AA", pointerEvents: "none",
          }}
        />
        <input
          ref={inputRef}
          id={id}
          type="text"
          className={cn(inputClass, "patient-search-input")}
          style={{
            width: "100%",
            cursor: disabled ? "not-allowed" : "text",
            fontSize: "0.85rem",
            paddingLeft: 36,
            transition: "border-color 0.2s ease, box-shadow 0.2s ease",
          }}
          value={isOpen ? query : displayValue}
          onChange={handleChange}
          onFocus={() => {
            setQuery("");
            doSearch("");
          }}
          onKeyDown={handleKeyDown}
          placeholder={resolvedPlaceholder}
          disabled={disabled}
          autoComplete="off"
          role="combobox"
          aria-expanded={isOpen}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={
            highlightIdx >= 0 ? `${id}-option-${highlightIdx}` : undefined
          }
        />
      </div>

      {isOpen && (
        <ul
          ref={listRef}
          id={`${id}-listbox`}
          role="listbox"
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 50,
            maxHeight: 280,
            overflowY: "auto",
            margin: 0,
            padding: 0,
            listStyle: "none",
            background: "rgba(255, 255, 255, 0.96)",
            backdropFilter: "blur(16px)",
            border: `1px solid ${theme.accentAlpha(0.15)}`,
            borderRadius: 8,
            marginTop: 4,
            boxShadow: `0 8px 24px ${theme.accentAlpha(0.12)}`,
          }}
        >
          {loading && (
            <li style={{ padding: "10px 14px", color: "#A1A1AA", fontSize: "0.82rem" }}>
              {t("cohort.patientSearch.searching")}
            </li>
          )}
          {!loading && results.length === 0 && (
            <li style={{ padding: "10px 14px", color: "#A1A1AA", fontSize: "0.82rem" }}>
              {error ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <span style={{ color: "#B91C1C" }}>{error}</span>
                  <Button
                    variant="secondary"
                    size="compact"
                    className={cn("self-start", buttonActiveClass)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={retrySearch}
                  >
                    <span className="text-xs font-semibold">{t("cohort.patientSearch.retry")}</span>
                  </Button>
                </div>
              ) : (
                t("cohort.patientSearch.noResults")
              )}
            </li>
          )}
          {!loading &&
            results.map((r, idx) => (
              <li
                key={r.patient_id}
                id={`${id}-option-${idx}`}
                role="option"
                aria-selected={highlightIdx === idx}
                onClick={() => handleSelect(r.patient_id)}
                style={{
                  padding: "8px 14px",
                  cursor: "pointer",
                  fontSize: "0.84rem",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background:
                    highlightIdx === idx
                      ? "#FAFAF9"
                      : r.patient_id === selectedPatientId
                        ? theme.accentAlpha(0.05)
                        : "transparent",
                  color: r.patient_id === selectedPatientId ? theme.accent : "#1A1A1A",
                  borderBottom: `1px solid ${theme.accentAlpha(0.05)}`,
                }}
                onMouseEnter={() => setHighlightIdx(idx)}
              >
                <span>{t("cohort.patientSearch.selectedLabel", { patientId: r.patient_id })}</span>
                <span style={{ color: "#A1A1AA", fontSize: "0.75rem" }}>
                  {r.age != null && t("cohort.patientSearch.ageSuffix", { age: r.age })}
                  {r.age != null && r.sex && " / "}
                  {r.sex}
                </span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
