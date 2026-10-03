"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DrugMaterialInputs } from "./DrugMaterialInputs";
import { drugMaterialPayload, optionalCount } from "./drugInputs";
import { clinicalMissingInputLabel } from "./clinicalFields";
import { theme } from "@/lib/theme";
import { validateSutClaim, getSutProcedureInfo } from "@/lib/api/sut";
import type {
  SutMaterialItem,
  SutClaimRequest,
  SutDrugContext,
  SutValidationResult,
  SutProcedureInfo,
  SutProcedureEntry,
  SutValidationEvidence,
} from "@/lib/api/sut";
import {
  ACCENT_LOCAL,
  fmtNum,
  fmtTRY2,
  KpiCard,
  EMPTY_MATERIAL,
} from "../shared";
import { Chip, Surface, Button, inputClass } from "@/components/primitives";
import { useT } from "@/lib/i18n/useTranslations";
import { getModuleLocale } from "@/lib/i18n/localeModule";
import { translateValidationMessage } from "@/lib/apiMessages";
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
  const [drugServiceDate, setDrugServiceDate] = useState("");
  const [drugReportDuration, setDrugReportDuration] = useState<number | null>(null);

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
        materials: validMaterials.map(material => drugMaterialPayload(material, drugContextEnabled)),
      };
      // Enabled checks retain unknown diagnosis instead of silently disappearing.
      if (drugContextEnabled) {
        const ctx: SutDrugContext = {
          primary_icd10: drugIcd10.trim(),
          prescriber_specialty: drugPrescriber.trim(),
          report_duration_months: drugReportDuration,
          service_date: drugServiceDate || null,
          board_report_present: null,
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
  }, [materials, claimId, procedureCode, drugContextEnabled, drugIcd10, drugPrescriber, drugReportPresent, drugReportDuration, drugServiceDate, t]);

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
            <input type="text" value={claimId} onChange={(e) => setClaimId(e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.claimIdPlaceholder")} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.procedureCode")}</label>
            <input type="text" value={procedureCode} onChange={(e) => setProcedureCode(e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.procedureCodePlaceholder")} />
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
            <div key={idx} className="space-y-3">
            <div className="grid gap-2 items-end" style={{ gridTemplateColumns: "1fr 1fr 120px 80px 36px" }}>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.name")}</label>}
                <input type="text" value={mat.name} onChange={(e) => updateMaterial(idx, "name", e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.namePlaceholder")} />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.code")}</label>}
                <input type="text" value={mat.code ?? ""} onChange={(e) => updateMaterial(idx, "code", e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.codePlaceholder")} />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.priceTry")}</label>}
                <input type="number" value={mat.unit_price || ""} onChange={(e) => updateMaterial(idx, "unit_price", Number(e.target.value))} className={inputClass} placeholder={t("sections.claimValidator.pricePlaceholder")} min="0" step="0.01" />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.qty")}</label>}
                <input type="number" value={mat.quantity || ""} onChange={(e) => updateMaterial(idx, "quantity", Number(e.target.value))} className={inputClass} placeholder={t("sections.claimValidator.qtyPlaceholder")} min="1" />
              </div>
              <div>
                {idx === 0 && <span className="block text-xs mb-1">&nbsp;</span>}
                <Button variant="icon" onClick={() => removeMaterial(idx)} title={t("sections.claimValidator.remove")} disabled={materials.length <= 1}>✕</Button>
              </div>
            </div>
            {drugContextEnabled && <DrugMaterialInputs material={mat} onChange={patch => setMaterials(previous => previous.map((row, i) => i === idx ? { ...row, ...patch } : row))} />}
            </div>
          ))}
        </div>

        <div className="mt-4 rounded-[var(--r-md)] border border-[var(--border-subtle)]">
          <button
            type="button"
            aria-expanded={drugContextEnabled}
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
                <input type="text" value={drugIcd10} onChange={(e) => setDrugIcd10(e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.drugContext.icd10Placeholder")} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.drugContext.prescriber")}</label>
                <input type="text" value={drugPrescriber} onChange={(e) => setDrugPrescriber(e.target.value)} className={inputClass} placeholder={t("sections.claimValidator.drugContext.prescriberPlaceholder")} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>{t("sections.claimValidator.drugContext.boardReport")}</label>
                <select value={drugReportPresent} onChange={(e) => setDrugReportPresent(e.target.value)} className={inputClass}>
                  <option value="">{t("sections.claimValidator.drugContext.unknown")}</option>
                  <option value="yes">{t("sections.claimValidator.drugContext.present")}</option>
                  <option value="no">{t("sections.claimValidator.drugContext.absent")}</option>
                </select>
              </div>
              <label className="text-xs">{t("sections.claimValidator.drugContext.serviceDate")}
                <input aria-label={t("sections.claimValidator.drugContext.serviceDate")} type="date" className={inputClass}
                  value={drugServiceDate} onChange={e => setDrugServiceDate(e.target.value)} />
              </label>
              <label className="text-xs">{t("sections.claimValidator.drugContext.reportDuration")}
                <input aria-label={t("sections.claimValidator.drugContext.reportDuration")} type="number" min="0" step="1" className={inputClass}
                  value={drugReportDuration ?? ""} placeholder={t("sections.claimValidator.drugContext.unknown")}
                  onChange={e => setDrugReportDuration(optionalCount(e.target.value))} />
              </label>
              <p className="text-xs text-[var(--text-muted)] sm:col-span-3">{t("sections.claimValidator.drugContext.unknownHint")}</p>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 mt-4">
          <Button variant="secondary" onClick={addMaterial}>{t("sections.claimValidator.addMaterial")}</Button>
          <Button variant="primary" onClick={handleValidate} disabled={loading}>
            {loading ? t("sections.claimValidator.validating") : t("sections.claimValidator.validateClaim")}
          </Button>
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

