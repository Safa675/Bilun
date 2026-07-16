#!/usr/bin/env python3
"""Run the hospital-code → SUT resolver over the finans LAB+PROCEDURE codes.

Phase 2 driver (subtasks 2.3–2.6). Produces:

  1. ``data/coding/crosswalk_review.csv`` — every LAB+PROCEDURE code with its
     generator result; the no-match / low-confidence tail is the queue for
     LLM-assisted resolution. ``reviewed=FALSE`` by default.
  2. A console summary of the exact / token / no-match split.

The LLM pass itself is run separately via subagents (see plan 2.3) — this
script prepares the review queue, it does not call any LLM. Reviewed rows
are promoted into ``data/coding/hospital_to_sut.csv`` by a human.

Scope: LAB + PROCEDURE only (~146 codes, ~27% of finans rows). DRUG needs
an external brand→barcode list; MATERIAL is skipped (1:many ambiguity).

Run:
    python scripts/analysis/run_finans_coder.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.bilun.domain.coding import CategoryHint, resolve_code  # noqa: E402
from src.bilun.domain.coding.code_resolver import clear_resolver_cache  # noqa: E402

FINANS_CLEAN = REPO_ROOT / "data" / "finans_clean.parquet"
REVIEW_CSV = REPO_ROOT / "data" / "coding" / "crosswalk_review.csv"

REVIEW_COLUMNS = [
    "hospital_code",
    "description",
    "category",
    "generator_method",
    "generator_sut_code",
    "generator_confidence",
    "generator_sut_name",
    "top5_candidates",
    "needs_llm",          # TRUE when generator didn't clear 0.5
    "llm_sut_code",       # filled by the LLM pass (subagent)
    "llm_confidence",
    "llm_rationale",
    "reviewer_decision",  # accept / reject / override (filled by human)
    "reviewer_sut_code",
    "reviewed",           # FALSE until a human reviews
]


def classify_category(desc: str) -> str:
    """Classify a finans line as LAB / PROCEDURE / DRUG / MATERIAL / UNCLEAR.

    Mirrors the probe classifier. Only LAB and PROCEDURE are in Phase 2 scope;
    DRUG/MATERIAL/UNCLEAR are excluded from the coder run.
    """
    d = str(desc or "").lower()
    if re.search(
        r"\b\d+\s*(mg|mcg|gr|iu)\b|tablet|ampul|flakon|kapsül|kapsul|film kaplı|"
        r"liyofilize|şurup|surup|merhem|krem|sprey|damla|inhaler|inhalasyon|"
        r"enjeksiyon|infüzyon|infuzyon|süspansiyon|suspansiyon|çözelti|cozelti|"
        r"solüsyon|solusyon|pomad",
        d,
    ):
        return "DRUG"
    if re.search(
        r"ref:|medtronic|covidien|boston|sorin|teleflex|stryker|pfm|nextech|"
        r"alpheta|seti$|set\b|sistem|sonda|kateter|kanül|kanul|trokar|kelepçe|"
        r"kelepce|vida|plak|mesh|yama|filtre|örgü|torba|poşet|süngeri|sungeri|"
        r"öreü|ortuz|tüp\b|tup\b|tel\b|kılavuz|kilavuz|bandı|örtü|ortu\b|soket|"
        r"firman|branül|branul",
        d,
    ):
        return "MATERIAL"
    if re.search(
        r"tam kan|sayımı|sayimi|hemogram|fosfataz|aminotransferase|aminotransferaz|"
        r"transaminaz|reaktif protein|crp|glukoz|glikoz|kolesterol|trigliserid|tsh|"
        r"kreatinin|üre|ure|albümin|albumin|sodyum|potasyum|kalsiyum|demir|ferritin|"
        r"hemoglobin|lenfosit|nötrofil|notrofil|trombosit|eritrosit|lokos|mcv|rdw|"
        r"mpv|bilirubin|ast\b|alt\b|tiroid|insülin|insulin|hba1c|sedim|koagülasyon|"
        r"inr|ptz|türbidite|immünhistokimyasal|histokimyasal|sitoloji|patoloji|"
        r"boyama|panel|tetkik|testi|analizi|kültür|kultur|antijen|antikor",
        d,
    ):
        return "LAB"
    if re.search(
        r"muayene|konsültasyon|konsultasyon|manevra|biyopsi|cerrahi|operasyon|"
        r"anestezi|revizyon|eksplorasyon|drenaj|debridman|insizyon|rezeksiyon|"
        r"endoskop|kolonoskop|gastroskop|poliklinik|vizit|kemoterapi|diyaliz|"
        r"radyoterapi|brakiterapi",
        d,
    ):
        return "PROCEDURE"
    return "UNCLEAR"


def main() -> None:
    clear_resolver_cache()
    finans = pl.read_parquet(FINANS_CLEAN)
    codes = (
        finans.group_by(["HIZMETKODU", "HIZMET_TANIMI"])
        .agg(n=pl.len())
        .sort("n", descending=True)
    )
    codes = codes.with_columns(
        pl.col("HIZMET_TANIMI").map_elements(classify_category, return_dtype=pl.Utf8).alias("cat")
    )
    in_scope = codes.filter(pl.col("cat").is_in(["LAB", "PROCEDURE"]))
    print(f"In scope (LAB+PROCEDURE): {in_scope.height} codes, {in_scope['n'].sum()} rows")

    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    method_counts = {"exact": 0, "token_prefix": 0, "no_match": 0, "llm_pending": 0}
    rows_out: list[dict[str, object]] = []

    for r in in_scope.iter_rows(named=True):
        code = r["HIZMETKODU"]
        desc = r["HIZMET_TANIMI"] or ""
        cat = r["cat"]
        res = resolve_code(code, desc, CategoryHint(kind=cat))

        needs_llm = res.sut_code is None or res.confidence < 0.5
        method = res.method
        # bucket for summary
        if method == "exact":
            method_counts["exact"] += 1
        elif method == "token_prefix":
            method_counts["token_prefix"] += 1
        elif method == "no_match":
            method_counts["no_match"] += 1
        elif method == "llm_pending":
            method_counts["llm_pending"] += 1

        top5 = "; ".join(
            f"{c['code']} ({c['confidence']:.2f}, {c.get('why','')})"
            for c in res.candidates[:5]
        )
        rows_out.append(
            {
                "hospital_code": code,
                "description": desc,
                "category": cat,
                "generator_method": method,
                "generator_sut_code": res.sut_code or "",
                "generator_confidence": round(res.confidence, 3),
                "generator_sut_name": res.sut_name or "",
                "top5_candidates": top5,
                "needs_llm": str(needs_llm),
                "llm_sut_code": "",
                "llm_confidence": "",
                "llm_rationale": "",
                "reviewer_decision": "",
                "reviewer_sut_code": "",
                "reviewed": "FALSE",
            }
        )

    with REVIEW_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows_out)

    resolved = method_counts["exact"] + method_counts["token_prefix"]
    needs = method_counts["no_match"] + method_counts["llm_pending"]
    print("\n=== Generator split ===")
    for m, c in method_counts.items():
        print(f"  {m:14s} {c:>4}  ({100*c/in_scope.height:.1f}%)")
    print(f"\nResolved by generator (≥0.5 conf): {resolved}/{in_scope.height} "
          f"({100*resolved/in_scope.height:.1f}%)")
    print(f"Needs LLM pass:                    {needs}/{in_scope.height} "
          f"({100*needs/in_scope.height:.1f}%)")
    print(f"\nWrote review queue: {REVIEW_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
