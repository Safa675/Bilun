"""EK-3O and EK-1A are read on the service date, not on the day the report runs (#292).

SGK amended EK-3/O from 2026-09-05 (HO1005 2,134.44 -> 2,116.57, HO1017 2,501.30 -> 2,483.43,
HO1034 added) and added G11.3 to EK-1/A from 2018-02-15. Every caller of the dated lookups
passes the line's date (a material line's ``material_date``, the procedure's date for a
material the bill lacks), the claim's date (admission, else start) when the line has none,
and today only when neither exists.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    MaterialClaimLine,
    PatientCopayProfile,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit

BEFORE, LAST_OLD, AMENDED = date(2026, 8, 1), date(2026, 9, 4), date(2026, 9, 5)
# Each set billed at its price on 2026-08-01 (and 2026-09-04) + 20 % KDV.
OLD_BILLED = {"HO1005": "2561.33", "HO1017": "3001.56"}
# The list price and the ceiling (+ 20 % KDV) from 2026-09-05.
NEW_PRICE = {"HO1005": (2116.57, 2539.88), "HO1017": (2483.43, 2980.12)}


def _claim(
    claim_id: str = "C-AFEREZ",
    *,
    admission: date | None = BEFORE,
    start: date = BEFORE,
    end: date | None = None,
    claim_type: str = "yatis",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P-AFEREZ",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="2_3_basamak_ozel",
        provider_type="Ozel",
        department="Hematoloji",
        admission_date=admission,
        discharge_date=end or start,
        claim_start_date=start,
        claim_end_date=end or start,
        primary_icd10="D59.3",
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="",
    )


def _material(
    code: str,
    day: date | None,
    billed: str,
    *,
    claim_id: str = "C-AFEREZ",
    line_id: str | None = None,
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id or f"M-{code}",
        claim_id=claim_id,
        procedure_line_id="PL1",
        patient_id="P-AFEREZ",
        material_date=day,
        material_code=code,  # type: ignore[arg-type]
        material_name="",
        material_type="sarf",
        specialty_category="hematoloji",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(billed),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _proc(day: date, *, claim_id: str = "C-AFEREZ", code: str = "704920") -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="PL1",
        claim_id=claim_id,
        patient_id="P-AFEREZ",
        episode_id="E1",
        procedure_date=day,
        procedure_code=code,
        procedure_name="Terapötik aferez",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _ctx(materials, claims=(), procedures=()) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P-AFEREZ",
        claims=tuple(claims),
        procedure_lines=tuple(procedures),
        material_lines=tuple(materials),
        drug_lines=(),
        diagnoses=(),
    )


def _id(value: object) -> str:
    """A test id that is the same in every xdist worker (a set's repr follows its hash order)."""
    if isinstance(value, (set, frozenset)):
        return "+".join(sorted(value)) or "none-flagged"
    return str(value)


def _apheresis(day: date | None, **kwargs) -> list[MaterialClaimLine]:
    return [_material(code, day, billed, **kwargs) for code, billed in OLD_BILLED.items()]


def _kdv_reviews(ctx: PatientClaimContext) -> dict[str, dict]:
    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims

    return {row["sut_code"]: row for row in precheck_materials_from_claims(ctx).kdv_price_reviews}


# --- KDV price review (§3.1.1(10)) -------------------------------------------------------


@pytest.mark.parametrize("day", [BEFORE, LAST_OLD], ids=str)
def test_an_apheresis_bill_billed_at_its_day_price_has_no_kdv_review(day: date) -> None:
    assert _kdv_reviews(_ctx(_apheresis(day), claims=[_claim(admission=day, start=day)])) == {}


def test_the_same_bill_dated_2026_09_05_flags_both_sets_at_the_new_price() -> None:
    rows = _kdv_reviews(
        _ctx(_apheresis(AMENDED), claims=[_claim(admission=AMENDED, start=AMENDED)])
    )
    assert set(rows) == {"HO1005", "HO1017"}
    for code, (ex_vat, ceiling) in NEW_PRICE.items():
        assert rows[code]["gazette_ex_vat_try"] == pytest.approx(ex_vat)
        assert rows[code]["gazette_ceiling_try"] == pytest.approx(ceiling)
        assert rows[code]["billed_try"] == pytest.approx(float(OLD_BILLED[code]))


def test_each_line_is_read_on_its_own_date_not_on_its_claims() -> None:
    # One stay across the amendment: the claim opens on 2026-08-01, the second set is used on
    # 2026-09-05. Only that line is above its day's ceiling.
    claim = _claim(admission=BEFORE, start=BEFORE, end=AMENDED)
    lines = [
        _material("HO1005", BEFORE, OLD_BILLED["HO1005"], line_id="M-1"),
        _material("HO1005", AMENDED, OLD_BILLED["HO1005"], line_id="M-2"),
    ]
    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims

    rows = precheck_materials_from_claims(_ctx(lines, claims=[claim])).kdv_price_reviews
    assert [row["material_line_id"] for row in rows] == ["M-2"]


@pytest.mark.parametrize("undated", [None, date.min], ids=["none", "date-min"])
@pytest.mark.parametrize(
    "claim_day, flagged",
    [(BEFORE, set()), (LAST_OLD, set()), (AMENDED, {"HO1005", "HO1017"})],
    ids=_id,
)
def test_an_undated_line_is_read_on_its_claims_admission_date(undated, claim_day, flagged) -> None:
    claim = _claim(admission=claim_day, start=claim_day)
    assert set(_kdv_reviews(_ctx(_apheresis(undated), claims=[claim]))) == flagged


@pytest.mark.parametrize(
    "claim_day, flagged", [(BEFORE, set()), (AMENDED, {"HO1005", "HO1017"})], ids=_id
)
def test_an_outpatient_claim_without_admission_lends_its_start_date(claim_day, flagged) -> None:
    claim = _claim(admission=None, start=claim_day, claim_type="poliklinik")
    assert set(_kdv_reviews(_ctx(_apheresis(None), claims=[claim]))) == flagged


@pytest.mark.parametrize("order", [0, 1], ids=["own-claim-first", "own-claim-last"])
def test_an_undated_line_reads_its_own_claim_among_the_patients(order: int) -> None:
    own = _claim("C-OWN", admission=AMENDED, start=AMENDED)
    other = _claim("C-OTHER", admission=BEFORE, start=BEFORE)
    claims = [own, other] if order == 0 else [other, own]
    lines = _apheresis(None, claim_id="C-OWN")
    assert set(_kdv_reviews(_ctx(lines, claims=claims))) == {"HO1005", "HO1017"}
    lines = _apheresis(None, claim_id="C-OTHER")
    assert set(_kdv_reviews(_ctx(lines, claims=claims))) == set()


def test_the_committed_s5_stay_reads_each_set_on_the_day_it_is_used() -> None:
    """S5 (patient 5's hip fracture stay, 2026-09-03..09-08) spans the EK-3/O amendment; its
    committed material lines are dated 2026-09-04. A therapeutic apheresis set added to the bill
    at its 2026-09-04 price + KDV is within the ceiling that day and above it on 2026-09-07."""
    from src.bilun.domain.claims.loader import load_sut_claim_dataset
    from src.bilun.domain.claims.patient_context import build_bill_claim_context
    from tests.fixtures import synthetic_cohort as cohort

    role = cohort.role("showcase_S5")
    ctx = build_bill_claim_context(role.patient_id, role.claim_id, load_sut_claim_dataset())
    assert ctx is not None
    (claim,) = ctx.claims
    assert claim.admission_date < AMENDED <= claim.claim_end_date
    committed = ctx.material_lines[0]
    assert committed.material_date == LAST_OLD
    assert _kdv_reviews(ctx) == {}

    on_the_old_day = replace(
        committed,
        material_line_id="HO-0904",
        material_code="HO1005",
        billed_amount_try=Decimal(OLD_BILLED["HO1005"]),
    )
    on_a_new_day = replace(
        on_the_old_day, material_line_id="HO-0907", material_date=date(2026, 9, 7)
    )
    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims

    result = precheck_materials_from_claims(
        replace(ctx, material_lines=(*ctx.material_lines, on_the_old_day, on_a_new_day))
    )
    assert [row["material_line_id"] for row in result.kdv_price_reviews] == ["HO-0907"]
    assert result.kdv_price_reviews[0]["gazette_ceiling_try"] == pytest.approx(2539.88)


# --- EK-3 catalog membership and the §3.1 material rules ---------------------------------


def _bundling_rules(materials, claims) -> dict[str, str]:
    from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_for_context

    rows = check_material_bundling_for_context(_ctx(materials, claims=claims))
    return {row["material_code"]: row["rule_id"] for row in rows}


@pytest.mark.parametrize(
    "day, rule_id",
    [
        (BEFORE, "3.1.2.(2).not_in_ek3c"),  # not in any EK-3 list that day
        (LAST_OLD, "3.1.2.(2).not_in_ek3c"),
        (AMENDED, "3.1.1.(15).separate_billing_not_authorized"),  # listed, no marker
    ],
    ids=str,
)
def test_ho1034_is_in_the_ek3_catalog_from_2026_09_05_only(day: date, rule_id: str) -> None:
    from src.bilun.domain.materials.catalog_lookup import is_material_in_ek3_catalog

    assert is_material_in_ek3_catalog("HO1034", as_of=day) is (day >= AMENDED)
    line = _material("HO1034", day, "5520.00")
    assert _bundling_rules([line], [_claim(admission=day, start=day)]) == {"HO1034": rule_id}


@pytest.mark.parametrize(
    "claim_day, rule_id",
    [
        (BEFORE, "3.1.2.(2).not_in_ek3c"),
        (AMENDED, "3.1.1.(15).separate_billing_not_authorized"),
    ],
    ids=str,
)
def test_an_undated_ho1034_line_is_checked_on_its_claims_date(
    claim_day: date, rule_id: str
) -> None:
    line = _material("HO1034", date.min, "5520.00")
    assert _bundling_rules([line], [_claim(admission=claim_day, start=claim_day)]) == {
        "HO1034": rule_id
    }


def test_a_validator_line_without_context_reads_the_date_it_carries() -> None:
    from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose

    def rule(day):
        rows = check_material_bundling_prose(
            [{"code": "HO1034", "name": "SPD SET", "unit_price": 5520.0, "material_date": day}]
        )
        return [row["rule_id"] for row in rows]

    assert rule(BEFORE) == ["3.1.2.(2).not_in_ek3c"]
    assert rule(AMENDED) == ["3.1.1.(15).separate_billing_not_authorized"]


def test_the_ek3_definitions_are_read_on_the_lines_date() -> None:
    """``_ek3_definition_frame`` (behind the §3.1.4 items, the EK-3 procedure conditions and the
    EK-2/C açıklama match) holds the rows in force on the day: HO1034 from 2026-09-05."""
    from src.bilun.domain.materials import catalog_lookup as cl

    codes = {
        day: set(cl._ek3_definition_frame(day.isoformat())["sut_code"]) for day in (BEFORE, AMENDED)
    }
    assert "HO1034" not in codes[BEFORE]
    assert "HO1034" in codes[AMENDED]
    assert codes[AMENDED] - codes[BEFORE] == {"HO1034"}
    # HO1000's row was amended on 2026-10-08: one row per day, never both versions.
    for day in ("2026-10-07", "2026-10-08"):
        assert list(cl._ek3_definition_frame(day)["sut_code"]).count("HO1000") == 1

    included = ("Seçici plazma değişimi seti dahildir.",)
    assert cl.ek2c_aciklama_verdict("HO1034", included, as_of=BEFORE) is None
    assert cl.ek2c_aciklama_verdict("HO1034", included, as_of=AMENDED) == "included"
    assert cl.ek3_procedure_condition_codes("HO1034", as_of=BEFORE) == frozenset()
    assert cl.sut_3_1_4_item("HO1034", as_of=BEFORE) is None


def test_a_package_aciklama_names_ho1034_only_where_it_is_listed() -> None:
    from src.bilun.domain.prose_rules.material_bundling import material_paid_next_to_package

    separate = ("Seçici plazma değişimi seti ayrıca faturalandırılır.",)

    def paid(day):
        return material_paid_next_to_package(
            code="HO1034",
            name="",
            package_descriptions=separate,
            procedure_codes=frozenset(),
            as_of=day,
        )

    assert paid(BEFORE) is False
    assert paid(AMENDED) is True


# --- A material the bill lacks (inverse EK-3B-1 uplift) -----------------------------------


@pytest.fixture
def _apheresis_pairing(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.prose_rules import material_uplift

    rule = {
        "rule_id": "pairing.test_704920_ek3o",
        "procedure_codes": ["704920"],
        "expected_material_codes": ["HO1005", "HO1034"],
        "pairing_mode": "specialty_annex",
        "specialty_annex": "EK-3O",
        "sut_section": "3.1.1",
    }
    monkeypatch.setattr(material_uplift, "load_material_pairing_rules", lambda: {"rules": [rule]})


def _uplift(claim: ClaimHeader, proc: ProcedureClaimLine) -> dict[str, dict]:
    from src.bilun.domain.prose_rules.material_uplift import (
        detect_missing_billable_material_opportunities,
    )

    rows = detect_missing_billable_material_opportunities(claim, [proc], [])
    return {row["material_code"]: row for row in rows}


@pytest.mark.usefixtures("_apheresis_pairing")
def test_a_missing_set_is_priced_on_the_procedures_date() -> None:
    before = _uplift(_claim(admission=BEFORE, start=BEFORE), _proc(BEFORE))
    assert set(before) == {"HO1005"}  # HO1034 is not listed yet
    assert before["HO1005"]["list_price_try"] == pytest.approx(2134.44)
    assert before["HO1005"]["ceiling_try"] == pytest.approx(2561.33)

    after = _uplift(_claim(admission=AMENDED, start=AMENDED), _proc(AMENDED))
    assert set(after) == {"HO1005", "HO1034"}
    assert after["HO1005"]["list_price_try"] == pytest.approx(2116.57)
    assert after["HO1005"]["ceiling_try"] == pytest.approx(2539.88)
    assert (after["HO1034"]["list_price_try"], after["HO1034"]["ceiling_try"]) == (4600.0, 5520.0)


@pytest.mark.usefixtures("_apheresis_pairing")
def test_the_procedures_own_date_wins_over_its_claims() -> None:
    rows = _uplift(_claim(admission=BEFORE, start=BEFORE, end=AMENDED), _proc(AMENDED))
    assert rows["HO1005"]["ceiling_try"] == pytest.approx(2539.88)
    assert "HO1034" in rows


@pytest.mark.usefixtures("_apheresis_pairing")
@pytest.mark.parametrize(
    "claim_day, ceiling, listed",
    [
        (BEFORE, 2561.33, False),
        (AMENDED, 2539.88, True),
    ],
    ids=str,
)
def test_an_undated_procedure_lends_its_claims_date(claim_day, ceiling, listed) -> None:
    rows = _uplift(_claim(admission=claim_day, start=claim_day), _proc(date.min))
    assert rows["HO1005"]["ceiling_try"] == pytest.approx(ceiling)
    assert ("HO1034" in rows) is listed


# --- The claim-line pricer of the validator ----------------------------------------------


def test_the_validator_pricer_reads_the_given_date() -> None:
    from src.bilun.domain.analytics.materials import price_material_lines

    def unit(day):
        (line,) = price_material_lines([{"code": "HO1005", "name": "AFEREZ SETİ"}], as_of=day)
        return line.unit_price, line.source

    assert unit(BEFORE) == (2134.44, "ek3_code")
    assert unit(AMENDED) == (2116.57, "ek3_code")
    (missing,) = price_material_lines([{"code": "HO1034", "name": "SPD SET"}], as_of=BEFORE)
    assert missing.source == "ek3_catalog_miss"
    # A line's own date wins over the request's.
    dated = [{"code": "HO1005", "name": "AFEREZ SETİ", "material_date": BEFORE}]
    assert [line.unit_price for line in price_material_lines(dated, as_of=AMENDED)] == [2134.44]


# --- No dated EK-3 read falls back to today when the bill has a date ----------------------


@pytest.mark.usefixtures("_apheresis_pairing")  # the uplift checks HO1005 and HO1034 for 704920
def test_no_ek3_lookup_of_a_dated_bill_is_read_on_today(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
    from src.bilun.domain.materials import catalog_lookup as cl
    from src.bilun.domain.prose_rules import mandated_package_gap, material_uplift
    from src.bilun.domain.prose_rules.material_bundling import (
        check_material_bundling_for_context,
        material_paid_next_to_package,
    )

    real = cl._ek3_version_day  # every dated EK-3 read resolves its day here
    days: list[object] = []

    def spy(as_of):
        days.append(as_of)
        return real(as_of)

    monkeypatch.setattr(cl, "_ek3_version_day", spy)
    claim = _claim(admission=BEFORE, start=BEFORE)
    lines = [
        *_apheresis(BEFORE),
        _material("HO1034", None, "5520.00"),
        _material("OP1106", BEFORE, "252"),
    ]
    ctx = _ctx(lines, claims=[claim], procedures=[_proc(BEFORE)])
    precheck_materials_from_claims(ctx)
    check_material_bundling_for_context(ctx)
    material_uplift.detect_missing_billable_material_opportunities(
        claim, list(ctx.procedure_lines), lines
    )
    # A package without an açıklama: the §3.1.4 item and the açıklama verdict are read too.
    assert days.count(BEFORE) > 0
    before_package = len(days)
    material_paid_next_to_package(
        code="OP1106",
        name="",
        package_descriptions=("",),
        procedure_codes=frozenset({"704920"}),
        as_of=BEFORE,
    )
    assert len(days) >= before_package + 3  # separate-billing marker, procedure condition, verdict
    seen: list[object] = []
    real_paid = mandated_package_gap.material_paid_next_to_package

    def paid_spy(**kwargs):
        seen.append(kwargs.get("as_of"))
        return real_paid(**kwargs)

    monkeypatch.setattr(mandated_package_gap, "material_paid_next_to_package", paid_spy)
    _mandated_gap_with_materials(monkeypatch, mandated_package_gap, lines)
    assert days and None not in days
    assert seen == [BEFORE] * len(lines)


def _mandated_gap_with_materials(monkeypatch, module, lines) -> None:
    """Run ``mandated_package_gap`` over ``lines`` with a stay its scope covers."""
    from types import SimpleNamespace

    claim = _claim(admission=BEFORE, start=BEFORE, end=date(2026, 8, 3))
    scope = SimpleNamespace(
        window_end=date(2026, 8, 3),
        lines=(),
        mandated=(),
        covers_the_stay=True,
        package_total_try=0.0,
        lenient_package_total_try=0.0,
        missing_facts=(),
    )
    monkeypatch.setattr(module, "mandated_package_scope", lambda *_a, **_k: scope)
    module.mandated_package_gap(claim, [], material_lines=lines)


# --- EK-1/A chronic disease exemption -------------------------------------------------------


def _g113_claim(claim_id: str, day: date, *, claim_type: str = "poliklinik") -> ClaimHeader:
    return replace(
        _claim(claim_id, admission=None, start=day, claim_type=claim_type),
        patient_id="P-G113",
        primary_icd10="G11.3",
    )


def _profile() -> PatientCopayProfile:
    return PatientCopayProfile(
        patient_id="P-G113",
        birth_year=1960,
        has_chronic_health_report=True,
    )


@pytest.mark.parametrize(
    "day, exempt",
    [
        (date(2017, 1, 1), False),
        (date(2018, 2, 14), False),
        (date(2018, 2, 15), True),
    ],
    ids=str,
)
def test_a_g113_claim_is_ek1a_exempt_from_2018_02_15(day: date, exempt: bool) -> None:
    from src.bilun.domain.optimization.copay_exemption_context import build_copay_exemption_input
    from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

    inp = build_copay_exemption_input(
        diagnoses=["G11.3"],
        patient_profile=_profile(),
        patient_claims=(_g113_claim("C1", day),),
    )
    assert inp.service_date == day
    result = evaluate_copay_exemption(inp)
    assert result["exempt"] is exempt
    assert bool(result["qualifying_diagnoses"]) is exempt


@pytest.mark.parametrize("order", [0, 1], ids=["latest-first", "latest-last"])
def test_a_patients_input_carries_the_latest_claims_date(order: int) -> None:
    from src.bilun.domain.optimization.copay_exemption_context import build_copay_exemption_input

    claims = [_g113_claim("C-2019", date(2019, 3, 1)), _g113_claim("C-2017", date(2017, 1, 1))]
    inp = build_copay_exemption_input(
        diagnoses=["G11.3"],
        patient_claims=tuple(claims if order == 0 else claims[::-1]),
    )
    assert inp.service_date == date(2019, 3, 1)
    # An inpatient claim's date is its admission date.
    stay = replace(
        _g113_claim("C-STAY", date(2019, 5, 2), claim_type="yatis"), admission_date=date(2019, 5, 1)
    )
    assert build_copay_exemption_input(diagnoses=[], patient_claims=(stay,)).service_date == date(
        2019, 5, 1
    )
    assert build_copay_exemption_input(diagnoses=[]).service_date is None


def test_the_ek1a_index_is_read_on_the_inputs_date(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.bilun.domain.optimization import copay_exemptions
    from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput

    seen: list[object] = []

    def ek1a(diagnoses, **kwargs):
        seen.append(kwargs.get("as_of", "missing"))
        return None

    monkeypatch.setattr(copay_exemptions, "evaluate_ek1a_exemption", ek1a)
    copay_exemptions.evaluate_copay_exemption(
        CopayExemptionInput(diagnoses=["G11.3"], service_date=date(2017, 1, 1))
    )
    assert seen == [date(2017, 1, 1)]


def _g113_dataset(order: int):
    from dataclasses import fields

    from src.bilun.domain.claims.dataset import SUTClaimDataset

    claims = (_g113_claim("C-2017", date(2017, 1, 1)), _g113_claim("C-2019", date(2019, 3, 1)))
    claims = claims if order == 0 else claims[::-1]
    empty = {field.name: {} for field in fields(SUTClaimDataset)}
    return SUTClaimDataset(
        **{
            **empty,
            "medula_rejection_ingest_available": False,
            "claims": {claim.claim_id: claim for claim in claims},
            "claims_by_patient": {"P-G113": claims},
            "copay_profiles_by_patient": {"P-G113": _profile()},
        }
    )


@pytest.mark.parametrize("order", [0, 1], ids=["2017-first", "2017-last"])
def test_the_aggregator_reads_each_bill_on_its_own_date(monkeypatch, order: int) -> None:
    import polars as pl

    from src.bilun.domain.optimization import aggregator

    dataset = _g113_dataset(order)
    warmed: list[object] = []
    real_index = aggregator._get_ek1a_by_letter

    def warm(as_of=None):
        warmed.append(as_of)
        return real_index(as_of)

    monkeypatch.setattr(aggregator, "_get_ek1a_by_letter", warm)
    summary = aggregator.compute_optimization_summary(
        pl.DataFrame({"patient_id": ["P-G113"]}),
        ["P-G113"],
        diagnoses_by_pid={"P-G113": ["G11.3"]},
        claim_dataset=dataset,
    )
    copay = summary["copay_exemptions"]
    # The patient is exempt as of the latest bill; of the two bills, only the 2019 one.
    assert copay["n_exempt_ek1a_patients"] == 1
    assert (copay["n_total_bills"], copay["n_exempt_bills"], copay["n_exempt_ek1a_bills"]) == (
        2,
        1,
        1,
    )
    assert set(warmed) == {date(2017, 1, 1), date(2019, 3, 1)}
    assert None not in warmed


# --- One cache entry per list version, not per day -----------------------------------------


@pytest.fixture
def _dated_list(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import polars as pl

    from src.bilun.domain.materials import catalog_lookup as cl

    path = tmp_path / "ek3x_test_materials.parquet"
    pl.DataFrame(
        {
            "sut_code": ["XX0001", "XX0002", "XX0003"],
            "material_name": ["REPEALED", "ADDED", "UNDATED"],
            "price_try": [100.0, 200.0, 300.0],
            "valid_from": [None, "2026-05-01", None],
            "valid_to": ["2026-03-31", None, None],
        },
        schema_overrides={"valid_from": pl.Utf8, "valid_to": pl.Utf8},
    ).write_parquet(path)
    caches = (cl._ek3_change_days, cl._build_ek3_price_index)
    for cache in caches:
        cache.cache_clear()
    monkeypatch.setattr(cl, "_all_ek3_catalog_paths", lambda: (path,))
    yield cl
    for cache in caches:
        cache.cache_clear()


def test_a_repealed_row_ends_and_an_added_row_starts_on_their_days(_dated_list) -> None:
    cl = _dated_list
    assert cl._ek3_change_days() == ("2026-04-01", "2026-05-01")
    price = cl.lookup_ek3_list_price_try
    assert (price("XX0001", "2026-03-31"), price("XX0001", "2026-04-01")) == (100.0, None)
    assert (price("XX0002", "2026-04-30"), price("XX0002", "2026-05-01")) == (None, 200.0)
    assert {price("XX0003", day) for day in ("2017-01-01", "2026-04-15", "2030-01-01")} == {300.0}
    assert [cl._ek3_version_day(day) for day in ("2026-03-31", "2026-04-01", "2026-04-30")] == [
        "0001-01-01",
        "2026-04-01",
        "2026-04-01",
    ]


def test_every_day_of_a_version_shares_one_index(_dated_list) -> None:
    cl = _dated_list
    for day in range(1, 31):
        cl.lookup_ek3_list_price_try("XX0003", date(2026, 4, day))
    assert cl._build_ek3_price_index.cache_info().currsize == 1
    cl.lookup_ek3_list_price_try("XX0003", date(2026, 5, 1))
    cl.lookup_ek3_list_price_try("XX0003", date(2026, 3, 1))
    assert cl._build_ek3_price_index.cache_info().currsize == 3


def test_the_ek1a_index_is_built_once_per_list_version() -> None:
    from src.bilun.domain.optimization.copay_exemption_rules import ek1a

    index = ek1a._get_ek1a_by_letter
    # G11.3 is added on 2018-02-15: the days before share one index, that day starts the next.
    assert index(date(2017, 1, 1)) is index(date(2018, 2, 14))
    assert index(date(2018, 2, 15)) is index("2026-10-24")
    assert index(date(2018, 2, 14)) is not index(date(2018, 2, 15))
    assert ek1a.evaluate_ek1a_exemption(["G11.3"], as_of=date(2018, 2, 14)) is None
    assert ek1a.evaluate_ek1a_exemption(["G11.3"], as_of=date(2018, 2, 15)) is not None


def test_a_null_validity_cell_is_no_change_day() -> None:
    import pandas as pd

    from src.bilun.domain.loaders.validity import FIRST_VERSION_DAY, change_days, version_day

    frame = pd.DataFrame(
        {
            "valid_from": [None, "2018-02-15", pd.NA, float("nan")],
            "valid_to": ["2020-12-31", None, pd.NA, "2021-06-30T00:00:00"],
        }
    )
    changes = change_days(frame["valid_from"], frame["valid_to"])
    assert changes == ("2018-02-15", "2021-01-01", "2021-07-01")
    assert [version_day(changes, day) for day in ("2018-02-14", "2020-12-31", "2021-01-01")] == [
        FIRST_VERSION_DAY,
        "2018-02-15",
        "2021-01-01",
    ]
