# Option C — Episode-Level Billing Reconstruction: Investigation Findings

**Status:** Not feasible with current data. Investigation closed.

## What Option C proposed

For each of the 2.7M episodes in ILAY data, pull all drugs + labs +
procedures. Check whether billed SUT codes match services actually rendered.
Build a real per-episode Bilun claim and audit it.

## Why it's not feasible

**ILAY has no billing data.** The dataset is purely clinical.

### What ILAY contains

| Table | What's there | What's missing |
|---|---|---|
| `anadata_clean` (4M encounters) | Diagnosis (TANIKODU), vitals, doctor notes, visit type (GELIS_TIPI), department | Procedure codes, billed SUT codes, billed amounts |
| `lab_clean` (74M results) | Lab test names (SUB_CODE), values, abnormal flags | SUT codes for the tests, billing flags |
| `recete_clean` (3.7M rx) | Drug names, doses, dates | Drug SUT codes (we mapped these via `code_resolver`) |

**No fatura (invoice) data. No procedure log. No materials record. No medula
submission log.** The ILAY dataset tells you what happened to the patient
clinically. It does not tell you what the hospital charged, what SGK paid,
or what codes were submitted.

### What Bilun's billing engine needs (verified)

`PatientClaimContext` at `src/bilun/domain/claims/patient_context.py:22`
requires:

| Field | Available in ILAY? |
|---|---|
| `claims: ClaimHeader` | ✅ Yes (basic encounter info) |
| `drug_lines: DrugClaimLine` | ✅ Yes (from `recete_clean`) |
| `diagnoses: ClaimDiagnosis` | ✅ Yes (from TANIKODU) |
| `procedure_lines: ProcedureClaimLine` | ❌ No procedure data |
| `material_lines: MaterialClaimLine` | ❌ No materials data |
| `performed_procedure_lines: PerformedProcedureLine` | ❌ No EMR procedure log |

`ProcedureClaimLine` requires `procedure_code`, `procedure_name`,
`billed_amount_try`, `unit_price_try` — none exist in ILAY. Same for
`MaterialClaimLine`.

## The "billing generator" alternative (also rejected)

Instead of auditing what was billed, generate what SHOULD have been billed
from clinical data. Then validate the generator's output.

### Why this also fails

1. **We can only generate 30-40% of a real bill.** Consultations + drugs +
   (eventually) labs. We can't see the expensive stuff (surgeries, imaging,
   materials) — which is where 60-70% of revenue lives.

2. **No ground truth to validate against.** A generator that produces claims
   from inference, then runs them through Bilun's audit engine, is checking
   its own homework. Circular reasoning. Without real fatura data or manual
   coder review, accuracy is unmeasurable.

3. **Manual coder validation would cost 20-50K TL** for 500 episodes — and
   even then, coders can only code what's documented. They can't code an
   MRI that isn't in the clinical note.

## Pattern across the investigation arc

| Option | Verdict | Reason |
|---|---|---|
| ICD coder from text | ❌ Dead | Text labels don't match (P@3 = 0.08) |
| Drug combination rules (A) | ❌ Dead | 1 of 53 rules has data overlap |
| Diagnosis validation (item 1) | ✅ Done | 89 golden cases, 18K violations |
| Specialty validation (item 2) | ✅ Done | 8 golden cases + Bilun bug found |
| **Episode billing reconstruction (C)** | ❌ **Dead** | **No billing data in ILAY** |
| Lab-drug monitoring (D) | TBD | Not yet investigated |

## Strategic conclusion

**ILAY has gone as far as it can go for Bilun.** Items 1 and 2 extracted
the available value (drug-diagnosis and drug-specialty validation). The
remaining options either lack the data (C) or lack ground truth (billing
generator).

The real next step for Bilun is not more data mining — it's getting actual
**fatura data from Acıbadem**. That single data unlock would:

- Enable Bilun's core audit product (the actual paid product)
- Provide ground truth for every rule
- Make the billing generator validatable
- Replace 255 synthetic test rows with real claims

Everything else is a workaround that hits the same wall.

## Recommendation

Do not build Option C. Do not build the billing generator. Pivot energy to
either:

1. **Hospital data acquisition** — convert the Acıbadem partnership into
   actual fatura data access. This is a commercial/legal task, not a
   technical one.
2. **Investigate Option D** (lab-drug monitoring consistency) — the last
   untested idea that uses lab + prescription data together. Lower expected
   value than item 1, but unvalidated.

The ILAY investigation arc has run its course. Further investment in ILAY
data mining has diminishing returns.
