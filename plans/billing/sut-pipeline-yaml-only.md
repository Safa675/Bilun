# YAML-only rule authoring (Track B1)

**One authored path for rules:** `data/gazette/prose_rule_sources/<family>/*.yaml`  
**One authored path for deferrals:** `data/gazette/prose_rules/deferral_table.yaml`  
**Everything else is derived** (JSON via compile, manifests, coverage).

## Edit a rule

1. Change the section YAML under `prose_rule_sources/`.
2. Set `gate_b_sources` to unique `clause_coordinate` values when possible
   (keep `C######` only for collision-heavy cites — see A0 audit).
3. Compile:

```bash
PYTHONPATH=. python scripts/sut/compile_rules.py --target <rule_set_id>
```

4. Do **not** hand-edit `data/gazette/prose_rules/*.json` or provenance goldens.
5. `SOURCE_PATCHES` / `SOURCE_DROPS` stages are retired no-ops (Track B1).

## Deferrals (Track B2)

Mark “not a gap / not encodeable” judgment only in `deferral_table.yaml`
(`tier_c_deferred`, `emr_blocked`, `non_actionable`). Coverage reads
`non_actionable` from that table — there is no parallel Python frozenset.

## Provenance goldens (Track B3)

`clause_id → expected_rule_id` cases are derived from `gate_b_sources` via
`scripts/sut/prose/provenance_golden.py`. Behavioral sample goldens
(`samples` key) remain committed fixtures for evaluator tests.
