"""EK-3 list-price KDV (§3.1.1(10)/(12) — C001630, C002692)."""

from __future__ import annotations

# SUT cites KDV on EK-3 list prices but not a single statutory rate in-clause;
# default aligns with general TR KDV (2023+). Override via env/config later.
DEFAULT_MATERIAL_KDV_RATE = 0.20


def should_apply_kdv_to_material(
    *,
    foreign_facility: bool = False,
    kdv_exempt: bool = False,
    kanun_3065_17_exempt: bool = False,
) -> bool:
    """Return False when SUT/KDVK exemptions apply (§3.1.1(12))."""
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
    """Payable ceiling from catalog ex-VAT list price."""
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
