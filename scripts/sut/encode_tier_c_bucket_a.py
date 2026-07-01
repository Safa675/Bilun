#!/usr/bin/env python3
"""Encode Tier-C Bucket A clauses (prescriber / report / combo / max-cycle)."""

from __future__ import annotations

import argparse
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

from scripts.sut.close_algorithmic_gaps import _manifest_for_section  # noqa: E402
from scripts.sut.promote_tier_ab_pending import apply_patches_to_yaml  # noqa: E402
from scripts.sut.prose.tier_c_classify import (  # noqa: E402
    extract_drug_tokens,
    extract_icd_hints,
    extract_report_duration_months,
    extract_signals,
    normalize_tr,
)

_CANDIDATES_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_candidates.json"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_PATCHES_PY = _REPO / "scripts/sut/prose/drug_indication_bucket_a_patches.py"
_BATCH_YAML = _REPO / "data/gazette/prose_rule_sources/drug_indication/tier_c_bucket_a.yaml"
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_REPORT_JSON = _REPO / "reports/tier_c_bucket_a_encode_report.json"

_SPECIALTY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"tıbbi onkoloji", "tıbbi onkoloji"),
    (r"hematoloji", "hematoloji"),
    (r"çocuk hematolojisi ve onkolojisi", "çocuk hematolojisi ve onkolojisi"),
    (r"dermatoloji", "dermatoloji"),
    (r"endokrinoloji", "endokrinoloji"),
    (r"göğüs hastalıkları", "göğüs hastalıkları"),
    (r"romatoloji", "romatoloji"),
    (r"klinik immünoloji", "klinik immünoloji"),
    (r"kardiyoloji", "kardiyoloji"),
    (r"kalp damar cerrahi", "kalp ve damar cerrahisi"),
    (r"kadın hastalıkları", "kadın hastalıkları ve doğum"),
    (r"enfeksiyon hastalıkları", "enfeksiyon hastalıkları"),
    (r"çocuk endokrinolojisi", "çocuk endokrinolojisi"),
    (r"çocuk sağlığı", "çocuk sağlığı ve hastalıkları"),
    (r"nöroloji", "nöroloji"),
    (r"üroloji", "üroloji"),
    (r"gastroenteroloji", "gastroenteroloji"),
    (r"radyasyon onkolojisi", "radyasyon onkolojisi"),
)

_SECTION_DRUG_DEFAULTS: dict[str, list[str]] = {
    "4.2.1": ["biyolojik ajan", "anti-tnf"],
    "4.2.3": ["immünoterapi", "alerji aşısı"],
    "4.2.4": ["kök hücre transplantasyonu", "hematopoetik kök hücre"],
    "4.2.10": ["enzim replasman tedavisi", "replasman enzimi"],
    "4.2.12": ["immünglobulin", "ivig"],
    "4.2.15": ["antikoagülan", "pıhtı önleyici"],
    "4.2.17": ["endokrin tedavi"],
    "4.2.37": ["akromegali tedavisi", "somatostatin analog"],
    "4.2.41": ["parenteral demir", "demir preparatı"],
    "4.2.42": ["gonadotropin", "ivf tedavisi"],
    "4.2.46": ["nintedanib", "pirfenidon"],
    "4.2.66": ["gonadotropin", "fsh"],
    "4.2.70": ["monoklonal gammopati"],
}


def _section_matches(rule_section: str, clause_section: str) -> bool:
    rule_section = str(rule_section or "")
    clause_section = str(clause_section or "")
    if not rule_section or not clause_section:
        return False
    if rule_section == clause_section:
        return True
    return clause_section.startswith(rule_section + ".") or rule_section.startswith(clause_section + ".")


def _normalize(text: str) -> str:
    return normalize_tr(text)


def _score_rule(rule: dict[str, Any], *, section_id: str, text: str) -> float:
    if not _section_matches(str(rule.get("sut_section") or ""), section_id):
        return -1.0
    norm_text = _normalize(text)
    score = 0.0
    for drug in rule.get("drug_names") or []:
        token = _normalize(str(drug))
        if token and token in norm_text:
            score += 5.0
    msg = _normalize(str(rule.get("message_tr") or rule.get("action", {}).get("message_tr", "")))
    if msg:
        score += sum(0.5 for w in msg.split() if len(w) > 4 and w in norm_text)
    if rule.get("report_required") and ("rapor" in norm_text or "saglik kurulu" in norm_text):
        score += 2.0
    if rule.get("gate_b_sources"):
        score += 0.25
    return score


def _extract_specialties(text: str) -> list[str]:
    lower = _normalize(text)
    found: list[str] = []
    for pattern, label in _SPECIALTY_PATTERNS:
        if re.search(pattern, lower, re.I):
            found.append(label)
    if re.search(r"tum uzman hekim", lower):
        return found or ["uzman hekim"]
    return found


def _extract_max_applications(text: str) -> int | None:
    m = re.search(
        r"(?:maksimum|en\s*fazla|toplam).{0,30}?(\d+).{0,20}?(?:iu/kg|küre|kür|doz|uygulama)",
        str(text or ""),
        re.I,
    )
    return int(m.group(1)) if m else None


