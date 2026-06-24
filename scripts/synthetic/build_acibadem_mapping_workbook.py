#!/usr/bin/env python3
"""Build an Acibadem-ready input-only subset of the synthetic SUT workbook.

The current synthetic workbook (`sentetik_sut_v2_50_hasta.xlsx`) carries many
columns that are NOT real hospital billing inputs:

  * ``beklenen_*`` / ``expected_*`` — BILUN's own computed answers (expected
    payable, expected denial reason, expected rule trace). A real billing export
    will never contain these; BILUN produces them.
  * ~78 material prose-rule boolean flags (``bone_stimulator_with_autograft``,
    ``cochlear_implant_under_12_months``, ...) — rule-trigger booleans that
    BILUN derives from material_name / procedure_code / diagnosis / age. A real
    export has no such columns.
  * ``senaryo_etiketi`` — a synthetic-demo vignette label (used only for demo
    lookup + API metadata, never a billing decision driver).
  * Non-billing clinical sheets (demographics/vitals, lab, prescriptions,
    manifest) — out of scope for a billing-system column mapping.

This script reads the source workbook, keeps ONLY the algorithm-consumed INPUT
columns per sheet (the set is derived from
``src/bilun/domain/claims/models.py``), preserves every data row, and writes a
new workbook plus two documentation sheets:

  * ``kolon_eslestirme`` — the column mapping template
        Turkish xlsx col | English parquet col | description | Acibadem field
  * ``kaldirilan_kolonlar`` — transparency log of every dropped column

The authoritative consumed-column set is the set of dataclass fields in
``models.py`` (ClaimHeader, ClaimDiagnosis, ProcedureClaimLine,
MaterialClaimLine, DrugClaimLine, PatientCopayProfile, MedulaRejectionEvent,
PerformedProcedureLine). The English names come from the rename maps in
``scripts/synthetic/exporters.py``.

This is a NEW artifact; the source workbook and the consumed parquets are left
untouched. Algorithms keep consuming ``data/synthetic/sut/claims/*.parquet``
unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

# --- Repository root -------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bilun.domain.claims.models import (  # noqa: E402  (path insert above)
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PatientCopayProfile,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.parsing.row_parsers import (  # noqa: E402
    _MATERIAL_EXPLICIT_FIELDS,
)

SOURCE_WORKBOOK = REPO_ROOT / "data/synthetic/sut/sentetik_sut_v2_50_hasta.xlsx"
OUTPUT_WORKBOOK = (
    REPO_ROOT / "data/synthetic/sut/sentetik_sut_v2_acibadem_input_50_hasta.xlsx"
)

# ---------------------------------------------------------------------------
# Per-sheet column policy
#
# KEPT_COLUMNS  : the columns that survive (order = as listed here).
# The kept set is exactly the algorithm-consumed INPUT fields for each sheet,
# i.e. every dataclass field that is NOT a BILUN-computed output or a derived
# prose-rule flag. Each kept Turkish column is paired with its English parquet
# name (from scripts/synthetic/exporters.py) and a short description.
#
# Borderline fields that BILUN can derive but that have a plausible real source
# are kept and explicitly flagged as 'borderline' in the mapping sheet.
# ---------------------------------------------------------------------------

# (turkish_xlsx_col, english_parquet_col, description, borderline?)
_SheetSpec = tuple  # readability

# fatura_basliklari -> claim_headers
FATURA_BASLIKLARI: list[tuple[str, str, str, bool]] = [
    ("fatura_id", "claim_id", "Fatura (ilaç/işlem/malzeme satırlarını bağlayan anahtar)", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka (episode) tanımlayıcı", False),
    ("fatura_tipi", "claim_type", "Fatura tipi (ayakta/yatarak vb.)", False),
    ("mesleki_kontekst", "occupational_context", "Mesleki kontekst (sgk uplif kuralı için)", False),
    ("kurum_basamagi", "facility_tier", "Kurum basamağı (devlet/özel/üniversite)", False),
    ("saglayici_tipi", "provider_type", "Sağlayıcı tipi", False),
    ("servis_adi", "department", "Servis adı", False),
    ("yatis_tarihi", "admission_date", "Yatış tarihi", False),
    ("taburcu_tarihi", "discharge_date", "Taburcu tarihi", False),
    ("fatura_baslangic_tarihi", "claim_start_date", "Fatura başlangıç tarihi", False),
    ("fatura_bitis_tarihi", "claim_end_date", "Fatura bitiş tarihi", False),
    ("birincil_icd10", "primary_icd10", "Birincil ICD-10 tanı kodu", False),
    ("paket_adayi_mi", "package_candidate", "Paket adayı mı (paketleme karar girdisi)", False),
]

# tani_satirlari -> claim_diagnoses
TANI_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("tani_satiri_id", "diagnosis_id", "Tanı satır tanımlayıcı", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka tanımlayıcı", False),
    ("icd10_kodu", "icd10_code", "ICD-10 tanı kodu (EK-1A muafiyet eşleştirme)", False),
    ("tani_rolu", "diagnosis_role", "Tanı rolü (birincil vs — is_primary üretir)", False),
    ("tani_tarihi", "diagnosis_date", "Tanı tarihi", False),
    ("ek1a_muafiyet_iliskili_mi", "exemption_eligible", "EK-1A muafiyet ilişkili mi", False),
]

# islem_fatura_satirlari -> procedure_claim_lines
ISLEM_FATURA_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("islem_satiri_id", "procedure_line_id", "İşlem satır tanımlayıcı", False),
    ("fatura_id", "claim_id", "Bağlı fatura", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka tanımlayıcı", False),
    ("islem_tarihi", "procedure_date", "İşlem tarihi", False),
    ("islem_kodu", "procedure_code", "SUT işlem kodu (fiyatlandırma + paketleme anahtarı)", False),
    ("islem_adi", "procedure_name", "İşlem adı", False),
    ("islem_kategorisi", "procedure_category", "İşlem kategorisi (laboratuvar yakalama kuralı)", False),
    ("adet", "quantity", "Adet", False),
    ("birim_fiyat_try", "unit_price_try", "Birim fiyat (TRY)", False),
    ("fatura_tutari_try", "billed_amount_try", "Faturalanan tutar (TRY)", False),
    ("pakete_dahil_mi", "is_package_included", "Pakete dahil mi", False),
    ("paket_kodu", "package_code", "Paket kodu", False),
    ("ilave_ucret_uygulanabilir_mi", "surcharge_applicable", "İlave ücret uygulanabilir mi", False),
    ("ilave_ucret_orani", "surcharge_rate", "İlave ücret oranı", False),
    ("katilim_payi_orani_uygulanabilir_mi", "copay_rate_applicable", "Katılım payı oranı uygulanabilir mi", False),
    ("katilim_payi_orani", "copay_rate", "Katılım payı oranı", False),
]

# malzeme_fatura_satirlari -> material_claim_lines
# Structural/financial fields only. The ~78 prose-rule booleans are dropped
# (BILUN derives them from material_name/procedure_code/diagnosis/age).
MALZEME_FATURA_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("malzeme_satiri_id", "material_line_id", "Malzeme satır tanımlayıcı", False),
    ("fatura_id", "claim_id", "Bağlı fatura", False),
    ("islem_satiri_id", "procedure_line_id", "Bağlı işlem satırı (procedure pairing)", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("malzeme_tarihi", "material_date", "Malzeme tarihi", False),
    ("malzeme_kodu", "material_code", "EK-3 / EK-3Ç malzeme kodu (fiyatlandırma anahtarı)", False),
    ("malzeme_adi", "material_name", "Malzeme adı (paketleme/özel kurallar için)", False),
    ("malzeme_tipi", "material_type", "Malzeme tipi", False),
    ("uzmanlik_kategorisi", "specialty_category", "Uzmanlık kategorisi", False),
    ("adet", "quantity", "Adet", False),
    ("birim_fiyat_try", "unit_price_try", "Birim fiyat (TRY)", False),
    ("fatura_tutari_try", "billed_amount_try", "Faturalanan tutar (TRY)", False),
    ("pakete_dahil_mi", "is_bundled", "Pakete dahil mi", False),
    ("on_onay_gerekli_mi", "requires_pre_auth", "Ön onay gerekli mi", False),
    # titubb/uts: borderline — BILUN could derive via registry lookup, but a
    # real procurement system tracks them. Kept; flagged in the mapping sheet.
    ("titubb_kayitli_mi", "titubb_registered", "TİTUBB kayıtlı mı", True),
    ("uts_kayitli_mi", "uts_registered", "UTS kayıtlı mı", True),
]

# ilac_fatura_satirlari -> drug_claim_lines
ILAC_FATURA_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("ilac_satiri_id", "drug_claim_line_id", "İlaç satır tanımlayıcı", False),
    ("recete_id", "prescription_id", "Reçete tanımlayıcı", False),
    ("fatura_id", "claim_id", "Bağlı fatura", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka tanımlayıcı", False),
    ("ilac_fatura_tarihi", "drug_claim_date", "İlaç fatura tarihi", False),
    ("ilac_adi", "drug_name", "İlaç adı (endikasyon kuralı)", False),
    ("ilac_kodu", "drug_code", "İlaç kodu (BILUN eylem eşleştirme)", False),
    ("barkod", "barkod", "Barkod", False),
    ("esdeger_grup", "equivalence_group", "Eşdeğer grup", False),
    ("adet", "quantity", "Adet", False),
    ("birim_fiyat_try", "unit_price_try", "Birim fiyat (TRY)", False),
    ("fatura_tutari_try", "billed_amount_try", "Faturalanan tutar (TRY)", False),
    ("katilim_payi_orani", "copay_rate", "Katılım payı oranı", False),
    ("ilave_ucret_orani", "surcharge_rate", "İlave ücret oranı", False),
    ("uzmanlik_kurulu_raporu_var", "drug_specialty_board_report_present", "Uzmanlık kurulu raporu var mı (endikasyon kuralı)", False),
    ("rapor_suresi_ay", "drug_report_duration_months", "Rapor süresi (ay) (endikasyon kuralı)", False),
    ("yatarak_tedavi_ilac", "drug_inpatient_supply", "Yatarak tedavi ilacı mı", False),
    ("recete_eden_uzmanlik", "prescriber_specialty", "Reçete eden uzmanlık", False),
]

# hasta_katilim_payi_profilleri -> patient_copay_profiles
HASTA_KATILIM_PAYI_PROFILLERI: list[tuple[str, str, str, bool]] = [
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("sgk_yararlanma_sinifi", "sgk_benefit_class", "SGK yararlanma sınıfı (muafiyet kuralı)", False),
    ("gazi_sehit_durumu", "veteran_martyr_status", "Gazi/şehit yakını durumu (muafiyet kuralı)", False),
    ("vatani_hizmet_durumu", "national_service_status", "Vatanı hizmet durumu (muafiyet kuralı)", False),
    ("yasli_aylik_2022", "elderly_allowance_2022", "Yaşlı aylığı 2022 (muafiyet kuralı)", False),
    ("dogum_yili", "birth_year", "Doğum yılı (muafiyet yaş kontrolü)", False),
]

# medula_red_satirlari -> medula_rejection_events
MEDULA_RED_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("medula_red_satir_id", "rejection_event_id", "MEDULA red satır tanımlayıcı", False),
    ("fatura_id", "claim_id", "Bağlı fatura", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka tanımlayıcı", False),
    ("medula_asamasi", "medula_stage", "MEDULA aşaması (rebill playbook girdisi)", False),
    ("sonuc_kodu", "sonuc_kodu", "Sonuç kodu (rebill playbook girdisi)", False),
    ("hata_kodu", "hata_kodu", "Hata kodu", False),
    ("hata_mesaji", "hata_mesaji", "Hata mesajı", False),
    ("red_zamani", "rejection_timestamp", "Red zamanı", False),
    ("ilgili_islem_kodu", "related_procedure_code", "İlgili işlem kodu", False),
    ("ilgili_islem_satiri_id", "related_procedure_line_id", "İlgili işlem satırı", False),
]

# gerceklestirilen_islem_satirlari -> performed_procedure_lines
GERCEKLESTIRILEN_ISLEM_SATIRLARI: list[tuple[str, str, str, bool]] = [
    ("gerceklestirilen_satir_id", "performed_line_id", "Gerçekleştirilen satır tanımlayıcı", False),
    ("fatura_id", "claim_id", "Bağlı fatura", False),
    ("hasta_id", "patient_id", "Hasta tanımlayıcı", False),
    ("basvuru_id", "episode_id", "Başvuru / vaka tanımlayıcı", False),
    ("hizmet_tarihi", "service_date", "Hizmet tarihi", False),
    ("islem_kodu", "procedure_code", "İşlem kodu (yakalama boşluğu kuralı)", False),
    ("islem_adi", "procedure_name", "İşlem adı", False),
    ("kaynak", "source", "Kaynak (emr vb.)", False),
]

# The source sheet `gerceklestirilen_islem_satirlari` is 32 chars, which
# Excel truncates/拒绝 at 31. We write it under a safe name and record both.
SHEET_NAME_OVERRIDES: dict[str, str] = {
    "gerceklestirilen_islem_satirlari": "gerceklestirilen_islem_satirlar",  # 31 chars
}


def _out_sheet_name(source_name: str) -> str:
    name = SHEET_NAME_OVERRIDES.get(source_name, source_name)
    assert len(name) <= 31, f"sheet name >31 chars: {name}"
    return name


SHEET_SPECS: list[tuple[str, list[tuple[str, str, str, bool]], type]] = [
    ("fatura_basliklari", FATURA_BASLIKLARI, ClaimHeader),
    ("tani_satirlari", TANI_SATIRLARI, ClaimDiagnosis),
    ("islem_fatura_satirlari", ISLEM_FATURA_SATIRLARI, ProcedureClaimLine),
    ("malzeme_fatura_satirlari", MALZEME_FATURA_SATIRLARI, MaterialClaimLine),
    ("ilac_fatura_satirlari", ILAC_FATURA_SATIRLARI, DrugClaimLine),
    ("hasta_katilim_payi_profilleri", HASTA_KATILIM_PAYI_PROFILLERI, PatientCopayProfile),
    ("medula_red_satirlari", MEDULA_RED_SATIRLARI, MedulaRejectionEvent),
    ("gerceklestirilen_islem_satirlari", GERCEKLESTIRILEN_ISLEM_SATIRLARI, PerformedProcedureLine),
]

DROPPED_SHEETS = [
    "veri_seti_manifestosu",
    "hastalar",
    "basvurular",
    "receteler",
    "laboratuvar_sonuclari",
    "beklenen_kural_ciktilari",
    "katalog_alt_kumesi",
]

# Categories of dropped columns, for the transparency sheet.
DROP_REASON = {
    "BILUN çıktısı": (
        "BILUN'un hesapladığı beklenen değer (ödenir/red/kural izi) — gerçek "
        "fatura ihracında yok; BILUN üretir."
    ),
    "Paket kural bayrağı (üretilmiş)": (
        "Malzeme SUT kural-tetikleyici boolean — BILUN malzeme_adı/işlem_kodu/"
        "tani/yaş'dan üretir; gerçek ihracatta yok."
    ),
    "Demo iskeleti": (
        "Sentetik-demo etiketi/scaffolding — algoritmik karar sürücüsü değil."
    ),
    "Algoritma tarafından okunmuyor": (
        "xlsx'te var ama parquet parse/yol haritasında tüketilmiyor."
    ),
}

# beklenen_* columns that are explicitly consumed by algorithms but are, by
# nature, BILUN outputs -> dropped per user decision, with that reason.
BILUN_OUTPUT_ENGLISH = {
    "expected_payable_try",
    "expected_total_billed_try",
    "expected_total_payable_try",
    "expected_denial_reason",
    "denial_reason_expected",
    "rule_trace_expected",
    "discount_tier_expected",
}


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def _validate_against_models() -> None:
    """Assert every kept column maps to a real dataclass field (no typos)."""
    import dataclasses

    expected_per_model: dict[type, set[str]] = {
        ClaimHeader: {"claim_id", "patient_id", "episode_id", "claim_type",
                      "occupational_context", "facility_tier", "provider_type",
                      "department", "admission_date", "discharge_date",
                      "claim_start_date", "claim_end_date", "primary_icd10",
                      "package_candidate"},
        ClaimDiagnosis: {"diagnosis_id", "patient_id", "episode_id",
                         "icd10_code", "diagnosis_role", "diagnosis_date",
                         "exemption_eligible"},
        ProcedureClaimLine: {"procedure_line_id", "claim_id", "patient_id",
                             "episode_id", "procedure_date", "procedure_code",
                             "procedure_name", "procedure_category", "quantity",
                             "unit_price_try", "billed_amount_try",
                             "is_package_included", "package_code",
                             "surcharge_applicable", "surcharge_rate",
                             "copay_rate_applicable", "copay_rate"},
        MaterialClaimLine: {"material_line_id", "claim_id", "procedure_line_id",
                            "patient_id", "material_date", "material_code",
                            "material_name", "material_type",
                            "specialty_category", "quantity", "unit_price_try",
                            "billed_amount_try", "is_bundled",
                            "requires_pre_auth", "titubb_registered",
                            "uts_registered"},
        DrugClaimLine: {"drug_claim_line_id", "prescription_id", "claim_id",
                        "patient_id", "episode_id", "drug_claim_date",
                        "drug_name", "drug_code", "barkod",
                        "equivalence_group", "quantity", "unit_price_try",
                        "billed_amount_try", "copay_rate", "surcharge_rate",
                        "drug_specialty_board_report_present",
                        "drug_report_duration_months", "drug_inpatient_supply",
                        "prescriber_specialty"},
        PatientCopayProfile: {"patient_id", "sgk_benefit_class",
                              "veteran_martyr_status",
                              "national_service_status",
                              "elderly_allowance_2022", "birth_year"},
        MedulaRejectionEvent: {"rejection_event_id", "claim_id", "patient_id",
                               "episode_id", "medula_stage", "sonuc_kodu",
                               "hata_kodu", "hata_mesaji",
                               "rejection_timestamp",
                               "related_procedure_code",
                               "related_procedure_line_id"},
        PerformedProcedureLine: {"performed_line_id", "claim_id", "patient_id",
                                 "episode_id", "service_date",
                                 "procedure_code", "procedure_name", "source"},
    }
    for _sheet, rows, model in SHEET_SPECS:
        kept = {english for (_tr, english, _desc, _b) in rows}
        missing = kept - {f.name for f in dataclasses.fields(model)}
        if model in expected_per_model and kept != expected_per_model[model]:
            extra = kept - expected_per_model[model]
            raise AssertionError(
                f"{_sheet}: kept english cols do not match {model.__name__} "
                f"fields. extra={extra} missing={missing}"
            )


def _classify_dropped(turkish_col: str, english_col: str, sheet: str) -> tuple[str, str]:
    """Return (reason_key, english_col) for a dropped column."""
    if english_col in BILUN_OUTPUT_ENGLISH or turkish_col.startswith("beklenen_"):
        return "BILUN çıktısı", english_col
    if turkish_col in {"senaryo_etiketi"}:
        return "Demo iskeleti", english_col
    if sheet == "medula_red_satirlari" and turkish_col in {
        "ilgili_satir_tipi", "ilgili_satir_id"
    }:
        return "Algoritma tarafından okunmuyor", english_col
    if sheet == "malzeme_fatura_satirlari":
        # Everything dropped from the material sheet beyond the kept set is a
        # derived prose-rule flag (or a BILUN output already caught above).
        if english_col == "":
            # Turkish-named flag never renamed in exporters.py? Check the
            # explicit set; if not structural, it's a flag.
            if turkish_col in {"ihale_ekrani_eksik_mi"}:
                return "Paket kural bayrağı (üretilmiş)", "procurement_record_incomplete"
            # Most remaining material flags are already english-named or have
            # a 1:1/passthrough english name; record english == turkish.
            return "Paket kural bayrağı (üretilmiş)", turkish_col
        return "Paket kural bayrağı (üretilmiş)", english_col
    return "Algoritma tarafından okunmuyor", english_col


# English-name lookup for a Turkish col on a given sheet (from SHEET_SPECS).
def _english_for(sheet: str, turkish: str) -> str:
    for name, rows, _m in SHEET_SPECS:
        if name == sheet:
            for (tr, en, _d, _b) in rows:
                if tr == turkish:
                    return en
    return ""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
_BORDERLINE_FILL = PatternFill("solid", fgColor="FFF4CE")
_WRAP = Alignment(wrap_text=True, vertical="top")


def _style_header(ws, ncols: int) -> None:
    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _WRAP
    ws.freeze_panes = "A2"
    # reasonable widths
    for i, cell in enumerate(ws[1], start=1):
        letter = cell.column_letter
        ws.column_dimensions[letter].width = max(18, min(46, len(str(cell.value or "")) + 2))


def build() -> None:
    _validate_against_models()

    if not SOURCE_WORKBOOK.exists():
        raise FileNotFoundError(f"Source workbook not found: {SOURCE_WORKBOOK}")

    src = openpyxl.load_workbook(SOURCE_WORKBOOK, read_only=True, data_only=True)
    out = openpyxl.Workbook()
    out.remove(out.active)

    removed_rows: list[list[str]] = []
    sheet_row_counts: dict[str, int] = {}

    for sheet, rows, _model in SHEET_SPECS:
        if sheet not in src.sheetnames:
            raise KeyError(f"Source workbook missing sheet {sheet!r}")
        src_ws = src[sheet]
        src_header = [c.value for c in next(src_ws.iter_rows(min_row=1, max_row=1))]
        kept_tr = [tr for (tr, _e, _d, _b) in rows]
        # integrity: every kept col must exist in the source
        missing = [c for c in kept_tr if c not in src_header]
        if missing:
            raise KeyError(f"{sheet}: source is missing kept columns {missing}")

        out_sheet = _out_sheet_name(sheet)
        out_ws = out.create_sheet(out_sheet)
        out_ws.append([tr for tr in kept_tr])  # header
        keep_idx = [src_header.index(c) for c in kept_tr]

        # Count source non-empty data rows to assert full preservation below.
        written = 0
        for row in src_ws.iter_rows(min_row=2, values_only=True):
            if not any(v is not None and str(v) != "" for v in row):
                continue
            out_ws.append([row[i] for i in keep_idx])
            written += 1
        _style_header(out_ws, len(kept_tr))

        # Row-preservation guard: every non-empty source data row must survive.
        src_nonempty = sum(
            1 for row in src_ws.iter_rows(min_row=2, values_only=True)
            if any(v is not None and str(v) != "" for v in row)
        )
        assert written == src_nonempty, (
            f"{sheet}: row preservation failed ({written} vs {src_nonempty})"
        )
        sheet_row_counts[sheet] = written

        # record removed columns for this sheet
        for col in src_header:
            if col in kept_tr:
                continue
            reason_key, en = _classify_dropped(col, _english_for(sheet, col), sheet)
            removed_rows.append([
                sheet, col, en, DROP_REASON[reason_key], reason_key
            ])

    # record removed whole sheets
    for sheet in DROPPED_SHEETS:
        if sheet not in src.sheetnames:
            continue
        src_ws = src[sheet]
        try:
            header = [c.value for c in next(src_ws.iter_rows(min_row=1, max_row=1))]
        except StopIteration:
            header = []
        kind = "Demo iskeleti" if sheet in {
            "veri_seti_manifestosu", "hastalar", "basvurular", "katalog_alt_kumesi"
        } else "BILUN çıktısı" if sheet == "beklenen_kural_ciktilari" else "Demo iskeleti"
        if not header:
            removed_rows.append([sheet, "(tüm sayfa)", "", DROP_REASON[kind], kind])
        else:
            for col in header:
                removed_rows.append([sheet, col, "", DROP_REASON[kind], kind])

    # --- mapping sheet -----------------------------------------------------
    map_ws = out.create_sheet("kolon_eslestirme", 0)  # first tab
    map_ws.append([
        "Sayfa (xlsx)", "Türkçe kolon", "İngilizce parquet kolonu",
        "Açıklama", "Sınırda mı (BILUN üretebilir)", "Acibadem alanı (doldurun)",
    ])
    for sheet, rows, _model in SHEET_SPECS:
        for (tr, en, desc, borderline) in rows:
            map_ws.append([
                sheet, tr, en, desc,
                "EVET — BILUN kayıt aramasıyla üretebilir" if borderline else "—",
                "",
            ])
    _style_header(map_ws, 6)
    map_ws.column_dimensions["F"].width = 34
    # tint borderline rows
    header_ncols = 6
    for r in map_ws.iter_rows(min_row=2, max_row=map_ws.max_row):
        if r[4].value and str(r[4].value).startswith("EVET"):
            for cell in r[:header_ncols]:
                cell.fill = _BORDERLINE_FILL

    # --- removed-columns sheet --------------------------------------------
    rem_ws = out.create_sheet("kaldirilan_kolonlar")
    rem_ws.append([
        "Sayfa", "Kaldırılan kolon (Türkçe)", "İngilizce karşılığı",
        "Gerekçe", "Kategori",
    ])
    for row in removed_rows:
        rem_ws.append(row)
    _style_header(rem_ws, 5)

    out.save(OUTPUT_WORKBOOK)
    print(f"Wrote {OUTPUT_WORKBOOK}")
    print(f"  data sheets: {len(SHEET_SPECS)}")
    total_kept = sum(len(r) for _s, r, _m in SHEET_SPECS)
    print(f"  kept columns (data sheets): {total_kept}")
    print(f"  removed columns/sheets entries: {len(removed_rows)}")
    print("  data rows preserved (source == output):")
    for sheet in sheet_row_counts:
        print(f"    {_out_sheet_name(sheet):40} {sheet_row_counts[sheet]}")


if __name__ == "__main__":
    build()
