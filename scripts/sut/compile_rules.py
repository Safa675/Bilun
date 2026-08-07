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
import functools
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


def _load_target_rules(target: CompileTarget) -> list[dict]:
    """Load rules from YAML section sources."""
    if target.yaml_sources:
        return load_yaml_sources(target.yaml_sources)
    return []


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
    _assert_gate_b_cites_resolvable(payload, rule_set_id)
    _write_json(path, payload)


def _assert_gate_b_cites_resolvable(payload: dict, rule_set_id: str) -> None:
    """Track A3 — gate_b_sources must be unique encode-eligible cites."""
    clauses_path = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
    if not clauses_path.is_file():
        return
    import polars as pl

    from scripts.sut.prose.clause_identity import assert_gate_b_sources_resolvable
    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

    frame = apply_clause_type_overrides(pl.read_parquet(clauses_path))
    assert_gate_b_sources_resolvable(
        list(payload.get("rules") or []),
        frame,
        rule_set_id=rule_set_id,
    )


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


@functools.lru_cache(maxsize=1)
def _clauses_frame():
    """Cached clause corpus (with type overrides) for gate_b resolution."""
    import polars as pl

    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

    path = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
    return apply_clause_type_overrides(pl.read_parquet(path))


@functools.lru_cache(maxsize=1)
def _clause_id_to_key() -> dict:
    """Map clause_id -> stable clause_key (Track E) for manifest dual-write."""
    frame = _clauses_frame()
    out: dict = {}
    if "clause_key" not in frame.columns or "clause_id" not in frame.columns:
        return out
    for cid, key in zip(frame["clause_id"].to_list(), frame["clause_key"].to_list()):
        if cid is not None and key is not None:
            out[str(cid)] = str(key)
    return out


def _resolve_gate_b_ids(refs: list[Any]) -> set[str]:
    """Resolve gate_b_sources refs (C* / coordinate / clause_key) to clause_ids.

    Track E dual-read: clause_key (``coord#hash``) refs resolve via content hash;
    C* pass through; unresolvable cites are soft-skipped (C* kept as-is).
    ``encode_eligible_only`` is off so prose/amendment C* behave exactly as before.
    """
    from scripts.sut.prose.clause_identity import (
        is_clause_id,
        resolve_gate_b_ref_to_clause_ids,
    )

    frame = _clauses_frame()
    out: set[str] = set()
    for raw in refs:
        text = str(raw).strip()
        if not text:
            continue
        try:
            out.update(
                resolve_gate_b_ref_to_clause_ids(
                    text, frame, in_force_only=True, encode_eligible_only=False
                )
            )
        except Exception:
            if is_clause_id(text):
                out.add(text)
    return out


# ─── manifest builders ────────────────────────────────────────────────────────

def _build_gap_manifest(rules: list[dict], rule_set_id: str, *, manifest_version: str = "canonical-v1",
                        extra_keys: dict[str, Any] | None = None,
                        section_id: str = "") -> dict:
    """Canonical encoded-only manifest from rule gate_b_sources."""
    from scripts.sut.prose.manifest_index import build_canonical_encoded_shell

    encoded: set[str] = set()
    for r in rules:
        encoded.update(_resolve_gate_b_ids(r.get("gate_b_sources") or []))
    id_to_key = _clause_id_to_key()
    keys = {id_to_key[cid] for cid in encoded if cid in id_to_key}
    return build_canonical_encoded_shell(
        rule_set_id=rule_set_id,
        encoded_clause_ids=encoded,
        encoded_clause_keys=keys,
        section_id=section_id,
        rules_in_json=len(rules),
        extra_keys=extra_keys,
    )


