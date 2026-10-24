"""Self-made procedure lines on the EK-2G and EK-2C-1 catalog lists.

The showcase cohort in `data/synthetic/sut` has no procedure line on either annex list (no
line with an EK-2G surcharge prohibition, none with an EK-2C-1 mandated copay rate), so a test that
needs such a line builds it here. The codes are read from the catalog, never typed: a gazette
update that changes the lists cannot break a test that uses this module, and every helper asserts
the list membership it promises.

- `ek2g_only_code()`: a code on EK-2G (ilave ücret prohibited) and not on EK-2C-1.
- `ek2c1_only_code()`: `(code, mandated copay %)` of a code on EK-2C-1 that the copay-rate check reads
  (not an ICU day package) and not on EK-2G.
- `unlisted_code()`: a made-up code that is on neither list.
- `procedure_line(code, ...)`: one dated, billable `ProcedureClaimLine` for that code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.catalog import get_ek2c1_copay_rates, get_ek2g_no_surcharge
from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.optimization.catalog_join import (
    catalog_copay_rate_applicable,
    get_ek2c1_mandated_copay_rate_pct,
    is_ek2g_surcharge_prohibited,
)

_UNLISTED_CODE = "T2-UNLISTED"


def unlisted_code() -> str:
    """A made-up procedure code that is on neither annex list."""
    assert not is_ek2g_surcharge_prohibited(_UNLISTED_CODE)
    assert not catalog_copay_rate_applicable(_UNLISTED_CODE)
    return _UNLISTED_CODE


def ek2g_only_code() -> str:
    """The first sorted EK-2G code that is not an EK-2C-1 code."""
    code = next(
        code for code in sorted(get_ek2g_no_surcharge()) if not catalog_copay_rate_applicable(code)
    )
    assert is_ek2g_surcharge_prohibited(code)
    return code


def ek2c1_only_code() -> tuple[str, Decimal]:
    """The first sorted EK-2C-1 code that the copay-rate check reads and that is not an EK-2G code, with its
    mandated copay %. The ICU day packages are on the list too, but their rate is the Sınıf-3 uplift of the ICU motor
    and the check does not read it (`catalog_join.get_ek2c1_mandated_copay_rate_pct`)."""
    code = next(
        code
        for code in sorted(get_ek2c1_copay_rates())
        if catalog_copay_rate_applicable(code) and not is_ek2g_surcharge_prohibited(code)
    )
    mandated = get_ek2c1_mandated_copay_rate_pct(code)
    assert mandated is not None
    return code, Decimal(str(mandated))


def procedure_line(
    code: str,
    *,
    line_id: str = "L1",
    patient_id: str = "P-T2",
    billed: str = "100.00",
    payable: str = "100.00",
    surcharge_flag: bool = False,
    copay_flag: bool = True,
    day: int = 15,
) -> ProcedureClaimLine:
    """One billable (not package-included) procedure line dated 2026-01-`day`."""
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=f"C-{patient_id}",
        patient_id=patient_id,
        episode_id=f"E-{patient_id}",
        procedure_date=date(2026, 1, day),
        procedure_code=code,
        procedure_name=f"Test procedure {code}",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(payable),
        is_package_included=False,
        package_code="",
        surcharge_applicable=surcharge_flag,
        copay_rate_applicable=copay_flag,
        denial_reason_expected="",
        rule_trace_expected="",
    )
