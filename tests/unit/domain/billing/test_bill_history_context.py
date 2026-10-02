"""Bill outputs stay local while dated predicates retain known patient history."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from itertools import permutations
from types import SimpleNamespace

import pytest

from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.billing.claim_yatak_icu_overlap import reconcile_yatak_icu_overlap
from src.bilun.domain.billing.claim_yatak_puani import recommend_yatak_puani_from_claims
from src.bilun.domain.billing.focused_legacy_materializer import FocusedLegacyMaterializer
from src.bilun.domain.billing.focused_rule_projection import project_focused_legacy_rows
from src.bilun.domain.billing.miat_interval import check_miat_interval_violation
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.sct_temporal_window import (
    detect_sct_temporal_window_violations_for_context,
)
from tests.unit._helpers.catalog_stubs import install_yatak_catalog_stub
from tests.unit.domain.billing.test_claim_materials_precheck import _material_line
from tests.unit.domain.billing.test_focused_rule_projection import _header, _procedure
from tests.unit.domain.prose_rules.test_yatak_icu_overlap import (
    _make_claim_header,
    _make_proc_line,
)

pytestmark = pytest.mark.unit
_DAY = date(2026, 7, 13)


def _context(claims, procedures=(), materials=()):
    return PatientClaimContext("P1", tuple(claims), tuple(procedures), tuple(materials), (), ())


def _materials_context(gap=30):
    prior = replace(
        _material_line(claim_id="PRIOR", line_id="prior", material_date=_DAY), patient_id="P1"
    )
    current = replace(
        _material_line(
            claim_id="CURRENT", line_id="current", material_date=_DAY + timedelta(days=gap)
        ),
        patient_id="P1",
    )
    return _context([_header("PRIOR"), _header("CURRENT")], materials=[prior, current]), current


def _icu_context(billed="0.00"):
    return _context(
        [
            _make_claim_header(claim_id="ICU"),
            _make_claim_header(
                claim_id="SRV",
                admission=_DAY,
                discharge=_DAY + timedelta(days=2),
                department="genel_cerrahi",
            ),
        ],
        [
            _make_proc_line(claim_id="ICU", procedure_line_id="icu"),
            _make_proc_line(
                claim_id="SRV",
                procedure_line_id="bed",
                procedure_code="510010",
                procedure_date=_DAY,
                billed_amount_try=billed,
            ),
        ],
    )


def test_bill_miat_retains_prior_use_without_emitting_prior_material(monkeypatch):
    from src.bilun.domain.billing import claim_materials

    monkeypatch.setattr(claim_materials, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(
        claim_materials, "_get_ek3c2_miat", lambda: [{"sut_code": "OP1000", "miat_period": "6 ay"}]
    )
    ctx, current = _materials_context()
    bill = ctx.slice_for_claim("CURRENT")
    assert bill.material_lines == (current,)
    hit = check_miat_interval_violation(bill, current, miat_period="6 ay")
    assert hit is not None
    assert hit["last_use_date"] == _DAY.isoformat()
    result = precheck_materials_from_claims(bill)
    assert [row["claim_id"] for row in result.miat_interval_violations] == ["CURRENT"]
    assert result.miat_restricted == []


def test_bill_icu_history_reconciles_only_service_money(monkeypatch):
    install_yatak_catalog_stub(monkeypatch, daily_rate_try=100)
    ctx = _icu_context()
    bill = ctx.slice_for_claim("SRV")
    result = reconcile_yatak_icu_overlap(bill, recommend_yatak_puani_from_claims(bill))
    assert [row["claim_id"] for row in result.opportunities] == ["SRV"]
    assert result.opportunities[0]["bed_days"] == 2
    assert result.opportunities[0]["expected_yatak_try"] == 200


@pytest.mark.parametrize(
    "category,rule_id,days",
    [
        ("muayene", "tablo15_2_duplicate_exam_10day", 10),
        ("laboratuvar", "tablo15_12_duplicate_test", 7),
    ],
)
def test_bill_duplicate_checks_preserve_prior_evidence(category, rule_id, days):
    ctx = _context(
        [_header("PRIOR"), _header("CURRENT")],
        [
            replace(_procedure("prior", "PRIOR"), procedure_category=category, procedure_date=_DAY),
            replace(
                _procedure("current", "CURRENT"),
                procedure_category=category,
                procedure_date=_DAY + timedelta(days=days),
            ),
        ],
    )
    bill = ctx.slice_for_claim("CURRENT")
    rows = [row for row in FocusedLegacyMaterializer(bill).all_rows() if row["rule_id"] == rule_id]
    assert len(rows) == 1
    assert rows[0]["claim_id"] == "CURRENT"
    projected = project_focused_legacy_rows("P1", bill, rows)
    assert not any(
        row.reason == "cross_claim_history_evidence_unavailable" for row in projected.evaluations
    )
    assert not any(
        row["rule_id"] == rule_id
        for row in FocusedLegacyMaterializer(ctx.slice_for_claim("PRIOR")).all_rows()
    )


def test_bill_sct_does_not_lose_qualifying_prior_transplant():
    ctx = _context(
        [_header("PRIOR"), _header("CURRENT")],
        [
            replace(_procedure("bmt", "PRIOR"), procedure_code="704970", procedure_date=_DAY),
            replace(
                _procedure("sct", "CURRENT"),
                procedure_code="704981",
                procedure_date=_DAY + timedelta(days=60),
            ),
        ],
    )
    assert detect_sct_temporal_window_violations_for_context(ctx) == []
    assert detect_sct_temporal_window_violations_for_context(ctx.slice_for_claim("CURRENT")) == []


@pytest.mark.parametrize(
    "gap,hit", [(-1, False), (0, False), (1, True), (179, True), (180, False), (181, False)]
)
def test_miat_event_date_boundaries(gap, hit):
    ctx, current = _materials_context(gap)
    bill = ctx.slice_for_claim("CURRENT")
    assert (check_miat_interval_violation(bill, current, miat_period="6 ay") is not None) is hit
    # Both the unsliced and explicitly no-history bill continue to work.
    assert check_miat_interval_violation(
        ctx, current, miat_period="6 ay"
    ) == check_miat_interval_violation(bill, current, miat_period="6 ay")
    assert (
        check_miat_interval_violation(
            replace(bill, patient_history=None), current, miat_period="6 ay"
        )
        is None
    )


@pytest.mark.parametrize("unknown", [None, date.min])
def test_miat_unknown_historical_and_target_dates_are_not_evidence(unknown):
    ctx, current = _materials_context()
    prior = replace(ctx.material_lines[0], material_date=unknown)
    changed = replace(ctx, material_lines=(prior, current)).slice_for_claim("CURRENT")
    assert check_miat_interval_violation(changed, current, miat_period="6 ay") is None
    assert (
        check_miat_interval_violation(
            ctx.slice_for_claim("CURRENT"),
            replace(current, material_date=unknown),
            miat_period="6 ay",
        )
        is None
    )


def test_miat_prose_retains_history_when_filtering_unknown_active_date(monkeypatch):
    from src.bilun.domain.prose_rules import material_miat_ek3c2 as prose

    monkeypatch.setattr(
        prose, "_get_ek3c2_miat", lambda: [{"sut_code": "OP1000", "miat_period": "6 ay"}]
    )
    ctx, current = _materials_context()
    bill = ctx.slice_for_claim("CURRENT")
    unknown = replace(current, material_line_id="unknown", material_date=None)
    result = prose.check_material_miat_for_context(replace(bill, material_lines=(current, unknown)))
    assert [row["details"]["material_line_id"] for row in result] == ["current"]
    assert result[0]["details"]["last_use_date"] == _DAY.isoformat()


@pytest.mark.parametrize(
    "category,rule_id,window",
    [
        ("muayene", "tablo15_2_duplicate_exam_10day", 10),
        ("laboratuvar", "tablo15_12_duplicate_test", 7),
    ],
)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_duplicate_boundaries_and_future_events(category, rule_id, window, offset):
    # Equal-date ordering remains the detectors' existing claim-ID ordering.
    for gap in (-1, 0, window + offset):
        ctx = _context(
            [_header("A"), _header("B")],
            [
                replace(_procedure("a", "A"), procedure_category=category, procedure_date=_DAY),
                replace(
                    _procedure("b", "B"),
                    procedure_category=category,
                    procedure_date=_DAY + timedelta(days=gap),
                ),
            ],
        )
        expected = [
            row
            for row in FocusedLegacyMaterializer(ctx).all_rows()
            if row.get("rule_id") == rule_id and row["claim_id"] == "B"
        ]
        actual = [
            row
            for row in FocusedLegacyMaterializer(ctx.slice_for_claim("B")).all_rows()
            if row.get("rule_id") == rule_id
        ]
        assert actual == expected
        assert bool(actual) is (0 <= gap <= window)


@pytest.mark.parametrize("gap,qualifies", [(-1, False), (0, True), (60, True), (61, False)])
def test_sct_boundary_and_future_primary(gap, qualifies):
    ctx = _context(
        [_header("A"), _header("B")],
        [
            replace(_procedure("bmt", "A"), procedure_code="704970", procedure_date=_DAY),
            replace(
                _procedure("sct", "B"),
                procedure_code="704981",
                procedure_date=_DAY + timedelta(days=gap),
            ),
        ],
    )
    rows = detect_sct_temporal_window_violations_for_context(ctx.slice_for_claim("B"))
    assert bool(rows) is not qualifies
    assert all(row["claim_id"] == "B" for row in rows)


@pytest.mark.parametrize("unknown", [None, date.min])
def test_sct_unknown_historical_date_does_not_qualify(unknown):
    ctx = _context(
        [_header("A"), _header("B")],
        [
            replace(_procedure("bmt", "A"), procedure_code="704970", procedure_date=unknown),
            replace(_procedure("sct", "B"), procedure_code="704981", procedure_date=_DAY),
        ],
    )
    rows = detect_sct_temporal_window_violations_for_context(ctx.slice_for_claim("B"))
    assert [row["rule_id"] for row in rows] == ["sct_addon_without_qualifying_bmt"]


def test_sct_same_date_primary_ties_preserve_patient_order_after_slicing():
    lines = [
        replace(_procedure("bmt-a", "A"), procedure_code="704970", procedure_date=_DAY),
        replace(_procedure("bmt-b", "B"), procedure_code="704970", procedure_date=_DAY),
        replace(
            _procedure("sct", "A"), procedure_code="704981", procedure_date=_DAY + timedelta(days=1)
        ),
    ]
    for claims in permutations([_header("A"), _header("B")]):
        for ordered in permutations(lines):
            ctx = _context(claims, ordered)
            expected = detect_sct_temporal_window_violations_for_context(ctx)
            bill = ctx.slice_for_claim("A")
            assert bill.history.procedure_lines == ctx.procedure_lines
            assert detect_sct_temporal_window_violations_for_context(bill) == expected
            assert (
                detect_sct_temporal_window_violations_for_context(bill.slice_for_claim("A"))
                == expected
            )


def test_history_overlay_uses_current_rows_and_does_not_resurrect_removed_rows():
    ctx, current = _materials_context()
    ctx = replace(ctx, procedure_lines=(_procedure("a", "PRIOR"), _procedure("b", "CURRENT")))
    bill = ctx.slice_for_claim("CURRENT")
    updated = replace(current, material_name="Current correction")
    changed = replace(bill, procedure_lines=(), material_lines=(updated,))
    assert changed.history.procedure_lines == (ctx.procedure_lines[0],)
    assert changed.history.material_lines == (ctx.material_lines[0], updated)
    assert changed.slice_for_claim("CURRENT").history == changed.history
    assert changed.slice_for_claim("PRIOR") is None
    assert ctx.material_lines[-1].material_name != "Current correction"
    # Distinct history participates in context hashing; memoized rules cannot
    # reuse a result computed for a bill with absent or changed evidence.
    assert len({bill, replace(bill, patient_history=None)}) == 2


@pytest.mark.parametrize(
    "corruption", ["header", "procedure", "material", "orphan", "duplicate_header"]
)
def test_foreign_or_orphan_history_is_rejected(corruption):
    ctx, _ = _materials_context()
    ctx = replace(ctx, procedure_lines=(_procedure("prior", "PRIOR"),))
    if corruption == "header":
        ctx = replace(ctx, claims=(replace(ctx.claims[0], patient_id="FOREIGN"), ctx.claims[1]))
    elif corruption == "procedure":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], patient_id="FOREIGN"),))
    elif corruption == "material":
        ctx = replace(
            ctx,
            material_lines=(
                replace(ctx.material_lines[0], patient_id="FOREIGN"),
                ctx.material_lines[1],
            ),
        )
    elif corruption == "orphan":
        ctx = replace(ctx, procedure_lines=(replace(ctx.procedure_lines[0], claim_id="ORPHAN"),))
    else:
        ctx = replace(ctx, claims=(*ctx.claims, ctx.claims[0]))
    with pytest.raises(ValueError, match="history"):
        ctx.slice_for_claim("CURRENT")


@pytest.mark.parametrize(
    "discharge,expected_days",
    [
        (_DAY - timedelta(days=1), 3),
        (_DAY, 2),
        (_DAY + timedelta(days=2), 2),
        (_DAY + timedelta(days=3), 3),
    ],
)
def test_icu_discharge_inclusive_stay_boundaries(monkeypatch, discharge, expected_days):
    install_yatak_catalog_stub(monkeypatch, daily_rate_try=100)
    ctx = _icu_context()
    ctx = replace(ctx, claims=(replace(ctx.claims[0], discharge_date=discharge), ctx.claims[1]))
    bill = ctx.slice_for_claim("SRV")
    result = reconcile_yatak_icu_overlap(bill, recommend_yatak_puani_from_claims(bill))
    assert result.opportunities[0]["bed_days"] == expected_days
    assert result.opportunities[0]["expected_yatak_try"] == 100 * expected_days


def _dataset(contexts):
    return SimpleNamespace(
        **{
            name + "_by_patient": {ctx.patient_id: getattr(ctx, name) for ctx in contexts}
            for name in (
                "claims",
                "procedure_lines",
                "material_lines",
                "drug_lines",
                "diagnoses",
                "performed_procedure_lines",
                "medula_rejection_events",
            )
        },
        medula_rejection_ingest_available=False,
    )


@pytest.mark.parametrize("workers", [1, 3])
def test_history_survives_cohort_reports_public_projection_and_cache(
    tmp_path, monkeypatch, workers
):
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.db import connect, init_schema, read_json_payload_row, write_json_payload_rows
    from src.bilun.domain.billing import claim_materials
    from src.bilun.domain.billing.cohort_runner import compute_all_bill_billing_reports
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report

    install_yatak_catalog_stub(monkeypatch, daily_rate_try=100)
    monkeypatch.setattr(claim_materials, "_get_ek3c1_preauth", lambda: [])
    monkeypatch.setattr(
        claim_materials, "_get_ek3c2_miat", lambda: [{"sut_code": "OP1000", "miat_period": "6 ay"}]
    )
    icu = _icu_context(billed="50")
    materials, current = _materials_context()
    current = replace(current, claim_id="SRV")
    ctx = replace(
        icu,
        claims=(*icu.claims, materials.claims[0]),
        material_lines=(materials.material_lines[0], current),
    )
    # Another patient's bed shares a date and code but has no ICU history.
    other = _context(
        [replace(icu.claims[1], patient_id="P2")],
        [replace(icu.procedure_lines[1], patient_id="P2")],
    )
    other = replace(other, patient_id="P2")
    reports = compute_all_bill_billing_reports(
        {"sut_claim_dataset": _dataset([ctx, other])}, max_workers=workers
    )
    bill = reports["P1::SRV"]
    patient = compute_patient_billing_report("P1", claim_context=ctx)
    assert bill.yatak_puani.opportunities[0]["bed_days"] == 2
    assert bill.yatak_puani.opportunities[0]["actual_billed_try"] == 50
    assert bill.yatak_puani.opportunities[0]["recoverable_uplift_try"] == 150
    assert reports["P2::SRV"].yatak_puani.opportunities[0]["bed_days"] == 3
    assert sum(
        report.total_recoverable_try for key, report in reports.items() if key.startswith("P1::")
    ) == pytest.approx(patient.total_recoverable_try)
    assert [row["claim_id"] for row in bill.materials.miat_interval_violations] == ["SRV"]
    assert all(row["claim_id"] == "SRV" for row in bill.financial_findings.rows)
    assert bill.wavea_evidence_detail["claim_scope_inventory"]["claims"] == [
        {"claim_id": "SRV", "material_line_ids": ["current"]}
    ]
    payload = json_ready(_serialize_billing_report(bill))
    assert "patient_history" not in str(payload)
    projected = project_public_response(payload, "get_billing_report")
    assert projected["yatak_puani"] == payload["yatak_puani"]
    injected = {**payload, "patient_history": {"claims": ["PRIVATE"]}}
    injected["yatak_puani"] = {**payload["yatak_puani"], "private_history": ["PRIVATE"]}
    assert project_public_response(injected, "get_billing_report") == projected
    assert (
        projected["materials"]["miat_interval_violations"]
        == payload["materials"]["miat_interval_violations"]
    )
    con = connect(tmp_path / "history.duckdb")
    try:
        init_schema(con)
        write_json_payload_rows(con, "patient_bill_billing_report_rows", "B1", {"P1::SRV": payload})
        stored = read_json_payload_row(con, "patient_bill_billing_report_rows", "B1", "P1::SRV")
        assert project_public_response(stored, "get_billing_report") == projected
    finally:
        con.close()
