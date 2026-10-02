"""Static source inventory must never claim measured clinical completion."""
from copy import deepcopy
import json

import polars as pl
import pytest

from src.bilun.domain.sut.coverage_evidence import (
    build_drug_coverage_evidence,
    coverage_evidence_summary,
)


def frame():
    return pl.DataFrame({
        "clause_id": ["C1", "C2", "C3"],
        "primary_rule_id": ["drug_indication_prose"] * 3,
        "has_rule_encoding": [True, False, False],
        "has_algorithmic_gap": [True, False, True],
    })


def rules():
    return [
        {"rule_id": "route", "drug_names": ["drug"], "icd10_codes": ["C50"]},
        {"rule_id": "text", "condition": {"clinical_text": True}, "action": {"enforcement": "text"}},
        {"rule_id": "deferred", "drug_names": ["drug"], "report_specialties": ["oncology"]},
        {"rule_id": "blocked", "drug_names": ["drug"], "icd10_codes": ["C50"], "pay": False},
        {"rule_id": "source_only", "drug_names": ["drug"], "icd10_codes": ["C50"],
         "temporal_source_only": True},
    ]


def test_static_inventory_separates_representation_predicates_and_runtime():
    result = build_drug_coverage_evidence(frame(), rules())
    assert result["source_clause_count"] == 3
    assert result["source_represented_clause_count"] == 1
    assert result["deferred_or_structural_clause_count"] == 1
    assert result["unrepresented_gap_clause_count"] == 1
    assert result["executable_predicate_rule_ids"] == ["route"]
    assert result["executable_predicate_scope"] == "diagnosis_applicability_only_lower_bound"
    assert result["inputs_available_count"] is None
    assert result["actually_evaluated_count"] is None
    assert result["clinical_completion_pct"] is None
    assert result["runtime_unavailable_reason"]


def test_source_and_rule_duplicates_do_not_inflate_counts_or_digest():
    base = build_drug_coverage_evidence(frame(), rules())
    duplicated = build_drug_coverage_evidence(
        pl.concat([frame(), frame().reverse()]), list(reversed(rules())) + rules(),
    )
    assert json.dumps(base, sort_keys=True) == json.dumps(duplicated, sort_keys=True)


def test_changed_input_changes_digest_even_when_counts_stay_equal():
    changed = rules()
    changed[0]["icd10_codes"] = ["C51"]
    assert (build_drug_coverage_evidence(frame(), changed)["input_sha256"]
            != build_drug_coverage_evidence(frame(), rules())["input_sha256"])


def test_conflicting_duplicate_source_ids_fail_closed():
    conflict = frame().head(1).with_columns(pl.lit(False).alias("has_rule_encoding"))
    with pytest.raises(ValueError, match="Conflicting coverage"):
        build_drug_coverage_evidence(pl.concat([frame(), conflict]), rules())


def test_conflicting_duplicate_rule_ids_fail_closed():
    conflict = deepcopy(rules()[0])
    conflict["icd10_codes"] = ["C51"]
    with pytest.raises(ValueError, match="Conflicting rule"):
        build_drug_coverage_evidence(frame(), rules() + [conflict])


def test_legacy_missing_columns_are_unavailable_not_zero():
    result = build_drug_coverage_evidence(frame().drop("has_rule_encoding"), rules())
    assert result["available"] is False
    assert "source_represented_clause_count" not in result


def test_missing_flags_are_unknown_not_deferred_or_executable():
    unknown = frame().with_columns(pl.lit(None, dtype=pl.Boolean).alias("has_rule_encoding"))
    result = build_drug_coverage_evidence(unknown, [])
    assert result["unknown_source_status_clause_count"] == 3
    assert result["deferred_or_structural_clause_count"] == 0
    assert result["source_represented_clause_count"] == 0


def test_api_summary_omits_large_identity_lists_but_keeps_counts_and_reason():
    result = coverage_evidence_summary(build_drug_coverage_evidence(frame(), rules()))
    assert not any(key.endswith("_ids") for key in result)
    assert result["executable_predicate_rule_count"] == 1
    assert result["actually_evaluated_count"] is None


def test_counted_predicate_is_executable_by_actual_router():
    from src.bilun.domain.prose_rules._drug_indication.routing import _drug_rule_candidates
    from src.bilun.domain.prose_rules._drug_indication.matching import _diagnosis_matches_specific_rule
    result = build_drug_coverage_evidence(frame(), rules())
    _, routes, _ = _drug_rule_candidates("drug", rules())
    counted = next(r for r in routes if r["rule_id"] == result["executable_predicate_rule_ids"][0])
    assert _diagnosis_matches_specific_rule(["C50"], counted)
    assert not _diagnosis_matches_specific_rule(["C51"], counted)


