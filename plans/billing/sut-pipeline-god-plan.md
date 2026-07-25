# God plan: SUT rule pipeline simplification

**Status:** APPROVED 2026-07-25 — implementation started on `refactor/sut-pipeline-god-plan`  
**Owner:** Bilun encode / coverage pipeline  
**Supersedes / extends:** `plans/billing/pipeline-simplification-plan.md`  
**Related:** `plans/data/2026-06-30-sut-clause-coordinate-and-prose-reclassification-plan.md`, brittle-test remediation (done), gap-closure roadmap  
**A0 audit:** `plans/billing/sut-pipeline-a0-uniqueness-audit.md`

**Meeting one-liner:**  
*Rules are the only authored truth; deferral is the only human judgment store; compile derives JSON + manifest + coverage; paragraph identity is the SUT cite (`clause_coordinate`), not artificial `C*`.*

---

## 0. Decisions (approved)

| # | Decision | Locked |
|---|----------|--------|
| D1 | Scope | **Full simplification** (identity + SoT collapse + compile/coverage shrink) |
| D2 | `C*` removal | **Phased:** coordinate public when unique → keep `C*` for collisions → delete public `C*` only after Track E |
| D3 | Non-drug Gate B | **Last optional phase** (Track F) |
| D4 | Encode universe | Only **encode-eligible** rows (see A0 / `clause_identity.filter_encode_eligible`) |
| D5 | Fatura `F*` | Separate later epic |

**A0 finding (blocks naïve “coordinates everywhere”):** even among encode-eligible in-force rows, **357 coordinates collide** (worst: `4.2.14.C.(1)` numbered_item ×68). Dual-read must fail loud on ambiguity; YAML may use coordinates only when unique.

---

## 1. Why this exists (problem)

### Irreducible (keep)
1. Extract SUT paragraphs from docx → parquet  
2. Author machine rules (YAML → compiled JSON)  
3. Record “won’t / can’t encode” clinical judgment (deferrals)  
4. Evaluate claims from **rule JSON only**

### Accidental (kill)
| Smell | Evidence today | Cognitive cost |
|-------|----------------|----------------|
| Artificial `C00xxxx` as FK | Extractor sequential id; `gate_b_sources: [C006162]`; ~6.8k refs | Humans don’t think in C*; regen renumbers → mass breakage |
| Many sources of truth | YAML + patch modules + committed JSON + manifests + deferral_table + corpus CSV + goldens + coverage frozensets | “Where do I edit this fact?” has 6 answers |
| Parallel Gate B / compile writers | `gate_b_generic` exists **and** shim + multi `gate_b_writer` flavors in `compile_rules.py` (~1.5k LOC) | Looks like 2–3 architectures |
| Multi-shape manifests | ~46 manifests, several `manifest_version` strings | Every reader is shape-tolerant glue |
| Fake gap noise | Unnumbered prose / headings share or null coordinates; `_RECLASSIFY_AS_NON_ALGORITHMIC` in Python | Gap meetings argue taxonomy instead of encoding |

### Identity truth (agreed in design discussion)
- **Specialists audit by fıkra**, not `C*`.  
- **Machine still needs a paragraph key** for joins / deferrals / coverage.  
- Best SUT-native key: **`clause_coordinate`** = `section_id` + fıkra + bent (already extracted).  
- Caveats (must design for, not ignore):
  - ~16 true nulls (chapter / part labels) → out of scope  
  - ~731 unnumbered prose under a section → collide on `section_id`-only coordinate  
  - ~1486 duplicate coordinates (struck vs live, amendments, shared section keys) → need `is_in_force` (and sometimes `clause_type`) in the join key  

**`C*` uniquely identifies a parquet row; it does *not* mean one rule per clause.** Many rules ↔ one paragraph is normal.

---

## 2. Target architecture

```
SUT docx
   │
   ▼
extractor ──► sut_clauses.parquet
              primary cite: clause_coordinate (+ is_in_force for disambiguation)
              structural rows: chapter / section_heading / bare prose (scoped out of encode)
   │
   │     ┌─────────────────────────────────────────┐
   │     │  AUTHORED (only these are hand-edited)  │
   │     │  • prose_rule_sources/**/*.yaml         │
   │     │  • deferral_table.yaml                  │
   │     └─────────────────────────────────────────┘
   │                         │
   │                         ▼
   │              compile_rules.py  (thin)
   │                         │
   │           ┌─────────────┼─────────────┐
   │           ▼             ▼             ▼
   │     rule JSON     canonical     (optional CI)
   │                   manifest      ephemeral goldens
   │           │             │
   │           │             ▼
   │           │      coverage derive
   │           │      (parquet + rules + deferral)
   │           ▼
   └────► runtime evaluator / API
          reads RULE JSON (+ clause parquet for Rule DB UI)
          NEVER reads corpus CSV / patch modules / goldens for claim logic
```

