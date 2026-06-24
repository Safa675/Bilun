#!/usr/bin/env python3
"""Validate the v1 SUT synthetic billing dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bilun.domain.claims.schema import build_synthetic_claim_validation_columns
from demo_config import load_demo_manifest, tier_a_patient_ids, vignette_registry

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
WORKBOOK_NAME = "sentetik_sut_v2_50_hasta.xlsx"
MIN_PATIENTS = 50
MIN_CLAIMS = 90
MIN_PROCEDURES = 300
MIN_DRUGS = 60
MIN_MATERIALS = 50
MIN_LABS = 500

REQUIRED_SHEETS = [
    "veri_seti_manifestosu",
    "hastalar",
    "basvurular",
    "tani_satirlari",
    "fatura_basliklari",
    "islem_fatura_satirlari",
    "malzeme_fatura_satirlari",
    "ilac_fatura_satirlari",
    "receteler",
    "laboratuvar_sonuclari",
    "beklenen_kural_ciktilari",
    "katalog_alt_kumesi",
]

REQUIRED_CLEAN_COLUMNS = {
    "anadata_clean.parquet": {
        "HASTA_ID",
        "SQ_EPISODE",
        "EPISODE_TARIH",
        "TANIKODU",
        "GELIS_TIPI",
        "SERVISADI",
    },
    "lab_clean.parquet": {"HASTA_ID", "basvuru_id", "SUB_CODE", "sonuc_sayisal", "tarih"},
    "recete_clean.parquet": {"HASTA_ID", "RECETE_TARIH", "RF_EPISODE", "ilac_adi"},
}

REQUIRED_CLAIM_COLUMNS = build_synthetic_claim_validation_columns()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate SUT synthetic v1 data")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Synthetic SUT data directory",
    )
    return parser.parse_args()


def _error(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"ERROR: {message}")


def _strings(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _truthy(series: pd.Series) -> pd.Series:
    normalized = _strings(series).str.lower()
    return normalized.isin({"true", "1", "evet", "yes"})


def _read_excel(data_dir: Path, errors: list[str]) -> dict[str, pd.DataFrame]:
    workbook = data_dir / WORKBOOK_NAME
    if not workbook.exists():
        _error(errors, f"Workbook missing: {workbook}")
        return {}
    with pd.ExcelFile(workbook) as xls:
        missing = [sheet for sheet in REQUIRED_SHEETS if sheet not in xls.sheet_names]
        for sheet in missing:
            _error(errors, f"Workbook missing sheet: {sheet}")
        return {
            sheet: pd.read_excel(xls, sheet_name=sheet)
            for sheet in REQUIRED_SHEETS
            if sheet in xls.sheet_names
        }


def _validate_workbook(tables: dict[str, pd.DataFrame], errors: list[str]) -> None:
    if not tables:
        return
    patients = tables["hastalar"]
    if len(patients) < MIN_PATIENTS:
        _error(errors, f"Expected at least {MIN_PATIENTS} patients, found {len(patients)}")
    patient_ids = set(patients["hasta_id"].astype(str))
    bad_ids = [pid for pid in patient_ids if not pid.startswith("SENTETIK-HASTA-")]
    if bad_ids:
        _error(errors, f"Non-fake-looking patient IDs found: {bad_ids}")

    procedures = tables["islem_fatura_satirlari"]
    patients_with_procedures = set(procedures["hasta_id"].astype(str))
    missing_proc = sorted(patient_ids - patients_with_procedures)
    if missing_proc:
        _error(errors, f"Patients without procedure lines: {missing_proc}")
    if len(procedures) < MIN_PROCEDURES:
        _error(errors, f"Expected at least {MIN_PROCEDURES} procedure lines, found {len(procedures)}")
    if len(tables["malzeme_fatura_satirlari"]) < MIN_MATERIALS:
        _error(
            errors,
            f"Expected at least {MIN_MATERIALS} material lines, found {len(tables['malzeme_fatura_satirlari'])}",
        )
    if len(tables["ilac_fatura_satirlari"]) < MIN_DRUGS:
        _error(
            errors,
            f"Expected at least {MIN_DRUGS} drug claim lines, found {len(tables['ilac_fatura_satirlari'])}",
        )
    if len(tables["laboratuvar_sonuclari"]) < MIN_LABS:
        _error(
            errors,
            f"Expected at least {MIN_LABS} lab rows, found {len(tables['laboratuvar_sonuclari'])}",
        )
    if len(tables["fatura_basliklari"]) < MIN_CLAIMS:
        _error(
            errors,
            f"Expected at least {MIN_CLAIMS} claims, found {len(tables['fatura_basliklari'])}",
        )
    _validate_lab_traceability(tables, procedures, errors)
    _validate_prescription_traceability(tables, errors)
    _validate_expected_outputs(tables, procedures, errors)

    episodes = set(tables["basvurular"]["basvuru_id"].astype(str))
    claims = set(tables["fatura_basliklari"]["fatura_id"].astype(str))
    for sheet, pid_col in [
        ("basvurular", "hasta_id"),
        ("fatura_basliklari", "hasta_id"),
        ("islem_fatura_satirlari", "hasta_id"),
        ("malzeme_fatura_satirlari", "hasta_id"),
        ("ilac_fatura_satirlari", "hasta_id"),
    ]:
        unknown = sorted(set(tables[sheet][pid_col].astype(str)) - patient_ids)
        if unknown:
            _error(errors, f"{sheet} has unknown patient IDs: {unknown}")

    for sheet in ["fatura_basliklari", "islem_fatura_satirlari", "ilac_fatura_satirlari"]:
        if "basvuru_id" in tables[sheet].columns:
            unknown = sorted(set(tables[sheet]["basvuru_id"].astype(str)) - episodes)
            if unknown:
                _error(errors, f"{sheet} has unknown episode IDs: {unknown}")

    for sheet in ["islem_fatura_satirlari", "malzeme_fatura_satirlari", "ilac_fatura_satirlari"]:
        unknown = sorted(set(tables[sheet]["fatura_id"].astype(str)) - claims)
        if unknown:
            _error(errors, f"{sheet} has unknown claim IDs: {unknown}")

    inpatient = tables["fatura_basliklari"][
        tables["fatura_basliklari"]["fatura_tipi"].astype(str) == "yatis"
    ]
    missing_dates = inpatient[
        inpatient["yatis_tarihi"].isna() | inpatient["taburcu_tarihi"].isna()
    ]
    if not missing_dates.empty:
        _error(errors, "Inpatient claims with missing admission/discharge dates")


def _validate_lab_traceability(
    tables: dict[str, pd.DataFrame],
    procedures: pd.DataFrame,
    errors: list[str],
) -> None:
    labs = tables["laboratuvar_sonuclari"]
    required_columns = {"faturalama_durumu", "islem_satiri_id"}
    missing = sorted(required_columns - set(labs.columns))
    if missing:
        _error(errors, f"laboratuvar_sonuclari missing columns: {missing}")
        return

    statuses = _strings(labs["faturalama_durumu"])
    allowed_statuses = {"faturalandirildi", "klinik_kanit_faturalandirilmadi"}
    bad_statuses = sorted(set(statuses) - allowed_statuses)
    if bad_statuses:
        _error(errors, f"Unknown lab billing statuses: {bad_statuses}")

    procedure_line_ids = set(_strings(procedures["islem_satiri_id"]))
    procedure_by_line = {
        str(row["islem_satiri_id"]): row
        for _, row in procedures.iterrows()
    }
    linked_ids = _strings(labs["islem_satiri_id"])
    billed_labs = labs[statuses == "faturalandirildi"]
    if billed_labs.empty:
        _error(errors, "No billed lab results are linked to procedure lines")
    billed_link_ids = _strings(billed_labs["islem_satiri_id"])
    blank_billed = billed_labs[billed_link_ids == ""]
    if not blank_billed.empty:
        _error(errors, "Billed lab rows without islem_satiri_id links")
    unknown_links = sorted(set(billed_link_ids[billed_link_ids != ""]) - procedure_line_ids)
    if unknown_links:
        _error(errors, f"Billed lab rows link to unknown procedure lines: {unknown_links}")

    for _, lab in billed_labs.iterrows():
        line_id = str(lab["islem_satiri_id"]).strip()
        if not line_id or line_id not in procedure_by_line:
            continue
        procedure = procedure_by_line[line_id]
        if str(procedure["islem_kategorisi"]) != "laboratuvar":
            _error(errors, f"Lab row links to non-lab procedure line: {line_id}")
        if str(procedure["islem_kodu"]) != str(lab["laboratuvar_kodu"]):
            _error(errors, f"Lab row code does not match linked procedure line: {line_id}")

    non_billed = labs[statuses == "klinik_kanit_faturalandirilmadi"]
    linked_non_billed = non_billed[_strings(non_billed["islem_satiri_id"]) != ""]
    if not linked_non_billed.empty:
        _error(errors, "Non-billed clinical lab rows should not have procedure line links")

    billed_lab_procedures = procedures[
        _strings(procedures["islem_kategorisi"]) == "laboratuvar"
    ]
    missing_result_links = sorted(
        set(_strings(billed_lab_procedures["islem_satiri_id"]))
        - set(linked_ids[linked_ids != ""])
    )
    if missing_result_links:
        _error(errors, f"Billed lab procedure lines have no linked lab result: {missing_result_links}")


def _validate_prescription_traceability(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    prescriptions = tables["receteler"]
    drug_lines = tables["ilac_fatura_satirlari"]
    for sheet, df in [("receteler", prescriptions), ("ilac_fatura_satirlari", drug_lines)]:
        if "recete_id" not in df.columns:
            _error(errors, f"{sheet} missing recete_id column")
            return
        blank = df[_strings(df["recete_id"]) == ""]
        if not blank.empty:
            _error(errors, f"{sheet} has blank recete_id values")

    prescription_ids = set(_strings(prescriptions["recete_id"]))
    if len(prescription_ids) != len(prescriptions):
        _error(errors, "receteler has duplicate recete_id values")
    unknown = sorted(set(_strings(drug_lines["recete_id"])) - prescription_ids)
    if unknown:
        _error(errors, f"Drug claim lines reference unknown recete_id values: {unknown}")


MATERIAL_PROSE_WORKBOOK_COLUMNS = (
    "titubb_kayitli_mi",
    "uts_kayitli_mi",
    "ihale_ekrani_eksik_mi",
    "bagli_islem_odenmez",
    "yurtdisi_kurum",
    "kurum_islem_kisiti_ihlali",
    "tani_medula_paket_ayri_fatura_yok",
    "ihale_fiyat_referansi_yetersiz",
    "medula_kod_tarihte_tanimsiz",
    "barkod_sut_uyumsuz",
    "tani_paket_malzeme_kapsam",
    "capraz_brans_fatura_ihlali",
    "ortez_protez_sozlesme_ihlali",
    "bakim_onarim_cap_asimi",
    "protez_onarim_belge_eksik",
    "garanti_bakim_prosedur_eksik",
    "ortez_protez_bakim_dogrulanmadi",
    "ihale_dts_zorunlu_alan_eksik",
    "tedarikci_sozlesme_fiyat_yolu",
    "ek3c_yatarak_dis_temin_ihlali",
    "ek3c_liste_fiyati_yok",
    "ek3_kalite_belge_eksik",
    "ek3c_miat_erken_yenileme",
    "ek3c_ismarlama_ihlali",
    "ek3c_tibbi_uygunluk_eksik",
    "ek3c_basi_giysi_sozlesme",
    "ek3c_mucbir_sebep_yenileme",
    "ek3c_ayakta_tedavi_kapsam",
    "yatarak_kurum_temin_ihlali",
    "karsilanmayan_yatarak_hasta",
    "laboratuvar_ayri_fatura",
    "cok_bransli_sarf_brans",
    "recete_miktar_asimi",
    "rapor_recete_gecersiz",
    "fatura_belge_eksik",
    "tani_paket_malzeme",
    "acil_sozlesmesiz_kurum",
    "listesiz_kesinti_fatura",
    "cift_tekerlekli_recete",
    "ayakta_sozlesmeli_temin",
    "cocuk_buyume_miat",
    "sozlesmeli_temin_kapsam",
    "ismarlama_bilesen_titubb_eksik",
    "titubb_uts_barkod_belge_eksik",
)

MATERIAL_PROSE_DEMO_PATIENTS: dict[str, str] = {
    "SENTETIK-HASTA-0021": "sgk_specialty_prose_optical_lens_upgrade",
    "SENTETIK-HASTA-0022": "sgk_specialty_prose_hip_graft_no_pay",
    "SENTETIK-HASTA-0023": "sgk_material_kdv_ceiling_exceeded",
    "SENTETIK-HASTA-0024": "sgk_material_bundling_procurement_incomplete",
}

MATERIAL_PROSE_DEMO_MATERIAL_CODES: dict[str, str] = {
    "SENTETIK-HASTA-0021": "SUT-DEMO-OPT",
    "SENTETIK-HASTA-0022": "SUT-DEMO-GRF",
    "SENTETIK-HASTA-0023": "OP1592",
    "SENTETIK-HASTA-0024": "OP1000",
}

MATERIAL_PROSE_DEMO_FLAG_EXPECTATIONS: dict[str, dict[str, object]] = {
    "SENTETIK-HASTA-0021": {"optical_lens_upgrade_difference_claim": True},
    "SENTETIK-HASTA-0022": {"hip_arthroplasty_graft_claim": True},
    "SENTETIK-HASTA-0024": {"ihale_ekrani_eksik_mi": True},
}

DRUG_INDICATION_DEMO_PATIENTS: dict[str, str] = {
    "SENTETIK-HASTA-0014": "sgk_drug_indication_bevacizumab_missing_report",
    "SENTETIK-HASTA-0015": "sgk_drug_indication_nivolumab_indication_mismatch",
    "SENTETIK-HASTA-0016": "sgk_drug_indication_daratumumab_report_unknown",
    "SENTETIK-HASTA-0017": "sgk_drug_indication_pembrolizumab_report_ok",
    "SENTETIK-HASTA-0019": "sgk_drug_indication_trastuzumab_report_duration_mismatch",
    "SENTETIK-HASTA-0020": "sgk_drug_indication_trabectedin_missing_report",
}

DRUG_INDICATION_DEMO_TIER_B_FIELDS: dict[str, dict[str, object]] = {
    "SENTETIK-HASTA-0017": {
        "yatarak_tedavi_ilac": True,
    },
    "SENTETIK-HASTA-0019": {
        "rapor_suresi_ay": 12,
        "recete_eden_uzmanlik": "Tıbbi Onkoloji",
        "uzmanlik_kurulu_raporu_var": True,
    },
    "SENTETIK-HASTA-0020": {
        "uzmanlik_kurulu_raporu_var": False,
    },
}

PAYMENT_METHOD_COMPLIANCE_DEMO_TAG = "payment_method_compliance_demo"
PAYMENT_METHOD_COMPLIANCE_DEMO_PATIENTS: dict[str, str] = {
    "SENTETIK-HASTA-0038": PAYMENT_METHOD_COMPLIANCE_DEMO_TAG,
}

DRUG_INDICATION_WORKBOOK_COLUMNS = (
    "uzmanlik_kurulu_raporu_var",
    "rapor_suresi_ay",
    "yatarak_tedavi_ilac",
    "recete_eden_uzmanlik",
)


def _validate_specialty_prose_flags(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    import sys

    synth_dir = PROJECT_ROOT / "scripts" / "synthetic"
    if str(synth_dir) not in sys.path:
        sys.path.insert(0, str(synth_dir))
    from generators import SPECIALTY_PROSE_FLAG_COLUMNS  # noqa: E402

    materials = tables.get("malzeme_fatura_satirlari")
    if materials is None or materials.empty:
        return

    missing_cols = [
        col for col in SPECIALTY_PROSE_FLAG_COLUMNS if col not in materials.columns
    ]
    if missing_cols:
        _error(
            errors,
            f"malzeme_fatura_satirlari missing L4.4 specialty flag columns: {missing_cols}",
        )
        return

    for col in SPECIALTY_PROSE_FLAG_COLUMNS:
        if not _truthy(materials[col]).any():
            _error(errors, f"Expected at least one material line with {col}=true")


def _validate_material_prose_flags(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    materials = tables.get("malzeme_fatura_satirlari")
    if materials is None or materials.empty:
        return

    missing_cols = [
        col for col in MATERIAL_PROSE_WORKBOOK_COLUMNS if col not in materials.columns
    ]
    if missing_cols:
        _error(errors, f"malzeme_fatura_satirlari missing prose flag columns: {missing_cols}")
        return

    for col in MATERIAL_PROSE_WORKBOOK_COLUMNS:
        if col in {"titubb_kayitli_mi", "uts_kayitli_mi"}:
            if col == "titubb_kayitli_mi":
                has_demo = (~_truthy(materials[col])).any()
                label = "titubb_kayitli_mi=false (TİTUBB incomplete demo row)"
            else:
                has_demo = (~_truthy(materials[col])).any()
                label = "uts_kayitli_mi=false (ÜTS incomplete demo row)"
        else:
            has_demo = _truthy(materials[col]).any()
            label = f"{col}=true"
        if not has_demo:
            _error(errors, f"Expected at least one material line with {label}")


def _workbook_care_setting(claim_type: str) -> str:
    if str(claim_type).strip() in {"yatis", "gunubirlik"}:
        return "inpatient"
    return "outpatient"


def _validate_payment_method_compliance_demos(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    claims = tables.get("fatura_basliklari")
    procedures = tables.get("islem_fatura_satirlari")
    if claims is None or procedures is None or claims.empty or procedures.empty:
        return

    for patient_id, scenario_tag in PAYMENT_METHOD_COMPLIANCE_DEMO_PATIENTS.items():
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Missing claim for payment-method compliance demo patient {patient_id}")
            continue
        matching = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == scenario_tag]
        if matching.empty:
            _error(
                errors,
                f"Patient {patient_id} missing scenario_tag {scenario_tag!r}",
            )
            continue

        demo_claim_ids = set(_strings(matching["fatura_id"]))
        demo_procs = procedures[_strings(procedures["fatura_id"]).isin(demo_claim_ids)]
        billed_paket = demo_procs[
            (_strings(demo_procs["islem_kategorisi"]) == "paket")
            & (pd.to_numeric(demo_procs["fatura_tutari_try"], errors="coerce").fillna(0) > 0)
        ]
        if billed_paket.empty:
            _error(
                errors,
                f"Payment-method compliance demo patient {patient_id} missing billed paket line",
            )


def _validate_packaged_claim_mandatory_side_procedures(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    from src.bilun.domain.prose_rules.payment_method import resolve_payment_method

    claims = tables.get("fatura_basliklari")
    procedures = tables.get("islem_fatura_satirlari")
    if claims is None or procedures is None or claims.empty or procedures.empty:
        return

    claim_by_id = {
        str(row["fatura_id"]): row
        for _, row in claims.iterrows()
    }
    for claim_id, claim_row in claim_by_id.items():
        claim_procs = procedures[_strings(procedures["fatura_id"]) == claim_id]
        if claim_procs.empty:
            continue

        billed_paket = claim_procs[
            (_strings(claim_procs["islem_kategorisi"]) == "paket")
            & (pd.to_numeric(claim_procs["fatura_tutari_try"], errors="coerce").fillna(0) > 0)
        ]
        if billed_paket.empty:
            continue

        scenario_tag = str(claim_row.get("senaryo_etiketi") or "").strip()
        if scenario_tag == PAYMENT_METHOD_COMPLIANCE_DEMO_TAG:
            continue

        care_setting = _workbook_care_setting(str(claim_row.get("fatura_tipi") or ""))
        facility_tier = str(claim_row.get("kurum_basamagi") or "").strip() or None
        provider_type = str(claim_row.get("saglayici_tipi") or "").strip() or None
        claim_date = claim_row.get("fatura_baslangic_tarihi")

        offenders: list[str] = []
        for _, proc_row in claim_procs.iterrows():
            if _truthy(pd.Series([proc_row.get("pakete_dahil_mi")])).iloc[0]:
                continue
            if str(proc_row.get("islem_kategorisi") or "").strip() == "paket":
                continue
            payable = float(pd.to_numeric(proc_row.get("beklenen_odenebilir_tutar_try"), errors="coerce") or 0)
            if payable <= 0:
                continue

            as_of_date = proc_row.get("islem_tarihi") or claim_date
            code = str(proc_row.get("islem_kodu") or "").strip()
            if not code:
                continue

            result = resolve_payment_method(
                code,
                care_setting=care_setting,  # type: ignore[arg-type]
                facility_tier=facility_tier,
                provider_type=provider_type,
                as_of_date=as_of_date,
            )
            if result.kind == "DRG_MANDATORY":
                offenders.append(code)

        if offenders:
            _error(
                errors,
                f"Claim {claim_id} has DRG_MANDATORY side procedures on a packaged bill: "
                f"{sorted(set(offenders))}",
            )


def _validate_drug_indication_demos(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    drugs = tables.get("ilac_fatura_satirlari")
    claims = tables.get("fatura_basliklari")
    if drugs is None or claims is None or drugs.empty or claims.empty:
        return

    missing_cols = [
        col for col in DRUG_INDICATION_WORKBOOK_COLUMNS if col not in drugs.columns
    ]
    if missing_cols:
        _error(
            errors,
            f"ilac_fatura_satirlari missing §4.2 drug indication columns: {missing_cols}",
        )
        return

    for patient_id, scenario_tag in DRUG_INDICATION_DEMO_PATIENTS.items():
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Missing claim for drug indication demo patient {patient_id}")
            continue
        matching = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == scenario_tag]
        if matching.empty:
            _error(
                errors,
                f"Patient {patient_id} missing scenario_tag {scenario_tag!r}",
            )
        patient_drugs = drugs[_strings(drugs["hasta_id"]) == patient_id]
        if patient_drugs.empty:
            _error(errors, f"Patient {patient_id} missing drug claim lines")
            continue

        demo_drugs = patient_drugs[
            _strings(patient_drugs["ilac_kodu"]).str.startswith("SUT-DEMO-")
        ]
        if demo_drugs.empty:
            _error(errors, f"Patient {patient_id} missing SUT-DEMO drug indication line")
            continue

        tier_b_expect = DRUG_INDICATION_DEMO_TIER_B_FIELDS.get(patient_id)
        if tier_b_expect:
            drug_row = demo_drugs.iloc[0]
            for column, expected in tier_b_expect.items():
                actual = drug_row.get(column)
                if pd.isna(actual):
                    actual = None
                if actual != expected:
                    _error(
                        errors,
                        f"Patient {patient_id} demo drug {column}={actual!r}, expected {expected!r}",
                    )


def _validate_material_prose_demos(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    materials = tables.get("malzeme_fatura_satirlari")
    claims = tables.get("fatura_basliklari")
    if materials is None or claims is None or materials.empty or claims.empty:
        return

    for patient_id, scenario_tag in MATERIAL_PROSE_DEMO_PATIENTS.items():
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Missing claim for material prose demo patient {patient_id}")
            continue
        matching = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == scenario_tag]
        if matching.empty:
            _error(
                errors,
                f"Patient {patient_id} missing scenario_tag {scenario_tag!r}",
            )

        expected_code = MATERIAL_PROSE_DEMO_MATERIAL_CODES.get(patient_id)
        patient_materials = materials[_strings(materials["hasta_id"]) == patient_id]
        if patient_materials.empty:
            _error(errors, f"Patient {patient_id} missing material claim lines")
            continue
        if expected_code:
            demo_rows = patient_materials[
                _strings(patient_materials["malzeme_kodu"]) == expected_code
            ]
            if demo_rows.empty:
                _error(
                    errors,
                    f"Patient {patient_id} missing demo material code {expected_code!r}",
                )
                continue
            demo_row = demo_rows.iloc[0]
            flag_expect = MATERIAL_PROSE_DEMO_FLAG_EXPECTATIONS.get(patient_id)
            if flag_expect:
                for column, expected in flag_expect.items():
                    actual = demo_row.get(column)
                    if pd.isna(actual):
                        actual = None
                    if actual != expected:
                        _error(
                            errors,
                            f"Patient {patient_id} demo material {column}={actual!r}, "
                            f"expected {expected!r}",
                        )


def _validate_medula_playbook_demos(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    import sys

    synth_dir = PROJECT_ROOT / "scripts" / "synthetic"
    if str(synth_dir) not in sys.path:
        sys.path.insert(0, str(synth_dir))
    from generators import _MEDULA_DEMO_SPECS  # noqa: E402

    claims = tables.get("fatura_basliklari")
    events = tables.get("medula_red_satirlari")
    if claims is None or events is None or claims.empty:
        return

    for suffix, spec in _MEDULA_DEMO_SPECS.items():
        patient_id = f"SENTETIK-HASTA-{suffix}"
        scenario_tag = str(spec["scenario_tag"])
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Missing claim for MEDULA demo patient {patient_id}")
            continue
        matching = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == scenario_tag]
        if matching.empty:
            _error(
                errors,
                f"Patient {patient_id} missing scenario_tag {scenario_tag!r}",
            )
        patient_events = events[_strings(events["hasta_id"]) == patient_id]
        if patient_events.empty:
            _error(errors, f"Patient {patient_id} missing MEDULA rejection event")
            continue
        event_row = patient_events.iloc[0]
        if str(event_row.get("sonuc_kodu")) != str(spec["sonuc_kodu"]):
            _error(
                errors,
                f"Patient {patient_id} sonuc_kodu={event_row.get('sonuc_kodu')!r}, "
                f"expected {spec['sonuc_kodu']!r}",
            )

        # Anchor coherence: the rejection must point at the offending line on
        # this claim, of the type declared by the spec's anchor. This is the
        # regression guard against the old "blind first-proc pointer" bug.
        anchor = spec.get("anchor") or {"type": "claim"}
        expected_type = {
            "procedure": "procedure",
            "procedure_duplicate": "procedure",
            "procedure_bundled": "procedure",
            "material": "material",
            "drug": "drug",
            "claim": "claim",
        }.get(str(anchor.get("type")), "claim")
        actual_type = str(event_row.get("ilgili_satir_tipi") or "")
        if actual_type != expected_type:
            _error(
                errors,
                f"Patient {patient_id} ilgili_satir_tipi={actual_type!r}, "
                f"expected {expected_type!r} for {spec['sonuc_kodu']}",
            )

        related_id = str(event_row.get("ilgili_satir_id") or "")
        if expected_type != "claim":
            sheet, id_col = {
                "procedure": ("islem_fatura_satirlari", "islem_satiri_id"),
                "material": ("malzeme_fatura_satirlari", "malzeme_satiri_id"),
                "drug": ("ilac_fatura_satirlari", "ilac_satiri_id"),
            }[expected_type]
            line_table = tables.get(sheet)
            if line_table is None or related_id == "":
                _error(
                    errors,
                    f"Patient {patient_id} {spec['sonuc_kodu']} anchor line id missing "
                    f"(related_id={related_id!r})",
                )
            else:
                claim_lines = line_table[_strings(line_table["hasta_id"]) == patient_id]
                if related_id not in set(_strings(claim_lines[id_col])):
                    _error(
                        errors,
                        f"Patient {patient_id} {spec['sonuc_kodu']} ilgili_satir_id "
                        f"{related_id!r} not found among {expected_type} lines on the claim",
                    )

        # Scenario-specific anchor content checks.
        _validate_medula_anchor_content(patient_id, spec, event_row, tables, errors)


def _validate_medula_anchor_content(
    patient_id: str,
    spec: dict,
    event_row: pd.Series,
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    """Assert the offending line's content matches the rejection reason."""
    anchor = spec.get("anchor") or {}
    anchor_type = str(anchor.get("type") or "")
    sonuc = str(spec["sonuc_kodu"])

    if sonuc == "1688":
        # Molecular microbiology: the anchored procedure must be the 912550 panel.
        _assert_procedure_code(patient_id, tables, anchor["code"], errors, sonuc)
    elif sonuc == "0901":
        # Duplicate: the anchored procedure code must appear ≥2 times.
        procs = tables.get("islem_fatura_satirlari")
        if procs is not None:
            claim_procs = procs[_strings(procs["hasta_id"]) == patient_id]
            code = str(anchor["code"])
            n = int((_strings(claim_procs["islem_kodu"]) == code).sum())
            if n < 2:
                _error(
                    errors,
                    f"Patient {patient_id} 0901 duplicate anchor {code} appears {n}x, "
                    f"expected ≥2",
                )
    elif sonuc == "0320":
        # Package-bundled: the component must be flagged pakete_dahil_mi.
        procs = tables.get("islem_fatura_satirlari")
        if procs is not None:
            claim_procs = procs[_strings(procs["hasta_id"]) == patient_id]
            comp = claim_procs[_strings(claim_procs["islem_kodu"]) == str(anchor["component_code"])]
            if comp.empty or not bool(comp.iloc[0].get("pakete_dahil_mi")):
                _error(
                    errors,
                    f"Patient {patient_id} 0320 bundled component {anchor['component_code']} "
                    f"not flagged pakete_dahil_mi",
                )
    elif sonuc == "0704":
        # Material anchor must have uts_kayitli_mi=False.
        mats = tables.get("malzeme_fatura_satirlari")
        if mats is not None:
            claim_mats = mats[_strings(mats["hasta_id"]) == patient_id]
            if claim_mats.empty or bool(claim_mats.iloc[0].get("uts_kayitli_mi", True)):
                _error(
                    errors,
                    f"Patient {patient_id} 0704 material anchor missing or "
                    f"uts_kayitli_mi not False",
                )
    elif sonuc == "0411":
        # Drug anchor must have uzmanlik_kurulu_raporu_var=False.
        drugs = tables.get("ilac_fatura_satirlari")
        if drugs is not None:
            claim_drugs = drugs[_strings(drugs["hasta_id"]) == patient_id]
            report_missing = claim_drugs[
                _strings(claim_drugs["ilac_kodu"]) == str(anchor["ilac_kodu"])
            ]
            if report_missing.empty or bool(report_missing.iloc[0].get("uzmanlik_kurulu_raporu_var", True)):
                _error(
                    errors,
                    f"Patient {patient_id} 0411 drug anchor {anchor['ilac_kodu']} missing or "
                    f"uzmanlik_kurulu_raporu_var not False",
                )


