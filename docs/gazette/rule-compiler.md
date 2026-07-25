# SUT Rule Compiler

> Pipeline overview (extract → compile → derive → evaluate): [sut-pipeline.md](./sut-pipeline.md).

`scripts/sut/compile_rules.py` is the single entrypoint for generated SUT prose rule artifacts.
It replaces the retired `merge_*.py` scripts and writes rule JSON, Gate B manifests, golden
fixtures, and prose-corpus CSVs from YAML section sources and named compile stages.

## Commands

- Compile all targets:
  `python scripts/sut/compile_rules.py`
- Compile one target:
  `python scripts/sut/compile_rules.py --target definitions_2_6`
- List targets:
  `python scripts/sut/compile_rules.py --list`
- Verify generated artifacts are current:
  `python scripts/sut/compile_rules.py --check`

## YAML rule sources (authoritative)

Authoring input lives under `data/gazette/prose_rule_sources/` — **one YAML file per SUT
section**, not one file per rule. Example layout:

```
data/gazette/prose_rule_sources/
  definitions_2_6/
    2.6.1.yaml
    2.6.1.A.yaml
    ...
  drug_indication/
    4.2.1.C-8.yaml
```

Each section file has:

```yaml
section_id: "4.2.1.C-8"
source_note: "optional migration provenance"
rules:
  - rule_id: ...
    sut_section: ...
    gate_b_sources: [C003839]
    ...
```

`compile_rules.py` loads YAML via `rule_family_yaml_paths()` and writes the **runtime JSON**
under `data/gazette/prose_rules/` (unchanged contract for `src/bilun/`).

**Coverage today**

All 17 runtime prose rule families compile from `prose_rule_sources/<family>/*.yaml`.
There are 42 compile targets total: 17 YAML `fresh` compiles + 17 drug Gate B stages +
8 shared Gate B/manifest stages.

Legacy `*_batch_rules.py` modules were removed in Phase 3. Rule bodies live only in YAML;
`legacy_batch_rule_ids.json` maps retired batch aliases to `rule_id` lists for tests and
Gate B CLIs (`load_legacy_drug_batch`).

## Generated artifacts (compile outputs)

These paths are **committed** and verified by `compile_rules.py --check`:

| Artifact | Location | Produced by |
|----------|----------|-------------|
| Runtime rule sets | `data/gazette/prose_rules/*.json` | YAML `fresh` targets |
| Golden fixtures | `data/gazette/prose_rules/golden/*.json` | same compile pass |
| Gate B manifests | `data/gazette/prose_manifests/*.json` | Gate B / manifest stages |
| Prose corpus CSVs | `data/gazette/prose_corpus/*.csv` | Gate B stages |

Manifest-only constants (material/specialty clause-ID sets) live in
`scripts/sut/prose/manifest_clause_ids.py`. Source linkage is authored only in
`data/gazette/prose_rule_sources/` YAML (`gate_b_sources`); compile stages no longer
apply `SOURCE_PATCHES` / `SOURCE_DROPS`.

Gate B manifest stages use `scripts/sut/prose/gate_b_generic.py` +
`gate_b_sections.py`. Section-specific `*_gate_b.py` modules remain for
non-drug families (Track F) and shared primitives (`drug_indication_gate_b`).

`test_all_rule_family_yaml_sources.py` enforces exact rule-level parity between every YAML
source family and its runtime JSON.

## JSON Schema validation

Before any rule-set JSON is written, `scripts/sut/rule_sources.py` validates the payload:

- **JSON Schema** when a schema is registered for the `rule_set_id`
  (`data/gazette/prose_rules/schemas/` and `*.schema.json` siblings)
- **Compile invariants** on top: no rule may set both `icd10_codes` and `icd10_ranges`;
  `gate_b_sources` is required for `definitions_2_6` and `drug_indication_prose`

Validation failures abort the compile with a path-qualified error (e.g.
`definitions_2_6.rules[3].gate_b_sources`).

## CI Guard

CI runs `python scripts/sut/compile_rules.py --check` after the Python test suite. If a YAML
source, gate-B writer, or compiler stage changes generated artifacts, rerun the compiler
locally and commit the artifact diffs with the code change.

## Ownership

- **Rule data**: `data/gazette/prose_rule_sources/<family>/<section>.yaml`
- **Manifest constants**: `manifest_clause_ids.py`
- **Gate B / manifests**: `gate_b_generic.py` + `gate_b_sections.py` (+ Track F `*_gate_b.py`)
- **Orchestration**: `compile_rules.py` (ordering, dedup, schema validation, manifest accumulation)
- **Runtime contract**: `data/gazette/prose_rules/*.json` (read by `src/bilun/`)
