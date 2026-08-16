"use client";

import { useState, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  COMPLIANCE_SUB_IDS,
  type ComplianceSubSection,
} from "@/lib/workspaceSubtabs";
import { useT } from "@/lib/i18n/useTranslations";
import { Surface, Chip } from "@/components/primitives";
import { ComplianceSubtabStrip } from "./ComplianceSubtabStrip";

// Modules
import { CopayExemptionCompliance } from "./modules/CopayExemptionCompliance";
import { SurchargeCompliance } from "./modules/SurchargeCompliance";
import { MaterialsCompliance } from "./modules/MaterialsCompliance";
import { PaymentMethodCompliance } from "./modules/PaymentMethodCompliance";
import { SurgicalSessionCompliance } from "./modules/SurgicalSessionCompliance";
import { DiagnosticLabCompliance } from "./modules/DiagnosticLabCompliance";
import { PreFlightDocsCompliance } from "./modules/PreFlightDocsCompliance";
import { MedulaPlaybookCompliance } from "./modules/MedulaPlaybookCompliance";

export interface SUTComplianceDashboardProps {
  cohortPatientIds: Set<string>;
  cohortFilterActive: boolean;
}

export function SUTComplianceDashboard({
  cohortPatientIds,
  cohortFilterActive,
}: SUTComplianceDashboardProps) {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const rawSubtab = (searchParams?.get("compTab") || searchParams?.get("subtab")) as ComplianceSubSection;
  const activeSubtab: ComplianceSubSection =
    rawSubtab && (COMPLIANCE_SUB_IDS as readonly string[]).includes(rawSubtab)
      ? rawSubtab
      : "exemptions";

  const handleSelectSubtab = (subtab: ComplianceSubSection) => {
    if (!pathname) return;
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.set("compTab", subtab);
    // Keep subtab in sync for generic tab linkers
    params.set("subtab", subtab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  const badgeCounts: Partial<Record<ComplianceSubSection, number>> = {
    materials: 6,
    payment_methods: 2,
    surgical_sessions: 1,
    diagnostics_lab: 3,
    pre_flight_docs: 4,
    medula_rejections: 4,
  };

  return (
    <div className="space-y-6">
      {/* Top Consolidated Audit Radar */}
      <Surface variant="base" padding="lg" className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-[var(--font-display)] text-xl font-medium tracking-tight text-[var(--text-primary)]">
                SUT Mevzuat ve Fatura Uyumluluk Merkezi
              </h2>
              <Chip variant="success">
                8 Boyutlu Denetim Aktif
              </Chip>
            </div>
            <p className="mt-1 text-xs text-[var(--text-secondary)] max-w-3xl">
              SGK Sağlık Uygulama Tebliği (SUT), 5510 Sayılı Kanun, ÜTS/TİTUBB kayıtları, SUT El Kitabı Tablo 15 ve Fatura İnceleme Usul Esasları kapsamında 360 derece kohort denetimi.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="text-[11px] font-medium text-[var(--text-tertiary)] block">
                SUT Uyumluluk Güvencesi
              </span>
              <span className="text-sm font-semibold text-emerald-400 font-mono tabular-nums">
                %98,4 Uyum
              </span>
            </div>
          </div>
        </div>

        {/* 4 Key Compliance Indicators */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-2 border-t border-[var(--border-subtle)]">
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)] block">Toplam Denetim Riski</span>
            <span className="text-base font-semibold text-rose-400 font-mono tabular-nums">
              ₺121.714,71
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)] block">Ön Onay / ÜTS Bekleyen</span>
            <span className="text-base font-semibold text-amber-400 font-mono tabular-nums">
              2 Protez İşlemi
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)] block">Muafiyet Kazanımı</span>
            <span className="text-base font-semibold text-emerald-400 font-mono tabular-nums">
              ₺599,28 / Hasta
            </span>
          </div>
          <div>
            <span className="text-[11px] text-[var(--text-tertiary)] block">Gönderim Evrak Hazırlığı</span>
            <span className="text-base font-semibold text-sky-400 font-mono tabular-nums">
              %100 Doğrulandı
            </span>
          </div>
        </div>
      </Surface>

      {/* 8-Subtab Navigation Strip */}
      <ComplianceSubtabStrip
        activeSubtab={activeSubtab}
        onSelectSubtab={handleSelectSubtab}
        badgeCounts={badgeCounts}
      />

      {/* Dynamic Module Rendering */}
      <div>
        {activeSubtab === "exemptions" && (
          <CopayExemptionCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "surcharge" && (
          <SurchargeCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "materials" && (
          <MaterialsCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "payment_methods" && (
          <PaymentMethodCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "surgical_sessions" && (
          <SurgicalSessionCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "diagnostics_lab" && (
          <DiagnosticLabCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "pre_flight_docs" && (
          <PreFlightDocsCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
        {activeSubtab === "medula_rejections" && (
          <MedulaPlaybookCompliance
            cohortPatientIds={cohortPatientIds}
            cohortFilterActive={cohortFilterActive}
          />
        )}
      </div>
    </div>
  );
}
