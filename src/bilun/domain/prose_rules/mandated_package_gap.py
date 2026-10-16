"""A hizmet başı bill whose EK-2/C package is mandated, compared with that package (#269).

SUT §2.2.2(1) and §2.2.1.B-1(a) (C000582): a procedure in EK-2/C is billed as its
package ("tanıya dayalı işlem"). When such a line was billed hizmet başı, the
correct bill replaces the part of the bill the package covers with the package.
One comparison serves three surfaces: the billing strategy shows the gap, audit
exposure claws back only what the bill overstates, and the session uplift claims
nothing inside it a second time.

The claim qualifies by its codes, never by the synthetic-only ``package_candidate``
flag: no line is billed as a package (``line_billed_as_package``) and
``mandated_package_lines`` (#286) finds a line that must be one, with a package
price and an işlem grubu on its date.

Package side, what the correct bill pays for the replaced part:

- a mandated line at its EK-2/C package price on its procedure date, +30 % for a
  starred package at the tiers C000678 names (training and research hospitals,
  university hospitals with a medical faculty);
- several mandated operations in one session by §2.2.2.B(3)(a)/(b) (C000670 /
  C000671): the highest in full, the others at 25 % / 50 %;
- a hizmet başı operation in the same session at 30 % / 50 % of its EK-2/B price
  (C000672 / C000673), all of the session hizmet başı under §2.2.2.A(5) when that
  operation outranks the packages;
- +25 points across specialties (C000674), read per session as elsewhere.

Replaced side, what the hizmet başı bill billed for that part: every line from
admission through the package window's last day (C000701–C000706) at its billed
amount. What the SUT pays next to the package either way is on neither side:

- materials §3.1.4 bills on top of the package (C000582, C002857–C002875), read by
  the §3.1.4 classifier (``material_paid_next_to_package``), never the
  ``is_bundled`` input flag; consumables are inside (C000695);
- the share of a blood component billed next to the package (C000694);
- blood products and bleeding-control, sealant and tissue-adhesive drugs
  (C000690);
- every line after the window (C000707).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING

import polars as pl

from ..constants import _PROJECT_ROOT
from ..money import money_round_half_up as _money
from .catalog_membership import (
    get_ek2c_description,
    get_ek2c_entry,
    normalize_procedure_code,
    procedure_has_star,
)
from .claim_utils import group_procedure_lines_by_session, infer_care_setting
from .facility_tier import normalize_facility_tier
from .material_bundling import material_paid_next_to_package
from .payment_method import check_payment_method_compliance
from .session_pricing import (
    blood_component_billable_fraction,
    compute_session_point_factors,
    line_gazette_list_billed_try,
)
from .session_scope import line_billed_as_package, session_operation_lines
from .session_specialty import detect_cross_specialty_session
from .types import PaymentMethodCompliance
from .yatak_puani import claim_package_window, mandated_package_lines

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimHeader,
        DrugClaimLine,
        MaterialClaimLine,
        ProcedureClaimLine,
    )

# C000678: "SUT eki EK-2/C Listesinde yanında (*) işareti olan işlemler, listede
# belirtilen puanlara %30 ilave edilerek faturalandırılır."
_STARRED_PACKAGE_UPLIFT = 1.30

# TİTCK barcode -> ATC (the EK-4/A crosswalk, data/synthetic/reference/sources.yaml).
_DRUG_CROSSWALK_PATH = _PROJECT_ROOT / "data" / "synthetic" / "reference" / "drug_crosswalk.parquet"
# C000690: "kan ürünleri ayrıca faturalandırılır, kanama durdurma, sızdırmazlık
# sağlama doku yapıştırmada kullanılan ilaçlar bu kapsamda değerlendirilmez".
# Blood products: albumin and plasma protein fractions (B05AA01/02), coagulation
# factors and fibrinogen (B02BD, B02BB), alfa-1 antitrypsin (B02AB) and
# immunoglobulins (J06BA, J06BB). Bleeding control, sealing and tissue adhesion:
# antifibrinolytics (B02AA), vitamin K (B02BA) and local haemostatics and fibrin
# sealants (B02BC). Synthetic plasma expanders (B05AA05-07) and the other
# systemic haemostatics (B02BX) stay inside the package.
_PACKAGE_EXCLUDED_DRUG_ATC = (
    "B05AA01", "B05AA02", "B02AA", "B02AB", "B02BA", "B02BB", "B02BC", "B02BD",
    "J06BA", "J06BB",
)


@dataclass(frozen=True)
class MandatedPackageScope:
    """A claim billed hizmet başı whose package is mandated, and the lines it covers.

    ``package_total_try`` is what the correct bill pays for those lines.
    """

    mandated: tuple[ProcedureClaimLine, ...]
    window_end: date
    lines: tuple[ProcedureClaimLine, ...]
    package_total_try: float


@dataclass(frozen=True)
class MandatedPackageGap:
    """The mandated package against the part of the hizmet başı bill it replaces."""

    package_total_try: float
    replaced_total_try: float
    billed_total_try: float
    window_end: date
    mandated_line_ids: frozenset[str]
    replaced_line_ids: frozenset[str]

    @property
    def excess_try(self) -> float:
        """What the bill overstates: 0 when the package pays at least as much."""
        return _money(max(0.0, self.replaced_total_try - self.package_total_try))


def line_payment_method_compliance(
    claim: ClaimHeader,
    line: ProcedureClaimLine,
) -> PaymentMethodCompliance:
    """The line's billing method against SUT §2.2 on its procedure date."""
    return check_payment_method_compliance(
        line.procedure_code,
        billed_as_package=line_billed_as_package(line),
        care_setting=infer_care_setting(claim),  # type: ignore[arg-type]
        facility_tier=claim.facility_tier,
        provider_type=claim.provider_type,
        as_of_date=line.procedure_date or claim.admission_date or claim.claim_start_date,
    )