def _build_golden(rules: list[dict], rule_set_id: str, *, include_encode_batch: bool = True) -> dict:
    """Provenance golden: clause_id → expected_rule_id mapping."""
    cases = []
    for r in rules:
        for cid in sorted(_resolve_gate_b_ids(r.get("gate_b_sources") or [])):
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
    mode: str  # "fresh" | "yaml_merge" | "stage"
    dedup: str  # "first_wins" | "union_overwrite" | "skip_dup"
    rule_set_id: str
    title: str
    sut_anchors: list[str]
    yaml_sources: list[Path] = field(default_factory=list)
    effective_date: str = "2026-05-23"
    strip_batch: bool = True
    # manifest
    manifest_path: Path | None = None
    manifest_version: str = "canonical-v1"
    manifest_extra_keys: dict[str, Any] | None = None
    manifest_filter_section: str | None = None  # e.g. "2.4.4" — only count clauses from this section
    # golden
    golden_path: Path | None = None
    golden_include_encode_batch: bool = True
    # wave tracking (for wave2-style manifests)
    wave_label: str | None = None  # e.g. "wave2a"
    wave_scope_note: str | None = None
    # stage-driven targets (Phase 3/4)
    stages: list[str] = field(default_factory=list)
    gate_b_module: str | None = None
    gate_b_section: str | None = None
    gate_b_writer: str = "rules_path"
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
    manifest_version: str = "canonical-v1",
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
            skip_golden=True,
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
            skip_golden=True,
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
            skip_golden=True,
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
            manifest_version="canonical-v1",
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
            manifest_version="canonical-v1",
            golden_path=_GOLDEN_DIR / "dental_2_4_1.json",
            skip_golden=True,
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
            manifest_version="canonical-v1",
            golden_path=_GOLDEN_DIR / "drug_combination_4_2.json",
            skip_golden=True,
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
    gate_b_section: str,
    manifest_name: str,
    corpus_name: str,
    merge_rules: bool = False,
    rule_json_name: str = "drug_indication_prose.json",
    rule_set_id: str | None = None,
) -> CompileTarget:
    return CompileTarget(
        name=name,
        rule_json=_RULES_DIR / rule_json_name,
        mode="stage",
        dedup="union_overwrite",
        rule_set_id=rule_set_id or name,
        title="",
        sut_anchors=[],
        stages=["write_gate_b_artifacts"],
        gate_b_section=gate_b_section,
        merge_rules=merge_rules,
        corpus_csv=_PROJECT_ROOT / f"data/gazette/prose_corpus/{corpus_name}",
        manifest_path=_MANIFEST_DIR / manifest_name,
    )


