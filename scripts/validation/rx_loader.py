"""Load ILAY prescriptions and join to encounter diagnoses.

Produces a clean DataFrame of drug-diagnosis pairs for the drugs that overlap
with Bilun's drug_indication rule corpus (68 tokens, ~44K prescriptions).

Output schema:
  drug_name        — raw ILAY brand string (e.g. "PLAVIX")
  primary_icd10    — the encounter's TANIKODU (cleaned)
  department       — SERVISADI
  patient_id       — HASTA_ID
  episode_id       — RF_EPISODE
  prescription_date — RECETE_TARIH
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import polars as pl

# ──────────────────────────────────────────────────────────────────────────
# Paths — ILAY data stays in ILAY-Health, read by absolute path
# ──────────────────────────────────────────────────────────────────────────

ILAY_DATA_DIR = Path("/home/safa/Documents/ILAY-Health/data/clean")
RECETE_PATH = ILAY_DATA_DIR / "recete_clean.parquet"
ANADATA_PATH = ILAY_DATA_DIR / "anadata_clean.parquet"

BILUN_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = BILUN_ROOT / "data/gazette/prose_rules/drug_indication_prose.json"
ANTI_VEGF_PATH = BILUN_ROOT / "data/gazette/prose_rules/anti_vegf_prose.json"


# ──────────────────────────────────────────────────────────────────────────
# Rule-token extraction — which drug names does the corpus reference?
# ──────────────────────────────────────────────────────────────────────────


def _normalize_tr(text: str) -> str:
    """NFKD fold matching the engine's _normalize_tr (drug_indication.py:461)."""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold()


def load_rule_drug_tokens() -> set[str]:
    """Return the set of drug-name tokens referenced by any drug_indication rule.

    These are INN/brand tokens like 'plavix', 'amoksisilin', 'atorvastatin 40 mg ve üzeri'.
    The engine matches them via word-boundary regex against the claim's drug_name string.
    """
    tokens: set[str] = set()
    for path in (RULES_PATH, ANTI_VEGF_PATH):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("rules", []):
            for name in rule.get("drug_names", []):
                name = str(name).strip().lower()
                if name:
                    tokens.add(name)
    return tokens


# ──────────────────────────────────────────────────────────────────────────
# Label cleaning — mirror the cleaning logic from the baseline investigation
# ──────────────────────────────────────────────────────────────────────────

_ICD10_RE = re.compile(r"^[A-Z][0-9]{2}(\.[0-9A-TV-Z]{1,4})?$")


def _clean_icd10(code: str | None) -> str | None:
    """Normalize an ICD-10 code. Returns None for junk."""
    if code is None:
        return None
    c = str(code).strip().rstrip(".?")
    if not c or c.lower() in ("nan", ""):
        return None
    if "-" in c:  # range code like C00-C14
        return None
    parts = c.split(".")
    if len(parts) > 2:  # three-part Turkish sub-code like M84.8.7.2
        c = parts[0] + "." + parts[1]
    c = c.upper()
    if not _ICD10_RE.match(c):
        return None
    return c


# ──────────────────────────────────────────────────────────────────────────
# Main loader
# ──────────────────────────────────────────────────────────────────────────


