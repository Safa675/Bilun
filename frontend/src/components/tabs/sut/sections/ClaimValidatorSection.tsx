"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { theme } from "@/lib/theme";
import { validateSutClaim, getSutProcedureInfo } from "@/lib/api/sut";
import type {
  SutMaterialItem,
  SutClaimRequest,
  SutValidationResult,
  SutProcedureInfo,
  SutProcedureEntry,
  SutViolation,
  SutMaterialEstimate,
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

export function ClaimValidatorSection() {
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
    const validMaterials = materials.filter((m) => m.name.trim() !== "");
    if (validMaterials.length === 0) {
      setError("Add at least one material with a name.");
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
      const res = await validateSutClaim(claim, { signal: controller.signal });
      if (!controller.signal.aborted) {
        setResult(res);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      if (abortRef.current === controller) {
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [materials, claimId, procedureCode]);

  useEffect(() => {
    return () => { abortRef.current?.abort(); };
  }, []);

  return (
    <div className="space-y-5">
      <Surface variant="base" padding="lg">
        <h3 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: ACCENT_LOCAL }}>
          Claim Details
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Claim ID</label>
            <input type="text" value={claimId} onChange={(e) => setClaimId(e.target.value)} className="sut-input" placeholder="CLM-001" />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Procedure Code</label>
            <input type="text" value={procedureCode} onChange={(e) => setProcedureCode(e.target.value)} className="sut-input" placeholder="e.g. 520.021" />
            {shouldShowProcedureLookup && procLookupLoading && (
              <p className="mt-1 text-xs" style={{ color: "#94A3B8" }}>Looking up...</p>
            )}
            {shouldShowProcedureLookup && !procLookupLoading && procInfo && procInfo.entry && procInfo.match_type !== "prefix_search" && (
              <p className="mt-1 text-xs font-medium" style={{ color: theme.accent }}>
                {procInfo.entry.name}
                {procInfo.entry.price_try > 0 && (
                  <span style={{ color: "#94A3B8", fontWeight: 400 }}>{" "}({fmtTRY2(procInfo.entry.price_try)})</span>
                )}
                {procInfo.match_type === "prefix_stripped" && (
                  <span style={{ color: "#94A3B8", fontWeight: 400 }}>{" "}(matched without P prefix)</span>
                )}
              </p>
            )}
            {shouldShowProcedureLookup && !procLookupLoading && procInfo && procInfo.match_type === "prefix_search" && procInfo.candidates.length > 0 && (
              <div className="mt-1.5 space-y-0.5">
                <p className="text-xs" style={{ color: "#94A3B8" }}>
                  {procInfo.candidates.length} matching procedure{procInfo.candidates.length > 1 ? "s" : ""}:
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
              <p className="mt-1 text-xs" style={{ color: "#B45309" }}>No matching procedure found. Try the full 6-digit SUT code.</p>
            )}
          </div>
        </div>

        <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>Materials</h3>

        <div className="space-y-2">
          {materials.map((mat, idx) => (
            <div key={idx} className="grid gap-2 items-end" style={{ gridTemplateColumns: "1fr 120px 80px 36px" }}>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Name</label>}
                <input type="text" value={mat.name} onChange={(e) => updateMaterial(idx, "name", e.target.value)} className="sut-input" placeholder="e.g. Stent, Enjektör" />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Price (TRY)</label>}
                <input type="number" value={mat.unit_price || ""} onChange={(e) => updateMaterial(idx, "unit_price", Number(e.target.value))} className="sut-input" placeholder="0.00" min="0" step="0.01" />
              </div>
              <div>
                {idx === 0 && <label className="block text-xs font-medium mb-1" style={{ color: "#71717A" }}>Qty</label>}
                <input type="number" value={mat.quantity || ""} onChange={(e) => updateMaterial(idx, "quantity", Number(e.target.value))} className="sut-input" placeholder="1" min="1" />
              </div>
              <div>
                {idx === 0 && <span className="block text-xs mb-1">&nbsp;</span>}
                <button type="button" onClick={() => removeMaterial(idx)} className="sut-btn-icon" title="Remove" disabled={materials.length <= 1}>✕</button>
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 mt-4">
          <button type="button" onClick={addMaterial} className="sut-btn-secondary">+ Add Material</button>
          <button type="button" onClick={handleValidate} disabled={loading} className="sut-btn-primary">
            {loading ? "Validating..." : "Validate Claim"}
          </button>
        </div>
      </Surface>

      {error && (
        <Surface variant="soft" padding="md">
          <Chip variant="danger">{error}</Chip>
        </Surface>
      )}

      {result && <ValidationResultPanel result={result} />}
    </div>
  );
}

function ValidationResultPanel({ result }: { result: SutValidationResult }) {
  const statusColor = result.is_valid ? theme.accent : "#B91C1C";
  const statusLabel = result.is_valid ? "VALID" : "INVALID";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard label="Status" value={statusLabel} valueColor={statusColor} />
        <KpiCard label="Claim Total" value={fmtTRY2(result.total_claim_amount)} />
        <KpiCard label="Potential Savings" value={fmtTRY2(result.total_savings_try)} valueColor="#B45309" />
        <KpiCard label="Violations" value={fmtNum(result.violations.length)} valueColor={result.violations.length > 0 ? "#B91C1C" : theme.accent} />
      </div>

      {result.violations.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>Rule Violations</h3>
          <div className="space-y-2">
            {result.violations.map((v, i) => (
              <ViolationRow key={i} violation={v} />
            ))}
          </div>
        </Surface>
      )}

      {result.material_estimates.length > 0 && (
        <Surface variant="base" padding="lg">
          <h3 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: ACCENT_LOCAL }}>Material Cost Estimates</h3>
          <DataTable>
              <thead>
                <tr>
                  <th className="text-left">Material</th>
                  <th className="text-right tabular-nums">Unit Price</th>
                  <th className="text-right tabular-nums">Qty</th>
                  <th className="text-right tabular-nums">Total</th>
                  <th className="text-center">Reimbursable</th>
                  <th className="text-center">Bundled</th>
                  <th className="text-left">Source</th>
                </tr>
              </thead>
              <tbody>
                {result.material_estimates.map((m, i) => (
                  <MaterialEstimateRow key={i} estimate={m} />
                ))}
              </tbody>
          </DataTable>
        </Surface>
      )}

      <div className="text-xs text-right" style={{ color: "#A1A1AA" }}>
        Validated in {result.validation_time_ms.toFixed(1)}ms &middot; {result.summary}
      </div>
    </div>
  );
}

