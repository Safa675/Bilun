"""A hizmet başı bill whose EK-2/C package is mandated, compared with that package (#269).

SUT §2.2.2(1) (C000646): a yatarak procedure in EK-2/C is billed as its package
("tanıya dayalı işlem"); §2.2.1.B-1(10)(a) (C000582): an outpatient one only when it
is also on EK-2/A-2 on its date (``payment_method``). When such a line was billed
hizmet başı, the correct bill replaces the part of the bill the package covers with
the package.
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
- several mandated operations in one session by §2.2.2.B(3)(a)/(b) (C000670,
  C000671): the highest in full, the others at 25 % / 50 %;
- a hizmet başı operation in the same session at 30 % / 50 % of its EK-2/B price
  (C000672, C000673); when such an operation outranks the packages, C000672 bills
  the whole session hizmet başı under §2.2.2.A(5) (``c000672_hizmet_basi_lines``);
- neuromonitoring and neuronavigation in full next to their operation
  (C001389, C001413);
- +25 points across specialties (C000674), read per session as elsewhere.

The incision is on no claim line and a line may lack its branch, so a session
with several operations has two package sides (``SessionReadings``): the strict
one (one incision, no +25 without two known branches) and the lenient one
(separate incisions, +25 when a branch is unknown). SGK uplift is claimed below
the strict side, over-billing above the lenient side; a bill between the two is
a 0-TL review (Safa, 2026-10-16, "2b").

Replaced side, what the hizmet başı bill billed for that part: every line of the
claim dated through the package window's last day (C000701–C000706) at its
billed amount. What the SUT pays next to the package either way is on neither
side:

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
from .claim_utils import claim_is_day_case, group_procedure_lines_by_session, infer_care_setting
from .facility_tier import normalize_facility_tier
from .material_bundling import material_paid_next_to_package
from .payment_method import check_payment_method_compliance
from .session_pricing import (
    MISSING_BRANCH,
    MISSING_INCISION,
    blood_component_billable_fraction,
    compute_session_readings,
    line_gazette_list_billed_try,
)
from .session_scope import (
    billed_without_session_rules,
    line_billed_as_package,
    session_operation_lines,
)
from .types import PaymentMethodCompliance
from .yatak_puani import (
    c000672_hizmet_basi_lines,
    claim_package_window,
    mandated_package_lines,
    must_be_billed_as_package,
)

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

    ``package_total_try`` is what the correct bill pays for those lines under
    the strict reading, ``lenient_package_total_try`` under the most lenient one
    (module docstring; ``None`` when the two agree). ``covers_the_stay`` is False
    when only neuromonitoring or neuronavigation must be packages: each is its
    own package and nothing else is inside it.
    """

    mandated: tuple[ProcedureClaimLine, ...]
    window_end: date
    lines: tuple[ProcedureClaimLine, ...]
    package_total_try: float
    covers_the_stay: bool = True
    lenient_package_total_try: float | None = None
    missing_facts: tuple[str, ...] = ()


@dataclass(frozen=True)
class MandatedPackageGap:
    """The mandated package against the part of the hizmet başı bill it replaces.

    ``package_total_try`` is the strict package side, ``lenient_package_total_try``
    the most lenient one (``None`` when the bill shows every fact they need).
    """

    package_total_try: float
    replaced_total_try: float
    billed_total_try: float
    window_end: date
    mandated_line_ids: frozenset[str]
    replaced_line_ids: frozenset[str]
    lenient_package_total_try: float | None = None
    missing_facts: tuple[str, ...] = ()

    @property
    def most_lenient_package_try(self) -> float:
        return max(self.package_total_try, self.lenient_package_total_try or 0.0)

    @property
    def excess_try(self) -> float:
        """What the bill overstates under every reading: 0 up to the lenient package."""
        return _money(max(0.0, self.replaced_total_try - self.most_lenient_package_try))

    @property
    def review_excess_try(self) -> float:
        """What the bill overstates under the strict reading only (0-TL review)."""
        strict_excess = max(0.0, self.replaced_total_try - self.package_total_try)
        return _money(strict_excess - self.excess_try)

    @property
    def in_review_band(self) -> bool:
        """The bill lies strictly between the two package sides: no money either way."""
        return self.package_total_try < self.replaced_total_try < self.most_lenient_package_try

    @property
    def comparison_package_total_try(self) -> float:
        """The package side a money claim compares with.

        The strict side when the package pays more (SGK uplift), the lenient one
        when the bill is higher (over-billing); the strict side, with no money,
        in the review band.
        """
        if self.replaced_total_try >= self.most_lenient_package_try:
            return self.most_lenient_package_try
        return self.package_total_try


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
        day_case=claim_is_day_case(claim),
    )


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
) -> tuple[float, float, bool, tuple[str, ...]]:
    """What the correct bill pays for ``lines``, strict and lenient, whether any
    package is in it, and the facts the bill does not show that set the gap.

    The sessions with a mandated line price their operations (module
    docstring), and so do the sessions C000672 bills hizmet başı. Neuromonitoring
    and neuronavigation are billed next to their operation wherever they are
    (C001389, C001413). Every other covered line is inside the package
    (operations, tests and stay; C000685–C000699).
    """
    starred_uplift = normalize_facility_tier(
        claim.facility_tier, provider_type=claim.provider_type,
    ).is_university_eah
    mandated = {id(line) for line in mandated_lines}
    hizmet_basi = {id(line) for line in c000672_hizmet_basi_lines(claim, list(lines))}
    strict_total = lenient_total = 0.0
    priced_a_package = False
    missing: set[str] = set()
    for session_date, session_lines in group_procedure_lines_by_session(lines).items():
        for line in session_lines:
            if billed_without_session_rules(line.procedure_code):
                amount = (
                    _package_price_try(line, starred_uplift=starred_uplift)
                    if must_be_billed_as_package(claim, line)
                    else _hizmet_basi_price_try(line)
                )
                strict_total += amount
                lenient_total += amount
        if not any(id(line) in mandated or id(line) in hizmet_basi for line in session_lines):
            continue
        operations = [
            line for line in session_operation_lines(session_lines)
            if normalize_procedure_code(line.procedure_code)
        ]
        strict_factors = lenient_factors = [1.0] * len(operations)
        itemized_session = False
        if len(operations) >= 2:
            readings = compute_session_readings(
                operations,
                claim=claim,
                as_of_date=session_date,
                billed_as_package=[id(line) in mandated for line in operations],
            )
            strict_factors = [factor.point_factor for factor in readings.strict.factors]
            missing.update(readings.missing_facts)
            lenient_factors = [factor.point_factor for factor in readings.lenient.factors]
            # C000672: an EK-2/B operation above the packages bills the whole
            # session hizmet başı under §2.2.2.A(5); both readings rank alike.
            itemized_session = readings.strict.rule_id == "2.2.2.A.(5)"
        for line, strict, lenient in zip(operations, strict_factors, lenient_factors, strict=True):
            if id(line) in mandated and not itemized_session:
                price = _package_price_try(line, starred_uplift=starred_uplift)
                priced_a_package = True
            else:
                price = _hizmet_basi_price_try(line)
            strict_total += price * strict
            lenient_total += price * lenient
        # A mandated line outside the session scope is its own package in full.
        operation_ids = {id(line) for line in operations}
        for line in session_lines:
            if id(line) in mandated and id(line) not in operation_ids:
                price = _package_price_try(line, starred_uplift=starred_uplift)
                strict_total += price
                lenient_total += price
                priced_a_package = True
    facts = tuple(fact for fact in (MISSING_INCISION, MISSING_BRANCH) if fact in missing)
    return _money(strict_total), _money(lenient_total), priced_a_package, facts