def _section_prefix(section_id: str) -> str:
    parts = str(section_id or "").split(".")
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return str(section_id or "")


def _default_drugs(section_id: str, text: str, known_inns: list[str]) -> list[str]:
    drugs = extract_drug_tokens(text, known_inns)
    drugs = [d for d in drugs if d and not d.startswith("__") and len(d) > 2]
    if drugs:
        return drugs[:6]
    for key in sorted(_SECTION_DRUG_DEFAULTS, key=len, reverse=True):
        if section_id == key or section_id.startswith(key + "."):
            return list(_SECTION_DRUG_DEFAULTS[key])
    return ["ilac endikasyonu"]


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
) -> dict[str, Any]:
    signals = extract_signals(text)
    drugs = _default_drugs(section_id, text, known_inns)
    specialties = _extract_specialties(text)
    duration = extract_report_duration_months(text)
    max_apps = _extract_max_applications(text)
    icd = extract_icd_hints(text)

    slug = clause_id.lower()
    rule_id = f"{section_id}.bucket_a.{slug}".replace(" ", "_")
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": section_id,
        "drug_names": drugs,
        "gate_b_sources": [clause_id],
        "report_required": bool(specialties or signals["has_prescriber_authority"]),
        "message_tr": " ".join(str(text or "").split())[:480],
        "encode_bucket": "A",
    }
    if specialties:
        rule["prescriber_specialties"] = specialties
        rule["report_specialties"] = specialties
    if duration:
        rule["report_duration_months"] = duration
    if max_apps:
        rule["max_applications_per_year"] = max_apps
    if signals["has_combo_prohibition"]:
        rule["combo_prohibition"] = True
    if icd:
        if any("-" in c for c in icd):
            rule["icd10_ranges"] = icd
        else:
            rule["icd10_codes"] = icd
    elif section_id.startswith("4.2.14"):
        rule["icd10_ranges"] = ["C00-C97"]
    return rule


