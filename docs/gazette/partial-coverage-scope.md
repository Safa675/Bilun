# Partial coverage scope (Wave 2 + Sprint 0 scope closure)

Registry `coverage_status` vs dashboard `has_algorithmic_gap` after Wave 2 classify fixes and Sprint 0 honesty pass (2026-06-17).

| rule_id | registry | primary gaps | engine | notes |
|---------|----------|--------------|--------|-------|
| `procedure_pairing` | partial | ≤4 | 6 JSON add-on rules | §2.2.2.A scoped |
| `material_pairing` | partial | 0 | 12 JSON pairing rules | §3.1.1 fallback → `material_bundling_prose` |
| `medula_rejection_playbook` | partial | 0 | Event + **10** template JSON | §1.7/§5.1 → `provizyon_medula` (non_algorithmic) |
| `provizyon_medula` | non_algorithmic | 0 | — | Admin MEDULA/provizyon prose |
| `billing_documents` | non_algorithmic | 0 | — | §5.2–5.4 + RG amendment headers in §5 |
| `lab_billing` | **implemented** | 0 | Hemogram + capture gap | |
| `material_bundling_prose` | **implemented** | 0 | 59 JSON rules + L1.4 manifest | Partial corpus honesty in dashboard partial-engines panel |
| `specialty_materials_prose` | **implemented** | 0 | 49 JSON rules + L4.4 manifest (84 traced) | Separate from EK-3 catalog engine |
| `drug_indication_prose` | partial | ~3643 | 131 INN + manifest | Tier C deferred; cohort demos purged 2026-08-22 (engine + unit tests remain) |
| Material prose demos | — | — | Sprint 2 | **0023–0024** (KDV, ihale); optik/ortopedi demos purged 2026-08-22 |
| MEDULA playbook demos | — | — | Sprint 3 | **10** `sonuc_kodu` templates; patients **0012, 0018, 0025–0032** |
| Claim readiness demos | — | — | Sprint 4 | **0033** proactive ÜTS checklist (no MEDULA event) |

## Sprint 0 metrics (live `build_sut_coverage`)

| Metric | Before | After Sprint 0 |
|--------|--------|----------------|
| Total algorithmic gaps | ~3957 | **3659** |
| Unclassified actionable gaps | 766 | **12** |
| §5 algorithmic gaps | 18 | **0** |
| Non-algorithmic clauses | ~893 | **~1599** |
| Drug share of algorithmic gaps | ~81% | **~99.6%** |

**Gap composition footnote (Rule Database UI):** ~99.6% of remaining algorithmic gaps are intentional `drug_indication_prose` partial (Tier C deferred). Optimizer gaps excluding drug ≈ **16**.

Encode manifests: `data/gazette/prose_manifests/L1.4_*`, `L3.1_*`, `L4.2_*`, `L4.4_*`.
