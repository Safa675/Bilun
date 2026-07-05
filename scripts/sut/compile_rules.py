#!/usr/bin/env python3
"""Unified rule compiler — consolidates the boilerplate merge_*.py scripts.

Replaces ~37 copy-pasted merge scripts with a single config-driven pipeline.
Each compile target declares: which batch modules to merge, which JSON to write,
which dedup strategy to use, how to build its manifest + golden, and which
legacy logic-bearing stages to run.

Usage:
  python scripts/sut/compile_rules.py                    # compile ALL targets
  python scripts/sut/compile_rules.py --target definitions_2_6
  python scripts/sut/compile_rules.py --check            # verify output == committed
  python scripts/sut/compile_rules.py --list             # list all targets
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.gate_b_wave_config import DRUG_INDICATION_WAVE_CLAUSE_IDS
from scripts.sut.rule_sources import (
    load_yaml_sources,
    rule_family_yaml_paths,
    sources_dir,
    validate_rule_set_payload,
)

_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_GOLDEN_DIR = _RULES_DIR / "golden"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
_SOURCES_DIR = sources_dir()


# ─── helpers ──────────────────────────────────────────────────────────────────

def _write_json(path: Path, payload: dict | list) -> None:
    """Write JSON with the exact formatting tests expect: indent=2, ensure_ascii=False, trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _strip_batch(rule: dict) -> dict:
    """Remove the 'encode_batch' field (internal tracking, not runtime)."""
    return {k: v for k, v in rule.items() if k != "encode_batch"}


def _load_batch(module_path: str, attr: str) -> list[dict]:
    """Dynamically import a batch_rules module and return its rule list."""
    mod = importlib.import_module(module_path)
    return list(getattr(mod, attr))


def _load_target_rules(target: "CompileTarget") -> list[dict]:
    """Load rules from Python batch modules and/or YAML section sources."""
    rules: list[dict] = []
    for mod_path, attr in target.batches:
        rules.extend(_load_batch(mod_path, attr))
    if target.yaml_sources:
        rules.extend(load_yaml_sources(target.yaml_sources))
    return rules


def _envelope_from_json(path: Path) -> dict[str, Any]:
    """Preserve committed envelope fields when recompiling from YAML."""
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: payload[key]
        for key in ("title", "effective_date", "sut_anchors", "coverage_note")
        if key in payload
    }


def _committed_rules_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(rule["rule_id"]): dict(rule) for rule in (payload.get("rules") or [])}


_COMMITTED_RULE_EXTENSION_KEYS = frozenset({"legacy_provision", "encode_batch"})


def _reconcile_rule_with_committed(committed: dict[str, Any] | None, yaml_rule: dict[str, Any]) -> dict[str, Any]:
    """Keep YAML values authoritative while preserving selected committed-only keys and ordering."""
    if committed is None:
        return dict(yaml_rule)
    merged = dict(yaml_rule)
    for key in _COMMITTED_RULE_EXTENSION_KEYS:
        if key in committed and key not in merged:
            merged[key] = committed[key]
    yaml_sources = list(yaml_rule.get("gate_b_sources") or [])
    committed_sources = list(committed.get("gate_b_sources") or [])
    if yaml_sources and set(yaml_sources) == set(committed_sources):
        merged["gate_b_sources"] = committed_sources
    ordered: dict[str, Any] = {}
    for key in committed:
        if key in merged:
            ordered[key] = merged[key]
    for key in merged:
        if key not in ordered:
            ordered[key] = merged[key]
    return ordered


