"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface PreFlightDocItem {
  id: string;
  patientId: string;
  claimId: string;
  ruleCode: string;
  docTitle: string;
  category: "pathology" | "radiology" | "epicrisis" | "report";
  categoryLabel: string;
  mandateSource: string;
  importance: "high" | "medium";
  description: string;
  status: "verified" | "pending";
}

const DEMO_PREFLIGHT_DOCS: PreFlightDocItem[] = [
  {
    id: "pfd-1",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    ruleCode: "ORTAK-17",
    docTitle: "EK-2/C Ameliyat Notu & Hizmet Detayı",
    category: "epicrisis",
    categoryLabel: "Cerrahi Rapor",
    mandateSource: "Fatura İnceleme ORTAK-17 · SUT EK-2/C",
    importance: "high",
    description: "EK-2/C listesindeki işlemler için ameliyat seyrini ve kesi adımlarını içeren detaylı ameliyat notu zorunludur.",
    status: "verified",
  },
  {
    id: "pfd-2",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    ruleCode: "ORTAK-21",
    docTitle: "Biyopsi ve Patoloji Raporu",
    category: "pathology",
    categoryLabel: "Patoloji",
    mandateSource: "Fatura İnceleme ORTAK-21",
    importance: "high",
    description: "Cerrahi müdahalelerde çıkarılan doku/parça için patoloji raporu dosya ekinde bulunmalıdır.",
    status: "verified",
  },
  {
    id: "pfd-3",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    ruleCode: "ORTOPEDİ-6",
    docTitle: "Pre-Op & Post-Op Radyoloji Grafileri",
    category: "radiology",
    categoryLabel: "Radyoloji",
    mandateSource: "Fatura İnceleme ORTOPEDİ-6",
    importance: "high",
    description: "Ortopedik protez ve implant ameliyatlarında operasyon öncesi ve sonrası grafiler Teletıp sisteminde bulunmalıdır.",
    status: "verified",
  },
  {
    id: "pfd-4",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    ruleCode: "ORTAK-27",
    docTitle: "Klinik Epikriz ve Günlük Hekim Vizit Takibi",
    category: "epicrisis",
    categoryLabel: "Epikriz",
    mandateSource: "Fatura İnceleme ORTAK-27",
    importance: "high",
    description: "Yatan hasta servis izlemleri, hekim vizitleri ve malzeme boyut/barkod tutanakları faturayla tam tutarlı olmalıdır.",
    status: "verified",
  },
];

export interface PreFlightDocsComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function PreFlightDocsCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: PreFlightDocsComplianceProps) {
  const [filterCat, setFilterCat] = useState<string>("all");

  const filteredItems = DEMO_PREFLIGHT_DOCS.filter((item) => {
    if (cohortFilterActive && !cohortPatientIds.has(item.patientId)) return false;
    if (filterCat !== "all" && item.category !== filterCat) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Gönderim Öncesi Evrak Skoru"
            value="%100 Hazır"
            hint="4 Kritik Evrak Doğrulandı"
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Fatura İnceleme Usul Esasları (FI)</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="success">ORTAK-17 (Ameliyat Notu)</Chip>
            <Chip variant="success">ORTAK-21 (Patoloji)</Chip>
            <Chip variant="success">ORTOPEDİ-6 (Grafiler)</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            SGK Fatura İnceleme Komisyonu örnekleme denetiminde aranan kanuni evraklar.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Geriye Dönük Kesinti Koruması</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              Eksik Evrak Cezası Engellendi
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Fatura kuryeye verilmeden önce klasör içeriği tam olarak onaylanır.
          </p>
        </Surface>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterCat("all")}
          className={cn("gap-1.5", filterCat === "all" && buttonActiveClass)}
        >
          Tüm Evraklar ({DEMO_PREFLIGHT_DOCS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterCat("pathology")}
          className={cn("gap-1.5", filterCat === "pathology" && buttonActiveClass)}
        >
          Patoloji Raporları
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterCat("radiology")}
          className={cn("gap-1.5", filterCat === "radiology" && buttonActiveClass)}
        >
          Pre/Post-Op Radyoloji
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterCat("epicrisis")}
          className={cn("gap-1.5", filterCat === "epicrisis" && buttonActiveClass)}
        >
          Epikriz & Vizit Notları
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>Hasta / Fatura</th>
            <th>Kural Kodu & Belge Adı</th>
            <th>Kategori</th>
            <th>Yasal Dayanak</th>
            <th>Evrak Açıklaması & Denetim Şartı</th>
            <th>Durum</th>
            <th className="text-right">İncele</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8 text-[var(--text-tertiary)]">
                Filtreye uygun gönderim evrak kaydı bulunamadı.
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
                  <div className="font-semibold text-[var(--text-primary)]">{item.ruleCode}</div>
                  <div className="text-[11px] text-[var(--text-secondary)]">{item.docTitle}</div>
                </td>
                <td>
                  <Chip variant="neutral">
                    {item.categoryLabel}
                  </Chip>
                </td>
                <td className="text-[var(--text-secondary)] font-mono text-[11px]">
                  {item.mandateSource}
                </td>
                <td className="text-[var(--text-secondary)] max-w-sm">
                  {item.description}
                </td>
                <td>
                  <Chip variant="success">
                    Doğrulandı
                  </Chip>
                </td>
                <td className="text-right">
                  <Link
                    href={buildSutBillingHref(item.patientId)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--gold)] hover:text-[var(--gold-hover)]"
                  >
                    Dosyaya Git <ArrowRight className="h-3 w-3" />
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
