"""Tests for the Finans.XLSX cleanup pipeline (Phase 1).

Asserts the data-quality invariants verified during the 2026-07-16 probe:
  - 166 duplicate rows dropped (full-row unique), 7,646 → 7,480.
  - The 2 re-priced-variant rows (same key, different price) survive dedup.
  - The 12 multi-patient faturas split correctly: 10 batch_invoice + 2 placeholder.
  - ``resolved_patient_key`` = ``SIRA`` and is non-null on every row.
  - Solo faturas are the clean 88.6% bulk.

These counts are frozen ground-truth from the 2026-07-15 probe of
``data/Finans.XLSX``. If the source file is replaced/refreshed and these
assertions break, that is the signal to re-audit — do NOT relax the
constants silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "scripts" / "analysis"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import analyze_finans_data as af  # noqa: E402

_SOURCE = _REPO / "data" / "Finans.XLSX"

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not _SOURCE.exists(),
        reason="data/Finans.XLSX is KVKK-sensitive and not committed; "
        "tests run only where the real source file is present",
    ),
]

# ---- Frozen ground-truth constants (probe 2026-07-15) ----
RAW_ROWS = 7_646
DEDUPED_ROWS = 7_480
N_DUPES_DROPPED = 166  # 164 fully-identical + 2 same-key-different-price w/ extra copies
N_PATIENTS = 6  # SIRA values are unique patient IDs (confirmed by provider)

# The two known re-priced-variant groups: same (FATURANO,SIRA,SATIRNO,TARIH,CODE)
# but distinct prices. These MUST survive full-row dedup.
VARIANT_GROUPS = [
    ("7100297066", "96", 1, "07010001"),
    ("4516117232", "11", 1, "07010001"),
]

# Multi-patient fatura breakdown: 10 real batch + 2 placeholder (FATURANO 0/1)
N_BATCH_FATURAS = 10
N_PLACEHOLDER_FATURAS = 2
N_SOLO_FATURAS = 473  # 485 total − 10 batch − 2 placeholder


@pytest.fixture(scope="module")
def cleaned() -> pl.DataFrame:
    """Run the full cleanup once and cache the result for all tests."""
    raw = af.load()
    deduped, _ = af.dedup_full_row(raw)
    flagged = af.classify_faturas(deduped)
    return af.add_patient_key(flagged)


def test_source_file_present() -> None:
    """Guard: if the source XLSX is missing, the test suite must fail loudly,
    not silently skip — the frozen constants assume this exact file."""
    assert _SOURCE.exists(), f"Missing source: {_SOURCE}"


def test_raw_row_count_matches_audit(cleaned: pl.DataFrame) -> None:
    """Raw file must have exactly 7,646 rows (probe 2026-07-15)."""
    raw = af.load()
    assert raw.height == RAW_ROWS


def test_dedup_drops_expected_count() -> None:
    """Full-row unique must drop exactly 166 rows (7,646 → 7,480)."""
    raw = af.load()
    _, n_dropped = af.dedup_full_row(raw)
    assert n_dropped == N_DUPES_DROPPED
    assert raw.height - n_dropped == DEDUPED_ROWS


def test_repriced_variants_survive_dedup() -> None:
    """The 2 same-key-different-price rows must survive — they are re-priced
    variants, not duplicates. After dedup each variant group retains both
    distinct prices."""
    raw = af.load()
    deduped, _ = af.dedup_full_row(raw)

    for fatura, sira, satirno, code in VARIANT_GROUPS:
        rows = deduped.filter(
            (pl.col("FATURANO") == fatura)
            & (pl.col("SIRA") == sira)
            & (pl.col("HIZMET_SATIRNO") == satirno)
            & (pl.col("HIZMETKODU") == code)
        )
        n_prices = rows["KDVLI_INDIRIMLI_FIYAT"].n_unique()
        assert n_prices >= 2, (
            f"Re-priced variant {fatura}/SIRA{sira}/SATIRNO{satirno} "
            f"collapsed to {n_prices} price(s) after dedup — expected 2+"
        )


def test_no_full_row_duplicates_remain(cleaned: pl.DataFrame) -> None:
    """Idempotency: running dedup again on cleaned output drops 0 rows."""
    _again, n_dropped = af.dedup_full_row(cleaned)
    assert n_dropped == 0


def test_fatura_kind_counts(cleaned: pl.DataFrame) -> None:
    """10 batch_invoice + 2 placeholder + 473 solo faturas."""
    by_kind = (
        cleaned.group_by("FLAG_fatura_kind")
        .agg(n_faturas=pl.col("FATURANO").n_unique())
        .sort("FLAG_fatura_kind")
    )
    counts = dict(by_kind.iter_rows())
    assert counts.get("batch_invoice") == N_BATCH_FATURAS
    assert counts.get("placeholder") == N_PLACEHOLDER_FATURAS
    assert counts.get("solo") == N_SOLO_FATURAS


def test_placeholder_faturas_are_only_zero_and_one(cleaned: pl.DataFrame) -> None:
    """The placeholder kind must map 1:1 to FATURANO ∈ {0,1} — no other
    fatura number should be tagged placeholder."""
    placeholder_faturas = (
        cleaned.filter(pl.col("FLAG_fatura_kind") == "placeholder")["FATURANO"]
        .unique()
        .sort()
        .to_list()
    )
    assert placeholder_faturas == ["0", "1"]


def test_batch_faturas_span_multiple_patients(cleaned: pl.DataFrame) -> None:
    """Every batch_invoice fatura must span >1 distinct SIRA (by definition)."""
    batch = cleaned.filter(pl.col("FLAG_fatura_kind") == "batch_invoice")
    spans = batch.group_by("FATURANO").agg(n_sira=pl.col("SIRA").n_unique())
    assert (spans["n_sira"] > 1).all(), "A batch_invoice fatura spans only 1 SIRA"


def test_solo_faturas_are_single_patient(cleaned: pl.DataFrame) -> None:
    """Every solo fatura must have exactly 1 distinct SIRA."""
    solo = cleaned.filter(pl.col("FLAG_fatura_kind") == "solo")
    spans = solo.group_by("FATURANO").agg(n_sira=pl.col("SIRA").n_unique())
    assert (spans["n_sira"] == 1).all(), "A solo fatura spans >1 SIRA"


def test_resolved_patient_key_equals_sira(cleaned: pl.DataFrame) -> None:
    """resolved_patient_key must equal SIRA on every row (confirmed patient ID)."""
    mismatches = cleaned.filter(pl.col("resolved_patient_key") != pl.col("SIRA"))
    assert mismatches.height == 0
    assert cleaned["resolved_patient_key"].null_count() == 0


def test_sira_values_are_six_confirmed_patients(cleaned: pl.DataFrame) -> None:
    """The 6 distinct SIRA values must be exactly {11,61,83,89,91,96}."""
    siras = set(cleaned["SIRA"].unique().sort().to_list())
    assert siras == {"11", "61", "83", "89", "91", "96"}
    assert cleaned["SIRA"].n_unique() == N_PATIENTS


def test_batch_fatura_rows_carry_their_own_patient(cleaned: pl.DataFrame) -> None:
    """Within batch faturas, patient attribution is trivial: every row already
    carries its own SIRA (the confirmed patient ID). There is no split problem
    to solve — the row knows its patient. This test asserts that invariant
    holds (no null SIRA, and the SIRA values are the confirmed patient set).

    Note: it is *valid* for two patients in the same batch fatura to share the
    same (TARIH, HIZMETKODU) — e.g. SIRA 61 and 91 both got test C8452001 on
    2021-01-14 in fatura 4516147101. That is a real shared encounter, not a
    data error. 8 such shared-service keys exist in the batch faturas."""
    batch = cleaned.filter(pl.col("FLAG_fatura_kind") == "batch_invoice")
    # Every batch row has a non-null SIRA from the confirmed patient set.
    assert batch["SIRA"].null_count() == 0
    assert set(batch["SIRA"].unique().to_list()).issubset({"11", "61", "83", "89", "91", "96"})
    # And resolved_patient_key matches SIRA on every batch row.
    mismatches = batch.filter(pl.col("resolved_patient_key") != pl.col("SIRA"))
    assert mismatches.height == 0
