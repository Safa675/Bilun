"""Phase 3.1 — ``check_dental_2_4_1_for_context`` context-wrapper tests.

Proves the ``_for_context`` shim threads a ``PatientClaimContext`` into the
canonical ``check_dental_2_4_1_prose`` material-dict evaluator: it resolves
``procedure_category`` from the material's linked ``ProcedureClaimLine`` (the
field lives on the procedure line, not ``MaterialClaimLine`` — see
``claims/models.py`` line 67) and copies through the rule-specific booleans so
the module's honesty guard skips non-surfaced rules.

Trigger rule (the wireable precious-metal case, ``dental_2_4_1.json`` line 14):
a ``dental_restoration`` material whose name contains a precious-metal keyword
(altın/platin/bego gold ewl/…) and carries
``material_contains_precious_metal=True`` must emit the
``2.4.1.(1).precious_metal_no_pay`` no-pay violation. The clean case — same
material without the flag — emits nothing (the honesty guard skips the rule).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.dental_2_4_1 import (
    check_dental_2_4_1_for_context,
)

pytestmark = pytest.mark.unit


def _make_material_line(
    *,
    name: str,
    code: str = "",
    material_line_id: str = "ML-DENTAL-1",
    procedure_line_id: str = "PL-DENTAL-1",
    material_contains_precious_metal: bool = False,
) -> MaterialClaimLine:
    """Build a minimal MaterialClaimLine carrying dental-surfaced flags.

    ``material_contains_precious_metal`` is not a first-class
    ``MaterialClaimLine`` field yet; it is set on the frozen dataclass instance
    via ``dataclasses.replace``-style construction so the shim's ``hasattr``
    copy-through picks it up (forward-compat with the model extension).
    """
    base = MaterialClaimLine(
        material_line_id=material_line_id,
        claim_id="C1",
        procedure_line_id=procedure_line_id,
        patient_id="P1",
        material_date=date(2026, 1, 1),
        material_code=code,
        material_name=name,
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    # Attach the surfaced dental flag directly to the instance. The frozen
    # dataclass is constructed above with all required fields; the dental
    # boolean is set as an object attribute so ``hasattr`` in the shim copies it
    # onto the material dict (mirrors how the build-time enricher would plumb
    # it once the model grows the field).
    object.__setattr__(
        base, "material_contains_precious_metal", material_contains_precious_metal
    )
    return base


def _make_procedure_line(
    *,
    procedure_category: str,
    procedure_line_id: str = "PL-DENTAL-1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 1),
        procedure_code="DENTAL-PROC",
        procedure_name="Dental procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_ctx(
    *,
    materials: tuple[MaterialClaimLine, ...],
    procedures: tuple[ProcedureClaimLine, ...] = (),
) -> PatientClaimContext:
    header = ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="inpatient",
        facility_tier="state",
        provider_type="public",
        department="general",
        admission_date="2026-01-01",
        discharge_date="2026-01-02",
        claim_start_date="2026-01-01",
        claim_end_date="2026-01-02",
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("600"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="dental_for_context",
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(header,),
        procedure_lines=procedures,
        material_lines=materials,
        drug_lines=(),
        diagnoses=(),
    )


def test_dental_precious_metal_violation_surfaced_from_context() -> None:
    """A dental_restoration precious-metal material must surface the no-pay rule.

    This is the wireable positive case from ``dental_2_4_1.json`` line 14:
    ``procedure_category == dental_restoration`` + name matches a precious-metal
    keyword (``bego gold ewl``) + ``material_contains_precious_metal == True``
    ⇒ the ``2.4.1.(1).precious_metal_no_pay`` rule fires with
    ``billable=False`` / ``material_outcome="no_pay"``.
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(
        materials=(material,),
        procedures=(procedure,),
    )

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1, "precious-metal dental material must be flagged"
    v = violations[0]
    assert v["rule"] == "dental_2_4_1"
    assert v["rule_id"] == "2.4.1.(1).precious_metal_no_pay"
    assert v["severity"] == "error"
    assert v["billable"] is False
    assert v["material_outcome"] == "no_pay"
    assert v["sut_section"] == "2.4.1"


