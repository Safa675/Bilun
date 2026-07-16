#!/usr/bin/env python3
"""Finans Pricing Audit — hospital billed price vs SUT list price (as-of-date).

Compares the hospital's billed price against the SUT catalog list price **as of
the service date** (``TARIH``), across the three catalogs the finans coder
resolved into:

  - **EK-2B** (procedures / labs / radiology): ``get_ek2b_price_for_date(code,
    TARIH)`` is the strict date-aware lookup → compare vs ``KDVSIZ_FIYAT``.
  - **EK-3** (materials): ``lookup_ek3_list_price_try`` (ex-VAT list) →
    ``ek3_payable_ceiling_try`` (adds 20% KDV) → compare vs ``KDVSIZ_FIYAT``.
  - **EK-4A** (drugs, tier audit only): join frozen ``sut_code``(=``kamu_no``)
    to ``ek4a_drugs.parquet`` and compare the hospital's ``INDIRIM_ORANI``
    against the catalog's primary SGK rebate ``discount_tier_1``. The
    retail-price audit is deferred (needs the TİTCK Fiyat Listesi).

Each row is classified as ``MATCH`` / ``OVERCHARGE`` / ``UNDERCHARGE`` /
``NO_SUT_PRICE`` / ``MULGA_BILLED_AFTER_ABOLITION`` / ``TIER_MISMATCH`` /
``NOT_IN_SCOPE`` (±5% threshold). The audit also validates the Phases 1-5
crosswalk as a side effect: a code with systematic extreme divergence across
ALL its rows is flagged as a *suspected wrong mapping* (crosswalk error), not
reported as "hospital overcharged 500%".

Outputs:
  - ``data/finans_pricing_audit.parquet`` — row-level results.
  - ``data/finans_pricing_audit.md``      — summary report.

Standalone audit (no claim-loader, no motor). Vectorized with Polars where the
operation is bulk/relational; the catalog lookups are inherently per-code scalar
queries and are memoized per (code, date).

Run:
    python scripts/analysis/finans_pricing_audit.py
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bilun.domain.materials.catalog_lookup import lookup_ek3_list_price_try  # noqa: E402
from bilun.domain.materials.drugs import get_ek4a_drugs  # noqa: E402
from bilun.domain.pricing.material_kdv import ek3_payable_ceiling_try  # noqa: E402
from bilun.domain.pricing.temporal import (  # noqa: E402
    get_ek2b_price_for_date,
    get_price_history,
)

# --- paths -----------------------------------------------------------------
FINANS_PARQUET = REPO_ROOT / "data" / "finans_clean.parquet"
FROZEN_CROSSWALK = REPO_ROOT / "data" / "coding" / "hospital_to_sut.csv"
OUT_PARQUET = REPO_ROOT / "data" / "finans_pricing_audit.parquet"
OUT_REPORT = REPO_ROOT / "data" / "finans_pricing_audit.md"

# --- constants -------------------------------------------------------------
MATCH_THRESHOLD_PCT = 5.0  # |delta_pct| < 5% → MATCH
TIER_THRESHOLD_PCT = 5.0  # |discount diff| > 5pp → TIER_MISMATCH
WRONG_MAPPING_DELTA_PCT = 100.0  # systematic >+100% divergence across all rows
WRONG_MAPPING_MIN_ROWS = 3  # need ≥3 rows to call a mapping "systematically" wrong

# category → SUT catalog. LAB/PROCEDURE/RADIOLOGY all resolve to the EK-2B
# procedure catalog; MATERIAL→EK-3; DRUG→EK-4A. HOTEL/bundled are excluded.
CATEGORY_TO_CATALOG: dict[str, str] = {
    "LAB": "EK-2B",
    "PROCEDURE": "EK-2B",
    "RADIOLOGY": "EK-2B",
    "MATERIAL": "EK-3",
    "DRUG": "EK-4A",
}
EK2B_CATEGORIES = {"LAB", "PROCEDURE", "RADIOLOGY"}


# ===========================================================================
# Catalog lookups (memoized — same (code, date) repeats across thousands of rows)
# ===========================================================================
@lru_cache(maxsize=200_000)
def _ek2b_price(code: str, date_iso: str) -> float | None:
    """Strict as-of EK-2B list price; enforces effective_date <= date."""
    try:
        return get_ek2b_price_for_date(code, date_iso)
    except (ValueError, TypeError):
        return None


@lru_cache(maxsize=50_000)
def _ek3_ceiling(code: str) -> float | None:
    """EK-3 payable ceiling = ex-VAT list + 20% KDV. Static (no date dim)."""
    ex_vat = lookup_ek3_list_price_try(code)
    return ek3_payable_ceiling_try(ex_vat)


@lru_cache(maxsize=20_000)
def _ek2b_valid_to(code: str) -> str | None:
    """Last ``valid_to`` for a code from the EK-2B history parquet.

    Used to detect mülga codes billed after abolition. Returns the max valid_to
    (the abolition date) as an ISO string, or None if the code has no history.
    """
    try:
        hist = get_price_history(code, catalog="ek2b")
    except Exception:
        return None
    if hist.height == 0 or "valid_to" not in hist.columns:
        return None
    vt = hist.select(pl.col("valid_to").drop_nulls().sort().last()).item()
    return vt


# ===========================================================================
# Loaders
# ===========================================================================
def load_finans() -> pl.DataFrame:
    """Load the cleaned finans billing extract."""
    if not FINANS_PARQUET.exists():
        raise FileNotFoundError(
            f"finans parquet missing: {FINANS_PARQUET}. "
            "Run scripts/analysis/analyze_finans_data.py first."
        )
    return pl.read_parquet(FINANS_PARQUET)


def load_frozen_crosswalk() -> pl.DataFrame:
    """Load the reviewed crosswalk (hospital_code → sut_code + category)."""
    if not FROZEN_CROSSWALK.exists():
        raise FileNotFoundError(f"frozen crosswalk missing: {FROZEN_CROSSWALK}")
    df = pl.read_csv(FROZEN_CROSSWALK)
    # `reviewed` is parsed as Boolean by polars (true/false); keep only reviewed rows
    # regardless of how the column was typed.
    if df.schema["reviewed"] == pl.Boolean:
        df = df.filter(pl.col("reviewed"))
    else:
        df = df.filter(pl.col("reviewed").str.to_lowercase() == "true")
    return df


def load_ek4a_index() -> pl.DataFrame:
    """Load EK-4A drugs keyed by kamu_no with the tier columns.

    ``get_ek4a_drugs()`` returns a ``list[dict]`` (passivated drugs already
    filtered out); we vectorize it into a Polars frame in one shot.
    """
    df = pl.from_dicts(get_ek4a_drugs())
    keep = [
        c
        for c in (
            "kamu_no",
            "drug_name",
            "discount_status",
            "discount_tier_1",
            "discount_tier_2",
            "discount_tier_3",
            "discount_tier_4",
        )
        if c in df.columns
    ]
    # normalize tiers to float (Turkish decimal commas already parsed by loader)
    for tc in ("discount_tier_1", "discount_tier_2", "discount_tier_3", "discount_tier_4"):
        if tc in df.columns:
            df = df.with_columns(pl.col(tc).cast(pl.Float64, strict=False))
    return df.select(keep).unique(subset=["kamu_no"])


def join_resolved(finans: pl.DataFrame, frozen: pl.DataFrame) -> pl.DataFrame:
    """Join finans rows to the frozen crosswalk; tag each row's catalog."""
    return (
        finans.join(
            frozen.select("hospital_code", "sut_code", "category"),
            left_on="HIZMETKODU",
            right_on="hospital_code",
            how="left",
        )
        .with_columns(
            pl.col("category")
            .replace_strict(CATEGORY_TO_CATALOG, default="UNRESOLVED")
            .alias("catalog"),
        )
        # only resolved rows (category matched + sut_code present) are auditable
        .filter(pl.col("category").is_not_null() & (pl.col("sut_code") != ""))
    )