def _drug_gate_b_targets() -> list[CompileTarget]:
    """Gate B manifest stages for §4.2 drug-indication sections (Track C2: one writer path)."""
    return [
        _drug_gate_b_target("drug_indication_4201", gate_b_section="4201", manifest_name="L4.2_drug_indication_4201_manifest.json", corpus_name="L4.2_drug_indication_4201.csv"),
        _drug_gate_b_target("drug_indication_4206", gate_b_section="4206", manifest_name="L4.2_drug_indication_4206_manifest.json", corpus_name="L4.2_drug_indication_4206.csv"),
        _drug_gate_b_target("drug_indication_4209_4227", gate_b_section="4209_4227", manifest_name="L4.2_drug_indication_4209_4227_manifest.json", corpus_name="L4.2_drug_indication_4209_4227.csv"),
        _drug_gate_b_target("drug_indication_4210", gate_b_section="4210", manifest_name="L4.2_drug_indication_4210_manifest.json", corpus_name="L4.2_drug_indication_4210.csv"),
        _drug_gate_b_target("drug_indication_4213_4216", gate_b_section="4213_4216", manifest_name="L4.2_drug_indication_4213_4216_manifest.json", corpus_name="L4.2_drug_indication_4213_4216.csv"),
        _drug_gate_b_target("drug_indication_4214c", gate_b_section="4214c", manifest_name="L4.2_drug_indication_4.2.14.C_manifest.json", corpus_name="L4.2_drug_indication_4.2.14.C.csv"),
        _drug_gate_b_target("drug_indication_4215", gate_b_section="4215", manifest_name="L4.2_drug_indication_4215_manifest.json", corpus_name="L4.2_drug_indication_4215.csv"),
        _drug_gate_b_target("drug_indication_4217", gate_b_section="4217", manifest_name="L4.2_drug_indication_4217_manifest.json", corpus_name="L4.2_drug_indication_4217.csv"),
        _drug_gate_b_target("drug_indication_4218_4236", gate_b_section="4218_4236", manifest_name="L4.2_drug_indication_4218_4236_manifest.json", corpus_name="L4.2_drug_indication_4218_4236.csv"),
        _drug_gate_b_target("drug_indication_4219", gate_b_section="4219", manifest_name="L4.2_drug_indication_4219_manifest.json", corpus_name="L4.2_drug_indication_4219.csv"),
        _drug_gate_b_target("drug_indication_4224", gate_b_section="4224", manifest_name="L4.2_drug_indication_4224_manifest.json", corpus_name="L4.2_drug_indication_4224.csv"),
        _drug_gate_b_target("drug_indication_4234", gate_b_section="4234", manifest_name="L4.2_drug_indication_4234_manifest.json", corpus_name="L4.2_drug_indication_4234.csv"),
        _drug_gate_b_target("drug_indication_4235_4237", gate_b_section="4235_4237", manifest_name="L4.2_drug_indication_4235_4237_manifest.json", corpus_name="L4.2_drug_indication_4235_4237.csv"),
        _drug_gate_b_target("drug_indication_4238", gate_b_section="4238", manifest_name="L4.2_drug_indication_4238_manifest.json", corpus_name="L4.2_drug_indication_4238.csv"),
        # Documented exceptions: 4201_w4 (regex filter) + 4213_tier_b_remap (oral-switch merge).
        _drug_gate_b_target("drug_indication_4201_w4", gate_b_section="4201", manifest_name="L4.2_drug_indication_4201_manifest.json", corpus_name="L4.2_drug_indication_4201.csv"),
        _drug_gate_b_target("drug_indication_4227_tier_b", gate_b_section="4209_4227", manifest_name="L4.2_drug_indication_4209_4227_manifest.json", corpus_name="L4.2_drug_indication_4209_4227.csv"),
        _drug_gate_b_target("drug_indication_4213_tier_b_remap", gate_b_section="4213", manifest_name="L4.2_drug_indication_4213_4216_manifest.json", corpus_name="L4.2_drug_indication_4213.csv"),
        _drug_gate_b_target("drug_indication_4210_tier_b", gate_b_section="4210", manifest_name="L4.2_drug_indication_4210_manifest.json", corpus_name="L4.2_drug_indication_4210.csv"),
    ]


