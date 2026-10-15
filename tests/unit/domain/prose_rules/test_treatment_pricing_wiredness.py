"""W3 wiredness tests — newly-surfaced predicates & context keys.

Covers the three wiring tasks:

* TASK 1 — ``procedure_in_annex`` predicate (EK-2/A-2, EK-2/C-1) recognized in
  both the gap_closing engine (which evaluates ``payment_method_2_2.json``) and
  the treatment_pricing engine.
* TASK 2 — 18 derivable FTR context keys surfaced by
  ``_build_treatment_pricing_context`` (sessions, specialties, ranges, …), plus
  the numeric range predicate (``{"min": x}``) and ``diagnosis_not_in`` /
  ``diagnosis_category_not_in`` negation handling.
* TASK 3 — HBO keys (``indication_in_ek2d3``, ``indication_is_emergency_listed``,
  ``origin_is_traffic_accident``) backed by the EK-2/D-3 indication-map loader.

Tests use real entries from ``treatment_pricing_2_4.json`` /
``payment_method_2_2.json`` so they stay honest if the JSON changes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.catalog_membership import (
    any_procedure_in_annex,
    codes_in_annex,
    get_ek2a2_codes,
    get_ek2d3_emergency_icd10_codes,
    get_ek2d3_icd10_codes,
    load_ek2d3_indication_map,
)
from src.bilun.domain.prose_rules.gap_closing import _condition_matches as gap_condition_matches
from src.bilun.domain.prose_rules.treatment_pricing import (
    _build_treatment_pricing_context,
    _condition_matches as tp_condition_matches,
    _icd10_categories,
    check_treatment_pricing_for_context,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "ayakta",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    department: str = "genel",
    primary_icd10: str = "Z00.0",
    scenario_tag: str = "test",
    occupational_context: str = "none",
    claim_start_date: date | None = None,
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type=provider_type,
        department=department,
        admission_date=None,
        discharge_date=None,
        claim_start_date=claim_start_date or date.today(),
        claim_end_date=date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
        occupational_context=occupational_context,
    )


def _make_procedure(
    *,
    code: str = "P915001",
    category: str = "physiotherapy_rehab",
    claim_id: str = "C1",
    procedure_date: date | None = None,
    specialty: str = "physical_medicine_rehabilitation",
    line_id: str = "PL1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date or date.today(),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=specialty,
    )


def _make_ctx(
    *,
    header: ClaimHeader | None = None,
    procedure_lines: tuple[ProcedureClaimLine, ...] = (),
    diagnoses: tuple[ClaimDiagnosis, ...] = (),
) -> PatientClaimContext:
    h = header or _make_header()
    return PatientClaimContext(
        patient_id="P1",
        claims=(h,),
        procedure_lines=procedure_lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=diagnoses,
    )


# ===========================================================================
# TASK 1 — procedure_in_annex predicate + EK-2/A-2 loader
# ===========================================================================


class TestProcedureInAnnexLoader:
    """The EK-2/A-2 snapshot loader and the codes_in_annex router."""

    def test_ek2a2_codes_loaded(self) -> None:
        codes = get_ek2a2_codes()
        assert len(codes) > 0, "EK-2/A-2 snapshot must load non-empty code set"

    def test_codes_in_annex_routes_known_annexes(self) -> None:
        assert len(codes_in_annex("EK-2/A-2")) > 0
        assert len(codes_in_annex("EK-2/B")) > 0
        assert len(codes_in_annex("EK-2/C")) > 0
        assert len(codes_in_annex("EK-2/C-1")) > 0

    def test_codes_in_annex_unknown_returns_empty(self) -> None:
        assert codes_in_annex("EK-9/Z") == frozenset()

    def test_any_procedure_in_annex_normalizes_p_prefix(self) -> None:
        """A claim code ``P552001`` resolves to ``552001`` for EK-2/C membership."""
        # 552001 is a known EK-2/C code (birinci basamak yoğun bakım).
        assert any_procedure_in_annex(["P552001"], "EK-2/C") is True
        assert any_procedure_in_annex(["P999999"], "EK-2/C") is False

    def test_any_procedure_in_annex_empty_annex(self) -> None:
        assert any_procedure_in_annex(["123456"], "EK-9/Z") is False


class TestProcedureInAnnexPredicateGapClosing:
    """The gap_closing engine evaluates payment_method_2_2.json rules."""

    def test_predicate_matches_when_code_in_annex(self) -> None:
        cond = {"procedure_in_annex": "EK-2/A-2"}
        a2_code = next(iter(get_ek2a2_codes()))
        ctx = {"procedure_code_any": [a2_code]}
        assert gap_condition_matches(cond, ctx) is True

    def test_predicate_no_match_when_code_absent(self) -> None:
        cond = {"procedure_in_annex": "EK-2/A-2"}
        ctx = {"procedure_code_any": ["999999"]}
        assert gap_condition_matches(cond, ctx) is False

    def test_predicate_honest_skip_when_codes_missing(self) -> None:
        cond = {"procedure_in_annex": "EK-2/A-2"}
        assert gap_condition_matches(cond, {}) is False

    def test_predicate_honest_skip_when_annex_empty(self) -> None:
        cond = {"procedure_in_annex": ""}
        ctx = {"procedure_code_any": ["123456"]}
        assert gap_condition_matches(cond, ctx) is False


class TestProcedureInAnnexPredicateTreatmentPricing:
    """The treatment_pricing engine also recognizes the predicate (parity)."""

    def test_predicate_matches(self) -> None:
        cond = {"procedure_in_annex": "EK-2/C"}
        ctx = {"procedure_code_any": ["P552001"]}
        assert tp_condition_matches(cond, ctx) is True


# ===========================================================================
# TASK 2 — 18 derivable FTR context keys + range/diagnosis_not_in handling
# ===========================================================================


class TestFtrContextKeys:
    """The 18 newly-surfaced FTR keys appear in the built context."""

    def test_ftr_session_keys_surfaced(self) -> None:
        today = date.today()
        procs = (
            _make_procedure(code="P915001", procedure_date=today, line_id="PL1"),
            _make_procedure(code="P915002", procedure_date=today, line_id="PL2"),
        )
        ctx = _make_ctx(
            header=_make_header(claim_start_date=today - timedelta(days=5)),
            procedure_lines=procs,
        )
        context = _build_treatment_pricing_context(ctx)
        # Two FTR lines on one date → sessions_per_day=2, same_day_physio_rehab
        assert context["sessions_per_day"] == 2
        assert context["sessions"] == 1
        assert context["same_day_physio_rehab"] is True

    def test_specialty_keys_surfaced(self) -> None:
        proc = _make_procedure(specialty="physical_medicine_rehabilitation")
        ctx = _make_ctx(procedure_lines=(proc,))
        context = _build_treatment_pricing_context(ctx)
        assert context["prescriber_specialty_any"] == ["physical_medicine_rehabilitation"]
        assert context["supervised_by_pmr_specialty"] is True

    def test_concomitant_service_when_non_ftr_same_day(self) -> None:
        today = date.today()
        procs = (
            _make_procedure(code="P915001", category="physiotherapy_rehab", procedure_date=today, line_id="PL1"),
            _make_procedure(code="P500100", category="hemodialysis", procedure_date=today, line_id="PL2"),
        )
        ctx = _make_ctx(procedure_lines=procs)
        context = _build_treatment_pricing_context(ctx)
        assert context["concomitant_service"] is True
        assert context["billed_with_other_physiotherapy"] is True

    def test_visit_type_and_treatment_setting(self) -> None:
        ctx = _make_ctx(header=_make_header(claim_type="yatis"))
        context = _build_treatment_pricing_context(ctx)
        assert context["visit_type"] == "inpatient"
        assert context["treatment_setting"] == "inpatient"

    def test_days_from_report_to_treatment(self) -> None:
        today = date.today()
        proc = _make_procedure(procedure_date=today)
        ctx = _make_ctx(
            header=_make_header(claim_start_date=today - timedelta(days=7)),
            procedure_lines=(proc,),
        )
        context = _build_treatment_pricing_context(ctx)
        assert context["days_from_report_to_treatment"] == 7

    def test_daily_exams_per_physician(self) -> None:
        today = date.today()
        procs = (
            _make_procedure(code="P915001", procedure_date=today, line_id="PL1"),
            _make_procedure(code="P915002", procedure_date=today, line_id="PL2"),
            _make_procedure(code="P915003", procedure_date=today, line_id="PL3"),
        )
        ctx = _make_ctx(procedure_lines=procs)
        context = _build_treatment_pricing_context(ctx)
        assert context["daily_exams_per_physician"] == 3

    def test_annual_session_count_approximations(self) -> None:
        d1 = date.today()
        d2 = d1 - timedelta(days=1)
        procs = (
            _make_procedure(code="P915001", procedure_date=d1, line_id="PL1"),
            _make_procedure(code="P915002", procedure_date=d2, line_id="PL2"),
        )
        ctx = _make_ctx(procedure_lines=procs)
        context = _build_treatment_pricing_context(ctx)
        assert context["sessions_within_year"] == 2
        assert context["sessions_same_region_within_1y"] == 2
        assert context["sessions_per_patient_per_year"] == 2

    def test_diagnosis_category_any_from_icd10(self) -> None:
        """A billed S82 fracture maps to the 'fracture' clinical category."""
        assert "fracture" in _icd10_categories(["S82.0"])
        assert "amputation" in _icd10_categories(["Z89.0"])
        assert _icd10_categories(["E11.9"]) == set()


class TestRangePredicate:
    """Numeric range predicates ({min}/{max}) evaluate surfaced scalars."""

    def test_range_min_satisfied(self) -> None:
        assert tp_condition_matches({"sessions_per_day": {"min": 2}}, {"sessions_per_day": 2}) is True

    def test_range_min_not_satisfied(self) -> None:
        assert tp_condition_matches({"sessions_per_day": {"min": 3}}, {"sessions_per_day": 2}) is False

    def test_range_min_max_band(self) -> None:
        cond = {"sessions": {"min": 1, "max": 30}}
        assert tp_condition_matches(cond, {"sessions": 15}) is True
        assert tp_condition_matches(cond, {"sessions": 0}) is False
        assert tp_condition_matches(cond, {"sessions": 31}) is False

    def test_range_honest_skips_unsurfaced_key(self) -> None:
        """A range on a key NOT in context → honest skip (W2.5 honesty guard)."""
        assert tp_condition_matches({"bmi": {"min": 30}}, {"procedure_category": "ivf"}) is False


class TestDiagnosisNotIn:
    """diagnosis_not_in uses ICD-10 prefix matching with negation."""

    def test_diagnosis_not_in_passes_when_outside(self) -> None:
        """M54.5 is not G80 → diagnosis_not_in [G80] passes."""
        ctx = {"diagnosis_codes": ["M54.5"]}
        assert tp_condition_matches({"diagnosis_not_in": ["G80"]}, ctx) is True

    def test_diagnosis_not_in_fails_when_inside(self) -> None:
        """G80.1 matches G80 prefix → diagnosis_not_in [G80] fails."""
        ctx = {"diagnosis_codes": ["G80.1"]}
        assert tp_condition_matches({"diagnosis_not_in": ["G80"]}, ctx) is False


class TestFtrRuleFiresEndToEnd:
    """End-to-end: real FTR rules fire on the newly-wired context."""

    def test_physio_session_cap_per_day_fires(self) -> None:
        """Real rule ``2.4.4.F-2.(4).physio_session_cap_per_day`` fires on a
        2-session/day FTR claim whose diagnosis is not G80."""
        today = date.today()
        procs = (
            _make_procedure(code="P915001", procedure_date=today, line_id="PL1"),
            _make_procedure(code="P915002", procedure_date=today, line_id="PL2"),
        )
        ctx = _make_ctx(
            header=_make_header(primary_icd10="M54.5"),
            procedure_lines=procs,
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert "2.4.4.F-2.(4).physio_session_cap_per_day" in ids

    def test_physio_start_within_15d_does_not_fire_under_window(self) -> None:
        """Real rule ``2.4.4.F-2.(7).physio_start_within_15d`` gates on
        ``days_from_report_to_treatment: {min: 16}`` — 7 days must NOT fire."""
        today = date.today()
        proc = _make_procedure(procedure_date=today)
        ctx = _make_ctx(
            header=_make_header(claim_start_date=today - timedelta(days=7)),
            procedure_lines=(proc,),
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert "2.4.4.F-2.(7).physio_start_within_15d" not in ids

    def test_physio_start_within_15d_fires_over_window(self) -> None:
        """Same rule, 20-day gap → fires."""
        today = date.today()
        proc = _make_procedure(procedure_date=today)
        ctx = _make_ctx(
            header=_make_header(claim_start_date=today - timedelta(days=20)),
            procedure_lines=(proc,),
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert "2.4.4.F-2.(7).physio_start_within_15d" in ids


# ===========================================================================
# TASK 3 — HBO context keys + EK-2/D-3 loader
# ===========================================================================


class TestEk2d3Loader:
    """The EK-2/D-3 HBO indication-map loader."""

    def test_indication_map_loaded(self) -> None:
        m = load_ek2d3_indication_map()
        assert len(m) > 0, "EK-2/D-3 map must load"
        # T58 (CO poisoning) is a known entry with session data.
        assert "T58" in m
        entry = m["T58"]
        assert entry["is_emergency"] is True
        assert entry["initial_sessions"] == 5

    def test_icd10_codes_set(self) -> None:
        codes = get_ek2d3_icd10_codes()
        assert len(codes) > 0
        assert "T70.3" in codes  # decompression sickness

    def test_emergency_codes_subset(self) -> None:
        all_codes = get_ek2d3_icd10_codes()
        emergency = get_ek2d3_emergency_icd10_codes()
        assert emergency.issubset(all_codes)
        assert "T58" in emergency  # CO poisoning = emergency
        assert "M87.0" not in emergency  # osteonekrosis = non-emergency


class TestHboContextKeys:
    """HBO keys are surfaced from the diagnosis + header data."""

    def test_indication_in_ek2d3_true(self) -> None:
        ctx = _make_ctx(
            header=_make_header(primary_icd10="T58"),
            procedure_lines=(_make_procedure(code="P530010", category="hyperbaric_oxygen"),),
        )
        context = _build_treatment_pricing_context(ctx)
        assert context["indication_in_ek2d3"] is True
        assert context["indication_is_emergency_listed"] is True

    def test_indication_in_ek2d3_false(self) -> None:
        ctx = _make_ctx(
            header=_make_header(primary_icd10="J00"),
            procedure_lines=(_make_procedure(code="P530010", category="hyperbaric_oxygen"),),
        )
        context = _build_treatment_pricing_context(ctx)
        assert context["indication_in_ek2d3"] is False

    @pytest.mark.parametrize("field", ["occupational_context", "claim_type"])
    @pytest.mark.parametrize("value", ["trafik_kazasi", "traffic_accident", "Trafik Kazası"])
    def test_origin_is_traffic_accident_from_explicit_value(self, field: str, value: str) -> None:
        ctx = _make_ctx(header=_make_header(**{field: value}))
        context = _build_treatment_pricing_context(ctx)
        assert context["origin_is_traffic_accident"] is True

    @pytest.mark.parametrize(
        "field", ["occupational_context", "claim_type", "department", "scenario_tag"]
    )
    @pytest.mark.parametrize("value", ["is_kazasi", "iş kazası", "is kazasi"])
    def test_work_accident_is_not_traffic_origin(self, field: str, value: str) -> None:
        """#268: "kaza" inside a work accident does not make it traffic."""
        ctx = _make_ctx(header=_make_header(**{field: value}))
        context = _build_treatment_pricing_context(ctx)
        assert context["origin_is_traffic_accident"] is False

    def test_scenario_tag_does_not_set_traffic_origin(self) -> None:
        """scenario_tag is synthetic-only and never read (#239, #268)."""
        ctx = _make_ctx(header=_make_header(scenario_tag="trafik_kazasi"))
        context = _build_treatment_pricing_context(ctx)
        assert context["origin_is_traffic_accident"] is False

    def test_origin_is_traffic_accident_false_default(self) -> None:
        ctx = _make_ctx(header=_make_header(scenario_tag="routine"))
        context = _build_treatment_pricing_context(ctx)
        assert context["origin_is_traffic_accident"] is False


