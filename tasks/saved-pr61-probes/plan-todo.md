# PR61 golden refresh — plan

## Task: Refresh data-layer golden constants to 2026-07-01 corpus

### Goal
Update the golden expectations in the 14 failing test files under tests/unit/scripts/
so all 28 unit tests pass against the regenerated 2026-07-01 corpus/manifests on
branch followup/pr61-data-goldens (do NOT re-run ingest, do NOT push).

### Subtasks
- [ ] Compute actual values from the new corpus for every failing assertion
  (clause IDs, tier counts, manifest traces, coverage sums, inventory counts).
- [ ] test_sut_coverage.py (4): copay ek4d gap sum, drug_indication deontic unencoded,
      specialty materials statuses, EMR-blocked catalog/blocked floors.
- [ ] test_authored_cstar_inventory.py (2): per-surface C* counts + identical-dup count.
- [ ] test_drug_indication_4210_gate_b.py (4): tier A IDs, encoded IDs, promotions, artifacts.
- [ ] test_drug_indication_4234_gate_b.py (3): tier A IDs, encoded set, encoded_clause_count.
- [ ] test_drug_indication_4206_gate_b.py (3): encoded sets, artifacts.
- [ ] test_drug_indication_4235_4237_gate_b.py (2): tier counts, trace membership.
- [ ] test_drug_indication_4215_gate_b.py (2): encoded sets, artifacts count.
- [ ] test_drug_indication_4214c_gate_b.py (2): export height 635 vs 615.
- [ ] test_drug_indication_4238_gate_b.py (1): encoded set + trace.
- [ ] test_drug_indication_4224_gate_b.py (1): encoded set.
- [ ] test_drug_indication_4213_gate_b.py (1): oral-switch encode_tier B vs C.
- [ ] test_drug_indication_4201_gate_b.py (1): tier_a_pending_count 1 vs 0.
- [ ] test_copay_exemption_gate_b.py (1): 1.8.2.(1) clause id mapping.
- [ ] test_track_e_public_contract.py (1): C002684 sample id no longer in corpus.
- [ ] Verify ALL 28 pass with .venv/bin/python -m pytest <file> -q --tb=short -n 4.
- [ ] Commit locally on followup/pr61-data-goldens (no push).

### Out of Scope
- Re-running ingest / regenerating parquets.
- Touching src/bilun/domain/rules, prose_rules JSON encoding, or rule YAML sources.
- Pushing to origin / opening a PR.