def _gate_b_stage_targets() -> list[CompileTarget]:
    """Manifest/corpus stages that do not merge Python batch rules."""
    wave_manifest_targets = [
        CompileTarget(
            name=f"csv_wave_clause_ids_{suffix}",
            rule_json=_RULES_DIR / "drug_indication_prose.json",
            mode="stage",
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
            dedup="first_wins",
            rule_set_id="treatment_pricing_2_4_wave2",
            title="",
            sut_anchors=[],
            stages=["treatment_pricing_wave2_manifest"],
            manifest_path=_MANIFEST_DIR / "L2.4_treatment_pricing_wave2_manifest.json",
            manifest_version="canonical-v1",
            manifest_filter_section="2.4.4",
            wave_scope_note=_TREATMENT_PRICING_WAVE2_SCOPE,
        ),
        *wave_manifest_targets,
        _drug_gate_b_target(
            "payment_method_gate_b",
            gate_b_section="payment_22",
            manifest_name="L2.2_payment_method_encoded_manifest.json",
            corpus_name="L2.2_payment_method_prose.csv",
            rule_json_name="payment_method_2_2.json",
            rule_set_id="payment_method_2_2",
        ),
        _drug_gate_b_target(
            "material_bundling_manifest",
            gate_b_section="material_31_32",
            manifest_name="L1.4_material_bundling_encoded_manifest.json",
            corpus_name="L1.4_material_bundling_prose.csv",
            rule_json_name="material_bundling_prose.json",
            rule_set_id="material_bundling_prose",
        ),
        _drug_gate_b_target(
            "copay_exemption_gate_b",
            gate_b_section="copay_18",
            manifest_name="L1.8_copay_exemption_encoded_manifest.json",
            corpus_name="L1.8_copay_exemption_prose.csv",
            rule_json_name="copay_general_1_8.json",
            rule_set_id="copay_general_1_8",
        ),
        CompileTarget(
            name="anti_vegf_manifest",
            rule_json=_RULES_DIR / "anti_vegf_prose.json",
            mode="stage",
            dedup="union_overwrite",
            rule_set_id="anti_vegf_prose",
            title="",
            sut_anchors=[],
            stages=["antivegf_manifest"],
            manifest_path=_MANIFEST_DIR / "L4.33_anti_vegf_4.2.33_manifest.json",
        ),
        CompileTarget(
            name="specialty_materials_manifest",
            rule_json=_RULES_DIR / "specialty_materials_prose.json",
            mode="stage",
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
    return fresh + tier_b_targets + drug_gate_b_main + stages


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


def _load_stage_rules(yaml_sources: list[Path] | None = None) -> list[dict]:
    if yaml_sources:
        return load_yaml_sources(yaml_sources)
    return []


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
    "manifest_version": "canonical-v1",
    "rule_set_id": "session_pricing_2_2_2_B",
    "section_id": "2.2.2.B",
    "session_fraction_status": "PARTIAL",
    "encoded_clause_ids": ["C000654", "C000655", "C000657", "C000658", "C000659", "C000660", "C000661"],
}


def _write_payment_session_manifest() -> None:
    from scripts.sut.prose.manifest_index import build_canonical_encoded_shell

    session_json = _RULES_DIR / "session_pricing_2_2_2_B.json"
    session_payload = json.loads(session_json.read_text(encoding="utf-8"))
    encoded = list(_PAYMENT_SESSION_MANIFEST_STUB.get("encoded_clause_ids") or [])
    manifest = build_canonical_encoded_shell(
        rule_set_id="session_pricing_2_2_2_B",
        encoded_clause_ids=encoded,
        section_id="2.2.2.B",
        rules_in_json=len(session_payload.get("rules") or []),
        extra_keys={"session_fraction_status": "PARTIAL"},
    )
    _write_json(_MANIFEST_DIR / "L2.2_session_pricing_2_2_2_B_encoded_manifest.json", manifest)


def _stage_write_gate_b_artifacts(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    """Drug / non-drug Gate B stage — section config → gate_b_generic.write_artifacts.

    Documented exceptions (Track C2):
    - ``drug_indication_4213_tier_b_remap``: merges oral-switch YAML rules into JSON first
    - ``drug_indication_4201_w4``: filters rules with §4.2.1 regex boundary before write
    """
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing gate-B manifest path")
    if not target.gate_b_section:
        raise ValueError(f"target {target.name} missing gate_b_section")

    from scripts.sut.prose.gate_b_sections import ALL_SECTIONS
    from scripts.sut.prose.gate_b_generic import write_artifacts

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    existing = list(payload.get("rules") or [])
    stage_rules = _load_stage_rules(target.yaml_sources)

    # Exception: §4.2.13 oral-switch remap merges stage YAML into the prose JSON.
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

    effective_date = _existing_effective_date(target.manifest_path) or date.today().isoformat()
    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
    section_key = str(target.gate_b_section)
    section = ALL_SECTIONS[section_key]
    write_kwargs: dict[str, Any] = {
        "clauses_path": clauses_path,
        "section": section,
        "manifest_path": target.manifest_path,
        "corpus_csv": target.corpus_csv,
        "effective_date": effective_date,
        "rules_path": target.rule_json,
        "write_corpus": False,
    }

    # Exception: §4.2.1 wave-4 uses regex boundary (not bare prefix) for rule filter.
    if target.name == "drug_indication_4201_w4":
        is_421_proper = ALL_SECTIONS["4201"].match.matches
        write_kwargs["batch_rules"] = [
            rule for rule in merged if is_421_proper(str(rule.get("sut_section") or ""))
        ]
        del write_kwargs["rules_path"]

    frame, manifest = write_artifacts(**write_kwargs)

    # Track F: payment still needs the session-pricing stub sibling manifest.
    if section_key == "payment_22":
        _write_payment_session_manifest()

    return {
        "rows": getattr(frame, "height", None),
        "encoded": manifest.get("encoded_clause_count") or len(manifest.get("encoded_clause_ids") or []),
    }


def _stage_csv_wave_clause_ids(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    from scripts.sut.prose.manifest_index import build_canonical_encoded_shell

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    merged = list(payload.get("rules") or [])
    wave_clause_ids = DRUG_INDICATION_WAVE_CLAUSE_IDS[target.rule_set_id]
    manifest = build_canonical_encoded_shell(
        rule_set_id=target.rule_set_id,
        encoded_clause_ids=wave_clause_ids,
        rules_in_json=len(merged),
    )
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing CSV-wave manifest path")
    _write_json(target.manifest_path, manifest)
    return {"added": 0, "encoded": len(wave_clause_ids)}


def _stage_antivegf_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _compile_antivegf_manifest(target)


def _stage_tier_b_remap(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _stage_write_gate_b_artifacts(target, ctx)


def _stage_specialty_materials_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    return _write_specialty_materials_manifest(target)


def _stage_treatment_pricing_wave2_manifest(target: CompileTarget, ctx: dict[str, Any]) -> dict:
    from scripts.sut.prose.manifest_index import build_canonical_encoded_shell

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    rules = payload.get("rules") or []
    filter_sec = target.manifest_filter_section or "2.4.4"
    encoded: set[str] = set()
    for rule in rules:
        srcs = rule.get("gate_b_sources") or []
        if not srcs:
            continue
        if not str(rule.get("sut_section", "")).startswith(filter_sec):
            continue
        encoded.update(_resolve_gate_b_ids(srcs))

    manifest = build_canonical_encoded_shell(
        rule_set_id=target.rule_set_id,
        encoded_clause_ids=encoded,
        section_id=filter_sec,
        rules_in_json=len(rules),
    )
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing manifest path")
    _write_json(target.manifest_path, manifest)
    return {"encoded": len(encoded), "rules": len(rules)}


def _compile_antivegf_manifest(target: CompileTarget) -> dict:
    import polars as pl
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        resolve_gate_b_ref_to_clause_ids,
    )
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    payload = json.loads(target.rule_json.read_text(encoding="utf-8"))
    merged = list(payload.get("rules") or [])
    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
    clauses = pl.read_parquet(clauses_path)
    section = clauses.filter(
        pl.col("section_id").str.starts_with("4.2.33") & pl.col("is_in_force")
    )
    rules_by_clause: dict[str, list[str]] = {}
    encoded_ids: set[str] = set()
    for rule in merged:
        rid = str(rule.get("rule_id") or "")
        for raw in rule.get("gate_b_sources") or []:
            if raw is None or not str(raw).strip():
                continue
            try:
                resolved = resolve_gate_b_ref_to_clause_ids(
                    str(raw),
                    clauses,
                    in_force_only=True,
                    encode_eligible_only=True,
                    allow_ambiguous=False,
                )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
            ):
                continue
            for cid in resolved:
                encoded_ids.add(cid)
                rules_by_clause.setdefault(cid, []).append(rid)

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
                "linked_rule_ids": sorted(set(rules_by_clause.get(clause_id, []))),
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
    encoded_in_force = sorted(encoded_ids & in_force_ids)
    coord_by_id = {
        str(row["clause_id"]): str(row.get("clause_coordinate") or "")
        for row in section.iter_rows(named=True)
    }
    manifest = {
        "manifest_version": "canonical-v1",
        "section_id": "4.2.33",
        "effective_date": effective_date,
        "rule_set_id": "anti_vegf_prose",
        "rules_in_json": len(merged),
        "section_clause_total": section.height,
        "encoded_clause_count": len(encoded_in_force),
        "encoded_clause_ids": encoded_in_force,
        "encoded_clause_coordinates": sorted(
            {
                coord_by_id[cid]
                for cid in encoded_in_force
                if coord_by_id.get(cid)
            }
        ),
        "tier_c_deferred_clause_ids": sorted(tier_c_deferred),
        "tier_c_deferred_count": len(tier_c_deferred),
        "emr_blocked_clause_ids": [],
        "non_actionable_clause_ids": [],
        "tier_a_pending_clause_ids": [],
        "tier_b_pending_clause_ids": [],
        "emr_blocked_count": 0,
        "non_actionable_count": 0,
        "tier_a_pending_count": 0,
        "tier_b_pending_count": 0,
        "clause_traces": traces,
    }
    if not target.manifest_path:
        raise ValueError(f"target {target.name} missing manifest path")
    _write_json(target.manifest_path, manifest)
    return {"added": 0, "covered": len(encoded_ids)}


def _write_specialty_materials_manifest(target: CompileTarget) -> dict:
    import polars as pl
    from scripts.sut.prose.clause_identity import (
        AmbiguousClauseCiteError,
        NonEncodeEligibleCiteError,
        UnknownClauseCiteError,
        resolve_gate_b_ref_to_clause_ids,
    )
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
    clauses_path = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
    clauses = pl.read_parquet(clauses_path) if clauses_path.is_file() else None
    sources: set[str] = set()
    for rule in rules:
        for raw in rule.get("gate_b_sources") or []:
            if raw is None or not str(raw).strip():
                continue
            text = str(raw).strip()
            if clauses is None:
                sources.add(text)
                continue
            try:
                sources.update(
                    resolve_gate_b_ref_to_clause_ids(
                        text,
                        clauses,
                        in_force_only=True,
                        encode_eligible_only=True,
                        allow_ambiguous=False,
                    )
                )
            except (
                AmbiguousClauseCiteError,
                NonEncodeEligibleCiteError,
                UnknownClauseCiteError,
            ):
                continue
    sorted_sources = sorted(sources)
    from scripts.sut.prose.manifest_index import build_canonical_encoded_shell

    manifest = build_canonical_encoded_shell(
        rule_set_id="specialty_materials_prose",
        encoded_clause_ids=sorted_sources,
        section_id="3.3",
        rules_in_json=len(rules),
        section_clause_total=len(sorted_sources),
        extra_keys={
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
        },
    )
    _write_json(_MANIFEST_DIR / "L4.4_specialty_prose_encoded_manifest.json", manifest)
    return {"added": 0, "patched": 0, "encoded": len(sorted_sources)}


_STAGES = {
    "write_gate_b_artifacts": _stage_write_gate_b_artifacts,
    "csv_wave_clause_ids": _stage_csv_wave_clause_ids,
    "antivegf_manifest": _stage_antivegf_manifest,
    "tier_b_remap": _stage_tier_b_remap,
    "treatment_pricing_wave2_manifest": _stage_treatment_pricing_wave2_manifest,
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
        manifest = _build_gap_manifest(rules, target.rule_set_id,
                                       manifest_version=target.manifest_version,
                                       extra_keys=extra or None)
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


def compile_target(target: CompileTarget) -> dict:
    """Compile a single target."""
    ctx: dict[str, Any] = {}
    if target.mode == "fresh":
        result = _compile_fresh(target)
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
    """Compile all registered targets."""
    targets = targets or all_targets()

    for t in targets:
        result = compile_target(t)
        print(f"  ✓ {t.name}: {result}")

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
    for t in targets:
        paths.update(p for p in [t.rule_json, t.manifest_path, t.golden_path] if p is not None)
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
        print(f"check ok: {len(after_paths)} rule/manifest artifacts byte-identical")
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
        print(f"  {t.name:40s} {mode:10s} → {t.rule_json.name}")


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
