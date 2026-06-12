#!/usr/bin/env python3
"""Validate the v1 SUT synthetic billing dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
WORKBOOK_NAME = "sentetik_sut_v2_50_hasta.xlsx"
MIN_PATIENTS = 50
MIN_CLAIMS = 100
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

REQUIRED_CLAIM_COLUMNS = {
    "claim_headers.parquet": {
        "claim_id",
        "patient_id",
        "episode_id",
        "claim_type",
        "admission_date",
        "expected_total_billed_try",
    },
    "procedure_claim_lines.parquet": {
        "procedure_line_id",
        "claim_id",
        "patient_id",
        "episode_id",
        "procedure_date",
        "procedure_code",
        "billed_amount_try",
    },
    "material_claim_lines.parquet": {
        "material_line_id",
        "claim_id",
        "patient_id",
        "material_code",
        "billed_amount_try",
        "titubb_registered",
        "uts_registered",
        "procurement_record_incomplete",
        "procedure_not_reimbursed",
        "foreign_facility",
        "facility_procedure_restriction_violation",
        "diagnosis_bundled_no_separate_bill",
        "procurement_price_refs_insufficient",
        "medula_code_undefined_on_date",
        "barcode_sut_mismatch",
        "diagnosis_bundled_material_scope",
        "cross_branch_material_unauthorized",
        "ortez_protez_contract_billing_invalid",
        "maintenance_cost_exceeds_sut_cap",
        "protez_repair_documentation_incomplete",
        "warranty_maintenance_procedure_incomplete",
        "ortez_protez_maintenance_unverified",
        "ihale_dts_mandatory_fields_incomplete",
        "supplier_contract_pricing_path",
        "ek3c_inpatient_external_supply_invalid",
        "ek3c_list_price_missing",
        "ek3_quality_documentation_incomplete",
        "ek3c_miat_early_renewal_unauthorized",
        "ek3c_custom_order_billing_invalid",
        "ek3c_medical_appropriateness_incomplete",
        "ek3c_custom_garment_contract_invalid",
        "ek3c_force_majeure_renewal_claim",
        "ek3c_outpatient_material_scope",
        "inpatient_material_facility_supply_violation",
        "non_reimbursed_inpatient_patient_charge",
        "lab_material_separate_billing",
        "shared_consumable_wrong_branch_billing",
        "material_prescription_quantity_exceeded",
        "material_report_prescription_invalid",
        "material_invoice_documentation_incomplete",
        "diagnosis_package_material_unbundled",
        "emergency_uncontracted_facility_material",
        "unlisted_material_surcharge_billing",
        "wheelchair_dual_prescription_invalid",
        "outpatient_contract_center_supply_required",
        "child_growth_miat_renewal_claim",
        "facility_contract_material_supply_scope",
        "ismarlama_device_component_titubb_incomplete",
        "titubb_uts_barcode_documentation_missing",
        "skin_substitute_non_burn_use",
        "bone_stimulator_combined_use",
        "cochlear_implant_under_12_months",
        "optical_lens_upgrade_difference_claim",
    },
    "drug_claim_lines.parquet": {
        "drug_claim_line_id",
        "prescription_id",
        "claim_id",
        "patient_id",
        "drug_claim_date",
        "billed_amount_try",
    },
    "expected_rule_outputs.parquet": {
        "expected_output_id",
        "scenario_tag",
        "patient_id",
        "claim_id",
        "line_id",
        "line_type",
        "rule_family",
        "expected_status",
    },
    "claim_diagnoses.parquet": {
        "diagnosis_id",
        "claim_id",
        "patient_id",
        "episode_id",
        "icd10_code",
        "is_primary",
        "diagnosis_role",
        "diagnosis_date",
        "exemption_eligible",
    },
}


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
    xls = pd.ExcelFile(workbook)
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
    _validate_parquet_dir(data_dir / "clean", REQUIRED_CLEAN_COLUMNS, errors)
    _validate_parquet_dir(data_dir / "claims", REQUIRED_CLAIM_COLUMNS, errors)

    print("=" * 72)
    if errors:
        print(f"Validation failed with {len(errors)} error(s)")
        raise SystemExit(1)
    print("Validation passed")


if __name__ == "__main__":
    main()
