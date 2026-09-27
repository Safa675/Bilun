# Wave A financial inventory — 2026-09-27

This is the Checkpoint 1 prerequisite audit of the four money-bearing focused groups. It records existing behavior, not an implemented financial projection. The audit was performed in `/root/worktrees/bilun-wavea-complete`; the worktree HEAD at document creation was `c19293ffe74c9cf96348b3424b5c28290e169433`. Other Wave A changes were in progress. The four audited detector files and the financial call chains below were unchanged by this audit.

**Decision: hold financial display implementation for independent plan review and separate Q9 detector corrections.** None of these four flat detector amounts currently enters patient/cohort totals directly. Yatak has a separate existing bed-day reconciliation that already affects those totals. Keeping new amounts separate does not make a wrong detector safe to surface.

Source-strength conclusions below concern provenance present in the code and emitted rows. This audit does not independently establish the current legal validity of each cited payment rule.

## Branch and amount matrix

There are four groups and **15 possible runtime IDs**: two dental, six radiation course, five radiation same-day, one transplant, and one yatak overlap. Radiation suffixes are enumerated immediately below the table.

| Emitted branch / IDs | Actual amount fields and calculation | Structured source strength | Current patient/cohort exposure | Safe separate classification |
| --- | --- | --- | --- | --- |
| `2-04.1.4_dental_ga_double_billed_anesthesia` | `dental_total_try` is the rounded sum of all classified dental billed amounts. `expected_ga_fee_try` is rounded 30% of that total; `ga_uplift_rate=0.30`. **No risk amount, billed anesthesia total, or net correction is calculated.** | `savings_basis="sourced"`, `sut_section_id="2-04.1"`; no structured `clause_ref` or `source_type`. Module comments point to Algoritma Rehberi. | Flat detector result only. No dedicated report block or contribution from this row to report/cohort totals. | Review pending source, positive-charge and dental/anesthesia association validation. Expected replacement fee must not be relabeled as exposure or net uplift. Confirmed financial amount unavailable. |
| `2-04.1.4_dental_ga_missing_uplift` | Same fields and formula, plus `recoverable_uplift_try=expected_ga_fee_try`. No subtraction for GA uplift already embedded in dental charges. | Explicit `savings_basis="heuristic"`; same unstructured locator. | Flat detector result only; no direct report/cohort contribution. | Potential uplift review. Confirmed amount unavailable without authoritative rate/base and evidence that the uplift was not already billed. |
| Six `radiation_oncology.course_cap.*` IDs | `billed_amount_try` and `risk_amount_try` each equal the rounded **entire billed line amount**. Once total quantity in a family exceeds cap 1, every participating line is emitted. | `sut_section="2.4.4.C"` and textual El Kitabı Tablo 30 reference. No structured reference or source classification in the row. | Flat detector result only; no direct report/cohort contribution. | Over-cap group review; confirmed excess amount unavailable until retained entitlement, source and quantity allocation are resolved. Separate Q9 monetary-semantics correction required. |
| Five `radiation_oncology.same_day_collapse.*` IDs | Same full-line billed/risk fields. Two or more family lines on one service date cause **every participating line** to be emitted. Single-line quantity is not checked. | Same as radiation course branch. | Flat detector result only; no direct report/cohort contribution. | Review pending source and allocation validation. Do not sum participant-line amounts as confirmed disallowance. Quantity representation needs a separate correctness decision. |
| `transplant_bundled_surgical_procedure` | `actual_billed_try=risk_amount_try=rounded billed amount` for inpatient P609080-associated `islem` lines billed above TRY0.02, excluding the package itself and any allowlisted codes. | Structured **Rehber** non-SUT reference with empty SUT clause key; `savings_basis="heuristic"`, `included_in_sgk_total=False`. The separately billable allowlist is explicitly empty and unverified. | Flat detector result only; no direct report/cohort contribution. | Review. Billed amount is a source-data fact; confirmed disallowance/risk remains unavailable until package carveouts are established. |
| `yatak_icu_overlap_510010` | `risk_amount_try=rounded whole billed 510010 line amount` when its procedure date equals an inferred ICU discharge day. No quantity/day allocation. | `savings_basis="sourced"`, `sut_section_id="2.4.4.H"`; no structured source reference. | Flat risk is absent from report audit totals. **Separate existing reconciliation changes bed opportunities, SGK uplift and cohort bed totals.** | Separate risk/review only after positive-charge, ICU evidence, allocation and source checks. Preserve existing bed reconciliation and totals. |

Matrix source locations:

