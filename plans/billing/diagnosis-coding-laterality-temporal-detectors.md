# Implementation Plan: Diagnosis Coding + Laterality + Temporal + Medula Codes

**Branch:** `feat/diagnosis-coding-detectors`
**Goal:** 4 parallel workstreams that add new detection capability to BILUN without touching shared files.

---

## Workstream A: Diagnosis Coding Quality (SB 12 Kategorisi)

**Files to create (no shared files touched):**
- `src/bilun/domain/prose_rules/diagnosis_coding_quality.py` (new detector)
- `tests/unit/domain/prose_rules/test_diagnosis_coding_quality.py` (new tests)

**What to encode:**

### A1. #12 "Never Principal" blocklist detector
ICD-10 codes that must NEVER be the primary/admitting diagnosis. When `primary_icd10` matches these patterns, emit a violation.

The blocklist (from SB 12 Kategorisi + TİG EK-3):
- **R-codes as principal** (R00-R99, symptoms/signs — a definitive diagnosis should exist)
- **Z-codes for personal history** (Z80-Z87 — history of, not active disease)
- **Z-codes for encounter status** (Z00-Z13 screening, Z32-Z36 pregnancy screening, Z39, Z40-Z43, Z45-Z49, Z50, Z51, Z71-Z76, Z85-Z87)
- **External cause codes** (V01-Y98 — injury causes, never the diagnosis itself)
- **Morphology codes** (M8000/0-M9979/1 — neoplasm morphology, not a diagnosis)
- **Specific never-principal codes:** O09 (pregnancy supervision), P00-P04 (newborn affected by maternal factors), Z48.0 (surgical aftercare), Z51.5 (encounter for rehabilitation), Z51.81 (dietary counseling)

Detector signature:
```python
def detect_never_principal_diagnosis(
    claims: list[ClaimHeader],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
```

Reads `ClaimHeader.primary_icd10`. Emits violation with `rule_id="never_principal_diagnosis_blocklist"`.

### A2. #2 Principal diagnosis ↔ procedure mismatch detector
When the principal diagnosis ICD-10 chapter is inconsistent with the billed procedure specialty, emit a warning.

Example mismatches:
- Primary diagnosis is mental health (F-codes) but procedures are orthopedic surgery (60xxxx)
- Primary diagnosis is pregnancy (O-codes) but procedures are cardiac (70xxxx)
- Primary diagnosis is injury (S/T) but procedures are routine screening

Implementation: map ICD-10 chapter prefixes to expected procedure code ranges, flag gross mismatches. Start conservative — only flag clearly impossible combinations (not "unusual but possible").

Detector signature:
```python
def detect_diagnosis_procedure_mismatch(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
```

### A3. #3 Unnecessary additional diagnosis detector
When an R-code symptom diagnosis is coded alongside a definitive diagnosis for the same body system, flag it as unnecessary.

Example: K35.8 (appendicitis, definitive) + R10.4 (abdominal pain, symptom) → the symptom is redundant.

Implementation: for each claim, check if there's a definitive diagnosis AND a symptom diagnosis in the same ICD-10 chapter. Conservative — start with obvious body-system overlaps.

Reads `PatientClaimContext.diagnoses` (tuple of `ClaimDiagnosis`).

**Tests (8-10 tests):**
- Never-principal: R-code as principal → violation
- Never-principal: Z85 (history of cancer) as principal → violation
- Never-principal: A definitive code (K35.8) as principal → no violation
- Dx-procedure mismatch: mental health dx + orthopedic procedure → warning
- Dx-procedure mismatch: consistent dx + procedure → no violation
- Unnecessary additional: definitive + symptom same chapter → warning
- Unnecessary additional: definitive + symptom different chapter → no violation

---

## Workstream B: sagSol Laterality Field

**Files to modify/create:**
- `src/bilun/domain/claims/models.py` — add `sag_sol: str = ""` field to `ProcedureClaimLine`
- `src/bilun/domain/prose_rules/laterality_validation.py` (new detector)
- `tests/unit/domain/prose_rules/test_laterality_validation.py` (new tests)