def _assert_procedure_code(
    patient_id: str,
    tables: dict[str, pd.DataFrame],
    code: str,
    errors: list[str],
    sonuc: str,
) -> None:
    procs = tables.get("islem_fatura_satirlari")
    if procs is None:
        return
    claim_procs = procs[_strings(procs["hasta_id"]) == patient_id]
    if str(code) not in set(_strings(claim_procs["islem_kodu"])):
        _error(
            errors,
            f"Patient {patient_id} {sonuc} anchor procedure {code} not found on claim",
        )


CLAIM_READINESS_DEMO_PATIENTS: dict[str, str] = {
    "SENTETIK-HASTA-0033": "sgk_claim_readiness_uts_barcode_missing",
}


def _validate_claim_readiness_demos(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    import sys

    synth_dir = PROJECT_ROOT / "scripts" / "synthetic"
    if str(synth_dir) not in sys.path:
        sys.path.insert(0, str(synth_dir))
    from generators import _CLAIM_READINESS_DEMO_SPECS  # noqa: E402

    claims = tables.get("fatura_basliklari")
    materials = tables.get("malzeme_fatura_satirlari")
    events = tables.get("medula_red_satirlari")
    if claims is None or materials is None or claims.empty:
        return

    for patient_id, scenario_tag in CLAIM_READINESS_DEMO_PATIENTS.items():
        suffix = patient_id.rsplit("-", 1)[-1]
        spec = _CLAIM_READINESS_DEMO_SPECS.get("uts_barcode_missing")
        if suffix != "0033" or spec is None:
            continue
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Missing claim for claim-readiness demo patient {patient_id}")
            continue
        matching = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == scenario_tag]
        if matching.empty:
            _error(
                errors,
                f"Patient {patient_id} missing scenario_tag {scenario_tag!r}",
            )
        patient_materials = materials[_strings(materials["hasta_id"]) == patient_id]
        if patient_materials.empty:
            _error(errors, f"Patient {patient_id} missing material line for readiness demo")
            continue
        material_row = patient_materials.iloc[0]
        for column, expected in (spec.get("prose_flags") or {}).items():
            actual = material_row.get(column)
            if bool(actual) != bool(expected):
                _error(
                    errors,
                    f"Patient {patient_id} readiness material {column}={actual!r}, "
                    f"expected {expected!r}",
                )
        if events is not None and not events.empty:
            patient_events = events[_strings(events["hasta_id"]) == patient_id]
            if not patient_events.empty:
                _error(
                    errors,
                    f"Patient {patient_id} should not have MEDULA rejection events "
                    "(proactive readiness period demo)",
                )