def propose_bucket_a_encoding(
    *,
    candidates_path: Path = _CANDIDATES_JSON,
    clauses_path: Path = _CLAUSES,
    rules_path: Path = _RULES_JSON,
    min_patch_score: float = 2.5,
) -> tuple[dict[str, list[str]], list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    bucket_a = [r for r in payload.get("rules") or [] if r.get("encode_bucket") == "A"]

    rules = list(json.loads(rules_path.read_text(encoding="utf-8")).get("rules") or [])
    known_inns = _load_known_inns(rules)
    existing_sources: set[str] = set()
    for rule in rules:
        existing_sources.update(str(c) for c in (rule.get("gate_b_sources") or []))

    clause_rows = pl.read_parquet(clauses_path).filter(pl.col("is_in_force"))
    clauses_by_id = {str(r["clause_id"]): r for r in clause_rows.iter_rows(named=True)}

    patches: dict[str, list[str]] = defaultdict(list)
    new_rules: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []

    for candidate in bucket_a:
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

        scores = [
            (_score_rule(rule, section_id=section_id, text=text), rule)
            for rule in rules
        ]
        scores = [(s, r) for s, r in scores if s >= min_patch_score]
        if scores:
            best_score, best_rule = max(scores, key=lambda item: item[0])
            patches[str(best_rule["rule_id"])].append(clause_id)
            continue

        new_rules.append(
            _build_new_rule(
                clause_id=clause_id,
                section_id=section_id,
                text=text,
                known_inns=known_inns,
            )
        )

    stats = {
        "bucket_a_total": len(bucket_a),
        "patch_rules": len(patches),
        "patch_clauses": sum(len(v) for v in patches.values()),
        "new_rules": len(new_rules),
        "skipped": len(skipped),
        "generated_at": date.today().isoformat(),
    }
    return dict(patches), new_rules, {"stats": stats, "skipped": skipped, "unmatched": unmatched}


def write_patches_module(patches: dict[str, list[str]]) -> None:
    lines = [
        '"""Tier-C Bucket A gate_b_sources patches (clause-ID append only)."""',
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
        "section_id": "tier_c_bucket_a",
        "source_note": "Tier-C Bucket A encode batch — prescriber/report/combo/max-cycle (pre-EMR fields only)",
        "rules": new_rules,
    }
    _BATCH_YAML.write_text(
        yaml.dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _all_encoded_clause_ids(
    patches: dict[str, list[str]],
    new_rules: list[dict[str, Any]],
) -> set[str]:
    ids: set[str] = set()
    for clause_ids in patches.values():
        ids.update(str(c) for c in clause_ids)
    for rule in new_rules:
        ids.update(str(c) for c in (rule.get("gate_b_sources") or []))
    return ids


def promote_manifests(
    patches: dict[str, list[str]],
    new_rules: list[dict[str, Any]],
    *,
    clauses_path: Path = _CLAUSES,
) -> dict[str, int]:
    """Move encoded clause IDs from tier_c_deferred → encoded_clause_ids in manifests."""
    clause_to_rules: dict[str, list[str]] = defaultdict(list)
    for rule_id, clause_ids in patches.items():
        for cid in clause_ids:
            clause_to_rules[cid].append(rule_id)
    for rule in new_rules:
        for cid in rule.get("gate_b_sources") or []:
            clause_to_rules[str(cid)].append(str(rule["rule_id"]))

    all_ids = _all_encoded_clause_ids(patches, new_rules)

    clauses = pl.read_parquet(clauses_path).filter(pl.col("is_in_force"))
    section_by_id = {str(r["clause_id"]): str(r["section_id"]) for r in clauses.iter_rows(named=True)}

    by_manifest: dict[str, list[str]] = defaultdict(list)
    for clause_id in all_ids:
        section = section_by_id.get(clause_id, "")
        by_manifest[_manifest_for_section(section)].append(clause_id)

    stats = {"manifests_touched": 0, "clauses_promoted": 0}
    for manifest_name, clause_ids in sorted(by_manifest.items()):
        path = _MANIFEST_DIR / manifest_name
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        tier_c = {str(c) for c in (payload.get("tier_c_deferred_clause_ids") or [])}
        encoded = {str(c) for c in (payload.get("encoded_clause_ids") or [])}
        promoted = 0
        dirty = False
        traces = payload.get("clause_traces")
        trace_by_id: dict[str, dict[str, Any]] = {}
        if isinstance(traces, list):
            trace_by_id = {str(t.get("clause_id")): t for t in traces if isinstance(t, dict)}
        elif isinstance(traces, dict):
            trace_by_id = {str(k): v for k, v in traces.items() if isinstance(v, dict)}

        for clause_id in sorted(set(clause_ids)):
            if clause_id in tier_c:
                tier_c.discard(clause_id)
                dirty = True
            if clause_id in encoded:
                if clause_id in trace_by_id:
                    trace_by_id[clause_id]["manifest_status"] = "encoded"
                    trace_by_id[clause_id]["linked_rule_ids"] = sorted(
                        set(trace_by_id[clause_id].get("linked_rule_ids") or [])
                        | set(clause_to_rules.get(clause_id, []))
                    )
                    trace_by_id[clause_id].pop("defer_themes", None)
                    trace_by_id[clause_id].pop("defer_reason", None)
                    dirty = True
                continue
            encoded.add(clause_id)
            promoted += 1
            dirty = True
            if clause_id in trace_by_id:
                trace_by_id[clause_id]["manifest_status"] = "encoded"
                trace_by_id[clause_id]["linked_rule_ids"] = sorted(
                    set(trace_by_id[clause_id].get("linked_rule_ids") or [])
                    | set(clause_to_rules.get(clause_id, []))
                )
                trace_by_id[clause_id].pop("defer_themes", None)
                trace_by_id[clause_id].pop("defer_reason", None)

        if not dirty:
            continue
        payload["encoded_clause_ids"] = sorted(encoded)
        payload["encoded_clause_count"] = len(encoded)
        payload["tier_c_deferred_clause_ids"] = sorted(tier_c)
        payload["tier_c_deferred_count"] = len(tier_c)
        if isinstance(traces, list):
            payload["clause_traces"] = list(trace_by_id.values())
        elif isinstance(traces, dict):
            payload["clause_traces"] = trace_by_id
        payload["bucket_a_encode_note"] = (
            f"Tier-C Bucket A promoted {promoted} clause(s) on {date.today().isoformat()}"
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stats["manifests_touched"] += 1
        stats["clauses_promoted"] += promoted
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-score", type=float, default=2.5)
    args = parser.parse_args()

    patches, new_rules, report = propose_bucket_a_encoding(min_patch_score=args.min_score)
    report["patches"] = {k: sorted(set(v)) for k, v in sorted(patches.items())}
    report["new_rule_ids"] = [r["rule_id"] for r in new_rules]

    print(json.dumps(report["stats"], indent=2))
    if args.dry_run:
        print(f"would patch {report['stats']['patch_clauses']} clauses across {report['stats']['patch_rules']} rules")
        print(f"would add {report['stats']['new_rules']} new rules")
        return 0

    import importlib

    write_patches_module(patches)
    if new_rules:
        write_batch_yaml(new_rules)
    yaml_applied = apply_patches_to_yaml(patches)
    patch_mod = importlib.import_module("scripts.sut.prose.drug_indication_bucket_a_patches")
    committed_patches = dict(getattr(patch_mod, "SOURCE_PATCHES", {}) or {})
    batch_rules: list[dict[str, Any]] = []
    if _BATCH_YAML.is_file():
        batch_rules = list(yaml.safe_load(_BATCH_YAML.read_text(encoding="utf-8")).get("rules") or [])
    manifest_stats = promote_manifests(committed_patches, batch_rules)
    report["yaml_patches_applied"] = yaml_applied
    report["manifest_promotion"] = manifest_stats
    _REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"patches module → {_PATCHES_PY}")
    if new_rules:
        print(f"batch yaml → {_BATCH_YAML} ({len(new_rules)} rules)")
    print(f"yaml gate_b_sources updated: {yaml_applied} rules")
    print(f"manifest promotion: {manifest_stats}")
    print(f"report → {_REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
