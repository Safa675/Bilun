"""In-memory variants of the showcase bills, for tests that need a clean control or one more line.

`data/synthetic/sut` holds the 8 faulty bills of the demo cohort. Each story also has a clean twin (the same
bill without its injected fault) that the builder composes in memory and never writes. A test that needs
"the bill with nothing wrong" asks this module for the twin of a registry role, and a test that needs the
bill with one more operation on it asks for `with_extra_operation`. Roles and ids come from
`tests/fixtures/synthetic_cohort.py`; nothing here names a patient, a claim or an amount.

- `clean_context(role_name)`: the clean twin of the showcase bill that the role names, as a
  `PatientClaimContext`. It is built by `scripts.synthetic.cohort.build_showcase()` (once per process) the
  way `tests/unit/synthetic/test_cohort_engine_proof.py` builds it.
- `with_extra_operation(ctx, code, factor="1")`: the context with one more EK-2/B operation line on the day
  of its most expensive `islem` line, billed at `factor` of the code's list price on that day.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from functools import cache

from scripts.synthetic.cohort import BuildResult, build_showcase, context_from_composed
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date
from tests.fixtures import synthetic_cohort as cohort

_CENT = Decimal("0.01")


@cache
def _built() -> BuildResult:
    return build_showcase()


def clean_context(role_name: str) -> PatientClaimContext:
    """The clean twin of the showcase bill that `role_name` names, as a claim context."""
    claim_id = cohort.role(role_name).claim_id
    for composed in _built().clean_claims:
        if composed.header.claim_id == claim_id:
            return context_from_composed(composed)
    raise KeyError(f"the builder composed no clean twin for {claim_id} ({role_name})")


def with_extra_operation(
    ctx: PatientClaimContext, code: str, *, factor: str = "1"
) -> PatientClaimContext:
    """`ctx` with one more operation `code`, billed at `factor` of its EK-2/B list price on the day of
    the bill's most expensive `islem` line (that line's specialty, claim and episode are copied)."""
    operations = [line for line in ctx.procedure_lines if line.procedure_category == "islem"]
    assert operations, "the bill has no islem line to put an operation next to"
    primary = max(operations, key=lambda line: line.billed_amount_try)
    raw = get_ek2b_price_for_date(code, primary.procedure_date)
    assert raw, f"{code} has no EK-2/B price on {primary.procedure_date}"
    list_price = Decimal(str(raw)).quantize(_CENT, rounding=ROUND_HALF_UP)
    billed = (list_price * Decimal(factor)).quantize(_CENT, rounding=ROUND_HALF_UP)
    extra = replace(
        primary,
        procedure_line_id=f"{primary.procedure_line_id}-OP2",
        procedure_code=code,
        procedure_name=f"Second operation {code}",
        quantity=1,
        unit_price_try=list_price,
        billed_amount_try=billed,
        expected_payable_try=billed,
    )
    return replace(ctx, procedure_lines=(*ctx.procedure_lines, extra))