function ViolationRow({ violation }: { violation: SutViolation }) {
  const sev = SEVERITY_COLORS[violation.severity] ?? SEVERITY_COLORS.info;
  return (
    <div className="rounded-xl p-3 flex items-start gap-3" style={{ background: sev.bg, border: `1px solid ${sev.border}` }}>
      <span className="inline-block rounded-md px-2 py-0.5 text-xs font-bold uppercase shrink-0 mt-0.5" style={{ background: sev.border, color: sev.text }}>
        {getSutSeverityLabel(violation.severity)}
      </span>
      <div className="min-w-0">
        <div className="text-sm font-semibold" style={{ color: "#1A1A1A" }}>{violation.material_name}</div>
        <div className="text-xs mt-0.5" style={{ color: "#71717A" }}>{violation.message}</div>
        {violation.savings_try > 0 && (
          <div className="text-xs mt-1 font-medium" style={{ color: "#B45309" }}>Potential saving: {fmtTRY2(violation.savings_try)}</div>
        )}
      </div>
    </div>
  );
}

function MaterialEstimateRow({ estimate }: { estimate: SutMaterialEstimate }) {
  return (
    <tr>
      <td className="text-left">
        <div className="text-sm font-medium" style={{ color: "#1A1A1A" }}>{estimate.material_name}</div>
        {estimate.material_code && <div className="text-xs" style={{ color: "#A1A1AA" }}>{estimate.material_code}</div>}
      </td>
      <td className="text-right text-sm" style={{ color: "#71717A" }}>{fmtTRY2(estimate.unit_price)}</td>
      <td className="text-right text-sm" style={{ color: "#71717A" }}>{estimate.quantity}</td>
      <td className="text-right text-sm font-semibold" style={{ color: "#1A1A1A" }}>{fmtTRY2(estimate.total_price)}</td>
      <td className="text-center"><StatusPill ok={estimate.is_reimbursable} yesLabel="Yes" noLabel="No" /></td>
      <td className="text-center"><StatusPill ok={!estimate.is_bundled} yesLabel="No" noLabel="Bundled" invertColor /></td>
      <td className="text-left text-xs" style={{ color: "#A1A1AA" }}>
        {estimate.source}
        {estimate.notes && <span className="block text-xs italic">{estimate.notes}</span>}
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