def must_be_billed_as_package(claim: ClaimHeader, line: ProcedureClaimLine) -> bool:
    """A line billed hizmet başı whose EK-2/C package is mandated (the payment-method row's test)."""
    compliance = line_payment_method_compliance(claim, line)
    return not compliance.is_compliant and compliance.mandated_method == "package"


def _on_or_before(day: date | None, end: date) -> bool:
    return day is None or day <= end


def _package_price_try(line: ProcedureClaimLine, *, starred_uplift: bool) -> float:
    entry = get_ek2c_entry(line.procedure_code, as_of_date=line.procedure_date) or {}
    price = float(entry.get("price_try") or 0.0) * max(int(line.quantity or 1), 1)
    if starred_uplift and procedure_has_star(line.procedure_code, as_of_date=line.procedure_date):
        price *= _STARRED_PACKAGE_UPLIFT
    return price


def _hizmet_basi_price_try(line: ProcedureClaimLine) -> float:
    listed = line_gazette_list_billed_try(line)
    return float(line.billed_amount_try) if listed is None else listed


def _package_side_try(
    claim: ClaimHeader,
    mandated_lines: Sequence[ProcedureClaimLine],
    lines: Sequence[ProcedureClaimLine],
) -> tuple[float, bool]:
    """What the correct bill pays for ``lines`` and whether any package is in it.

    Only the sessions with a mandated line are priced; every other covered line
    is inside the package (operations, tests and stay; C000685–C000699).
    """
    starred_uplift = normalize_facility_tier(
        claim.facility_tier, provider_type=claim.provider_type,
    ).is_university_eah
    mandated = {id(line) for line in mandated_lines}
    total = 0.0
    priced_a_package = False
    for session_date, session_lines in group_procedure_lines_by_session(lines).items():
        if not any(id(line) in mandated for line in session_lines):
            continue
        operations = [
            line for line in session_operation_lines(session_lines)
            if normalize_procedure_code(line.procedure_code)
        ]
        factors = [1.0] * len(operations)
        itemized_session = False
        if len(operations) >= 2:
            session = compute_session_point_factors(
                [line.procedure_code for line in operations],
                same_incision=True,
                cross_specialty=detect_cross_specialty_session(operations, claim),
                as_of_date=session_date,
                billed_as_package=[id(line) in mandated for line in operations],
            )
            factors = [factor.point_factor for factor in session.factors]
            # C000672: an EK-2/B operation above the packages bills the whole
            # session hizmet başı under §2.2.2.A(5).
            itemized_session = session.rule_id == "2.2.2.A.(5)"
        for line, factor in zip(operations, factors, strict=True):
            if id(line) in mandated and not itemized_session:
                total += _package_price_try(line, starred_uplift=starred_uplift) * factor
                priced_a_package = True
            else:
                total += _hizmet_basi_price_try(line) * factor
        # A mandated line outside the session scope (e.g. neuromonitoring,
        # C001389) is its own package at full price.
        operation_ids = {id(line) for line in operations}
        for line in session_lines:
            if id(line) in mandated and id(line) not in operation_ids:
                total += _package_price_try(line, starred_uplift=starred_uplift)
                priced_a_package = True
    return _money(total), priced_a_package