- Dental formula and branches: `src/bilun/domain/prose_rules/dental_ga_uplift.py:200-271`; rate: `:65-67`; source comments: `:41-42`.
- Radiation course predicate/emission: `src/bilun/domain/prose_rules/radiation_oncology.py:148-197`; same-day predicate/emission: `:200-253`; common fields: `:267-285`.
- Transplant provenance/explicit limitation: `src/bilun/domain/prose_rules/transplant_package_scope.py:39-70`; eligibility: `:105-135`; amounts and classification: `:145-166`.
- Yatak inferred ICU dates: `src/bilun/domain/prose_rules/yatak_icu_overlap.py:110-139`; overlap predicate/fields: `:175-222`; reconciliation calculation: `:307-320`.

Exact radiation runtime IDs, derived from `radiation_oncology.py:73-113` and the constructor at `:278`:

```text
radiation_oncology.course_cap.external_rt_design
radiation_oncology.course_cap.brachytherapy_design
radiation_oncology.course_cap.rt_planning
radiation_oncology.course_cap.external_rt_dose
radiation_oncology.course_cap.brachytherapy_dose
radiation_oncology.course_cap.special_devices
radiation_oncology.same_day_collapse.rt_application
radiation_oncology.same_day_collapse.linac_application
radiation_oncology.same_day_collapse.hyperthermia
radiation_oncology.same_day_collapse.brachy_application
radiation_oncology.same_day_collapse.afterloading
```

## Exact flat-output versus report-total paths

1. `analyze_claim` returns flat dictionaries and invokes transplant at `src/bilun/domain/billing/engine.py:246-255`, yatak overlap at `:263-277`, radiation at `:295-302`, and dental GA at `:388-395`.
2. `compute_patient_billing_report` independently assembles report blocks (`src/bilun/domain/billing/patient_report.py:82-174`). It does not consume these four flat outputs. Its current canonical evaluator lists five original IDs in `src/bilun/domain/billing/rule_findings.py:23-35`, none of these 15. This boundary must be rechecked after the concurrent Wave A evaluator expansion.
3. `finalize_report_totals` calls `sum_sgk_uplift_try`, which sums only registered exact block fields (`src/bilun/domain/billing/report_totals.py:24-42,64-75`). It sets `total_recoverable_try=sgk_uplift_try`.
4. Report `audit_exposure_try` is computed separately by `compute_audit_exposure_from_claims`: per claim it calls `analyze_claim_unbundling`, then sums `session_violations`, `blood_component_violations`, `payment_method_violations`, and `bundled_violations` (`src/bilun/domain/billing/claim_audit_exposure.py:16-35`). It does not sum `analyze_claim` or these four detector results.
5. Cohort audit exposure sums each report's audit exposure (`src/bilun/domain/billing/cohort_summary.py:180-186`). Cohort SGK uplift sums report SGK uplift and sets grand recoverable total to that value (`:121-130`). Registry block rollup uses the registered block field (`:64-84`).
6. The current frontend summary reads the report's existing `sgk_uplift_try`, `audit_exposure_try`, and other report fields (`frontend/src/components/patient/SutBillingReportSections.tsx:334-345`). The four flat detector rows do not become visible there merely because `analyze_claim` emits them.

The separate legacy `validate_claim` adapter also does not establish monetary inclusion: it reads `savings_try` and `risk_amount`, not these groups' `recoverable_uplift_try`, `risk_amount_try`, or `expected_ga_fee_try` (`src/bilun/domain/rule_engine.py:438-451`). Its catch-all retains raw details but aggregates only selected outcome/amount fields (`:520-549`). Do not infer a headline contribution from the presence of a raw amount in `details`.

### Yatak's already-active financial path

`patient_report.py:129-140` builds `report.yatak_puani`, then calls `reconcile_yatak_icu_overlap`. The wrapper calls `reconcile_yatak_bed_days` and replaces only the opportunities (`src/bilun/domain/billing/claim_yatak_icu_overlap.py:43-53`). Reconciliation removes overlapping ICU last days, avoiding an already excluded package surgery day, then calculates:

```text
new_days = max(bed_days - overlapping_day_count, 0)
expected_yatak_try = rounded(new_days * daily_rate_try)
recoverable_uplift_try = rounded(max(0, expected_yatak_try - actual_billed_try))
```

See `src/bilun/domain/prose_rules/yatak_icu_overlap.py:288-320`.

**Existing `YatakPuaniReview.confirmed_yatak_try` sums included `expected_yatak_try`, not the recoverable delta** (`src/bilun/domain/billing/types.py:418-425`). The registry uses this property for SGK uplift and `total_yatak_puani` (`src/bilun/domain/billing/block_registry.py:103-109`). Recommended actions also use `expected_yatak_try` for the yatak surface (`src/bilun/domain/billing/billing_actions.py:306-329`). Preserve this existing contract during surfacing; any accounting correction to it is a separate task with its own baseline and approval.