def _validate_expected_outputs(
    tables: dict[str, pd.DataFrame],
    procedures: pd.DataFrame,
    errors: list[str],
) -> None:
    expected = tables["beklenen_kural_ciktilari"]
    required_columns = {"satir_id", "satir_tipi"}
    missing = sorted(required_columns - set(expected.columns))
    if missing:
        _error(errors, f"beklenen_kural_ciktilari missing columns: {missing}")
        return

    claim_ids = set(_strings(tables["fatura_basliklari"]["fatura_id"]))
    line_types = _strings(expected["satir_tipi"])
    line_ids = _strings(expected["satir_id"])
    claim_level = expected[(line_types == "fatura") & (line_ids == "")]
    missing_claims = sorted(claim_ids - set(_strings(claim_level["fatura_id"])))
    if missing_claims:
        _error(errors, f"Missing claim-level expected output rows: {missing_claims}")

    line_level = expected[line_ids != ""]
    if line_level.empty:
        _error(errors, "Expected outputs contain no line-level assertions")

    bundled_procedure_ids = set(
        _strings(procedures.loc[_truthy(procedures["pakete_dahil_mi"]), "islem_satiri_id"])
    )
    materials = tables["malzeme_fatura_satirlari"]
    material_rule_mask = _truthy(materials["pakete_dahil_mi"]) | _truthy(materials["on_onay_gerekli_mi"])
    material_ids = set(_strings(materials.loc[material_rule_mask, "malzeme_satiri_id"]))
    drug_ids = set(_strings(tables["ilac_fatura_satirlari"]["ilac_satiri_id"]))
    required_line_ids = bundled_procedure_ids | material_ids | drug_ids
    missing_line_outputs = sorted(required_line_ids - set(line_ids[line_ids != ""]))
    if missing_line_outputs:
        _error(errors, f"Missing line-level expected outputs: {missing_line_outputs}")