def load_drug_diagnosis_pairs() -> pl.DataFrame:
    """Load ILAY prescriptions joined to diagnoses, filtered to rule-relevant drugs.

    Returns a DataFrame with columns:
      drug_name, primary_icd10, department, patient_id, episode_id, prescription_date
    """
    # 1. Load rule tokens
    rule_tokens = load_rule_drug_tokens()
    rule_tokens_norm = {_normalize_tr(t) for t in rule_tokens}
    print(f"Rule drug tokens: {len(rule_tokens):,}")

    # 2. Pre-compile a single regex alternation for fast matching
    #    Sort by length descending so longer phrases match first
    sorted_tokens = sorted(rule_tokens_norm, key=len, reverse=True)
    # Escape each token; the engine uses (?<![\w)])TOKEN(?![\w(])
    alternation = "|".join(re.escape(t) for t in sorted_tokens if t)
    token_pattern = re.compile(r"(?<![\w)])(?:" + alternation + r")(?![\w(])")

    # 3. Load prescriptions
    print("Loading ILAY prescriptions...")
    recete = pl.read_parquet(RECETE_PATH)
    print(f"  Total prescriptions: {recete.height:,}")

    # Filter out null drug names
    recete = recete.filter(
        pl.col("ilac_adi").is_not_null()
        & (pl.col("ilac_adi") != "nan")
        & (pl.col("ilac_adi").str.strip_chars() != "")
    )
    print(f"  With valid drug name: {recete.height:,}")

    # 4. Match drugs against rule tokens (Python-side, one pass)
    print("Matching drugs against rule tokens...")
    rx_names = recete["ilac_adi"].to_list()
    rx_norm = [_normalize_tr(n) for n in rx_names]
    matched_mask = [bool(token_pattern.search(n)) for n in rx_norm]
    matched_drugs = set(
        rx_names[i] for i in range(len(rx_names)) if matched_mask[i]
    )
    print(f"  ILAY drugs matching ≥1 rule token: {len(matched_drugs):,}")

    # 5. Filter prescriptions to matched drugs
    recete_matched = recete.filter(pl.col("ilac_adi").is_in(list(matched_drugs)))
    print(f"  Matched prescriptions: {recete_matched.height:,}")

    # 6. Load encounter diagnoses (one primary dx per episode)
    print("Loading encounter diagnoses...")
    ana = pl.read_parquet(ANADATA_PATH, columns=["SQ_EPISODE", "TANIKODU", "SERVISADI", "HASTA_ID"])
    # Take the first diagnosis per episode (any row — they share the episode's dx context)
    ep_dx = ana.group_by("SQ_EPISODE").agg(
        pl.col("TANIKODU").first().alias("primary_icd10_raw"),
        pl.col("SERVISADI").first().alias("department"),
    )
    print(f"  Episodes with diagnosis: {ep_dx.height:,}")

    # 7. Join prescriptions to diagnoses via episode ID
    print("Joining prescriptions to diagnoses...")
    joined = recete_matched.join(
        ep_dx,
        left_on="RF_EPISODE",
        right_on="SQ_EPISODE",
        how="inner",
    )
    print(f"  Joined rows: {joined.height:,}")

    # 8. Clean ICD-10 labels and drop unparseable
    joined = joined.with_columns(
        pl.col("primary_icd10_raw")
        .map_elements(_clean_icd10, return_dtype=pl.String)
        .alias("primary_icd10")
    ).filter(pl.col("primary_icd10").is_not_null())
    print(f"  After ICD-10 cleaning: {joined.height:,}")

    # 9. Select final columns
    result = joined.select(
        [
            pl.col("ilac_adi").alias("drug_name"),
            "primary_icd10",
            "department",
            pl.col("HASTA_ID").alias("patient_id"),
            pl.col("RF_EPISODE").alias("episode_id"),
            pl.col("RECETE_TARIH").alias("prescription_date"),
        ]
    )

    return result


if __name__ == "__main__":
    df = load_drug_diagnosis_pairs()
    print("\n=== FINAL DATASET ===")
    print(f"Rows: {df.height:,}")
    print(f"Unique drugs: {df['drug_name'].n_unique():,}")
    print(f"Unique diagnoses: {df['primary_icd10'].n_unique():,}")
    print("\nTop 15 drugs by prescription count:")
    print(df.group_by("drug_name").len().sort("len", descending=True).head(15))


# ──────────────────────────────────────────────────────────────────────────
# Specialty pairs — for option B (specialty scope validation)
# ──────────────────────────────────────────────────────────────────────────


def load_specialty_rule_drug_tokens() -> set[str]:
    """Drug tokens referenced by rules that ALSO have prescriber_specialties.

    Returns the set of drug-name tokens from rules where
    ``rule.get('prescriber_specialties')`` is non-empty. These are the only
    drug tokens relevant to the specialty-validation harness.
    """
    tokens: set[str] = set()
    for path in (RULES_PATH, ANTI_VEGF_PATH):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("rules", []):
            if not rule.get("prescriber_specialties"):
                continue
            for name in rule.get("drug_names", []):
                name = str(name).strip().lower()
                if name:
                    tokens.add(name)
    return tokens


