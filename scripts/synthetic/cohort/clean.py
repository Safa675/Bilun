"""Build, validate, hash and write the 3 SUT clean clinical Parquet tables (Polars only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
import hashlib
from pathlib import Path
from typing import Any

import polars as pl

from scripts.synthetic.faults import load_siblings
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.schema import Drug, Pins

from .catalogs import CohortCatalogs
from .clinical import PatientClinical, ShowcaseClinical, Vitals, load_clinical
from .compose import ComposedClaim
from .ids import PATIENT_ID_RE
from .tables import TableSchemaError, _canonical_table_text

CLEAN_TABLE_FILES: tuple[str, ...] = (
    "anadata_clean.parquet",
    "lab_clean.parquet",
    "recete_clean.parquet",
)

ANADATA_CLEAN_SCHEMA = pl.Schema(
    {
        "HASTA_ID": pl.String(),
        "SQ_EPISODE": pl.String(),
        "EPISODE_TARIH": pl.Datetime("ns"),
        "TANI_YASI": pl.Int64(),
        "CINSIYET": pl.String(),
        "KB-S": pl.Int64(),
        "KB-D": pl.Int64(),
        "Nabiz": pl.Int64(),
        "SPO2": pl.Int64(),
        "Boy": pl.Int64(),
        "Kilo": pl.Float64(),
        "BMI": pl.Float64(),
        "ILK_TANI_SON_TANI_GUN_FARKI": pl.Int64(),
        "TOPLAM_GELIS_SAYISI": pl.Int64(),
        "GELIS_SAYISI": pl.Int64(),
        "GELIS_TIPI": pl.String(),
        "SERVISADI": pl.String(),
        "TANIKODU": pl.String(),
        "TUM_EPS_TANILAR": pl.String(),
        "TANI_TIPI": pl.String(),
        "TANITARIH": pl.Datetime("ns"),
        "MIN_TANI_TARIH": pl.Datetime("ns"),
        "MAX_TANI_TARIH": pl.Datetime("ns"),
        "Hipertansiyon Hastada": pl.Boolean(),
        "Kalp Damar Hastada": pl.Boolean(),
        "Diyabet Hastada": pl.Boolean(),
        "Kan Hastaliklari Hastada": pl.Boolean(),
        "YAKINMA": pl.String(),
        "OYKU": pl.String(),
        "Muayene Notu": pl.String(),
        "Tedavi Notu": pl.String(),
        "kohort": pl.String(),
        "donem": pl.String(),
    }
)

LAB_CLEAN_SCHEMA = pl.Schema(
    {
        "HASTA_ID": pl.String(),
        "basvuru_id": pl.String(),
        "SUB_CODE": pl.String(),
        "parametre": pl.String(),
        "sonuc_sayisal": pl.Float64(),
        "sonuc_nitel": pl.String(),
        "birim": pl.String(),
        "ref_alt": pl.Float64(),
        "ref_ust": pl.Float64(),
        "anormal_mi": pl.Boolean(),
        "organ_sistemi": pl.String(),
        "kohort": pl.String(),
        "donem": pl.String(),
        "tarih": pl.Datetime("ns"),
    }
)

RECETE_CLEAN_SCHEMA = pl.Schema(
    {
        "HASTA_ID": pl.String(),
        "RECETE_TARIH": pl.Datetime("ns"),
        "RF_EPISODE": pl.String(),
        "ilac_adi": pl.String(),
        "ilac_adi_ham": pl.String(),
        "dozaj_ham": pl.String(),
        "verilis_yolu": pl.String(),
        "gun": pl.Int64(),
        "doz_mg": pl.Int64(),
        "doz_birimi": pl.String(),
        "siklik": pl.Int64(),
        "miktar": pl.Int64(),
        "kohort": pl.String(),
        "donem": pl.String(),
    }
)

CLEAN_TABLE_SCHEMAS: dict[str, pl.Schema] = {
    "anadata_clean.parquet": ANADATA_CLEAN_SCHEMA,
    "lab_clean.parquet": LAB_CLEAN_SCHEMA,
    "recete_clean.parquet": RECETE_CLEAN_SCHEMA,
}

_ONE_DECIMAL = Decimal("0.1")
_HUNDRED = Decimal("100")

_SEX_PIN_TO_CINSIYET: dict[str, str] = {
    "M": "E",
    "F": "K",
}

_CINSIYET_TO_PROSE: dict[str, str] = {
    "E": "erkek",
    "K": "kadın",
}

_CLAIM_TYPE_TO_HOW: dict[str, str] = {
    "yatis": "yatarak tedavi için",
    "acil": "acil olarak",
    "poliklinik": "poliklinik muayenesi için",
    "gunubirlik": "günübirlik işlem için",
}

_EXCLUDED_PROCEDURE_CATEGORIES: frozenset[str] = frozenset({"laboratuvar", "yatak", "muayene"})

_UNIT_TR: dict[str, str] = {
    "vial": "flakon",
    "box": "kutu",
    "syringe": "enjektör",
    "tablet": "tablet",
}


class CleanTableError(TableSchemaError):
    """Raised when a clean clinical table violates its schema or cross-table claim invariants."""


def clean_table_schemas() -> dict[str, pl.Schema]:
    """Return ordered, explicit Polars schemas for all 3 clean clinical Parquet tables."""
    return {name: pl.Schema(schema) for name, schema in CLEAN_TABLE_SCHEMAS.items()}


def sentence_case_tr(text: str) -> str:
    """Turkish-aware sentence case: İ->i, I->ı, lowercase, then capitalise the first letter."""
    stripped = text.strip()
    if not stripped:
        return ""
    lowered = stripped.replace("İ", "i").replace("I", "ı").lower()
    first = lowered[0]
    first_up = "İ" if first == "i" else ("I" if first == "ı" else first.upper())
    return first_up + lowered[1:]


def _icd_in_block(code: str, letter: str, lo: int, hi: int) -> bool:
    if len(code) < 3 or code[0] != letter or not code[1:3].isdigit():
        return False
    num = int(code[1:3])
    return lo <= num <= hi


def derive_comorbidity_flags(icd_codes: Sequence[str]) -> dict[str, bool]:
    """Derive the 4 anadata boolean comorbidity flags from the claim's ICD-10 codes only.

    ICD chapter-level mapping (judgment):
    - 'Hipertansiyon Hastada': any code I10..I15
    - 'Kalp Damar Hastada': any code I20..I99
    - 'Diyabet Hastada': any code E10..E14
    - 'Kan Hastaliklari Hastada': any code D50..D89
    """
    return {
        "Hipertansiyon Hastada": any(_icd_in_block(c, "I", 10, 15) for c in icd_codes),
        "Kalp Damar Hastada": any(_icd_in_block(c, "I", 20, 99) for c in icd_codes),
        "Diyabet Hastada": any(_icd_in_block(c, "E", 10, 14) for c in icd_codes),
        "Kan Hastaliklari Hastada": any(_icd_in_block(c, "D", 50, 89) for c in icd_codes),
    }


def compute_bmi(weight_kg: float | Decimal, height_cm: int) -> Decimal:
    """Compute BMI = weight / (height/100)^2 rounded to 1 decimal with ROUND_HALF_UP."""
    h_m = Decimal(str(height_cm)) / _HUNDRED
    raw = Decimal(str(weight_kg)) / (h_m * h_m)
    return raw.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


def _format_decimal_comma(val: float | Decimal) -> str:
    dec = Decimal(str(val)).quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)
    return f"{dec:.1f}".replace(".", ",")


def format_dozaj_ham(quantity: int, unit: str | None) -> str:
    """Format `dozaj_ham` as `{quantity} {unit_tr}` (or `{quantity}` if unit is unknown)."""
    if not unit:
        return str(quantity)
    unit_tr = _UNIT_TR.get(unit, unit)
    return f"{quantity} {unit_tr}"


def derive_route_from_titck(titck_product_name: str) -> str | None:
    """Conservative route read from the TITCK product name words (None when none match)."""
    low = titck_product_name.replace("İ", "i").replace("I", "ı").lower()
    if "intravenöz" in low or " IV " in f" {titck_product_name} ":
        return "Intravenöz"
    if any(word in low for word in ("tablet", "kapsül", "film kaplı")):
        return "Ağızdan (Oral)"
    if any(word in low for word in ("nebül", "inhalasyon")):
        return "İnhalasyon"
    if "subkütan" in low:
        return "Subkütan"
    return None


def _patient_no_from_id(pid: str) -> int:
    match = PATIENT_ID_RE.fullmatch(pid)
    if match is None:
        raise CleanTableError(f"Invalid patient_id format {pid!r}")
    return int(pid.rsplit("-", 1)[1])


def _resolve_vitals_map(
    clinical: ShowcaseClinical
    | Sequence[PatientClinical]
    | Mapping[int, PatientClinical | Vitals]
    | None,
) -> dict[int, Vitals]:
    if clinical is None:
        loaded = load_clinical()
        return {p.patient_no: p.vitals for p in loaded.patients}
    if isinstance(clinical, ShowcaseClinical):
        return {p.patient_no: p.vitals for p in clinical.patients}
    if isinstance(clinical, Mapping):
        return {
            int(k): (v.vitals if isinstance(v, PatientClinical) else v) for k, v in clinical.items()
        }
    return {p.patient_no: p.vitals for p in clinical}


def _find_drug_entry_and_pins(
    claim: ComposedClaim,
    drug_line_id: str,
    barcode: str,
    pathway: Pathway,
    siblings_by_story: Mapping[str, list[Pathway]],
) -> tuple[Drug | None, Pins]:
    line_to_entry = {lid: eid for eid, lids in claim.entry_line_ids.items() for lid in lids}
    entry_id = line_to_entry.get(drug_line_id)
    candidate_pathways: list[Pathway] = [
        pathway,
        *siblings_by_story.get(pathway.showcase.story, ()),
    ]

    if entry_id is not None:
        for pw in candidate_pathways:
            for d in pw.drugs:
                if d.id == entry_id and d.barcode == barcode:
                    return d, pw.showcase
        for pw in candidate_pathways:
            for d in pw.drugs:
                if d.id == entry_id:
                    return d, pw.showcase

    for pw in candidate_pathways:
        matches = [d for d in pw.drugs if d.barcode == barcode]
        if len(matches) == 1:
            return matches[0], pw.showcase

    return None, pathway.showcase


def _build_narratives(
    claim: ComposedClaim,
    *,
    age: int,
    cinsiyet: str,
    vitals: Vitals,
    bmi_dec: Decimal,
    episode_dt: datetime,
    icd_names: Mapping[str, str],
) -> tuple[str, str, str, str]:
    header = claim.header
    pid = header.patient_id
    primary_code = header.primary_icd10
    if primary_code not in icd_names:
        raise CleanTableError(
            f"anadata_clean.parquet for {pid}: primary_icd10 {primary_code!r} not found in icd10_tr.parquet"
        )
    primary_name = sentence_case_tr(icd_names[primary_code])
    yakinma = f"Başvuru tanısı: {primary_name} ({primary_code})."

    all_names: list[str] = []
    for dx in claim.diagnoses:
        if dx.icd10_code not in icd_names:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: diagnosis {dx.icd10_code!r} not found in icd10_tr.parquet"
            )
        all_names.append(sentence_case_tr(icd_names[dx.icd10_code]))

    if header.claim_type not in _CLAIM_TYPE_TO_HOW:
        raise CleanTableError(
            f"anadata_clean.parquet for {pid}: unsupported GELIS_TIPI {header.claim_type!r}"
        )
    how = _CLAIM_TYPE_TO_HOW[header.claim_type]
    sex_word = _CINSIYET_TO_PROSE[cinsiyet]
    date_str = episode_dt.strftime("%d.%m.%Y")
    oyku = (
        f"{age} yaşında {sex_word} hasta, {date_str} tarihinde {header.department} "
        f"bölümüne {how} başvurdu. Kayıtlı tanılar: {'; '.join(all_names)}."
    )

    weight_str = _format_decimal_comma(vitals.weight_kg)
    bmi_str = _format_decimal_comma(bmi_dec)
    muayene_notu = (
        f"Vital bulgular: tansiyon {vitals.sbp}/{vitals.dbp} mmHg, nabız {vitals.pulse}/dk, "
        f"SpO2 %{vitals.spo2}. Boy {vitals.height_cm} cm, kilo {weight_str} kg, VKİ {bmi_str}."
    )

    proc_candidates = [
        p.procedure_name
        for p in claim.procedures
        if p.procedure_category not in _EXCLUDED_PROCEDURE_CATEGORIES
    ] + [pf.procedure_name for pf in claim.performed]
    distinct_procs = list(dict.fromkeys(proc_candidates))[:6]
    distinct_drugs = list(dict.fromkeys(d.drug_name for d in claim.drugs))[:8]

    procs_text = "; ".join(distinct_procs) if distinct_procs else "yok"
    drugs_text = "; ".join(distinct_drugs) if distinct_drugs else "yok"
    tedavi_notu = f"Uygulanan işlemler: {procs_text}. İlaçlar: {drugs_text}."

    return yakinma, oyku, muayene_notu, tedavi_notu


def build_clean_tables(
    claims: Sequence[ComposedClaim],
    *,
    clinical: ShowcaseClinical
    | Sequence[PatientClinical]
    | Mapping[int, PatientClinical | Vitals]
    | None = None,
    pathways: Mapping[str, Pathway] | None = None,
    siblings: Mapping[str, Pathway] | None = None,
    catalogs: CohortCatalogs | None = None,
    icd_names: Mapping[str, str] | None = None,
    drug_crosswalk: Mapping[str, str] | None = None,
) -> dict[str, pl.DataFrame]:
    """Build the 3 clean Polars DataFrames (`anadata_clean`, `lab_clean`, `recete_clean`)."""
    cats = catalogs if catalogs is not None else CohortCatalogs()
    icd_map = icd_names if icd_names is not None else cats.icd_names_map
    titck_map = drug_crosswalk if drug_crosswalk is not None else cats.titck_names_map
    pathways_map = pathways if pathways is not None else load_all()
    siblings_map = siblings if siblings is not None else load_siblings()
    vitals_by_no = _resolve_vitals_map(clinical)

    siblings_by_story: dict[str, list[Pathway]] = {}
    for sib in siblings_map.values():
        siblings_by_story.setdefault(sib.showcase.story, []).append(sib)

    anadata_rows: list[dict[str, Any]] = []
    recete_rows: list[dict[str, Any]] = []

    for claim in claims:
        header = claim.header
        pid = header.patient_id
        pno = _patient_no_from_id(pid)
        if pno not in vitals_by_no:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: missing clinical vitals for patient_no {pno}"
            )
        vitals = vitals_by_no[pno]

        if header.scenario_tag not in pathways_map:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: pathway {header.scenario_tag!r} not found"
            )
        pathway = pathways_map[header.scenario_tag]
        pins = pathway.showcase
        age = pins.age
        if pins.sex not in _SEX_PIN_TO_CINSIYET:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: unsupported sex pin {pins.sex!r}"
            )
        cinsiyet = _SEX_PIN_TO_CINSIYET[pins.sex]

        ref_date = header.admission_date or header.claim_start_date
        episode_dt = datetime.combine(ref_date, time.min)
        bmi_dec = compute_bmi(vitals.weight_kg, vitals.height_cm)

        dx_codes = [dx.icd10_code for dx in claim.diagnoses]
        if not dx_codes or dx_codes[0] != header.primary_icd10:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: diagnoses must start with primary_icd10 "
                f"{header.primary_icd10!r}, got {dx_codes}"
            )
        tum_eps_tanilar = ",".join(dx_codes)
        comorbidity = derive_comorbidity_flags(dx_codes)
        yakinma, oyku, muayene_notu, tedavi_notu = _build_narratives(
            claim,
            age=age,
            cinsiyet=cinsiyet,
            vitals=vitals,
            bmi_dec=bmi_dec,
            episode_dt=episode_dt,
            icd_names=icd_map,
        )

        anadata_rows.append(
            {
                "HASTA_ID": pid,
                "SQ_EPISODE": header.episode_id,
                "EPISODE_TARIH": episode_dt,
                "TANI_YASI": age,
                "CINSIYET": cinsiyet,
                "KB-S": vitals.sbp,
                "KB-D": vitals.dbp,
                "Nabiz": vitals.pulse,
                "SPO2": vitals.spo2,
                "Boy": vitals.height_cm,
                "Kilo": float(vitals.weight_kg),
                "BMI": float(bmi_dec),
                "ILK_TANI_SON_TANI_GUN_FARKI": 0,
                "TOPLAM_GELIS_SAYISI": 1,
                "GELIS_SAYISI": 1,
                "GELIS_TIPI": header.claim_type,
                "SERVISADI": header.department,
                "TANIKODU": header.primary_icd10,
                "TUM_EPS_TANILAR": tum_eps_tanilar,
                "TANI_TIPI": "Kesin Tani",
                "TANITARIH": episode_dt,
                "MIN_TANI_TARIH": episode_dt,
                "MAX_TANI_TARIH": episode_dt,
                "Hipertansiyon Hastada": comorbidity["Hipertansiyon Hastada"],
                "Kalp Damar Hastada": comorbidity["Kalp Damar Hastada"],
                "Diyabet Hastada": comorbidity["Diyabet Hastada"],
                "Kan Hastaliklari Hastada": comorbidity["Kan Hastaliklari Hastada"],
                "YAKINMA": yakinma,
                "OYKU": oyku,
                "Muayene Notu": muayene_notu,
                "Tedavi Notu": tedavi_notu,
                "kohort": "showcase",
                "donem": str(episode_dt.year),
            }
        )

        for drug_line in claim.drugs:
            rec_dt = datetime.combine(drug_line.drug_claim_date, time.min)
            ilac_adi = drug_line.drug_name
            ilac_adi_ham = titck_map.get(drug_line.barkod) or ilac_adi
            entry, entry_pins = _find_drug_entry_and_pins(
                claim,
                drug_line.drug_claim_line_id,
                drug_line.barkod,
                pathway,
                siblings_by_story,
            )
            unit = entry.unit if entry is not None else None
            dozaj_ham = format_dozaj_ham(drug_line.quantity, unit)
            verilis_yolu = derive_route_from_titck(ilac_adi_ham)

            gun: int | None = None
            siklik: int | None = None
            if entry is not None:
                siklik = entry.per_day
                if entry.course_days is not None:
                    gun = entry_pins.course_days.get(entry.id)
                elif entry.per_night is not None:
                    gun = entry_pins.nights

            recete_rows.append(
                {
                    "HASTA_ID": pid,
                    "RECETE_TARIH": rec_dt,
                    "RF_EPISODE": drug_line.episode_id,
                    "ilac_adi": ilac_adi,
                    "ilac_adi_ham": ilac_adi_ham,
                    "dozaj_ham": dozaj_ham,
                    "verilis_yolu": verilis_yolu,
                    "gun": gun,
                    "doz_mg": None,
                    "doz_birimi": None,
                    "siklik": siklik,
                    "miktar": drug_line.quantity,
                    "kohort": "showcase",
                    "donem": str(rec_dt.year),
                }
            )

    return {
        "anadata_clean.parquet": pl.DataFrame(
            anadata_rows, schema=ANADATA_CLEAN_SCHEMA, strict=True
        ),
        "lab_clean.parquet": pl.DataFrame([], schema=LAB_CLEAN_SCHEMA, strict=True),
        "recete_clean.parquet": pl.DataFrame(recete_rows, schema=RECETE_CLEAN_SCHEMA, strict=True),
    }


def validate_clean_tables(
    clean: Mapping[str, pl.DataFrame],
    claims_tables: Mapping[str, pl.DataFrame] | None = None,
) -> None:
    """Validate clean clinical table schemas, empty `lab_clean`, and cross-checks with `claims_tables`."""
    missing_tables = [t for t in CLEAN_TABLE_FILES if t not in clean]
    extra_tables = [t for t in clean if t not in CLEAN_TABLE_FILES]
    if missing_tables or extra_tables:
        raise CleanTableError(
            f"Clean table set mismatch: missing={missing_tables}, unexpected={extra_tables}"
        )

    for name in CLEAN_TABLE_FILES:
        df = clean[name]
        if not isinstance(df, pl.DataFrame):
            raise CleanTableError(f"{name} must be a polars.DataFrame, got {type(df).__name__}")
        expected = dict(CLEAN_TABLE_SCHEMAS[name])
        actual = dict(df.schema)

        null_cols = [col for col, dt in actual.items() if dt == pl.Null]
        if null_cols:
            raise CleanTableError(f"{name} has Null-typed columns: {null_cols}")

        missing_cols = [col for col in expected if col not in actual]
        extra_cols = [col for col in actual if col not in expected]
        if missing_cols or extra_cols:
            raise CleanTableError(
                f"{name} column mismatch: missing={missing_cols}, unexpected={extra_cols}"
            )

        if list(df.columns) != list(expected.keys()):
            raise CleanTableError(
                f"{name} column order mismatch: expected {list(expected.keys())}, got {list(df.columns)}"
            )

        dtype_mismatches = [
            f"{col}: expected {expected[col]}, got {actual[col]}"
            for col in expected
            if actual[col] != expected[col]
        ]
        if dtype_mismatches:
            raise CleanTableError(f"{name} dtype mismatch: {'; '.join(dtype_mismatches)}")

    lab_df = clean["lab_clean.parquet"]
    if lab_df.height != 0:
        raise CleanTableError(
            f"lab_clean.parquet must be empty (0 rows) in slice C1, got {lab_df.height} rows"
        )

    if claims_tables is None:
        return

    ana_df = clean["anadata_clean.parquet"]
    rec_df = clean["recete_clean.parquet"]
    headers_df = claims_tables["claim_headers.parquet"]
    diagnoses_df = claims_tables["claim_diagnoses.parquet"]
    drugs_df = claims_tables["drug_claim_lines.parquet"]

    if ana_df.height != headers_df.height:
        raise CleanTableError(
            f"anadata_clean.parquet row count ({ana_df.height}) does not equal "
            f"claim_headers.parquet row count ({headers_df.height})"
        )

    ana_episodes = list(
        zip(
            ana_df["HASTA_ID"].to_list(),
            ana_df["SQ_EPISODE"].to_list(),
            strict=True,
        )
    )
    expected_episodes = list(
        zip(
            headers_df["patient_id"].to_list(),
            headers_df["episode_id"].to_list(),
            strict=True,
        )
    )
    if ana_episodes != expected_episodes:
        raise CleanTableError(
            f"anadata_clean.parquet (HASTA_ID, SQ_EPISODE) mismatch against claim_headers.parquet: "
            f"expected {expected_episodes}, got {ana_episodes}"
        )

    for ana_col, hdr_col in (
        ("GELIS_TIPI", "claim_type"),
        ("SERVISADI", "department"),
        ("TANIKODU", "primary_icd10"),
    ):
        ana_vals = ana_df[ana_col].to_list()
        hdr_vals = headers_df[hdr_col].to_list()
        if ana_vals != hdr_vals:
            for pid, got_v, exp_v in zip(
                ana_df["HASTA_ID"].to_list(), ana_vals, hdr_vals, strict=True
            ):
                if got_v != exp_v:
                    raise CleanTableError(
                        f"anadata_clean.parquet.{ana_col} for {pid}: expected {exp_v!r}, got {got_v!r}"
                    )

    dx_grouped = diagnoses_df.group_by("episode_id", maintain_order=True).agg(
        pl.col("icd10_code").str.join(",").alias("expected_tum_eps_tanilar")
    )
    expected_tanilar_by_ep = dict(
        zip(
            dx_grouped["episode_id"].to_list(),
            dx_grouped["expected_tum_eps_tanilar"].to_list(),
            strict=True,
        )
    )
    for pid, ep_id, got_tanilar in zip(
        ana_df["HASTA_ID"].to_list(),
        ana_df["SQ_EPISODE"].to_list(),
        ana_df["TUM_EPS_TANILAR"].to_list(),
        strict=True,
    ):
        exp_tanilar = expected_tanilar_by_ep.get(ep_id, "")
        if got_tanilar != exp_tanilar:
            raise CleanTableError(
                f"anadata_clean.parquet.TUM_EPS_TANILAR for {pid} ({ep_id}): "
                f"expected {exp_tanilar!r} from claim_diagnoses.parquet, got {got_tanilar!r}"
            )

    rec_projected = rec_df.select(
        pl.col("HASTA_ID").alias("patient_id"),
        pl.col("RF_EPISODE").alias("episode_id"),
        pl.col("RECETE_TARIH").dt.strftime("%Y-%m-%d").alias("drug_claim_date"),
        pl.col("ilac_adi").alias("drug_name"),
        pl.col("miktar").alias("quantity"),
    )
    billed_projected = drugs_df.select(
        "patient_id",
        "episode_id",
        "drug_claim_date",
        "drug_name",
        "quantity",
    )
    unbilled = rec_projected.join(
        billed_projected,
        on=["patient_id", "episode_id", "drug_claim_date", "drug_name", "quantity"],
        how="anti",
    )
    if unbilled.height > 0:
        bad_pid = unbilled["patient_id"][0]
        bad_drug = unbilled["drug_name"][0]
        bad_date = unbilled["drug_claim_date"][0]
        raise CleanTableError(
            f"recete_clean.parquet for {bad_pid}: row (ilac_adi={bad_drug!r}, "
            f"RECETE_TARIH={bad_date}) does not match any billed drug line in drug_claim_lines.parquet"
        )
    if rec_df.height != drugs_df.height or not rec_projected.equals(
        billed_projected, null_equal=True
    ):
        raise CleanTableError(
            f"recete_clean.parquet rows ({rec_df.height}) do not match "
            f"drug_claim_lines.parquet ({drugs_df.height})"
        )


def write_clean_tables(
    tables: Mapping[str, pl.DataFrame],
    directory: str | Path,
    *,
    claims_tables: Mapping[str, pl.DataFrame] | None = None,
) -> dict[str, Path]:
    """Write the 3 clean clinical Parquet tables deterministically after validation."""
    validate_clean_tables(tables, claims_tables)
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for name in CLEAN_TABLE_FILES:
        df = tables[name]
        target = out_dir / name
        df.write_parquet(
            target,
            compression="zstd",
            compression_level=3,
            statistics=False,
        )
        written[name] = target
    return written


def clean_tables_digest(tables: Mapping[str, pl.DataFrame]) -> dict[str, str]:
    """Return a SHA-256 hex digest per clean table over its canonical text serialization."""
    validate_clean_tables(tables)
    return {
        name: hashlib.sha256(
            _canonical_table_text(tables[name], dict(CLEAN_TABLE_SCHEMAS[name])).encode("utf-8")
        ).hexdigest()
        for name in CLEAN_TABLE_FILES
    }
