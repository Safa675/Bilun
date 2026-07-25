"""Tests for YAML rule sources and compile-time schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.sut.rule_sources import (
    DRUG_INDICATION_YAML_WAVE1_SECTIONS,
    DRUG_INDICATION_YAML_WAVE2_SECTIONS,
    DRUG_INDICATION_YAML_WAVE3_SECTIONS,
    DRUG_INDICATION_YAML_WAVE4_SECTIONS,
    drug_indication_yaml_all_paths,
    drug_indication_yaml_wave1_paths,
    drug_indication_yaml_wave2_paths,
    drug_indication_yaml_wave3_paths,
    drug_indication_yaml_wave4_paths,
    load_drug_section_rules,
    load_legacy_drug_batch,
    load_rule_family_yaml_rules,
    load_yaml_rules,
    validate_rule_set_payload,
)
from tests.unit._helpers.brittle_guards import soft_floor

_REPO = Path(__file__).resolve().parents[3]
_DEFINITIONS_YAML = _REPO / "data/gazette/prose_rule_sources/definitions_2_6/2.6.1.yaml"
_DRUG_YAML = _REPO / "data/gazette/prose_rule_sources/drug_indication/4.2.1.C-8.yaml"


def test_drug_yaml_wave1_covers_first_20_sections() -> None:
    paths = drug_indication_yaml_wave1_paths()
    assert len(paths) == len(DRUG_INDICATION_YAML_WAVE1_SECTIONS)
    yaml_rules = [
        r
        for r in load_rule_family_yaml_rules("drug_indication_prose")
        if r["sut_section"] in DRUG_INDICATION_YAML_WAVE1_SECTIONS
    ]
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    wave1 = [r for r in committed if r["sut_section"] in DRUG_INDICATION_YAML_WAVE1_SECTIONS]
    assert len(yaml_rules) == len(wave1)
    assert {r["rule_id"] for r in yaml_rules} == {r["rule_id"] for r in wave1}


def test_load_drug_section_rules_helper() -> None:
    rules = load_drug_section_rules("4.2.1.C-1")
    yaml_rules = load_yaml_rules(
        _REPO / "data/gazette/prose_rule_sources/drug_indication/4.2.1.C-1.yaml"
    )
    assert len(rules) == len(yaml_rules)
    soft_floor(len(rules), 20, label="4.2.1.C-1 rules")
    assert all(r["sut_section"] == "4.2.1.C-1" for r in rules)


def test_drug_yaml_wave2_covers_sections_21_to_40() -> None:
    paths = drug_indication_yaml_wave2_paths()
    assert len(paths) == len(DRUG_INDICATION_YAML_WAVE2_SECTIONS)
    soft_floor(len(paths), 15, label="wave2 paths")
    yaml_rules = [
        r
        for r in load_rule_family_yaml_rules("drug_indication_prose")
        if r["sut_section"] in DRUG_INDICATION_YAML_WAVE2_SECTIONS
    ]
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    wave2 = [r for r in committed if r["sut_section"] in DRUG_INDICATION_YAML_WAVE2_SECTIONS]
    assert len(yaml_rules) == len(wave2)
    assert {r["rule_id"] for r in yaml_rules} == {r["rule_id"] for r in wave2}
    assert DRUG_INDICATION_YAML_WAVE1_SECTIONS.isdisjoint(DRUG_INDICATION_YAML_WAVE2_SECTIONS)


def test_migrated_sections_union_is_complete() -> None:
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    corpus_sections = {r["sut_section"] for r in committed}
    yaml_rules = load_rule_family_yaml_rules("drug_indication_prose")
    yaml_sections = {r["sut_section"] for r in yaml_rules}
    # Soft floors (not exact equality): the drug corpus grows as new sections are
    # encoded. These guards catch regressions (count dropping below the baseline
    # established 2026-07) without blocking legitimate growth. See
    # plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 0.3.
    assert len(corpus_sections) >= 179
    assert len(committed) >= 919
    assert yaml_sections == corpus_sections


def test_drug_yaml_wave4_covers_final_86_sections() -> None:
    paths = drug_indication_yaml_wave4_paths()
    assert len(paths) == len(DRUG_INDICATION_YAML_WAVE4_SECTIONS)
    soft_floor(len(paths), 70, label="wave4 paths")
    yaml_rules = [
        r
        for r in load_rule_family_yaml_rules("drug_indication_prose")
        if r["sut_section"] in DRUG_INDICATION_YAML_WAVE4_SECTIONS
    ]
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    wave4 = [r for r in committed if r["sut_section"] in DRUG_INDICATION_YAML_WAVE4_SECTIONS]
    assert len(yaml_rules) == len(wave4)
    assert {r["rule_id"] for r in yaml_rules} == {r["rule_id"] for r in wave4}


def test_drug_yaml_all_paths_cover_full_corpus() -> None:
    paths = drug_indication_yaml_all_paths()
    assert len(paths) >= 166
    yaml_rules = load_rule_family_yaml_rules("drug_indication_prose")
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    assert len(yaml_rules) == len(committed)
    assert {r["rule_id"] for r in yaml_rules} == {r["rule_id"] for r in committed}


def test_drug_yaml_wave3_covers_sections_41_to_80() -> None:
    paths = drug_indication_yaml_wave3_paths()
    assert len(paths) == len(DRUG_INDICATION_YAML_WAVE3_SECTIONS)
    soft_floor(len(paths), 30, label="wave3 paths")
    yaml_rules = [
        r
        for r in load_rule_family_yaml_rules("drug_indication_prose")
        if r["sut_section"] in DRUG_INDICATION_YAML_WAVE3_SECTIONS
    ]
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/drug_indication_prose.json").read_text(encoding="utf-8")
    )["rules"]
    wave3 = [r for r in committed if r["sut_section"] in DRUG_INDICATION_YAML_WAVE3_SECTIONS]
    assert len(yaml_rules) == len(wave3)
    assert {r["rule_id"] for r in yaml_rules} == {r["rule_id"] for r in wave3}


def test_legacy_drug_batch_loader_matches_yaml() -> None:
    rules = load_legacy_drug_batch("BATCH_A24_RULES")
    soft_floor(len(rules), 5, label="BATCH_A24_RULES")
    assert all(r.get("gate_b_sources") for r in rules)


def test_definitions_section_yaml_loads_rules() -> None:
    rules = load_yaml_rules(_DEFINITIONS_YAML)
    soft_floor(len(rules), 3, label="definitions 2.6.1")
    assert all(rule.get("gate_b_sources") for rule in rules)
    assert rules[0]["rule_id"].startswith("2.6.1")


def test_drug_indication_pilot_yaml_loads_vedolizumab_rules() -> None:
    rules = load_yaml_rules(_DRUG_YAML)
    soft_floor(len(rules), 2, label="vedolizumab pilot yaml")
    ids = {rule["rule_id"] for rule in rules}
    assert "4.2.1.vedolizumab_crohn_anti_tnf_initiation" in ids


def test_definitions_yaml_matches_committed_json_semantics() -> None:
    committed = json.loads(
        (_REPO / "data/gazette/prose_rules/definitions_2_6.json").read_text(encoding="utf-8")
    )
    by_id = {rule["rule_id"]: rule for rule in committed["rules"]}
    source_dir = _REPO / "data/gazette/prose_rule_sources/definitions_2_6"
    yaml_rules: list[dict] = []
    for path in sorted(source_dir.glob("*.yaml")):
        yaml_rules.extend(load_yaml_rules(path))
    assert len(yaml_rules) == len(committed["rules"])
    for rule in yaml_rules:
        assert rule == by_id[rule["rule_id"]]


def test_schema_rejects_missing_gate_b_sources() -> None:
    payload = {
        "rule_set_id": "definitions_2_6",
        "title": "test",
        "effective_date": "2026-06-30",
        "rules": [
            {
                "rule_id": "test.missing_sources",
                "sut_section": "2.6.1",
                "condition": {"definition_scope": "x"},
                "action": {"message_tr": "y"},
            }
        ],
    }
    with pytest.raises(ValueError, match="gate_b_sources"):
        validate_rule_set_payload(payload, "definitions_2_6")


def test_schema_rejects_both_icd10_fields() -> None:
    payload = {
        "rule_set_id": "drug_indication_prose",
        "title": "test",
        "effective_date": "2026-06-30",
        "rules": [
            {
                "rule_id": "test.both_icd",
                "sut_section": "4.2.1",
                "drug_names": ["trastuzumab"],
                "icd10_codes": ["C50"],
                "icd10_ranges": ["C50"],
                "gate_b_sources": ["C000001"],
            }
        ],
    }
    with pytest.raises(ValueError, match="icd10_codes OR icd10_ranges"):
        validate_rule_set_payload(payload, "drug_indication_prose")


def test_schema_accepts_clause_coordinate_gate_b_sources() -> None:
    payload = {
        "rule_set_id": "drug_indication_prose",
        "title": "test",
        "effective_date": "2026-06-30",
        "rules": [
            {
                "rule_id": "test.coord_cite",
                "sut_section": "4.2.24.B",
                "drug_names": ["x"],
                "gate_b_sources": ["4.2.24.B.(3)", "C000001"],
                "condition": {"coverage_note": True},
                "action": {"message_tr": "ok"},
            }
        ],
    }
    validate_rule_set_payload(payload, "drug_indication_prose")


def test_schema_rejects_garbage_gate_b_sources() -> None:
    payload = {
        "rule_set_id": "drug_indication_prose",
        "title": "test",
        "effective_date": "2026-06-30",
        "rules": [
            {
                "rule_id": "test.bad_cite",
                "sut_section": "4.2.1",
                "drug_names": ["x"],
                "gate_b_sources": ["not-a-cite"],
                "condition": {"coverage_note": True},
                "action": {"message_tr": "ok"},
            }
        ],
    }
    with pytest.raises(ValueError, match="gate_b_sources"):
        validate_rule_set_payload(payload, "drug_indication_prose")


def test_drug_yaml_has_multiline_friendly_message_tr() -> None:
    text = _DRUG_YAML.read_text(encoding="utf-8")
    payload = yaml.safe_load(text)
    message = payload["rules"][0]["message_tr"]
    assert "Vedolizumab" in message
    assert "\n" not in message