def load_specialty_pairs() -> pl.DataFrame:
    """Load ILAY prescriptions joined to departments, filtered to specialty rules.

    Mirrors ``load_drug_diagnosis_pairs`` but:
      - Uses the specialty-rule drug-token set (39 tokens vs 856)
      - Joins to encounter SERVISADI (department) as prescriber_specialty
      - Also carries TANIKODU for rules that gate on both specialty AND diagnosis

    Returns a DataFrame with columns:
      drug_name, primary_icd10, prescriber_specialty, patient_id, episode_id,
      prescription_date
    """
    # 1. Load specialty-rule tokens
    rule_tokens = load_specialty_rule_drug_tokens()
    rule_tokens_norm = {_normalize_tr(t) for t in rule_tokens}
    print(f"Specialty-rule drug tokens: {len(rule_tokens):,}")

    # 2. Pre-compile matching regex
    sorted_tokens = sorted(rule_tokens_norm, key=len, reverse=True)
    alternation = "|".join(re.escape(t) for t in sorted_tokens if t)
    token_pattern = re.compile(r"(?<![\w)])(?:" + alternation + r")(?![\w(])")

    # 3. Load prescriptions
    print("Loading ILAY prescriptions...")
    recete = pl.read_parquet(RECETE_PATH)
    print(f"  Total prescriptions: {recete.height:,}")

    recete = recete.filter(
        pl.col("ilac_adi").is_not_null()
        & (pl.col("ilac_adi") != "nan")
        & (pl.col("ilac_adi").str.strip_chars() != "")
    )
    print(f"  With valid drug name: {recete.height:,}")

    # 4. Match against specialty-rule tokens
    print("Matching drugs against specialty-rule tokens...")
    rx_names = recete["ilac_adi"].unique().to_list()
    rx_norm = [_normalize_tr(n) for n in rx_names]
    matched_drugs = [
        name for name, norm in zip(rx_names, rx_norm) if token_pattern.search(norm)
    ]
    print(f"  ILAY drugs matching ≥1 specialty-rule token: {len(matched_drugs):,}")

    recete_matched = recete.filter(pl.col("ilac_adi").is_in(matched_drugs))
    print(f"  Matched prescriptions: {recete_matched.height:,}")

    # 5. Load encounter department + diagnosis
    print("Loading encounter departments...")
    ana = pl.read_parquet(
        ANADATA_PATH, columns=["SQ_EPISODE", "TANIKODU", "SERVISADI", "HASTA_ID"]
    )
    ep_info = ana.group_by("SQ_EPISODE").agg(
        pl.col("TANIKODU").first().alias("primary_icd10_raw"),
        pl.col("SERVISADI").first().alias("prescriber_specialty"),
        pl.col("HASTA_ID").first().alias("patient_id"),
    )
    print(f"  Episodes with department: {ep_info.height:,}")

    # 6. Join prescriptions to encounters
    print("Joining prescriptions to departments...")
    joined = recete_matched.join(
        ep_info,
        left_on="RF_EPISODE",
        right_on="SQ_EPISODE",
        how="inner",
    )
    print(f"  Joined rows: {joined.height:,}")

    # 7. Drop rows with no department (cannot validate specialty without it)
    before = joined.height
    joined = joined.filter(
        pl.col("prescriber_specialty").is_not_null()
        & (pl.col("prescriber_specialty").str.strip_chars() != "")
        & (pl.col("prescriber_specialty") != "nan")
    )
    print(f"  After dropping null departments: {joined.height:,} (dropped {before - joined.height:,})")

    # 8. Clean ICD-10 — keep nulls (some specialty rules don't gate on dx)
    joined = joined.with_columns(
        pl.col("primary_icd10_raw")
        .map_elements(_clean_icd10, return_dtype=pl.String)
        .alias("primary_icd10")
    )

    # 9. Select final columns
    result = joined.select(
        [
            pl.col("ilac_adi").alias("drug_name"),
            "primary_icd10",
            "prescriber_specialty",
            "patient_id",
            pl.col("RF_EPISODE").alias("episode_id"),
            pl.col("RECETE_TARIH").alias("prescription_date"),
        ]
    )

    return result
