"""Runtime readers apply a curated row from its own Yürürlük date (#227).

SGK writes later amendments into the list they change: P609541 sits in the EK-2C list
effective 2026-07-07 with "Yürürlük: 10/10/2026", 603331 in the EK-2B list with
"Yürürlük: 05/09/2026". The curated rows carry those dates in valid_from.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.bilun.domain.catalog import get_ek1a_exemptions, load_sut_catalog
from src.bilun.domain.loaders import legacy
from src.bilun.domain.materials.catalog_lookup import (
    is_material_in_ek3_catalog,
    lookup_ek3_list_price_try,
)
from src.bilun.domain.optimization.copay_exemption_rules.ek1a import evaluate_ek1a_exemption
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date, get_ek2c_price_for_date
from src.bilun.domain.prose_rules.catalog_membership import (
    codes_in_annex,
    get_ek2c_entry,
    procedure_annex_membership,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("day", ["2026-07-07", "2026-09-05", "2026-10-09"])
def test_p609541_does_not_match_a_claim_dated_before_2026_10_10(day: str) -> None:
    assert procedure_annex_membership("P609541", as_of_date=day) == (False, False)
    assert get_ek2c_entry("P609541", as_of_date=day) is None
    assert get_ek2c_price_for_date("P609541", day) is None
    assert "609541" not in codes_in_annex("EK-2/C", as_of_date=day)


def test_p609541_matches_from_2026_10_10() -> None:
    assert procedure_annex_membership("P609541", as_of_date="2026-10-10") == (True, True)
    assert get_ek2c_price_for_date("P609541", "2026-10-10") == pytest.approx(127499.25)
    assert get_ek2b_price_for_date("609541", "2026-10-10", "puan") == pytest.approx(25278.02)


def test_row_marked_05_09_2026_in_the_2026_07_07_list_applies_from_that_date() -> None:
    assert procedure_annex_membership("603331", as_of_date="2026-07-07") == (False, False)
    assert get_ek2b_price_for_date("603331", "2026-07-07") is None
    assert procedure_annex_membership("603331", as_of_date="2026-09-05") == (True, True)
    assert get_ek2b_price_for_date("603331", "2026-09-05", "puan") == pytest.approx(26822.66)


def test_amended_row_replaces_its_clean_row_on_the_amendment_date() -> None:
    before = load_sut_catalog(visit_date="2026-07-07")["ek2b"]["by_code"]["701223"]
    after = load_sut_catalog(visit_date="2026-09-05")["ek2b"]["by_code"]["701223"]
    assert before["name"].startswith("Endobronşial Ultrasonografi (Biyopsi")
    assert (before["valid_from"], before["valid_to"]) == ("2026-07-07", "2026-09-04")
    assert after["name"] == "Endobronşial Ultrasonografi (EBUS) eşliğinde biyopsi"
    assert (after["effective_date"], after["valid_from"]) == ("2026-07-07", "2026-09-05")


def test_ek1a_reader_applies_a_range_from_its_valid_from() -> None:
    assert "G11.3" not in set(get_ek1a_exemptions("2018-02-14")["icd10_start"])
    assert "G11.3" in set(get_ek1a_exemptions("2018-02-15")["icd10_start"])
    assert evaluate_ek1a_exemption(["G11.3"], as_of="2018-02-14") is None
    assert evaluate_ek1a_exemption(["G11.3"], as_of="2018-02-15") is not None


def test_ek1a_reader_skips_a_range_not_yet_in_force(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = pd.DataFrame({
        "icd10_start": ["N11", "N04"],
        "icd10_end": ["N11", "N04"],
        "disease_name_tr": ["Kronik Tübülo-İnterstisyel Nefrit", "Nefrotik Sendrom"],
        "valid_from": pd.array(["2026-10-02", None], dtype="string"),
        "valid_to": pd.array([None, "2026-01-31"], dtype="string"),
    })
    monkeypatch.setattr(legacy, "_ek1a_cache", listed)
    assert legacy._load_ek1a_exemptions("2026-01-31")["icd10_start"].tolist() == ["N04"]
    assert legacy._load_ek1a_exemptions("2026-10-02")["icd10_start"].tolist() == ["N11"]


def test_ek3o_readers_apply_amended_and_added_rows_from_2026_09_05() -> None:
    assert lookup_ek3_list_price_try("HO1005", as_of="2026-09-04") == pytest.approx(2134.44)
    assert lookup_ek3_list_price_try("HO1005", as_of="2026-09-05") == pytest.approx(2116.57)
    assert lookup_ek3_list_price_try("HO1017", as_of="2026-09-04") == pytest.approx(2501.296875)
    assert lookup_ek3_list_price_try("HO1017", as_of="2026-09-05") == pytest.approx(2483.43)
    assert not is_material_in_ek3_catalog("HO1034", as_of="2026-09-04")
    assert lookup_ek3_list_price_try("HO1034", as_of="2026-09-04") is None
    assert is_material_in_ek3_catalog("HO1034", as_of="2026-09-05")
    assert lookup_ek3_list_price_try("HO1034", as_of="2026-09-05") == pytest.approx(4600.0)
