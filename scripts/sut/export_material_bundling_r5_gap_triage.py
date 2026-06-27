#!/usr/bin/env python3
"""R5 Epic B Phase B0 — §3.1–3.2 material bundling motor-bound gap triage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.export_material_bundling_corpus_batch2 import _theme_label  # noqa: E402
from scripts.sut.prose.material_bundling_gate_b import (  # noqa: E402
    _annex_refs_list,
    _duplicate_of,
    _normalize_tr,
)

_MANIFEST_HEADER_KEYS = (
    "corpus_ek3_annex_header_clause_ids",
    "corpus_ek3_scope_clause_ids",
    "corpus_malzeme_general_header_clause_ids",
    "corpus_malzeme_scope_clause_ids",
    "ek3c_list_price_ceiling_clause_ids",
    "sut_material_list_price_ceiling_clause_ids",
    "kdv_pricing_clause_ids",
    "separate_billing_allowlist_clause_ids",
    "r5_amendment_header_clause_ids",
    "r5_manifest_header_only_clause_ids",
)

_MÜLGA_PATTERN = re.compile(r"mulga|yururluge girer|yürürlüğe girer", re.IGNORECASE)
_LIST_ITEM_PATTERN = re.compile(
    r"^[a-zçğıöşü]\)\s",
    re.IGNORECASE,
)


def _load_manifest_header_ids(manifest_path: Path) -> set[str]:
    if not manifest_path.is_file():
        return set()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    header_ids: set[str] = set()
    for key in _MANIFEST_HEADER_KEYS:
        header_ids.update(str(item) for item in (manifest.get(key) or []))
    return header_ids


def _filter_gap_rows(coverage_path: Path) -> pl.DataFrame:
    df = pl.read_parquet(coverage_path)
    return df.filter(
        (
            pl.col("section_id").str.starts_with("3.1")
            | pl.col("section_id").str.starts_with("3.2")
        )
        & (pl.col("primary_rule_id") == "material_bundling_prose")
        & (pl.col("has_rule_encoding") == False)  # noqa: E712
        & (pl.col("coverage_status") != "non_algorithmic")
    )


def _is_manifest_header_only(
    *,
    clause_id: str,
    section_id: str,
    excerpt: str,
    is_heading: bool,
    in_manifest_headers: bool,
    in_batch2_manifest: bool,
) -> bool:
    if is_heading or in_manifest_headers or in_batch2_manifest:
        return True
    norm = _normalize_tr(excerpt)
    if _MÜLGA_PATTERN.search(norm):
        return True
    if section_id.startswith("3.1.4") and _LIST_ITEM_PATTERN.match(excerpt.strip()):
        return True
    if section_id.startswith("3.2.1.") and is_heading:
        return True
    return False


def _triage_action(
    *,
    clause_id: str,
    section_id: str,
    excerpt: str,
    annex_refs: list[str],
    is_heading: bool,
    manifest_header_ids: set[str],
    batch2_manifest_ids: set[str],
) -> str:
    duplicate = _duplicate_of(excerpt=excerpt, annex_refs=annex_refs)
    if duplicate in {"ek3b1", "ek3b2", "ek3b1_and_ek3b2"}:
        return "duplicate_ek3b"
    if _is_manifest_header_only(
        clause_id=clause_id,
        section_id=section_id,
        excerpt=excerpt,
        is_heading=is_heading,
        in_manifest_headers=clause_id in manifest_header_ids,
        in_batch2_manifest=clause_id in batch2_manifest_ids,
    ):
        return "manifest_header_only"
    return "encode_now"


def build_gap_triage(
    coverage_path: Path,
    *,
    batch2_path: Path | None = None,
    manifest_path: Path | None = None,
) -> pl.DataFrame:
    """Build R5 gap triage rows from coverage parquet (+ optional batch2 join)."""
    gap = _filter_gap_rows(coverage_path)
    manifest_header_ids = _load_manifest_header_ids(
        manifest_path or Path("data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json")
    )

    batch2_theme: dict[str, str] = {}
    batch2_manifest_ids: set[str] = set()
    resolved_batch2 = batch2_path or Path(
        "data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2.csv"
    )
    if resolved_batch2.is_file():
        batch2 = pl.read_csv(resolved_batch2)
        batch2_theme = dict(
            zip(batch2["clause_id"].cast(pl.Utf8), batch2["theme"].cast(pl.Utf8), strict=False)
        )
        if "in_l14_encode_manifest" in batch2.columns:
            batch2_manifest_ids = set(
                batch2.filter(pl.col("in_l14_encode_manifest") == True)["clause_id"]  # noqa: E712
                .cast(pl.Utf8)
                .to_list()
            )

    rows: list[dict[str, object]] = []
    for record in gap.iter_rows(named=True):
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        excerpt = str(record.get("in_force_text") or record.get("text_tr") or "")
        annex_refs = _annex_refs_list(record.get("annex_refs"))
        theme = batch2_theme.get(clause_id) or _theme_label(excerpt)
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": record.get("deontic_modality"),
                "theme": theme,
                "triage_action": _triage_action(
                    clause_id=clause_id,
                    section_id=section_id,
                    excerpt=excerpt,
                    annex_refs=annex_refs,
                    is_heading=bool(record.get("is_heading")),
                    manifest_header_ids=manifest_header_ids,
                    batch2_manifest_ids=batch2_manifest_ids,
                ),
            }
        )

    df = pl.DataFrame(rows)
    if len(df):
        df = df.sort("triage_action", "theme", "section_id", "clause_id")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R5 §3.1–3.2 material bundling motor-bound gap triage"
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=Path("data/gazette/sut_clause_coverage.parquet"),
    )
    parser.add_argument(
        "--batch2",
        type=Path,
        default=Path("data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2.csv"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/gazette/prose_corpus/L1.4_material_bundling_r5_gap_triage.csv"),
    )
    args = parser.parse_args()

    df = build_gap_triage(
        args.coverage,
        batch2_path=args.batch2 if args.batch2.is_file() else None,
        manifest_path=args.manifest,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if len(df):
        df.write_csv(args.out)
    else:
        args.out.write_text(
            "clause_id,section_id,deontic_modality,theme,triage_action\n",
            encoding="utf-8",
        )

    breakdown = (
        df.group_by("triage_action").len().sort("triage_action").to_dicts()
        if len(df)
        else []
    )
    print(f"R5 gap triage: {len(df)} rows → {args.out}")
    for item in breakdown:
        print(f"  {item['triage_action']}: {item['len']}")


if __name__ == "__main__":
    main()
