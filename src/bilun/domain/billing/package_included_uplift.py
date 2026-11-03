"""What an optional EK-2/C package would include of the uplift an itemized bill is owed.

SUT §2.2.2.B-1(1) puts the bed (a), the anaesthesia (g) and the companion (h) inside an EK-2/C package from the
admission through its window (§2.2.2.B-1(3)); days after the window stay billable (§2.2.2.B-1(4)). For a mandated
package (§2.2.2(1)) the bed, companion, newborn bed and anaesthesia motors expect nothing inside the window (#288),
because the itemized bill is not a legal alternative. A third-tier hospital may bill an overridable procedure
either way (§2.2.2(2)), so those motors keep their rows on the itemized bill, and the strategy's comparison counts
what they say the itemized bill is owed inside the window: the package against the correct itemized bill, not the
incomplete one. Otherwise the package advice and the same days' bed or companion uplift both enter the SGK total.
"""

from __future__ import annotations

from dataclasses import replace

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.money import money_round_half_up as _money
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.session_scope import line_billed_as_package

from .claim_anestezi_puani import recommend_anestezi_puani_from_claims
from .claim_refakatci import recommend_refakatci_from_claims
from .claim_yatak_icu_overlap import reconcile_yatak_icu_overlap
from .claim_yatak_newborn_overlap import reconcile_yatak_newborn_overlap
from .claim_yatak_puani import recommend_yatak_puani_from_claims
from .claim_yenidogan_yatak import recommend_yenidogan_yatak_from_claims

# Turkish labels for the row detail, by motor.
INCLUDED_LABELS_TR = {
    "yatak_puani": "yatak",
    "yenidogan_yatak": "yenidoğan yatağı",
    "refakatci": "refakatçi",
    "anestezi_puani": "anestezi",
}


def _owed_try(ctx: PatientClaimContext) -> dict[str, float]:
    """The SGK-total uplift of the bed, newborn bed, companion and anaesthesia motors, wired as the report wires them."""
    newborn = recommend_yenidogan_yatak_from_claims(ctx)
    bed = reconcile_yatak_newborn_overlap(
        reconcile_yatak_icu_overlap(ctx, recommend_yatak_puani_from_claims(ctx)), newborn,
    )
    return {
        "yatak_puani": bed.confirmed_yatak_try,
        "yenidogan_yatak": newborn.confirmed_yenidogan_yatak_try,
        "refakatci": recommend_refakatci_from_claims(ctx).confirmed_refakat_try,
        "anestezi_puani": recommend_anestezi_puani_from_claims(ctx).confirmed_anestezi_try,
    }


def package_included_uplift_try(
    ctx: PatientClaimContext,
    claim: ClaimHeader,
    claim_procs: list[ProcedureClaimLine],
    package_code: str | None,
) -> dict[str, float]:
    """By motor, the uplift the itemized ``claim`` is owed that billing ``package_code`` would include.

    The motors run on the claim as billed and as if its lines of ``package_code`` were billed as that package
    (the P code); the difference is the uplift inside the package's window. Motors with none are left out.
    """
    code = normalize_procedure_code(package_code or "")
    if not code:
        return {}
    as_billed = replace(ctx, claims=(claim,), procedure_lines=tuple(claim_procs))
    as_package = replace(
        as_billed,
        procedure_lines=tuple(
            replace(line, procedure_code=f"P{code}", procedure_category="paket")
            if normalize_procedure_code(line.procedure_code) == code and not line_billed_as_package(line)
            else line
            for line in claim_procs
        ),
    )
    if as_package.procedure_lines == as_billed.procedure_lines:
        return {}
    billed, packaged = _owed_try(as_billed), _owed_try(as_package)
    included = {name: _money(max(0.0, billed[name] - packaged[name])) for name in billed}
    return {name: amount for name, amount in included.items() if amount > 0}