> **⚠️ CRITICAL PREREQUISITE — `sag_sol` is not ingested today.**
> Verified: the synthetic data generator, the claims loader, and the raw SUT
> parquets all lack `sag_sol` (it's a Medula claim-submission field, not an
> EK-2B catalog field). Adding the field is harmless (default `""`), but the
> detectors will **never fire on real data** unless the ingestion path
> populates it. Two options — pick one before building the detectors:
>
> **Option B-guard (honest-skip):** if every `sag_sol` on a context is empty,
> the detectors return `[]` (no violation) instead of flagging everything as
> "missing laterality." This mirrors the gap_closing honesty-guard pattern.
> Ship the detectors dormant; they activate once real `sag_sol` data flows.
>
> **Option B-pipeline (full fix):** extend the synthetic generator
> (`scripts/synthetic/gen/`) + the CSV/dict loader to populate `sag_sol` from
> the Medula `sagSol` column. Larger scope — defer to a separate task and use
> B-guard until then.

**What to do:**

### B1. Add field to data model
Add to `ProcedureClaimLine` dataclass (after `copay_rate_applicable`):
```python
    sag_sol: str = "",  # Medula sagSol: "1"=Sağ, "2"=Sol, "3"=Ayrım yok, ""=missing
```
Default empty string preserves all existing construction — no backwards breakage.

### B2. Laterality validation detector
Two detectors. **Both must implement the B-guard honest-skip** (see
prerequisite above): if every `sag_sol` value in the supplied
`procedure_lines` is empty, return `[]` immediately — this prevents a
false-positive flood on data sources that don't carry the field yet.

**#6 — Bilateral MR/CT billed without laterality:**
Codes that require laterality (MR, CT, USG of paired organs): when quantity=1 but `sag_sol` is empty or "3" (no distinction), flag it. The claim should either have `sag_sol="1"` or `"2"`, or two separate lines.

Laterality-required code prefixes: 801xxx (MR), 803xxx (CT) — specifically for paired organs (brain is single, knees are paired). Use a lookup of code prefixes that are paired-organ imaging.

**#17 — Missing laterality on bilateral-organ procedures:**
Surgical procedures on paired organs (eyes, ears, kidneys, lungs, extremities) where `sag_sol` is empty.

Detector signatures (both take the established `(claims, procedure_lines, *, claim_ids_with_procs=None)` shape):
```python
def detect_missing_laterality_imaging(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:

def detect_missing_laterality_surgery(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
```

