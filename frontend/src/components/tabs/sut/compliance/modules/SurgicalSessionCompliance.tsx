"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface SurgicalSessionItem {
  id: string;
  patientId: string;
  claimId: string;
  sessionDate: string;
  procedures: string;
  appliedModifier: string;
  normativeModifier: string;
  impactTry: number;
  status: "warning" | "optimal";
  clauseCoord: string;
  detail: string;
}

const DEMO_SURGICAL_SESSIONS: SurgicalSessionItem[] = [
  {
    id: "surg-1",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sessionDate: "2024-10-11",
    procedures: "614340 (Primer Ameliyat) + 614350 (İkincil Kesi Ameliyatı)",
    appliedModifier: "%100 + %100 (Hatalı)",
    normativeModifier: "%100 (Ana İşlem) + %50 (Farklı Kesi)",
    impactTry: 4350.00,
    status: "warning",
    clauseCoord: "SUT §2.4.1",
    detail: "Aynı seansta yapılan farklı kesi işlemlerinde 2. işlem %50 katsayısıyla fatura edilmelidir.",
  },
  {
    id: "surg-2",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0005",
    sessionDate: "2023-06-22",
    procedures: "618250 (Majör Cerrahi) + 618260 (Aynı Kesi Revizyon)",
    appliedModifier: "%100 (Optimal)",
    normativeModifier: "%100 + %30 (Aynı Kesi)",
    impactTry: 0,
    status: "optimal",
    clauseCoord: "SUT §2.4.2",
    detail: "Aynı kesi üzerinden yapılan ek girişimler SUT kuralına uygun olarak %30 çarpanıyla puanlanmıştır.",
  },
];

export interface SurgicalSessionComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function SurgicalSessionCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: SurgicalSessionComplianceProps) {
  const [filter, setFilter] = useState<string>("all");

  const filteredItems = DEMO_SURGICAL_SESSIONS.filter((item) => {
    if (cohortFilterActive && !cohortPatientIds.has(item.patientId)) {
      return false;
    }
    if (filter === "all") return true;
    return item.status === filter;
  });

  const warningCount = DEMO_SURGICAL_SESSIONS.filter((i) => i.status === "warning").length;

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Seans Katsayı İhlali Riski"
            value={`${warningCount} Seans`}
            hint="Çoklu Cerrahi Katsayı Uyumsuzluğu"
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT Cerrahi Kuralları</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="neutral">SUT §2.4 (Seans Oranları)</Chip>
            <Chip variant="neutral">%100 + %50 + %30 Kuralı</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            Aynı seansta çoklu cerrahide en yüksek puanlı işlem %100, ikincisi %50, diğerleri %30 faturalandırılır.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Anestezi ve Kesi Ayrımı</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              Farklı Kesi Doğrulandı
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Epikrizdeki cerrahi kesi giriş yerleri ile faturadaki katsayılar otomatik eşleştirilir.
          </p>
        </Surface>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilter("all")}
          className={cn("gap-1.5", filter === "all" && buttonActiveClass)}
        >
          Tüm Cerrahi Seanslar ({DEMO_SURGICAL_SESSIONS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilter("warning")}
          className={cn("gap-1.5", filter === "warning" && buttonActiveClass)}
        >
          Katsayı Hataları ({warningCount})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilter("optimal")}
          className={cn("gap-1.5", filter === "optimal" && buttonActiveClass)}
        >
          Uyumlu Seanslar ({DEMO_SURGICAL_SESSIONS.length - warningCount})
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>Hasta / Fatura</th>
            <th>Seans Tarihi & Ameliyatlar</th>
            <th>Uygulanan Katsayı</th>
            <th>Mevzuat Katsayısı</th>
            <th>Durum & SUT Maddesi</th>
            <th>Denetim Açıklaması</th>
            <th className="text-right">İncele</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8 text-[var(--text-tertiary)]">
                Filtreye uygun seans kaydı bulunamadı.
              </td>
            </tr>
          ) : (
            filteredItems.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link
                    href={buildSutBillingHref(item.patientId)}
                    className="font-semibold text-slate-950 hover:text-[var(--gold-hover)]"
                  >
                    {item.patientId}
                  </Link>
                  <div className="text-[10px] text-[var(--text-tertiary)]">{item.claimId}</div>
                </td>
                <td>
                  <div className="font-semibold text-[var(--text-primary)]">{item.sessionDate}</div>
                  <div className="max-w-xs truncate text-[11px] text-[var(--text-secondary)]">{item.procedures}</div>
                </td>
                <td className="text-[var(--text-secondary)]">
                  {item.appliedModifier}
                </td>
                <td className="font-medium text-[var(--text-primary)]">
                  {item.normativeModifier}
                </td>
                <td>
                  <div className="flex flex-col items-start gap-1">
                    <Chip
                      variant={item.status === "warning" ? "warning" : "success"}
                    >
                      {item.status === "warning" ? "Katsayı Hatası" : "Uyumlu"}
                    </Chip>
                    <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
                      {item.clauseCoord}
                    </span>
                  </div>
                </td>
                <td className="text-[var(--text-secondary)] max-w-sm">
                  {item.detail}
                </td>
                <td className="text-right">
                  <Link
                    href={buildSutBillingHref(item.patientId)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                  >
                    Düzelt <ArrowRight className="h-3 w-3" />
                  </Link>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </DataTable>
    </div>
  );
}
