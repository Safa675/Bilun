#!/usr/bin/env python3
"""Merge LLM-resolved codes into crosswalk_review.csv and build the frozen
mapping table (hospital_to_sut.csv).

Reads:
  - data/coding/crosswalk_review.csv (generator output, llm_* empty)
  - /tmp/finans_batch_{1..4}_result.json (subagent LLM results)

Writes:
  - data/coding/crosswalk_review.csv (re-written with llm_* filled)
  - data/coding/hospital_to_sut.csv (the frozen, reviewed mapping)

Promotion rule into the frozen table:
  - generator FOUND (exact, conf==1.0) → promoted, reviewed=TRUE (deterministic)
  - generator token_prefix (conf in [0.5,1.0)) → promoted, reviewed=TRUE (deterministic)
  - LLM FOUND (conf >= 0.8) → promoted, reviewed=TRUE
  - LLM AMBIGUOUS → NOT promoted (reviewed=FALSE) — needs human disambiguation
  - LLM NO_MATCH → NOT promoted
  - LLM conf < 0.8 → NOT promoted

The reviewed=TRUE rows are the only ones resolve_code() will trust as frozen.
A wrong mapping produces wrong bills — the conservative promotion threshold
is deliberate. AMBIGUOUS rows wait for human review in the CSV.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_CSV = REPO_ROOT / "data" / "coding" / "crosswalk_review.csv"
FROZEN_CSV = REPO_ROOT / "data" / "coding" / "hospital_to_sut.csv"
LLM_BATCHES = [REPO_ROOT.parent / f"tmp/finans_batch_{i}_result.json" for i in range(1, 5)]
# The subagents wrote to /tmp (absolute), not REPO_ROOT-relative:
LLM_BATCHES = [Path(f"/tmp/finans_batch_{i}_result.json") for i in range(1, 5)]

FROZEN_COLUMNS = [
    "hospital_code",
    "sut_code",
    "category",
    "source",           # generator_exact | generator_token | llm_found
    "confidence",
    "rationale",
    "verified_by",      # "generator" or "llm_subagent" or a human name
    "verified_date",
    "reviewed",         # TRUE only
]

LLM_PROMOTE_CONFIDENCE = 0.8


def load_llm_results() -> dict[str, dict]:
    """Merge the 4 subagent result files into one code→result dict."""
    merged: dict[str, dict] = {}
    for path in LLM_BATCHES:
        if not path.exists():
            print(f"WARN: {path} missing, skipping")
            continue
        with path.open(encoding="utf-8") as f:
            for r in json.load(f):
                merged[r["hospital_code"]] = r
    return merged


def main() -> None:
    llm = load_llm_results()
    print(f"Loaded {len(llm)} LLM results from {sum(1 for p in LLM_BATCHES if p.exists())} batch files")

    # Read the generator-produced review CSV
    with REVIEW_CSV.open(encoding="utf-8") as f:
        review_rows = list(csv.DictReader(f))
    print(f"Review CSV: {len(review_rows)} rows")

    # Fill llm_* columns + decide promotion
    promoted: list[dict[str, str]] = []
    n_gen_exact = n_gen_token = n_llm = n_ambig_kept = n_nomatch = 0

    for row in review_rows:
        code = row["hospital_code"]
        llm_r = llm.get(code)

        # Fill LLM columns
        if llm_r:
            row["llm_sut_code"] = llm_r.get("llm_sut_code", "") or ""
            row["llm_confidence"] = str(llm_r.get("llm_confidence", ""))
            row["llm_rationale"] = llm_r.get("llm_rationale", "") or ""

        # Promotion decision
        gen_method = row["generator_method"]
        gen_code = row["generator_sut_code"]
        gen_conf = float(row["generator_confidence"] or 0)

        if gen_method == "exact" and gen_code:
            promoted.append(_frozen_row(code, gen_code, row["category"],
                                        "generator_exact", 1.0, "exact name match"))
            row["reviewed"] = "TRUE"
            row["reviewer_decision"] = "accept_generator"
            row["reviewer_sut_code"] = gen_code
            n_gen_exact += 1
        elif gen_method == "token_prefix" and gen_code and gen_conf >= 0.5:
            promoted.append(_frozen_row(code, gen_code, row["category"],
                                        "generator_token", gen_conf,
                                        f"token match: {row['generator_sut_name']}"))
            row["reviewed"] = "TRUE"
            row["reviewer_decision"] = "accept_generator"
            row["reviewer_sut_code"] = gen_code
            n_gen_token += 1
        elif llm_r and llm_r.get("decision") == "FOUND" and float(llm_r.get("llm_confidence", 0)) >= LLM_PROMOTE_CONFIDENCE:
            sut = llm_r["llm_sut_code"]
            promoted.append(_frozen_row(code, sut, row["category"],
                                        "llm_found", float(llm_r["llm_confidence"]),
                                        llm_r.get("llm_rationale", "")))
            row["reviewed"] = "TRUE"
            row["reviewer_decision"] = "accept_llm"
            row["reviewer_sut_code"] = sut
            n_llm += 1
        elif llm_r and llm_r.get("decision") == "AMBIGUOUS":
            row["reviewed"] = "FALSE"
            row["reviewer_decision"] = "needs_human_disambiguation"
            row["reviewer_sut_code"] = llm_r.get("llm_sut_code", "")
            n_ambig_kept += 1
        else:
            row["reviewed"] = "FALSE"
            row["reviewer_decision"] = "no_match"
            n_nomatch += 1

    # Re-write review CSV with llm columns filled
    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=review_rows[0].keys())
        writer.writeheader()
        writer.writerows(review_rows)

    # Write frozen mapping (reviewed=TRUE only)
    FROZEN_CSV.parent.mkdir(parents=True, exist_ok=True)
    with FROZEN_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FROZEN_COLUMNS)
        writer.writeheader()
        writer.writerows(promoted)

    total = len(review_rows)
    print("\n=== Promotion summary ===")
    print(f"  generator_exact (promoted):      {n_gen_exact}")
    print(f"  generator_token (promoted):      {n_gen_token}")
    print(f"  llm_found (promoted):            {n_llm}")
    print(f"  ambiguous (kept for human):      {n_ambig_kept}")
    print(f"  no_match (unresolved):           {n_nomatch}")
    promoted_n = n_gen_exact + n_gen_token + n_llm
    print(f"\n  REVIEWED=TRUE: {promoted_n}/{total} ({100*promoted_n/total:.1f}%)")
    print(f"  REVIEWED=FALSE: {total-promoted_n}/{total} ({100*(total-promoted_n)/total:.1f}%)")
    print(f"\nWrote frozen mapping: {FROZEN_CSV.relative_to(REPO_ROOT)} ({len(promoted)} rows)")


def _frozen_row(
    code: str, sut: str, category: str, source: str, conf: float, rationale: str
) -> dict[str, str]:
    from datetime import date

    return {
        "hospital_code": code,
        "sut_code": sut,
        "category": category,
        "source": source,
        "confidence": f"{conf:.3f}",
        "rationale": rationale[:200],
        "verified_by": "generator" if source.startswith("generator") else "llm_subagent",
        "verified_date": str(date.today()),
        "reviewed": "TRUE",
    }


if __name__ == "__main__":
    main()