class TestHboRuleFiresEndToEnd:
    """End-to-end: real HBO rules fire on the newly-wired context."""

    def test_hbo_traffic_accident_rule_fires(self) -> None:
        """Real rule ``2.4.4.B.(13).hbo_traffic_accident_no_session_limit``."""
        today = date.today()
        ctx = _make_ctx(
            header=_make_header(
                claim_type="yatis",
                primary_icd10="S82.0",
                occupational_context="traffic_accident",
            ),
            procedure_lines=(_make_procedure(code="P530010", category="hyperbaric_oxygen"),),
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert "2.4.4.B.(13).hbo_traffic_accident_no_session_limit" in ids

    def test_hbo_start_gap_rule_fires(self) -> None:
        """Real rule ``2.4.4.B.(6).hbo_start_10d_gap_7_biz_days`` (min: 11)."""
        today = date.today()
        ctx = _make_ctx(
            header=_make_header(
                primary_icd10="T58",
                claim_start_date=today - timedelta(days=15),
            ),
            procedure_lines=(_make_procedure(code="P530010", category="hyperbaric_oxygen"),),
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert "2.4.4.B.(6).hbo_start_10d_gap_7_biz_days" in ids


class TestTrafficOriginRulesEndToEnd:
    """#268: the traffic-origin HBO / FTR rules fire for a traffic accident
    and stay silent for a work accident."""

    # (procedure code, category, primary ICD-10, rule id); the HBO case is the
    # #268 claim (P702590, decompression sickness T70.3).
    _HBO = (
        "P702590",
        "hyperbaric_oxygen",
        "T70.3",
        "2.4.4.B.(13).hbo_traffic_accident_no_session_limit",
    )
    _FTR = (
        "P915001",
        "physiotherapy_rehab",
        "S82.0",
        "2.4.4.F-2.(10).traffic_accident_physio_controls_isolated",
    )

    @pytest.mark.parametrize(("code", "category", "icd10", "rule_id"), [_HBO, _FTR])
    @pytest.mark.parametrize(
        ("occupational_context", "fires"),
        [
            ("trafik_kazasi", True),
            ("traffic_accident", True),
            ("is_kazasi", False),
            ("iş kazası", False),
            ("is kazasi", False),
        ],
    )
    def test_rule_fires_only_for_traffic_accident(
        self,
        code: str,
        category: str,
        icd10: str,
        rule_id: str,
        occupational_context: str,
        fires: bool,
    ) -> None:
        ctx = _make_ctx(
            header=_make_header(
                claim_type="yatis", primary_icd10=icd10, occupational_context=occupational_context
            ),
            procedure_lines=(_make_procedure(code=code, category=category),),
        )
        ids = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx)}
        assert (rule_id in ids) is fires

    @pytest.mark.parametrize("occupational_context", ["none", "is_kazasi", "trafik_kazasi"])
    def test_scenario_tag_changes_no_rule_output(self, occupational_context: str) -> None:
        """Blanking the synthetic-only scenario_tag changes no output (#239)."""
        code, category, icd10, _ = self._HBO
        outputs = [
            check_treatment_pricing_for_context(
                _make_ctx(
                    header=_make_header(
                        claim_type="yatis",
                        primary_icd10=icd10,
                        occupational_context=occupational_context,
                        scenario_tag=tag,
                    ),
                    procedure_lines=(_make_procedure(code=code, category=category),),
                )
            )
            for tag in ("", "trafik_kazasi", "is_kazasi")
        ]
        assert outputs[0] == outputs[1] == outputs[2]
