"""EK-2Ç (dental) catalog loading pipeline tests.

Covers the three pieces of the dental data fix:

1. **Regex routing** — the annex parser in ``convert_xlsx_to_parquet.py`` must
   route the ``EK-2Ç DİŞ TEDAVİLERİ`` workbook into ``annex=EK-2Ç`` (previously
   the ``[A-ZC]`` character class silently dropped the ``Ç`` and bucketed it
   under the bare ``EK-2`` family, so the dental price list never reached the
   curated catalog).

2. **Catalog membership** — ``lookup_procedure_code`` must resolve 6-digit
   dental codes (40xxxx amalgam fillings, examinations, etc.) to the merged
   EK-2B + EK-2Ç ``by_code`` index that ``load_sut_catalog`` builds.

3. **Fallback** — when the curated parquet is absent, the dental loader reads
   the raw ``.xls`` workbook directly so the catalog still resolves dental
   codes on a fresh checkout with raw data but no built parquet.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ────────────────────────────────────────────────────────────────────────────
# 1. Regex routing: EK-2Ç must parse as its own annex, not collapse to "EK-2"
# ────────────────────────────────────────────────────────────────────────────


def test_annex_regex_matches_turkish_cedilla() -> None:
    """The annex regex must capture the Turkish ``Ç`` suffix.

    Regression for the ``[A-ZC]`` bug: that class doesn't include ``Ç`` so
    ``EK-2Ç ...`` matched only the ``EK-2`` prefix and the dental workbook was
    mis-bucketed. The fixed character class includes every Turkish uppercase
    letter used in SUT annex names.
    """
    from scripts.sut.convert_xlsx_to_parquet import RE_ANNEX

    cases = {
        "EK-2Ç DİŞ TEDAVİLERİ PUAN LİSTESİ": "EK-2Ç",
        "EK-2Ç-1 AÇIKLAMALAR": "EK-2Ç-1",
        "EK-2Ç-3 FORMU": "EK-2Ç-3",
        # Existing annexes must keep working (no regression).
        "EK-2B HİZMET BAŞI": "EK-2B",
        "EK-2C TANIYA": "EK-2C",
        "EK-2A AYAKTAN": "EK-2A",
    }
    for path, expected in cases.items():
        m = RE_ANNEX.search(path)
        assert m is not None, f"regex failed to match {path!r}"
        assert m.group(1) == expected, f"{path!r}: expected {expected}, got {m.group(1)}"


def test_annex_regex_is_not_bare_AZ_class() -> None:
    """Guardrail: the character class must explicitly include Turkish letters.

    A plain ``[A-ZC]`` fails on ``Ç``. We assert the compiled pattern source
    contains the cedilla-C so a future refactor can't silently revert it.
    """
    from scripts.sut.convert_xlsx_to_parquet import RE_ANNEX

    assert "Ç" in RE_ANNEX.pattern, (
        "EK-2Ç routing requires Ç in the annex character class; "
        f"got pattern {RE_ANNEX.pattern!r}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 2. Catalog membership: lookup_procedure_code resolves 40xxxx dental codes
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def dental_lookup_results() -> dict[str, dict]:
    """Resolve the four canonical dental codes once for the module."""
    from src.bilun.domain.catalog import lookup_procedure_code

    return {
        code: lookup_procedure_code(code)
        for code in ("401010", "402010", "402020", "402030")
    }


@pytest.mark.parametrize("code", ["401010", "402010", "402020", "402030"])
def test_dental_codes_resolve_to_exact_match(
    dental_lookup_results: dict[str, dict], code: str
) -> None:
    """Each canonical dental code must produce an ``exact`` match.

    401010 = Diş hekimi muayenesi (dental exam); 402010/20/30 = one/two/three-
    surface amalgam fillings. These are the codes the dental prose rules and
    pricing engine bill against, so they must be in the unified catalog.
    """
    result = dental_lookup_results[code]
    assert result["match_type"] == "exact", (
        f"{code}: expected exact match, got {result['match_type']!r}"
    )
    assert result["entry"] is not None, f"{code}: entry is None"


def test_dental_entries_carry_puan_and_price(
    dental_lookup_results: dict[str, dict],
) -> None:
    """Dental entries must expose ``puan`` (SUT points) and ``price_try`` (TRY).

    Both fields flow from the EK-2Ç puan list through the shared
    puan→TRY coefficient; downstream pricing depends on ``price_try`` being a
    positive float.
    """
    for code, result in dental_lookup_results.items():
        entry = result["entry"]
        assert entry["puan"] is not None and entry["puan"] > 0, (
            f"{code}: puan missing or non-positive ({entry.get('puan')})"
        )
        assert entry["price_try"] is not None and entry["price_try"] > 0, (
            f"{code}: price_try missing or non-positive ({entry.get('price_try')})"
        )


def test_402010_is_amalgam_filling(dental_lookup_results: dict[str, dict]) -> None:
    """Spot-check the most-billed dental code resolves to the right procedure.

    402010 = "Amalgam dolgu, bir yüzlü" (single-surface amalgam filling). This
    is the canonical dental billing code referenced in the task brief.
    """
    entry = dental_lookup_results["402010"]["entry"]
    name = (entry.get("name") or "").lower()
    assert "amalgam" in name or "dolgu" in name, (
        f"402010 name should mention amalgam/dolgu, got {entry.get('name')!r}"
    )


def test_dental_codes_do_not_collide_with_ek2b() -> None:
    """Dental 40xxxx codes must be distinct from EK-2B's code space.

    EK-2B uses L1/R1/G1 prefixes and 5xxxxx-9xxxxx numeric ranges; the dental
    annex uses 40xxxx. The merge in ``load_sut_catalog`` adds dental entries
    only when the code is absent from EK-2B, so a known EK-2B lab code must
    still resolve to its original (non-dental) entry.
    """
    from src.bilun.domain.catalog import lookup_procedure_code

    # L101840 is the latex CRP test — a lab test, not a dental procedure.
    crp = lookup_procedure_code("L101840")
    assert crp["match_type"] == "exact"
    assert crp["entry"] is not None
    assert crp["entry"].get("annex") != "EK-2Ç", (
        "EK-2B lab code L101840 (CRP) must not be overwritten by a dental entry"
    )


def test_load_sut_catalog_exposes_dental_code_count() -> None:
    """``load_sut_catalog`` stats must report how many dental codes loaded."""
    from src.bilun.domain.catalog import load_sut_catalog

    catalog = load_sut_catalog()
    stats = catalog["ek2b"]["stats"]
    assert "dental_codes" in stats, "stats must include dental_codes count"
    assert stats["dental_codes"] > 0, (
        f"expected dental codes in catalog, got {stats['dental_codes']}"
    )


# ────────────────────────────────────────────────────────────────────────────
# 3. Fallback: raw .xls is parsed when the curated parquet is absent
# ────────────────────────────────────────────────────────────────────────────


def test_dental_fallback_reads_xls_when_parquet_missing(monkeypatch) -> None:
    """When the curated parquet is missing, the loader reads the .xls directly.

    The fallback path is what makes ``lookup_procedure_code('402010')`` work
    on a fresh checkout that has the raw data but hasn't run
    ``build_curated_catalogs.py``. We simulate that state by pointing the
    curated path at a non-existent file and asserting the .xls fallback still
    yields dental entries.
    """
    import pathlib

    from src.bilun.domain.loaders import gazette as gazette_mod

    # Reset the module-level caches so the fallback re-reads.
    monkeypatch.setattr(gazette_mod, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette_mod, "_ek2c_dental_by_asof_cache", {})

    # Pretend the curated parquet doesn't exist.
    fake_missing = pathlib.Path("/nonexistent/ek2c_dental_catalog_history.parquet")
    monkeypatch.setattr(
        gazette_mod, "EK2C_DENTAL_CURATED_HISTORY_PATH", fake_missing
    )

    result = gazette_mod._load_curated_ek2c_dental_by_asof("2026-07-01")

    # If the raw .xls is present in this environment, the fallback yields
    # dental entries; if it isn't (CI without raw data), the loader returns
    # an empty dict — both are valid, but it must NOT raise.
    assert isinstance(result, dict)
    if result:
        # When the .xls is available, the canonical codes must resolve.
        assert "402010" in result, "fallback must parse 402010 (amalgam filling)"
        entry = result["402010"]
        assert entry["puan"] > 0
        assert entry["price_try"] > 0

    # Restore the real cache state so other tests aren't affected.
    monkeypatch.setattr(gazette_mod, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette_mod, "_ek2c_dental_by_asof_cache", {})
    # Reload the constant to its real value by re-importing through constants.
    from src.bilun.domain.constants import EK2C_DENTAL_CURATED_HISTORY_PATH

    monkeypatch.setattr(
        gazette_mod, "EK2C_DENTAL_CURATED_HISTORY_PATH", EK2C_DENTAL_CURATED_HISTORY_PATH
    )


@pytest.mark.parametrize("missing_path", [False, True])
def test_dental_fallback_without_raw_workbook_is_empty(monkeypatch, tmp_path, missing_path):
    from src.bilun.domain.loaders import gazette

    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", tmp_path / "missing.parquet")
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK",
                        tmp_path / "missing.xls" if missing_path else None)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})
    monkeypatch.setattr(gazette.pd, "read_excel",
                        lambda *args, **kwargs: pytest.fail("No raw workbook must not be read"))
    assert gazette._load_curated_ek2c_dental_by_asof("2026-07-01") == {}


def test_dental_curated_snapshot_precedes_missing_raw_fallback(monkeypatch, tmp_path):
    import pandas as pd

    from src.bilun.domain.loaders import gazette

    path = tmp_path / "dental.parquet"
    pd.DataFrame([{"code": "402010", "name": "fixture dental entry", "puan": 10.0,
                   "price_try": 5.93, "effective_date": "2026-01-01"}]).to_parquet(path)
    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", path)
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})
    assert gazette._load_curated_ek2c_dental_by_asof("2026-07-01")["402010"]["price_try"] == 5.93


def test_dental_raw_fallback_still_parses_available_workbook(monkeypatch, tmp_path):
    import pandas as pd

    from src.bilun.domain.loaders import gazette

    path = tmp_path / "dental.xls"
    path.touch()
    raw = pd.DataFrame([["İŞLEM KODU", "İŞLEM ADI", "NOT", "İŞLEM PUANI"],
                        ["402010", "fixture dental entry", "", 10.0]])

    def read_excel(source, *, engine):
        assert source == path and engine == "xlrd"
        return raw

    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", tmp_path / "missing.parquet")
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", path)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})
    monkeypatch.setattr(gazette.pd, "read_excel", read_excel)
    result = gazette._load_curated_ek2c_dental_by_asof("2026-07-01")
    assert set(result) == {"402010"}
    assert result["402010"]["puan"] == 10.0
    assert result["402010"]["price_try"] == 5.93


# ────────────────────────────────────────────────────────────────────────────
# 4. History: a dental code's row is the one in force on the date (#293)
# ────────────────────────────────────────────────────────────────────────────

# (code, puan, effective_date, valid_from, valid_to): the shape of the RG-12/12/2024
# amendment of the list in force since 11/05/2024 (Yürürlük 20/12/2024): 402150 amended,
# 402251 added, 402270 repealed and absent from the list of 01/01/2026.
_HISTORY = [
    ("402150", 815.16, "2023-09-02", "2023-09-02", "2024-05-10"),
    ("402150", 1222.74, "2024-05-11", "2024-05-11", "2024-12-19"),
    ("402150", 959.04, "2024-05-11", "2024-12-20", "2025-12-31"),
    ("402150", 1150.848, "2026-01-01", "2026-01-01", None),
    ("402251", 73.01, "2024-05-11", "2024-12-20", "2025-12-31"),
    ("402251", 87.612, "2026-01-01", "2026-01-01", None),
    ("402270", 199.76, "2023-09-02", "2023-09-02", "2024-05-10"),
    ("402270", 299.64, "2024-05-11", "2024-05-11", "2024-12-19"),
]
# The rows in three orders, so no answer depends on where a row sits in the file.
_ORDERS = {
    "built": list(range(len(_HISTORY))),
    "reversed": list(reversed(range(len(_HISTORY)))),
    "mixed": [5, 2, 7, 0, 4, 1, 6, 3],
}


@pytest.fixture(params=sorted(_ORDERS))
def dental_history(request, monkeypatch, tmp_path):
    """The reader of a curated dental history holding ``_HISTORY`` in one of ``_ORDERS``."""
    import pandas as pd

    from src.bilun.domain.loaders import gazette

    rows = [_HISTORY[i] for i in _ORDERS[request.param]]
    frame = pd.DataFrame(rows, columns=["code", "puan", "effective_date", "valid_from", "valid_to"])
    frame.insert(1, "name", "fixture dental entry " + frame["code"])
    frame["price_try"] = (frame["puan"] * 0.593).round(2)
    frame["valid_to"] = frame["valid_to"].astype("string")
    path = tmp_path / "dental.parquet"
    frame.to_parquet(path, index=False)
    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", path)
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})
    return gazette._load_curated_ek2c_dental_by_asof


@pytest.mark.parametrize(
    "day, expected",
    [
        # Before the whole history each code's first row answers, as for EK-2B and EK-2C.
        ("2023-01-01", {"402150": 815.16, "402251": 73.01, "402270": 199.76}),
        ("2024-05-10", {"402150": 815.16, "402270": 199.76}),
        # The list's own date: the clean rows; the added code is not in force yet.
        ("2024-05-11", {"402150": 1222.74, "402270": 299.64}),
        ("2024-06-01", {"402150": 1222.74, "402270": 299.64}),
        # valid_to is the last day a row applies.
        ("2024-12-19", {"402150": 1222.74, "402270": 299.64}),
        # Yürürlük 20/12/2024: the amended and the added rows start, the repealed code ends.
        ("2024-12-20", {"402150": 959.04, "402251": 73.01}),
        ("2025-01-15", {"402150": 959.04, "402251": 73.01}),
        ("2025-12-31", {"402150": 959.04, "402251": 73.01}),
        ("2026-01-01", {"402150": 1150.848, "402251": 87.612}),
        ("2026-02-15", {"402150": 1150.848, "402251": 87.612}),
    ],
)
def test_dental_reader_takes_the_row_whose_validity_covers_the_date(dental_history, day, expected):
    by_code = dental_history(day)
    assert {code: entry["puan"] for code, entry in by_code.items()} == expected
    for code, entry in by_code.items():
        assert entry["price_try"] == round(expected[code] * 0.593, 2)
        assert entry["annex"] == "EK-2Ç"


def test_dental_entry_carries_the_validity_of_its_row(dental_history):
    entry = dental_history("2025-01-15")["402150"]
    assert (entry["effective_date"], entry["valid_from"], entry["valid_to"]) == (
        "2024-05-11", "2024-12-20", "2025-12-31",
    )
    assert dental_history("2026-02-15")["402150"]["valid_to"] is None


def test_dental_snapshot_without_validity_is_in_force_from_its_list_date(monkeypatch, tmp_path):
    """The .xls fallback carries only effective_date: each row applies from it, open-ended."""
    import pandas as pd

    from src.bilun.domain.loaders import gazette

    path = tmp_path / "dental.parquet"
    pd.DataFrame([
        {"code": "402010", "name": "fixture dental entry", "puan": 10.0, "price_try": 5.93,
         "effective_date": "2024-05-11"},
        {"code": "402010", "name": "fixture dental entry", "puan": 20.0, "price_try": 11.86,
         "effective_date": "2026-01-01"},
    ]).to_parquet(path)
    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", path)
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})
    assert gazette._load_curated_ek2c_dental_by_asof("2025-12-31")["402010"]["puan"] == 10.0
    entry = gazette._load_curated_ek2c_dental_by_asof("2030-01-01")["402010"]
    assert (entry["puan"], entry["valid_from"], entry["valid_to"]) == (20.0, "2026-01-01", None)


# The committed catalog (#293): a fresh build of the raw lists, read on the line's date.
# 1,688 rows of 8 lists plus the 45 marked twins that start after the clean row of their code.
_DENTAL_ROWS = 1733


def test_committed_dental_history_is_a_fresh_build_of_the_raw_lists() -> None:
    import pandas as pd
    import polars as pl

    from scripts.sut import build_curated_catalogs as builder
    from scripts.sut._common import _load_manifest
    from scripts.sut.catalogs.price_history import extract_ek2c_dental
    from src.bilun.domain.constants import EK2C_DENTAL_CURATED_HISTORY_PATH

    root = builder.DEFAULT_PARQUET_ROOT
    fresh = builder._build_history(root, _load_manifest(root), "EK-2Ç", extract_ek2c_dental, "code")
    committed = pd.read_parquet(EK2C_DENTAL_CURATED_HISTORY_PATH)
    assert list(committed.columns) == list(fresh.columns)
    assert pl.from_pandas(committed).equals(pl.from_pandas(fresh))
    assert len(committed) == _DENTAL_ROWS


@pytest.mark.parametrize(
    "day, puan",
    [
        ("2024-05-10", 815.16),
        ("2024-06-01", 1222.74),
        ("2024-12-19", 1222.74),
        ("2024-12-20", 959.04),
        ("2025-01-15", 959.04),
        ("2026-02-15", 1150.848),
    ],
)
def test_402150_is_priced_by_the_list_row_in_force_on_the_date(day, puan) -> None:
    """RG-12/12/2024 amends 402150 from Yürürlük 20/12/2024; the list's clean row applies before."""
    from src.bilun.domain.catalog import lookup_procedure_code
    from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date

    result = lookup_procedure_code("402150", visit_date=day)
    assert result["match_type"] == "exact"
    assert result["entry"]["annex"] == "EK-2Ç"
    assert result["entry"]["puan"] == pytest.approx(puan)
    assert get_ek2b_price_for_date("402150", day, "puan") == pytest.approx(puan)


@pytest.mark.parametrize("code", ["402270", "402271", "402272", "402273"])
def test_root_canal_codes_repealed_from_2024_12_20_have_no_dental_match_after(code) -> None:
    """Mülga: RG-12/12/2024, Yürürlük 20/12/2024; the list of 01/01/2026 has no row of them."""
    from src.bilun.domain.catalog import lookup_procedure_code
    from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date

    before = lookup_procedure_code(code, visit_date="2024-12-19")
    assert before["match_type"] == "exact"
    assert before["entry"]["annex"] == "EK-2Ç"
    assert get_ek2b_price_for_date(code, "2024-12-19") == before["entry"]["price_try"]
    for day in ("2024-12-20", "2025-06-01", "2026-02-15"):
        assert lookup_procedure_code(code, visit_date=day) == {
            "match_type": "none", "entry": None, "candidates": [],
        }
        assert get_ek2b_price_for_date(code, day) is None