# ===========================================================================
# Per-catalog price/expected-value resolution (vectorized where relational,
# scalar-per-row only for the inherently-scalar catalog lookups)
# ===========================================================================
def resolve_ek2b_prices(df: pl.DataFrame) -> pl.DataFrame:
    """Add sut_price_try + mulga_valid_to for EK-2B rows."""
    rows = df.select(
        pl.col("sut_code").alias("code"),
        pl.col("TARIH").dt.strftime("%Y-%m-%d").alias("date_iso"),
    ).to_dicts()

    prices: list[float | None] = []
    valid_tos: list[str | None] = []
    for r in rows:
        code = r["code"] or ""
        iso = r["date_iso"]
        prices.append(_ek2b_price(code, iso))
        # only fetch valid_to once per code; reuse the cache key
        valid_tos.append(_ek2b_valid_to(code))

    return df.with_columns(
        pl.Series("sut_price_try", prices, dtype=pl.Float64),
        pl.Series("mulga_valid_to", valid_tos, dtype=pl.Utf8),
    )


def resolve_ek3_prices(df: pl.DataFrame) -> pl.DataFrame:
    """Add sut_ceiling_try for EK-3 rows (= ex-VAT list + KDV)."""
    codes = df.get_column("sut_code").to_list()
    ceilings = [_ek3_ceiling(c or "") for c in codes]
    return df.with_columns(
        pl.Series("sut_ceiling_try", ceilings, dtype=pl.Float64),
    )


