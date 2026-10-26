"""EK-3 list-price KDV (§3.1.1(10) — C002748) at the rate a line declares (§3.2.1.C(1) — C002886).

EK-3 prices are ex-KDV and SGK adds KDV "Kurum bilgi işlem sistemine girilen KDV oranında": at the rate entered in its
system, MEDULA's ``MalzemeBilgisiDVO.kdv``, an integer percent the facility declares on every material line
(``MaterialClaimLine.kdv_percent``; implants 10 %). A line that declares no rate is priced at the 20 % default and its
row says the rate was not declared (Safa675/Bilun#298).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import MaterialClaimLine

# The rate of a line that declares none: the general TR KDV rate (2023+); SUT names no rate in-clause.
DEFAULT_MATERIAL_KDV_RATE = 0.20


def declared_kdv_rate(kdv_percent: int | None) -> float | None:
    """The rate of a declared MEDULA ``kdv`` percent (10 -> 0.10); None when the line declares none."""
    if kdv_percent is None:
        return None
    return kdv_percent / 100


def material_line_kdv_rate(line: MaterialClaimLine) -> tuple[float, bool]:
    """``(rate, declared)``: the rate the line declares, else the 20 % default with ``declared`` False."""
    rate = declared_kdv_rate(line.kdv_percent)
    if rate is None:
        return DEFAULT_MATERIAL_KDV_RATE, False
    return rate, True


def should_apply_kdv_to_material(
    *,
    foreign_facility: bool = False,
    kdv_exempt: bool = False,
    kanun_3065_17_exempt: bool = False,
) -> bool:
    """Return False when SUT/KDVK exemptions apply (§3.1.1(10))."""
    if foreign_facility:
        return False
    if kdv_exempt or kanun_3065_17_exempt:
        return False
    return True


def gazette_price_with_kdv(
    ex_vat_price: float,
    *,
    apply_kdv: bool,
    kdv_rate: float = DEFAULT_MATERIAL_KDV_RATE,
) -> float:
    """Convert ex-VAT EK-3 list price to payable ceiling incl. KDV when applicable."""
    base = max(0.0, float(ex_vat_price))
    if not apply_kdv or base <= 0:
        return round(base, 2)
    return round(base * (1.0 + float(kdv_rate)), 2)


def ek3_payable_ceiling_try(
    ex_vat_list_price: float | None,
    *,
    foreign_facility: bool = False,
    kdv_exempt: bool = False,
    kanun_3065_17_exempt: bool = False,
    kdv_rate: float = DEFAULT_MATERIAL_KDV_RATE,
) -> float | None:
    """Payable ceiling from catalog ex-VAT list price, at ``kdv_rate`` (a line's declared rate, else the default)."""
    if ex_vat_list_price is None or float(ex_vat_list_price) <= 0:
        return None
    apply = should_apply_kdv_to_material(
        foreign_facility=foreign_facility,
        kdv_exempt=kdv_exempt,
        kanun_3065_17_exempt=kanun_3065_17_exempt,
    )
    return gazette_price_with_kdv(
        float(ex_vat_list_price),
        apply_kdv=apply,
        kdv_rate=kdv_rate,
    )
