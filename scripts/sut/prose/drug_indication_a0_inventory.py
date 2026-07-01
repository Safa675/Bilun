"""Phase A0 — §4.2 drug indication gap refresh + manifest vs coverage inventory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sut.prose.drug_indication_gate_b import (  # noqa: E402
    _encode_tier,
    _heuristic_inn,
    export_4_2_14_c_candidates,
    gate_b_summary,
    write_gate_b_export,
)

_DEFAULT_CLAUSES = _REPO / "data/gazette/sut_clauses.parquet"
_DEFAULT_COVERAGE = _REPO / "data/gazette/sut_clause_coverage.parquet"
_DEFAULT_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_DEFAULT_RULES = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_DEFAULT_GATE_B_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv"
_DEFAULT_MANIFEST = _DEFAULT_MANIFEST_DIR / "L4.2_drug_indication_4.2.14.C_manifest.json"
_DEFAULT_GAP_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_gap_refresh.csv"
_DEFAULT_SUMMARY = _REPO / "data/gazette/prose_corpus/L4.2_drug_indication_a0_summary.json"

_MOTOR = "drug_indication_prose"
_EXCERPT_LEN = 240
_SECTION_PREFIXES = ("4.2.14.C", "4.2.13", "4.2.16", "4.2.33")


def _text_excerpt(text: str, *, max_len: int = _EXCERPT_LEN) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _infer_encode_tier(text: str) -> str:
    inn = _heuristic_inn(text)
    return _encode_tier(text, inn)


from scripts.sut.prose.manifest_index import (  # noqa: E402
    load_all_drug_clause_ids,
    manifest_clause_ids_and_tiers,
)


def _load_manifest_index(manifest_path: Path) -> tuple[set[str], dict[str, str]]:
    ids, tiers = manifest_clause_ids_and_tiers(manifest_path)
    return set(ids), tiers


def _gate_b_tier_lookup(clauses_path: Path, rules_path: Path) -> dict[str, str]:
    frame = export_4_2_14_c_candidates(clauses_path, rules_path=rules_path)
    return {
        str(row["clause_id"]): str(row["encode_tier"])
        for row in frame.iter_rows(named=True)
        if row.get("clause_id")
    }


def _section_bucket(section_id: str) -> str:
    sid = str(section_id or "")
    for prefix in _SECTION_PREFIXES:
        if sid.startswith(prefix):
            return prefix
    return "rest"


def _load_all_drug_manifest_indices(manifest_dir: Path) -> tuple[set[str], dict[str, str]]:
    """Union clause IDs and encode tiers from all §4.2 drug Gate B manifests."""
    ids, tiers = load_all_drug_clause_ids(manifest_dir)
    return set(ids), tiers


def build_gap_refresh_frame(
    coverage_path: Path,
    *,
    manifest_path: Path,
    clauses_path: Path,
    rules_path: Path,
) -> pl.DataFrame:
    coverage = pl.read_parquet(coverage_path)
    motor = coverage.filter(pl.col("primary_rule_id") == _MOTOR)
    if motor.is_empty():
        return pl.DataFrame()

    manifest_ids, manifest_tiers = _load_all_drug_manifest_indices(_DEFAULT_MANIFEST_DIR)
    gate_b_tiers = _gate_b_tier_lookup(clauses_path, rules_path)

    rows: list[dict[str, Any]] = []
    for record in motor.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        text = str(record.get("in_force_text") or record.get("text_tr") or "")
        encode_tier = manifest_tiers.get(clause_id) or gate_b_tiers.get(clause_id) or _infer_encode_tier(text)
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": str(record.get("section_id") or ""),
                "text_excerpt": _text_excerpt(text),
                "deontic_modality": record.get("deontic_modality"),
                "encode_tier": encode_tier,
                "in_manifest": clause_id in manifest_ids,
                "has_rule_encoding": bool(record.get("has_rule_encoding")),
            }
        )

    return pl.DataFrame(rows).sort("clause_id")


def build_a0_summary(
    gap_frame: pl.DataFrame,
    *,
    manifest_path: Path,
    gate_b_frame: pl.DataFrame | None = None,
) -> dict[str, Any]:
    manifest_ids, _ = _load_manifest_index(manifest_path)
    encoded_ids = {
        str(row["clause_id"])
        for row in gap_frame.filter(pl.col("has_rule_encoding")).iter_rows(named=True)
    }

    unencoded = gap_frame.filter(~pl.col("has_rule_encoding"))
    deontic_unencoded = unencoded.filter(
        pl.col("deontic_modality").is_not_null() & (pl.col("deontic_modality") != "")
    )

    unencoded_by_prefix: dict[str, int] = {}
    for prefix in (*_SECTION_PREFIXES, "rest"):
        if prefix == "rest":
            mask = ~pl.col("section_id").str.starts_with("4.2.14.C") & ~pl.col(
                "section_id"
            ).str.starts_with("4.2.13") & ~pl.col("section_id").str.starts_with("4.2.16") & ~pl.col(
                "section_id"
            ).str.starts_with("4.2.33")
        else:
            mask = pl.col("section_id").str.starts_with(prefix)
        unencoded_by_prefix[prefix] = int(unencoded.filter(mask).height)

    tier_counts: dict[str, int] = {}
    for tier, count in gap_frame.group_by("encode_tier").len().iter_rows():
        tier_counts[str(tier)] = int(count)

    in_manifest_not_encoded = sorted(manifest_ids - encoded_ids)
    encoded_not_in_manifest = sorted(encoded_ids - manifest_ids)

    summary: dict[str, Any] = {
        "generated_at": date.today().isoformat(),
        "motor": _MOTOR,
        "total_clauses": int(gap_frame.height),
        "has_rule_encoding_true": int(gap_frame.filter(pl.col("has_rule_encoding")).height),
        "has_rule_encoding_false": int(unencoded.height),
        "manifest_clause_count": len(manifest_ids),
        "in_manifest_not_encoded_count": len(in_manifest_not_encoded),
        "in_manifest_not_encoded_clause_ids": in_manifest_not_encoded,
        "encoded_not_in_manifest_count": len(encoded_not_in_manifest),
        "encoded_not_in_manifest_clause_ids": encoded_not_in_manifest,
        "deontic_not_encoded_count": int(deontic_unencoded.height),
        "encode_tier_counts": dict(sorted(tier_counts.items())),
        "unencoded_by_section_prefix": unencoded_by_prefix,
    }
    if gate_b_frame is not None and not gate_b_frame.is_empty():
        summary["gate_b_4_2_14_c_summary"] = gate_b_summary(gate_b_frame)
    return summary


def run_a0_inventory(
    *,
    clauses_path: Path = _DEFAULT_CLAUSES,
    coverage_path: Path = _DEFAULT_COVERAGE,
    manifest_path: Path = _DEFAULT_MANIFEST,
    rules_path: Path = _DEFAULT_RULES,
    gate_b_csv: Path = _DEFAULT_GATE_B_CSV,
    gap_csv: Path = _DEFAULT_GAP_CSV,
    summary_json: Path = _DEFAULT_SUMMARY,
    refresh_gate_b: bool = True,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    gate_b_frame = (
        write_gate_b_export(clauses_path, gate_b_csv, rules_path=rules_path)
        if refresh_gate_b
        else pl.read_csv(gate_b_csv)
    )

    gap_frame = build_gap_refresh_frame(
        coverage_path,
        manifest_path=manifest_path,
        clauses_path=clauses_path,
        rules_path=rules_path,
    )
    gap_csv.parent.mkdir(parents=True, exist_ok=True)
    gap_frame.write_csv(gap_csv)

    summary = build_a0_summary(gap_frame, manifest_path=manifest_path, gate_b_frame=gate_b_frame)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return gate_b_frame, gap_frame, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_DEFAULT_CLAUSES)
    parser.add_argument("--coverage", type=Path, default=_DEFAULT_COVERAGE)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--rules", type=Path, default=_DEFAULT_RULES)
    parser.add_argument("--gate-b-csv", type=Path, default=_DEFAULT_GATE_B_CSV)
    parser.add_argument("--gap-csv", type=Path, default=_DEFAULT_GAP_CSV)
    parser.add_argument("--summary-json", type=Path, default=_DEFAULT_SUMMARY)
    parser.add_argument("--skip-gate-b-refresh", action="store_true")
    args = parser.parse_args()

    gate_b_frame, gap_frame, summary = run_a0_inventory(
        clauses_path=args.clauses,
        coverage_path=args.coverage,
        manifest_path=args.manifest,
        rules_path=args.rules,
        gate_b_csv=args.gate_b_csv,
        gap_csv=args.gap_csv,
        summary_json=args.summary_json,
        refresh_gate_b=not args.skip_gate_b_refresh,
    )
    print(f"Gate B §4.2.14.C rows: {gate_b_frame.height} -> {args.gate_b_csv}")
    print(f"Gap refresh rows: {gap_frame.height} -> {args.gap_csv}")
    print(f"Summary -> {args.summary_json}")
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith("_clause_ids")}, indent=2))


if __name__ == "__main__":
    main()
