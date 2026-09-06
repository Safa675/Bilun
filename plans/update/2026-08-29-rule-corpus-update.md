# Plan: 2026-08-29 SUT rule corpus (PR 80 follow-through)

**Base:** `chore/sut-auto-update` (PR #80 ingest)  
**Branch:** `cursor/sut-2026-08-29-corpus-bd12`

## What PR 80 already did

Auto-ingest of the 2026-08-29 consolidated package:

- Branch A catalogs + Branch B `sut_clauses.parquet`
- Deltas: `data/gazette/deltas/2026-08-29_{clause_diff,delta}.*`
- Clause summary: **8,323 STABLE / 93 AMENDED / 2 NEW / 0 REMOVED**
- **Zero** `prose_rule_sources` / `prose_rules` / coverage updates

## What this follow-through does

Track E hashed `gate_b_sources` fail loud when clause text changes. Twelve YAML cites and five `gate_b_wave_config.py` keys are stale. Two new bents (`4.2.1.C-3.d`, `4.2.1.C-5.d`) grandfather patients who started drug before the (a)-bent amendment.

Re-extraction also shifted positional `C*` ids (~+4 to +10). YAML `C*` `gate_b_sources` and `clause_type_overrides.yaml` are remapped by `clause_key`. Stale 07-01 overrides had mis-tagged `4.2.9.A.(1)` as `prose`. Extractor false-struck §4.2.61 (text unchanged) — `is_in_force` restored from the 07-01 in-force hash.

### Hash remaps (old → new, similarity-matched)

| Old | New | Law change |
|---|---|---|
| `4.2.24.A.(1)#207d4fe2` | `#ad80aeff` | Cosmetic RG spacing |
| `4.2.33.D.(2)#44415262` | `#aa6d3ab7` | Cosmetic (wave config) |
| `4.1.4.c#52e18a39` | `#7c13ccb7` | Gyn antiinfective split; derm-only for other topicals |
| `4.2.1.C-3.a#d3c2cedc` | `#c15fa9c1` | 3-DMARD×3mo prerequisite repealed; anti-TNF + DAS28>5.1 remains |
| `4.2.1.C-5.a#9e9d422a` | `#63f23c5d` | Same DMARD repeal |
| `4.2.8.A.b#62004870` | `#2882a47a` | Neuro report 6mo → 1 year |
| `4.2.8.A.b#72dbe183` | `#5c30b19e` | Same |
| `4.2.14.C.b#5b46c37b` | `#e25fdb2c` | KLL relapse: 4-kür chemoimmuno / BCL2 nüks |
| `4.2.14.C.(1)#defc4bdc` | `#8d129088` | KLL: monotherapy (rituximab combo dropped) |
| `4.2.14.C.(2)#9d743db2` | `#03a4bab4` | Nilotinib already mülga; KÜB clause added |
| `4.2.15.D-1.(2)#ff4360aa` | `#173f99d4` | Wave config |
| `4.2.15.D-2.(3)#0f717c91` | `#d84c05b4` | Interventional radiology added to board |

### New rules

- `4.2.1.C-3.d#7199a67d` / `4.2.1.C-5.d#7199a67d`: continue coverage if started before 05/09/2026 and continuation criteria still hold.

### Commands

```bash
python scripts/sut/compile_rules.py
python scripts/sut/compile_rules.py --check
python scripts/sut/build_sut_coverage.py
python scripts/sut/audit_manifest_parity.py --drug-only
```

## Out of scope

- Unencoded AMENDED coords
- Deferral-table hashes not on the compile path
- Synthetic cohort / cache rebuild