def _validate_vignette_manifest_alignment(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    """P2: vignette registry and manifest scenario tags stay in sync."""
    registry = vignette_registry()
    manifest = load_demo_manifest()
    scenario_by_index = manifest.get("scenario_by_index") or {}
    for index, expected_tag in scenario_by_index.items():
        vignette = registry.get(str(index))
        if vignette is None:
            _error(errors, f"Manifest index {index} has no vignette row")
            continue
        if vignette.scenario_tag != expected_tag:
            _error(
                errors,
                f"Vignette {index} scenario_tag={vignette.scenario_tag!r} "
                f"!= manifest {expected_tag!r}",
            )

    claims = tables["fatura_basliklari"]
    for index, expected_tag in scenario_by_index.items():
        patient_id = f"SENTETIK-HASTA-{index}"
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            continue
        tagged = patient_claims[_strings(patient_claims["senaryo_etiketi"]) == expected_tag]
        if tagged.empty:
            _error(
                errors,
                f"Patient {patient_id} missing generated claim for scenario {expected_tag!r}",
            )


def _validate_tier_a_credibility(
    tables: dict[str, pd.DataFrame],
    errors: list[str],
) -> None:
    """Tier A showcase: no ghost package lines; header totals match line sums."""
    manifest = load_demo_manifest()
    tier_a = tier_a_patient_ids()
    if not tier_a:
        return

    procedures = tables["islem_fatura_satirlari"]
    claims = tables["fatura_basliklari"]
    materials = tables["malzeme_fatura_satirlari"]
    drugs = tables["ilac_fatura_satirlari"]

    for patient_id in sorted(tier_a):
        patient_claims = claims[_strings(claims["hasta_id"]) == patient_id]
        if patient_claims.empty:
            _error(errors, f"Tier A patient missing claims: {patient_id}")
            continue

        scenario_by_index = manifest.get("scenario_by_index") or {}
        patient_index = patient_id.rsplit("-", 1)[-1]
        showcase_tag = scenario_by_index.get(patient_index)
        if showcase_tag:
            tagged = patient_claims[
                _strings(patient_claims["senaryo_etiketi"]) == showcase_tag
            ]
            if tagged.empty:
                _error(
                    errors,
                    f"Tier A patient {patient_id} missing showcase scenario {showcase_tag!r}",
                )

        for _, claim in patient_claims.iterrows():
            claim_id = str(claim["fatura_id"])
            claim_tag = str(claim.get("senaryo_etiketi") or "")
            is_showcase_claim = showcase_tag and claim_tag == showcase_tag
            claim_procs = procedures[_strings(procedures["fatura_id"]) == claim_id]
            billed = float(claim.get("beklenen_toplam_fatura_tutari_try") or 0)
            payable = float(claim.get("beklenen_toplam_odenebilir_tutar_try") or 0)

            line_billed = sum(float(row.get("fatura_tutari_try") or 0) for _, row in claim_procs.iterrows())
            line_billed += sum(
                float(row.get("fatura_tutari_try") or 0)
                for _, row in materials[_strings(materials["fatura_id"]) == claim_id].iterrows()
            )
            line_billed += sum(
                float(row.get("fatura_tutari_try") or 0)
                for _, row in drugs[_strings(drugs["fatura_id"]) == claim_id].iterrows()
            )
            line_payable = sum(
                float(row.get("beklenen_odenebilir_tutar_try") or 0) for _, row in claim_procs.iterrows()
            )
            line_payable += sum(
                float(row.get("beklenen_odenebilir_tutar_try") or 0)
                for _, row in materials[_strings(materials["fatura_id"]) == claim_id].iterrows()
            )
            line_payable += sum(
                float(row.get("beklenen_odenebilir_tutar_try") or 0)
                for _, row in drugs[_strings(drugs["fatura_id"]) == claim_id].iterrows()
            )
            if abs(billed - line_billed) > 0.02:
                _error(
                    errors,
                    f"Tier A claim {claim_id} header billed {billed} != line sum {line_billed}",
                )
            if abs(payable - line_payable) > 0.02:
                _error(
                    errors,
                    f"Tier A claim {claim_id} header payable {payable} != line sum {line_payable}",
                )

            if not is_showcase_claim:
                continue

            optional_override = claim_tag.startswith("sgk_optional_override_")
            if not optional_override:
                continue

            ghost = claim_procs[
                (_strings(claim_procs["islem_kategorisi"]) == "paket")
                & (claim_procs["fatura_tutari_try"].fillna(0).astype(float) <= 0)
                & (claim_procs["beklenen_odenebilir_tutar_try"].fillna(0).astype(float) > 0)
            ]
            if not ghost.empty:
                _error(
                    errors,
                    f"Tier A claim {claim_id} has ghost package line(s): "
                    f"{ghost['islem_kodu'].astype(str).tolist()}",
                )

            billed_paket = claim_procs[
                (_strings(claim_procs["islem_kategorisi"]) == "paket")
                & (claim_procs["fatura_tutari_try"].fillna(0).astype(float) > 0)
            ]
            billed_itemized = claim_procs[
                (_strings(claim_procs["islem_kategorisi"]) != "paket")
                & (claim_procs["fatura_tutari_try"].fillna(0).astype(float) > 0)
                & (~_truthy(claim_procs["pakete_dahil_mi"]))
            ]
            if not billed_paket.empty and not billed_itemized.empty:
                paket_payable = float(
                    billed_paket["beklenen_odenebilir_tutar_try"].fillna(0).astype(float).sum()
                )
                item_payable = float(
                    billed_itemized["beklenen_odenebilir_tutar_try"].fillna(0).astype(float).sum()
                )
                if paket_payable > 0 and item_payable > 0:
                    _error(
                        errors,
                        f"Tier A claim {claim_id} double billing path: package and itemized payables",
                    )


def _validate_parquet_dir(
    directory: Path,
    required: dict[str, set[str]],
    errors: list[str],
) -> None:
    for filename, columns in required.items():
        path = directory / filename
        if not path.exists():
            _error(errors, f"Parquet missing: {path}")
            continue
        df = pd.read_parquet(path)
        missing = sorted(columns - set(df.columns))
        if missing:
            _error(errors, f"{path} missing columns: {missing}")
        if df.empty:
            _error(errors, f"{path} is empty")


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    errors: list[str] = []

    print("=" * 72)
    print(f"Validating synthetic SUT data: {data_dir}")
    tables = _read_excel(data_dir, errors)
    if not tables:
        _error(errors, f"Workbook validation skipped because {WORKBOOK_NAME} is missing or invalid")
    else:
        _validate_workbook(tables, errors)
        _validate_material_prose_flags(tables, errors)
        _validate_specialty_prose_flags(tables, errors)
        _validate_drug_indication_demos(tables, errors)
        _validate_material_prose_demos(tables, errors)
        _validate_medula_playbook_demos(tables, errors)
        _validate_claim_readiness_demos(tables, errors)
        _validate_payment_method_compliance_demos(tables, errors)
        _validate_packaged_claim_mandatory_side_procedures(tables, errors)
        _validate_vignette_manifest_alignment(tables, errors)
        _validate_tier_a_credibility(tables, errors)
    _validate_parquet_dir(data_dir / "clean", REQUIRED_CLEAN_COLUMNS, errors)
    _validate_parquet_dir(data_dir / "claims", REQUIRED_CLAIM_COLUMNS, errors)

    print("=" * 72)
    if errors:
        print(f"Validation failed with {len(errors)} error(s)")
        raise SystemExit(1)
    print("Validation passed")


if __name__ == "__main__":
    main()