**Hard rules after this epic**
1. One authored path for rules: YAML only.  
2. One authored path for “not a gap”: deferral_table (incl. non_actionable / emr_blocked / tier_c + themes).  
3. Manifests and coverage are **derived**, never the place clinical judgment is born.  
4. Public paragraph identity in YAML/UI/audit = `clause_coordinate` (qualified).  
5. Runtime claim path does not depend on `C*` or manifests.

---

## 3. Current state (do not re-do blindly)

| Already present | Still debt |
|-----------------|------------|
| `clause_coordinate` columns in extractor + parquet + API | Public FK still `C*` in `gate_b_sources` / manifests / deferrals |
| `gate_b_generic.py` + `gate_b_sections.py` | `gate_b_shim.py`, multi writers, leftover one-off scripts |
| `deferral_table.yaml` | Deferral **also** copied into manifests / traces; dual SoT |
| Brittle census tests softened (2026-07-25) | Goldens + corpus CSVs + patch stages still maintained |
| Pipeline simplification Phases 1–5 partially started | Manifest versions not all `canonical-v1`; coverage still special-cases |

---

## 4. Workstreams (execution order)

Prefer **Track A → B → C → D → E**. Track F optional. Do not start Track E (delete `C*`) until Track A uniqueness gates pass.

### Track A — Paragraph identity (foundation)

**Goal:** Make `clause_coordinate` the *contract* for provenance; keep `C*` only as private remappable row id until Track E.

#### A0 — Uniqueness & encode-universe audit (no product change)
- [x] Measure: % rows with null coordinate; duplicate `(clause_coordinate)` vs `(clause_coordinate, is_in_force)` vs `(clause_coordinate, is_in_force, clause_type)`
- [x] Define **encode-eligible** predicate (recommended):  
  `is_in_force` ∧ `clause_type ∈ {fikra, bent, numbered_item}` ∧ coordinate has fıkra **or** bent **or** numbered item (not section-only)
- [x] Document collision classes (struck+live, section-only prose, bent reuse across drugs) in `plans/billing/sut-pipeline-a0-uniqueness-audit.md`
- [x] **Exit:** written uniqueness report + approved encode-eligible rule (D4)

#### A1 — Dual-write / dual-read period
- [x] Schema: `gate_b_sources` accepts **coordinate strings** (and temporarily still `C*` during migration)
- [x] Compiler + coverage resolve either form → internal row set via parquet lookup *(foundation: `clause_identity` + `gate_b_generic`; coverage full wire = follow-up)*
- [ ] Deferral table gains `clause_coordinate` column (or migrate keys); keep `C*` during transition if needed for join
- [ ] Rule DB / Clause UI: show **coordinate** as primary mono badge; demote `C*` to secondary “internal id” or hide
- [x] **Exit (partial):** new YAML *can* cite unique coordinates; CI unit tests green; old `C*` refs still resolve

#### A2 — Migrate authored refs
- [ ] Rewrite `gate_b_sources` in YAML (and compiled JSON via compile) from `C*` → coordinate
- [ ] Migrate `deferral_table.yaml` keys to coordinate (+ `is_in_force` where required)
- [ ] Migrate manifest builders to emit coordinate lists / traces
- [ ] Update stale-ref / parity / audit scripts to speak coordinate
- [ ] **Exit:** `rg 'gate_b_sources:.*C[0-9]{6}'` clean in YAML sources; deferral has no bare `C*` keys (or only documented exceptions)

#### A3 — Disambiguation policy for collisions
- [x] Default join: `(clause_coordinate, is_in_force=true)`
- [x] If still ambiguous: require explicit `clause_type` or refuse compile with actionable error *(encode-eligible filter as implicit type disambiguation; still-ambiguous → refuse with candidate `C*` list)*
- [x] Section-only / heading / chapter: never appear in `gate_b_sources`; coverage excludes from algorithmic gap unless opted in *(contentful mis-tags → `clause_type_overrides.yaml` + prose; true headings remapped/dropped in YAML)*
- [x] **Exit:** compile fails loud on ambiguous cites; no silent “first row wins”

---

