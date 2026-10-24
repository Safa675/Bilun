"""EK-3B exceptions/qualifiers must precede adverse and monetary decisions."""

from dataclasses import replace
from datetime import date

import pytest

from src.bilun.domain.analytics.materials import price_material_lines
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.dataset_builder import _enrich_material_regulatory_flags
from src.bilun.domain.rules.bundling_rules import check_bundling_violations_for_context
from src.bilun.domain.rules.exclusion_rules import check_exclusion_violations_for_context

pytestmark = pytest.mark.unit


def _ctx(name, care="inpatient"):
    ctx = build_context_from_material_dict({
        "claim_id": "C1", "materials": [{"name": name, "billed_amount": 100}]
    })
    header = replace(ctx.claims[0], patient_id="P1", claim_type=care, scenario_tag="actual_claim")
    materials = tuple(replace(row, patient_id="P1", material_date=date(2024, 6, 1))
                      for row in ctx.material_lines)
    materials = tuple(_enrich_material_regulatory_flags(
        {row.material_line_id: row for row in materials}, {header.claim_id: header}
    ).values())
    return replace(ctx, patient_id="P1", claims=(header,), material_lines=materials)


@pytest.mark.parametrize("name,care,family", [
    ("Cerrahi steril eldiven", "inpatient", "bundling"),
    ("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "outpatient", "bundling"),
    ("Viskosüplemantasyon ürünleri", "inpatient", "exclusion"),
])
def test_explicit_exception_or_unknown_applicability_cannot_be_a_confirmed_violation(name, care, family):
    ctx = _ctx(name, care)
    detector = check_bundling_violations_for_context if family == "bundling" else check_exclusion_violations_for_context
    assert detector(ctx) == []


def test_conditional_viscosupplementation_is_unknown_not_proven_reimbursable():
    row = price_material_lines([{"name": "Viskosüplemantasyon ürünleri", "billed_amount": 100}])[0]
    assert row.is_reimbursable is None
    assert "unavailable" in row.notes


def test_enrichment_clears_stale_derived_flags_without_touching_package_flag():
    line = replace(_ctx("unrelated implant").material_lines[0],
                   is_bundled=True, is_ek3b1_bundled=True, is_excluded=True)
    updated = _enrich_material_regulatory_flags({line.material_line_id: line})[line.material_line_id]
    assert updated.is_ek3b1_bundled is False
    assert updated.is_excluded is False
    assert updated.is_bundled is True


def test_genuine_unconditional_glove_and_inflow_matches_remain():
    assert check_bundling_violations_for_context(_ctx("Eldiven"))
    assert check_exclusion_violations_for_context(_ctx("İnflow kateter"))


@pytest.mark.parametrize("name,care,status", [
    ("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "inpatient", "matched"),
    ("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "outpatient", "not_matched"),
    ("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", None, "unavailable"),
    ("Kan şekeri ölçüm çubukları", "inpatient", "matched"),
    ("Kan şekeri ölçüm çubukları", "outpatient", "not_matched"),
    ("İdrar ölçüm çubukları", "outpatient", "matched"),
    ("Oksijen", "inpatient", "unavailable"),
    ("Disposable enjektör", "inpatient", "unavailable"),
    ("Oksijen (pansuman için)", "inpatient", "unavailable"),
    ("Oksijen maskesi", "outpatient", "matched"),
    ("Nazal oksijen kanülü", "outpatient", "matched"),
    ("Disposable enjektör iğnesi", "outpatient", "matched"),
    ("Steril eldiven", "inpatient", "unavailable"),
    ("Nonsteril eldiven", "inpatient", "matched"),
])
def test_setting_and_clinical_use_qualifiers_are_not_inferred_from_candidate_name(name, care, status):
    from src.bilun.domain.materials.exclusions import assess_bundled_material

    assert assess_bundled_material(name, care_setting=care).status == status


def test_dictionary_adapter_never_uses_its_invented_care_setting_as_evidence():
    ctx = build_context_from_material_dict({"materials": [{
        "name": "Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "billed_amount": 100,
    }]})
    assert ctx.claims[0].claim_type == "ayakta"
    assert ctx.material_lines[0].is_ek3b1_bundled is None
    assert check_bundling_violations_for_context(ctx) == []


@pytest.mark.parametrize("reimbursable,bundled", [(None, False), (True, None)])
def test_unknown_exclusion_or_bundling_never_creates_uplift(monkeypatch, reimbursable, bundled):
    from src.bilun.domain.prose_rules import material_uplift as module

    monkeypatch.setattr(module, "is_material_in_ek3_catalog", lambda *_: True)
    monkeypatch.setattr(module, "is_material_reimbursable", lambda *_, **__: reimbursable)
    monkeypatch.setattr(module, "resolve_material_name_by_code", lambda _: "material")
    monkeypatch.setattr(module, "is_consumable_bundled", lambda *_, **__: bundled)
    monkeypatch.setattr(module, "is_separate_billing_allowed", lambda *_: True)
    assert module._material_eligible_for_uplift("CODE", pairing_mode="separate_billing")[0] is False


def test_positive_flags_cannot_override_explicit_sterile_exception():
    ctx = _ctx("Cerrahi steril eldiven")
    forged = replace(ctx.material_lines[0], is_ek3b1_bundled=True)
    assert check_bundling_violations_for_context(replace(ctx, material_lines=(forged,))) == []


def test_code_resolved_surgical_sterile_glove_is_not_bundled(monkeypatch):
    from src.bilun.domain.materials import catalog_lookup
    from src.bilun.domain.materials.exclusions import assess_bundled_material

    monkeypatch.setattr(catalog_lookup, "resolve_material_name_by_code", lambda _: "Cerrahi steril eldiven")
    assert assess_bundled_material("", material_code="STERILE").status == "not_matched"


def test_duplicate_names_use_their_own_claim_header_and_keep_line_identity():
    first = _ctx("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "inpatient")
    second_header = replace(first.claims[0], claim_id="C2", claim_type="outpatient")
    second = replace(first.material_lines[0], claim_id="C2", material_line_id="M2")
    headers = {first.claims[0].claim_id: first.claims[0], "C2": second_header}
    lines = {first.material_lines[0].material_line_id: first.material_lines[0], "M2": second}
    enriched = _enrich_material_regulatory_flags(lines, headers)
    assert enriched[first.material_lines[0].material_line_id].is_ek3b1_bundled is True
    assert enriched["M2"].is_ek3b1_bundled is False
    assert set(enriched) == set(lines)


def test_unenriched_material_regulatory_flags_are_unknown():
    from dataclasses import fields
    from src.bilun.domain.claims.models import MaterialClaimLine

    defaults = {field.name: field.default for field in fields(MaterialClaimLine)}
    assert defaults["is_ek3b1_bundled"] is None
    assert defaults["is_excluded"] is None


def test_missing_catalog_cannot_certify_absence_or_reimbursability(monkeypatch):
    from src.bilun.domain.materials import exclusions

    monkeypatch.setattr(exclusions, "get_bundled_consumables", lambda: ())
    monkeypatch.setattr(exclusions, "get_non_reimbursable_materials", lambda: ())
    assert exclusions.is_consumable_bundled("material") is None
    assert exclusions.is_material_reimbursable("material") is None


def test_code_resolved_conditional_exclusion_stays_unknown_in_pricing(monkeypatch):
    from src.bilun.domain.materials import catalog_lookup

    monkeypatch.setattr(catalog_lookup, "resolve_material_name_by_code", lambda _: "Viskosüplemantasyon ürünleri")
    line = price_material_lines([{"name": "", "code": "VISCO1", "unit_price": 100}])[0]
    assert line.is_reimbursable is None
    assert line.total_price == 100


@pytest.mark.parametrize("name", ["Oksijen", "Disposable enjektör"])
def test_shared_prefix_does_not_select_first_source_row(name):
    from src.bilun.domain.materials.exclusions import assess_bundled_material

    assessment = assess_bundled_material(name, care_setting="inpatient")
    assert assessment.status == "unavailable"
    assert assessment.match_kind == "name_ambiguous"
    assert assessment.reason == "annex_material_identity_ambiguous"


def test_foreign_patient_header_cannot_supply_inpatient_eligibility():
    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims

    ctx = _ctx("Disposable enjektör (1,2,5,10,20 ve 50 cc likler)", "inpatient")
    line = replace(ctx.material_lines[0], is_bundled=True, is_ek3b1_bundled=True)
    foreign = replace(ctx.claims[0], patient_id="FOREIGN")
    ctx = replace(ctx, claims=(foreign,), material_lines=(line,))
    assert check_bundling_violations_for_context(ctx) == []
    enriched = _enrich_material_regulatory_flags(
        {line.material_line_id: line}, {foreign.claim_id: foreign}
    )
    assert enriched[line.material_line_id].is_ek3b1_bundled is None
    reviews = precheck_materials_from_claims(ctx).bundled_separate_billing
    assert len(reviews) == 1  # independent package flag is still preserved
    assert reviews[0]["sut_section_id"] == "package_flag"


@pytest.mark.parametrize("name", ["kateter", "İnflow"])
def test_partial_exclusion_category_cannot_prove_named_subtype(name):
    from src.bilun.domain.materials.exclusions import assess_excluded_material

    assessment = assess_excluded_material(name)
    assert assessment.status == "unavailable"
    assert assessment.reason == "annex_material_identity_partial"
    assert check_exclusion_violations_for_context(_ctx(name)) == []


@pytest.mark.parametrize("name", ["İnflow kateter", "İnflow kateter 12 Fr"])
def test_full_exclusion_subtype_remains_confirmed(name):
    from src.bilun.domain.materials.exclusions import assess_excluded_material

    assert assess_excluded_material(name).status == "matched"
    assert check_exclusion_violations_for_context(_ctx(name))
