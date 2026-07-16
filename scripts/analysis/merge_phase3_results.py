#!/usr/bin/env python3
"""Phase 3 merge: DRUG + MATERIAL generator results + LLM results → frozen table.

Extends the Phase 2 merge to handle:
  - DRUG: resolves to EK-4A entries carrying full drug_identity
    (kamu_no + barcode + equivalence_group). Promotes generator brand-match
    (conf≥0.7) + LLM FOUND (conf≥0.8).
  - MATERIAL: resolves to EK-3 categories. Promotes generator (conf≥0.7) +
    LLM FOUND (conf≥0.8). BUNDLED_CONSUMABLE LLM results are promoted as
    reviewed=TRUE with sut_code="" (explicitly resolved-as-not-reimbursable).
  - Re-runs the generator with the Phase 3 classifier (tightened DRUG/MATERIAL
    regex) so the review CSV reflects the new category assignments.

Reads:
  - data/finans_clean.parquet (source codes + descriptions)
  - /tmp/p3/drug_*_result.json, /tmp/p3/material_*_result.json (LLM results)
  - data/coding/hospital_to_sut.csv (existing Phase 2 frozen rows — preserved)

Writes:
  - data/coding/crosswalk_review.csv (all 924 codes, generator+LLM columns)
  - data/coding/hospital_to_sut.csv (frozen, reviewed-only — all 4 categories)
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO_ROOT))

from src.bilun.domain.coding import (  # noqa: E402
    CategoryHint,
    classify_category,
    resolve_code,
)
from src.bilun.domain.coding.code_resolver import clear_resolver_cache  # noqa: E402

FINANS_CLEAN = REPO_ROOT / "data" / "finans_clean.parquet"
REVIEW_CSV = REPO_ROOT / "data" / "coding" / "crosswalk_review.csv"
FROZEN_CSV = REPO_ROOT / "data" / "coding" / "hospital_to_sut.csv"

REVIEW_COLUMNS = [
    "hospital_code", "description", "category",
    "generator_method", "generator_sut_code", "generator_confidence",
    "generator_sut_name", "top5_candidates", "needs_llm",
    "llm_sut_code", "llm_confidence", "llm_rationale",
    "reviewer_decision", "reviewer_sut_code", "reviewed",
]

FROZEN_COLUMNS = [
    "hospital_code", "sut_code", "category", "source", "confidence",
    "rationale", "drug_identity", "verified_by", "verified_date", "reviewed",
]

DRUG_LLM_FILES = [
    Path("/tmp/p3/drug_1to3_result.json"),
    Path("/tmp/p3/drug_4to5_result.json"),
    Path("/tmp/p3/drug_6to8_result.json"),
]
MATERIAL_LLM_FILES = [Path("/tmp/p3/material_1to2_result.json")]


def load_llm_results() -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in [*DRUG_LLM_FILES, *MATERIAL_LLM_FILES]:
        if not path.exists():
            print(f"WARN: {path} missing")
            continue
        for r in json.load(path.open(encoding="utf-8")):
            merged[r["hospital_code"]] = r
    return merged


def main() -> None:
    clear_resolver_cache()
    llm = load_llm_results()
    print(f"Loaded {len(llm)} LLM results")

    # Load existing frozen table (Phase 2 LAB+PROCEDURE) to preserve
    existing_frozen: dict[str, dict] = {}
    if FROZEN_CSV.exists():
        with FROZEN_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing_frozen[r["hospital_code"]] = r

    # Load all finans codes, classify with the tightened Phase 3 classifier
    finans = pl.read_parquet(FINANS_CLEAN)
    codes = (
        finans.group_by(["HIZMETKODU", "HIZMET_TANIMI"])
        .agg(n=pl.len())
        .sort("n", descending=True)
    )
    codes = codes.with_columns(
        pl.col("HIZMET_TANIMI")
        .map_elements(classify_category, return_dtype=pl.Utf8)
        .alias("category")
    )
    print(f"\nTotal codes: {len(codes)}")
    print(codes.group_by("category").agg(n=pl.len(), n_rows=pl.col("n").sum()).sort("n_rows", descending=True))

    review_rows: list[dict] = []
    promoted: dict[str, dict] = dict(existing_frozen)  # start with Phase 2
    counts = Counter()

    for r in codes.iter_rows(named=True):
        code = r["HIZMETKODU"]
        desc = r["HIZMET_TANIMI"] or ""
        cat = r["category"]
        res = resolve_code(code, desc, CategoryHint(kind=cat))
        llm_r = llm.get(code)
        needs_llm = res.sut_code is None or res.confidence < 0.7

        # Top-5 candidates string
        top5 = "; ".join(
            f"{c['code']}({c['confidence']:.2f})" for c in res.candidates[:5]
        )

        # Promotion logic by category
        promoted_row = None
        decision = ""
        reviewer_code = ""

        # Already in frozen table (Phase 2)? skip re-promotion.
        if code in existing_frozen:
            decision = "already_frozen"
            reviewer_code = existing_frozen[code].get("sut_code", "")
            counts["already_frozen"] += 1
        # Generator resolved at confidence
        elif res.sut_code and res.confidence >= 0.7:
            drug_identity = res.drug_identity if cat == "DRUG" else None
            promoted_row = _frozen_row(
                code, res.sut_code, cat, f"generator_{res.method}",
                res.confidence, f"generator: {res.sut_name or ''}",
                drug_identity,
            )
            decision = "accept_generator"
            reviewer_code = res.sut_code
            counts[f"gen_{cat}"] += 1
        # LLM FOUND
        elif llm_r and llm_r.get("decision") == "FOUND" and float(llm_r.get("llm_confidence", 0)) >= 0.8:
            sut = llm_r["llm_sut_code"]
            di = None
            if cat == "DRUG":
                di = {
                    "kamu_no": sut,
                    "barcode": llm_r.get("llm_barcode", ""),
                    "equivalence_group": llm_r.get("llm_equivalence_group", ""),
                }
            promoted_row = _frozen_row(
                code, sut, cat, "llm_found",
                float(llm_r["llm_confidence"]),
                llm_r.get("llm_rationale", ""), di,
            )
            decision = "accept_llm"
            reviewer_code = sut
            counts[f"llm_found_{cat}"] += 1
        # LLM BUNDLED_CONSUMABLE (material, explicitly not reimbursable)
        elif llm_r and llm_r.get("decision") == "BUNDLED_CONSUMABLE":
            promoted_row = _frozen_row(
                code, "", cat, "llm_bundled",
                float(llm_r.get("llm_confidence", 0.9)),
                llm_r.get("llm_rationale", "bundled consumable"), None,
            )
            decision = "accept_bundled"
            counts["bundled"] += 1
        # LLM AMBIGUOUS → human review
        elif llm_r and llm_r.get("decision") == "AMBIGUOUS":
            decision = "needs_human_disambiguation"
            reviewer_code = llm_r.get("llm_sut_code", "")
            counts[f"ambig_{cat}"] += 1
        # LLM NOT_IN_EK4A / NO_MATCH
        elif llm_r and llm_r.get("decision") in ("NOT_IN_EK4A", "NO_MATCH"):
            decision = "no_match"
            counts[f"nomatch_{cat}"] += 1
        # No LLM result (DRUG/MATERIAL generator miss with no LLM, or LAB/PROC
        # already handled in Phase 2 review — but we re-run all here)
        else:
            decision = "no_llm"
            counts[f"no_llm_{cat}"] += 1

        if promoted_row:
            promoted[code] = promoted_row

        review_rows.append({
            "hospital_code": code, "description": desc, "category": cat,
            "generator_method": res.method, "generator_sut_code": res.sut_code or "",
            "generator_confidence": round(res.confidence, 3),
            "generator_sut_name": res.sut_name or "",
            "top5_candidates": top5, "needs_llm": str(needs_llm),
            "llm_sut_code": (llm_r or {}).get("llm_sut_code", ""),
            "llm_confidence": (llm_r or {}).get("llm_confidence", ""),
            "llm_rationale": (llm_r or {}).get("llm_rationale", ""),
            "reviewer_decision": decision, "reviewer_sut_code": reviewer_code,
            "reviewed": "TRUE" if promoted_row else "FALSE",
        })

    # Write review CSV
    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
        w.writeheader(); w.writerows(review_rows)

    # Write frozen CSV (reviewed-only)
    frozen_rows = [r for r in promoted.values()]
    # ensure all have the Phase 3 columns
    for r in frozen_rows:
        for c in FROZEN_COLUMNS:
            r.setdefault(c, "")
    with FROZEN_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FROZEN_COLUMNS)
        w.writeheader()
        w.writerows(frozen_rows)

    # Summary
    reviewed = sum(1 for r in review_rows if r["reviewed"] == "TRUE")
    print("\n=== Promotion summary ===")
    for k, v in sorted(counts.items()):
        print(f"  {k:25s} {v}")
    print(f"\n  REVIEWED=TRUE: {reviewed}/{len(review_rows)} ({100*reviewed/len(review_rows):.1f}%)")
    print(f"  Frozen table: {len(frozen_rows)} rows")
    # by category
    by_cat = Counter(r["category"] for r in frozen_rows if str(r.get("reviewed","")).upper()=="TRUE")
    print(f"  frozen by category: {dict(by_cat)}")


def _frozen_row(
    code: str, sut: str, cat: str, source: str, conf: float,
    rationale: str, drug_identity: dict | None,
) -> dict[str, str]:
    return {
        "hospital_code": code, "sut_code": sut, "category": cat,
        "source": source, "confidence": f"{conf:.3f}",
        "rationale": (rationale or "")[:200],
        "drug_identity": json.dumps(drug_identity) if drug_identity else "",
        "verified_by": "generator" if source.startswith("generator") else (
            "safa_human" if source == "human" else "llm_subagent"
        ),
        "verified_date": str(date.today()),
        "reviewed": "TRUE",
    }


if __name__ == "__main__":
    main()