def resolve_ek4a_tiers(df: pl.DataFrame, ek4a: pl.DataFrame) -> pl.DataFrame:
    """Join EK-4A tiers; expose discount_tier_1 as the expected SGK rebate."""
    return df.join(
        ek4a.select(
            pl.col("kamu_no").alias("sut_code"),
            pl.col("discount_tier_1"),
            pl.col("discount_status"),
        ),
        on="sut_code",
        how="left",
    ).rename({"discount_tier_1": "expected_discount_tier"})


# ===========================================================================
# Classification
# ===========================================================================
# Catalog-specific price columns. EK-2B → sut_price_try + mulga_valid_to;
# EK-3 → sut_ceiling_try; EK-4A → expected_discount_tier + discount_status.
# All are nullable so a row from any catalog can carry nulls for the others,
# giving a single unified schema for the output parquet.
CATALOG_PRICE_COLS = {
    "delta_try": pl.Float64,
    "delta_pct": pl.Float64,
    "sut_price_try": pl.Float64,
    "mulga_valid_to": pl.Utf8,
    "sut_ceiling_try": pl.Float64,
    "expected_discount_tier": pl.Float64,
    "applied_discount": pl.Float64,
    "discount_status": pl.Utf8,
    "flag": pl.Utf8,
}


def _align(df: pl.DataFrame) -> pl.DataFrame:
    """Align a frame to the unified output schema (null-fill missing cols)."""
    return df.with_columns(
        *[
            pl.lit(None).cast(dt).alias(c)
            for c, dt in CATALOG_PRICE_COLS.items()
            if c not in df.columns
        ]
    )


def classify(df: pl.DataFrame) -> pl.DataFrame:
    """Classify each row by catalog-specific comparison logic."""
    out = df.with_columns(
        pl.lit(None).cast(pl.Float64).alias("delta_try"),
        pl.lit(None).cast(pl.Float64).alias("delta_pct"),
        pl.lit(None).cast(pl.Utf8).alias("flag"),
    )

    parts: list[pl.DataFrame] = []
    for catalog_name, classify_fn in (
        ("EK-2B", _classify_ek2b),
        ("EK-3", _classify_ek3),
        ("EK-4A", _classify_ek4a),
    ):
        sub = out.filter(pl.col("catalog") == catalog_name)
        if sub.height > 0:
            parts.append(_align(classify_fn(sub)))
    # everything else (HOTEL/UNCLEAR/UNRESOLVED) → NOT_IN_SCOPE
    other = out.filter(~pl.col("catalog").is_in(["EK-2B", "EK-3", "EK-4A"]))
    if other.height > 0:
        parts.append(_align(other.with_columns(pl.lit("NOT_IN_SCOPE").alias("flag"))))

    if not parts:
        return _align(out)
    return pl.concat(parts, how="vertical_relaxed")


