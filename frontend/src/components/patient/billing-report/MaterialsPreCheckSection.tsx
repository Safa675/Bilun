"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDate } from "@/lib/i18n/formatters";
import { translateApiText } from "@/lib/apiMessages";
import { isExactOutput } from "@/lib/sutExactness";
import { MaterialBundlingScopeNotice } from "@/components/sut/MaterialBundlingScopeNotice";
import { SpecialtyProseScopeNotice } from "@/components/sut/SpecialtyProseScopeNotice";
import { ExactnessBlock as ExactnessNotice, Eyebrow, Surface } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, BillingSectionShell, TableWrap } from "./shared";

export function MaterialsPreCheckSection({ materialsData }: { materialsData: BillingActionReport["materials"] }) {
  const t = useT();
  const ceilingEntries = Object.entries(materialsData.gazette_ceiling_by_specialty);
  const materialsExact = isExactOutput(materialsData);
  const intervalViolations = materialsData.miat_interval_violations ?? [];
  const bundledLines = materialsData.bundled_separate_billing ?? [];
  const proseViolations = materialsData.prose_bundling_violations ?? [];
  const specialtyProseViolations = materialsData.specialty_prose_violations ?? [];
  const kdvPriceReviews = materialsData.kdv_price_reviews ?? [];
  const hasExactListData =
    materialsData.pre_auth_required.length > 0 ||
    materialsData.miat_restricted.length > 0 ||
    intervalViolations.length > 0 ||
    bundledLines.length > 0 ||
    proseViolations.length > 0 ||
    specialtyProseViolations.length > 0 ||
    kdvPriceReviews.length > 0;
  const hasAnyData = hasExactListData || ceilingEntries.length > 0;

  if (!hasAnyData && materialsExact) {
    return null;
  }

  return (
    <BillingSectionShell id="materials-pre-check" title={t("billing.materials.title")}>
      <div className="space-y-4">
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          {t("billing.materials.advisoryFootnote")}
        </p>
        <MaterialBundlingScopeNotice scope={materialsData.coverage_scope} compact />
        <SpecialtyProseScopeNotice scope={materialsData.specialty_coverage_scope} compact />
        {!materialsExact && (
          <ExactnessNotice block={materialsData} fallback={t("billing.materials.unavailable")} />
        )}
        {materialsData.pre_auth_required.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              {t("billing.materials.preAuth")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.pre_auth_required.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {intervalViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B91C1C" }}>
              {t("billing.materials.miatIntervalViolations")}
            </p>
            <TableWrap minWidth={920}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.lastUse")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.miatPeriod")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {intervalViolations.map((material, index) => (
                  <tr key={`miat-int-${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td>{material.last_use_date ? fmtDate(material.last_use_date) : "—"}</td>
                    <td>{material.miat_period}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {materialsData.miat_restricted.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#64748B" }}>
              {t("billing.materials.miatCatalog")}
            </p>
            <TableWrap minWidth={900}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.miatPeriod")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {materialsData.miat_restricted.map((material, index) => (
                  <tr key={`${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td>{material.miat_period}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {bundledLines.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#D97706" }}>
              {t("billing.materials.bundledSeparate")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {bundledLines.map((material, index) => (
                  <tr key={`bundled-${material.sut_code}-${index}`}>
                    <td className="font-mono text-xs">{material.sut_code}</td>
                    <td>{material.material_name}</td>
                    <td className="num-col tabular-nums text-right">{fmtTRY2(material.price_try)}</td>
                    <td>{material.note ? translateApiText(material.note) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {proseViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B45309" }}>
              {t("billing.materials.proseBundling")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {proseViolations.map((hit, index) => (
                  <tr key={`prose-${hit.material_code ?? "row"}-${hit.rule_id ?? "rule"}-${index}`}>
                    <td className="font-mono text-xs">{hit.material_code || "—"}</td>
                    <td>{hit.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {hit.risk_amount != null ? fmtTRY2(hit.risk_amount) : "—"}
                    </td>
                    <td>{hit.message ? translateApiText(hit.message) : (hit.rule_id || "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {specialtyProseViolations.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#7C3AED" }}>
              {t("billing.materials.specialtyProse")}
            </p>
            <TableWrap minWidth={820}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazettePrice")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {specialtyProseViolations.map((hit, index) => (
                  <tr
                    key={`specialty-prose-${hit.material_code ?? "row"}-${hit.rule_id ?? "rule"}-${index}`}
                  >
                    <td className="font-mono text-xs">{hit.material_code || "—"}</td>
                    <td>{hit.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {hit.risk_amount != null ? fmtTRY2(hit.risk_amount) : "—"}
                    </td>
                    <td>{hit.message ? translateApiText(hit.message) : (hit.rule_id || "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {kdvPriceReviews.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B45309" }}>
              {t("billing.materials.kdvPriceReviews")}
            </p>
            <TableWrap minWidth={920}>
              <thead>
                <tr>
                  <th>{t("billing.materials.sutCode")}</th>
                  <th>{t("billing.materials.material")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.billedAmount")}</th>
                  <th className="num-col tabular-nums text-right" style={WRAPPED_HEADER_STYLE}>{t("billing.materials.gazetteCeiling")}</th>
                  <th style={WRAPPED_HEADER_STYLE}>{t("billing.materials.note")}</th>
                </tr>
              </thead>
              <tbody>
                {kdvPriceReviews.map((row, index) => (
                  <tr key={`kdv-${row.sut_code ?? "row"}-${index}`}>
                    <td className="font-mono text-xs">{row.sut_code || "—"}</td>
                    <td>{row.material_name || "—"}</td>
                    <td className="num-col tabular-nums text-right">
                      {row.billed_try != null ? fmtTRY2(row.billed_try) : "—"}
                    </td>
                    <td className="num-col tabular-nums text-right">
                      {row.gazette_ceiling_try != null ? fmtTRY2(row.gazette_ceiling_try) : "—"}
                    </td>
                    <td>{row.note ? translateApiText(row.note) : (row.kdv_applied ? t("billing.materials.kdvApplied") : "—")}</td>
                  </tr>
                ))}
              </tbody>
            </TableWrap>
          </div>
        )}

        {!materialsExact && ceilingEntries.length > 0 && (
          <p className="text-sm text-[var(--text-secondary)]">
            {t("billing.materials.partialBenchmarkNotice")}
          </p>
        )}

        {ceilingEntries.length > 0 && (
          <Surface variant="base" padding="md">
            <Eyebrow>{t("billing.materials.ceilingEyebrow")}</Eyebrow>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {ceilingEntries.map(([specialty, amount]) => (
                <Surface key={specialty} variant="soft" padding="sm">
                  <Eyebrow>{specialty}</Eyebrow>
                  <p className="mt-1 font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
                    {fmtTRY2(amount)}
                  </p>
                </Surface>
              ))}
            </div>
          </Surface>
        )}
      </div>
    </BillingSectionShell>
  );
}
