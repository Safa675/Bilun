"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { theme } from "@/lib/theme";
import { validateSutClaim, getSutProcedureInfo } from "@/lib/api/sut";
import type {
  SutMaterialItem,
  SutClaimRequest,
  SutDrugContext,
  SutValidationResult,
  SutProcedureInfo,
  SutProcedureEntry,
  SutViolation,
  SutMaterialLine,
} from "@/lib/api/sut";
import {
  ACCENT_LOCAL,
  fmtNum,
  fmtTRY2,
  KpiCard,
  SEVERITY_COLORS,
  EMPTY_MATERIAL,
} from "../shared";
import { getSutSeverityLabel } from "@/lib/sutLabels";
import { Chip, DataTable, Surface } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translateValidationMessage, translateValidationSummary } from "@/lib/apiMessages";
import { MaterialBundlingScopeNotice } from "@/components/sut/MaterialBundlingScopeNotice";
import { SpecialtyProseScopeNotice } from "@/components/sut/SpecialtyProseScopeNotice";

export function ClaimValidatorSection() {
  const t = useT();
  const [claimId, setClaimId] = useState("CLM-001");
  const [procedureCode, setProcedureCode] = useState("");
  const [materials, setMaterials] = useState<SutMaterialItem[]>([{ ...EMPTY_MATERIAL }]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SutValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [procInfo, setProcInfo] = useState<SutProcedureInfo | null>(null);
  const [procLookupLoading, setProcLookupLoading] = useState(false);
  const [procNotFound, setProcNotFound] = useState(false);
  const procAbortRef = useRef<AbortController | null>(null);
  const normalizedProcedureCode = procedureCode.trim().replace(/[\s.]/g, "");
  const shouldShowProcedureLookup = normalizedProcedureCode.length >= 3;

  // §4.2 drug indication context (optional — toggled by user for drug claims)
  const [drugContextEnabled, setDrugContextEnabled] = useState(false);
  const [drugIcd10, setDrugIcd10] = useState("");
  const [drugPrescriber, setDrugPrescriber] = useState("");
  const [drugReportPresent, setDrugReportPresent] = useState<string>("");

  useEffect(() => {
    if (!shouldShowProcedureLookup) {
      procAbortRef.current?.abort();
      return;
    }

    const timer = setTimeout(async () => {
      procAbortRef.current?.abort();
      const controller = new AbortController();
      procAbortRef.current = controller;
      setProcLookupLoading(true);
      setProcNotFound(false);
      setProcInfo(null);

      try {
        const info = await getSutProcedureInfo(normalizedProcedureCode, { signal: controller.signal });
        if (!controller.signal.aborted) {
          setProcInfo(info);
          setProcNotFound(false);
          setProcLookupLoading(false);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!controller.signal.aborted) {
          setProcInfo(null);
          setProcNotFound(true);
          setProcLookupLoading(false);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      procAbortRef.current?.abort();
    };
  }, [normalizedProcedureCode, shouldShowProcedureLookup]);

  const addMaterial = useCallback(() => {
    setMaterials((prev) => [...prev, { ...EMPTY_MATERIAL }]);
  }, []);

  const removeMaterial = useCallback((idx: number) => {
    setMaterials((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const updateMaterial = useCallback((idx: number, field: keyof SutMaterialItem, value: string | number) => {
    setMaterials((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, [field]: value } : m))
    );
  }, []);

  const handleValidate = useCallback(async () => {
    // A material is submittable when it has a name (drives bundling/exclusion
    // rules) OR a SUT code (drives exact EK-3 pricing). The backend needs at
    // least one of the two to produce a meaningful line.
    const validMaterials = materials.filter(
      (m) => m.name.trim() !== "" || (m.code ?? "").trim() !== "",
    );
    if (validMaterials.length === 0) {
      setError(t("sections.claimValidator.errors.addAtLeastOneMaterial"));
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const claim: SutClaimRequest = {
        claim_id: claimId || "CLM-001",
        procedure_code: procedureCode || "GENERIC",
        materials: validMaterials,
      };
      // Attach drug_context only when the user enabled it and filled at least
      // the ICD-10. The backend runs §4.2.14.C + §4.2.33 checks when present.
      if (drugContextEnabled && drugIcd10.trim()) {
        const ctx: SutDrugContext = {
          primary_icd10: drugIcd10.trim(),
          prescriber_specialty: drugPrescriber.trim(),
        };
        if (drugReportPresent === "yes") ctx.board_report_present = true;
        else if (drugReportPresent === "no") ctx.board_report_present = false;
        claim.drug_context = ctx;
      }
      const res = await validateSutClaim(claim, { signal: controller.signal });
      if (!controller.signal.aborted) {
        setResult(res);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : t("sections.claimValidator.errors.validationFailed"));
    } finally {
      if (abortRef.current === controller) {
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [materials, claimId, procedureCode, drugContextEnabled, drugIcd10, drugPrescriber, drugReportPresent, t]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  return (
    <div className="space-y-5">
      <MaterialBundlingScopeNotice compact />
      <SpecialtyProseScopeNotice compact />
      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
          {t("sections.claimValidator.claimDetails")}
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.claimId")}</label>
            <input type="text" value={claimId} onChange={(e) => setClaimId(e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.claimIdPlaceholder")} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.procedureCode")}</label>
            <input type="text" value={procedureCode} onChange={(e) => setProcedureCode(e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.procedureCodePlaceholder")} />
            {shouldShowProcedureLookup && procLookupLoading && (
              <p className="mt-1 text-xs" style={{ color: "#94A3B8" }}>{t("sections.claimValidator.lookingUp")}</p>
            )}
            {shouldShowProcedureLookup && !procLookupLoading && procInfo && procInfo.entry && procInfo.match_type !== "prefix_search" && (
              <p className="mt-1 text-xs font-medium" style={{ color: theme.accent }}>
                {procInfo.entry.name}
                {procInfo.entry.price_try > 0 && (
                  <span style={{ color: "#94A3B8", fontWeight: 400 }}>{" "}({fmtTRY2(procInfo.entry.price_try)})</span>
                )}
                {procInfo.match_type === "prefix_stripped" && (
                  <span style={{ color: "#94A3B8", fontWeight: 400 }}>{" "}{t("sections.claimValidator.matchedWithoutPPrefix")}</span>
                )}
              </p>
            )}
            {shouldShowProcedureLookup && !procLookupLoading && procInfo && procInfo.match_type === "prefix_search" && procInfo.candidates.length > 0 && (
              <div className="mt-1.5 space-y-0.5">
                <p className="text-xs" style={{ color: "#94A3B8" }}>
                  {t("sections.claimValidator.matchingProcedures", {
                    count: procInfo.candidates.length,
                    ...(getModuleLocale() === "en"
                      ? { plural: procInfo.candidates.length > 1 ? "s" : "" }
                      : {}),
                  })}
                </p>
                {procInfo.candidates.map((c: SutProcedureEntry) => (
                  <button
                    key={c.code}
                    type="button"
                    className="block w-full text-left text-xs px-2 py-1 rounded hover:bg-white/5 transition-colors"
                    style={{ color: theme.accent }}
                    onClick={() => setProcedureCode(c.code)}
                  >
                    <span className="font-mono font-medium">{c.code}</span>
                    <span className="text-[var(--text-muted)]">{" — "}</span>
                    <span>{c.name}</span>
                    {c.price_try > 0 && (
                      <span style={{ color: "#94A3B8" }}>{" "}({fmtTRY2(c.price_try)})</span>
                    )}
                  </button>
                ))}
              </div>
            )}
            {shouldShowProcedureLookup && !procLookupLoading && procNotFound && (
              <p className="mt-1 text-xs" style={{ color: "#B45309" }}>{t("sections.claimValidator.noMatchingProcedure")}</p>
            )}
          </div>
        </div>

        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>{t("sections.claimValidator.materials")}</h3>

        <div className="space-y-2">
          {materials.map((mat, idx) => (
            <div key={idx} className="grid gap-2 items-end" style={{ gridTemplateColumns: "1fr 1fr 120px 80px 36px" }}>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.name")}</label>}
                <input type="text" value={mat.name} onChange={(e) => updateMaterial(idx, "name", e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.namePlaceholder")} />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.code")}</label>}
                <input type="text" value={mat.code ?? ""} onChange={(e) => updateMaterial(idx, "code", e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.codePlaceholder")} />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.priceTry")}</label>}
                <input type="number" value={mat.unit_price || ""} onChange={(e) => updateMaterial(idx, "unit_price", Number(e.target.value))} className="sut-input" placeholder={t("sections.claimValidator.pricePlaceholder")} min="0" step="0.01" />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.qty")}</label>}
                <input type="number" value={mat.quantity || ""} onChange={(e) => updateMaterial(idx, "quantity", Number(e.target.value))} className="sut-input" placeholder={t("sections.claimValidator.qtyPlaceholder")} min="1" />
              </div>
              <div>
                {idx === 0 && <span className="block text-xs mb-1">&nbsp;</span>}
                <button type="button" onClick={() => removeMaterial(idx)} className="sut-btn-icon" title={t("sections.claimValidator.remove")} disabled={materials.length <= 1}>✕</button>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-[var(--r-md)] border border-[var(--border-subtle)]">
          <button
            type="button"
            onClick={() => setDrugContextEnabled((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-left"
          >
            <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: ACCENT_LOCAL }}>
              {t("sections.claimValidator.drugContext.title")}
            </span>
            <span className="text-[10px]" style={{ color: "#94A3B8" }}>
              {drugContextEnabled ? "−" : "+"}
            </span>
          </button>
          {drugContextEnabled && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 px-3 pb-3 pt-1 border-t border-[var(--border-subtle)]">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.drugContext.icd10")}</label>
                <input type="text" value={drugIcd10} onChange={(e) => setDrugIcd10(e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.drugContext.icd10Placeholder")} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.drugContext.prescriber")}</label>
                <input type="text" value={drugPrescriber} onChange={(e) => setDrugPrescriber(e.target.value)} className="sut-input" placeholder={t("sections.claimValidator.drugContext.prescriberPlaceholder")} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.drugContext.boardReport")}</label>
                <select value={drugReportPresent} onChange={(e) => setDrugReportPresent(e.target.value)} className="sut-input">
                  <option value="">{t("sections.claimValidator.drugContext.unknown")}</option>
                  <option value="yes">{t("sections.claimValidator.drugContext.present")}</option>
                  <option value="no">{t("sections.claimValidator.drugContext.absent")}</option>
                </select>
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button type="button" onClick={addMaterial} className="sut-btn-secondary">{t("sections.claimValidator.addMaterial")}</button>
          <button type="button" onClick={handleValidate} disabled={loading} className="sut-btn-primary">
            {loading ? t("sections.claimValidator.validating") : t("sections.claimValidator.validateClaim")}
          </button>
        </div>
      </Surface>

      {error && (
        <Surface variant="soft" padding="md">
          <Chip variant="danger">{error}</Chip>
        </Surface>
      )}

      {result && <ValidationResultPanel result={result} t={t} />}
    </div>
  );
}

function ValidationResultPanel({ result, t }: { result: SutValidationResult; t: ReturnType<typeof useT> }) {
  const statusColor = result.is_valid ? theme.accent : "#B91C1C";
  const statusLabel = result.is_valid ? t("sections.claimValidator.statusValid") : t("sections.claimValidator.statusInvalid");

  return (
    <div className="space-y-4">
      <MaterialBundlingScopeNotice scope={result.coverage_scope} />
      <SpecialtyProseScopeNotice scope={result.specialty_coverage_scope} />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label={t("sections.claimValidator.kpi.status")} value={statusLabel} valueColor={statusColor} />
        <KpiCard label={t("sections.claimValidator.kpi.claimTotal")} value={fmtTRY2(result.total_claim_amount)} />
        <KpiCard label={t("sections.claimValidator.kpi.potentialSavings")} value={fmtTRY2(result.total_savings_try)} valueColor="#B45309" />
        <KpiCard label={t("sections.claimValidator.kpi.violations")} value={fmtNum(result.violations.length)} valueColor={result.violations.length > 0 ? "#B91C1C" : theme.accent} />
      </div>

      {result.violations.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>{t("sections.claimValidator.ruleViolations")}</h3>
          <div className="space-y-2">
            {result.violations.map((v, i) => (
              <ViolationRow key={i} violation={v} t={t} />
            ))}
          </div>
        </Surface>
      )}

      {result.material_lines.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>{t("sections.claimValidator.materialLines")}</h3>
          <DataTable>
              <thead>
                <tr>
                  <th className="text-left">{t("sections.claimValidator.table.material")}</th>
                  <th className="text-right tabular-nums">{t("sections.claimValidator.table.unitPrice")}</th>
                  <th className="text-right tabular-nums">{t("sections.claimValidator.table.qty")}</th>
                  <th className="text-right tabular-nums">{t("sections.claimValidator.table.total")}</th>
                  <th className="text-center">{t("sections.claimValidator.table.reimbursable")}</th>
                  <th className="text-center">{t("sections.claimValidator.table.bundled")}</th>
                  <th className="text-left">{t("sections.claimValidator.table.source")}</th>
                </tr>
              </thead>
              <tbody>
                {result.material_lines.map((line, i) => (
                  <MaterialLineRow key={i} line={line} t={t} />
                ))}
              </tbody>
          </DataTable>
        </Surface>
      )}

      <div className="text-xs text-right" style={{ color: "#A1A1AA" }}>
        {t("sections.claimValidator.validatedIn", {
          ms: result.validation_time_ms.toFixed(1),
          summary: translateValidationSummary(result.summary),
        })}
      </div>
    </div>
  );
}

function ViolationRow({ violation, t }: { violation: SutViolation; t: ReturnType<typeof useT> }) {
  const sev = SEVERITY_COLORS[violation.severity] ?? SEVERITY_COLORS.info;
  return (
    <div className="rounded-xl p-3 flex items-start gap-3" style={{ background: sev.bg, border: `1px solid ${sev.border}` }}>
      <span className="inline-block rounded-md px-2 py-0.5 text-xs font-bold uppercase shrink-0 mt-0.5" style={{ background: sev.border, color: sev.text }}>
        {getSutSeverityLabel(violation.severity)}
      </span>
      <div className="min-w-0">
        <div className="text-sm font-semibold" style={{ color: "#1A1A1A" }}>{violation.material_name}</div>
        <div className="text-xs mt-0.5" style={{ color: "#71717A" }}>
          {translateValidationMessage(violation.message)}
        </div>
        {violation.savings_try > 0 && (
          <div className="text-xs mt-1 font-medium" style={{ color: "#B45309" }}>
            {t("sections.claimValidator.potentialSaving", { amount: fmtTRY2(violation.savings_try) })}
          </div>
        )}
      </div>
    </div>
  );
}

function MaterialLineRow({ line, t }: { line: SutMaterialLine; t: ReturnType<typeof useT> }) {
  return (
    <tr>
      <td className="text-left">
        <div className="text-sm font-medium" style={{ color: "#1A1A1A" }}>{line.material_name}</div>
        {line.material_code && <div className="text-xs" style={{ color: "#A1A1AA" }}>{line.material_code}</div>}
      </td>
      <td className="text-right text-sm" style={{ color: "#71717A" }}>{fmtTRY2(line.unit_price)}</td>
      <td className="text-right text-sm" style={{ color: "#71717A" }}>{line.quantity}</td>
      <td className="text-right text-sm font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(line.total_price)}</td>
      <td className="text-center"><StatusPill ok={line.is_reimbursable} yesLabel={t("sections.claimValidator.yes")} noLabel={t("sections.claimValidator.no")} /></td>
      <td className="text-center"><StatusPill ok={!line.is_bundled} yesLabel={t("sections.claimValidator.no")} noLabel={t("sections.claimValidator.bundledStatus")} invertColor /></td>
      <td className="text-left text-xs" style={{ color: "#A1A1AA" }}>
        {line.source}
        {line.exactness_status === "missing_exact_inputs" && (
          <span className="block text-xs italic">{t("sections.claimValidator.missingExactInputs")}</span>
        )}
        {line.notes && <span className="block text-xs italic">{line.notes}</span>}
      </td>
    </tr>
  );
}

function StatusPill({ ok, yesLabel, noLabel, invertColor }: { ok: boolean; yesLabel: string; noLabel: string; invertColor?: boolean }) {
  const isGood = invertColor ? !ok : ok;
  const bg = isGood ? theme.accentAlpha(0.12) : "rgba(185, 28, 28, 0.10)";
  const color = isGood ? theme.accent : "#B91C1C";
  const label = ok ? yesLabel : noLabel;
  return (
    <span className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold" style={{ background: bg, color }}>
      {label}
    </span>
  );
}
