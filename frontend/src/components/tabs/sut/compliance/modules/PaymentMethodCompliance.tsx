"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Surface, Eyebrow, Stat, Chip, Button, buttonActiveClass, DataTable } from "@/components/primitives";
import { buildSutBillingHref } from "@/lib/constants";
import { cn } from "@/lib/cn";

interface PaymentMethodItem {
  id: string;
  patientId: string;
  claimId: string;
  procCode: string;
  procTitle: string;
  requiredMethod: string;
  currentMethod: string;
  status: "violation" | "compliant";
  clauseCoord: string;
  note: string;
}

const DEMO_PAYMENT_METHODS: PaymentMethodItem[] = [
  {
    id: "pm-1",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-002",
    procCode: "608550",
    procTitle: "Akciğer transplantasyonu, global",
    requiredMethod: "Tanıya Dayalı / DRG Paket",
    currentMethod: "Kalem İşlem (Fee-For-Service)",
    status: "violation",
    clauseCoord: "SUT §2.2.1.B-1.a",
    note: "608550 işlemi SUT §2.2.1.B-1.a uyarınca paket faturalandırma kullanmalıdır (kalem işlem kesinti doğurur).",
  },
  {
    id: "pm-2",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-003",
    procCode: "611240",
    procTitle: "Küçük kemik ve eklem amputasyonu, dezartikülasyonu",
    requiredMethod: "Tanıya Dayalı / DRG Paket",
    currentMethod: "Kalem İşlem (Fee-For-Service)",
    status: "violation",
    clauseCoord: "SUT §2.2.2(1)",
    note: "611240 işlemi §2.2.2(1) uyarınca zorunlu paket faturalandırma kuralına geçirilmelidir.",
  },
  {
    id: "pm-3",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-001",
    procCode: "P614340",
    procTitle: "Ortopedik Paket Cerrahi",
    requiredMethod: "Tanıya Dayalı / DRG Paket",
    currentMethod: "Tanıya Dayalı / DRG Paket",
    status: "compliant",
    clauseCoord: "SUT §2.2.2(1)",
    note: "F-001 talebi SUT §2.2.2(1)'e göre paket olarak doğru faturalandırılmış (Paket: ₺8.705,13).",
  },
  {
    id: "pm-4",
    patientId: "SENTETIK-HASTA-0001",
    claimId: "F-SENTETIK-HASTA-0001-005",
    procCode: "P618250",
    procTitle: "Majör Eklem Cerrahisi",
    requiredMethod: "Tanıya Dayalı / DRG Paket",
    currentMethod: "Tanıya Dayalı / DRG Paket",
    status: "compliant",
    clauseCoord: "SUT §2.2.2(1)",
    note: "F-005 talebi SUT §2.2.2(1)'e göre paket olarak doğru faturalandırılmış (Paket: ₺41.912,76).",
  },
];

export interface PaymentMethodComplianceProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function PaymentMethodCompliance({
  cohortPatientIds,
  cohortFilterActive,
}: PaymentMethodComplianceProps) {
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const filteredItems = DEMO_PAYMENT_METHODS.filter((item) => {
    if (cohortFilterActive && !cohortPatientIds.has(item.patientId)) {
      return false;
    }
    if (filterStatus === "all") return true;
    return item.status === filterStatus;
  });

  const violationCount = DEMO_PAYMENT_METHODS.filter((i) => i.status === "violation").length;

  return (
    <div className="space-y-5">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Surface variant="base" padding="md" className="space-y-1">
          <Stat
            label="Zorunlu Paket / DRG İhlalleri"
            value={`${violationCount} İhlal`}
            hint="Kalem işlem yerine Paket Faturalandırma Zorunlu"
          />
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>SUT Mevzuat Dayanağı</Eyebrow>
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <Chip variant="danger">SUT §2.2.1 (Tanıya Dayalı)</Chip>
            <Chip variant="neutral">SUT §2.2.2 (Zorunlu DRG)</Chip>
          </div>
          <p className="pt-2 text-xs text-[var(--text-tertiary)]">
            Transplantasyon ve majör cerrahilerde paket dışı kalem faturalama SGK denetiminde reddedilir.
          </p>
        </Surface>
        <Surface variant="base" padding="md" className="space-y-1">
          <Eyebrow>DRG Ayrıştırma (Unbundling) Koruması</Eyebrow>
          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              Otomatik Paket Dönüşümü
            </span>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Kalem bazlı işlemler tek tıkla mevzuata uygun paket koduna çevrilebilir.
          </p>
        </Surface>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterStatus("all")}
          className={cn("gap-1.5", filterStatus === "all" && buttonActiveClass)}
        >
          Tümü ({DEMO_PAYMENT_METHODS.length})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterStatus("violation")}
          className={cn("gap-1.5", filterStatus === "violation" && buttonActiveClass)}
        >
          Ödeme Yöntemi İhlalleri ({violationCount})
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="compact"
          onClick={() => setFilterStatus("compliant")}
          className={cn("gap-1.5", filterStatus === "compliant" && buttonActiveClass)}
        >
          Uyumlu Talepler ({DEMO_PAYMENT_METHODS.length - violationCount})
        </Button>
      </div>

      {/* Table */}
      <DataTable minWidth={950}>
        <thead>
          <tr>
            <th>Hasta / Fatura</th>
            <th>İşlem Kodu & Tanımı</th>
            <th>Mevcut Faturalama</th>
            <th>Mevzuatın Zorunlu Kıldığı Yöntem</th>
            <th>Durum & SUT Maddesi</th>
            <th>Açıklama ve Düzeltme</th>
            <th className="text-right">İncele</th>
          </tr>
        </thead>
        <tbody>
          {filteredItems.length === 0 ? (
            <tr>
              <td colSpan={7} className="text-center py-8 text-[var(--text-tertiary)]">
                Filtreye uygun ödeme yöntemi kaydı bulunamadı.
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
                  <div className="font-semibold text-[var(--text-primary)]">{item.procCode}</div>
                  <div className="max-w-xs truncate text-[11px] text-[var(--text-secondary)]">{item.procTitle}</div>
                </td>
                <td className="text-[var(--text-secondary)]">
                  {item.currentMethod}
                </td>
                <td className="font-medium text-[var(--text-primary)]">
                  {item.requiredMethod}
                </td>
                <td>
                  <div className="flex flex-col items-start gap-1">
                    <Chip
                      variant={item.status === "violation" ? "danger" : "success"}
                    >
                      {item.status === "violation" ? "Yöntem İhlali" : "Uyumlu"}
                    </Chip>
                    <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
                      {item.clauseCoord}
                    </span>
                  </div>
                </td>
                <td className="text-[var(--text-secondary)] max-w-sm">
                  {item.note}
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
