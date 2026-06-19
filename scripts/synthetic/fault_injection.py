"""Shared fault-injection helpers for synthetic demo generation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from catalog import _money
from constants import SCENARIO_TEMPLATES
from vignettes import BillingVignette, ItemizedCodeVignette, get_vignette_registry

# Canonical fault identifiers (see synthetic-demo-credibility-plan.md).
FAULT_ITEMIZED_WHEN_PACKAGE_HIGHER = "itemized_when_package_higher"
FAULT_PACKAGE_WHEN_ITEMIZED_HIGHER = "package_when_itemized_higher"
FAULT_PACKAGE_UNDERBILLED = "package_underbilled"
FAULT_COMPLIANCE_MANDATORY_ITEMIZED = "compliance_mandatory_itemized"
FAULT_PACKAGE_MATERIALS_UNBUNDLED = "package_materials_unbundled"
FAULT_GAZETTE_STALE_PRICE = "gazette_stale_price"
FAULT_SESSION_UNDERBILLED = "session_underbilled"
FAULT_PROCEDURE_CAPTURE_GAP = "procedure_capture_gap"
FAULT_MEDULA_PREFIX = "medula_rejection_"
FAULT_DRUG_INDICATION_PREFIX = "drug_indication_"
FAULT_MATERIAL_PREFIX = "material_"


def _lookup_ek2b_price(code: str, ek2b_procs: dict[str, pd.DataFrame]) -> tuple[str, float]:
    for pool in ek2b_procs.values():
        if pool.empty:
            continue
        match = pool[pool["code"].astype(str) == str(code)]
        if not match.empty:
            row = match.iloc[0]
            return str(row["name"]), float(row.get("price_try", row.get("price", 0)) or 0)
    return f"Procedure {code}", 0.0


def _orthopedics_template() -> dict[str, Any]:
    for template in SCENARIO_TEMPLATES:
        if template.get("specialty") == "orthopedics":
            return template
    return SCENARIO_TEMPLATES[0]


def apply_vignette_episode_defaults(
    episode_row: dict[str, Any],
    vignette: BillingVignette,
) -> None:
    """Pin clinical shell from a vignette onto an episode row."""
    if vignette.primary_icd10:
        if vignette.department and "Ortopedi" in vignette.department:
            episode_row["_template"] = _orthopedics_template()
        episode_row["birincil_icd10"] = vignette.primary_icd10
        all_codes = [vignette.primary_icd10, *vignette.secondary_icd10]
        episode_row["tum_icd10_kodlari"] = ",".join(all_codes)
        episode_row["_all_codes"] = all_codes
    if vignette.department:
        episode_row["servis_adi"] = vignette.department


def _default_itemized_codes() -> tuple[ItemizedCodeVignette, ...]:
    return (
        ItemizedCodeVignette(code="600150", price_try=2200.0),
        ItemizedCodeVignette(code="600160", price_try=1800.0),
    )


def build_itemized_procedure_specs(
    itemized_codes: tuple[ItemizedCodeVignette, ...],
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    candidate_package_code: str | None = None,
) -> list[dict[str, Any]]:
    disable_surcharge = {"disable_surcharge": True}
    package_metadata = (
        {"candidate_package_code": candidate_package_code}
        if candidate_package_code
        else {}
    )
    specs: list[dict[str, Any]] = []
    for entry in itemized_codes:
        price = _money(entry.price_try)
        name, _ = _lookup_ek2b_price(entry.code, ek2b_procs)
        specs.append(
            {
                "code": entry.code,
                "name": name,
                "price": price,
                "category": "islem",
                "included_in_package": False,
                "billed_override": price,
                **package_metadata,
                **disable_surcharge,
            }
        )
    return specs


def build_package_procedure_spec(
    package_code: str,
    package_price: float,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    name, _ = _lookup_ek2b_price(package_code, ek2b_procs)
    return {
        "code": package_code,
        "name": name,
        "price": _money(package_price),
        "category": "paket",
        "is_package": True,
        "billed_override": _money(package_price),
        "disable_surcharge": True,
    }


def build_optional_override_specs(
    vignette: BillingVignette,
    demo_kind: str,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    """§2.2.2(2) credible submitted shape; alternative path lives in billing_strategy."""
    itemized_codes = vignette.itemized_codes or _default_itemized_codes()
    package_code = str(vignette.package_code or "609300")
    package_price = _money(float(vignette.package_price_try or 9000.0))

    if demo_kind == "package_higher":
        return build_itemized_procedure_specs(
            itemized_codes,
            ek2b_procs=ek2b_procs,
            candidate_package_code=package_code,
        )

    return [build_package_procedure_spec(package_code, package_price, ek2b_procs=ek2b_procs)]


def vignette_for_episode(episode: dict[str, Any]) -> BillingVignette | None:
    pid = str(episode.get("hasta_id", ""))
    return get_vignette_registry().get_for_patient_id(pid)


def is_ghost_package_line(
    *,
    procedure_category: str,
    billed_amount_try: float,
    expected_payable_try: float,
) -> bool:
    return (
        str(procedure_category).strip().lower() == "paket"
        and billed_amount_try <= 0
        and expected_payable_try > 0
    )


def find_ghost_package_lines(procedure_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ghosts: list[dict[str, Any]] = []
    for row in procedure_rows:
        if is_ghost_package_line(
            procedure_category=str(row.get("islem_kategorisi", "")),
            billed_amount_try=float(row.get("fatura_tutari_try") or 0),
            expected_payable_try=float(row.get("beklenen_odenebilir_tutar_try") or 0),
        ):
            ghosts.append(row)
    return ghosts
