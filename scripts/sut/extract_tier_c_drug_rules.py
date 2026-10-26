#!/usr/bin/env python3
"""Extract structured rule candidates from all tier-C deferred drug-indication clauses.

Pre-EMR inventory: classifies ~1,250 unencoded pathway clauses (A/B/C/D buckets),
mines drugs/ICD/signals, and writes CSV + JSON rule stubs for future compile waves.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT := str(_REPO)) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes  # noqa: E402
from scripts.sut.prose.tier_c_classify import (  # noqa: E402
    build_rule_candidate,
    classify_bucket,
    extract_drug_tokens,
)
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish  # noqa: E402

_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_SNAPSHOT = _REPO / "data/gazette/prose_rule_sources/drug_indication/gap_closure_tier_c.json"

_DEFAULT_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_extraction.csv"
_DEFAULT_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_candidates.json"
_DEFAULT_SUMMARY = _REPO / "reports/tier_c_drug_extraction_summary.json"


def _load_known_inns(rules_path: Path) -> list[str]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    inns: set[str] = set()
    for rule in payload.get("rules") or []:
        for name in rule.get("drug_names") or []:
            token = fold_turkish(name or "", TurkishFold.ACCENTLESS)
            if token and not token.startswith("__"):
                inns.add(token)
    return sorted(inns, key=len, reverse=True)


def _load_tier_c_index() -> dict[str, str]:
    """clause_id → manifest filename (first manifest wins)."""
    index: dict[str, str] = {}
    for path in sorted(_MANIFEST_DIR.glob("L4*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for cid in payload.get("tier_c_deferred_clause_ids") or []:
            index.setdefault(str(cid), path.name)
    if _SNAPSHOT.is_file():
        snap = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
        for _manifest_name, ids in (snap.get("manifests") or {}).items():
            for cid in ids or []:
                index.setdefault(str(cid), f"snapshot:{_manifest_name}")
    return index


def _iter_clause_traces(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("clause_traces")
    if not raw:
        return []
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    return [t for t in raw if isinstance(t, dict)]


def _load_manifest_defer_meta() -> dict[str, dict[str, Any]]:
    """clause_id → {defer_themes, defer_reason} from manifest traces where present."""
    meta: dict[str, dict[str, Any]] = {}
    for path in _MANIFEST_DIR.glob("L4*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for trace in _iter_clause_traces(payload):
            cid = str(trace.get("clause_id") or "")
            if not cid:
                continue
            if trace.get("manifest_status") == "tier_c_deferred":
                meta[cid] = {
                    "defer_themes": trace.get("defer_themes") or [],
                    "defer_reason": trace.get("defer_reason"),
                }
        for row in payload.get("tier_c_manifest") or []:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("clause_id") or "")
            if cid and cid not in meta:
                meta[cid] = {
                    "defer_themes": row.get("defer_themes") or [],
                    "defer_reason": row.get("defer_reason"),
                }
    return meta


def _target_clause_ids(
    coverage_path: Path,
    tier_c_index: dict[str, str],
    *,
    in_force_only: bool = True,
) -> set[str]:
    """Unencoded drug-indication clauses = tier-C extraction scope."""
    cov = pl.read_parquet(coverage_path)
    if in_force_only and "is_in_force" in cov.columns:
        cov = cov.filter(pl.col("is_in_force"))
    motor = cov.filter(
        (pl.col("primary_rule_id") == "drug_indication_prose")
        & ~pl.col("has_rule_encoding")
    )
    ids = {str(c) for c in motor["clause_id"].to_list()}
    # Union manifest tier-C (honesty: some may be flagged off-gap but still unencoded)
    ids |= set(tier_c_index)
    return ids


def extract_tier_c_rules(
    *,
    clauses_path: Path = _CLAUSES,
    coverage_path: Path = _COVERAGE,
    rules_path: Path = _RULES_JSON,
    in_force_only: bool = True,
) -> tuple[pl.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    tier_c_index = _load_tier_c_index()
    defer_meta = _load_manifest_defer_meta()
    target_ids = _target_clause_ids(coverage_path, tier_c_index, in_force_only=in_force_only)
    known_inns = _load_known_inns(rules_path)

    clauses = pl.read_parquet(clauses_path)
    if in_force_only:
        clauses = clauses.filter(pl.col("is_in_force"))

    cov = pl.read_parquet(coverage_path)
    if in_force_only:
        cov = cov.filter(pl.col("is_in_force"))
    cov_di = cov.filter(pl.col("primary_rule_id") == "drug_indication_prose").select(
        "clause_id", "deontic_modality", "has_rule_encoding", "has_algorithmic_gap"
    )

    frame = (
        clauses.filter(pl.col("clause_id").is_in(list(target_ids)))
        .join(cov_di, on="clause_id", how="left")
        .sort("paragraph_index")
    )

    inventory_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for record in frame.iter_rows(named=True):
        cid = str(record["clause_id"])
        text = str(record.get("in_force_text") or record.get("text_tr") or "")
        section_id = str(record.get("section_id") or "")
        bucket = classify_bucket(record)
        deontic = record.get("deontic_modality")
        manifest_name = tier_c_index.get(cid, "unmapped")
        meta = defer_meta.get(cid, {})
        drugs = extract_drug_tokens(text, known_inns)
        themes = meta.get("defer_themes") or infer_defer_themes(text)

        inventory_rows.append(
            {
                "clause_id": cid,
                "section_id": section_id,
                "bucket": bucket,
                "deontic_modality": str(deontic) if deontic is not None else "",
                "manifest_source": manifest_name,
                "defer_themes": ",".join(themes),
                "drug_tokens": "|".join(drugs[:6]),
                "char_count": int(record.get("char_count") or len(text)),
                "has_rule_encoding": bool(record.get("has_rule_encoding") or False),
                "text_excerpt": " ".join(text.split())[:320],
            }
        )

        if bucket != "D":
            candidate = build_rule_candidate(
                clause_id=cid,
                section_id=section_id,
                text=text,
                bucket=bucket,
                deontic_modality=str(deontic) if deontic else None,
                known_inns=known_inns,
                manifest_name=manifest_name,
            )
            if meta.get("defer_reason"):
                candidate["manifest_defer_reason"] = meta["defer_reason"]
            candidates.append(candidate)
        elif int(record.get("char_count") or len(text)) >= 100:
            # Substantive pathway prose (headings/amendments filtered by classify_bucket)
            candidate = build_rule_candidate(
                clause_id=cid,
                section_id=section_id,
                text=text,
                bucket="D",
                deontic_modality=str(deontic) if deontic else None,
                known_inns=known_inns,
                manifest_name=manifest_name,
            )
            candidate["pathway_fragment"] = True
            if meta.get("defer_reason"):
                candidate["manifest_defer_reason"] = meta["defer_reason"]
            candidates.append(candidate)

    inv = pl.DataFrame(inventory_rows)
    bucket_counts = Counter(r["bucket"] for r in inventory_rows)

    summary: dict[str, Any] = {
        "generated_at": date.today().isoformat(),
        "target_clause_count": len(target_ids),
        "inventory_rows": len(inventory_rows),
        "rule_candidates": len(candidates),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "candidates_by_bucket": dict(
            sorted(Counter(c["encode_bucket"] for c in candidates).items())
        ),
        "pathway_fragment_candidates": sum(1 for c in candidates if c.get("pathway_fragment")),
        "manifest_tier_c_index_size": len(tier_c_index),
        "top_section_prefixes": dict(
            sorted(
                Counter(
                    ".".join(str(r["section_id"]).split(".")[:3]) for r in inventory_rows
                ).items(),
                key=lambda x: -x[1],
            )[:20]
        ),
        "note": (
            "Pre-EMR extraction only. Bucket A=encodable with current claim fields; "
            "B=biomarker/prior-therapy (model ext); C=EMR-blocked; D=non-actionable "
            "(excluded from rule_candidates JSON)."
        ),
    }
    return inv, candidates, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_CLAUSES)
    parser.add_argument("--coverage", type=Path, default=_COVERAGE)
    parser.add_argument("--rules", type=Path, default=_RULES_JSON)
    parser.add_argument("--out-csv", type=Path, default=_DEFAULT_CSV)
    parser.add_argument("--out-json", type=Path, default=_DEFAULT_JSON)
    parser.add_argument("--out-summary", type=Path, default=_DEFAULT_SUMMARY)
    parser.add_argument("--include-superseded", action="store_true")
    args = parser.parse_args()

    inv, candidates, summary = extract_tier_c_rules(
        clauses_path=args.clauses,
        coverage_path=args.coverage,
        rules_path=args.rules,
        in_force_only=not args.include_superseded,
    )

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    inv.write_csv(args.out_csv)

    payload = {
        "rule_set_id": "drug_indication_tier_c_extracted",
        "title": "Tier-C drug indication rule candidates (pre-EMR extraction)",
        "effective_date": date.today().isoformat(),
        "runtime_status": "extracted_pre_emr",
        "rules": candidates,
    }
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Inventory: {inv.height} rows → {args.out_csv}")
    print(f"Candidates: {len(candidates)} rules → {args.out_json}")
    print(f"Summary → {args.out_summary}")
    print(f"Buckets: {summary['bucket_counts']}")


if __name__ == "__main__":
    main()
