"use client";

import { useState } from "react";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { cn } from "@/lib/cn";

interface MedulaPlaybookItem {
  id: string;
  errorCode: string;
  errorTitle: string;
  frequencyRank: number;
  rootCause: string;
  proactiveFix: string;
  automationStatus: "automated" | "semi_automated" | "manual";
}

const MEDULA_PLAYBOOK_ITEMS: MedulaPlaybookItem[] = [
  {
    id: "med-1",
    errorCode: "1001",
    errorTitle: "Hastanın Provizyon Türü ile İşlem Uyumsuz",
    frequencyRank: 1,
    rootCause: "Acil provizyonlu hastaya elektif cerrahi veya poliklinik tetkiki faturalandırılması.",
    proactiveFix: "Takip numarası türü (Acil / Yeşil Alan / Normal) ile hizmet branş kodu otomatik eşitlenir.",
    automationStatus: "automated",
  },
  {
    id: "med-2",
    errorCode: "1054",
    errorTitle: "Malzeme ÜTS Tekil Bildirim Kaydı Bulunamadı",
    frequencyRank: 2,
    rootCause: "İmplant veya protezin Sağlık Bakanlığı Ürün Takip Sistemi tekil barkodunun sisteme işlenmemesi.",
    proactiveFix: "Fatura kapatılmadan önce ÜTS API servisi üzerinden tekil bildirim sorgusu tetiklenir.",
    automationStatus: "automated",
  },
  {
    id: "med-3",
    errorCode: "1072",
    errorTitle: "Zorunlu Sağlık Kurulu Raporu Eksik",
    frequencyRank: 3,
    rootCause: "Yüksek tutarlı protez ve ilaçlar için e-rapor kaydının MEDULA'da bulunmaması.",
    proactiveFix: "SUT §3.1.2 ve EK-4/D kapsamında geçerli rapor numarası faturaya eklenir.",
    automationStatus: "semi_automated",
  },
  {
    id: "med-4",
    errorCode: "1099",
    errorTitle: "Mükerrer veya Paket İçi İşlem Bildirimi",
    frequencyRank: 4,
    rootCause: "Ameliyat paketine dahil sarf veya tetkikin ayrıca sisteme gönderilmesi.",
    proactiveFix: "EK-3B-1 ve EK-2/C paket unbundling filtresi mükerrer kalemleri otomatik ayıklar.",
    automationStatus: "automated",
  },
];

export interface MedulaPlaybookComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function MedulaPlaybookCompliance({
  cohortPatientIds: _cohortPatientIds,
  cohortFilterActive: _cohortFilterActive,
}: MedulaPlaybookComplianceProps) {
  const [filter, setFilter] = useState<string>("all");

  const filteredItems = MEDULA_PLAYBOOK_ITEMS.filter((item) => {
    if (filter === "all") return true;
    return item.automationStatus === filter;
  });

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="MEDULA Otomatik Red Engelleme"
            value="%98 Önleme"
            hint="4 Sık Karşılaşılan Red Deseni"
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>MEDULA Kılavuzu & Hata Kodları</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="danger">Kod 1001</Chip>
            <Chip variant="danger">Kod 1054</Chip>
            <Chip variant="warning">Kod 1072</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            MEDULA red kodları fatura oluşturulurken proaktif olarak yakalanır ve çözülür.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>Otomasyon Düzeyi</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              Kural Motoru Aktif
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Hatalı kayıtlar MEDULA'ya gitmeden önce faturacıya doğrudan düzeltme sunar.
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
          Tüm Red Kılavuzu ({MEDULA_PLAYBOOK_ITEMS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilter("automated")}
          className={cn("gap-1.5", filter === "automated" && buttonActiveClass)}
        >
          Otomatik Çözülenler
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilter("semi_automated")}
          className={cn("gap-1.5", filter === "semi_automated" && buttonActiveClass)}
        >
          Kullanıcı Onayı Gerekenler
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>MEDULA Hata Kodu</th>
            <th>Red Başlığı & Açıklaması</th>
            <th>Temel Sebep (Root Cause)</th>
            <th>Bilun Proaktif Çözümü (Playbook)</th>
            <th>Otomasyon</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.map((item) => (
            <tr key={item.id}>
              <td className="font-mono font-bold text-rose-500">
                KOD {item.errorCode}
              </td>
              <td className="font-medium text-[var(--text-primary)]">
                {item.errorTitle}
              </td>
              <td className="text-[var(--text-secondary)] max-w-xs">
                {item.rootCause}
              </td>
              <td className="text-emerald-600 max-w-sm font-medium">
                {item.proactiveFix}
              </td>
              <td>
                <Chip
                  variant={item.automationStatus === "automated" ? "success" : "warning"}
                >
                  {item.automationStatus === "automated" ? "Otomatik Düzeltme" : "Yarı Otomatik"}
                </Chip>
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </div>
  );
}
