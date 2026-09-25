"""Procedure selection for synthetic claims."""

from __future__ import annotations


import numpy as np
import pandas as pd

from catalog import _money
from demo_config import vignette_for_patient_id
from fault_injection import build_optional_override_specs
from gen.patients import _drg_group
from payment_method_sampling import episode_care_setting, filter_ek2b_pool_for_packaged_claim

def _pick_procedures(
    episode: dict,
    num_procs: int,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    facility_tier: str | None = None,
    provider_type: str | None = None,
    allow_mandatory_side_procs: bool = False,
) -> list[dict]:
    procs: list[dict] = []
    visit_type = episode["gelis_tipi"]
    all_codes = episode.get("_all_codes", [])
    drg_grp = _drg_group(all_codes)
    service_date = episode.get("basvuru_tarihi")
    care_setting = episode_care_setting(visit_type)

    package_code = None
    package_name = None
    package_price = 0.0
    is_package_candidate = (visit_type in ("yatis", "gunubirlik")) and rng.random() < 0.6
    if is_package_candidate and drg_grp in ek2c_packages:
        pkg_pool = ek2c_packages[drg_grp]
        if not pkg_pool.empty:
            pkg_row = pkg_pool.sample(1, random_state=rng.bit_generator).iloc[0]
            package_code = str(pkg_row["package_code"])
            package_name = str(pkg_row["name"])
            package_price = _money(float(pkg_row.get("price_try", 0) or 0))

    def _side_pool(df: pd.DataFrame) -> pd.DataFrame:
        if not package_code or allow_mandatory_side_procs:
            return df
        return filter_ek2b_pool_for_packaged_claim(
            df,
            care_setting=care_setting,
            facility_tier=facility_tier,
            provider_type=provider_type,
            as_of_date=service_date,
            allow_mandatory_side_procs=False,
        )

    if not ek2b_procs.get("muayene", pd.DataFrame()).empty:
        exam_pool = _side_pool(ek2b_procs["muayene"])
        exam_valid = exam_pool[exam_pool["price_try"].notna() & (exam_pool["price_try"] > 0)]
        if not exam_valid.empty:
            row = exam_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            procs.append({
                "code": str(row["code"]),
                "name": str(row["name"]),
                "price": _money(float(row.get("price_try", 0) or 0)),
                "category": "muayene",
            })

    if visit_type == "yatis" and not ek2b_procs.get("yatak", pd.DataFrame()).empty:
        bed_pool = _side_pool(ek2b_procs["yatak"])
        bed_valid = bed_pool[bed_pool["price_try"].notna() & (bed_pool["price_try"] > 0)]
        if not bed_valid.empty:
            row = bed_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            days = int(rng.integers(1, 21))
            procs.append({
                "code": str(row["code"]),
                "name": str(row["name"]),
                "price": _money(float(row.get("price_try", 0) or 0)),
                "category": "yatak",
                "quantity_override": days,
            })

    n_labs = int(rng.integers(1, 4))
    lab_pool = ek2b_procs.get("lab", pd.DataFrame())
    if not lab_pool.empty:
        lab_pool_valid = _side_pool(lab_pool)
        lab_pool_valid = lab_pool_valid[
            lab_pool_valid["price_try"].notna() &
            (lab_pool_valid["price_try"] > 0)
        ]
        if not lab_pool_valid.empty:
            n_sample = min(n_labs, len(lab_pool_valid))
            lab_sample = lab_pool_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in lab_sample.iterrows():
                procs.append({
                    "code": str(row["code"]),
                    "name": str(row["name"]),
                    "price": _money(float(row.get("price_try", 0) or 0)),
                    "category": "laboratuvar",
                })

    # Build set of all EK-2C package codes so we never sample them as general procedures
    ek2c_all_codes: set[str] = set()
    for pkg_df in ek2c_packages.values():
        if not pkg_df.empty and "package_code" in pkg_df.columns:
            ek2c_all_codes.update(pkg_df["package_code"].astype(str).tolist())

    remaining = num_procs - len(procs) - (1 if package_code else 0)
    general_pool = ek2b_procs.get("general", pd.DataFrame())
    if remaining > 0 and not general_pool.empty:
        gen_valid = _side_pool(general_pool)
        gen_valid = gen_valid[
            gen_valid["price_try"].notna() &
            (gen_valid["price_try"] > 0)
        ]
        if not gen_valid.empty and ek2c_all_codes:
            gen_valid = gen_valid[~gen_valid["code"].astype(str).isin(ek2c_all_codes)]
        if not gen_valid.empty:
            n_sample = min(remaining, len(gen_valid))
            sample = gen_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in sample.iterrows():
                included_in_pkg = False
                if package_code:
                    included_in_pkg = rng.random() < 0.45
                procs.append({
                    "code": str(row["code"]),
                    "name": str(row["name"]),
                    "price": _money(float(row.get("price_try", 0) or 0)),
                    "category": "islem",
                    "included_in_package": included_in_pkg,
                })

    if package_code:
        procs.append({
            "code": package_code,
            "name": package_name or package_code,
            "price": package_price,
            "category": "paket",
            "is_package": True,
        })

    return procs


