"""Standalone draft transport stays strict without inventing shared integration."""
from dataclasses import asdict, fields
from datetime import date, datetime
from decimal import Decimal
import json
from types import MappingProxyType

import pytest

from src.bilun.domain.claims.mds_evidence import MdsEvidence, parse_mds_evidence

DAY = date(2026, 10, 2)


def facts(**changes):
    return MdsEvidence(**{
        "applies_on": DAY, "assessment_date": DAY,
        "indication": "mds_anemia", "substance": "epoetin_alfa", "phase": "initiation",
        "hb_value": 10.9, "hb_unit": "g/dL", "hb_date": DAY,
        "blast_value": 4.9, "blast_unit": "%", "blast_date": DAY,
        "serum_epo_value": 499, "serum_epo_unit": "mu/ml", "serum_epo_date": DAY,
        "weekly_dose_value": 900, "weekly_dose_unit": "IU/kg/week",
        "specialist_report_present": True, "report_author_specialty": "hematology", "report_date": DAY,
        "prescribed_by_specialist": True, "prescribed_by_specialty": "internal_medicine",
        "prescription_based_on_same_hematology_report": True,
        "usage_dose_documented_in_report": True, "usage_duration_documented_in_report": True,
        "lab_results_dates_documented_in_prescription_or_report": True,
        "hemogram_date": DAY, "hemogram_result_documented_in_prescription": True,
        "hemogram_date_documented_in_prescription": True, "prescribed_supply_months": 1,
        **changes,
    })


def test_mapping_json_and_typed_transport_preserve_explicit_facts_without_defaults():
    payload = asdict(facts(prescribed_by_specialist=False, prescribed_supply_months=0.5))
    payload = {name: value.isoformat() if type(value) is date else value for name, value in payload.items()}
    expected = facts(prescribed_by_specialist=False, prescribed_supply_months=0.5)
    assert parse_mds_evidence(payload) == expected
    assert parse_mds_evidence(MappingProxyType(payload)) == expected
    assert parse_mds_evidence(json.dumps(payload)) == expected
    assert parse_mds_evidence(expected) == expected
    assert expected.prescribed_by_specialist is False


@pytest.mark.parametrize("value", [None, [], True, 3, "not JSON", "[]", "null", "true"])
def test_non_object_evidence_is_absent(value):
    assert parse_mds_evidence(value) is None


NUMBERS = [field.name for field in fields(MdsEvidence) if field.type == "float | None"]
BOOLS = [field.name for field in fields(MdsEvidence) if field.type == "bool | None"]
DATES = [field.name for field in fields(MdsEvidence) if field.type == "date | None"]


@pytest.mark.parametrize("field", NUMBERS)
@pytest.mark.parametrize("value", [True, False, "10", -1, float("nan"), float("inf"), Decimal("10"), 10**1000])
def test_numbers_reject_coercion_and_nonfinite_values_even_in_typed_objects(field, value):
    for supplied in ({field: value}, facts(**{field: value})):
        assert getattr(parse_mds_evidence(supplied), field) is None


@pytest.mark.parametrize("field", NUMBERS)
@pytest.mark.parametrize("value", [0, 0.5, 10])
def test_exact_finite_nonnegative_numbers_are_retained(field, value):
    assert getattr(parse_mds_evidence({field: value}), field) == value


@pytest.mark.parametrize("field", BOOLS)
@pytest.mark.parametrize("value", [0, 1, "true", "false", {}, []])
def test_documentary_booleans_never_accept_truthy_coercion(field, value):
    assert getattr(parse_mds_evidence(facts(**{field: value})), field) is None
    assert getattr(parse_mds_evidence(facts(**{field: False})), field) is False


@pytest.mark.parametrize("field", DATES)
@pytest.mark.parametrize("value", ["2026-10-2", "2026-02-30", "2026-10-02T00:00:00", datetime(2026, 10, 2), True])
def test_dates_are_exact_and_typed_objects_do_not_bypass_validation(field, value):
    assert getattr(parse_mds_evidence(facts(**{field: value})), field) is None


@pytest.mark.parametrize("field,value", [
    ("indication", "D46"), ("indication", "D47"), ("indication", "MDS"),
    ("substance", "epoetin"), ("substance", "epoetin_zeta"), ("substance", "darbepoetin"),
    ("substance", "peg_epoetin_beta"), ("phase", "renewal"), ("phase", "INITIATION"),
    ("hb_unit", "g/L"), ("hb_unit", "gr/dl"), ("blast_unit", "fraction"),
    ("serum_epo_unit", "mu/mL"), ("serum_epo_unit", "mIU/mL"), ("serum_epo_unit", "U/L"),
    ("weekly_dose_unit", "IU/week"), ("weekly_dose_unit", "µg/week"),
    ("report_author_specialty", "hematoloji"), ("prescribed_by_specialty", "specialist"),
])
def test_no_substance_unit_or_specialty_aliases_are_silently_reinterpreted(field, value):
    assert getattr(parse_mds_evidence(facts(**{field: value})), field) is None


def test_absent_facts_and_generic_metadata_never_become_source_specific_facts():
    parsed = parse_mds_evidence({"board_report_present": True, "prescriber_specialty": "hematoloji",
                                 "hb": 10, "dose": 900, "supply_days": 30})
    assert parsed == MdsEvidence()
    assert parse_mds_evidence({"phase": "restart"}).phase == "restart"
    assert parse_mds_evidence({"indication": "ckd_anemia"}).indication == "ckd_anemia"