def test_precious_metal_fires_without_model_flag() -> None:
    """W1.1 dead-wire fix: the rule must fire even when
    ``material_contains_precious_metal`` is NOT set on ``MaterialClaimLine``.

    ``MaterialClaimLine`` does not carry the flag (it is not a first-class
    field — see ``claims/models.py``), so the ``hasattr`` copy-through in the
    shim never sees it. Before the fix the ``precious_metal_no_pay`` rule's
    boolean condition was therefore absent and ``_condition_matches`` skipped
    it: 0 of 11 rules fired. The shim now computes the flag locally from the
    rule's own ``material_name_any`` keyword list, so a material named
    "altın köprü" (gold bridge) — with NO model-level flag — must still surface
    the violation.
    """
    # Build the line WITHOUT the artificial object.__setattr__ flag to prove the
    # shim's local computation is what drives the match, not a model attribute.
    material = MaterialClaimLine(
        material_line_id="ML-DENTAL-NOFLAG",
        claim_id="C1",
        procedure_line_id="PL-DENTAL-1",
        patient_id="P1",
        material_date=date(2026, 1, 1),
        material_code="",
        material_name="altın köprü",
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    assert not hasattr(material, "material_contains_precious_metal")
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1, (
        "precious-metal rule must fire from the local keyword computation, "
        "not from a model-level flag"
    )
    assert violations[0]["rule_id"] == "2.4.1.(1).precious_metal_no_pay"


def test_composite_filling_emits_no_violation() -> None:
    """A non-precious dental material ("kompozit dolgu" / composite filling)
    must NOT trip the precious-metal rule — its name matches none of the
    ``material_name_any`` keywords, so the local computation leaves the flag
    unset and ``_condition_matches`` honestly skips the rule.
    """
    material = MaterialClaimLine(
        material_line_id="ML-DENTAL-CLEAN",
        claim_id="C1",
        procedure_line_id="PL-DENTAL-1",
        patient_id="P1",
        material_date=date(2026, 1, 1),
        material_code="",
        material_name="kompozit dolgu",
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    assert check_dental_2_4_1_for_context(ctx) == []


def test_dental_turkish_normalization_in_name_match() -> None:
    """``altın`` (Turkish dotless i / diacritics) must normalize-match the
    precious-metal keyword list — the same assertion as
    ``test_turkish_normalization_in_keyword_match`` in
    ``test_wired_orphan_engines.py``, but threaded through the context wrapper.
    """
    material = _make_material_line(
        name="altın kaplama",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1
    assert "precious_metal" in violations[0]["rule_id"]


def test_clean_dental_material_emits_no_violation() -> None:
    """The same dental_restoration line WITHOUT ``material_contains_precious_metal``
    must emit nothing — the honesty guard in ``_condition_matches`` skips the
    rule when its boolean condition data is absent on the surfaced material dict.
    """
    material = _make_material_line(
        name="çelik kron",
        material_contains_precious_metal=False,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    assert check_dental_2_4_1_for_context(ctx) == []


def test_non_dental_category_does_not_fire_dental_rule() -> None:
    """A precious-metal-named material on a NON-dental procedure category must
    not trip the dental rule (the rule conditions are gated on
    ``procedure_category == dental_restoration``).
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="orthopedic_surgery")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    assert check_dental_2_4_1_for_context(ctx) == []


def test_empty_context_emits_nothing() -> None:
    """A context with no material lines short-circuits cleanly."""
    ctx = _make_ctx(materials=(), procedures=())

    assert check_dental_2_4_1_for_context(ctx) == []


def test_procedure_category_falls_back_to_material_specialty_category() -> None:
    """When no procedure line is linked, the material's own ``specialty_category``
    feeds ``procedure_category`` — a dental specialty material still surfaces the
    precious-metal rule without a linked procedure line.
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    # Override the specialty_category to a dental category so the fallback path
    # resolves ``procedure_category`` from the material itself.
    object.__setattr__(material, "specialty_category", "dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=())

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1
    assert "precious_metal" in violations[0]["rule_id"]


def test_bone_implant_no_pay_fires_when_board_report_absent() -> None:
    """W2.5h (MEDIUM, Bugbot): ``2.4.1.(2).bone_implant_no_pay_default`` gates
    on ``medical_necessity_board_report: false``. A typical implant line never
    sets the flag, so the surfaced material dict lacks the key. Before the fix
    ``_condition_matches`` honest-skipped on the absent key and the default
    no-pay rule NEVER fired — defeating the rule's purpose (implants default to
    no-pay absent a board report). Now absent optional dental flags are treated
    as ``False``, matching the regulatory default.
    """
    material = _make_material_line(name="kemik içi implant")
    procedure = _make_procedure_line(procedure_category="dental_implant")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1, "absent board-report flag must fire default no-pay"
    v = violations[0]
    assert v["rule_id"] == "2.4.1.(2).bone_implant_no_pay_default"
    assert v["billable"] is False
    assert v["material_outcome"] == "no_pay"
    assert v["severity"] == "error"


def test_dental_no_pay_surfaces_billed_amount_as_risk() -> None:
    """W2.5l (MEDIUM, Bugbot): no_pay dental violations must surface the billed
    amount as ``risk_amount`` (matching material_bundling / specialty_materials
    convention) so the W2.5e projection catch-all aggregates it into
    ``total_risk_try``. Before the fix dental risk_amount was always 0, so a
    no_pay dental error marked the claim invalid but contributed nothing to
    the risk headline.
    """
    material = _make_material_line(name="kemik içi implant")  # billed 500 (fixture)
    procedure = _make_procedure_line(procedure_category="dental_implant")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    v = violations[0]
    assert v["material_outcome"] == "no_pay"
    # The fixture's MaterialClaimLine carries billed_amount_try = 500; the
    # _for_context shim surfaces unit_price = float(billed_amount_try).
    assert v["risk_amount"] == 500.0



def test_bone_implant_with_explicit_board_report_no_default_no_pay() -> None:
    """W2.5h complement: when ``medical_necessity_board_report`` is explicitly
    ``True`` (board report present), the default no-pay rule must NOT fire.
    Confirms the absent→False mapping doesn't over-fire on present flags.
    """
    material = _make_material_line(name="kemik içi implant")
    object.__setattr__(material, "medical_necessity_board_report", True)
    procedure = _make_procedure_line(procedure_category="dental_implant")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    default_no_pay = [
        v for v in violations
        if v.get("rule_id") == "2.4.1.(2).bone_implant_no_pay_default"
    ]
    assert default_no_pay == []


def _precious_name_context(name: str) -> PatientClaimContext:
    """Use real line fields; composition must come from the actual name bridge."""
    day = date(2026, 7, 10)
    material = replace(
        _make_material_line(name=name),
        material_date=day,
        billed_amount_try=Decimal("125.50"),
    )
    assert not hasattr(material, "material_contains_precious_metal")
    procedure = replace(
        _make_procedure_line(procedure_category="dental_restoration"), procedure_date=day
    )
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))
    return replace(
        ctx,
        claims=(
            replace(
                ctx.claims[0],
                admission_date=day,
                discharge_date=day,
                claim_start_date=day,
                claim_end_date=day,
            ),
        ),
    )


@pytest.mark.parametrize(
    "name",
    [
        "altın içermeyen kanal tedavisi materyali",
        "platin içermeyen kanal tedavisi materyali",
        "altınsız kompozit dolgu",
        "platinsiz kompozit dolgu",
        "altın içermez",
        "altın ve platin içermeyen kompozit dolgu",
        "altın veya platin içermez",
        "paladyum+platin içermeyen kompozit dolgu",
        "altın içermeyen platin içermeyen",
        "platin içermeyen altın içermeyen",
        "altınsız platin içermeyen",
        "Bego gold EWL içermeyen materyal",
    ],
)
def test_negated_precious_metal_names_do_not_emit_a_no_pay_finding(name: str) -> None:
    assert check_dental_2_4_1_for_context(_precious_name_context(name)) == []


@pytest.mark.parametrize(
    "name",
    [
        "altın",
        "altın köprü",
        "platin",
        "platinli alaşım",
        "paladyum+platin",
        "argenco 23",
        "bego gold EWL",
        "polliag-M",
        "altın içermeyen platin içeren",
        "platin içeren altın içermeyen",
        "platin içermeyen altın içeren",
        "altın içeren platin içermeyen",
        "altın ve platin içermeyen, argenco 23",
        "argenco 23, altın ve platin içermeyen",
    ],
)
def test_affirmative_precious_metal_names_keep_the_original_raw_payload(name: str) -> None:
    from src.bilun.domain.prose_rules.dental_2_4_1 import load_dental_2_4_1_rules

    rule = load_dental_2_4_1_rules()["rules"][0]
    assert check_dental_2_4_1_for_context(_precious_name_context(name)) == [
        {
            "rule": "dental_2_4_1",
            "severity": "error",
            "material_name": name,
            "message": rule["action"]["denial_tr"],
            "savings_try": 0.0,
            "risk_amount": 125.5,
            "sut_section": "2.4.1",
            "rule_id": "2.4.1.(1).precious_metal_no_pay",
            "billable": False,
            "material_outcome": "no_pay",
            "annex_basis": None,
        }
    ]


def test_negated_line_does_not_change_other_lines_or_first_winner(monkeypatch) -> None:
    from copy import deepcopy

    from src.bilun.domain.prose_rules import dental_2_4_1 as dental

    ctx = _precious_name_context("altın köprü")
    first = ctx.material_lines[0]
    negative = replace(first, material_line_id="NEGATIVE", material_name="altın içermeyen")
    last = replace(
        first,
        material_line_id="LAST",
        material_name="argenco 23",
        billed_amount_try=Decimal("83.75"),
    )
    expected = dental.check_dental_2_4_1_for_context(replace(ctx, material_lines=(first, last)))
    ruleset = deepcopy(dental.load_dental_2_4_1_rules())
    later = deepcopy(ruleset["rules"][0])
    later["rule_id"] = "test_later_matching_rule"
    ruleset["rules"].append(later)
    monkeypatch.setattr(dental, "load_dental_2_4_1_rules", lambda: ruleset)

    assert dental.check_dental_2_4_1_for_context(
        replace(ctx, material_lines=(first, negative, last))
    ) == expected
    assert [row["risk_amount"] for row in expected] == [125.5, 83.75]


def test_precious_metal_clause_matches_the_verified_official_source_versions() -> None:
    """SGK July/August 2026 DOCX paragraphs 1009/1015 have identical §2.4.1(1).

    Official downloads (both independently fetched on 2026-09-27):
    https://www.sgk.gov.tr/Download/DownloadFile?f=dae9aa86-dbf6-452d-9cd7-d5a937f25425.zip&d=27442b51-e108-4aac-853d-6e03d9704e4e
    https://www.sgk.gov.tr/Download/DownloadFile?f=9afde55e-9207-4432-a54e-3b441f11e70c.zip&d=658f4ba1-b0e8-4dfb-8504-fa0b09e353e0

    This pins the checked text, not applicability to an arbitrary service date.
    """
    import polars as pl

    from src.bilun.domain.constants import SUT_CLAUSES_PATH

    rows = pl.read_parquet(SUT_CLAUSES_PATH).filter(
        (pl.col("clause_key") == "2.4.1.(1)#10e6c764") & pl.col("is_in_force")
    )
    assert rows.height == 1
    assert not rows["is_heading"][0] and not rows["is_amendment"][0]
    assert sha256(rows["in_force_text"][0].encode()).hexdigest() == (
        "10e6c764fd9f71cff7e1f8ef9e1bc5b700da119ac7f82d4916add48143c72ba3"
    )