def _pick_payment_method_compliance_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 demo: billed paket + DRG_MANDATORY side line billed as itemized (612070)."""
    _ = (episode, ek2c_packages, rng)
    name_m, price_m = _lookup_ek2b_price("700390", ek2b_procs)
    name_b, unit_b = _lookup_ek2b_price("612070", ek2b_procs)
    name_l, price_l = _lookup_ek2b_price("L116470", ek2b_procs)
    name_i, price_i = _lookup_ek2b_price("G100580", ek2b_procs)
    pkg_name, _pkg_catalog = _lookup_ek2b_price("P615440", ek2b_procs)
    bed_days = 7
    return [
        {
            "code": "700390",
            "name": name_m,
            "price": _money(max(price_m, 17.11)),
            "category": "muayene",
        },
        {
            "code": "612070",
            "name": name_b,
            "price": _money(unit_b),
            "category": "yatak",
            "quantity_override": bed_days,
        },
        {
            "code": "L116470",
            "name": name_l,
            "price": _money(max(price_l, 107.55)),
            "category": "laboratuvar",
        },
        {
            "code": "G100580",
            "name": name_i,
            "price": _money(max(price_i, 1848.56)),
            "category": "islem",
        },
        {
            "code": "P615440",
            "name": pkg_name,
            "price": _money(103260.58),
            "category": "paket",
            "is_package": True,
            "billed_override": 103260.58,
            "payable_override": 61956.35,
        },
    ]


def _lookup_ek2b_price(code: str, ek2b_procs: dict[str, pd.DataFrame]) -> tuple[str, float]:
    general = ek2b_procs.get("general", pd.DataFrame())
    if general.empty:
        return code, 1000.0
    match = general[general["code"].astype(str) == str(code)]
    if match.empty:
        return code, 1000.0
    row = match.iloc[0]
    return str(row["name"]), _money(float(row.get("price_try", 0) or 1000))


def _pick_blood_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2.B-1.e demo: 705371 billed below 36% of reference payable."""
    all_codes = episode.get("_all_codes", [])
    drg_grp = _drg_group(all_codes)
    name, _price = _lookup_ek2b_price("705371", ek2b_procs)

    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    if drg_grp in ek2c_packages and not ek2c_packages[drg_grp].empty:
        pkg_row = ek2c_packages[drg_grp].sample(1, random_state=rng.bit_generator).iloc[0]
        package_code = str(pkg_row["package_code"])
        package_name = str(pkg_row.get("name") or package_code)
        package_price = _money(float(pkg_row.get("price_try", 0) or package_price))

    reference_try = 1000.0
    billed_try = 50.0
    return [
        {
            "code": "705371",
            "name": name or "Eritrosit süspansiyonu",
            "price": reference_try,
            "category": "islem",
            "included_in_package": False,
            "billed_override": billed_try,
            "payable_override": reference_try,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
        },
    ]