**Tests (8-10 tests):**
- MR knee with sag_sol="" → violation (#6)
- MR knee with sag_sol="1" → no violation
- MR brain (single organ) → no violation (not paired)
- Cataract surgery with sag_sol="" → violation (#17)
- Cataract surgery with sag_sol="2" → no violation
- Appendectomy (non-paired) → no violation

**IMPORTANT constraint:** This is the ONLY workstream that touches `models.py`. No other agent should touch it.

---

## Workstream C: Temporal Overlap + LOS Density (Orhan #8 + #9)

> **Source citation needed:** the "#8 / #9" references are from Orhan's
> billing-audit list. Add the full document title + link to the rule-origin
> doc so the detector rationale is traceable.

**Files to create:**
- `src/bilun/domain/prose_rules/temporal_anomaly.py` (new detector)
- `tests/unit/domain/prose_rules/test_temporal_anomaly.py` (new tests)

**What to encode:**

### C1. #8 — Generic procedure time-overlap detector
When two procedures on the same claim have overlapping time windows (same `procedure_date` + high duration procedures that can't physically overlap), flag as suspicious.

Conservative approach: flag when a single physician has >N hours of billed procedures on the same date, or when two surgeries overlap (same date + both are surgical category + same specialty).

Use `group_procedure_lines_by_session` from `claim_utils.py` for date grouping.

Detector signature:
```python
def detect_procedure_time_overlap(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
```

### C2. #9 — LOS vs procedure density detector
When a patient has a 1-day stay but 5+ procedures, or conversely a 10-day stay with 0 procedures, flag as suspicious.

Implementation: compute `procedure_count / LOS_days` ratio. If ratio > 5 (too many procedures per day) or LOS > 3 days with 0 billable procedures (ghost stay), flag.

Reads `ClaimHeader.admission_date`, `discharge_date`, and `procedure_lines`.

Detector signature:
```python
def detect_los_procedure_density_anomaly(
    claims: list[ClaimHeader],
    procedure_lines: list[ProcedureClaimLine],
    *,
    claim_ids_with_procs: set[str] | None = None,
) -> list[dict[str, Any]]:
```

**Tests (8-10 tests):**
- 2 surgeries same date same specialty → time-overlap flag
- 1 surgery same date → no flag
- 5 procedures + 1-day stay → density flag
- 2 procedures + 3-day stay → no flag
- 0 procedures + 5-day stay → ghost stay flag
- Outpatient (no LOS) → no density check

**IMPORTANT constraint:** Do NOT touch `models.py`, `engine.py`, or any file another agent touches. Only create new files.

---

## Workstream D: Medula 0963-0968 Codes (quick win)

**Files to modify:**
- `data/medula/known_codes.json` — add 6 new codes
- `data/medula/rejection_playbook.json` — add 1-2 new templates

**What to do:**

### D1. Add 0963-0968 to known_codes.json
Codes from OHSAD/Medula Kılavuzu:
- `0963`: "{takipNo} nolu takip içinde {hizmetSunucuRefNo} malzeme için kesinleştirme yapılmamıştır"
- `0964-0966`: Related material finalization errors
- `0967-0968`: Same family

### D2. Add rejection playbook template
One template covering the 0963-0968 family:
```json
{
  "sonuc_kodu_pattern": "096[3-8]",
  "category": "material_finalization",
  "rebill_permitted": true,
  "corrective_steps": [
    "Malzeme kesinleştirme (finalization) yapılmamış",
    "Medula'da malzeme kaydını açın → kesinleştir butonuna basın",
    "Faturayı silin → yeniden gönderin"
  ]
}
```

**Tests:**
- Verify codes are in known_codes.json
- Verify playbook template exists for the family
- Test pattern matching: "0963", "0964" match the regex

---

## Parallelization Plan

```
┌─────────────────────────────────────────────────┐
│  Agent A: Diagnosis Coding Quality               │
│  Files: diagnosis_coding_quality.py + tests      │
│  Touches: NONE shared                            │
├─────────────────────────────────────────────────┤
│  Agent B: sagSol Laterality                      │
│  Files: models.py + laterality_validation.py     │
│  Touches: models.py (ONLY this agent)            │
├─────────────────────────────────────────────────┤
│  Agent C: Temporal Overlap + LOS Density         │
│  Files: temporal_anomaly.py + tests              │
│  Touches: NONE shared                            │
├─────────────────────────────────────────────────┤
│  Agent D: Medula 0963-0968 Codes                 │
│  Files: known_codes.json + rejection_playbook    │
│  Touches: data/medula/ ONLY                      │
└─────────────────────────────────────────────────┘
```

No file conflicts between any agents.

## Serial Wiring (after all 4 agents complete)

The existing `engine.py` wires detectors two ways: inline arg-unpack
(`detect_missing_diagnosis(list(ctx.claims))`) and context-wrapper
(`detect_sct_temporal_window_violations_for_context(ctx)`). **Provide a
`*_for_context(ctx)` wrapper for each new detector** so the wiring stays
consistent with the SCT pattern (the canonical `PatientClaimContext` shape)
and the `engine.py` call sites stay uniform. Each wrapper unpacks `ctx` into
the raw detector args:

```python
def detect_never_principal_diagnosis_for_context(ctx) -> list[dict]: ...
def detect_diagnosis_procedure_mismatch_for_context(ctx) -> list[dict]: ...
def detect_unnecessary_additional_diagnosis_for_context(ctx) -> list[dict]: ...
def detect_missing_laterality_imaging_for_context(ctx) -> list[dict]: ...
def detect_missing_laterality_surgery_for_context(ctx) -> list[dict]: ...
def detect_procedure_time_overlap_for_context(ctx) -> list[dict]: ...
def detect_los_procedure_density_anomaly_for_context(ctx) -> list[dict]: ...
```

1. Wire **all 7** `*_for_context` detectors into `engine.py` inside the
   `if ctx.patient_id:` block (L191+). Gate each on the data it needs:
   - diagnosis-only detectors (never_principal, unnecessary_additional): no gate
   - procedure-dependent detectors (dx_procedure_mismatch, both laterality,
     time_overlap, los_density): inside `if ctx.procedure_lines:`
2. Run full test suite
3. `compile_rules.py --check` byte-identical — **Workstream D does NOT affect
   this** (Medula JSON files are outside the prose-rule compile chain; verified
   the 147 artifacts are all under `data/gazette/`, none in `data/medula/`).
   So `--check` should pass unchanged.

## Verification

- `pytest tests/unit/ tests/smoke/` green
- `compile_rules.py --check` byte-identical (Workstream D is isolated from this gate)
- Each of the 7 detectors has positive + negative tests
- **Laterality detectors (B):** include a test for the honest-skip path —
  when all `sag_sol` values are empty, both laterality detectors return `[]`
  (no false-positive flood on un-populated data)
- No regression in existing tests
