"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { fmtTRY } from "../../shared";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface MaterialRiskItem {
  id: string;
  patientId: string;
  claimId: string;
  sutCode: string;
  materialName: string;
  billedTry: number;
  clauseCoord: string;
  riskType: "prior_auth" | "uts_unregistered" | "unbundling" | "miat_limit" | "specialty_scope";
  riskLabel: string;
  detail: string;
}

const DEMO_MATERIAL_RISKS: MaterialRiskItem[] = [
  {
    id: "mat-1",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "OP1266",
    materialName: "DİRSEK ÜSTÜ AMPUTASYONU İÇİN MYOLEKTRİK KONTROLLÜ PROTEZİ 4 KANAL SİSTEM",
    billedTry: 129746.40,
    clauseCoord: "§3.1.2 / EK-3C-1",
    riskType: "prior_auth",
    riskLabel: "Ön Onay Eksikliği",
    detail: "SGK gönderiminden önce Sağlık Kurulu Raporu ve İl Müdürlüğü Tıbbi Uygunluk Onayı zorunludur.",
  },
  {
    id: "mat-2",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "OP1266",
    materialName: "DİRSEK ÜSTÜ AMPUTASYONU İÇİN MYOLEKTRİK KONTROLLÜ PROTEZİ 4 KANAL SİSTEM",
    billedTry: 129746.40,
    clauseCoord: "§3.1.1(2)",
    riskType: "uts_unregistered",
    riskLabel: "ÜTS Bildirim Eksik",
    detail: "Sağlık Bakanlığı Ürün Takip Sistemi (ÜTS) tekil hasta bildirimi tamamlanmamış.",
  },
  {
    id: "mat-3",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "AP4340",
    materialName: "DİZ APARATI",
    billedTry: 71286.96,
    clauseCoord: "§package_flag / EK-2C",
    riskType: "unbundling",
    riskLabel: "Pakete Dahil Sarf",
    detail: "Ameliyat paket fiyatına dahildir; faturada ayrı kalem olarak eklenmesi kesinti doğurur.",
  },
  {
    id: "mat-4",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "AP1260",
    materialName: "EL BİLEĞİ",
    billedTry: 3545.95,
    clauseCoord: "§3.1.2 / EK-2C",
    riskType: "unbundling",
    riskLabel: "Pakete Dahil Sarf",
    detail: "Paket bileşeni olarak işaretlenmiş ve ayrı faturalandırılmış (Unbundling riski).",
  },
  {
    id: "mat-5",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "DEMO-L44-SS1",
    materialName: "Deri taklidi yedek",
    billedTry: 250.00,
    clauseCoord: "§3.3.1(9)",
    riskType: "specialty_scope",
    riskLabel: "Yanık Dışı Kullanım",
    detail: "Yapay deri greftleri yalnızca tescilli Yanık Tedavi Merkezlerindeki yanık vakalarında ödenir.",
  },
  {
    id: "mat-6",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    sutCode: "DEMO-L44-W2",
    materialName: "Hidrojel yara nemlendirici",
    billedTry: 120.00,
    clauseCoord: "§3.3.1(10)",
    riskType: "specialty_scope",
    riskLabel: "Kurumca Karşılanmaz",
    detail: "Hidrojel/nemlendirici yara bakım ürünleri genel hastane pansuman gideri sayılır, ödenmez.",
  },
];

export interface MaterialsComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function MaterialsCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: MaterialsComplianceProps) {
  const [filterType, setFilterType] = useState<string>("all");

  const filteredItems = DEMO_MATERIAL_RISKS.filter((item) => {
    if (cohortFilterActive && !cohortPatientIds.has(item.patientId)) {
      return false;
    }
    if (filterType === "all") return true;
    return item.riskType === filterType;
  });

  const totalRiskTry = DEMO_MATERIAL_RISKS.reduce((acc, i) => acc + i.billedTry, 0);

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Toplam Tıbbi Malzeme Riski"
            value={fmtTRY(totalRiskTry)}
            hint={`${DEMO_MATERIAL_RISKS.length} Riskli Kalem Tespiti`}
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT & Bakanlık Dayanağı</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="danger">SUT §3.1.2 (Ön Onay)</Chip>
            <Chip variant="warning">ÜTS §3.1.1(2)</Chip>
            <Chip variant="neutral">MIAT §3.1.4</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            TİTUBB/ÜTS kaydı olmayan ve ön onayı alınmayan protezlerin faturası SGK tarafından tamamen kesilir.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Paket İçi (Unbundling) Koruması</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-red-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              EK-3B-1 / EK-2C Denetimi
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Paket ameliyat bedeline dahil sarfların mükerrer faturalandırılması önlenir.
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
          Tüm Malzeme Riskleri ({DEMO_MATERIAL_RISKS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("prior_auth")}
          className={cn("gap-1.5", filterType === "prior_auth" && buttonActiveClass)}
        >
          Ön Onay Bekleyenler
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("uts_unregistered")}
          className={cn("gap-1.5", filterType === "uts_unregistered" && buttonActiveClass)}
        >
          ÜTS / TİTUBB Eksikleri
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("unbundling")}
          className={cn("gap-1.5", filterType === "unbundling" && buttonActiveClass)}
        >
          Pakete Dahil / Unbundling
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterType("specialty_scope")}
          className={cn("gap-1.5", filterType === "specialty_scope" && buttonActiveClass)}
        >
          SUT Dışı Sarflar
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>Hasta / Fatura</th>
            <th>SUT Kodu & Malzeme Adı</th>
            <th>Fatura Tutarı (Risk)</th>
            <th>Risk Türü & SUT Maddesi</th>
            <th>Gerekçe ve Gerekli Aksiyon</th>
            <th className="text-right">İncele</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr>
              <td colSpan={6} className="text-center py-8 text-[var(--text-tertiary)]">
                Filtreye uygun riskli malzeme kaydı bulunamadı.
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
                  <div className="font-semibold text-[var(--text-primary)]">{item.sutCode}</div>
                  <div className="max-w-xs truncate text-[11px] text-[var(--text-secondary)]">
                    {item.materialName}
                  </div>
                </td>
                <td className="font-semibold text-rose-500 font-mono">
                  {fmtTRY(item.billedTry)}
                </td>
                <td>
                  <div className="flex flex-col items-start gap-1">
                    <Chip
                      variant={
                        item.riskType === "prior_auth" || item.riskType === "unbundling"
                          ? "danger"
                          : "warning"
                      }
                    >
                      {item.riskLabel}
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
