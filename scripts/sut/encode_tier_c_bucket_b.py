#!/usr/bin/env python3
"""Encode Tier-C Bucket B clauses (biomarker + prior-therapy gating)."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import yaml

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sut.promote_tier_ab_pending import apply_patches_to_yaml  # noqa: E402
from scripts.sut.prose.compile_bucket_b_rules import (  # noqa: E402
    _extract_biomarkers,
    _extract_drugs,
    _extract_prior_therapy,
)
from scripts.sut.prose.tier_c_classify import (  # noqa: E402
    extract_drug_tokens,
    extract_icd_hints,
    extract_signals,
    normalize_tr,
)
from scripts.sut.tier_c_manifest_ops import update_manifest_bucket  # noqa: E402

_CANDIDATES_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_candidates.json"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_PATCHES_PY = _REPO / "scripts/sut/prose/drug_indication_bucket_b_patches.py"
_BATCH_YAML = _REPO / "data/gazette/prose_rule_sources/drug_indication/tier_c_bucket_b.yaml"
_REPORT_JSON = _REPO / "reports/tier_c_bucket_b_encode_report.json"

_SECTION_DRUG_DEFAULTS: dict[str, list[str]] = {
    "4.2.1": ["biyolojik ajan", "anti-tnf"],
    "4.2.5": ["ilaç endikasyonu"],
    "4.2.13": ["hepatit c tedavisi", "antiviral"],
    "4.2.14": ["onkoloji ilacı"],
    "4.2.23": ["antifungal", "antimikotik"],
    "4.2.27": ["eltrombopag", "romiplostim"],
    "4.2.47": ["ilaç endikasyonu"],
}


def _section_matches(rule_section: str, clause_section: str) -> bool:
    rule_section = str(rule_section or "")
    clause_section = str(clause_section or "")
    if not rule_section or not clause_section:
        return False
    if rule_section == clause_section:
        return True
    return clause_section.startswith(rule_section + ".") or rule_section.startswith(clause_section + ".")


def _score_rule(rule: dict[str, Any], *, section_id: str, text: str, signals: dict[str, Any]) -> float:
    if not _section_matches(str(rule.get("sut_section") or ""), section_id):
        return -1.0
    norm_text = normalize_tr(text)
    score = 0.0
    for drug in rule.get("drug_names") or []:
        token = normalize_tr(str(drug))
        if token and token in norm_text:
            score += 5.0
    msg = normalize_tr(str(rule.get("message_tr") or rule.get("action", {}).get("message_tr", "")))
    if msg:
        score += sum(0.5 for w in msg.split() if len(w) > 4 and w in norm_text)
    if rule.get("encode_bucket") == "A":
        score -= 8.0
    if rule.get("required_biomarkers") and signals.get("has_biomarker_signal"):
        score += 4.0
    if rule.get("requires_prior_therapy") and signals.get("has_prior_therapy_signal"):
        score += 4.0
    if rule.get("report_required") and "rapor" in norm_text:
        score += 1.5
    if rule.get("gate_b_sources"):
        score += 0.25
    return score


def _default_drugs(section_id: str, text: str, known_inns: list[str]) -> list[str]:
    drugs = _extract_drugs(text)
    if not drugs:
        drugs = extract_drug_tokens(text, known_inns)
    drugs = [d for d in drugs if d and not d.startswith("__") and len(d) > 2]
    if drugs:
        return drugs[:6]
    for key in sorted(_SECTION_DRUG_DEFAULTS, key=len, reverse=True):
        if section_id == key or section_id.startswith(key + "."):
            return list(_SECTION_DRUG_DEFAULTS[key])
    return ["ilaç endikasyonu"]


def _load_known_inns(rules: list[dict[str, Any]]) -> list[str]:
    inns: set[str] = set()
    for rule in rules:
        for name in rule.get("drug_names") or []:
            token = normalize_tr(name)
            if token and not token.startswith("__"):
                inns.add(token)
    return sorted(inns, key=len, reverse=True)


def _build_new_rule(
    *,
    clause_id: str,
    section_id: str,
    text: str,
    known_inns: list[str],
) -> dict[str, Any] | None:
    biomarkers = _extract_biomarkers(text)
    prior = _extract_prior_therapy(text)
    if not biomarkers and not prior:
        return None
    drugs = _default_drugs(section_id, text, known_inns)
    icd = extract_icd_hints(text)
    rule_id = f"{section_id}.bucket_b.{clause_id}".replace(" ", "_")
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": section_id,
        "drug_names": drugs,
        "gate_b_sources": [clause_id],
        "report_required": True,
        "message_tr": " ".join(str(text or "").split())[:480],
        "encode_bucket": "B",
    }
    if biomarkers:
        rule["required_biomarkers"] = biomarkers
    if prior:
        rule["requires_prior_therapy"] = prior
    if section_id.startswith("4.2.14"):
        rule["report_specialties"] = ["tıbbi onkoloji"]
        rule["prescriber_specialties"] = ["tıbbi onkoloji"]
        rule["icd10_ranges"] = ["C00-C97"]
    elif icd:
        if any("-" in c for c in icd):
            rule["icd10_ranges"] = icd
        else:
            rule["icd10_codes"] = icd
    return rule


def propose_bucket_b_encoding(
    *,
    candidates_path: Path = _CANDIDATES_JSON,
    clauses_path: Path = _CLAUSES,
    rules_path: Path = _RULES_JSON,
    min_patch_score: float = 2.5,
) -> tuple[dict[str, list[str]], list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    bucket_b = [r for r in payload.get("rules") or [] if r.get("encode_bucket") == "B"]

    rules = list(json.loads(rules_path.read_text(encoding="utf-8")).get("rules") or [])
    known_inns = _load_known_inns(rules)
    existing_sources: set[str] = set()
    for rule in rules:
        existing_sources.update(str(c) for c in (rule.get("gate_b_sources") or []))

    clauses_by_id = {
        str(r["clause_id"]): r
        for r in pl.read_parquet(clauses_path).filter(pl.col("is_in_force")).iter_rows(named=True)
    }

    patches: dict[str, list[str]] = defaultdict(list)
    new_rules: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    no_extract: list[str] = []

    for candidate in bucket_b:
        clause_id = str(candidate["clause_id"])
        if clause_id in existing_sources:
            skipped.append({"clause_id": clause_id, "reason": "already_encoded"})
            continue
        row = clauses_by_id.get(clause_id)
        if not row:
            skipped.append({"clause_id": clause_id, "reason": "clause_missing"})
            continue
        text = str(row.get("in_force_text") or row.get("text_tr") or "")
        section_id = str(row.get("section_id") or candidate.get("sut_section") or "")
        signals = extract_signals(text)

        scores = [
            (_score_rule(rule, section_id=section_id, text=text, signals=signals), rule)
            for rule in rules
        ]
        scores = [(s, r) for s, r in scores if s >= min_patch_score]
        if scores:
            _, best_rule = max(scores, key=lambda item: item[0])
            patches[str(best_rule["rule_id"])].append(clause_id)
            continue

        built = _build_new_rule(
            clause_id=clause_id, section_id=section_id, text=text, known_inns=known_inns
        )
        if built:
            new_rules.append(built)
        else:
            no_extract.append(clause_id)

    stats = {
        "bucket_b_total": len(bucket_b),
        "patch_rules": len(patches),
        "patch_clauses": sum(len(v) for v in patches.values()),
        "new_rules": len(new_rules),
        "skipped": len(skipped),
        "no_extract": len(no_extract),
        "generated_at": date.today().isoformat(),
    }
    return (
        dict(patches),
        new_rules,
        {"stats": stats, "skipped": skipped, "no_extract": no_extract},
    )


def write_patches_module(patches: dict[str, list[str]]) -> None:
    lines = [
        '"""Tier-C Bucket B gate_b_sources patches (clause-ID append only)."""',
        "",
        "from __future__ import annotations",
        "",
        "SOURCE_PATCHES: dict[str, list[str]] = {",
    ]
    for rule_id, clause_ids in sorted(patches.items()):
        ids = ", ".join(f'"{c}"' for c in sorted(set(clause_ids)))
        lines.append(f'    "{rule_id}": [{ids}],')
    lines.append("}")
    lines.append("")
    _PATCHES_PY.write_text("\n".join(lines), encoding="utf-8")


def write_batch_yaml(new_rules: list[dict[str, Any]]) -> None:
    payload = {
        "section_id": "tier_c_bucket_b",
        "source_note": "Tier-C Bucket B — biomarker / prior-therapy gating (DrugClaimLine fields)",
        "rules": new_rules,
    }
    _BATCH_YAML.write_text(
        yaml.dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _clause_to_rules(
    patches: dict[str, list[str]], new_rules: list[dict[str, Any]]
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for rule_id, clause_ids in patches.items():
        for cid in clause_ids:
            out[cid].append(rule_id)
    for rule in new_rules:
        for cid in rule.get("gate_b_sources") or []:
            out[str(cid)].append(str(rule["rule_id"]))
    return dict(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-score", type=float, default=2.5)
    args = parser.parse_args()

    patches, new_rules, report = propose_bucket_b_encoding(min_patch_score=args.min_score)
    report["patches"] = {k: sorted(set(v)) for k, v in sorted(patches.items())}
    report["new_rule_ids"] = [r["rule_id"] for r in new_rules]
    print(json.dumps(report["stats"], indent=2))
    if args.dry_run:
        if report.get("no_extract"):
            print("no_extract sample:", report["no_extract"][:10])
        return 0

    write_patches_module(patches)
    if new_rules:
        write_batch_yaml(new_rules)
    yaml_applied = apply_patches_to_yaml(patches)
    patch_mod = importlib.import_module("scripts.sut.prose.drug_indication_bucket_b_patches")
    committed = dict(getattr(patch_mod, "SOURCE_PATCHES", {}) or {})
    batch_rules: list[dict[str, Any]] = []
    if _BATCH_YAML.is_file():
        batch_rules = list(yaml.safe_load(_BATCH_YAML.read_text(encoding="utf-8")).get("rules") or [])
    manifest_stats = update_manifest_bucket(
        set(_clause_to_rules(committed, batch_rules)),
        status="encoded",
        clause_to_rules=_clause_to_rules(committed, batch_rules),
        note_prefix="bucket_b_encode",
    )
    report["yaml_patches_applied"] = yaml_applied
    report["manifest_promotion"] = manifest_stats
    _REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patches → {_PATCHES_PY}, yaml → {_BATCH_YAML}, report → {_REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
