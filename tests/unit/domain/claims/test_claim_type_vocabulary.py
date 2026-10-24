"""The claim-type vocabulary folds every spelling once and gives each type its SUT care setting (#335)."""

from __future__ import annotations

import pytest

from src.bilun.domain.claims.claim_type import (
    CARE_SETTING_BY_KIND,
    care_setting_gap,
    claim_type_care_setting,
    claim_type_kind,
    fold_claim_type,
    is_day_case,
    is_emergency,
)

pytestmark = pytest.mark.unit

# (raw value, type) for the ASCII and the Turkish spelling of every type the issue lists.
SPELLINGS = (
    ("yatis", "yatis"),
    ("yatış", "yatis"),
    ("YATIŞ", "yatis"),
    ("yatan", "yatis"),
    ("Yatan Hasta", "yatis"),
    ("yatarak", "yatis"),
    ("YATARAK", "yatis"),
    ("inpatient", "yatis"),
    ("poliklinik", "poliklinik"),
    ("Poliklinik", "poliklinik"),
    ("ayakta", "poliklinik"),
    ("ayaktan", "poliklinik"),
    ("Ayakta Tedavi", "poliklinik"),
    ("outpatient", "poliklinik"),
    ("gunubirlik", "gunubirlik"),
    ("günübirlik", "gunubirlik"),
    ("GÜNÜBİRLİK", "gunubirlik"),
    ("Günübirlik Tedavi", "gunubirlik"),
    ("günübirlik yatış", "gunubirlik"),
    ("gunubirlik yatis", "gunubirlik"),
    ("day_case", "gunubirlik"),
    ("Day-Case", "gunubirlik"),
    ("daycase", "gunubirlik"),
    ("acil", "acil"),
    ("ACİL", "acil"),
    ("Acil Servis", "acil"),
    ("acil-servis", "acil"),
    ("emergency", "acil"),
    ("koruyucu", "koruyucu"),
    ("Koruyucu Sağlık", "koruyucu"),
    ("preventive", "koruyucu"),
    ("meslek_hastaligi", "meslek_hastaligi"),
    ("meslek hastalığı", "meslek_hastaligi"),
    ("MESLEK HASTALIĞI", "meslek_hastaligi"),
    ("occupational_disease", "meslek_hastaligi"),
)


@pytest.mark.parametrize(("raw", "kind"), SPELLINGS)
def test_every_spelling_folds_to_its_type(raw: str, kind: str) -> None:
    assert claim_type_kind(raw) == kind
    assert claim_type_kind(f"  {raw}  ") == kind


@pytest.mark.parametrize(
    ("raw", "folded"),
    [("Günübirlik", "gunubirlik"), ("ACİL SERVİS", "acil_servis"), ("Day-Case", "day_case"), ("YATIŞ", "yatis")],
)
def test_the_fold_is_case_turkish_and_space_blind(raw: str, folded: str) -> None:
    assert fold_claim_type(raw) == folded


@pytest.mark.parametrize(
    ("kind", "care_setting"),
    [
        # SUT 2.1.2.A (C000490): yatış to taburcu.
        ("yatis", "inpatient"),
        # SUT 2.1.1 (C000482): care without admission.
        ("poliklinik", "outpatient"),
        # Read as outpatient with the day-case flag, as before #335 (SUT 2.1.2.B, C000492).
        ("gunubirlik", "outpatient"),
        # SUT 2.2.1.B-2(2)(a) (C000607): emergency services are ayakta tedavi billed fee for service.
        ("acil", "outpatient"),
        # Provision grounds (SUT 1.7, C000193, C000196): the type does not say whether the patient was admitted.
        ("koruyucu", None),
        ("meslek_hastaligi", None),
    ],
)
def test_each_type_has_the_care_setting_the_sut_gives_it(kind: str, care_setting: str | None) -> None:
    assert CARE_SETTING_BY_KIND[kind] == care_setting
    spellings = [raw for raw, k in SPELLINGS if k == kind]
    assert spellings
    assert {claim_type_care_setting(raw) for raw in spellings} == {care_setting}


def test_the_vocabulary_has_the_six_types_of_the_issue() -> None:
    assert set(CARE_SETTING_BY_KIND) == {"yatis", "poliklinik", "gunubirlik", "acil", "koruyucu", "meslek_hastaligi"}


@pytest.mark.parametrize(
    ("raw", "gap"),
    [
        ("", "missing"),
        ("   ", "missing"),
        (None, "missing"),
        ("unknown", "unrecognized"),
        ("yatiss", "unrecognized"),
        # A whole value, never a substring: a compound is not guessed.
        ("acil_yatis", "unrecognized"),
        ("poliklinik_acil", "unrecognized"),
        ("koruyucu", "not_settled"),
        ("Meslek Hastalığı", "not_settled"),
        ("acil", None),
        ("günübirlik", None),
        ("day_case", None),
        ("yatan", None),
        ("ayakta", None),
    ],
)
def test_the_care_setting_gap_names_why_no_setting_can_be_read(raw: str | None, gap: str | None) -> None:
    assert care_setting_gap(raw) == gap


@pytest.mark.parametrize(("raw", "kind"), SPELLINGS)
def test_day_case_and_emergency_follow_the_type(raw: str, kind: str) -> None:
    assert is_day_case(raw) is (kind == "gunubirlik")
    assert is_emergency(raw) is (kind == "acil")
