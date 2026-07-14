"""Claims and lines orchestrator."""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pandas as pd

from catalog import _ek2b, _ek2c1, _ek2c_latest, _ek2g, _ek3_material, _ek4a, _money
from constants import CURATED_DIR
from gen.claim_lines import (
    ClaimEpisodeContext,
    _append_drug_lines_for_claim,
    _append_material_lines_for_claim,
    _append_material_prose_demo_line,
    _append_procedure_lines_for_claim,
)
from gen.drug_fields import _empty_drug_indication_fields
from gen.medula_anchor import _inject_medula_anchor_line
from gen.procedures import (
    _lookup_ek2b_price,
    _pick_blood_uplift_demo_procedures,
    _pick_care_setting_review_demo_procedures,
    _pick_drg_uplift_demo_procedures,
    _pick_gazette_repricing_demo_procedures,
    _pick_material_uplift_demo_procedures,
    _pick_optional_override_demo_procedures,
    _pick_package_adequacy_demo_procedures,
    _pick_payment_method_compliance_demo_procedures,
    _pick_procedure_addon_demo_procedures,
    _pick_procedure_capture_demo_procedures,
    _pick_procedures,
    _pick_session_uplift_demo_procedures,
)
from gen.reconcile import _build_normalized_ek2c1_copay_rates
from gen.specs import (
    PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
    _CLAIM_READINESS_DEMO_SPECS,
    _COPAY_EXEMPTION_DEMO_SPECS,
    _DRUG_INDICATION_DEMO_SPECS,
    _MATERIAL_PROSE_DEMO_SPECS,
    _MEDULA_DEMO_SPECS,
)