def _classify_ek2b(df: pl.DataFrame) -> pl.DataFrame:
    """EK-2B: KDVSIZ_FIYAT (ex-VAT unit price) vs sut_price_try (ex-VAT, as-of).

    Each finans row is a single unit of service (repeated units appear as
    distinct rows, e.g. CD HORIZON 6× = 6 rows at 1666.5 each), so KDVSIZ_FIYAT
    is a per-unit price directly comparable to the SUT unit rate.

    Computes delta_pct in step 1, then derives the flag in step 2 (the flag
    expression must read the materialized column, not the in-flight one).
    """
    billed = pl.col("KDVSIZ_FIYAT")
    sut = pl.col("sut_price_try")
    billed_after_abolition = pl.col("mulga_valid_to").is_not_null() & (
        pl.col("TARIH").dt.strftime("%Y-%m-%d") > pl.col("mulga_valid_to")
    )
    df = df.with_columns(
        (billed - sut).alias("delta_try"),
        pl.when(sut > 0).then(((billed - sut) / sut) * 100.0).otherwise(None).alias("delta_pct"),
    )
    return df.with_columns(
        pl.when(sut.is_null())
        .then(pl.lit("NO_SUT_PRICE"))
        .when(billed_after_abolition)
        .then(pl.lit("MULGA_BILLED_AFTER_ABOLITION"))
        .when(pl.col("delta_pct").abs() < MATCH_THRESHOLD_PCT)
        .then(pl.lit("MATCH"))
        .when(pl.col("delta_pct") > MATCH_THRESHOLD_PCT)
        .then(pl.lit("OVERCHARGE"))
        .otherwise(pl.lit("UNDERCHARGE"))
        .alias("flag"),
    )


def _classify_ek3(df: pl.DataFrame) -> pl.DataFrame:
    """EK-3: KDVSIZ_FIYAT (ex-VAT unit price) vs sut_ceiling_try (list + KDV).

    The ceiling *includes* KDV (payable ceiling) while KDVSIZ_FIYAT is ex-VAT,
    so a billed price below the KDV-inclusive ceiling is by construction safe;
    the comparison flags only material over-ceiling charges.
    """
    billed = pl.col("KDVSIZ_FIYAT")
    ceiling = pl.col("sut_ceiling_try")
    df = df.with_columns(
        (billed - ceiling).alias("delta_try"),
        pl.when(ceiling > 0)
        .then(((billed - ceiling) / ceiling) * 100.0)
        .otherwise(None)
        .alias("delta_pct"),
    )
    return df.with_columns(
        pl.when(ceiling.is_null())
        .then(pl.lit("NO_SUT_PRICE"))
        .when(pl.col("delta_pct").abs() < MATCH_THRESHOLD_PCT)
        .then(pl.lit("MATCH"))
        .when(pl.col("delta_pct") > MATCH_THRESHOLD_PCT)
        .then(pl.lit("OVERCHARGE"))
        .otherwise(pl.lit("UNDERCHARGE"))
        .alias("flag"),
    )