### Track B — Single authored truth (biggest cognitive win)

**Goal:** One place to edit rules; one place to edit deferrals.

#### B1 — YAML-only authoring
- [x] Delete / stop using `SOURCE_PATCHES` / `SOURCE_DROPS` and `drug_indication_*_patches.py` as edit paths
- [x] All linkage lives in YAML `gate_b_sources` (coordinates after A2)
- [x] Committed JSON is compile output only (CI `--check` proves drift)
- [x] **Exit:** documented “edit YAML → run compile”; patch modules empty/deprecated (`plans/billing/sut-pipeline-yaml-only.md`)

#### B2 — Deferral table is the only judgment store
- [x] Normalize statuses: `encoded` (derived), `tier_c_deferred`, `emr_blocked`, `non_actionable`, pending A/B
- [x] Move `_RECLASSIFY_AS_NON_ALGORITHMIC` (~562 ids in `coverage.py`) into deferral / non_actionable data
- [x] Manifests **derive** bucket lists + traces from rules ∪ deferral; no hand-maintained defer themes in manifests *(`build_manifest` applies deferral statuses; §4.2.14.C on GateBSection)*
- [x] **Exit (coverage):** deleting a deferral `non_actionable` row changes coverage taxonomy; no parallel Python frozenset

#### B3 — Goldens
- [x] Prefer ephemeral / derived provenance goldens from `gate_b_sources` (`provenance_golden.py`); delete committed pure-provenance golden JSON
- [x] **Exit:** no third maintained `clause → rule` artifact (behavioral `samples` goldens kept)

---

### Track C — One derive pipeline

**Goal:** Manifest + coverage are boring, single-shaped derivatives.

#### C1 — Canonical manifest only
- [x] One schema (`manifest_version: canonical-v1`) — see prior plan fields; keys use coordinates post-A
- [x] Re-stamp all GateBSection / existing manifests; delete `r5-*` / `wave2-v1` / `t1-v1` shells
- [x] Drop dead fields (pcts, duplicate source maps, inn_named_*, etc.) *(restamp strips non-canonical shells; Track F extras preserved on pad)*
- [x] **Exit:** every committed SUT manifest validates against one JSON schema *(exceptions: fatura, L1.8 copay)*

#### C2 — Thin `compile_rules.py`
- [x] Collapse `gate_b_writer` flavors → one path: load section YAML → write JSON → derive manifest via `gate_b_generic`
- [x] Target: compile orchestrator understandable in one screenful of stage list
- [x] **Exit:** no `shared_manifest` / `rules_path_with_batch_rules` special cases (or ≤1 documented exception) *(exceptions: `4201_w4`, `4213_tier_b_remap`; §4.2.14.C now on GateBSection)*

#### C3 — Coverage = one function
- [x] Input: parquet + rule JSON + deferral *(encoding via `_clause_has_rule_encoding`; drug supplements via manifest globs)*
- [x] Output: coverage parquets  
- [x] Delete §4.2.14.C-only side tools (`drug_indication_manifest`, `a1_manifest_coverage`) once generic covers them *(`SECTION_4214C` + deferral-driven `build_manifest`)*
- [ ] Prefer Polars end-to-end (drop pandas dual stack in prose coverage/classify when touched) *(still pandas in `_enrich_with_coverage` — dedicated follow-up)*
- [x] **Exit:** “what is a gap?” answerable from one predicate + deferral *(`_clause_has_rule_encoding` + structural/deferral exclusions)*

#### C4 — Corpus CSVs
- [x] Stop committing / stop runtime-reading Gate B corpus CSVs; optional export-only for humans *(gitignored; payment/copay/drug writers default `write_corpus=False`)*
- [x] Counts from parquet  
- [x] **Exit:** `rules_catalog` / coverage do not open `prose_corpus/*.csv`

#### C5 — Retire shims & one-offs
- [x] Remove `gate_b_shim` once tests call generic  
- [x] Delete dead export/repair scripts superseded by generic audit *(a0 inventory, anti_vegf_4233_export, a1/phase5 repair, `drug_indication_manifest`)*
- [x] **Exit:** `scripts/sut/prose/gate_b*.py` is generic + sections + audit (+ Track F non-drug if deferred) *(plus `drug_indication_gate_b` shared primitives)*

---

### Track D — Product / audit UX

**Goal:** Specialists never need `C*` to audit.