def _payload_preserving_key_order(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return payload
    existing = json.loads(path.read_text(encoding="utf-8"))
    merged = dict(payload)
    for key, value in existing.items():
        if key not in merged:
            merged[key] = value
    ordered: dict[str, Any] = {}
    for key in existing:
        if key in merged:
            ordered[key] = merged[key]
    for key, value in merged.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _preserved_golden_batches(golden_path: Path) -> dict[tuple[str, str], Any]:
    if not golden_path.is_file():
        return {}
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    return {
        (str(case["clause_id"]), str(case["expected_rule_id"])): case.get("encode_batch")
        for case in (payload.get("cases") or [])
    }


def _validation_rule_set_id(target: CompileTarget) -> str:
    if target.rule_json.name == "drug_indication_prose.json":
        return "drug_indication_prose"
    return target.rule_set_id


def _write_rule_set_json(path: Path, payload: dict, *, rule_set_id: str) -> None:
    validate_rule_set_payload(payload, rule_set_id)
    _write_json(path, payload)


def _write_rule_set_for_target(target: CompileTarget, payload: dict) -> None:
    payload = _payload_preserving_key_order(target.rule_json, payload)
    if target.rule_json.is_file():
        committed = json.loads(target.rule_json.read_text(encoding="utf-8"))
        if committed == payload:
            return
    _write_rule_set_json(target.rule_json, payload, rule_set_id=_validation_rule_set_id(target))


# ─── dedup strategies ─────────────────────────────────────────────────────────

def _dedup_first_wins(rules: list[dict]) -> list[dict]:
    """First occurrence of each rule_id wins; later duplicates dropped."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rules:
        rid = r["rule_id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    return out


def _dedup_skip_dup(existing: list[dict], new_rules: list[dict]) -> tuple[list[dict], list[str]]:
    """Append new rules whose rule_id isn't already present; return (combined, skipped_ids)."""
    existing_ids = {r.get("rule_id") for r in existing}
    added, skipped = [], []
    for r in new_rules:
        if r["rule_id"] in existing_ids:
            skipped.append(r["rule_id"])
            continue
        added.append(_strip_batch(r))
    return existing + added, skipped


def _dedup_union_overwrite(existing: list[dict], new_rules: list[dict]) -> tuple[list[dict], int, set[str]]:
    """Overwrite duplicate rule bodies but preserve the union of gate_b_sources."""
    by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
    added = 0
    covered: set[str] = set()
    for raw in new_rules:
        clean = _strip_batch(raw)
        rule_id = str(clean["rule_id"])
        sources = list(clean.get("gate_b_sources") or [])
        covered.update(sources)
        if rule_id in by_id:
            before = set(by_id[rule_id].get("gate_b_sources") or [])
            clean["gate_b_sources"] = sorted(before | set(sources))
        else:
            added += 1
        by_id[rule_id] = clean
    return sorted(by_id.values(), key=lambda r: str(r.get("rule_id", ""))), added, covered


# ─── manifest builders ────────────────────────────────────────────────────────

def _build_gap_manifest(rules: list[dict], rule_set_id: str, *, manifest_version: str = "gap-v1",
                        extra_keys: dict[str, Any] | None = None,
                        gate_b_sources_encoded: list[str] | None = None) -> dict:
    """gap-v1 / t1-v1 manifest: encoded_clause_ids + gate_b_sources_by_rule.

    If gate_b_sources_encoded is provided, it's inserted between encoded_clause_ids
    and gate_b_sources_by_rule (matching the original merge scripts' key order).
    """
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        if srcs:
            sources_by_rule[r["rule_id"]] = srcs
            encoded.update(srcs)
    payload = {
        "manifest_version": manifest_version,
        "rule_set_id": rule_set_id,
        "rules_in_json": len(rules),
        "encoded_clause_ids": sorted(encoded),
    }
    if gate_b_sources_encoded is not None:
        payload["gate_b_sources_encoded"] = gate_b_sources_encoded
    payload["gate_b_sources_by_rule"] = sources_by_rule
    if extra_keys:
        payload.update(extra_keys)
    return payload


def _build_golden(rules: list[dict], rule_set_id: str, *, include_encode_batch: bool = True) -> dict:
    """Provenance golden: clause_id → expected_rule_id mapping."""
    cases = []
    for r in rules:
        for cid in (r.get("gate_b_sources") or []):
            case = {"clause_id": cid, "expected_rule_id": r["rule_id"]}
            if include_encode_batch:
                case["encode_batch"] = r.get("encode_batch")
            cases.append(case)
    return {"description": f"Gate B golden — {rule_set_id}", "cases": cases}


# ─── compile target config ────────────────────────────────────────────────────

@dataclass
class CompileTarget:
    name: str
    rule_json: Path
    mode: str  # "fresh" (build from scratch) | "append" (load existing + append)
    batches: list[tuple[str, str]]  # [(module_path, attr), ...]
    dedup: str  # "first_wins" | "union_overwrite" | "skip_dup"
    rule_set_id: str
    title: str
    sut_anchors: list[str]
    yaml_sources: list[Path] = field(default_factory=list)
    effective_date: str = "2026-05-23"
    strip_batch: bool = True
    # manifest
    manifest_path: Path | None = None
    manifest_version: str = "gap-v1"
    manifest_extra_keys: dict[str, Any] | None = None
    manifest_filter_section: str | None = None  # e.g. "2.4.4" — only count clauses from this section
    # shared manifest group (for wave2 cumulative)
    shared_manifest_group: str | None = None
    # golden
    golden_path: Path | None = None
    golden_include_encode_batch: bool = True
    # wave tracking (for wave2-style manifests)
    wave_label: str | None = None  # e.g. "wave2a"
    wave_scope_note: str | None = None
    # stage-driven targets (Phase 3/4)
    stages: list[str] = field(default_factory=list)
    gate_b_module: str | None = None
    gate_b_writer: str = "rules_path"
    manifest_batches: list[tuple[str, str]] = field(default_factory=list)
    section_prefixes: list[str] = field(default_factory=list)
    merge_rules: bool = True
    corpus_csv: Path | None = None
    output_paths: list[Path] = field(default_factory=list)
    skip_manifest: bool = False
    skip_golden: bool = False


# ─── target registry (YAML-first + Gate B stages) ─────────────────────────────

_TREATMENT_PRICING_WAVE2_COUNTS = {
    "wave2a": 27,
    "wave2b": 42,
    "wave2c": 32,
    "wave2_rest": 42,
}
_TREATMENT_PRICING_WAVE2_SCOPE = (
    "§2.4.4 treatment package pricing & coverage rules — batch 1 (T1) + "
    "wave-2a/b/c (W2A/W2B/W2C). Full §2.4.4 coverage including sitogenetik, "
    "moleküler genetik, yoğun bakım, göz ayaktan, kaplıca, palyatif."
)


def _yaml_fresh_target(
    name: str,
    *,
    rule_set_id: str,
    title: str = "",
    sut_anchors: list[str] | None = None,
    manifest_path: Path | None = None,
    manifest_version: str = "gap-v1",
    manifest_extra_keys: dict[str, Any] | None = None,
    golden_path: Path | None = None,
    golden_include_encode_batch: bool = True,
    strip_batch: bool = True,
    skip_manifest: bool = False,
    skip_golden: bool = False,
) -> CompileTarget:
    return CompileTarget(
        name=name,
        rule_json=_RULES_DIR / f"{rule_set_id}.json",
        mode="fresh",
        batches=[],
        yaml_sources=rule_family_yaml_paths(rule_set_id),
        dedup="first_wins",
        rule_set_id=rule_set_id,
        title=title,
        sut_anchors=sut_anchors or [],
        strip_batch=strip_batch,
        manifest_path=manifest_path,
        manifest_version=manifest_version,
        manifest_extra_keys=manifest_extra_keys,
        golden_path=golden_path,
        golden_include_encode_batch=golden_include_encode_batch,
        skip_manifest=skip_manifest,
        skip_golden=skip_golden,
    )


def _yaml_fresh_targets() -> list[CompileTarget]:
    """One fresh compile target per rule family — rules sourced from YAML only."""
    return [
        _yaml_fresh_target(
            "definitions_2_6",
            rule_set_id="definitions_2_6",
            title="§2.6 tanım/kapsam — yol, gündelik, refakatçi, kontrol, nakil, kaplıca, cenaze kuralları",
            sut_anchors=[
                "2.6.1", "2.6.1.A", "2.6.1.B", "2.6.1.B-1", "2.6.1.B-2", "2.6.1.B-3",
                "2.6.1.B-4", "2.6.2", "2.6.3", "2.6.4", "2.6.5", "2.6.6", "2.6.8", "2.6.9",
            ],
            strip_batch=False,
            manifest_path=_MANIFEST_DIR / "L2.6_definitions_manifest.json",
            golden_path=_GOLDEN_DIR / "definitions_2_6.json",
            golden_include_encode_batch=False,
        ),
        _yaml_fresh_target(
            "gap_closing_treatment_2",
            rule_set_id="gap_closing_treatment_2",
            title="§2 tedavi/yurt dışı/yol-gündelik — kalan faturalandırma/dışlama kuralları",
            sut_anchors=[
                "2.2.1.B-3", "2.2.2.B", "2.2.2.B-1", "2.2.2.B-2", "2.2.2.B-3", "2.3", "2.3.1",
                "2.4.2.A", "2.4.2.B-2", "2.4.4.F-3", "2.4.4.Ğ", "2.4.4.H", "2.4.4.J", "2.4.4.İ-2",
                "2.5.1", "2.5.2", "2.5.3.A", "2.5.3.A-2", "2.5.3.A-3", "2.5.3.B", "2.6.1.A",
                "2.6.1.B-3", "2.6.2", "2.6.3", "2.6.4", "2.6.6", "2.6.8", "2.6.9",
            ],
            manifest_path=_MANIFEST_DIR / "gap_closing_treatment_2_manifest.json",
            golden_path=_GOLDEN_DIR / "gap_closing_treatment_2.json",
        ),
        _yaml_fresh_target(
            "gap_closing_misc",
            rule_set_id="gap_closing_misc",
            title="§1/§3/§4/§5/§6 — kalan hüküm/malzeme/liste/MEDULA/KDV kuralları",
            sut_anchors=[
                "1.5.1", "1.5.2", "1.6", "1.8.2", "1.8.3", "1.8.5", "1.9.1", "1.10", "3.1.1",
                "3.1.3", "3.3.10", "3.3.11", "4.1", "4.1.3", "4.1.4", "4.1.5", "4.1.7", "4.1.8",
                "4.1.9", "4.3", "4.4.2", "4.5.1", "4.6", "5.2", "5.2.2", "5.3.1.C", "6.3.2",
            ],
            manifest_path=_MANIFEST_DIR / "gap_closing_misc_manifest.json",
            golden_path=_GOLDEN_DIR / "gap_closing_misc.json",
        ),
        _yaml_fresh_target(
            "treatment_pricing_2_4",
            rule_set_id="treatment_pricing_2_4",
            title="§2.4.4 Bazı tetkik ve tedavi yöntemleri — fiyatlandırma/dışlama kuralları",
            sut_anchors=[
                "2.4.4.A", "2.4.4.B", "2.4.4.C", "2.4.4.Ç", "2.4.4.D-1", "2.4.4.D-2", "2.4.4.E",
                "2.4.4.F-2", "2.4.4.F-4", "2.4.4.F-5", "2.4.4.F-6", "2.4.4.G-1", "2.4.4.G-2",
                "2.4.4.H", "2.4.4.I", "2.4.4.İ-1", "2.4.4.J", "2.4.4.K", "2.4.4.N",
            ],
            manifest_path=_MANIFEST_DIR / "treatment_pricing_2_4_manifest.json",
            manifest_version="t1-v1",
            manifest_extra_keys={"_include_gate_b_sources_encoded": True},
            golden_path=_GOLDEN_DIR / "treatment_pricing_2_4.json",
            skip_manifest=True,
            skip_golden=True,
        ),
        _yaml_fresh_target(
            "dental_2_4_1",
            rule_set_id="dental_2_4_1",
            title="§2.4.1 Diş tedavileri — dışlama/fiyatlandırma kuralları",
            sut_anchors=["2.4.1", "2.4.1.A", "2.4.1.B-1", "2.4.1.B-2", "2.4.1.B-3"],
            manifest_path=_MANIFEST_DIR / "dental_2_4_1_manifest.json",
            manifest_version="t1-v1",
            manifest_extra_keys={"_include_gate_b_sources_encoded": True},
            golden_path=_GOLDEN_DIR / "dental_2_4_1.json",
        ),
        _yaml_fresh_target(
            "drug_combination_4_2",
            rule_set_id="drug_combination_4_2",
            title="§4.2 İlaç kombinasyon/ardışık/endikasyon-dışı NO_PAY + Tier C biomarker kuralları",
            sut_anchors=[
                "4.2.1.C", "4.2.3", "4.2.5", "4.2.7", "4.2.9.A", "4.2.9.Ç", "4.2.9.E", "4.2.10.B-3",
                "4.2.12.B-1", "4.2.12.B-2", "4.2.14.C", "4.2.15.D-1", "4.2.16", "4.2.17.A", "4.2.17.B",
                "4.2.23", "4.2.24.A", "4.2.24.B", "4.2.25", "4.2.28.C", "4.2.30.A", "4.2.33", "4.2.34",
                "4.2.35.A", "4.2.38", "4.2.49.C", "4.2.71",
            ],
            manifest_path=_MANIFEST_DIR / "drug_combination_4_2_manifest.json",
            manifest_version="d42-v1",
            golden_path=_GOLDEN_DIR / "drug_combination_4_2.json",
        ),
        _yaml_fresh_target("drug_indication_prose", rule_set_id="drug_indication_prose", title=""),
        _yaml_fresh_target("anti_vegf_prose", rule_set_id="anti_vegf_prose", title=""),
        _yaml_fresh_target("payment_method_2_2", rule_set_id="payment_method_2_2", title=""),
        _yaml_fresh_target("material_bundling_prose", rule_set_id="material_bundling_prose", title=""),
        _yaml_fresh_target("specialty_materials_prose", rule_set_id="specialty_materials_prose", title=""),
        _yaml_fresh_target("copay_general_1_8", rule_set_id="copay_general_1_8", title=""),
        _yaml_fresh_target("gazette_repricing_prose", rule_set_id="gazette_repricing_prose", title=""),
        _yaml_fresh_target("material_pairing_uplift", rule_set_id="material_pairing_uplift", title=""),
        _yaml_fresh_target("procedure_pairing_prose", rule_set_id="procedure_pairing_prose", title=""),
        _yaml_fresh_target("drg_package_adequacy_prose", rule_set_id="drg_package_adequacy_prose", title=""),
        _yaml_fresh_target("session_pricing_2_2_2_B", rule_set_id="session_pricing_2_2_2_B", title=""),
    ]


def _drug_gate_b_target(
    name: str,
    *,
    gate_b_module: str,
    manifest_name: str,
    corpus_name: str,
    gate_b_writer: str = "rules_path",
    section_prefixes: list[str] | None = None,
    merge_rules: bool = False,
) -> CompileTarget:
    return CompileTarget(
        name=name,
        rule_json=_RULES_DIR / "drug_indication_prose.json",
        mode="stage",
        batches=[],
        dedup="union_overwrite",
        rule_set_id=name,
        title="",
        sut_anchors=[],
        stages=["write_gate_b_artifacts"],
        gate_b_module=gate_b_module,
        gate_b_writer=gate_b_writer,
        section_prefixes=section_prefixes or [],
        merge_rules=merge_rules,
        corpus_csv=_PROJECT_ROOT / f"data/gazette/prose_corpus/{corpus_name}",
        manifest_path=_MANIFEST_DIR / manifest_name,
    )


def _drug_gate_b_targets() -> list[CompileTarget]:
    """Gate B manifest/corpus stages for §4.2 drug-indication sections."""
    return [
        _drug_gate_b_target("drug_indication_4201", gate_b_module="scripts.sut.prose.drug_indication_4201_gate_b", manifest_name="L4.2_drug_indication_4201_manifest.json", corpus_name="L4.2_drug_indication_4201.csv"),
        _drug_gate_b_target("drug_indication_4206", gate_b_module="scripts.sut.prose.drug_indication_4206_gate_b", manifest_name="L4.2_drug_indication_4206_manifest.json", corpus_name="L4.2_drug_indication_4206.csv", gate_b_writer="section_rules", section_prefixes=["4.2.6"]),
        _drug_gate_b_target("drug_indication_4209_4227", gate_b_module="scripts.sut.prose.drug_indication_4209_4227_gate_b", manifest_name="L4.2_drug_indication_4209_4227_manifest.json", corpus_name="L4.2_drug_indication_4209_4227.csv"),
        _drug_gate_b_target("drug_indication_4210", gate_b_module="scripts.sut.prose.drug_indication_4210_gate_b", manifest_name="L4.2_drug_indication_4210_manifest.json", corpus_name="L4.2_drug_indication_4210.csv", gate_b_writer="section_rules", section_prefixes=["4.2.10"]),
        _drug_gate_b_target("drug_indication_4213_4216", gate_b_module="scripts.sut.prose.drug_indication_4213_4216_gate_b", manifest_name="L4.2_drug_indication_4213_4216_manifest.json", corpus_name="L4.2_drug_indication_4213_4216.csv"),
        _drug_gate_b_target("drug_indication_4215", gate_b_module="scripts.sut.prose.drug_indication_4215_gate_b", manifest_name="L4.2_drug_indication_4215_manifest.json", corpus_name="L4.2_drug_indication_4215.csv", gate_b_writer="section_rules", section_prefixes=["4.2.15"]),
        _drug_gate_b_target("drug_indication_4217", gate_b_module="scripts.sut.prose.drug_indication_4217_gate_b", manifest_name="L4.2_drug_indication_4217_manifest.json", corpus_name="L4.2_drug_indication_4217.csv"),
        _drug_gate_b_target("drug_indication_4218_4236", gate_b_module="scripts.sut.prose.drug_indication_4218_4236_gate_b", manifest_name="L4.2_drug_indication_4218_4236_manifest.json", corpus_name="L4.2_drug_indication_4218_4236.csv"),
        _drug_gate_b_target("drug_indication_4219", gate_b_module="scripts.sut.prose.drug_indication_4219_gate_b", manifest_name="L4.2_drug_indication_4219_manifest.json", corpus_name="L4.2_drug_indication_4219.csv"),
        _drug_gate_b_target("drug_indication_4224", gate_b_module="scripts.sut.prose.drug_indication_4224_gate_b", manifest_name="L4.2_drug_indication_4224_manifest.json", corpus_name="L4.2_drug_indication_4224.csv", gate_b_writer="section_rules", section_prefixes=["4.2.24"]),
        _drug_gate_b_target("drug_indication_4234", gate_b_module="scripts.sut.prose.drug_indication_4234_gate_b", manifest_name="L4.2_drug_indication_4234_manifest.json", corpus_name="L4.2_drug_indication_4234.csv"),
        _drug_gate_b_target("drug_indication_4235_4237", gate_b_module="scripts.sut.prose.drug_indication_4235_4237_gate_b", manifest_name="L4.2_drug_indication_4235_4237_manifest.json", corpus_name="L4.2_drug_indication_4235_4237.csv", gate_b_writer="batch_rules", section_prefixes=["4.2.35", "4.2.37"]),
        _drug_gate_b_target("drug_indication_4238", gate_b_module="scripts.sut.prose.drug_indication_4238_gate_b", manifest_name="L4.2_drug_indication_4238_manifest.json", corpus_name="L4.2_drug_indication_4238.csv", gate_b_writer="section_rules", section_prefixes=["4.2.38"]),
        _drug_gate_b_target("drug_indication_4201_w4", gate_b_module="scripts.sut.prose.drug_indication_4201_gate_b", manifest_name="L4.2_drug_indication_4201_manifest.json", corpus_name="L4.2_drug_indication_4201.csv", gate_b_writer="batch_rules", section_prefixes=["4.2.1"]),
        _drug_gate_b_target("drug_indication_4227_tier_b", gate_b_module="scripts.sut.prose.drug_indication_4209_4227_gate_b", manifest_name="L4.2_drug_indication_4209_4227_manifest.json", corpus_name="L4.2_drug_indication_4209_4227.csv", gate_b_writer="rules_path_with_batch_rules"),
        _drug_gate_b_target("drug_indication_4213_tier_b_remap", gate_b_module="scripts.sut.prose.drug_indication_4213_gate_b", manifest_name="L4.2_drug_indication_4213_4216_manifest.json", corpus_name="L4.2_drug_indication_4213.csv", gate_b_writer="shared_manifest", section_prefixes=["4.2.13"]),
        _drug_gate_b_target("drug_indication_4210_tier_b", gate_b_module="scripts.sut.prose.drug_indication_4210_gate_b", manifest_name="L4.2_drug_indication_4210_manifest.json", corpus_name="L4.2_drug_indication_4210.csv", gate_b_writer="section_rules", section_prefixes=["4.2.10"]),
    ]


def _gate_b_stage_targets() -> list[CompileTarget]:
    """Manifest/corpus stages that do not merge Python batch rules."""
    payment_json = _RULES_DIR / "payment_method_2_2.json"
    wave_manifest_targets = [
        CompileTarget(
            name=f"csv_wave_clause_ids_{suffix}",
            rule_json=_RULES_DIR / "drug_indication_prose.json",
            mode="stage",
            batches=[],
            dedup="union_overwrite",
            rule_set_id=rule_set_id,
            title="",
            sut_anchors=[],
            stages=["csv_wave_clause_ids"],
            manifest_path=_MANIFEST_DIR / manifest_name,
        )
        for suffix, rule_set_id, manifest_name in [
            ("rheum_biologics", "drug_indication_rheum_biologics", "L4.2_drug_indication_rheum_biologics_manifest.json"),
            ("small_mid", "drug_indication_small_mid", "L4.2_drug_indication_small_mid_manifest.json"),
            ("metabolic_mid", "drug_indication_metabolic_mid", "L4.2_drug_indication_metabolic_mid_manifest.json"),
        ]
    ]
    return [
        CompileTarget(
            name="treatment_pricing_wave2_manifest",
            rule_json=_RULES_DIR / "treatment_pricing_2_4.json",
            mode="stage",
            batches=[],
            dedup="first_wins",
            rule_set_id="treatment_pricing_2_4_wave2",
            title="",
            sut_anchors=[],
            stages=["treatment_pricing_wave2_manifest"],
            manifest_path=_MANIFEST_DIR / "L2.4_treatment_pricing_wave2_manifest.json",
            manifest_version="wave2-v1",
            manifest_filter_section="2.4.4",
            wave_scope_note=_TREATMENT_PRICING_WAVE2_SCOPE,
        ),
        *wave_manifest_targets,
        CompileTarget(
            name="payment_method_gate_b",
            rule_json=payment_json,
            mode="stage",
            batches=[],
            dedup="skip_dup",
            rule_set_id="payment_method_2_2",
            title="",
            sut_anchors=[],
            stages=["payment_pipeline"],
            manifest_path=_MANIFEST_DIR / "L2.2_payment_method_encoded_manifest.json",
            corpus_csv=_PROJECT_ROOT / "data/gazette/prose_corpus/L2.2_payment_method_prose.csv",
        ),
        CompileTarget(
            name="drug_indication_wave23",
            rule_json=_RULES_DIR / "drug_indication_prose.json",
            mode="stage",
            batches=[],
            dedup="union_overwrite",
            rule_set_id="drug_indication_wave23",
            title="",
            sut_anchors=[],
            stages=["wave23_patches"],
        ),
        CompileTarget(
            name="drug_indication_phase5",
            rule_json=_RULES_DIR / "drug_indication_prose.json",
            mode="stage",
            batches=[],
            dedup="skip_dup",
            rule_set_id="drug_indication_4.2.14.C",
            title="",
            sut_anchors=[],
            stages=["phase5_manifest"],
            gate_b_module="scripts.sut.prose.drug_indication_4214c_patches",
            manifest_path=_MANIFEST_DIR / "L4.2_drug_indication_4.2.14.C_manifest.json",
            corpus_csv=_PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv",
        ),
        CompileTarget(
            name="anti_vegf_manifest",
            rule_json=_RULES_DIR / "anti_vegf_prose.json",
            mode="stage",
            batches=[],
            dedup="union_overwrite",
            rule_set_id="anti_vegf_prose",
            title="",
            sut_anchors=[],
            stages=["antivegf_manifest"],
            manifest_path=_MANIFEST_DIR / "L4.33_anti_vegf_4.2.33_manifest.json",
        ),
        CompileTarget(
            name="material_bundling_manifest",
            rule_json=_RULES_DIR / "material_bundling_prose.json",
            mode="stage",
            batches=[],
            dedup="skip_dup",
            rule_set_id="material_bundling_prose",
            title="",
            sut_anchors=[],
            stages=["material_bundling_manifest"],
        ),
        CompileTarget(
            name="specialty_materials_manifest",
            rule_json=_RULES_DIR / "specialty_materials_prose.json",
            mode="stage",
            batches=[],
            dedup="skip_dup",
            rule_set_id="specialty_materials_prose",
            title="",
            sut_anchors=[],
            stages=["specialty_materials_manifest"],
        ),
    ]



def all_targets() -> list[CompileTarget]:
    fresh = _yaml_fresh_targets()
    drug_gate_b = _drug_gate_b_targets()
    tier_b_targets = [t for t in drug_gate_b if "tier_b" in t.name]
    drug_gate_b_main = [t for t in drug_gate_b if "tier_b" not in t.name]
    stages = _gate_b_stage_targets()
    phase5 = [t for t in stages if t.name == "drug_indication_phase5"]
    wave23 = [t for t in stages if t.name == "drug_indication_wave23"]
    stages_main = [
        t for t in stages if t.name not in {"drug_indication_phase5", "drug_indication_wave23"}
    ]
    return fresh + wave23 + tier_b_targets + drug_gate_b_main + phase5 + stages_main


# ─── compiler stages ──────────────────────────────────────────────────────────

def _existing_effective_date(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    effective = payload.get("effective_date")
    return str(effective) if effective else None


def _load_stage_rules(
    specs: list[tuple[str, str]],
    yaml_sources: list[Path] | None = None,
) -> list[dict]:
    rules: list[dict] = []
    for mod_path, attr in specs:
        rules.extend(_load_batch(mod_path, attr))
    if yaml_sources:
        rules.extend(load_yaml_sources(yaml_sources))
    return rules


def _rules_for_sections(rules: list[dict], prefixes: list[str]) -> list[dict]:
    if not prefixes:
        return list(rules)
    return [
        rule
        for rule in rules
        if any(str(rule.get("sut_section") or "").startswith(prefix) for prefix in prefixes)
    ]


def _batch_clause_ids(rules: list[dict]) -> dict[str, list[str]]:
    batches: dict[str, list[str]] = {}
    for rule in rules:
        batch = str(rule.get("encode_batch") or "")
        if not batch:
            continue
        batches.setdefault(batch, []).extend(rule.get("gate_b_sources") or [])
    return {key: sorted(set(values)) for key, values in batches.items()}


_PAYMENT_SESSION_MANIFEST_STUB: dict[str, object] = {
    "manifest_version": "wave2-v1",
    "rule_set_id": "session_pricing_2_2_2_B",
    "scope_note": (
        "§2.2.2.B session-fraction PARTIAL — runtime in session_pricing.py; "
        "4 JSON rules with Gate B clause traces (not merged into payment_method_2_2.json)"
    ),
    "rules_in_json": 4,
    "session_fraction_status": "PARTIAL",
    "gate_b_sources_encoded": ["C000654", "C000655", "C000657", "C000658", "C000659", "C000660", "C000661"],
    "encoded_clause_ids": ["C000654", "C000655", "C000657", "C000658", "C000659", "C000660", "C000661"],
    "gate_b_sources_by_rule": {
        "2.2.2.B.(1).ek2c_package_basis": ["C000654"],
        "2.2.2.B.(2).non_package_itemized": ["C000655"],
        "2.2.2.B.a": ["C000657"],
        "2.2.2.B.b": ["C000658"],
        "2.2.2.B.c": ["C000659"],
        "2.2.2.B.ç": ["C000660"],
        "2.2.2.B.(3).cross_specialty_uplift": ["C000661"],
    },
}


def _write_payment_session_manifest() -> None:
    session_json = _RULES_DIR / "session_pricing_2_2_2_B.json"
    session_payload = json.loads(session_json.read_text(encoding="utf-8"))
    manifest = dict(_PAYMENT_SESSION_MANIFEST_STUB)
    manifest["rules_in_json"] = len(session_payload.get("rules") or [])
    _write_json(_MANIFEST_DIR / "L2.2_session_pricing_2_2_2_B_encoded_manifest.json", manifest)


def _apply_payment_manifest_cross_refs(
    manifest: dict[str, object],
    rule_count: int,
    batch_num: str,
) -> dict[str, object]:
    suffix = {
        "2": "batch-1+2",
        "3": "batch-1+2+3",
        "4": "batch-1–4",
    }.get(batch_num, f"batch-{batch_num}")
    manifest["scope_note"] = f"§2.2 package vs itemized vs tier-override ({rule_count} JSON rules, C2 {suffix})"
    manifest["rules_in_json"] = rule_count
    manifest["session_fraction_status"] = "PARTIAL"
    manifest["related_rule_sets"] = [
        {
            "rule_set_id": "session_pricing_2_2_2_B",
            "json_path": "session_pricing_2_2_2_B.json",
            "manifest": "L2.2_session_pricing_2_2_2_B_encoded_manifest.json",
            "note": "§2.2.2.B session-fraction remains PARTIAL — see session_pricing.py",
        }
    ]
    return manifest


def _stage_write_gate_b_artifacts(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    """Phase 3 gate-B stage backed by retained batch/gate-B modules."""
    if not target.gate_b_module or not target.manifest_path or not target.corpus_csv:
        raise ValueError(f"target {target.name} missing gate-B stage configuration")
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    stage_rules = _load_stage_rules(target.batches, target.yaml_sources)
    manifest_rules = _load_stage_rules(target.manifest_batches)

    if target.name == "drug_indication_4213_tier_b_remap":
        oral_switch_rule_ids = {
            "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
        }
        by_id = {str(rule["rule_id"]): dict(rule) for rule in existing}
        for raw in stage_rules:
            clean = _strip_batch(raw)
            rule_id = str(clean["rule_id"])
            if rule_id in oral_switch_rule_ids and rule_id in by_id:
                by_id[rule_id] = {**by_id[rule_id], **clean}
        merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
        payload["rules"] = merged
        payload["coverage_note"] = (
            f"R5 TierB remap — {len(merged)} rules; §4.2.13 oral-switch sources "
            "remapped to in-force C004584/C004593."
        )
        _write_rule_set_for_target(target, payload)
    elif target.merge_rules and stage_rules:
        merged, _added, _covered = _dedup_union_overwrite(existing, stage_rules)
        payload["rules"] = merged
        _write_rule_set_for_target(target, payload)
    else:
        merged = existing

    mod = importlib.import_module(target.gate_b_module)
    effective_date = _existing_effective_date(target.manifest_path) or date.today().isoformat()
    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"

    if target.gate_b_writer == "from_prose":
        writer = getattr(mod, "write_gate_b_artifacts_from_prose")
        frame, manifest = writer(
            clauses_path=clauses_path,
            rules_path=target.rule_json,
            corpus_csv=target.corpus_csv,
            manifest_path=target.manifest_path,
            effective_date=effective_date,
        )
    elif target.gate_b_writer == "section_rules":
        writer = getattr(mod, "write_gate_b_artifacts")
        rules = manifest_rules or _rules_for_sections(merged, target.section_prefixes) or merged
        frame, manifest = writer(
            clauses_path=clauses_path,
            rules=rules,
            corpus_csv=target.corpus_csv,
            manifest_path=target.manifest_path,
            effective_date=effective_date,
        )
    elif target.gate_b_writer == "batch_rules":
        writer = getattr(mod, "write_gate_b_artifacts")
        if target.name == "drug_indication_4201_w4" and hasattr(mod, "is_421_proper"):
            is_421_proper = getattr(mod, "is_421_proper")
            base_rules = [rule for rule in merged if is_421_proper(str(rule.get("sut_section") or ""))]
        else:
            base_rules = _rules_for_sections(merged, target.section_prefixes) if target.section_prefixes else merged
        combined, _added, _covered = _dedup_union_overwrite(base_rules, manifest_rules)
        frame, manifest = writer(
            clauses_path=clauses_path,
            batch_rules=combined,
            corpus_csv=target.corpus_csv,
            manifest_path=target.manifest_path,
            effective_date=effective_date,
        )
    elif target.gate_b_writer == "rules_path_with_batch_rules":
        writer = getattr(mod, "write_gate_b_artifacts")
        batch_for_writer = manifest_rules if manifest_rules else None
        frame, manifest = writer(
            clauses_path=clauses_path,
            rules_path=target.rule_json,
            corpus_csv=target.corpus_csv,
            manifest_path=target.manifest_path,
            effective_date=effective_date,
            batch_rules=batch_for_writer,
        )
    elif target.gate_b_writer == "shared_manifest":
        writer = getattr(mod, "write_gate_b_artifacts")
        frame, manifest = writer(
            clauses_path=clauses_path,
            rules_path=target.rule_json,
            corpus_csv=target.corpus_csv,
            shared_manifest_path=target.manifest_path,
            effective_date=effective_date,
        )
    else:
        writer = getattr(mod, "write_gate_b_artifacts")
        frame, manifest = writer(
            clauses_path=clauses_path,
            rules_path=target.rule_json,
            corpus_csv=target.corpus_csv,
            manifest_path=target.manifest_path,
            effective_date=effective_date,
        )
    return {
        "rows": getattr(frame, "height", None),
        "encoded": manifest.get("encoded_clause_count") or len(manifest.get("encoded_clause_ids") or []),
    }


def _stage_csv_wave_clause_ids(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    merged = list(payload.get("rules") or [])
    wave_clause_ids = DRUG_INDICATION_WAVE_CLAUSE_IDS[target.rule_set_id]
    manifest = {
        "manifest_version": "drug-indication-wave-v1",
        "rule_set_id": target.rule_set_id,
        "rules_in_json": len(merged),
        "rules_added": 0,
        "wave_clause_ids": wave_clause_ids,
        "gate_b_sources_encoded": wave_clause_ids,
    }
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing CSV-wave manifest path")
    _write_json(target.manifest_path, manifest)
    return {"added": 0, "encoded": len(wave_clause_ids)}


def _stage_payment_pipeline(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    from scripts.sut.prose.payment_method_gate_b import run_gate_b_pipeline

    if not target.manifest_path or not target.corpus_csv:
        raise ValueError(f"target {target.name} missing payment pipeline paths")
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = list(payload.get("rules") or [])

    _write_payment_session_manifest()

    result = run_gate_b_pipeline(
        clauses_path=_PROJECT_ROOT / "data/gazette/sut_clauses.parquet",
        prose_json_path=target.rule_json,
        corpus_csv_path=target.corpus_csv,
        manifest_path=target.manifest_path,
        write_prose_json=True,
    )
    manifest = _apply_payment_manifest_cross_refs(result["manifest"], len(rules), "4")
    _write_json(target.manifest_path, manifest)
    return {"added": 0, "skipped": [], "encoded": len(manifest.get("gate_b_sources_encoded") or [])}


def _apply_source_patches(
    rules: list[dict[str, Any]],
    patch_modules: list[str],
) -> tuple[list[dict[str, Any]], int]:
    """Merge SOURCE_PATCHES clause IDs into existing rules (append-only)."""
    by_id = {str(rule["rule_id"]): dict(rule) for rule in rules}
    patched = 0
    for module_path in patch_modules:
        mod = importlib.import_module(module_path)
        for rule_id, clause_ids in getattr(mod, "SOURCE_PATCHES", {}).items():
            if rule_id not in by_id:
                raise KeyError(f"SOURCE_PATCHES references missing rule_id: {rule_id} ({module_path})")
            before = set(by_id[rule_id].get("gate_b_sources") or [])
            by_id[rule_id]["gate_b_sources"] = sorted(before | {str(c) for c in clause_ids})
            if set(by_id[rule_id]["gate_b_sources"]) != before:
                patched += 1
    merged = sorted(by_id.values(), key=lambda r: str(r.get("rule_id", "")))
    return merged, patched


def _stage_wave23_patches(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    """Wave 2/3 — append gate_b_sources for tier A/B promotions."""
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    modules = [
        "scripts.sut.prose.drug_indication_wave23_patches",
        "scripts.sut.prose.drug_indication_bucket_a_patches",
        "scripts.sut.prose.drug_indication_bucket_b_patches",
    ]
    if target.gate_b_module:
        modules.insert(0, str(target.gate_b_module))
    merged, patched = _apply_source_patches(existing, modules)
    payload["rules"] = sorted([_strip_batch(r) for r in merged], key=lambda r: str(r.get("rule_id", "")))
    _write_rule_set_for_target(target, payload)
    return {"patched": patched, "rules": len(merged)}


def _stage_phase5_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    from scripts.sut.prose.drug_indication_a1_manifest_coverage import repair_4214c_manifest
    from scripts.sut.prose.drug_indication_gate_b import write_gate_b_export

    if not target.manifest_path or not target.corpus_csv:
        raise ValueError(f"target {target.name} missing phase5 manifest paths")
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])

    added = patched = 0
    if target.gate_b_module:
        mod = importlib.import_module(str(target.gate_b_module))
        merged, patched = _apply_source_patches(existing, [str(target.gate_b_module)])
        covered: set[str] = set()
        for rule_id, clause_ids in getattr(mod, "SOURCE_PATCHES", {}).items():
            covered.update(clause_ids)
        pending = getattr(mod, "PENDING_CLAUSE_IDS", set())
        if pending:
            missing = sorted(pending - covered)
            if missing:
                raise RuntimeError(f"Phase 5 merge did not cover pending clause IDs: {missing}")
        phase1_added, phase2_added = 0, 0
    else:
        merged = existing
        phase1_added, phase2_added = 0, 0

    payload["rules"] = sorted([_strip_batch(r) for r in merged], key=lambda r: str(r.get("rule_id", "")))
    payload["title"] = "SUT §4.2 drug indication and report requirements (4.2.14.C Phase 5)"
    payload["coverage_note"] = (
        f"Phase 0–5 — {len(payload['rules'])} rules for §4.2.14.C; full clause trace manifest "
        "(encoded + pending + Tier C deferred with theme tags)."
    )
    payload["sut_anchors"] = ["4.2", "4.2.14.C"]
    _write_rule_set_for_target(target, payload)

    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
    write_gate_b_export(clauses_path, target.corpus_csv, rules_path=target.rule_json)
    effective_date = _existing_effective_date(target.manifest_path) or date.today().isoformat()
    manifest = repair_4214c_manifest(
        clauses_path=clauses_path,
        rules_path=target.rule_json,
        manifest_path=target.manifest_path,
        effective_date=effective_date,
    )
    return {
        "added": phase1_added + phase2_added,
        "patched": patched,
        "encoded": manifest.get("encoded_clause_count", 0),
        "in_force_traces": manifest.get("section_clause_total", 0),
    }


def _stage_antivegf_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _compile_antivegf_manifest(target)


def _stage_tier_b_remap(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _stage_write_gate_b_artifacts(target, ctx)


def _stage_material_bundling_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _write_material_bundling_manifest(target)


def _stage_specialty_materials_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _write_specialty_materials_manifest(target)


def _stage_treatment_pricing_wave2_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = payload.get("rules") or []
    filter_sec = target.manifest_filter_section or "2.4.4"
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for rule in rules:
        srcs = rule.get("gate_b_sources") or []
        if not srcs:
            continue
        if not str(rule.get("sut_section", "")).startswith(filter_sec):
            continue
        sources_by_rule[str(rule["rule_id"])] = srcs
        encoded.update(str(cid) for cid in srcs)

    if target.manifest_path and target.manifest_path.is_file():
        manifest = json.loads(target.manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "manifest_version": target.manifest_version,
            "rule_set_id": target.rule_set_id,
            "scope_note": target.wave_scope_note,
            "rules_added_wave2_rest": _TREATMENT_PRICING_WAVE2_COUNTS["wave2_rest"],
            "rules_added_wave2a": _TREATMENT_PRICING_WAVE2_COUNTS["wave2a"],
            "rules_added_wave2b": _TREATMENT_PRICING_WAVE2_COUNTS["wave2b"],
            "rules_added_wave2c": _TREATMENT_PRICING_WAVE2_COUNTS["wave2c"],
            "rules_skipped_dup": [],
        }
    manifest["rules_in_json"] = len(rules)
    manifest["encoded_clause_ids"] = sorted(encoded)
    manifest["gate_b_sources_by_rule"] = sources_by_rule
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing manifest path")
    _write_json(target.manifest_path, manifest)
    return {"encoded": len(encoded), "rules": len(rules)}


def _compile_antivegf_manifest(target: CompileTarget) -> dict:
    import polars as pl
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    merged = list(payload.get("rules") or [])
    encoded_ids = {str(cid) for rule in merged for cid in (rule.get("gate_b_sources") or [])}
    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
    section = pl.read_parquet(clauses_path).filter(
        pl.col("section_id").str.starts_with("4.2.33") & pl.col("is_in_force")
    )
    rules_by_clause: dict[str, list[str]] = {}
    clause_traces: dict[str, list[str]] = {}
    for rule in merged:
        rid = str(rule.get("rule_id") or "")
        clause_traces[rid] = sorted(str(c) for c in (rule.get("gate_b_sources") or []))
        for cid in rule.get("gate_b_sources") or []:
            rules_by_clause.setdefault(str(cid), []).append(rid)

    tier_c_deferred: list[str] = []
    traces: list[dict[str, Any]] = []
    for row in section.sort("clause_id").iter_rows(named=True):
        clause_id = str(row["clause_id"])
        text = str(row.get("text_tr") or "")
        if clause_id in encoded_ids:
            entry: dict[str, Any] = {
                "clause_id": clause_id,
                "section_id": str(row.get("section_id") or ""),
                "manifest_status": "encoded",
                "linked_rule_ids": sorted(rules_by_clause.get(clause_id, [])),
            }
        elif str(row.get("clause_type") or "") in {"section_heading", "chapter"} and not row.get("deontic_modality"):
            entry = {
                "clause_id": clause_id,
                "section_id": str(row.get("section_id") or ""),
                "manifest_status": "non_actionable",
            }
        else:
            themes = infer_defer_themes(text)
            tier_c_deferred.append(clause_id)
            entry = {
                "clause_id": clause_id,
                "section_id": str(row.get("section_id") or ""),
                "manifest_status": "tier_c_deferred",
                "defer_themes": themes,
                "defer_reason": (
                    "Deferred — dose pathway / combination rule not yet structurable "
                    f"({', '.join(themes) if themes else 'clinical_pathway'})."
                ),
            }
        traces.append(entry)

    in_force_ids = {str(cid) for cid in section["clause_id"].to_list()}
    effective_date = _existing_effective_date(target.manifest_path) or date.today().isoformat()
    manifest = {
        "manifest_version": "r5-a2c-v1",
        "section_id": "4.2.33",
        "effective_date": effective_date,
        "rule_set_id": "anti_vegf_prose",
        "rules_in_json": len(merged),
        "section_clause_total": section.height,
        "clause_trace_complete": len({t["clause_id"] for t in traces} - {t["clause_id"] for t in traces if t["manifest_status"] == "non_actionable"}) == len((encoded_ids & in_force_ids) | set(tier_c_deferred)),
        "manifest_coverage_pct": round(100.0 * len(encoded_ids) / section.height, 1) if section.height else 0.0,
        "encoded_clause_count": len(encoded_ids & in_force_ids),
        "encoded_clause_ids": sorted(encoded_ids & in_force_ids),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_c_deferred_count": len(tier_c_deferred),
        "clause_traces": clause_traces,
        "clause_trace_rows": traces,
        "note": (
            f"§4.2.33 anti-VEGF A2c — {len(merged)} rules, {len(encoded_ids)} encoded "
            f"clause sources, {len(tier_c_deferred)} tier-C deferred in-force rows."
        ),
    }
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing manifest path")
    _write_json(target.manifest_path, manifest)
    return {"added": 0, "covered": len(encoded_ids)}


def _write_material_bundling_manifest(target: CompileTarget) -> dict:
    from scripts.sut.prose.manifest_clause_ids import (
        EK3C_LIST_PRICE_CEILING_CLAUSE_IDS,
        EK3_SCOPE_ONLY_CLAUSE_IDS,
        GATE_B_STILL_DEFERRED_CLAUSE_IDS,
        KDV_PRICING_CLAUSE_IDS,
        MALZEME_SCOPE_ONLY_CLAUSE_IDS,
        R5_AMENDMENT_HEADER_CLAUSE_IDS,
        R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS,
        SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS,
        load_ek3_annex_header_clause_ids,
        load_malzeme_general_header_clause_ids,
    )

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = list(payload.get("rules") or [])
    sources = sorted({str(cid) for rule in rules for cid in (rule.get("gate_b_sources") or [])})
    manifest = {
        "rules_in_json": len(rules),
        "rules_added": 0,
        "rules_patched": 0,
        "gate_b_sources_encoded": sources,
        "gate_b_deferred_clause_ids": sorted(GATE_B_STILL_DEFERRED_CLAUSE_IDS),
        "kdv_pricing_clause_ids": sorted(KDV_PRICING_CLAUSE_IDS),
        "separate_billing_allowlist_clause_ids": ["C001823"],
        "ek3c_list_price_ceiling_clause_ids": sorted(EK3C_LIST_PRICE_CEILING_CLAUSE_IDS),
        "sut_material_list_price_ceiling_clause_ids": sorted(SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS),
        "corpus_ek3_annex_header_clause_ids": sorted(load_ek3_annex_header_clause_ids()),
        "corpus_ek3_scope_clause_ids": sorted(EK3_SCOPE_ONLY_CLAUSE_IDS),
        "corpus_malzeme_general_header_clause_ids": sorted(load_malzeme_general_header_clause_ids()),
        "corpus_malzeme_scope_clause_ids": sorted(MALZEME_SCOPE_ONLY_CLAUSE_IDS),
        "r5_amendment_header_clause_ids": sorted(R5_AMENDMENT_HEADER_CLAUSE_IDS),
        "r5_manifest_header_only_clause_ids": sorted(R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS),
    }
    _write_json(_MANIFEST_DIR / "L1.4_material_bundling_encoded_manifest.json", manifest)
    return {"added": 0, "patched": 0, "encoded": len(sources)}


def _write_specialty_materials_manifest(target: CompileTarget) -> dict:
    from scripts.sut.prose.manifest_clause_ids import (
        GLUCOSE_METER_BATCH_CLAUSE_IDS,
        OTHER_3_3_TAIL_CLAUSE_IDS,
        SPECIALTY_334_BATCH_CLAUSE_IDS,
        SPECIALTY_336_BATCH_CLAUSE_IDS,
        SPECIALTY_337_BATCH_CLAUSE_IDS,
        SPECIALTY_338_BATCH_CLAUSE_IDS,
        SPECIALTY_R5_HEADER_CLAUSE_IDS,
        VISION_OPTIK_BATCH_CLAUSE_IDS,
        WOUND_331_PILOT_CLAUSE_IDS,
    )

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = list(payload.get("rules") or [])
    sources = sorted({str(cid) for rule in rules for cid in (rule.get("gate_b_sources") or [])})
    manifest = {
        "rules_in_json": len(rules),
        "rules_added": 0,
        "rules_patched": 0,
        "pilot_331_clause_ids": sorted(WOUND_331_PILOT_CLAUSE_IDS),
        "vision_optik_batch_clause_ids": sorted(VISION_OPTIK_BATCH_CLAUSE_IDS),
        "specialty_334_batch_clause_ids": sorted(SPECIALTY_334_BATCH_CLAUSE_IDS),
        "glucose_meter_batch_clause_ids": sorted(GLUCOSE_METER_BATCH_CLAUSE_IDS),
        "specialty_337_batch_clause_ids": sorted(SPECIALTY_337_BATCH_CLAUSE_IDS),
        "specialty_338_batch_clause_ids": sorted(SPECIALTY_338_BATCH_CLAUSE_IDS),
        "specialty_336_batch_clause_ids": sorted(SPECIALTY_336_BATCH_CLAUSE_IDS),
        "other_3_3_tail_clause_ids": sorted(OTHER_3_3_TAIL_CLAUSE_IDS),
        "r5_specialty_header_clause_ids": sorted(SPECIALTY_R5_HEADER_CLAUSE_IDS),
        "gate_b_sources_encoded": sources,
    }
    _write_json(_MANIFEST_DIR / "L4.4_specialty_prose_encoded_manifest.json", manifest)
    return {"added": 0, "patched": 0, "encoded": len(sources)}


_STAGES = {
    "write_gate_b_artifacts": _stage_write_gate_b_artifacts,
    "csv_wave_clause_ids": _stage_csv_wave_clause_ids,
    "payment_pipeline": _stage_payment_pipeline,
    "phase5_manifest": _stage_phase5_manifest,
    "wave23_patches": _stage_wave23_patches,
    "antivegf_manifest": _stage_antivegf_manifest,
    "tier_b_remap": _stage_tier_b_remap,
    "treatment_pricing_wave2_manifest": _stage_treatment_pricing_wave2_manifest,
    "material_bundling_manifest": _stage_material_bundling_manifest,
    "specialty_materials_manifest": _stage_specialty_materials_manifest,
}


def _run_stages(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    results: dict[str, Any] = {}
    for stage_name in target.stages:
        stage = _STAGES.get(stage_name)
        if stage is None:
            raise ValueError(f"unknown stage {stage_name!r} for target {target.name}")
        results[stage_name] = stage(target, ctx)
    return results


# ─── compile logic ────────────────────────────────────────────────────────────

def _compile_yaml_merge(target: CompileTarget) -> dict:
    """Merge YAML section sources into an existing rule JSON (dedup union)."""
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    yaml_rules = _load_target_rules(target)
    if not yaml_rules:
        raise ValueError(f"{target.name}: no rules loaded from yaml_sources")
    combined, added, _covered = _dedup_union_overwrite(existing, yaml_rules)
    payload["rules"] = combined
    _write_rule_set_for_target(target, payload)
    return {"yaml_rules": len(yaml_rules), "added": added, "total": len(combined)}


def _compile_fresh(target: CompileTarget) -> dict:
    """Build a rule JSON from scratch (Tier A pattern)."""
    all_rules: list[dict] = _load_target_rules(target)

    if target.dedup == "first_wins":
        rules = _dedup_first_wins(all_rules)
    elif target.dedup == "union_overwrite":
        rules, _, _ = _dedup_union_overwrite([], all_rules)
    else:
        rules = all_rules

    if target.strip_batch:
        rules = [_strip_batch(r) for r in rules]

    envelope = _envelope_from_json(target.rule_json)
    committed_by_id = _committed_rules_by_id(target.rule_json)
    if committed_by_id:
        by_id = {str(rule["rule_id"]): rule for rule in rules}
        ordered: list[dict] = []
        seen: set[str] = set()
        committed_payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
        for raw in committed_payload.get("rules") or []:
            rule_id = str(raw.get("rule_id") or "")
            if rule_id in by_id:
                ordered.append(_reconcile_rule_with_committed(committed_by_id.get(rule_id), by_id[rule_id]))
                seen.add(rule_id)
        for rule_id in sorted(by_id):
            if rule_id not in seen:
                ordered.append(by_id[rule_id])
        rules = ordered

    payload = {
        "rule_set_id": target.rule_set_id,
        "title": envelope.get("title", target.title),
        "effective_date": envelope.get("effective_date", target.effective_date),
        "sut_anchors": envelope.get("sut_anchors", target.sut_anchors),
        "rules": rules,
    }
    if "coverage_note" in envelope:
        payload["coverage_note"] = envelope["coverage_note"]
    _write_rule_set_for_target(target, payload)

    # manifest
    if target.manifest_path and not target.skip_manifest:
        extra = dict(target.manifest_extra_keys or {})
        include_encoded_key = extra.pop("_include_gate_b_sources_encoded", False)
        encoded_list = None
        if include_encoded_key:
            encoded_list = sorted({cid for r in rules for cid in (r.get("gate_b_sources") or [])})
        manifest = _build_gap_manifest(rules, target.rule_set_id,
                                       manifest_version=target.manifest_version,
                                       extra_keys=extra or None,
                                       gate_b_sources_encoded=encoded_list)
        _write_json(target.manifest_path, manifest)

    # golden
    if target.golden_path and not target.skip_golden:
        # Match the exact description format each merge script used.
        if target.rule_set_id in ("treatment_pricing_2_4", "dental_2_4_1", "drug_combination_4_2"):
            desc = f"Gate B golden — {target.rule_set_id} clause → rule_id provenance"
        else:
            desc = f"Gate B golden — {target.rule_set_id}"
        golden = _build_golden(rules, target.rule_set_id,
                               include_encode_batch=target.golden_include_encode_batch)
        preserved_batches = _preserved_golden_batches(target.golden_path)
        for case in golden.get("cases") or []:
            key = (str(case["clause_id"]), str(case["expected_rule_id"]))
            if key in preserved_batches:
                case["encode_batch"] = preserved_batches[key]
        golden["description"] = desc
        _write_json(target.golden_path, golden)

    return {"rules": len(rules), "json": str(target.rule_json.name)}


def _compile_append(target: CompileTarget, group_state: dict) -> dict:
    """Append to an existing rule JSON (Tier F wave2 pattern)."""
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing_rules = list(payload.get("rules") or [])

    new_rules: list[dict] = _load_target_rules(target)

    if target.dedup == "union_overwrite":
        combined, added, covered = _dedup_union_overwrite(existing_rules, new_rules)
        skipped: list[str] = []
    else:
        combined, skipped = _dedup_skip_dup(existing_rules, new_rules)
        added = len(combined) - len(existing_rules)
        covered = {cid for r in new_rules for cid in (r.get("gate_b_sources") or [])}
    payload["rules"] = combined

    # append new sut_anchors
    anchors = list(dict.fromkeys(payload.get("sut_anchors") or []))
    new_sections = sorted({r["sut_section"] for r in new_rules if r.get("sut_section") not in anchors})
    payload["sut_anchors"] = anchors + [s for s in new_sections if s not in anchors]

    _write_rule_set_for_target(target, payload)

    # track wave additions for shared manifest
    if target.shared_manifest_group:
        gkey = target.wave_label or target.name
        group_state.setdefault("wave_added", {})[gkey] = added
        group_state.setdefault("wave_skipped", []).extend(skipped)

    return {"added": added, "skipped": skipped, "covered_sources": len(covered),
            "total": len(combined), "json": str(target.rule_json.name)}


def _finalize_shared_manifest(target: CompileTarget, group_state: dict) -> None:
    """Build the cumulative shared manifest after all append targets in the group ran."""
    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = payload.get("rules") or []

    # filter to section if specified (wave2 only counts §2.4.4)
    filter_sec = target.manifest_filter_section
    sources_by_rule: dict[str, list[str]] = {}
    encoded: set[str] = set()
    for r in rules:
        srcs = r.get("gate_b_sources") or []
        if not srcs:
            continue
        if filter_sec and not str(r.get("sut_section", "")).startswith(filter_sec):
            continue
        sources_by_rule[r["rule_id"]] = srcs
        encoded.update(srcs)

    wave_added = group_state.get("wave_added", {})
    manifest = {
        "manifest_version": target.manifest_version,
        "rule_set_id": target.rule_set_id,
    }
    if target.wave_scope_note:
        manifest["scope_note"] = target.wave_scope_note
    manifest["rules_in_json"] = len(rules)
    for label, count in sorted(wave_added.items()):
        manifest[f"rules_added_{label}"] = count
    manifest["rules_skipped_dup"] = sorted(set(group_state.get("wave_skipped", [])))
    manifest["encoded_clause_ids"] = sorted(encoded)
    manifest["gate_b_sources_by_rule"] = sources_by_rule
    _write_json(target.manifest_path, manifest)


def compile_target(target: CompileTarget, group_state: dict | None = None) -> dict:
    """Compile a single target."""
    ctx: dict[str, Any] = {}
    if target.mode == "fresh":
        result = _compile_fresh(target)
    elif target.mode == "append":
        gs = group_state if group_state is not None else {}
        result = _compile_append(target, gs)
    elif target.mode == "yaml_merge":
        result = _compile_yaml_merge(target)
    elif target.mode == "stage":
        result = {"stage_only": True}
    else:
        raise ValueError(f"unknown mode: {target.mode}")
    if target.stages:
        result["stages"] = _run_stages(target, ctx)
    return result


def compile_all(targets: list[CompileTarget] | None = None) -> None:
    """Compile all targets, handling shared-manifest groups."""
    targets = targets or all_targets()

    # group append targets by shared_manifest_group
    groups: dict[str, list[CompileTarget]] = {}
    standalone: list[CompileTarget] = []
    for t in targets:
        if t.shared_manifest_group and t.mode == "append":
            groups.setdefault(t.shared_manifest_group, []).append(t)
        else:
            standalone.append(t)

    # compile standalone (fresh) targets first
    for t in standalone:
        result = compile_target(t)
        print(f"  ✓ {t.name}: {result}")

    # compile shared-manifest groups (append targets that share one manifest)
    for group_name, group_targets in groups.items():
        group_state: dict = {}
        last_target = None
        for t in group_targets:
            result = compile_target(t, group_state)
            print(f"  ✓ {t.name}: {result}")
            last_target = t
        # finalize the shared manifest after all appends
        if last_target and last_target.manifest_path:
            _finalize_shared_manifest(last_target, group_state)
            print(f"    → shared manifest: {last_target.manifest_path.name}")

    from scripts.sut.close_algorithmic_gaps import apply_snapshot

    gap_stats = apply_snapshot()
    if gap_stats.get("clauses_deferred"):
        print(f"  ✓ gap_closure_tier_c: {gap_stats}")

    from scripts.sut.prose.manifest_reconcile import reconcile_drug_manifests

    reconcile_report = reconcile_drug_manifests()
    if reconcile_report.manifests_touched:
        print(
            f"  ✓ manifest_reconcile: {reconcile_report.manifests_touched} drug manifest(s) synced"
        )


def check(targets: list[CompileTarget] | None = None) -> int:
    """Verify compiler output matches committed artifacts. Returns exit code."""
    import fcntl

    targets = targets or all_targets()

    lock_path = Path("/tmp/bilun_compile_rules_check.lock")
    lock_file = lock_path.open("w", encoding="utf-8")
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

    paths: set[Path] = set()
    paths.update(_RULES_DIR.rglob("*.json"))
    paths.update(_MANIFEST_DIR.glob("*.json"))
    paths.update((_PROJECT_ROOT / "data/gazette/prose_corpus").glob("*.csv"))
    for t in targets:
        paths.update(p for p in [t.rule_json, t.manifest_path, t.golden_path, t.corpus_csv] if p is not None)
        paths.update(t.output_paths)

    before = {path: path.read_bytes() if path.exists() else None for path in sorted(paths)}
    try:
        import contextlib
        import io as _io

        # Suppress compile_all's stage-status output so --check prints only the verdict.
        with contextlib.redirect_stdout(_io.StringIO()):
            compile_all(targets)
        after_paths = set(before)
        after_paths.update(_RULES_DIR.rglob("*.json"))
        after_paths.update(_MANIFEST_DIR.glob("*.json"))
        after_paths.update((_PROJECT_ROOT / "data/gazette/prose_corpus").glob("*.csv"))
        mismatches = []
        for path in sorted(after_paths):
            old = before.get(path)
            new = path.read_bytes() if path.exists() else None
            if old != new:
                status = "created" if old is None else "deleted" if new is None else "changed"
                mismatches.append((status, path))
        if mismatches:
            print("check failed: compiler output differs from current artifacts")
            for status, path in mismatches[:50]:
                print(f"  {status}: {path.relative_to(_PROJECT_ROOT)}")
            if len(mismatches) > 50:
                print(f"  ... {len(mismatches) - 50} more")
            return 1
        print(f"check ok: {len(after_paths)} rule/manifest/corpus artifacts byte-identical")
        return 0
    finally:
        for path, content in before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)


def list_targets() -> None:
    for t in all_targets():
        mode = f"[{t.mode}]"
        group = f" (group: {t.shared_manifest_group})" if t.shared_manifest_group else ""
        print(f"  {t.name:40s} {mode:10s} → {t.rule_json.name}{group}")


def _select_targets(target_name: str | None) -> list[CompileTarget]:
    targets = all_targets()
    if not target_name:
        return targets
    match = [t for t in targets if t.name == target_name]
    if not match:
        print(f"unknown target: {target_name}")
        sys.exit(1)
    return match


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Unified rule compiler.")
    parser.add_argument("--target", type=str, default=None, help="Compile a single target by name.")
    parser.add_argument("--check", action="store_true", help="Verify output matches committed (CI mode).")
    parser.add_argument("--list", action="store_true", help="List all compile targets.")
    args = parser.parse_args()

    if args.list:
        list_targets()
        return
    if args.check:
        sys.exit(check(_select_targets(args.target)))
    if args.target:
        compile_all(_select_targets(args.target))
    else:
        print("compiling all targets...")
        compile_all()
        print("done.")


if __name__ == "__main__":
    main()