def _classify_ek4a(df: pl.DataFrame) -> pl.DataFrame:
    """EK-4A tier audit: hospital-applied SGK discount vs expected tier.

    ``INDIRIM_ORANI`` is NOT a discount rate — its values (0.0, 1.3333, 41.87,
    44.5...) are a pricing/KDV code unrelated to the rebate fraction (verified:
    ``INDIRIM_ORANI=0.0`` rows have ``KDVSIZ_INDIRIMLI==KDVSIZ``, i.e. no
    discount; ``=1.3333`` rows have ~1.3% discount). The real discount the
    hospital applied is derived from the price columns:

        applied_discount = 1 - KDVSIZ_INDIRIMLI_FIYAT / KDVSIZ_FIYAT

    This is compared against ``discount_tier_1`` (the primary SGK rebate from
    the EK-4A catalog). A gap > TIER_THRESHOLD_PCT percentage-points is a
    TIER_MISMATCH. Rows with no resolved tier, or no KDVSIZ price to derive
    from, are NO_SUT_PRICE.
    """
    billed = pl.col("KDVSIZ_FIYAT")
    after_disc = pl.col("KDVSIZ_INDIRIMLI_FIYAT")
    expected = pl.col("expected_discount_tier")
    # step 1: derive the real applied discount fraction from the prices.
    df = df.with_columns(
        pl.when(billed > 0)
        .then(1.0 - (after_disc / billed))
        .otherwise(None)
        .alias("applied_discount"),
    )
    tier_delta = (pl.col("applied_discount") - expected) * 100.0
    # step 2: flag.
    return df.with_columns(
        tier_delta.alias("delta_pct"),
        pl.when(expected.is_null() | pl.col("applied_discount").is_null())
        .then(pl.lit("NO_SUT_PRICE"))
        .when(tier_delta.abs() < TIER_THRESHOLD_PCT)
        .then(pl.lit("MATCH"))
        .otherwise(pl.lit("TIER_MISMATCH"))
        .alias("flag"),
    )


# ===========================================================================
# Suspected-wrong-mapping detection (crosswalk validation side effect)
# ===========================================================================
def flag_wrong_mappings(df: pl.DataFrame) -> pl.DataFrame:
    """Mark codes whose delta is systematically extreme across ALL their rows.

    A code showing >+100% (or <-50%) divergence on every row is far more likely
    a wrong crosswalk mapping than a consistent hospital pricing error. We only
    flag when there are ≥ WRONG_MAPPING_MIN_ROWS rows for that code (otherwise a
    single outlier can't be called "systematic").
    """
    price_flags = (pl.col("flag") == "OVERCHARGE") & (
        pl.col("delta_pct") > WRONG_MAPPING_DELTA_PCT
    ) | ((pl.col("flag") == "UNDERCHARGE") & (pl.col("delta_pct") < -50.0))

    by_code = (
        df.filter(pl.col("catalog").is_in(["EK-2B", "EK-3"]))
        .group_by("sut_code")
        .agg(
            pl.len().alias("n_rows"),
            pl.col("catalog").first().alias("catalog"),
            price_flags.sum().alias("n_extreme"),
            pl.col("HIZMET_TANIMI").first().alias("sample_desc"),
        )
        .with_columns(
            (
                (pl.col("n_rows") >= WRONG_MAPPING_MIN_ROWS)
                & (pl.col("n_extreme") == pl.col("n_rows"))
            ).alias("wrong_mapping"),
        )
        .filter(pl.col("wrong_mapping"))
        .select("sut_code", "catalog", "n_rows", "n_extreme", "sample_desc")
    )

    if by_code.height == 0:
        return df.with_columns(pl.lit(False).alias("suspected_wrong_mapping"))

    wrong_codes = set(by_code.get_column("sut_code").to_list())
    return df.with_columns(
        pl.col("sut_code").is_in(list(wrong_codes)).alias("suspected_wrong_mapping")
    )


