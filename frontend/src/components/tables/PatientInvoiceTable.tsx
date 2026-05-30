"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getRevenueRecovery, getSutPatients } from "@/lib/api/sut";
import type { CohortRecoverySummary } from "@/lib/domains/sut";
import type { PatientMeta } from "@/lib/domains/patient";
import { DataTable, Eyebrow, Surface } from "@/components/primitives";
import { fmtTRY2, fmtPriorityLabel, fmtNum } from "@/components/tabs/sut/shared";
import { buildSutPatientHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface PatientRow {
  patient_id: string;
  age: number | null;
  sex: string | null;
  total_recoverable_try: number | null;
  priority: string | null;
  action_count: number | null;
  top_action_type: string | null;
}

const PAGE_SIZE = 10;

export default function PatientInvoiceTable({
  cohortPatientIds,
  cohortFilterActive = false,
}: {
  cohortPatientIds?: Set<string>;
  cohortFilterActive?: boolean;
} = {}) {
  const router = useRouter();
  const [rows, setRows] = useState<PatientRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [jumpInput, setJumpInput] = useState("");

  const totalPages = useMemo(() => Math.max(1, Math.ceil(rows.length / PAGE_SIZE)), [rows.length]);
  const currentPage = useMemo(() => Math.min(page, totalPages), [page, totalPages]);
  const pageRows = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return rows.slice(start, start + PAGE_SIZE);
  }, [rows, currentPage]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);

        const [patientsData, recoveryData] = await Promise.all([
          getSutPatients().catch(() => null),
          getRevenueRecovery().catch(() => null),
        ]);

        if (cancelled) return;

        const metaLookup = new Map<string, PatientMeta>();
        patientsData?.patient_meta?.forEach((m) => {
          metaLookup.set(m.patient_id, m);
        });

        const recovery = recoveryData as CohortRecoverySummary | null;
        const summarySource =
          recovery?.patient_summaries?.length
            ? recovery.patient_summaries
            : recovery?.top_patients ?? [];
        const summaryMap = new Map<
          string,
          CohortRecoverySummary["top_patients"][number]
        >();
        summarySource.forEach((p) => {
          summaryMap.set(p.patient_id, p);
        });

        const allIds = patientsData?.patients ?? summarySource.map((p) => p.patient_id);

        const merged: PatientRow[] = allIds
          .filter((pid) => !cohortFilterActive || cohortPatientIds?.has(pid))
          .map((pid) => {
          const meta = metaLookup.get(pid);
          const summary = summaryMap.get(pid);
          return {
            patient_id: pid,
            age: meta?.age ?? null,
            sex: meta?.sex ?? null,
            total_recoverable_try: summary?.total_recoverable_try ?? null,
            priority: summary?.priority ?? null,
            action_count: summary?.action_count ?? null,
            top_action_type: summary?.top_action_type ?? null,
          };
        });

        setRows(merged);
        setPage(1);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load patient data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [cohortFilterActive, cohortPatientIds]);

  function handlePrev() {
    setPage((p) => Math.max(1, p - 1));
  }

  function handleNext() {
    setPage((p) => Math.min(totalPages, p + 1));
  }

  function handleJump() {
    const n = Number(jumpInput);
    if (!Number.isNaN(n) && n >= 1 && n <= totalPages) {
      setPage(n);
    }
    setJumpInput("");
  }

  if (loading) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">Loading patient data…</p>
      </Surface>
    );
  }

  if (error) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-danger)]">{error}</p>
      </Surface>
    );
  }

  if (rows.length === 0) {
    return (
      <Surface variant="base" padding="lg">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">No patients found in the current cohort.</p>
      </Surface>
    );
  }

  return (
    <Surface variant="base" padding="lg" className="space-y-4">
      <div className="flex items-center justify-between">
        <Eyebrow tone="muted">Patient invoices</Eyebrow>
        <span className="text-xs text-[var(--text-muted)]">
          {rows.length} patient{rows.length === 1 ? "" : "s"}
        </span>
      </div>

      <DataTable minWidth={720} className="text-[0.82rem]">
        <thead>
          <tr>
            <th>Patient ID</th>
            <th>Age</th>
            <th>Sex</th>
            <th className="num-col tabular-nums text-right">Recoverable</th>
            <th>Priority</th>
            <th className="num-col tabular-nums text-right">Actions</th>
            <th>Top action</th>
          </tr>
        </thead>
        <tbody>
          {pageRows.map((row) => (
            <tr
              key={row.patient_id}
              className="cursor-pointer hover:bg-[var(--surface-tint)] transition-colors"
              onClick={() => router.push(buildSutPatientHref(row.patient_id))}
            >
              <td className="font-mono text-xs font-medium">{row.patient_id}</td>
              <td>{row.age ?? "—"}</td>
              <td className="capitalize">{row.sex ?? "—"}</td>
              <td className="num-col tabular-nums text-right font-semibold text-[var(--text-primary)]">
                {row.total_recoverable_try !== null ? fmtTRY2(row.total_recoverable_try) : "—"}
              </td>
              <td>
                {row.priority ? (
                  <span
                    className="inline-flex rounded-full px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wide"
                    style={{
                      background:
                        row.priority === "high"
                          ? "rgba(185,28,28,0.1)"
                          : row.priority === "medium"
                            ? "rgba(217,119,6,0.1)"
                            : "rgba(5,150,105,0.1)",
                      color:
                        row.priority === "high"
                          ? "#B91C1C"
                          : row.priority === "medium"
                            ? "#D97706"
                            : "var(--success)",
                    }}
                  >
                    {fmtPriorityLabel(row.priority)}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td className="num-col tabular-nums text-right">
                {row.action_count !== null ? fmtNum(row.action_count) : "—"}
              </td>
              <td className="text-[var(--text-secondary)]">{row.top_action_type ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>

      {/* Pagination */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePrev}
            disabled={currentPage <= 1}
            className={cn(
              "inline-flex items-center rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
              currentPage <= 1
                ? "border-[var(--border-subtle)] text-[var(--text-muted)] cursor-not-allowed opacity-50"
                : "border-[var(--border-subtle)] text-[var(--text-primary)] hover:bg-[var(--surface-tint)]",
            )}
          >
            Prev
          </button>
          <span className="text-xs text-[var(--text-secondary)] tabular-nums">
            Page {currentPage} of {totalPages}
          </span>
          <button
            type="button"
            onClick={handleNext}
            disabled={currentPage >= totalPages}
            className={cn(
              "inline-flex items-center rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
              currentPage >= totalPages
                ? "border-[var(--border-subtle)] text-[var(--text-muted)] cursor-not-allowed opacity-50"
                : "border-[var(--border-subtle)] text-[var(--text-primary)] hover:bg-[var(--surface-tint)]",
            )}
          >
            Next
          </button>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)]">Jump to page</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            value={jumpInput}
            onChange={(e) => setJumpInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleJump();
            }}
            className="w-16 rounded-md border border-[var(--border-subtle)] bg-[var(--surface-base)] px-2 py-1 text-xs text-[var(--text-primary)] text-center tabular-nums outline-none focus:border-[var(--gold)]"
          />
          <button
            type="button"
            onClick={handleJump}
            className="inline-flex items-center rounded-md border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-tint)] transition-colors"
          >
            Go
          </button>
        </div>
      </div>
    </Surface>
  );
}