def _pick_material_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.1 demo: procedure 600150 billed without expected material OR2640."""
    _ = (episode, ek2c_packages, rng)
    name, price = _lookup_ek2b_price("600150", ek2b_procs)
    price = _money(max(price, 4500.0))
    return [
        {
            "code": "600150",
            "name": name,
            "price": price,
            "category": "islem",
            "included_in_package": False,
            "disable_surcharge": True,
        },
    ]


def _pick_drg_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 DRG uplift demo: package_candidate=False, package billed, itemized higher."""
    _ = (episode, ek2c_packages, rng)
    disable_surcharge = {"disable_surcharge": True}
    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 5000.0))
    price_b = _money(max(price_b, 4000.0))
    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(package_price or 3500.0, 3500.0))
    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_a,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_b,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]


def _pick_optional_override_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2(2) demo: credible submitted billing + optimizer alternative in strategy."""
    demo_kind = episode.get("_sgk_optional_override_demo")
    _ = (ek2c_packages, rng)
    pid = str(episode.get("hasta_id", ""))
    vignette = vignette_for_patient_id(pid)
    if vignette is None:
        msg = f"Missing vignette for optional override demo patient {pid}"
        raise ValueError(msg)
    return build_optional_override_specs(
        vignette,
        str(demo_kind),
        ek2b_procs=ek2b_procs,
    )


def _pick_package_adequacy_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.2 demo: package 609270 billed while 600150+600160 support candidate 609300."""
    _ = (episode, ek2c_packages, rng)
    disable_surcharge = {"disable_surcharge": True}
    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 5000.0))
    price_b = _money(max(price_b, 4000.0))
    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(package_price or 3500.0, 3500.0))
    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]


def _pick_procedure_capture_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.1 demo: colonoscopy billed; polypectomy performed in EMR but not submitted."""
    _ = (episode, ek2c_packages, rng)
    return _pick_procedure_addon_demo_procedures(
        episode,
        ek2b_procs=ek2b_procs,
        ek2c_packages=ek2c_packages,
        rng=rng,
    )


def _pick_session_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 session demo: secondary cerrahi line under-billed vs list × point factor."""
    _ = (episode, ek2c_packages, rng)
    primary_name, primary_price = _lookup_ek2b_price("609270", ek2b_procs)
    secondary_name, secondary_price = _lookup_ek2b_price("610070", ek2b_procs)
    primary_price = _money(primary_price)
    secondary_price = _money(secondary_price)
    underbilled = _money(secondary_price * 0.10)
    disable_surcharge = {"disable_surcharge": True}
    return [
        {
            "code": "609270",
            "name": primary_name,
            "price": primary_price,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": "610070",
            "name": secondary_name,
            "price": secondary_price,
            "category": "islem",
            "included_in_package": False,
            "billed_override": underbilled,
            "payable_override": underbilled,
            **disable_surcharge,
        },
    ]


def _pick_procedure_addon_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 demo: colonoscopy billed without expected polypectomy add-on."""
    _ = (episode, ek2c_packages, rng)
    name, price = _lookup_ek2b_price("701450", ek2b_procs)
    price = _money(price)
    return [
        {
            "code": "701450",
            "name": name,
            "price": price,
            "category": "islem",
            "included_in_package": False,
            "disable_surcharge": True,
        },
    ]


def _pick_care_setting_review_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2 gunubirlik demo: outpatient mandatory package vs inpatient optional override."""
    _ = (episode, ek2c_packages, rng)

    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 4500.0))
    price_b = _money(max(price_b, 3500.0))

    package_code = "609270"
    package_name, catalog_pkg_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(catalog_pkg_price or 3500.0, 3500.0))
    disable_surcharge = {"disable_surcharge": True}

    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_a,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_b,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]
