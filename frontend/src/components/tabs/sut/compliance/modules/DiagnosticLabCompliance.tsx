"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface DiagnosticLabItem {
  id: string;
  patientId: string;
  claimId: string;
  testCode: string;
  testName: string;
  errorType: "duplicate" | "bundled" | "unsupported_dx" | "frequency_limit";
  errorLabel: string;
  sourceDoc: string;
  clauseCoord: string;
  recommendation: string;
}

const DEMO_LAB_ERRORS: DiagnosticLabItem[] = [
  {
    id: "lab-1",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0004",
    testCode: "901120",
    testName: "Glukoz (Açlık Kan Şekeri)",
    errorType: "duplicate",
    errorLabel: "Aynı Gün Mükerrer Tetkik",
    sourceDoc: "SUT El Kitabı Tablo 15",
    clauseCoord: "Tablo 15 Madde 4",
    recommendation: "Aynı poliklinik başvurusunda 2 saat arayla girilen mükerrer glukoz kaydını teke indirin.",
  },
  {
    id: "lab-2",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0002",
    testCode: "900550",
    testName: "Tam Kan Sayımı (Hemogram 18 Parametre)",
    errorType: "bundled",
    errorLabel: "Paket İçi Biyokimya",
    sourceDoc: "SUT §2.2.1",
    clauseCoord: "§2.2.1.B",
    recommendation: "Yatış günü yapılan rutin hemogram ameliyat paketi kapsamındadır, ayrıca faturalanamaz.",
  },
  {
    id: "lab-3",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0002",
    testCode: "908110",
    testName: "Genetik Panel / Moleküler Analiz",
    errorType: "unsupported_dx",
    errorLabel: "Desteklenmeyen Tanı Eşleşmesi",
    sourceDoc: "EK-2/B Tetkik Kılavuzu",
    clauseCoord: "EK-2/B Açıklamalar",
    recommendation: "Moleküler analiz için endikasyon uyumlu ICD-10 genetik/onkoloji alt tanı kodu girilmelidir.",
  },
];

export interface DiagnosticLabComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function DiagnosticLabCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: DiagnosticLabComplianceProps) {
  const [filterType, setFilterType] = useState<string>("all");

  const filteredItems = DEMO_LAB_ERRORS.filter((item) => {
    if (cohortFilterActive && !cohortPatientIds.has(item.patientId)) return false;
    if (filterType !== "all" && item.errorType !== filterType) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Laboratuvar & Tetkik Uyarıları"
            value={`${DEMO_LAB_ERRORS.length} Tetkik Hatası`}
            hint="Mükerrerlik & Paket Kapsamı"
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT El Kitabı Tablo 15 Dayanağı</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="neutral">Tablo 15 (24 Ayaktan Hata)</Chip>
            <Chip variant="neutral">EK-2/B Kuralları</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            Aynı gün tekrarlanan rutin biyokimya ve paket içi tahliller MEDULA tarafından otomatik kesilir.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Tanı / Tetkik Endikasyon Eşleşmesi</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              ICD-10 Kod Doğrulama
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Özel genetik ve immünolojik testlerde yetkili uzman hekim ve ICD-10 uyumu aranır.
          </p>
        </Surface>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("all")}
          className={cn("gap-1.5", filterType === "all" && buttonActiveClass)}
        >
          Tümü ({DEMO_LAB_ERRORS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("duplicate")}
          className={cn("gap-1.5", filterType === "duplicate" && buttonActiveClass)}
        >
          Mükerrer Tetkikler
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("bundled")}
          className={cn("gap-1.5", filterType === "bundled" && buttonActiveClass)}
        >
          Paket İçi Lab Sarfları
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("unsupported_dx")}
          className={cn("gap-1.5", filterType === "unsupported_dx" && buttonActiveClass)}
        >
          Tanı Uyumsuzluğu
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>Hasta / Fatura</th>
            <th>Tetkik Kodu & Adı</th>
            <th>Hata Türü & Dayanak</th>
            <th>SUT / Rehber Maddesi</th>
            <th>Düzeltici Öneri</th>
            <th className="text-right">İncele</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center py-8 text-[var(--text-tertiary)]">
                Filtreye uygun laboratuvar uyarısı bulunamadı.
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
                  <div className="font-semibold text-[var(--text-primary)]">{item.testCode}</div>
                  <div className="max-w-xs truncate text-[11px] text-[var(--text-secondary)]">{item.testName}</div>
                </td>
                <td>
                  <div className="flex flex-col items-start gap-1">
                    <Chip variant="warning">
                      {item.errorLabel}
                    </Chip>
                    <span className="text-[10px] text-[var(--text-tertiary)]">
                      {item.sourceDoc}
                    </span>
                  </div>
                </td>
                <td className="font-mono text-[var(--text-primary)]">
                  {item.clauseCoord}
                </td>
                <td className="text-[var(--text-secondary)] max-w-sm">
                  {item.recommendation}
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