- [x] Rule DB Hüküm: primary id = coordinate; copyable; search by coordinate + text  
- [x] Rule detail: show source fıkra cite(s) from `gate_b_sources` as coordinates + snippet  
- [x] Gap / deferral review views keyed by coordinate  
- [x] Docs: 4-verb pipeline README — `extract → compile → derive → evaluate`  
- [x] **Exit:** meeting demo can audit a rule without mentioning `C*`

---

### Track E — Delete artificial `C*` (only after A–D)

**Goal:** Surrogate gone or demoted to non-referenced internal column.

- [ ] Prove: no YAML/deferral/manifest/API contract requires `C*`  
- [ ] Optional: stop emitting `clause_id` **or** keep as opaque remappable column never used in authored data  
- [ ] Embeddings / joins migrate to coordinate (+ hash)  
- [ ] Update `stale_clause_refs`, schemas (`^[CF][0-9]{6}$` → coordinate pattern), tests  
- [ ] **Exit:** artificial SUT `C*` not part of public contract; Fatura `F*` unchanged until its own epic (D5)

---

### Track F — Non-drug Gate B (optional, last)

- [ ] Port payment_method / material_bundling / copay_exemption onto generic + canonical manifest  
- [ ] Same coordinate identity rules  
- [ ] **Exit:** zero bespoke drug-vs-nondrug architecture stories

---

## 5. Definition of done (epic)

- [ ] Architecture diagram above is true in code + docs  
- [ ] Public provenance uses `clause_coordinate` (qualified); specialists don’t need `C*`  
- [ ] Authored surfaces ≤ 2: YAML rules + deferral_table  
- [ ] One manifest schema; coverage derived; no corpus CSV in runtime  
- [ ] `compile_rules.py` is a thin orchestrator  
- [ ] Encode-eligible universe excludes structural noise by policy  
- [ ] CI green; compile `--check` green; coverage rebuild deterministic  
- [ ] Tech-meeting narrative fits on **one slide** without apologizing for shims  

---

## 6. Out of scope (explicit)

- Rewriting claim **evaluator** matching logic / clinical rule content  
- LLM-based bulk rule extraction as the complexity fix  
- Docx extractor rewrite beyond coordinate quality / encode-eligible tagging  
- Regenerating synthetic cohorts  
- Frontend redesign beyond identity display (Track D minimum)  
- Merging Fatura İnceleme into SUT ids in this epic  

---

## 7. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Coordinate collisions silently remap rules | A0 audit + A3 loud compile errors; never “first match” |
| Mass YAML migration churn | A1 dual-read; migrate section-by-section; atomic compile per batch |
| Gap counts jump when taxonomy honesty improves | Pre-announce: count changes ≠ encoding loss (lesson from gap-closure Phase 1.1) |
| Partial epic leaves two architectures | Do not start Track E until A–C exits green; avoid long dual-key *forever* (D2) |
| Team still edits JSON/manifests by habit | CI drift checks + short “how to encode” doc in Track D |

---

## 8. Suggested meeting agenda (30–40 min)

1. **Irreducible vs accidental** (2 min) — slide with 4 verbs  
2. **Identity decision** (8 min) — `C*` vs `clause_coordinate`; show real collision examples from A0  
3. **SoT collapse** (8 min) — YAML + deferral only; list artifacts to delete  
4. **Phased delivery** (8 min) — Tracks A→E; what ships first  
5. **Risks / gap-count honesty** (5 min)  
6. **Decide D1–D4** (5 min) — record in `tasks/todo.md`  

---

## 9. Appendix — artifact inventory (targets to shrink)

| Artifact | Count (approx, 2026-07-25) | Fate |
|----------|----------------------------|------|
| `prose_manifests/*.json` | ~46 | Derive; one schema |
| `prose_corpus/*.csv` | ~34 | Export-only or delete |
| `prose_rules/golden/*` | ~56 | Ephemeral or delete |
| `compile_rules.py` | ~1541 LOC | Thin |
| `coverage.py` | ~696 LOC | ~200 + data-driven deferrals |
| `gate_b_generic.py` | ~648 LOC | Keep as the one engine |
| `deferral_table.yaml` | exists | Sole judgment SoT |

---

## 10. Cross-links

- Predecessor: `plans/billing/pipeline-simplification-plan.md` (Phases 1–7) — treat this god plan as the living roadmap; tick predecessor items into Tracks B/C  
- Coordinate extraction history: `plans/data/2026-06-30-sut-clause-coordinate-and-prose-reclassification-plan.md`  
- Brittle tests (done): `plans/refactor/brittle-test-remediation-plan.md`  