## Reproduced cases and Q9 correction blockers

The following were executed directly against the current detector functions with real `ClaimHeader`/`ProcedureClaimLine` dataclasses and the real catalog. No pytest run or source/test edits were needed. Each radiation line below has quantity 1 and billed TRY1,000 unless stated otherwise.

| Case | Exact trigger | Observed output | Required disposition |
| --- | --- | --- | --- |
| R1: course amount | One claim, codes `800070` and `800110`, distinct line IDs | Two `radiation_oncology.course_cap.external_rt_design` rows, each `risk_amount_try=1000`; sum TRY2,000 | The detector's own rule permits one charge. Full participant billed value is not the confirmed excess. Separate correction must distinguish participant evidence from monetary entitlement/allocation; do not silently select a survivor without authority. |
| R2: same-day amount | One claim/date, codes `800330` and `800350`, distinct line IDs | Two `radiation_oncology.same_day_collapse.rt_application` rows, each risk TRY1,000; sum TRY2,000 | Same allocation correction as R1. |
| R3: quantity representation | One `800330` line, quantity 2, billed TRY2,000 | No radiation finding | Current same-day predicate counts lines, not quantity. Establish the authoritative quantity/fraction semantics and correct the detector separately if one line represents multiple payable applications. Do not certify this as evaluated-clean while the representation question is unresolved. |
| D1: zero-charge anesthesia | Dental `402010` billed TRY1,000 plus `550130` billed TRY0 on the same claim | `2-04.1.4_dental_ga_double_billed_anesthesia`, `severity="error"`, `savings_basis="sourced"`, expected GA fee TRY300 | Confirmed false positive in the claimed double-billing predicate: presence of a zero-charge line is treated as a separately billed charge. Separate Q9 correction. |
| Y1: zero-charge bed and wrong evidence owner | Inpatient ICU and non-ICU service claims both discharge 2026-07-12; only ICU claim has `510090`; service claim has `510010` dated 2026-07-12 and billed TRY0 | Sourced/error `yatak_icu_overlap_510010`, risk TRY0, `icu_claim_id="ICU,SERVICE"` | Separate Q9 corrections: require actual billed exposure for a double-billing violation, and identify only qualifying ICU evidence claims. Do not change the shared bed-day financial calculation incidentally. |

Code evidence:

- R1/R2: radiation docstrings promise only excess lines (`radiation_oncology.py:154-156,206-208`), but loops emit every member (`:178-180,235`), and amounts equal full billed value (`:282-283`). Existing tests explicitly expect two participant rows (`tests/unit/domain/prose_rules/test_radiation_oncology.py:96,195`); the correction must distinguish participants from excess amount, not blindly discard evidence rows.
- R3: `radiation_oncology.py:230-235` checks `len(fam_lines)`, while course logic separately sums quantity at `:169-175`.
- D1: `dental_ga_uplift.py:188-195,212` tests anesthesia presence with no positive-charge gate and no link to a particular dental procedure/session.
- Y1: `yatak_icu_overlap.py:179-185` adds every claim discharging on any ICU last day to the ICU reference; `:188-216` checks bed code/date but not a positive billed amount.

Under locked Q9, placing these wrong outputs in a review table does not discharge the correction requirement. Record the separate corrections and validate them before the combined release. Monetary authority and entitlement decisions must be explicit; a projection adapter must not invent a new payment rule to make a number available.

### Reproduction command

Run from the repository root using its Python environment. This uses existing test factories only to construct real immutable claim dataclasses; it does not execute their tests. `PYTHONDONTWRITEBYTECODE=1` avoids bytecode writes.

```bash
POLARS_MAX_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /opt/Bilun/.venv/bin/python - <<'PY'
import json
import runpy
from datetime import date
from decimal import Decimal

from src.bilun.domain.prose_rules.dental_ga_uplift import detect_dental_ga_uplift_violations
from src.bilun.domain.prose_rules.radiation_oncology import detect_radiation_oncology_violations
from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap

factories = runpy.run_path("tests/unit/domain/prose_rules/test_radiation_oncology.py")
claim, proc = factories["_claim"], factories["_proc"]
out = {}
for name, codes in (
    ("R1", ("800070", "800110")),
    ("R2", ("800330", "800350")),
):
    rows = detect_radiation_oncology_violations(
        [claim()],
        [proc(procedure_line_id=f"PL{i}", procedure_code=c) for i, c in enumerate(codes)],
    )
    out[name] = {
        "rows": len(rows),
        "risk_sum": sum(row["risk_amount_try"] for row in rows),
        "risk_by_line": [(row["procedure_line_id"], row["risk_amount_try"]) for row in rows],
    }
out["R3"] = detect_radiation_oncology_violations(
    [claim()],
    [proc(procedure_code="800330", quantity=2, billed_amount_try=Decimal("2000"))],
)
out["D1"] = detect_dental_ga_uplift_violations(
    [claim()],
    [proc(procedure_line_id="D", procedure_code="402010"),
     proc(procedure_line_id="A", procedure_code="550130", billed_amount_try=Decimal("0"))],
)
out["Y1"] = detect_yatak_icu_overlap(
    [claim(claim_id="ICU", discharge_date=date(2026, 7, 12)),
     claim(claim_id="SERVICE", discharge_date=date(2026, 7, 12))],
    [proc(claim_id="ICU", procedure_code="510090"),
     proc(claim_id="SERVICE", procedure_code="510010", procedure_date=date(2026, 7, 12),
          billed_amount_try=Decimal("0"))],
)
print(json.dumps(out, ensure_ascii=False, indent=2))
PY
```

