## Task: Track A3 — Clear structural-cite blocker (1+2)

### Goal
Compile assert passes: contentful mis-tagged `section_heading` rows reclassified; remaining true navigational heading `C*` cites dropped or remapped to encode-eligible children.

### Subtasks
- [x] Inventory 38 cited `section_heading` C* → contentful vs true-navigational
- [x] Reclassify contentful rows via `data/gazette/clause_type_overrides.yaml` + parquet patch + extractor hook
- [x] Drop structural C* from drop-safe rules; remap heading-only to encode-eligible children/coords in YAML
- [x] Recompile five affected targets; A3 assert green on all 14 compile rule JSONs
- [x] Unit tests (clause_identity + extract + sample prose rules)
- [x] Mark A3 done in god-plan + todo Review

### Out of Scope
- New cite syntax (`coord#fikra`)
- Track D/E/F
- Mass reclassify of uncited section_heading rows
- Fixing historically wrong provenance families (e.g. pulmoner→2.5.1.*, ravulizumab→6.4/6.5) beyond making cites non-structural

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- Overrides: 15 contentful `section_heading` → `prose` (`clause_type_overrides.yaml` + committed parquet)
- YAML: 20 files, 34 remaps + 5 drops of navigational heading cites
- Verify: A3 assert OK on 14 rule JSONs; `test_clause_identity` + related prose tests pass
