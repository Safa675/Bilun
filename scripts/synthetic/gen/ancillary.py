"""Prescription and lab result generation."""

from __future__ import annotations

from typing import Any

import numpy as np

def _generate_prescriptions(drug_claim_rows: list[dict], patients: list[dict]) -> list[dict]:
    prescriptions = []
    pid_to_kohort = {p["hasta_id"]: p["kohort"] for p in patients}
    for drug in drug_claim_rows:
        prescriptions.append({
            "recete_id": drug["recete_id"],
            "hasta_id": drug["hasta_id"],
            "recete_tarihi": drug["ilac_fatura_tarihi"],
            "basvuru_id": drug["basvuru_id"],
            "ilac_adi": drug["ilac_adi"],
            "ham_ilac_adi": drug["ilac_adi"],
            "ham_dozaj": "1 kutu",
            "verilis_yolu": "Agizdan (Oral)",
            "gun": 7,
            "doz_mg": 500,
            "doz_birimi": "mg",
            "siklik": 2,
            "miktar": drug["adet"],
            "kohort": pid_to_kohort.get(drug["hasta_id"], "checkup"),
            "donem": "2024",
        })
    return prescriptions


# ── Lab result generation ────────────────────────────────────────────
def _generate_lab_results(
    episodes: list[dict],
    lab_billing_budget: dict[tuple[str, str], dict],
    rng: np.random.Generator,
) -> list[dict]:
    lab_rows: list[dict] = []
    for episode in episodes:
        eid = episode["basvuru_id"]
        pid = episode["hasta_id"]
        kohort = episode["kohort"]

        for (budget_eid, code), budget in lab_billing_budget.items():
            if budget_eid != eid:
                continue
            qty = int(budget.get("kalan_adet", 0))
            test_name = budget.get("test_adi", code)
            total_reps = max(int(qty) + 2, 4)
            for rep in range(total_reps):
                ref_low = round(rng.uniform(0.0, 5.0), 2)
                ref_high = round(rng.uniform(10.0, 200.0), 2)
                value = round(rng.uniform(ref_low * 0.5, ref_high * 1.5), 2)
                abnormal = value < ref_low or value > ref_high
                is_billed = rep < int(qty)

                lab_rows.append({
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "test_tarihi": episode["basvuru_tarihi"],
                    "laboratuvar_kodu": code,
                    "laboratuvar_adi": test_name,
                    "sayisal_sonuc": value,
                    "nitel_sonuc": "Pozitif" if abnormal and rng.random() < 0.3 else "",
                    "birim": rng.choice(["mg/dL", "mm/h", "/mm3", "U/L", "g/dL", "mEq/L"]),
                    "referans_alt": ref_low,
                    "referans_ust": ref_high,
                    "anormal_mi": abnormal,
                    "organ_sistemi": rng.choice([
                        "Hematoloji", "Biyokimya", "Endokrinoloji",
                        "Mikrobiyoloji", "Seroloji", "Onkoloji",
                    ]),
                    "kohort": kohort,
                    "donem": "2024",
                    "faturalama_durumu": "faturalandirildi" if is_billed else "klinik_kanit_faturalandirilmadi",
                    "islem_satiri_id": budget.get("islem_satiri_id", "") if is_billed else "",
                })
    return lab_rows