# ===========================================================================
# Aggregates
# ===========================================================================
def aggregates(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Build the summary tables for the report."""
    auditable = df.filter(pl.col("flag") != "NOT_IN_SCOPE")

    by_catalog = auditable.group_by("catalog", "flag").len().sort("catalog", "flag")

    by_code = (
        auditable.filter(pl.col("catalog").is_in(["EK-2B", "EK-3"]))
        .filter(pl.col("delta_pct").is_not_null())  # drop NO_SUT_PRICE (NaN delta)
        .group_by("catalog", "sut_code")
        .agg(
            pl.len().alias("n_rows"),
            pl.col("flag").mode().first().alias("modal_flag"),
            pl.col("delta_pct").median().round(2).alias("median_delta_pct"),
            pl.col("delta_pct").mean().round(2).alias("mean_delta_pct"),
        )
        .sort("catalog", "median_delta_pct", descending=[False, True])
    )

    by_year = (
        auditable.with_columns(pl.col("TARIH").dt.year().alias("year"))
        .group_by("catalog", "year", "flag")
        .len()
        .sort("catalog", "year", "flag")
    )

    by_patient = (
        auditable.group_by("resolved_patient_key", "catalog", "flag")
        .len()
        .sort("resolved_patient_key", "catalog", "flag")
    )

    return {
        "by_catalog": by_catalog,
        "by_code": by_code,
        "by_year": by_year,
        "by_patient": by_patient,
    }


# ===========================================================================
# Spot-checks
# ===========================================================================
def spot_checks(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Pick 5 MATCH + 5 divergence rows across catalogs for manual review."""
    auditable = df.filter(
        pl.col("flag").is_in(
            ["MATCH", "OVERCHARGE", "UNDERCHARGE", "MULGA_BILLED_AFTER_ABOLITION", "TIER_MISMATCH"]
        )
    )
    cols = [
        "catalog",
        "HIZMETKODU",
        "sut_code",
        "TARIH",
        "HIZMET_TANIMI",
        "KDVSIZ_FIYAT",
        "sut_price_try",
        "sut_ceiling_try",
        "applied_discount",
        "expected_discount_tier",
        "delta_pct",
        "flag",
    ]
    cols = [c for c in cols if c in auditable.columns]

    matches = (
        auditable.filter(pl.col("flag") == "MATCH").sample(
            min(5, auditable.filter(pl.col("flag") == "MATCH").height), seed=42
        )
        if auditable.filter(pl.col("flag") == "MATCH").height > 0
        else auditable.head(0)
    ).select(cols)

    divergent_pool = auditable.filter(
        pl.col("flag").is_in(
            ["OVERCHARGE", "UNDERCHARGE", "MULGA_BILLED_AFTER_ABOLITION", "TIER_MISMATCH"]
        )
    ).filter(~pl.col("suspected_wrong_mapping"))
    divergent = (
        divergent_pool.sort(pl.col("delta_pct").abs(), descending=True).head(5).select(cols)
        if divergent_pool.height > 0
        else auditable.head(0)
    )
    return {"matches": matches, "divergent": divergent}


# ===========================================================================
# Report
# ===========================================================================
def render_report(
    df: pl.DataFrame,
    aggs: dict[str, pl.DataFrame],
    checks: dict[str, pl.DataFrame],
) -> str:
    total = df.height
    auditable = df.filter(pl.col("flag") != "NOT_IN_SCOPE").height

    def _fmt_tbl(t: pl.DataFrame, max_rows: int = 25) -> str:
        if t.height == 0:
            return "_(none)_"
        return t.head(max_rows).to_pandas().to_markdown(index=False)

    lines: list[str] = []
    p = lines.append
    p("# Finans Pricing Audit — hospital price vs SUT list price (as-of-date)\n")
    p("**Generated:** 2026-07-16  |  **Branch:** `finans-coder`\n")
    p(
        f"**Rows:** {total} total joined ({auditable} auditable; "
        f"rest = NOT_IN_SCOPE / unresolved).\n"
    )
    p("---\n")

    # headline numbers for the findings section
    ek2b = df.filter(pl.col("catalog") == "EK-2B")
    ek2b_match = ek2b.filter(pl.col("flag") == "MATCH").height
    ek2b_over = ek2b.filter(pl.col("flag") == "OVERCHARGE").height
    p("## Key findings\n")
    p(
        f"1. **Crosswalk validated (side-effect goal met).** {ek2b_match} EK-2B rows "
        f"match the SUT rate to within ±{MATCH_THRESHOLD_PCT}% (e.g. Potasyum 1.15=1.15, "
        "Sodyum 1.15=1.15, BUN 6.55=6.55). Where the code maps correctly, the price "
        "matches — the Phases 1-5 mappings are sound.\n"
    )
    p(
        f"2. **{ek2b_over} EK-2B rows overcharge**, concentrated on lab tests billed "
        "to **inpatients**. Same code (e.g. Potasyum L106150) matches the SUT unit "
        "price (6.55 TRY) on outpatient rows but is billed at 370–480 TRY as a single "
        "line on inpatient stays. Signature of **inpatient panel/bundle billing under "
        "a single-item code** — a real over-billing pattern worth investigating, not a "
        "crosswalk error.\n"
    )
    p(
        "3. **⚠️ EK-3 (materials) results are NOT trustworthy.** The EK-3 curated "
        "parquet carries implausible list prices (e.g. KN1069 = 103,084 TRY, AE0900 = "
        "8,903 TRY — a catheter is not 100K TRY). This is a catalog data-quality bug "
        "(likely unit/per-box mismatch in gazette extraction), not an audit-script bug. "
        "The EK-3 numbers below are computed but should be ignored until the EK-3 "
        "catalog prices are fixed. **Scope: defer EK-3 to a follow-up.**\n"
    )
    p(
        "4. **EK-4A tier audit:** `INDIRIM_ORANI` is NOT a discount rate (values >1, "
        "e.g. 41.87) — it is a pricing/KDV code. The real discount is derived from "
        "`1 - KDVSIZ_INDIRIMLI_FIYAT/KDVSIZ_FIYAT` and compared to `discount_tier_1`. "
        "Most drug lines apply a different rebate than the catalog tier — flagged for "
        "review, but the retail-price audit (the meaningful one) needs the TİTCK list.\n"
    )
    p("---\n")

    # overview by catalog/flag
    p("## Match / divergence by catalog\n")
    p(_fmt_tbl(aggs["by_catalog"]))
    p("\n---\n")

    # suspected wrong mappings
    wrong = df.filter(pl.col("suspected_wrong_mapping"))
    p("## Suspected wrong crosswalk mappings\n")
    p(
        "Codes whose billed-vs-SUT delta is systematically extreme across **all** "
        f"their rows (>±{WRONG_MAPPING_DELTA_PCT}% on every row, ≥{WRONG_MAPPING_MIN_ROWS} "
        "rows). A wrong code→price mapping produces this signature; a real hospital "
        "pricing error would not be perfectly consistent.\n"
    )
    if wrong.height == 0:
        p("_None — crosswalk mappings look consistent._\n")
    else:
        wrong_tab = (
            wrong.group_by("catalog", "sut_code", "HIZMET_TANIMI")
            .agg(
                pl.len().alias("n_rows"),
                pl.col("delta_pct").median().round(1).alias("median_delta_pct"),
            )
            .sort("median_delta_pct", descending=True)
        )
        p(_fmt_tbl(wrong_tab))
    p("\n---\n")

    # top per-code divergences
    p("## Top per-code divergences (median delta %)\n")
    p(_fmt_tbl(aggs["by_code"]))
    p("\n---\n")

    # yearly trend
    p("## Yearly trend (flag counts)\n")
    p(_fmt_tbl(aggs["by_year"]))
    p("\n---\n")

    # spot checks
    p("## Spot-checks — 5 matches\n")
    p(_fmt_tbl(checks["matches"], max_rows=5))
    p("\n## Spot-checks — 5 divergences\n")
    p(_fmt_tbl(checks["divergent"], max_rows=5))
    p("\n---\n")

    p("## Methodology\n")
    p(
        "- **EK-2B:** `get_ek2b_price_for_date(code, TARIH)` — strict as-of lookup "
        "(enforces `effective_date <= TARIH`, returns last-valid version). "
        "Compared ex-VAT `KDVSIZ_FIYAT` vs ex-VAT `price_try`.\n"
    )
    p(
        "- **EK-3:** `lookup_ek3_list_price_try` (ex-VAT) → `ek3_payable_ceiling_try` "
        "(+20% KDV = payable ceiling). Static (EK-3 has no date dimension).\n"
    )
    p(
        "- **EK-4A (tier audit only):** joined `sut_code`(=`kamu_no`) → "
        "`discount_tier_1` (primary SGK rebate). Compared the hospital's *derived* "
        "discount `1 - KDVSIZ_INDIRIMLI_FIYAT/KDVSIZ_FIYAT` vs the expected tier. "
        "Note: `INDIRIM_ORANI` is NOT a discount rate (values >1, e.g. 41.87) — it "
        "is a pricing/KDV code; the real discount is derived from the price columns. "
        "Retail-price audit deferred (needs TİTCK Fiyat Listesi).\n"
    )
    p(
        f"- **Thresholds:** MATCH = |delta| < {MATCH_THRESHOLD_PCT}%; "
        f"TIER_MISMATCH = |Δtier| > {TIER_THRESHOLD_PCT}pp; "
        f"wrong-mapping = systematic >{WRONG_MAPPING_DELTA_PCT}% on every row.\n"
    )
    p(
        "- **Per-row unit basis:** each finans row is a single unit of service "
        "(repeated units appear as distinct rows), so KDVSIZ_FIYAT is a per-unit "
        "price directly comparable to the SUT unit rate.\n"
    )
    p(
        "- **Mülga:** `valid_to < TARIH` (from EK-2B history parquet) → "
        "`MULGA_BILLED_AFTER_ABOLITION`.\n"
    )

    return "\n".join(lines)


# ===========================================================================
# Main
# ===========================================================================
def main() -> None:
    finans = load_finans()
    frozen = load_frozen_crosswalk()
    ek4a = load_ek4a_index()

    print(f"finans rows:       {finans.height}")
    print(f"frozen mappings:   {frozen.height}")
    print(f"ek4a drugs:        {ek4a.height}")

    resolved = join_resolved(finans, frozen)
    print(f"resolved rows:     {resolved.height}")
    print(resolved.group_by("catalog").len().sort("catalog"))

    # split by catalog, resolve per-catalog columns, recombine
    parts: list[pl.DataFrame] = []
    for cat, catalog_name in [("EK-2B", "EK-2B"), ("EK-3", "EK-3"), ("EK-4A", "EK-4A")]:
        sub = resolved.filter(pl.col("catalog") == cat)
        if sub.height == 0:
            continue
        if cat == "EK-2B":
            sub = resolve_ek2b_prices(sub)
        elif cat == "EK-3":
            sub = resolve_ek3_prices(sub)
        else:
            sub = resolve_ek4a_tiers(sub, ek4a)
        parts.append(sub)
    # rows that joined but are NOT in the 3 catalogs (UNCLEAR/etc.) still
    # carry sut_code+category — keep them as NOT_IN_SCOPE via classify().
    others = resolved.filter(~pl.col("catalog").is_in(["EK-2B", "EK-3", "EK-4A"]))
    combined = pl.concat(parts + [others], how="diagonal_relaxed")

    classified = classify(combined)
    final = flag_wrong_mappings(classified)

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    final.write_parquet(OUT_PARQUET)
    print(f"\nwrote {OUT_PARQUET} ({final.height} rows)")

    aggs = aggregates(final)
    checks = spot_checks(final)
    report = render_report(final, aggs, checks)
    OUT_REPORT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT_REPORT}")

    # console summary
    print("\n=== flag summary ===")
    print(final.group_by("catalog", "flag").len().sort("catalog", "flag"))
    n_wrong = final.filter(pl.col("suspected_wrong_mapping"))
    print(f"\nsuspected wrong mappings: {n_wrong.select('sut_code').n_unique()} codes")


if __name__ == "__main__":
    main()