def _generate_claims_and_lines(
    episodes: list[dict],
    rng: np.random.Generator,
) -> tuple[
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    dict[tuple, dict],
]:
    ek2b_df = _ek2b()
    ek2c_df = _ek2c_latest()
    ek2c1_df = _ek2c1()
    ek2g_df = _ek2g()
    ek4a_df = _ek4a()

    ek2g_no_surcharge: set[str] = set()
    if not ek2g_df.empty:
        ek2g_no_surcharge = set(ek2g_df["procedure_code"].astype(str).tolist())

    ek2c1_copay_rates = _build_normalized_ek2c1_copay_rates(ek2c1_df)

    ek2c_packages: dict[str, pd.DataFrame] = {}
    if not ek2c_df.empty:
        for grp in ek2c_df["group"].dropna().unique():
            grp_df = ek2c_df[ek2c_df["group"] == grp]
            if not grp_df.empty:
                ek2c_packages[str(grp)] = grp_df

    ek3_all: list[tuple[str, pd.DataFrame]] = []
    for cat_name in sorted(CURATED_DIR.glob("ek3*_materials.parquet")):
        df = _ek3_material(cat_name.name)
        if df.empty:
            continue
        ek3_all.append((cat_name.name, df))

    active_drugs = ek4a_df[
        ek4a_df["passivation_date"].isna() |
        (ek4a_df["passivation_date"].astype(str).isin(["", "nan", "None"]))
    ] if not ek4a_df.empty else ek4a_df

    ek2b_procs: dict[str, pd.DataFrame] = {}
    if not ek2b_df.empty:
        ek2b_df["code_str"] = ek2b_df["code"].astype(str)
        ek2b_procs["general"] = ek2b_df[
            ~ek2b_df["code_str"].str.startswith("L1") &
            ~ek2b_df["code_str"].str.startswith("P")
        ]
        ek2b_procs["lab"] = ek2b_df[ek2b_df["code_str"].str.startswith("L1")]
        ek2b_procs["yatak"] = ek2b_df[ek2b_df["name"].str.contains("yatak", case=False, na=False)]
        ek2b_procs["muayene"] = ek2b_df[
            ek2b_df["name"].str.contains("muayene", case=False, na=False) |
            ek2b_df["name"].str.contains("konsültasyon", case=False, na=False)
        ]

    claims: list[dict] = []
    procedure_rows: list[dict] = []
    performed_rows: list[dict] = []
    medula_rejection_rows: list[dict] = []
    materials: list[dict] = []
    drug_claims: list[dict] = []
    expected: list[dict] = []
    lab_billing_budget: dict[tuple[str, str], dict[str, Any]] = {}

    for ep_idx, episode in enumerate(episodes):
        pid = episode["hasta_id"]
        eid = episode["basvuru_id"]
        visit_type = episode["gelis_tipi"]
        override_demo = episode.get("_sgk_optional_override_demo")
        blood_demo = episode.get("_sgk_blood_uplift_demo")
        drg_demo = episode.get("_sgk_drg_uplift_demo")
        material_demo = episode.get("_sgk_material_uplift_demo")
        care_setting_demo = episode.get("_sgk_care_setting_review_demo")
        procedure_addon_demo = episode.get("_sgk_procedure_addon_demo")
        procedure_capture_demo = episode.get("_sgk_procedure_capture_demo")
        package_adequacy_demo = episode.get("_sgk_package_adequacy_demo")
        gazette_repricing_demo = episode.get("_sgk_gazette_repricing_demo")
        medula_playbook_demo = episode.get("_sgk_medula_playbook_demo")
        medula_demo_spec = (
            _MEDULA_DEMO_SPECS.get(pid.rsplit("-", 1)[-1])
            if medula_playbook_demo
            else None
        )
        session_uplift_demo = episode.get("_sgk_session_uplift_demo")
        drug_indication_demo = episode.get("_sgk_drug_indication_demo")
        material_prose_demo = episode.get("_sgk_material_prose_demo")
        claim_readiness_demo = episode.get("_sgk_claim_readiness_demo")
        payment_method_compliance_demo = episode.get("_payment_method_compliance_demo")
        copay_exemption_demo = episode.get("_copay_exemption_demo")
        copay_exemption_spec = (
            _COPAY_EXEMPTION_DEMO_SPECS.get(str(copay_exemption_demo))
            if copay_exemption_demo
            else None
        )
        drug_indication_spec = (
            _DRUG_INDICATION_DEMO_SPECS.get(str(drug_indication_demo))
            if drug_indication_demo
            else None
        )
        material_prose_spec = (
            _MATERIAL_PROSE_DEMO_SPECS.get(str(material_prose_demo))
            if material_prose_demo
            else None
        )
        claim_readiness_spec = (
            _CLAIM_READINESS_DEMO_SPECS.get(str(claim_readiness_demo))
            if claim_readiness_demo
            else None
        )
        scenario_tag = (
            PAYMENT_METHOD_COMPLIANCE_DEMO_TAG
            if payment_method_compliance_demo
            else copay_exemption_spec["scenario_tag"]
            if copay_exemption_spec
            else medula_demo_spec["scenario_tag"]
            if medula_demo_spec
            else drug_indication_spec["scenario_tag"]
            if drug_indication_spec
            else material_prose_spec["scenario_tag"]
            if material_prose_spec
            else claim_readiness_spec["scenario_tag"]
            if claim_readiness_spec
            else "sgk_session_uplift_cerrahi"
            if session_uplift_demo
            else "sgk_gazette_repricing_600150"
            if gazette_repricing_demo
            else "sgk_package_adequacy_undercoded"
            if package_adequacy_demo
            else "sgk_procedure_capture_kolonoskopi"
            if procedure_capture_demo
            else "sgk_procedure_addon_kolonoskopi"
            if procedure_addon_demo
            else "sgk_care_setting_review_gunubirlik"
            if care_setting_demo
            else "sgk_blood_uplift_yatis"
            if blood_demo
            else "sgk_material_uplift_yatis"
            if material_demo
            else "sgk_drg_uplift_yatis"
            if drg_demo
            else f"sgk_optional_override_{override_demo}"
            if override_demo
            else f"{episode.get('_template', {}).get('specialty', 'genel')}_{visit_type}"
        )
        template = episode.get("_template", {})
        all_codes = episode.get("_all_codes", [])

        claim_id = f"F-{pid}-{(ep_idx + 1):03d}"

        is_university = bool(
            override_demo
            or blood_demo
            or drg_demo
            or material_demo
            or care_setting_demo
            or procedure_addon_demo
            or procedure_capture_demo
            or package_adequacy_demo
            or gazette_repricing_demo
            or medula_playbook_demo
            or session_uplift_demo
            or drug_indication_demo
            or material_prose_demo
            or claim_readiness_demo
            or payment_method_compliance_demo
            or copay_exemption_demo
        ) or rng.random() < 0.15
        if payment_method_compliance_demo:
            facility_tier = "2_basamak_kamu"
            provider = "Kamu"
            is_university = False
        else:
            facility_tier = (
                "egitim_arastirma"
                if is_university
                else rng.choice(["2_3_basamak_ozel", "2_basamak_kamu"])
            )
            provider = "Universite" if is_university else rng.choice(["Ozel", "Kamu"])

        start_date = episode["basvuru_tarihi"]
        if visit_type == "yatis":
            start_dt = dt.date.fromisoformat(start_date)
            los = int(rng.integers(1, 22))
            discharge_dt = start_dt + dt.timedelta(days=los)
            admission = start_date
            discharge = discharge_dt.isoformat()
            claim_end = discharge
        elif care_setting_demo or visit_type == "gunubirlik":
            admission = start_date
            discharge = start_date
            claim_end = start_date
        else:
            admission = None
            discharge = None
            claim_end = start_date

        if blood_demo:
            proc_specs = _pick_blood_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif material_demo:
            proc_specs = _pick_material_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif care_setting_demo:
            proc_specs = _pick_care_setting_review_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif gazette_repricing_demo:
            proc_specs = _pick_gazette_repricing_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif package_adequacy_demo:
            proc_specs = _pick_package_adequacy_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif procedure_capture_demo:
            proc_specs = _pick_procedure_capture_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif procedure_addon_demo:
            proc_specs = _pick_procedure_addon_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif session_uplift_demo:
            proc_specs = _pick_session_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif drg_demo:
            proc_specs = _pick_drg_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif payment_method_compliance_demo:
            proc_specs = _pick_payment_method_compliance_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif override_demo:
            proc_specs = _pick_optional_override_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        else:
            n_procs = rng.integers(3, 9)
            proc_specs = _pick_procedures(
                episode,
                n_procs,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
                facility_tier=facility_tier,
                provider_type=provider,
                allow_mandatory_side_procs=False,
            )

        package_code_for_claim = None
        for ps in proc_specs:
            if ps.get("is_package"):
                package_code_for_claim = ps["code"]
                break
            if ps.get("candidate_package_code"):
                package_code_for_claim = str(ps["candidate_package_code"])

        # DRG uplift demo keeps package lines but package_candidate=False so strategy defers.
        package_candidate = package_code_for_claim is not None and (
            not drg_demo or package_adequacy_demo or override_demo
        )

        ctx = ClaimEpisodeContext(
            pid=pid,
            eid=eid,
            visit_type=visit_type,
            claim_id=claim_id,
            start_date=start_date,
            scenario_tag=scenario_tag,
            facility_tier=facility_tier,
            is_university=is_university,
            provider=provider,
            admission=admission,
            discharge=discharge,
            claim_end=claim_end,
            package_candidate=package_candidate,
            package_code_for_claim=package_code_for_claim,
            all_codes=all_codes,
            template=template,
            ek2g_no_surcharge=ek2g_no_surcharge,
            ek2c1_copay_rates=ek2c1_copay_rates,
            ek3_all=ek3_all,
            active_drugs=active_drugs,
            rng=rng,
            procedure_rows=procedure_rows,
            materials=materials,
            drug_claims=drug_claims,
            expected=expected,
            lab_billing_budget=lab_billing_budget,
            proc_specs=proc_specs,
        )

        proc_billed, proc_payable = _append_procedure_lines_for_claim(ctx)
        if procedure_capture_demo:
            addon_name, _addon_price = _lookup_ek2b_price("701460", ek2b_procs)
            performed_rows.append({
                "gerceklestirilen_satir_id": f"EMR-{claim_id}-001",
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "hizmet_tarihi": start_date,
                "islem_kodu": "701460",
                "islem_adi": addon_name,
                "kaynak": "emr",
            })
        if material_demo or override_demo:
            mat_billed, mat_payable = 0.0, 0.0
        elif material_prose_spec or claim_readiness_spec:
            mat_billed, mat_payable = _append_material_prose_demo_line(
                ctx,
                material_prose_spec or claim_readiness_spec or {},
            )
        else:
            mat_billed, mat_payable = _append_material_lines_for_claim(ctx)
        if override_demo:
            drug_billed, drug_payable = 0.0, 0.0
        else:
            drug_billed, drug_payable = _append_drug_lines_for_claim(ctx)
        if drug_indication_spec:
            d_line_id = f"ILC-{claim_id}-IND-001"
            prescription_id = f"REC-{claim_id}-IND-001"
            unit_price = 12500.0
            qty = 1
            billed = _money(unit_price * qty)
            payable = _money(billed * 0.72)
            drug_row: dict[str, Any] = {
                "ilac_satiri_id": d_line_id,
                "recete_id": prescription_id,
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "ilac_fatura_tarihi": start_date,
                "ilac_adi": drug_indication_spec["ilac_adi"],
                "ilac_kodu": drug_indication_spec["ilac_kodu"],
                "barkod": drug_indication_spec["barkod"],
                "esdeger_grup": drug_indication_spec["esdeger_grup"],
                "adet": qty,
                "birim_fiyat_try": unit_price,
                "fatura_tutari_try": billed,
                "beklenen_odenebilir_tutar_try": payable,
                "beklenen_indirim_kademesi": 0.28,
                "beklenen_red_nedeni": drug_indication_spec["beklenen_red_nedeni"],
                "beklenen_kural_izi": drug_indication_spec["beklenen_kural_izi"],
                "uzmanlik_kurulu_raporu_var": drug_indication_spec["uzmanlik_kurulu_raporu_var"],
                **_empty_drug_indication_fields(),
            }
            drug_row["uzmanlik_kurulu_raporu_var"] = drug_indication_spec["uzmanlik_kurulu_raporu_var"]
            for optional_key in ("rapor_suresi_ay", "yatarak_tedavi_ilac", "recete_eden_uzmanlik"):
                if optional_key in drug_indication_spec:
                    drug_row[optional_key] = drug_indication_spec[optional_key]
            ctx.drug_claims.append(drug_row)
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{d_line_id}",
                "senaryo_etiketi": drug_indication_spec["scenario_tag"],
                "hasta_id": pid,
                "fatura_id": claim_id,
                "satir_id": d_line_id,
                "satir_tipi": "ilac",
                "kural_ailesi": "drug_indication",
                "beklenen_durum": (
                    drug_indication_spec["beklenen_kural_izi"].split(":")[-1]
                    if drug_indication_spec.get("beklenen_kural_izi")
                    else "odenebilir"
                ),
                "beklenen_odenebilir_tutar_try": payable,
                "beklenen_tasarruf_try": _money(billed - payable),
                "beklenen_red_nedeni": drug_indication_spec["beklenen_red_nedeni"],
                "beklenen_kural_izi": drug_indication_spec["beklenen_kural_izi"],
                "test_notu": "§4.2 drug indication demo drug line",
            })
            drug_billed += billed
            drug_payable += payable

        # MEDULA rejection demo: inject the offending anchor line ON TOP of the
        # realistic base bill, then stamp the rejection row pointing at it. The
        # anchor line(s) are added after all base lines so their ids continue
        # the existing numbering and their amounts fold into the claim total.
        if medula_demo_spec:
            anchor_ptr = _inject_medula_anchor_line(
                ctx, medula_demo_spec.get("anchor") or {"type": "claim"}, ek2b_procs
            )
            anchor_billed = float(anchor_ptr.get("anchor_billed") or 0.0)
            anchor_payable = float(anchor_ptr.get("anchor_payable") or 0.0)
            proc_billed = _money(proc_billed + anchor_billed)
            proc_payable = _money(proc_payable + anchor_payable)
            medula_rejection_rows.append({
                "medula_red_satir_id": f"MEDULA-{claim_id}-001",
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "medula_asamasi": medula_demo_spec["medula_asamasi"],
                "sonuc_kodu": medula_demo_spec["sonuc_kodu"],
                "hata_kodu": medula_demo_spec["hata_kodu"],
                "hata_mesaji": medula_demo_spec["hata_mesaji"],
                "red_zamani": start_date,
                "ilgili_islem_kodu": anchor_ptr.get("ilgili_islem_kodu", ""),
                "ilgili_islem_satiri_id": anchor_ptr.get("ilgili_islem_satiri_id", ""),
                "ilgili_satir_tipi": anchor_ptr.get("related_line_type", ""),
                "ilgili_satir_id": anchor_ptr.get("related_line_id", ""),
            })

        total_billed = proc_billed + mat_billed + drug_billed
        total_payable = proc_payable + mat_payable + drug_payable
        total_billed = max(total_billed, 0.01)
        total_payable = max(total_payable, 0.0)
        total_billed = _money(total_billed)
        total_payable = _money(total_payable)

        occupational_context = "none"
        if visit_type in ("is_kazasi", "meslek_hastaligi"):
            occupational_context = visit_type

        claims.append({
            "fatura_id": claim_id,
            "hasta_id": pid,
            "basvuru_id": eid,
            "fatura_tipi": visit_type,
            "mesleki_kontekst": occupational_context,
            "kurum_basamagi": facility_tier,
            "saglayici_tipi": provider,
            "servis_adi": episode["servis_adi"],
            "yatis_tarihi": admission,
            "taburcu_tarihi": discharge,
            "fatura_baslangic_tarihi": start_date,
            "fatura_bitis_tarihi": claim_end,
            "birincil_icd10": all_codes[0] if all_codes else "",
            "paket_adayi_mi": package_candidate,
            "beklenen_toplam_fatura_tutari_try": _money(total_billed),
            "beklenen_toplam_odenebilir_tutar_try": _money(total_payable),
            "beklenen_red_nedeni": "Kismi paket ici satir reddi" if total_payable < total_billed else "",
            "senaryo_etiketi": scenario_tag,
        })

        expected.append({
            "beklenen_cikti_id": f"BEK-{claim_id}",
            "senaryo_etiketi": scenario_tag,
            "hasta_id": pid,
            "fatura_id": claim_id,
            "satir_id": "",
            "satir_tipi": "fatura",
            "kural_ailesi": "fatura_dogrulama",
            "beklenen_durum": "kismi_red" if total_payable < total_billed else "odenebilir",
            "beklenen_odenebilir_tutar_try": _money(total_payable),
            "beklenen_tasarruf_try": _money(total_billed - total_payable),
            "beklenen_red_nedeni": "Paket ici satirlar reddedilir" if total_payable < total_billed else "",
            "beklenen_kural_izi": scenario_tag,
            "test_notu": "Fatura duzeyi sentetik beklenen cikti",
        })

    return (
        claims,
        procedure_rows,
        performed_rows,
        medula_rejection_rows,
        materials,
        drug_claims,
        expected,
        lab_billing_budget,
    )