def mandated_package_scope(
    claim: ClaimHeader,
    claim_procs: Iterable[ProcedureClaimLine],
) -> MandatedPackageScope | None:
    """The #269 gate, read from the codes, and the procedure lines the package covers.

    ``None`` unless no line is billed as a package and at least one line billed
    hizmet başı must be one. With a mandated package (``mandated_package_lines``)
    the covered lines are the hizmet başı lines dated through the last day of
    its window; when only neuromonitoring or neuronavigation must be packages,
    they are the only covered lines (``_add_on_scope``).
    """
    procs = [line for line in claim_procs if line.claim_id == claim.claim_id]
    if any(line_billed_as_package(line) and float(line.billed_amount_try) > 0 for line in procs):
        return None
    mandated = tuple(mandated_package_lines(claim, procs))
    if not mandated:
        return _add_on_scope(claim, procs)
    window = claim_package_window(claim, procs)
    if window is None:
        return None
    lines = tuple(
        line for line in procs
        if not line_billed_as_package(line)
        and not line.is_package_included
        and float(line.billed_amount_try) > 0
        and _on_or_before(line.procedure_date, window.end)
    )
    package_total, lenient_total, priced_a_package, missing = _package_side_try(
        claim, mandated, lines,
    )
    if not priced_a_package or package_total <= 0:
        return None
    differs = lenient_total != package_total
    return MandatedPackageScope(
        mandated=mandated, window_end=window.end, lines=lines, package_total_try=package_total,
        lenient_package_total_try=lenient_total if differs else None,
        missing_facts=missing if differs else (),
    )


def _add_on_scope(
    claim: ClaimHeader,
    procs: Sequence[ProcedureClaimLine],
) -> MandatedPackageScope | None:
    """Neuromonitoring or neuronavigation that must be a package, next to an operation
    billed hizmet başı legally (e.g. without a star at a third-tier hospital).

    Each line is its own package (C001389, C001413) and compares only with itself.
    """
    add_ons = tuple(
        line for line in procs
        if billed_without_session_rules(line.procedure_code)
        and not line.is_package_included
        and must_be_billed_as_package(claim, line)
    )
    if not add_ons:
        return None
    starred_uplift = normalize_facility_tier(
        claim.facility_tier, provider_type=claim.provider_type,
    ).is_university_eah
    package_total = _money(sum(
        _package_price_try(line, starred_uplift=starred_uplift) for line in add_ons
    ))
    if package_total <= 0:
        return None
    return MandatedPackageScope(
        mandated=add_ons,
        window_end=max(line.procedure_date for line in add_ons),
        lines=add_ons,
        package_total_try=package_total,
        covers_the_stay=False,
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
    materials = [line for line in material_lines if line.claim_id == claim.claim_id]
    if scope.covers_the_stay:
        replaced += sum(
            float(line.billed_amount_try) for line in drugs
            if float(line.billed_amount_try) > 0
            and _on_or_before(line.drug_claim_date, end)
            and not drug_billed_next_to_package(line)
        )
    if materials and scope.covers_the_stay:
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
        lenient_package_total_try=scope.lenient_package_total_try,
        missing_facts=scope.missing_facts,
    )
