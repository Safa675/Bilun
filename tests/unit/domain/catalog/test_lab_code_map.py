"""BILUN lab test names must map to the EK-2B code that bills that test."""

from __future__ import annotations

import re

import pytest

from src.bilun.domain.catalog import load_sut_catalog, lookup_procedure_code
from src.bilun.domain.constants import BILUN_TO_SUT_CODE, HEMOGRAM_TESTS, _OLD_CODE_TO_TEST_NAME
from src.bilun.domain.utils import turkish_lower

pytestmark = pytest.mark.unit

# Test names the catalog spells differently. Every other name must appear in
# its catalog name as written.
_CATALOG_SPELLING: dict[str, str] = {
    **dict.fromkeys(HEMOGRAM_TESTS, "Hemogram"),  # billed once as Tam Kan Sayımı (Hemogram)
    "GFR": "Kreatinin",  # calculated from serum creatinine
    "ALP": "Alkalen fosfataz",
    "HbA1c": "Hb A1c",
    "PT": "Protrombin zamanı",
    "INR": "Protrombin zamanı",  # reported from the PT result; EK-2B has no INR code
    "Albumin": "Albümin",
}

# Reviewed EK-2B name of each test's code (2026-07-07 edition; each name is
# unique in the catalog). Kalsiyum is total calcium, not ionized L103820. CRP
# is the quantitative test, not latex L101840, which EK-2B forbids billing
# together with L101850. Safa confirmed both on 2026-10-15.
_REVIEWED_NAME: dict[str, str] = {
    "CRP": "C reaktif protein (CRP)",
    "Prokalsitonin": "Prokalsitonin (Serum/Plazma)",
    "Kreatinin": "Kreatinin (Serum/Plazma)",
    "Üre": "Üre (Serum/Plazma)",
    "GFR": "Kreatinin (Serum/Plazma)",
    "ALT": "Alanin aminotransferaz (ALT) (Serum/Plazma)",
    "AST": "Aspartat aminotransferaz (AST) (Serum/Plazma)",
    "ALP": "Alkalen fosfataz (Serum/Plazma)",
    "GGT": "Gamma glutamil transferaz (GGT) (Serum/Plazma)",
    "Albumin": "Albümin (Serum/Plazma)",
    "Bilirubin": "Bilirubin, total (Serum/Plazma)",
    **dict.fromkeys(HEMOGRAM_TESTS, "Tam Kan Sayımı (Hemogram)"),
    "Glukoz": "Glukoz (Serum/Plazma)",
    "HbA1c": "Glike hemoglobin (Hb A1c)",
    "Kolesterol": "Kolesterol (Serum/Plazma)",
    "Trigliserid": "Trigliserid (Serum/Plazma)",
    "LDL": "LDL kolesterol (Direkt)",
    "HDL": "HDL kolesterol",
    "Sodyum": "Sodyum (Serum/Plazma)",
    "Potasyum": "Potasyum (Serum/Plazma)",
    "Kalsiyum": "Kalsiyum (Serum/Plazma)",
    "Protein": "Protein (Serum/Plazma)",
    "TSH": "TSH",
    "T3": "Serbest T3",
    "T4": "Serbest T4",
    "PT": "Protrombin zamanı (Koagülometre)",
    "aPTT": "APTT",
    "INR": "Protrombin zamanı (Koagülometre)",
}

_WORD = re.compile(r"\w+")


def _words(text: str) -> str:
    """Turkish case-folded words, space-padded so ``in`` matches whole words only."""
    return f" {' '.join(_WORD.findall(turkish_lower(text)))} "


def _in_force() -> dict[str, dict]:
    """EK-2B entries in force today, as /api/lab-prices reads them."""
    return load_sut_catalog()["ek2b"]["by_code"]


@pytest.mark.parametrize("test_name", sorted(BILUN_TO_SUT_CODE))
def test_mapped_code_is_in_force_and_named_for_the_test(test_name: str) -> None:
    code = BILUN_TO_SUT_CODE[test_name]
    entry = _in_force().get(code)
    assert entry is not None and entry["code"] == code, (
        f"{test_name}: {code} is not in the EK-2B catalog in force"
    )
    expected = _CATALOG_SPELLING.get(test_name, test_name)
    assert _words(expected) in _words(entry["name"]), (
        f"{test_name} maps to {code} = {entry['name']!r}, which does not name {expected!r}"
    )


def test_every_mapped_test_has_a_reviewed_catalog_name() -> None:
    assert set(_REVIEWED_NAME) == set(BILUN_TO_SUT_CODE)


@pytest.mark.parametrize("test_name", sorted(BILUN_TO_SUT_CODE))
def test_mapped_code_has_the_reviewed_catalog_name(test_name: str) -> None:
    code = BILUN_TO_SUT_CODE[test_name]
    assert _in_force()[code]["name"] == _REVIEWED_NAME[test_name], f"{test_name} maps to {code}"


@pytest.mark.parametrize("old_code", sorted(_OLD_CODE_TO_TEST_NAME))
def test_old_code_resolves_to_the_entry_of_its_test(old_code: str) -> None:
    test_name = _OLD_CODE_TO_TEST_NAME[old_code]
    lookup = lookup_procedure_code(old_code)
    assert lookup["match_type"] == "exact"
    assert lookup["entry"]["code"] == BILUN_TO_SUT_CODE[test_name]
    assert lookup["entry"]["name"] == _REVIEWED_NAME[test_name]


def test_lab_prices_route_serves_each_mapped_code_at_its_catalog_price() -> None:
    from src.bilun.api.routes.pricing import get_lab_prices

    by_code = _in_force()
    rows = get_lab_prices()["tests"]
    assert {row["test_name"] for row in rows} == set(BILUN_TO_SUT_CODE)
    for row in rows:
        code = BILUN_TO_SUT_CODE[row["test_name"]]
        assert row["sut_code"] == code
        assert row["price_try"] == round(by_code[code]["price_try"], 2) > 0
