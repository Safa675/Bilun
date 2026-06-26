"""Top-level workbook table assembly."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

import numpy as np
import pandas as pd

from constants import SYNTHETIC_NOTICE
from gen.ancillary import _generate_lab_results, _generate_prescriptions
from gen.drug_fields import _ensure_drug_indication_columns
from gen.materials_flags import _ensure_prose_flag_coverage, _ensure_specialty_flag_coverage
from gen.orchestrate import _generate_claims_and_lines
from gen.patients import _assign_scenarios, _generate_patients
from gen.reconcile import (
    _ensure_ek2c1_violation_demos,
    _inject_specialty_keyword_demo_rows,
    _reconcile_claim_header_totals,
    _reconcile_ek2c1_procedure_lines,
    _build_normalized_ek2c1_copay_rates,
)
from catalog import _ek2c1

def build_workbook_tables(
    num_patients: int = 50,
    min_claims_per_patient: int = 1,
    max_claims_per_patient: int = 5,
    seed: int = 20260504,
) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    patients = _generate_patients(num_patients, rng)
    episodes, diagnosis_rows = _assign_scenarios(patients, rng)

    patient_episodes: dict[str, list] = defaultdict(list)
    patient_scenarios: dict[str, set] = defaultdict(set)
    for ep in episodes:
        patient_episodes[ep["hasta_id"]].append(ep)
        patient_scenarios[ep["hasta_id"]].add(
            ep.get("_template", {}).get("specialty", "genel")
        )
    for p in patients:
        pid = p["hasta_id"]
        n_eps = len(patient_episodes.get(pid, []))
        p["hasta_toplam_gelis_sayisi"] = n_eps
        p["ana_senaryo"] = ",".join(sorted(patient_scenarios.get(pid, {"genel"})))

    (
        claims,
        procedure_rows,
        performed_rows,
        medula_rejection_rows,
        materials,
        drug_claims,
        expected,
        lab_billing_budget,
    ) = _generate_claims_and_lines(episodes, rng)
    # Inpatient (yatarak) claim ids — needed so coverage post-passes don't set
    # inpatient-scoped flags on outpatient materials (false-positive guard).
    inpatient_claim_ids = frozenset(
        str(c.get("fatura_id", ""))
        for c in claims
        if "yatis" in str(c.get("fatura_tipi", "")) or "yatarak" in str(c.get("fatura_tipi", ""))
    )
    _ensure_prose_flag_coverage(materials, inpatient_claim_ids=inpatient_claim_ids)
    _ensure_specialty_flag_coverage(materials, claims=claims)
    _inject_specialty_keyword_demo_rows(materials, claims)
    ek2c1_copay_rates = _build_normalized_ek2c1_copay_rates(_ek2c1())
    _reconcile_ek2c1_procedure_lines(procedure_rows, ek2c1_copay_rates)
    _ensure_ek2c1_violation_demos(procedure_rows, ek2c1_copay_rates)
    _reconcile_claim_header_totals(
        claims, procedure_rows, materials, drug_claims, expected
    )

    prescriptions = _generate_prescriptions(drug_claims, patients)
    lab_rows = _generate_lab_results(episodes, lab_billing_budget, rng)

    for ep in episodes:
        pid = ep["hasta_id"]
        n_eps = len(patient_episodes.get(pid, []))
        ep["hasta_toplam_gelis_sayisi"] = n_eps

    scenario_tags = sorted({c["senaryo_etiketi"] for c in claims})
    manifest = pd.DataFrame([{
        "veri_seti_id": f"sentetik_sut_v2_{num_patients}_hasta",
        "versiyon": "2.0.0",
        "olusturulma_zamani": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rastgelelik_tohumu": seed,
        "hasta_sayisi": len(patients),
        "basvuru_sayisi": len(episodes),
        "islem_satiri_sayisi": len(procedure_rows),
        "ilac_satiri_sayisi": len(drug_claims),
        "malzeme_satiri_sayisi": len(materials),
        "laboratuvar_sonucu_sayisi": len(lab_rows),
        "senaryo_etiketleri": ",".join(scenario_tags[:50]),
        "sentetik_uyari": SYNTHETIC_NOTICE,
    }])

    copay_profiles = [
        {
            "hasta_id": p["hasta_id"],
            "sgk_yararlanma_sinifi": p.get("sgk_yararlanma_sinifi", "standard"),
            "gazi_sehit_durumu": p.get("gazi_sehit_durumu", "none"),
            "vatani_hizmet_durumu": p.get("vatani_hizmet_durumu", "none"),
            "yasli_aylik_2022": bool(p.get("yasli_aylik_2022", False)),
            "dogum_yili": int(p.get("dogum_yili") or 1970),
        }
        for p in patients
    ]

    return {
        "veri_seti_manifestosu": manifest,
        "hastalar": pd.DataFrame(patients),
        "hasta_katilim_payi_profilleri": pd.DataFrame(copay_profiles),
        "basvurular": pd.DataFrame(episodes),
        "tani_satirlari": pd.DataFrame(diagnosis_rows),
        "fatura_basliklari": pd.DataFrame(claims),
        "islem_fatura_satirlari": pd.DataFrame(procedure_rows),
        "gerceklestirilen_islem_satirlari": pd.DataFrame(performed_rows),
        "medula_red_satirlari": pd.DataFrame(medula_rejection_rows),
        "malzeme_fatura_satirlari": pd.DataFrame(materials),
        "ilac_fatura_satirlari": pd.DataFrame(_ensure_drug_indication_columns(drug_claims)),
        "receteler": pd.DataFrame(prescriptions),
        "laboratuvar_sonuclari": pd.DataFrame(lab_rows),
        "beklenen_kural_ciktilari": pd.DataFrame(expected),
        "katalog_alt_kumesi": pd.DataFrame(),
    }