def test_malformed_selectors_do_not_count_as_predicates():
    malformed = [{"rule_id": "bad", "drug_names": ["drug"], "icd10_codes": "C50"}]
    assert build_drug_coverage_evidence(frame(), malformed)["executable_predicate_rule_count"] == 0


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_invalid_source_identity_fails_closed(bad):
    changed = frame().with_columns(pl.lit(bad, dtype=pl.String).alias("clause_id"))
    with pytest.raises(ValueError, match="nonempty"):
        build_drug_coverage_evidence(changed, [])


def test_nonboolean_flags_cannot_masquerade_as_source_coverage():
    changed = frame().with_columns(pl.col("has_rule_encoding").cast(pl.Int64))
    with pytest.raises(ValueError, match="booleans"):
        build_drug_coverage_evidence(changed, [])


def test_rule_identity_whitespace_cannot_create_a_second_rule():
    with pytest.raises(ValueError, match="whitespace"):
        build_drug_coverage_evidence(frame(), [{"rule_id": " route "}])


def test_malformed_drug_names_do_not_count_as_executable():
    malformed = [{"rule_id": "bad", "drug_names": ["drug", None], "icd10_codes": ["C50"]}]
    assert build_drug_coverage_evidence(frame(), malformed)["executable_predicate_rule_count"] == 0


def test_all_real_counted_rules_enter_actual_candidate_router():
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
    from src.bilun.domain.prose_rules._drug_indication.routing import _drug_rule_candidates
    from src.bilun.domain.prose_rules._drug_indication.matching import _diagnosis_matches_specific_rule
    corpus = list_drug_indication_rules()
    result = build_drug_coverage_evidence(frame(), corpus)
    by_id = {rule["rule_id"]: rule for rule in corpus}
    assert result["executable_predicate_rule_count"] > 0
    assert result["executable_predicate_rule_count"] < result["rules_on_disk_count"]
    for rule_id in result["executable_predicate_rule_ids"]:
        rule = by_id[rule_id]
        _, specific, _ = _drug_rule_candidates(rule["drug_names"][0], [rule])
        assert [r["rule_id"] for r in specific] == [rule_id]
        assert _diagnosis_matches_specific_rule(["__outside_all_icd_selectors__"], rule) is False


def test_dependency_hashes_pin_rules_manifests_temporal_and_canonical_source(tmp_path):
    import shutil
    from src.bilun.domain.sut.coverage_evidence import coverage_dependency_hashes
    first = tmp_path / "first"
    for name in ("data/gazette/prose_rules/rules.json", "data/gazette/prose_manifests/manifest.json",
                 "data/gazette/temporal/amendment.json", "data/gazette/sut_clauses.parquet",
                 "data/gazette/deferral_table.yaml", "alternate.parquet"):
        path = first / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
    baseline = coverage_dependency_hashes(first, first / "alternate.parquet")
    assert baseline["input_clauses"] != baseline["data/gazette/sut_clauses.parquet"]
    relocated = tmp_path / "relocated"
    shutil.copytree(first, relocated)
    assert coverage_dependency_hashes(relocated, relocated / "alternate.parquet") == baseline
    path = first / "data/gazette/prose_manifests/manifest.json"
    path.write_text("changed")
    changed = coverage_dependency_hashes(first, first / "alternate.parquet")
    assert changed[path.relative_to(first).as_posix()] != baseline[path.relative_to(first).as_posix()]
    assert changed["input_clauses"] == baseline["input_clauses"]


def test_api_summary_uses_unique_ids_without_relabeling_legacy_row_fields(monkeypatch):
    from src.bilun.domain.sut.engine_summaries import _drug_indication_partial_engine_summary
    from src.bilun.domain.prose_rules import drug_indication
    monkeypatch.setattr(drug_indication, "drug_indication_registry_promotion_gate", lambda _: {})
    doubled = pl.concat([frame(), frame()])
    summary = _drug_indication_partial_engine_summary(doubled)
    assert summary["classified_clause_rows"] == 6  # Compatibility row count is unchanged.
    assert summary["coverage_evidence"]["source_clause_count"] == 3
    assert summary["coverage_evidence"]["source_represented_clause_count"] == 1
    assert summary["coverage_evidence"]["actually_evaluated_count"] is None
