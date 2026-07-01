#!/usr/bin/env python3
"""Encode unencoded deontic §4.2.14.C clauses — patch existing rules + new YAML batch."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import polars as pl
import yaml

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_PATCHES_PY = _REPO / "scripts/sut/prose/drug_indication_4214c_patches.py"
_BATCH_YAML = _REPO / "data/gazette/prose_rule_sources/drug_indication/4.2.14.C.yaml"
_REPORT_JSON = _REPO / "reports/deontic_4214c_encode_report.json"

_SECTION = "4.2.14.C"
_MATCH_THRESHOLD = 5.0
_MSG_MAX = 480

# Extra INN tokens common in §4.2.14.C prose but sometimes missing from rule drug_names.
_EXTRA_INNS = (
    "rituksimab",
    "rituximab",
    "obinutuzumab",
    "ofatumumab",
    "bendamustin",
    "bendamustine",
    "fludarabin",
    "fludarabine",
    "kladribin",
    "cladribine",
    "dosetaksel",
    "docetaxel",
    "abirateron",
    "abiraterone",
    "enzalutamid",
    "enzalutamide",
    "apalutamid",
    "apalutamide",
    "olaparib",
    "niraparib",
    "rucaparib",
    "talazoparib",
    "venetoklaks",
    "venetoclax",
    "ibrutinib",
    "akalabrutinib",
    "acalabrutinib",
    "zanubrutinib",
    "idelalisib",
    "duvelisib",
    "copanlisib",
    "alpelisib",
    "everolimus",
    "temsirolimus",
    "sunitinib",
    "sorafenib",
    "pazopanib",
    "lenvatinib",
    "cabozantinib",
    "regorafenib",
    "axitinib",
    "tivozanib",
    "pembrolizumab",
    "nivolumab",
    "atezolizumab",
    "durvalumab",
    "avelumab",
    "ipilimumab",
    "trastuzumab",
    "pertuzumab",
    "lapatinib",
    "neratinib",
    "tucatinib",
    "fam-trastuzumab",
    "ado-trastuzumab",
    "trastuzumab emtansine",
    "trastuzumab deruktecan",
    "inotuzumab",
    "gemtuzumab",
    "brentuksimab",
    "brentuximab",
    "polatuzumab",
    "mogamulizumab",
    "moxetumomab",
    "tagraxofusp",
    "blinatumomab",
    "inotuzumab ozogamicin",
)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _norm_tokens(text: str) -> str:
    t = _normalize(text)
    t = re.sub(r"[^\w\s+]", " ", t)
    return " ".join(t.split())


def _load_known_inns(rules: list[dict[str, Any]]) -> list[str]:
    inns: set[str] = set(_EXTRA_INNS)
    for rule in rules:
        if not str(rule.get("sut_section") or "").startswith("4.2"):
            continue
        for name in rule.get("drug_names") or []:
            token = _normalize(name).strip()
            if token:
                inns.add(token)
    return sorted(inns, key=len, reverse=True)


def _extract_drugs(text: str, known_inns: list[str]) -> list[str]:
    norm_text = _norm_tokens(text)
    found: list[str] = []
    for inn in known_inns:
        if inn in norm_text:
            found.append(inn)
    if found:
        return found[:6]

    # Leading INN before semicolon (Gate B heuristic).
    t = str(text or "").strip()
    m = re.match(r"^[\(\[]?(?:\d+|[a-zçğıöşü])[\)\].]\s*", t, re.I)
    rest = t[m.end() :].strip() if m else t
    seg = rest.split(";")[0].split(",")[0].strip()
    if 2 < len(seg) < 60 and not seg.lower().startswith("bu "):
        return [_normalize(seg)]
    return ["onkoloji_ilac"]


def _extract_icd(text: str) -> list[str]:
    codes = re.findall(r"\bC\d{2}(?:\.\d+)?\b", str(text or ""), re.I)
    uniq = sorted({c.upper().split(".")[0] for c in codes})
    if uniq:
        return uniq
    if re.search(r"prostat|psa|mhpk|mhspk", text, re.I):
        return ["C61"]
    if re.search(r"meme|mamografi|breast", text, re.I):
        return ["C50"]
    if re.search(r"lenfoma|lymphoma", text, re.I):
        return ["C81", "C82", "C83", "C84", "C85", "C86", "C88"]
    if re.search(r"myelodisplastik|mds|anemi", text, re.I):
        return ["D46"]
    return ["C00-C97"]


def _score_rule(rule: dict[str, Any], text: str) -> float:
    nt = _norm_tokens(text)
    score = 0.0
    for drug in rule.get("drug_names") or []:
        token = _norm_tokens(str(drug))
        if token and token in nt:
            score += 5.0
    msg = _norm_tokens(str(rule.get("message_tr") or rule.get("action", {}).get("message_tr", "")))
    if msg:
        overlap = sum(1 for w in msg.split() if len(w) > 5 and w in nt)
        score += min(overlap * 0.4, 4.0)
    return score


def _message_tr(text: str, modality: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) > _MSG_MAX:
        cleaned = cleaned[: _MSG_MAX - 1].rstrip() + "…"
    prefix = {
        "COVERAGE": "Endikasyon",
        "NO_PAY": "Ödeme koşulu",
        "PROHIBITED": "Birlikte kullanım yasağı",
        "PERMISSION": "Kullanım koşulu",
        "MANDATORY": "Zorunlu koşul",
    }.get(modality, "§4.2.14.C koşulu")
    return f"{prefix}: {cleaned} (§4.2.14.C deontic encode)."


def _build_rule(
    *,
    clause_id: str,
    text: str,
    modality: str,
    coordinate: str,
    known_inns: list[str],
) -> dict[str, Any]:
    drugs = _extract_drugs(text, known_inns)
    icd = _extract_icd(text)
    slug = coordinate.replace(".", "_").replace("(", "").replace(")", "") or clause_id
    rule_id = f"4.2.14.C.deontic.{clause_id}"
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": _SECTION,
        "drug_names": drugs,
        "message_tr": _message_tr(text, modality),
        "gate_b_sources": [clause_id],
    }
    if any("-" in c for c in icd):
        rule["icd10_ranges"] = icd
    else:
        rule["icd10_codes"] = icd
    if modality in {"NO_PAY", "PROHIBITED"}:
        rule["pay"] = False
        rule["action"] = {
            "enforcement": f"deontic_{modality.lower()}",
            "message_tr": rule["message_tr"],
        }
    else:
        rule["report_required"] = True
        rule["report_specialties"] = ["tıbbi onkoloji", "hematoloji"]
    return rule


def _load_targets() -> pl.DataFrame:
    cov = pl.read_parquet(_COVERAGE).filter(pl.col("is_in_force"))
    cl = pl.read_parquet(_CLAUSES)
    targets = cov.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & pl.col("deontic_modality").is_not_null()
        & ~pl.col("has_rule_encoding")
    )
    return targets.join(
        cl.select("clause_id", "text_tr", "deontic_modality", "clause_coordinate", "in_force_text"),
        on="clause_id",
    ).sort("clause_id")


def _render_patches_py(patches: dict[str, list[str]], existing: dict[str, list[str]]) -> str:
    merged: dict[str, list[str]] = {k: list(v) for k, v in existing.items()}
    for rule_id, clause_ids in patches.items():
        merged.setdefault(rule_id, [])
        for cid in clause_ids:
            if cid not in merged[rule_id]:
                merged[rule_id].append(cid)
    for rule_id in merged:
        merged[rule_id] = sorted(merged[rule_id])

    lines = [
        '"""§4.2.14.C Phase 5 manifest source patches (clause-ID append only)."""',
        "",
        "from __future__ import annotations",
        "",
        "# Existing rules: append manifest clause IDs only (merge unions gate_b_sources).",
        "SOURCE_PATCHES: dict[str, list[str]] = {",
    ]
    for rule_id in sorted(merged):
        ids = merged[rule_id]
        lines.append(f'    "{rule_id}": {json.dumps(ids, ensure_ascii=False)},')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _sync_patches_to_yaml(patches: dict[str, list[str]]) -> int:
    """Append SOURCE_PATCHES clause IDs into YAML gate_b_sources for parity."""
    touched = 0
    yaml_paths = sorted((_REPO / "data/gazette/prose_rule_sources/drug_indication").glob("*.yaml"))
    docs: list[tuple[Path, dict[str, Any]]] = []
    for path in yaml_paths:
        docs.append((path, yaml.safe_load(path.read_text(encoding="utf-8")) or {}))

    by_rule: dict[str, dict[str, Any]] = {}
    by_path: dict[str, Path] = {}
    for path, doc in docs:
        for rule in doc.get("rules") or []:
            rid = str(rule.get("rule_id") or "")
            if rid:
                by_rule[rid] = rule
                by_path[rid] = path

    for rule_id, clause_ids in patches.items():
        rule = by_rule.get(rule_id)
        if not rule:
            continue
        sources = [str(c) for c in (rule.get("gate_b_sources") or [])]
        before = set(sources)
        sources.extend(str(c) for c in clause_ids if str(c) not in before)
        if set(sources) == before:
            continue
        rule["gate_b_sources"] = sorted(set(sources))
        touched += 1

    if touched:
        dirty_paths = {by_path[rid] for rid in patches if rid in by_path}
        for path, doc in docs:
            if path in dirty_paths:
                path.write_text(
                    yaml.dump(doc, allow_unicode=True, sort_keys=False, width=120),
                    encoding="utf-8",
                )
    return touched


def run_encode(*, dry_run: bool = False) -> dict[str, Any]:
    rules = json.loads(_RULES_JSON.read_text(encoding="utf-8")).get("rules") or []
    sec_rules = [r for r in rules if str(r.get("sut_section") or "").startswith("4.2.14")]
    known_inns = _load_known_inns(rules)
    targets = _load_targets()
    if targets.is_empty():
        return {"target_count": 0, "patched": 0, "new_rules": 0}

    patches: dict[str, list[str]] = defaultdict(list)
    new_rules: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []

    for row in targets.iter_rows(named=True):
        cid = str(row["clause_id"])
        text = str(row.get("in_force_text") or row.get("text_tr") or "")
        modality = str(row.get("deontic_modality") or "")
        coordinate = str(row.get("clause_coordinate") or "")
        scored = sorted(
            ((_score_rule(r, text), str(r["rule_id"])) for r in sec_rules),
            reverse=True,
        )
        best_score, best_rule = scored[0]
        if best_score >= _MATCH_THRESHOLD:
            patches[best_rule].append(cid)
            assignments.append({"clause_id": cid, "mode": "patch", "rule_id": best_rule, "score": best_score})
        else:
            rule = _build_rule(
                clause_id=cid,
                text=text,
                modality=modality,
                coordinate=coordinate,
                known_inns=known_inns,
            )
            new_rules.append(rule)
            assignments.append({"clause_id": cid, "mode": "new_rule", "rule_id": rule["rule_id"]})

    existing_patches: dict[str, list[str]] = {}
    if _PATCHES_PY.is_file():
        ns: dict[str, Any] = {}
        exec(_PATCHES_PY.read_text(encoding="utf-8"), ns)  # noqa: S102
        existing_patches = dict(ns.get("SOURCE_PATCHES") or {})

    report = {
        "target_count": int(targets.height),
        "patched_clauses": sum(len(v) for v in patches.values()),
        "patch_rule_count": len(patches),
        "new_rule_count": len(new_rules),
        "assignments": assignments,
    }

    if dry_run:
        return report

    _PATCHES_PY.write_text(_render_patches_py(dict(patches), existing_patches), encoding="utf-8")
    _sync_patches_to_yaml({**existing_patches, **{k: v for k, v in patches.items()}})

    existing_doc = yaml.safe_load(_BATCH_YAML.read_text(encoding="utf-8"))
    existing_rules = list(existing_doc.get("rules") or [])
    existing_ids = {str(r["rule_id"]) for r in existing_rules}
    for rule in new_rules:
        if rule["rule_id"] not in existing_ids:
            existing_rules.append(rule)
            existing_ids.add(rule["rule_id"])
    existing_doc["rules"] = sorted(existing_rules, key=lambda r: str(r["rule_id"]))
    _BATCH_YAML.write_text(
        yaml.dump(existing_doc, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    _REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = run_encode(dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in report.items() if k != "assignments"}, indent=2))


if __name__ == "__main__":
    main()
