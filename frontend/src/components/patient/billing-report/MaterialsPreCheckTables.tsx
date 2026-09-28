"use client";

import type { BillingActionReport } from "@/lib/domains/sut";
import { useT } from "@/lib/i18n/useTranslations";
import { fmtDate } from "@/lib/i18n/formatters";
import { translateApiText } from "@/lib/apiMessages";
import { Eyebrow, Surface } from "@/components/primitives";
import { fmtTRY2 } from "@/components/tabs/sut/shared";
import { WRAPPED_HEADER_STYLE, TableWrap } from "./shared";

type MaterialsData = BillingActionReport["materials"];

export function MaterialPreAuthorizationTable({ rows }: { rows: NonNullable<MaterialsData["pre_auth_required"]> }) {
  const t = useT();
  return (
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
          {rows.map((material, index) => (
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
  );
}

export function MaterialMiatIntervalTable({ rows }: { rows: NonNullable<MaterialsData["miat_interval_violations"]> }) {
  const t = useT();
  return (
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
          {rows.map((material, index) => (
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
  );
}

export function MaterialMiatCatalogTable({ rows }: { rows: NonNullable<MaterialsData["miat_restricted"]> }) {
  const t = useT();
  return (
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
          {rows.map((material, index) => (
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
  );
}

export function BundledMaterialTable({ rows }: { rows: NonNullable<MaterialsData["bundled_separate_billing"]> }) {
  const t = useT();
  return (
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
          {rows.map((material, index) => (
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
  );
}

export function MaterialProseViolationsTable({ rows }: { rows: NonNullable<MaterialsData["prose_bundling_violations"]> }) {
  const t = useT();
  return (
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
          {rows.map((hit, index) => (
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
  );
}

export function MaterialSpecialtyProseTable({ rows }: { rows: NonNullable<MaterialsData["specialty_prose_violations"]> }) {
  const t = useT();
  return (
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
          {rows.map((hit, index) => (
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
  );
}

export function MaterialKdvReviewTable({ rows }: { rows: NonNullable<MaterialsData["kdv_price_reviews"]> }) {
  const t = useT();
  return (
    <div className="space-y-2">
      <p className="text-xs font-bold uppercase tracking-wider" style={{ color: "#B45309" }}>
        {t("billing.materials.rows")}
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
          {rows.map((row, index) => (
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
  );
}

export function MaterialCeilingBenchmarks({ entries }: { entries: [string, number][] }) {
  const t = useT();
  return (
    <Surface variant="base" padding="md">
      <Eyebrow>{t("billing.materials.ceilingEyebrow")}</Eyebrow>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {entries.map(([specialty, amount]) => (
          <Surface key={specialty} variant="soft" padding="sm">
            <Eyebrow>{specialty}</Eyebrow>
            <p className="mt-1 font-mono text-sm font-semibold tabular-nums text-[var(--text-primary)]">
              {fmtTRY2(amount)}
            </p>
          </Surface>
        ))}
      </div>
    </Surface>
  );
}