export function ValidationResultPanel({ result, t }: { result: SutValidationResult; t: ReturnType<typeof useT> }) {
  const confirmed = result.validation_status === "violations_found";
  const incomplete = result.validation_status !== "no_violations_in_evaluated_scope" && !confirmed;
  const statusColor = confirmed ? "#B91C1C" : incomplete ? "#B45309" : theme.accent;
  // A client retained during rollback can receive the prior v2 API shape.
  const materialApplicability = result.material_applicability ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label={t("sections.claimValidator.kpi.status")} value={t("sections.claimValidator.validationStatus." + result.validation_status)} valueColor={statusColor} />
        <KpiCard label={t("sections.claimValidator.kpi.violations")} value={fmtNum(result.violations.length)} valueColor={confirmed ? "#B91C1C" : undefined} />
        <KpiCard label={t("sections.claimValidator.kpi.advisories")} value={fmtNum(result.advisories.length)} />
        <KpiCard label={t("sections.claimValidator.kpi.unresolved")} value={fmtNum(result.coverage.unresolved_count)} valueColor={result.coverage.unresolved_count > 0 ? "#B45309" : undefined} />
      </div>
      {result.violations.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold mb-3">{t("sections.claimValidator.ruleViolations")}</h3>
          <div className="space-y-3">
            {result.violations.map((row) => <ValidationEvidenceRow key={row.evidence_id} evidence={row} confirmed t={t} />)}
          </div>
        </Surface>
      )}
      {result.advisories.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold mb-3">{t("sections.claimValidator.advisories")}</h3>
          <div className="space-y-3">
            {result.advisories.map((row) => <ValidationEvidenceRow key={row.evidence_id} evidence={row} t={t} />)}
          </div>
        </Surface>
      )}
      {materialApplicability.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold mb-3">{t("sections.claimValidator.annexAssessment.title")}</h3>
          <div className="space-y-3">
            {materialApplicability.map((material) => (
              <div key={material.material_id} className="text-xs">
                <div className="font-medium">{material.material_name || material.material_code || material.material_id}</div>
                {(["ek3b1", "ek3b2"] as const).map((annex) => (
                  <div key={annex} style={{ color: "#71717A" }}>
                    {annex === "ek3b1" ? "EK-3B-1" : "EK-3B-2"}: {t(
                      material[annex].matched === true
                        ? "sections.claimValidator.annexAssessment.matched"
                        : material[annex].matched === false
                          ? "sections.claimValidator.annexAssessment.notMatched"
                          : "sections.claimValidator.annexAssessment.unresolved"
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p className="text-xs mt-3" style={{ color: "#71717A" }}>
            {t("sections.claimValidator.annexAssessment.disclaimer")}
          </p>
        </Surface>
      )}
      <div className="text-xs text-right" style={{ color: "#71717A" }}>
        {t("sections.claimValidator.coverageSummary", {
          checked: result.coverage.evaluation_count,
          unresolved: result.coverage.unresolved_count,
        })}
      </div>
    </div>
  );
}

function unresolvedAnnexReviewKey(evidence: SutValidationEvidence): string | null {
  if (evidence.disposition !== "review_only" || evidence.source_status !== "historical_match_unverified") {
    return null;
  }
  if (evidence.rule === "bundling" && evidence.reason === "ek3b1_exception_setting_and_exact_line_proof_required") {
    return "sections.claimValidator.annexReview.ek3b1";
  }
  if (evidence.rule === "exclusion" && evidence.reason === "ek3b2_exception_applicability_and_exact_line_proof_required") {
    return "sections.claimValidator.annexReview.ek3b2";
  }
  return null;
}

function ValidationEvidenceRow({ evidence, confirmed = false, t }: {
  evidence: SutValidationEvidence;
  confirmed?: boolean;
  t: ReturnType<typeof useT>;
}) {
  const informational = evidence.disposition === "information_only" || evidence.disposition === "permission_or_instruction";
  const annexReviewKey = unresolvedAnnexReviewKey(evidence);
  return (
    <div className="flex items-start gap-3">
      <Chip variant={confirmed ? "danger" : informational ? "neutral" : "warning"}>
        {t(confirmed ? "sections.claimValidator.confirmedFinding" : informational ? "sections.claimValidator.information" : "sections.claimValidator.reviewCandidate")}
      </Chip>
      <div className="min-w-0">
        <div className="text-sm font-medium">{evidence.material_name}</div>
        <div className="text-xs mt-1" style={{ color: "#71717A" }}>
          {translateValidationMessage(evidence.message)}
        </div>
        {(evidence.missing_inputs?.length ?? 0) > 0 && (
          <div className="text-xs mt-1" style={{ color: "#B45309" }}>
            {t("sections.claimValidator.drugContext.missingInputs")}: {evidence.missing_inputs!.map(field => {
              const clinicalLabel = clinicalMissingInputLabel(field, t);
              if (clinicalLabel) return clinicalLabel;
              const [key, detail] = field.split(".");
              const label = ["service_date", "drug_claim_date"].includes(key) ? "serviceDate" : key;
              const detailLabel = key === "prior_therapies" && detail === "drug_or_class"
                ? t("sections.claimValidator.drugContext.therapy") : detail;
              return `${t(`sections.claimValidator.drugContext.${label}`)}${detailLabel ? ` (${detailLabel})` : ""}`;
            }).join(", ")}
          </div>
        )}
        {annexReviewKey && (
          <div className="text-xs mt-1" style={{ color: "#B45309" }}>
            {t("sections.claimValidator.annexUnconfirmed")}: {t(annexReviewKey)}
          </div>
        )}
      </div>
    </div>
  );
}
