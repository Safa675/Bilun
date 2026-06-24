#!/usr/bin/env python3
"""Classify §4.2.14.C Tier-C deferred clauses into encode buckets (L4.2 Phase C).

Reads the 549 Tier-C clause IDs from the §4.2.14.C manifest, pulls their actual
text from sut_clauses.parquet, and classifies each into:

  A — ENCODABLE_NOW: prescriber/report/duration/combo-prohibition/max-cycle
      (uses only existing drug_indication matcher fields).
  B — ENCODABLE_WITH_MODEL_EXT: biomarker-gated (HER-2+, CD20+, KRAS) or
      prior-therapy-gated (imatinib-resistant, 2nd-line).
  C — EMR_BLOCKED: ECOG, disease progression, lab/imaging thresholds, İSHAK
      score, MoH off-label case approval — genuinely needs clinical data.
  D — NON_ACTIONABLE: headings, amendments (mülga), superseded markers,
      drug-name fragments, very short tail phrases.

Output CSV feeds the Phase 2a/2b golden-file JSON compilation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DEFAULT_CLAUSES = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_DEFAULT_MANIFEST = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
)
_DEFAULT_OUT_CSV = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_oncology_tier_c_classification.csv"
_DEFAULT_OUT_SUMMARY = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_oncology_tier_c_summary.json"

# ── Bucket B: biomarker + prior-therapy signal patterns ──────────────────────

# Biomarker keywords (Bucket B-biomarker)
_BIOMARKER_KEYWORDS = [
    r"her\s*-?\s*2\s*(?:immünhistokimya|ihk|fish|cish|sish)",
    r"her2",
    r"cd\s*20\s*pozitif",
    r"cd\s*20\s*\+",
    r"kras",
    r"braf",
    r"egfr\s*mutasyon",
    r"alk\s*pozitif",
    r"philadelphia\s*kromozomu\s*pozitif",
    r"bcr\s*-?\s*abl",
    r"brca",
    r"hormon\s*reseptörü\s*pozitif",
    r"östrojen\s*reseptörü",
    r"achr\s*antikor",
    r"fish\s*/\s*cish",
    r"genotip\s*\d",
    r"jAK2",
    r"jak\s*2\s*V617F",
    r"17p\s*delesyon",
    r"5q\s*delesyon",
]
_BIOMARKER_RE = re.compile("|".join(_BIOMARKER_KEYWORDS), re.IGNORECASE)

# Prior-therapy keywords (Bucket B-prior-therapy)
_PRIOR_THERAPY_KEYWORDS = [
    r"önceki\s+tedavi",
    r"dirençli",
    r"intolere",
    r"birinci\s*basamak\s*tedavisinde",
    r"ikinci\s*basamak",
    r"üçüncü\s*basamak",
    r"ilk\s*sıra\s*tedavi",
    r"ikinci\s*sıra",
    r"önceden\s+.{0,20}kullan",
    r"transplantasyon\s+sonrasında",
    r"otolog\s+kök\s*hücre",
    r"nüks",
    r" kemorezistan",
    r"tedavi\s*sonrasında\s*nüks",
    r"idame\s*tedavisinde",
    r"öncesi\s*tedavi",
    r"line\s*tedavi",  # "1st/2nd line"
    r"sıra\s*tedaviden",
]
_PRIOR_THERAPY_RE = re.compile("|".join(_PRIOR_THERAPY_KEYWORDS), re.IGNORECASE)

# Bucket A signals (encodable now)
_COMBO_PROHIBITION_RE = re.compile(
    r"(?:ardışık|kombine|peş\s*peşe).{0,40}?(?:kullanılamaz|yasak|karşılanmaz)",
    re.IGNORECASE,
)
_MAX_CYCLE_RE = re.compile(
    r"(?:maksimum|en\s*fazla|toplam).{0,30}?(?:küre|doz|uygulama|kür)",
    re.IGNORECASE,
)
_PRESCRIBER_AUTHORITY_RE = re.compile(
    r"(?:tüm\s+uzman\s+hekimlerce|uzman\s+hekim(?:ler)?ce\s+reçete|"
    r"tıbbi\s+onkoloji|hematoloji\s+uzman|sağlık\s+kurulu\s+raporu)",
    re.IGNORECASE,
)
_REPORT_DURATION_RE = re.compile(r"\d+\s*ay\s*süreli", re.IGNORECASE)


def _classify_bucket(record: dict) -> str:
    """Classify a Tier-C clause into A/B/C/D by actual text + structural markers."""
    text = str(record.get("text_tr") or "")
    lower = text.lower()

    # Bucket D — non-actionable structural fragments
    is_heading = bool(record.get("is_heading"))
    is_amendment = bool(record.get("is_amendment"))
    is_superseded = bool(record.get("is_superseded_marker"))
    char_count = int(record.get("char_count") or len(text))

    if is_heading or is_amendment or is_superseded:
        return "D"
    if char_count < 50:
        return "D"
    # Drug-name-only fragments: "b) Alemtuzumab;" / "i) Sunitinib:"
    if re.fullmatch(r"\s*[a-zçşğüöı)]{1,3}\)?\s*[A-ZÇŞĞÜÖİ][\w\-()]{2,40}\s*[;:.]?\s*", text):
        return "D"

    # Bucket B — biomarker or prior-therapy gated (check BEFORE C because biomarker
    # clauses may also mention "metastatik"/clinical staging which looks EMR-ish).
    has_biomarker = bool(_BIOMARKER_RE.search(text))
    has_prior_therapy = bool(_PRIOR_THERAPY_RE.search(text))
    if has_biomarker or has_prior_therapy:
        return "B"

    # Bucket C — genuinely EMR-dependent. Strict signals only: clinical scores,
    # response/progression over time, lab thresholds, MoH case approval.
    # NOTE: "metastatik", "stadium", "evre" alone are NOT EMR signals — they're
    # cancer staging terminology usable in deterministic ICD-10 mapping.
    strict_emr_signals = [
        r"ecog",
        r"performans\s*statüsü",
        r"performans\s*skoru?",
        r"progresyon",
        r"hastalık\s*ilerlemesi",
        r"cevapsızlık",
        r"yanıt\s*değerlendir",
        r"tedaviye\s*yanıt",
        r"klinik\s+ve/?veya\s+radyolojik",
        r"ishak",
        r"fibroz\s*skoru",
        r"düzeltilmiş\s*kalsiyum",
        r"hematokrit",
        r"dipps",
        r"edss",
        r"endikasyon\s*dışı\s*onay",
        r"bilgilendirilmiş\s*hasta\s*olur",
        r"meningokok",
        r"skorlama\s*sistemi",
        r"minör\s*yanıt",
        r"kısmi\s*yanıt",
        r"\d\s*üncü\s*kür\s*sonunda",
        r"altıncı\s*kür",
        r"6\s*ıncı\s*kür",
    ]
    emr_re = re.compile("|".join(strict_emr_signals), re.IGNORECASE)
    if emr_re.search(text):
        return "C"

    # Bucket A — encodable now (existing matcher fields)
    if (
        _COMBO_PROHIBITION_RE.search(text)
        or _MAX_CYCLE_RE.search(text)
        or _PRESCRIBER_AUTHORITY_RE.search(text)
        or _REPORT_DURATION_RE.search(text)
    ):
        return "A"

    # Default: substantive content with no recognized deterministic signal →
    # EMR-blocked (safer to defer than mis-encode).
    if char_count > 100:
        return "C"
    return "D"


def build_classification(
    clauses_path: Path, manifest_path: Path
) -> tuple[pl.DataFrame, dict]:
    """Classify all Tier-C clauses; return (dataframe, summary)."""
    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    tier_c_ids = set(manifest.get("tier_c_deferred_clause_ids") or [])

    clauses = pl.read_parquet(clauses_path)
    tc = clauses.filter(pl.col("clause_id").is_in(list(tier_c_ids))).sort("paragraph_index")

    rows: list[dict] = []
    for record in tc.iter_rows(named=True):
        bucket = _classify_bucket(record)
        text = str(record.get("text_tr") or "")
        rows.append(
            {
                "clause_id": record.get("clause_id"),
                "section_id": record.get("section_id"),
                "bucket": bucket,
                "is_heading": record.get("is_heading"),
                "is_amendment": record.get("is_amendment"),
                "is_superseded": record.get("is_superseded_marker"),
                "char_count": record.get("char_count"),
                "text_excerpt": text[:300],
            }
        )

    df = pl.DataFrame(
        rows,
        schema={
            "clause_id": pl.Utf8,
            "section_id": pl.Utf8,
            "bucket": pl.Utf8,
            "is_heading": pl.Boolean,
            "is_amendment": pl.Boolean,
            "is_superseded": pl.Boolean,
            "char_count": pl.Int64,
            "text_excerpt": pl.Utf8,
        },
    )

    bucket_counts = Counter(r["bucket"] for r in rows)
    summary = {
        "tier_c_total": len(tier_c_ids),
        "classified_rows": len(rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "note": (
            "§4.2.14.C Tier-C classification. A=encodable now, B=model-ext (biomarker/"
            "prior-therapy), C=EMR-blocked (ECOG/progresyon/lab), D=non-actionable "
            "(heading/amendment/fragment). Classification by actual clause text, not "
            "manifest theme labels (which are unreliable)."
        ),
    }
    return df, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_DEFAULT_CLAUSES)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--out-csv", type=Path, default=_DEFAULT_OUT_CSV)
    parser.add_argument("--out-summary", type=Path, default=_DEFAULT_OUT_SUMMARY)
    args = parser.parse_args()

    df, summary = build_classification(args.clauses, args.manifest)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out_csv)
    args.out_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Wrote {df.height} classified clauses to {args.out_csv}")
    print(f"Summary: {args.out_summary}")
    print(f"Bucket counts: {summary['bucket_counts']}")


if __name__ == "__main__":
    main()
