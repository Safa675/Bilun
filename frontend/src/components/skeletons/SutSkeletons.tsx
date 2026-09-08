"use client";

import { DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";

function SkeletonBars({ count, widths }: { count: number; widths?: string[] }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="skeleton skeleton-line"
          style={{ width: widths?.[index] ?? (index % 2 === 0 ? "100%" : "72%") }}
        />
      ))}
    </div>
  );
}

function SkeletonCardGrid({ count }: { count: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton skeleton-card h-28" />
      ))}
    </div>
  );
}

function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <DataTable className="overflow-hidden">
      <tbody>
        <tr>
          <td colSpan={4} className="border-0 p-0">
            <div className="space-y-3 p-4">
              <div className="grid grid-cols-4 gap-3">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="skeleton skeleton-line h-4" />
                ))}
              </div>
              {Array.from({ length: rows }).map((_, index) => (
                <div key={index} className="grid grid-cols-4 gap-3">
                  {Array.from({ length: 4 }).map((__, cellIndex) => (
                    <div key={cellIndex} className="skeleton skeleton-line h-4" />
                  ))}
                </div>
              ))}
            </div>
          </td>
        </tr>
      </tbody>
    </DataTable>
  );
}

export function SutAnalyticsShellSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="skeleton skeleton-card h-10 w-40" />
        ))}
      </div>
      <Surface variant="base" padding="lg">
        <SkeletonBars count={2} widths={["30%", "55%"]} />
        <div className="mt-5">
          <SkeletonCardGrid count={3} />
        </div>
        <div className="mt-5 skeleton skeleton-block h-72" />
      </Surface>
    </div>
  );
}

export function SutPatientAnalyticsSkeleton({ patientId }: { patientId?: string | null }) {
  const t = useT();
  return (
    <div className="space-y-5">
      <Surface variant="base" padding="lg">
        <SkeletonBars count={2} widths={["22%", "48%"]} />
      </Surface>
      <Surface variant="base" padding="lg">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
          {patientId
            ? t("common.skeleton.patientAnalyticsWithId", { patientId })
            : t("common.skeleton.patientAnalytics")}
        </p>
        <div className="mt-3">
          <SkeletonCardGrid count={3} />
        </div>
        <div className="mt-5 skeleton skeleton-block h-80" />
      </Surface>
    </div>
  );
}

export function SutOptimizerShellSkeleton() {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="skeleton skeleton-card h-10 w-44" />
        ))}
      </div>
      <SkeletonCardGrid count={4} />
      <div className="skeleton skeleton-block h-96" />
    </div>
  );
}

export function SutAlertTableSkeleton() {
  return (
    <div className="space-y-5">
      <SkeletonCardGrid count={4} />
      <Surface variant="base" padding="lg">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="skeleton skeleton-card h-11 w-72" />
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="skeleton skeleton-card h-9 w-24" />
            ))}
          </div>
        </div>
        <div className="mt-5">
          <SkeletonTable rows={6} />
        </div>
      </Surface>
    </div>
  );
}

export function SutReferenceSectionSkeleton({ title }: { title: string }) {
  return (
    <Surface variant="base" padding="lg">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
        {title}
      </p>
      <div className="mt-4">
        <SkeletonBars count={2} widths={["28%", "52%"]} />
      </div>
      <div className="mt-5">
        <SkeletonTable rows={5} />
      </div>
    </Surface>
  );
}
