"use client";

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
    <div className="frost-table-wrap overflow-hidden rounded-2xl">
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
    </div>
  );
}

export function SutAnalyticsShellSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex gap-3 flex-wrap">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="skeleton skeleton-card h-10 w-40" />
        ))}
      </div>
      <div className="frost-panel rounded-2xl p-5">
        <SkeletonBars count={2} widths={["30%", "55%"]} />
        <div className="mt-5">
          <SkeletonCardGrid count={3} />
        </div>
        <div className="mt-5 skeleton skeleton-block h-72" />
      </div>
    </div>
  );
}

export function SutPatientAnalyticsSkeleton({ patientId }: { patientId?: string | null }) {
  return (
    <div className="space-y-5">
      <div className="frost-card p-6">
        <SkeletonBars count={2} widths={["22%", "48%"]} />
      </div>
      <div className="frost-card p-6">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {patientId ? `Loading patient ${patientId}` : "Loading patient analytics"}
        </p>
        <div className="mt-3">
          <SkeletonCardGrid count={3} />
        </div>
        <div className="mt-5 skeleton skeleton-block h-80" />
      </div>
    </div>
  );
}

export function SutExposureSkeleton() {
  return (
    <div className="frost-panel rounded-2xl p-5">
      <SkeletonBars count={2} widths={["24%", "44%"]} />
      <div className="mt-5">
        <SkeletonCardGrid count={3} />
      </div>
      <div className="mt-5 skeleton skeleton-block h-72" />
    </div>
  );
}

export function SutOptimizerShellSkeleton() {
  return (
    <div className="space-y-5">
      <div className="flex gap-3 flex-wrap">
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
      <div className="frost-panel rounded-2xl p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="skeleton skeleton-card h-11 w-72" />
          <div className="flex gap-2 flex-wrap">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="skeleton skeleton-card h-9 w-24" />
            ))}
          </div>
        </div>
        <div className="mt-5">
          <SkeletonTable rows={6} />
        </div>
      </div>
    </div>
  );
}

export function SutReferenceSectionSkeleton({ title }: { title: string }) {
  return (
    <div className="frost-panel rounded-2xl p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
      <div className="mt-4">
        <SkeletonBars count={2} widths={["28%", "52%"]} />
      </div>
      <div className="mt-5">
        <SkeletonTable rows={5} />
      </div>
    </div>
  );
}

export function SutBillingReportSkeleton({ patientId }: { patientId?: string | null }) {
  return (
    <div className="space-y-6">
      <div className="frost-panel rounded-3xl p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">
          {patientId ? `Loading ${patientId}` : "Loading billing report"}
        </p>
        <div className="mt-4">
          <SkeletonBars count={2} widths={["35%", "58%"]} />
        </div>
        <div className="mt-5">
          <SkeletonCardGrid count={3} />
        </div>
      </div>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="frost-panel rounded-2xl p-5">
          <SkeletonBars count={1} widths={["30%"]} />
          <div className="mt-4">
            <SkeletonTable rows={4} />
          </div>
        </div>
      ))}
    </div>
  );
}
