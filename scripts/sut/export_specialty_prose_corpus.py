#!/usr/bin/env python3
"""Export §3.3 specialty prose corpus (L4.4 Phase 0 — keyword / NO_PAY subset)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.material_bundling_gate_b import _normalize_tr  # noqa: E402

_DEFAULT_CLAUSES = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_DEFAULT_OUT_CSV = _PROJECT_ROOT / "evidence/clauses/L4.4_specialty_prose.csv"
_DEFAULT_OUT_SUMMARY = _PROJECT_ROOT / "evidence/clauses/L4.4_specialty_prose_summary.json"
_MANIFEST_PATH = _PROJECT_ROOT / "evidence/clauses/L4.4_specialty_prose_encoded_manifest.json"


def _is_section_3_3_1(section_id: str) -> bool:
    """True for §3.3.1 only — excludes 3.3.10, 3.3.11, …"""
    sid = str(section_id or "")
    return sid == "3.3.1" or sid.startswith("3.3.1.")


def _is_section_3_3_3(section_id: str) -> bool:
    """True for §3.3.3 / 3.3.3.A–C only — excludes 3.3.30+."""
    sid = str(section_id or "")
    return sid == "3.3.3" or sid.startswith("3.3.3.")


def _is_section_3_3_4(section_id: str) -> bool:
    """True for §3.3.4 / 3.3.4.A–C only — excludes 3.3.40+."""
    sid = str(section_id or "")
    return sid == "3.3.4" or sid.startswith("3.3.4.")


def _is_section_3_3_2(section_id: str) -> bool:
    """True for §3.3.2 only — excludes 3.3.20+."""
    sid = str(section_id or "")
    return sid == "3.3.2" or sid.startswith("3.3.2.")


def _is_section_3_3_7(section_id: str) -> bool:
    """True for §3.3.7 / 3.3.7.* only — excludes 3.3.70+."""
    sid = str(section_id or "")
    return sid == "3.3.7" or sid.startswith("3.3.7.")


def _is_section_3_3_6(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.6" or sid.startswith("3.3.6.")


def _is_section_3_3_8(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.8" or sid.startswith("3.3.8.")


def _is_section_3_3_11(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.11" or sid.startswith("3.3.11.")


def _is_section_3_3_12(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.12" or sid.startswith("3.3.12.")


def _is_section_3_3_14(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.14" or sid.startswith("3.3.14.")


def _is_section_3_3_16(section_id: str) -> bool:
    sid = str(section_id or "")
    return sid == "3.3.16" or sid.startswith("3.3.16.")


def _section_theme(section_id: str) -> str:
    """Map §3.3 branch to encode batch theme (L4.4 Phase 3 table)."""
    sid = str(section_id or "")
    if _is_section_3_3_1(sid):
        return "wound_dressing"
    if _is_section_3_3_3(sid):
        return "vision_optik"
    if sid.startswith("3.3.35") or sid.startswith("3.3.32"):
        return "hearing_aid"
    if sid.startswith("3.3.36") or sid.startswith("3.3.33"):
        return "implant_cochlear"
    if sid.startswith("3.3.37") or sid.startswith("3.3.34"):
        return "incontinence_urology"
    if _is_section_3_3_2(sid):
        return "glucose_meter"
    if _is_section_3_3_4(sid):
        return "specialty_3_3_4"
    if sid.startswith("3.3.5"):
        return "specialty_3_3_5"
    if _is_section_3_3_6(sid):
        return "specialty_3_3_6"
    if _is_section_3_3_7(sid):
        return "specialty_3_3_7"
    if _is_section_3_3_8(sid):
        return "specialty_3_3_8"
    if _is_section_3_3_11(sid) or _is_section_3_3_12(sid):
        return "dental_prosthetic"
    if _is_section_3_3_14(sid) or _is_section_3_3_16(sid):
        return "hernia_mesh"
    if sid.startswith("3.3.9"):
        return "specialty_3_3_9"
    return "other_3_3"


def _is_candidate_row(record: dict[str, object]) -> bool:
    deontic = str(record.get("deontic_modality") or "")
    if deontic in {"NO_PAY", "MUST_NOT_BILL"}:
        return True
    text = _normalize_tr(str(record.get("text_tr") or ""))
    return "faturaland" in text


def _encoded_clause_ids() -> set[str]:
    encoded: set[str] = set()
    prose_path = _PROJECT_ROOT / "data/gazette/prose_rules/specialty_materials_prose.json"
    if prose_path.is_file():
        payload = json.loads(prose_path.read_text(encoding="utf-8"))
        for rule in payload.get("rules") or []:
            encoded.update(str(x) for x in (rule.get("gate_b_sources") or []))
    if _MANIFEST_PATH.is_file():
        manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        for key in (
            "gate_b_sources_encoded",
            "pilot_331_clause_ids",
            "pilot_clause_ids",
            "vision_optik_batch_clause_ids",
            "specialty_334_batch_clause_ids",
            "glucose_meter_batch_clause_ids",
            "specialty_337_batch_clause_ids",
            "specialty_338_batch_clause_ids",
            "specialty_336_batch_clause_ids",
            "other_3_3_tail_clause_ids",
            "corpus_scope_clause_ids",
            "corpus_header_clause_ids",
        ):
            encoded.update(str(x) for x in (manifest.get(key) or []))
    return encoded


def build_corpus(clauses_path: Path) -> pl.DataFrame:
    sec33 = pl.read_parquet(clauses_path).filter(pl.col("section_id").str.starts_with("3.3"))
    encoded = _encoded_clause_ids()

    rows: list[dict[str, object]] = []
    for record in sec33.iter_rows(named=True):
        if not _is_candidate_row(record):
            continue
        clause_id = str(record.get("clause_id") or "")
        section_id = str(record.get("section_id") or "")
        excerpt = str(record.get("text_tr") or "")
        rows.append(
            {
                "clause_id": clause_id,
                "section_id": section_id,
                "deontic_modality": record.get("deontic_modality"),
                "theme": _section_theme(section_id),
                "has_deontic": bool(record.get("deontic_modality")),
                "text_len": len(excerpt),
                "excerpt": excerpt[:500],
                "in_l44_encode_manifest": clause_id in encoded,
            }
        )
    return pl.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_DEFAULT_CLAUSES)
    parser.add_argument("--out-csv", type=Path, default=_DEFAULT_OUT_CSV)
    parser.add_argument("--out-summary", type=Path, default=_DEFAULT_OUT_SUMMARY)
    args = parser.parse_args()

    df = build_corpus(args.clauses)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out_csv)

    theme_counts = df.group_by("theme").len().sort("len", descending=True)
    summary = {
        "total_3_3_clauses": int(
            pl.read_parquet(args.clauses)
            .filter(pl.col("section_id").str.starts_with("3.3"))
            .height
        ),
        "export_row_count": df.height,
        "encoded_in_manifest": int(df.filter(pl.col("in_l44_encode_manifest")).height),
        "theme_counts": {
            row["theme"]: row["len"] for row in theme_counts.iter_rows(named=True)
        },
        "deontic_counts": {
            str(row["deontic_modality"] or "null"): row["len"]
            for row in df.group_by("deontic_modality").len().iter_rows(named=True)
        },
        "note": (
            "L4.4 keyword subset (NO_PAY | MUST_NOT_BILL | faturalandır). "
            "Separate from L1.4 material_bundling_prose (§3.1–3.2). "
            "Encode via specialty_materials_prose.json — not material_bundling_prose.json."
        ),
    }
    args.out_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {df.height} rows to {args.out_csv}")
    print(f"Summary: {args.out_summary}")


if __name__ == "__main__":
    main()