## Review/unavailable limitations, distinct from reproduced wrong outputs

- **Transplant carveouts:** the detector itself explicitly limits its conclusion to heuristic exposure until its empty allowlist is established from source (`transplant_package_scope.py:60-70`). Honest review/unavailable treatment is supported by its existing contract; do not upgrade it to confirmed risk or Compliance.
- **Missing monetary provenance:** a `savings_basis="sourced"` string is not proof that a specific current clause, tariff, eligibility condition and calculation were verified. Dental and yatak lack structured references; radiation lacks both structured reference and source classification. Attaching a nearby section alone is insufficient.
- **Dental missing-uplift base:** no field inspected by the detector establishes that the billed dental total excludes an already applied uplift. A GA marker plus no anesthesia line cannot establish an additional receivable. Use an input/source limitation and review status with unavailable confirmed amount.
- **Radiation treatment-course identity:** course rules aggregate by claim (`radiation_oncology.py:323-338`), not an explicit treatment-course identifier. Avoid claiming complete course validation when treatment spans claims or multiple courses share a claim.
- **Whole-line versus affected-day amount:** yatak risk uses the whole line, regardless of quantity. Confirm how a source row represents bed days before presenting an exact single-day exposure. The existing claim-span ICU model is an assumption described at `yatak_icu_overlap.py:110-120`, not evidence of actual payment on the last date.
- **Anesthesia association:** dental checks every `550xxx` line on the claim; it does not demonstrate that a charge is for the dental procedure rather than another procedure/session. Missing association should not become a confirmed adverse conclusion.

These limitations can be represented honestly as review/unavailable with reasons and stable identities. They do not justify hiding or waiving the reproduced Q9 correction blockers.

## Overlap and identity requirements

“Not directly included from this detector” does not mean the underlying charge is absent from every existing calculation. Generic audit exposure already counts some same physical lines through package-included billed-minus-payable logic (`src/bilun/domain/prose_rules/drg_unbundling.py:238-253`) and other unbundling buckets. Transplant, dental/anesthesia and yatak rows can intersect those lines. Radiation participant amounts also overlap the permitted first charge within their own group.

Keep the new sourced risk/uplift display separate from current report and cohort headlines. Preserve stable claim, procedure-line and evidence/group identities so overlapping observations can be explained without summed double-counting. Dental currently emits claim-level code lists, not individual source line IDs (`dental_ga_uplift.py:226-242,255-272`); a future projection must retain the actual contributing line IDs rather than using a code as a line identity. Yatak's expected-day adjustment is already active and must not be added a second time as new uplift.

## Latent dental annex issue — not demonstrated on current data

`_is_dental_code` accepts both `EK-2Ç` and `EK-2C` (`dental_ga_uplift.py:75-88`), despite those being different annexes. However, the current lookup uses a combined EK-2B plus dental index (`src/bilun/domain/catalog.py:127-141,390-391`) and keeps package entries separately (`:168-175`). The inspected actual index contained **7,340 entries with no annex and 214 EK-2Ç entries**. Real `P609080`, `609080`, `P610070`, and `610070` all classified non-dental; `402010` classified dental.

Therefore the EK-2C acceptance is a latent classifier defect, not a demonstrated current-data release blocker. Do not report it as an observed production false positive. A future correction should distinguish the annexes explicitly and test the catalog contract.

## Self-review

- Four groups and all 15 runtime IDs accounted for; no synthetic `kind:radiation_oncology` counted as a runtime ID.
- Expected fee, billed value, risk, expected bed charge and recoverable delta kept distinct.
- Flat validator outputs traced separately from patient/cohort report aggregation.
- Reproduced predicate/evidence errors separated from source/input limitations and the latent annex issue.
- Existing totals are a parity boundary, not permission to repeat a wrong detector result in a new financial surface.
- This task adds only this report. It does not modify production code, tests, plans, remote state or deployment.