def mandated_package_scope(
    claim: ClaimHeader,
    claim_procs: Iterable[ProcedureClaimLine],
) -> MandatedPackageScope | None:
    """The #269 gate, read from the codes, and the procedure lines the package covers.

    ``None`` unless no line is billed as a package, at least one line billed
    hizmet başı must be one (``mandated_package_lines``), and the correct bill
    holds a package: when C000672 bills every session of the mandated lines
    hizmet başı there is none to compare with. The covered lines are the
    hizmet başı lines dated through the last day of the package window.
    """
    procs = [line for line in claim_procs if line.claim_id == claim.claim_id]
    if any(line_billed_as_package(line) and float(line.billed_amount_try) > 0 for line in procs):
        return None
    mandated = tuple(
        line for line in mandated_package_lines(claim, procs) if float(line.billed_amount_try) > 0
    )
    window = claim_package_window(claim, procs) if mandated else None
    if window is None:
        return None
    lines = tuple(
        line for line in procs
        if not line_billed_as_package(line)
        and not line.is_package_included
        and float(line.billed_amount_try) > 0
        and _on_or_before(line.procedure_date, window.end)
    )
    package_total, priced_a_package = _package_side_try(claim, mandated, lines)
    if not priced_a_package or package_total <= 0:
        return None
    return MandatedPackageScope(
        mandated=mandated, window_end=window.end, lines=lines, package_total_try=package_total,
    )


@lru_cache(maxsize=1)
def _drug_atc_index() -> dict[str, str]:
    if not _DRUG_CROSSWALK_PATH.exists():
        return {}
    frame = pl.read_parquet(_DRUG_CROSSWALK_PATH, columns=["barcode", "kamu_no", "atc_code"])
    frame = frame.filter(pl.col("atc_code").is_not_null())
    index = dict(zip(frame["kamu_no"].to_list(), frame["atc_code"].to_list(), strict=True))
    index.update(zip(frame["barcode"].to_list(), frame["atc_code"].to_list(), strict=True))
    return {str(key).strip(): str(atc).strip().upper() for key, atc in index.items() if key}


def drug_billed_next_to_package(line: DrugClaimLine) -> bool:
    """C000690: a blood product or a bleeding-control, sealant or tissue-adhesive drug."""
    index = _drug_atc_index()
    atc = index.get(str(line.barkod or "").strip()) or index.get(str(line.drug_code or "").strip())
    return bool(atc) and atc.startswith(_PACKAGE_EXCLUDED_DRUG_ATC)


def mandated_package_gap(
    claim: ClaimHeader,
    claim_procs: Iterable[ProcedureClaimLine],
    *,
    drug_lines: Sequence[DrugClaimLine] = (),
    material_lines: Sequence[MaterialClaimLine] = (),
) -> MandatedPackageGap | None:
    """The #269 comparison of a claim, or ``None`` when it does not qualify.

    The billing strategy, audit exposure and session uplift all read this one
    figure (module docstring).
    """
    procs = [line for line in claim_procs if line.claim_id == claim.claim_id]
    scope = mandated_package_scope(claim, procs)
    if scope is None:
        return None

    end = scope.window_end
    replaced = 0.0
    for line in scope.lines:
        billed = float(line.billed_amount_try)
        fraction = blood_component_billable_fraction(line.procedure_code)
        replaced += billed * (1.0 - fraction) if fraction is not None else billed
    drugs = [line for line in drug_lines if line.claim_id == claim.claim_id]
    replaced += sum(
        float(line.billed_amount_try) for line in drugs
        if float(line.billed_amount_try) > 0
        and _on_or_before(line.drug_claim_date, end)
        and not drug_billed_next_to_package(line)
    )
    materials = [line for line in material_lines if line.claim_id == claim.claim_id]
    if materials:
        packages = tuple(
            get_ek2c_description(line.procedure_code, as_of_date=line.procedure_date)
            for line in scope.mandated
        )
        codes = frozenset(normalize_procedure_code(line.procedure_code) for line in scope.lines)
        replaced += sum(
            float(line.billed_amount_try) for line in materials
            if float(line.billed_amount_try) > 0
            and _on_or_before(line.material_date, end)
            and not material_paid_next_to_package(
                code=line.material_code, name=line.material_name,
                package_descriptions=packages, procedure_codes=codes - {""},
            )
        )

    # Every hizmet başı line, drug and material billed on the claim, for display.
    billed_total = sum(
        float(line.billed_amount_try) for line in procs
        if not line_billed_as_package(line) and not line.is_package_included
        and float(line.billed_amount_try) > 0
    ) + sum(
        float(line.billed_amount_try) for line in (*drugs, *materials)
        if float(line.billed_amount_try) > 0
    )
    return MandatedPackageGap(
        package_total_try=scope.package_total_try,
        replaced_total_try=_money(replaced),
        billed_total_try=_money(billed_total),
        window_end=end,
        mandated_line_ids=frozenset(line.procedure_line_id for line in scope.mandated),
        replaced_line_ids=frozenset(line.procedure_line_id for line in scope.lines),
    )
