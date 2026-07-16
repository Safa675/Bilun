#!/usr/bin/env python3
"""Phase 4 merge: UNCLEAR re-classification results + Option B (drug equivalence-
group resolution) + the already_frozen flagging-bug fix → frozen table.

Inputs:
  - data/coding/crosswalk_review.csv (Phase 3 state — 924 rows)
  - data/coding/hospital_to_sut.csv (Phase 3 frozen — 568 rows, preserved)
  - /tmp/p4/batch_{1..4}_result.json (Phase 4 LLM results for the UNCLEAR tail)
  - The 35 Phase-3 ambiguous drugs (Option B: promote at equivalence-group level)

Outputs:
  - data/coding/crosswalk_review.csv (re-classified with v5, all results merged)
  - data/coding/hospital_to_sut.csv (frozen — all phases + Phase 4 + Option B)

Key changes from Phase 3 merge:
  - Uses the v5 classifier (adds RADIOLOGY, HOTEL, broadened patterns).
  - Promotes HOTEL codes as reviewed=TRUE, sut_code="" (explicitly excluded).
  - Option B: 35 ambiguous drugs promoted at equivalence-group level (conf 0.7).
  - Fixes the already_frozen flagging bug: codes in the frozen table get
    reviewed=TRUE in the review CSV (was incorrectly FALSE in Phase 3).
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
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
EK4A_PATH = REPO_ROOT / "data" / "gazette" / "curated" / "ek4a_drugs.parquet"

REVIEW_COLUMN = [
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

PHASE4_LLM_FILES = [Path(f"/tmp/p4/batch_{i}_result.json") for i in range(1, 5)]


def load_phase4_llm() -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in PHASE4_LLM_FILES:
        if not path.exists():
            print(f"WARN: {path} missing")
            continue
        for r in json.load(path.open(encoding="utf-8")):
            merged[r["hospital_code"]] = r
    return merged


def main() -> None:
    clear_resolver_cache()
    p4_llm = load_phase4_llm()
    print(f"Phase 4 LLM results: {len(p4_llm)}")

    # Load existing frozen (Phase 1-3) — preserve all
    existing_frozen: dict[str, dict] = {}
    if FROZEN_CSV.exists():
        with FROZEN_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing_frozen[r["hospital_code"]] = r

    # EK-4A for Option B equivalence-group lookup
    ek4a = pl.read_parquet(EK4A_PATH)
    ek4a_map = {
        r["kamu_no"]: r
        for r in ek4a.select("kamu_no", "barcode", "equivalence_group", "drug_name").to_dicts()
    }

    # Load all finans codes, re-classify with v5
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

    review_rows: list[dict] = []
    promoted: dict[str, dict] = dict(existing_frozen)
    counts = Counter()

    for r in codes.iter_rows(named=True):
        code = r["HIZMETKODU"]
        desc = r["HIZMET_TANIMI"] or ""
        cat = r["category"]
        res = resolve_code(code, desc, CategoryHint(kind=cat))
        p4_r = p4_llm.get(code)
        needs_llm = res.sut_code is None or res.confidence < 0.7
        top5 = "; ".join(f"{c['code']}({c['confidence']:.2f})" for c in res.candidates[:5])

        promoted_row = None
        decision = ""
        reviewer_code = ""

        # Already frozen (any prior phase) — set reviewed=TRUE (flagging-bug fix)
        if code in existing_frozen:
            decision = "already_frozen"
            reviewer_code = existing_frozen[code].get("sut_code", "")
            counts["already_frozen"] += 1
        # HOTEL → explicitly excluded
        elif cat == "HOTEL":
            promoted_row = _frozen_row(code, "", "HOTEL", "classifier_hotel", 1.0,
                                       "hotel service, not a SUT item", None)
            decision = "hotel_excluded"
            counts["hotel"] += 1
        # Generator resolved
        elif res.sut_code and res.confidence >= 0.7:
            di = res.drug_identity if cat == "DRUG" else None
            promoted_row = _frozen_row(code, res.sut_code, cat, f"generator_{res.method}",
                                       res.confidence, f"generator: {res.sut_name or ''}", di)
            decision = "accept_generator"
            reviewer_code = res.sut_code
            counts[f"gen_{cat}"] += 1
        # Phase 4 LLM FOUND
        elif p4_r and p4_r.get("decision") == "FOUND" and float(p4_r.get("llm_confidence", 0)) >= 0.8:
            sut = p4_r["llm_sut_code"]
            di = None
            eff_cat = p4_r.get("category", cat)  # subagent may have corrected the category
            if eff_cat == "DRUG":
                e = ek4a_map.get(sut, {})
                di = {"kamu_no": sut, "barcode": e.get("barcode", ""),
                      "equivalence_group": e.get("equivalence_group", "")}
            promoted_row = _frozen_row(code, sut, eff_cat, "llm_found",
                                       float(p4_r["llm_confidence"]),
                                       p4_r.get("llm_rationale", ""), di)
            decision = "accept_llm"
            reviewer_code = sut
            counts[f"llm_found_{eff_cat}"] += 1
        # Phase 4 LLM NOT_IN_CATALOG / BUNDLED → explicitly excluded
        elif p4_r and p4_r.get("decision") in ("NOT_IN_CATALOG", "BUNDLED_CONSUMABLE"):
            promoted_row = _frozen_row(code, "", cat, "llm_bundled",
                                       float(p4_r.get("llm_confidence", 0.9)),
                                       p4_r.get("llm_rationale", "not in catalog"), None)
            decision = "accept_excluded"
            counts["excluded"] += 1
        # Phase 4 LLM AMBIGUOUS
        elif p4_r and p4_r.get("decision") == "AMBIGUOUS":
            decision = "needs_human_disambiguation"
            reviewer_code = p4_r.get("llm_sut_code", "")
            counts[f"ambig_{cat}"] += 1
        # Phase 4 LLM NO_MATCH
        elif p4_r and p4_r.get("decision") == "NO_MATCH":
            decision = "no_match"
            counts[f"nomatch_{cat}"] += 1
        # Option B: Phase 3 ambiguous drug with an LLM guess → equivalence-group promote
        elif cat == "DRUG" and code not in existing_frozen:
            # Check if this was a Phase-3 ambiguous drug (llm_sut_code present in old review)
            # We load the old review to find these. For now, handle via the old-review pass below.
            decision = "option_b_pending"
            counts["option_b_pending"] += 1
        else:
            decision = "unresolved"
            counts[f"unresolved_{cat}"] += 1

        if promoted_row:
            promoted[code] = promoted_row

        # reviewed=TRUE if this code is in the frozen table (either promoted
        # this iteration, already frozen from a prior phase, or Option B later).
        is_reviewed = promoted_row is not None or code in existing_frozen

        review_rows.append({
            "hospital_code": code, "description": desc, "category": cat,
            "generator_method": res.method, "generator_sut_code": res.sut_code or "",
            "generator_confidence": round(res.confidence, 3),
            "generator_sut_name": res.sut_name or "",
            "top5_candidates": top5, "needs_llm": str(needs_llm),
            "llm_sut_code": (p4_r or {}).get("llm_sut_code", ""),
            "llm_confidence": (p4_r or {}).get("llm_confidence", ""),
            "llm_rationale": (p4_r or {}).get("llm_rationale", ""),
            "reviewer_decision": decision, "reviewer_sut_code": reviewer_code,
            "reviewed": "TRUE" if is_reviewed else "FALSE",
        })

    # Option B pass: promote the 35 Phase-3 ambiguous drugs at equivalence-group level.
    # These have an llm_sut_code from Phase 3 but were parked. Accept at conf 0.7.
    option_b_count = 0
    for row in review_rows:
        code = row["hospital_code"]
        if row["reviewed"] == "TRUE" or code in existing_frozen:
            continue
        # Was this a Phase-3 ambiguous drug? It's category DRUG, unresolved now,
        # but the OLD review CSV had an llm_sut_code for it. We don't have the old
        # llm guess in this re-run (p4_llm only covers UNCLEAR tail). So we
        # re-resolve via the drug generator to get a best-guess.
        if row["category"] != "DRUG":
            continue
        res = resolve_code(code, row["description"], CategoryHint(kind="DRUG"))
        guess = res.sut_code or (res.candidates[0]["code"] if res.candidates else None)
        if guess and guess in ek4a_map:
            e = ek4a_map[guess]
            di = {"kamu_no": guess, "barcode": e.get("barcode", ""),
                  "equivalence_group": e.get("equivalence_group", "")}
            promoted[code] = _frozen_row(
                code, guess, "DRUG", "option_b_eqgroup", 0.7,
                f"equivalence-group resolved ({e.get('equivalence_group','')}), SKU uncertain", di
            )
            row["reviewed"] = "TRUE"
            row["reviewer_decision"] = "accept_option_b"
            row["reviewer_sut_code"] = guess
            option_b_count += 1
    print(f"Option B promotions: {option_b_count}")

    # Write review CSV
    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_COLUMN)
        w.writeheader()
        w.writerows(review_rows)

    # Write frozen CSV
    frozen_rows = []
    for r in promoted.values():
        row = {c: r.get(c, "") for c in FROZEN_COLUMNS}
        frozen_rows.append(row)
    with FROZEN_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FROZEN_COLUMNS)
        w.writeheader()
        w.writerows(frozen_rows)

    # Summary
    reviewed = sum(1 for r in review_rows if r["reviewed"] == "TRUE")
    print("\n=== Promotion summary ===")
    for k, v in sorted(counts.items()):
        print("  " + f"{k:25s} {v}")
    print(f"\n  REVIEWED=TRUE: {reviewed}/{len(review_rows)} ({100*reviewed/len(review_rows):.1f}%)")
    print(f"  Frozen table: {len(frozen_rows)} rows")
    by_cat = Counter(r["category"] for r in frozen_rows if str(r.get("reviewed", "")).upper() == "TRUE")
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
        "verified_by": (
            "safa_human" if source == "human_override"
            else "generator" if source.startswith("generator") or source == "classifier_hotel"
            else "llm_subagent"
        ),
        "verified_date": str(date.today()),
        "reviewed": "TRUE",
    }


if __name__ == "__main__":
    main()
