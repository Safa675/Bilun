#!/usr/bin/env python3
"""Wave 2/3 — promote tier A/B pending clauses to encoded gate_b_sources."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
_SOURCES_DIR = _PROJECT_ROOT / "data/gazette/prose_rule_sources/drug_indication"
_RULES_JSON = _PROJECT_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
_PATCHES_MODULE = _PROJECT_ROOT / "scripts/sut/prose/drug_indication_wave23_patches.py"
_CLAUSES = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"

_WAVE2_PREFIXES = ("4.2.1", "4.2.6", "4.2.9", "4.2.10", "4.2.13", "4.2.15", "4.2.16", "4.2.27")
_WAVE3_PREFIXES = (
    "4.2.12",
    "4.2.17",
    "4.2.23",
    "4.2.24",
    "4.2.28",
    "4.2.30",
    "4.2.33",
    "4.2.34",
    "4.2.38",
    "4.2.42",
    "4.2.46",
    "4.2.49",
    "4.2.70",
)


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _section_match(rule_section: str, clause_section: str) -> bool:
    rule_section = str(rule_section or "")
    clause_section = str(clause_section or "")
    if not rule_section or not clause_section:
        return False
    return clause_section.startswith(rule_section) or rule_section.startswith(clause_section)


def _load_pending() -> list[dict[str, Any]]:
    clauses = pd.read_parquet(
        _CLAUSES, columns=["clause_id", "section_id", "text_tr", "deontic_modality"]
    )
    by_id = {str(r.clause_id): r for r in clauses.itertuples()}
    rows: list[dict[str, Any]] = []
    for path in sorted(_MANIFEST_DIR.glob("L4*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        for tier, key in [("A", "tier_a_pending_clause_ids"), ("B", "tier_b_pending_clause_ids")]:
            for cid in payload.get(key) or []:
                rec = by_id.get(str(cid))
                rows.append(
                    {
                        "clause_id": str(cid),
                        "tier": tier,
                        "manifest": path.name,
                        "section_id": str(rec.section_id) if rec is not None else "",
                        "text": str(rec.text_tr or "") if rec is not None else "",
                    }
                )
    return rows


def _load_rules() -> list[dict[str, Any]]:
    return list(json.loads(_RULES_JSON.read_text(encoding="utf-8")).get("rules") or [])


def _score_rule(rule: dict[str, Any], *, section_id: str, text: str) -> float:
    sut = str(rule.get("sut_section") or "")
    if not _section_match(sut, section_id):
        return -1.0
    norm_text = _normalize(text)
    score = 0.0
    for drug in rule.get("drug_names") or []:
        token = _normalize(str(drug))
        if token and token in norm_text:
            score += 5.0
    msg = _normalize(str(rule.get("message_tr") or rule.get("action", {}).get("message_tr", "")))
    if msg:
        overlap = sum(1 for w in msg.split() if len(w) > 4 and w in norm_text)
        score += overlap * 0.5
    if rule.get("report_required"):
        if "rapor" in norm_text or "sağlık kurulu" in norm_text:
            score += 2.0
    if rule.get("gate_b_sources"):
        score += 0.25
    return score


def propose_patches(
    pending: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    *,
    min_score: float = 2.0,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    patches: dict[str, list[str]] = defaultdict(list)
    unmatched: list[dict[str, Any]] = []
    for row in pending:
        scores = [
            (_score_rule(rule, section_id=row["section_id"], text=row["text"]), rule)
            for rule in rules
        ]
        scores = [(s, r) for s, r in scores if s >= min_score]
        if not scores:
            unmatched.append(row)
            continue
        best_score, best_rule = max(scores, key=lambda item: item[0])
        rule_id = str(best_rule["rule_id"])
        patches[rule_id].append(row["clause_id"])
    return {k: sorted(set(v)) for k, v in sorted(patches.items())}, unmatched


def _yaml_path_for_rule(rule_id: str) -> Path | None:
    section = rule_id.split(".", 2)
    if len(section) < 2:
        return None
    # 4.2.9.esa... -> 4.2.9.A-1.yaml via sut_section on rule — scan is expensive; glob by prefix
    prefix = ".".join(rule_id.split(".")[:3]) if rule_id.count(".") >= 2 else rule_id
    for path in _SOURCES_DIR.glob("*.yaml"):
        if path.stem.startswith(prefix.rsplit(".", 1)[0]):
            return path
    return None


def apply_patches_to_yaml(patches: dict[str, list[str]]) -> int:
    """Append gate_b_sources in YAML section files."""
    rules = _load_rules()
    by_id = {str(r["rule_id"]): r for r in rules}
    touched_files: dict[Path, dict[str, Any]] = {}
    applied = 0
    for rule_id, clause_ids in patches.items():
        rule = by_id.get(rule_id)
        if not rule:
            continue
        sut = str(rule.get("sut_section") or "")
        candidates = sorted(_SOURCES_DIR.glob("*.yaml"))
        yaml_path = None
        for path in candidates:
            if not path.stem.startswith(sut.split(".")[0]):
                continue
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            for entry in payload.get("rules") or []:
                if str(entry.get("rule_id")) == rule_id:
                    yaml_path = path
                    break
            if yaml_path:
                break
        if not yaml_path:
            continue
        if yaml_path not in touched_files:
            touched_files[yaml_path] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        payload = touched_files[yaml_path]
        for entry in payload.get("rules") or []:
            if str(entry.get("rule_id")) != rule_id:
                continue
            before = set(str(c) for c in (entry.get("gate_b_sources") or []))
            after = sorted(before | set(clause_ids))
            if after != sorted(before):
                entry["gate_b_sources"] = after
                applied += 1
    for path, payload in touched_files.items():
        path.write_text(
            yaml.dump(payload, allow_unicode=True, sort_keys=False, width=120),
            encoding="utf-8",
        )
    return applied


def write_patches_module(patches: dict[str, list[str]]) -> None:
    lines = [
        '"""Wave 2/3 gate_b_sources patches (clause-ID append only)."""',
        "",
        "from __future__ import annotations",
        "",
        "SOURCE_PATCHES: dict[str, list[str]] = {",
    ]
    for rule_id, clause_ids in sorted(patches.items()):
        ids = ", ".join(f'"{c}"' for c in clause_ids)
        lines.append(f'    "{rule_id}": [{ids}],')
    lines.append("}")
    lines.append("")
    _PATCHES_MODULE.write_text("\n".join(lines), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote tier A/B pending to gate_b_sources.")
    parser.add_argument("--wave", choices=["2", "3", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-score", type=float, default=2.0)
    parser.add_argument("--apply-yaml", action="store_true", help="Write patches into YAML sources.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    prefixes = _WAVE2_PREFIXES if args.wave == "2" else _WAVE3_PREFIXES if args.wave == "3" else _WAVE2_PREFIXES + _WAVE3_PREFIXES

    pending = _load_pending()
    pending = [r for r in pending if any(r["section_id"].startswith(p) for p in prefixes)]
    rules = _load_rules()
    patches, unmatched = propose_patches(pending, rules, min_score=args.min_score)

    stats = {
        "pending_in_scope": len(pending),
        "patch_rules": len(patches),
        "patch_clauses": sum(len(v) for v in patches.values()),
        "unmatched": len(unmatched),
    }
    print(json.dumps(stats, indent=2))
    if args.dry_run:
        for rule_id, ids in sorted(patches.items())[:20]:
            print(f"  {rule_id}: {ids}")
        if unmatched:
            print("unmatched sample:", [r["clause_id"] for r in unmatched[:15]])
        return 0

    write_patches_module(patches)
    if args.apply_yaml:
        applied = apply_patches_to_yaml(patches)
        print(f"yaml files updated for {applied} rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
