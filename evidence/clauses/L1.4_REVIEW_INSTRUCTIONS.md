# L1.4 Gate B — Human review sample instructions

**Artifacts**
- Full export: `L1.4_material_bundling_prose.csv`
- Review sample (≥10% of `p1_encode` rows): `L1.4_material_bundling_prose_review_sample.csv`
- Summary counts: `L1.4_material_bundling_gate_b_summary.json`

## Reviewer checklist (per row)

1. **Deontic** — Confirm `deontic_modality` matches excerpt (NO_PAY vs MUST_NOT_BILL).
2. **Trigger** — Can this clause be encoded as a machine condition?
   - `material_name_any` (Turkish keywords)
   - `material_not_in_ek3c` / `procedure_pairing_required` (claim fields)
   - `manual_review` only if neither applies
3. **Dedup** — If `duplicate_of` is `ek3b1` or `ek3b2`, confirm annex list already covers the legal outcome (do not add prose rule).
4. **Priority** — Change `encode_priority` to `defer` or `p2` in a copy column if legal review disagrees with automation.

## Sign-off

Record reviewer name, date, and count of rows approved for Phase 2 JSON encoding in `tasks/todo.md` or a PR comment.
