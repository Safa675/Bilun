#!/usr/bin/env python3
"""Export §3.1–3.2 material bundling corpus backlog (Phase 8 — beyond Gate B CSV)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.material_bundling_gate_b import (  # noqa: E402
    _normalize_tr,
    load_candidate_clauses,
)
from src.bilun.domain.sut.clause_in_force import in_force_polars_filter, regulatory_text_column


def _theme_label(excerpt: str) -> str:
    text = _normalize_tr(excerpt)
    if "ihale" in text or "dogrudan temin" in text or "dts" in text:
        return "ihale_dts"
    if "titubb" in text or "uts" in text or "barkod" in text:
        return "titubb_uts_barkod"
    if "garanti" in text or "onarim" in text or "onarım" in excerpt.lower():
        return "garanti_onarim"
    if "faturaland" in text:
        prohib = (
            "faturalandirilamaz",
            "ayrica faturalandirilamaz",
            "karsilanmaz",
            "odenmez",
        )
        if any(marker in text for marker in prohib):
            return "faturalandirma_prohibition"
        return "faturalandirma_scope"
    if "ek-3" in text or "ek3" in text.replace("-", ""):
        return "ek3_list"
    if "malzeme" in text:
        return "malzeme_general"
    return "other"


def build_corpus_batch2(clauses_path: Path, prose_json_path: Path) -> pl.DataFrame:
    """§3.1+3.2 rows with material keywords not already in Gate B export."""
    all_sec = in_force_polars_filter(pl.read_parquet(clauses_path)).filter(
        pl.col("section_id").str.starts_with("3.1")
        | pl.col("section_id").str.starts_with("3.2")
    )
    text_col = regulatory_text_column(all_sec)
    gate_b_ids = set(load_candidate_clauses(clauses_path)["clause_id"].to_list())

    keywords = (
        "malzeme",
        "ek-3",
        "titubb",
        "uts",
        "barkod",
        "faturaland",
        "ihale",
        "garanti",
        "onarım",
        "onarim",
    )
    keyword_expr = pl.lit(False)
    for kw in keywords:
        keyword_expr = keyword_expr | pl.col(text_col).str.to_lowercase().str.contains(kw)

    backlog = all_sec.filter(keyword_expr).filter(~pl.col("clause_id").is_in(list(gate_b_ids)))

    encoded_sources: set[str] = set()
    if prose_json_path.is_file():
        payload = json.loads(prose_json_path.read_text(encoding="utf-8"))
        for rule in payload.get("rules") or []:
            encoded_sources.update(rule.get("gate_b_sources") or [])

    manifest_path = Path("data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json")
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in (
            "ek3c_list_price_ceiling_clause_ids",
            "corpus_ek3_annex_header_clause_ids",
            "corpus_ek3_scope_clause_ids",
            "corpus_malzeme_general_header_clause_ids",
            "corpus_malzeme_scope_clause_ids",
            "sut_material_list_price_ceiling_clause_ids",
            "kdv_pricing_clause_ids",
            "separate_billing_allowlist_clause_ids",
        ):
            encoded_sources.update(str(item) for item in (manifest.get(key) or []))

    rows: list[dict[str, object]] = []
    for record in backlog.iter_rows(named=True):
        excerpt = str(record.get("in_force_text") or record.get("text_tr") or "")
        clause_id = str(record.get("clause_id") or "")
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": record.get("section_id"),
                "deontic_modality": record.get("deontic_modality"),
                "theme": _theme_label(excerpt),
                "in_l14_encode_manifest": clause_id in encoded_sources,
                "char_count": record.get("char_count"),
                "excerpt": excerpt,
            }
        )
    return pl.DataFrame(rows).sort("theme", "section_id", "clause_id")


def main() -> None:
    parser = argparse.ArgumentParser(description="L1.4 corpus batch 2 backlog export")
    parser.add_argument(
        "--clauses",
        type=Path,
        default=Path("data/gazette/sut_clauses.parquet"),
    )
    parser.add_argument(
        "--prose-json",
        type=Path,
        default=Path("data/gazette/prose_rules/material_bundling_prose.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2.csv"),
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=Path("data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2_summary.json"),
    )
    args = parser.parse_args()

    df = build_corpus_batch2(args.clauses, args.prose_json)
    theme_counts = (
        df.group_by("theme").len().sort("len", descending=True).to_dicts()
        if len(df)
        else []
    )
    summary = {
        "total_rows": len(df),
        "already_in_l14_encode_manifest": int(
            df.filter(pl.col("in_l14_encode_manifest")).height
        )
        if len(df)
        else 0,
        "by_theme": theme_counts,
        "note": (
            "§3.1+3.2 keyword backlog beyond Gate B CSV (48 rows). "
            "733 registry rows include §3.3 specialty bulk — not all encodable as prose."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(df)} rows to {args.out}")
    print(f"Summary: {args.summary_out}")


if __name__ == "__main__":
    main()
