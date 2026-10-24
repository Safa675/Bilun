"""A procedure line's unit price moves no showcase report (Safa675/Bilun#300).

MEDULA prices an operation itself: the hospital sends no amount for it (``AmeliyatveGirisimBilgisiDVO`` carries the
incision code ``ayniFarkliKesi``, no price) and MEDULA returns each line's amount after the §2.2.2 session reduction.
A bill built from those amounts states the reduced amount as the line's unit price. The session checks compare a
line with its list price in force on its date (``line_gazette_list_billed_try``), so every committed story bill and
every clean twin gives the same report with its unit prices as the builder writes them (the catalog's) and with each
procedure line's unit price set to its billed amount per unit. Before #300 five bills did not: the clean twins of S8,
S9, S22 and S50 showed 896.20, 758.00, 219.93 and 288.84 TL of audit exposure, and S9 lost its 151.60 TL session
uplift for 379.00 TL of exposure. Roles and ids come from `tests/fixtures/synthetic_cohort.py`.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from functools import cache

import pytest

from src.bilun.domain.billing.patient_report import compute_patient_billing_report
from src.bilun.domain.claims.patient_context import PatientClaimContext, build_bill_claim_context
from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.t1_showcase_bills import clean_context, clean_context_for_story

pytestmark = pytest.mark.unit

_CENT = Decimal("0.01")
_SCALARS = (
    "sgk_uplift_try",
    "total_recoverable_try",
    "compliance_adjustment_try",
    "audit_exposure_try",
    "capture_gap_try",
    "action_count",
)


def _bills() -> list[tuple[str, str, str]]:
    """(story, claim id or "" for the clean twin, test id) of every committed story bill and clean twin."""
    bills: list[tuple[str, str, str]] = []
    for i in range(1, 9):
        role = cohort.role(f"showcase_S{i}")
        bills += [(f"S{i}", role.claim_id, f"S{i}"), (f"S{i}", "", f"S{i}-twin")]
    for story, scenario in sorted(cohort.scenarios().items()):
        for k, claim_id in enumerate(scenario.claim_ids):
            bills.append((story, claim_id, story if k == 0 else f"{story}#{k + 1}"))
        bills.append((story, "", f"{story}-twin"))
    return bills


_BILLS = _bills()


@cache
def _dataset():
    return load_showcase_dataset()


def _context(story: str, claim_id: str) -> PatientClaimContext:
    if not claim_id:
        if story in {f"S{i}" for i in range(1, 9)}:
            return clean_context(f"showcase_{story}")
        return clean_context_for_story(story)
    patient_id = next(
        claim.patient_id
        for claims in _dataset().claims_by_patient.values()
        for claim in claims
        if claim.claim_id == claim_id
    )
    ctx = build_bill_claim_context(patient_id, claim_id, _dataset())
    assert ctx is not None, claim_id
    return ctx


def _with_billed_unit_prices(ctx: PatientClaimContext) -> PatientClaimContext:
    """Each procedure line's unit price set to its billed amount per unit, as MEDULA returns it."""
    return replace(
        ctx,
        procedure_lines=tuple(
            replace(
                line,
                unit_price_try=(line.billed_amount_try / line.quantity).quantize(
                    _CENT,
                    rounding=ROUND_HALF_UP,
                ),
            )
            for line in ctx.procedure_lines
        ),
    )


def _numbers(ctx: PatientClaimContext) -> dict:
    report = compute_patient_billing_report(
        ctx.patient_id,
        claim_context=ctx,
        copay_exemption={"exempt": False},
    )
    return {
        "scalars": {name: getattr(report, name) for name in _SCALARS},
        "actions": sorted(
            (
                a["action_id"],
                a["finding_type"],
                a["procedure_code"],
                a["sgk_uplift_try"],
                a["audit_risk_try"],
                a["compliance_savings_try"],
                a["billed_try"],
            )
            for a in report.recommended_actions
        ),
    }


@pytest.mark.parametrize(("story", "claim_id"), [b[:2] for b in _BILLS], ids=[b[2] for b in _BILLS])
def test_the_report_does_not_depend_on_the_procedure_unit_prices(story: str, claim_id: str) -> None:
    ctx = _context(story, claim_id)
    medula = _with_billed_unit_prices(ctx)
    if medula == ctx:  # every line is billed at its unit price already
        return
    assert _numbers(medula) == _numbers(ctx)


@pytest.mark.parametrize(
    ("story", "claim_id", "sgk_uplift", "was"),
    [
        ("S8", "", 0.0, "audit exposure 896.20"),  # the issue's clean S8: P603840 at 25 %
        ("S9", "", 0.0, "audit exposure 758.00"),
        ("S22", "", 0.0, "audit exposure 219.93"),
        ("S50", "", 0.0, "audit exposure 288.84"),
        ("S9", None, 151.60, "no uplift, audit exposure 379.00"),
    ],
    ids=["S8-twin", "S9-twin", "S22-twin", "S50-twin", "S9"],
)
def test_bills_with_a_reduced_secondary_keep_their_numbers_on_medula_amounts(
    story: str,
    claim_id: str | None,
    sgk_uplift: float,
    was: str,
) -> None:
    if claim_id is None:
        (claim_id, *_) = cohort.scenario(story).claim_ids
    ctx = _with_billed_unit_prices(_context(story, claim_id))
    assert ctx != _context(story, claim_id), "the bill has a line billed below its unit price"
    numbers = _numbers(ctx)["scalars"]
    assert (numbers["audit_exposure_try"], numbers["sgk_uplift_try"]) == (0.0, sgk_uplift), was
