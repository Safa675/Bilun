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
from .clinical import DrugRoute, PatientClinical, ShowcaseClinical, Vitals, load_clinical
from .compose import ComposedClaim
from .ids import PATIENT_ID_RE, claim_sequence
from .labs import LabReferenceError, _fmt, build_lab_clean, check_lab_coherence, expected_lab_keys
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
    "capsule": "kapsül",
    "bottle": "şişe",
    "ampoule": "ampul",
    "bag": "torba",
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


def whole_units(quantity: Decimal | int) -> int:
    """`miktar` of the clean recete table is a whole count (Int64): the cohort bills whole units (a pathway's qty,
    per_night and per_day are integers), so a fraction here is a builder error, never truncated."""
    if quantity != int(quantity):
        raise CleanTableError(
            f"a drug line holds {quantity} units; the recete table counts whole units"
        )
    return int(quantity)


def format_dozaj_ham(quantity: Decimal | int, unit: str | None) -> str:
    """Format `dozaj_ham` as `{quantity} {unit_tr}` (or `{quantity}` if unit is unknown)."""
    if not unit:
        return str(quantity)
    # A unit with no Turkish word stays as written; no pathway unit is such a unit (a test pins that).
    unit_tr = _UNIT_TR.get(unit, unit)
    return f"{quantity} {unit_tr}"


_TR_TO_ASCII = str.maketrans("ıüöşçğ", "iuoscg")


def _fold_tr(text: str) -> str:
    """Lower-case ASCII spelling of a Turkish text: `İ` and `I` become `i`, and `ı ü ö ş ç ğ` their plain letters.

    TITCK product names are written with and without the Turkish letters, so every word list below is
    ASCII and matched against this one spelling. (`str.lower` turns an ASCII `I` into `i`; the dotted
    `İ` it would turn into an `i` plus a combining dot, so that one is replaced first.)
    """
    return text.replace("İ", "i").lower().translate(_TR_TO_ASCII)


def derive_route_from_titck(titck_product_name: str) -> DrugRoute | None:
    """Conservative route read from the TITCK product name words (None when none match).

    The name is folded to lower-case ASCII first, so `KAPSÜL`, `kapsül` and `KAPSUL` are one word.
    """
    padded = f" {_fold_tr(titck_product_name)} "
    if "im/iv" in padded:
        return "İntramusküler/İntravenöz"
    if any(word in padded for word in ("intravenoz", "infuzyon", "i.v.", " iv ")):
        return "Intravenöz"
    if any(word in padded for word in ("tablet", "kapsul", "film kapli")):
        return "Ağızdan (Oral)"
    if any(word in padded for word in ("nebul", "inhalasyon")):
        return "İnhalasyon"
    if "subkutan" in padded:
        return "Subkütan"
    return None


def resolve_drug_route(product_name: str, barcode: str, declared: Mapping[str, str]) -> str:
    """Route of a billed product: read from its TITCK name, else the one declared for its barcode.

    `declared` is `drug_routes.by_barcode` of the clinical YAML. A name that states a route and a
    declaration that disagrees with it is an error, and so is a product with neither.
    """
    derived = derive_route_from_titck(product_name)
    declared_route = declared.get(barcode)
    if derived is None:
        if declared_route is None:
            raise CleanTableError(
                f"recete_clean.parquet: the TITCK name {product_name!r} (barcode {barcode}) "
                f"states no route of administration; declare it in drug_routes"
            )
        return declared_route
    if declared_route is not None and declared_route != derived:
        raise CleanTableError(
            f"recete_clean.parquet: drug_routes declares {declared_route!r} for {product_name!r} "
            f"(barcode {barcode}) but its TITCK name states {derived!r}"
        )
    return derived


def _patient_no_from_id(pid: str) -> int:
    match = PATIENT_ID_RE.fullmatch(pid)
    if match is None:
        raise CleanTableError(f"Invalid patient_id format {pid!r}")
    return int(pid.rsplit("-", 1)[1])


def _encounter_no_from_claim(claim_id: str) -> int:
    """The encounter of a claim: its sequence within the patient (the last three digits of the id)."""
    try:
        return claim_sequence(claim_id)
    except ValueError as exc:
        raise CleanTableError(str(exc)) from None


def _resolve_vitals_map(
    clinical: ShowcaseClinical | Sequence[PatientClinical] | Mapping[Any, PatientClinical | Vitals],
) -> dict[tuple[int, int], Vitals]:
    """The vitals of each encounter, keyed by (patient_no, encounter_no).

    A mapping may be keyed by the patient number alone (the patient's first encounter) or by a
    (patient_no, encounter_no) pair.
    """
    if isinstance(clinical, ShowcaseClinical):
        return {(p.patient_no, p.encounter_no): p.vitals for p in clinical.patients}
    if isinstance(clinical, Mapping):
        return {
            (int(key[0]), int(key[1])) if isinstance(key, tuple) else (int(key), 1): (
                value.vitals if isinstance(value, PatientClinical) else value
            )
            for key, value in clinical.items()
        }
    return {(p.patient_no, p.encounter_no): p.vitals for p in clinical}


def _resolve_drug_routes(
    clinical: ShowcaseClinical | Sequence[PatientClinical] | Mapping[Any, PatientClinical | Vitals],
) -> dict[str, str]:
    """Routes declared per barcode; only a `ShowcaseClinical` document can carry them."""
    if isinstance(clinical, ShowcaseClinical) and clinical.drug_routes is not None:
        return dict(clinical.drug_routes.by_barcode)
    return {}


def _find_drug_entry_and_pins(
    claim: ComposedClaim,
    drug_line_id: str,
    barcode: str,
    pathway: Pathway,
    siblings_by_story: Mapping[str, list[Pathway]],
) -> tuple[Drug | None, Pins]:
    """The pathway entry a billed drug line comes from, and the pins of the encounter it was expanded with.

    The pins are the claim's effective pins (`ComposedClaim.pins`: the recipe's overrides over the pathway's
    own `showcase` block); a claim that carries none gets the `showcase` pins of the pathway or sibling the
    entry was found in.
    """
    line_to_entry = {lid: eid for eid, lids in claim.entry_line_ids.items() for lid in lids}
    entry_id = line_to_entry.get(drug_line_id)
    candidate_pathways: list[Pathway] = [
        pathway,
        *siblings_by_story.get(pathway.showcase.story, ()),
    ]

    def pins_of(pw: Pathway) -> Pins:
        return claim.pins if claim.pins is not None else pw.showcase

    if entry_id is not None:
        for pw in candidate_pathways:
            for d in pw.drugs:
                if d.id == entry_id and d.barcode == barcode:
                    return d, pins_of(pw)
        for pw in candidate_pathways:
            for d in pw.drugs:
                if d.id == entry_id:
                    return d, pins_of(pw)

    for pw in candidate_pathways:
        matches = [d for d in pw.drugs if d.barcode == barcode]
        if len(matches) == 1:
            return matches[0], pins_of(pw)

    return None, pins_of(pathway)


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
    | Mapping[Any, PatientClinical | Vitals]
    | None = None,
    pathways: Mapping[str, Pathway] | None = None,
    siblings: Mapping[str, Pathway] | None = None,
    catalogs: CohortCatalogs | None = None,
    icd_names: Mapping[str, str] | None = None,
    drug_crosswalk: Mapping[str, str] | None = None,
) -> dict[str, pl.DataFrame]:
    """Build the 3 clean Polars DataFrames (`anadata_clean`, `lab_clean`, `recete_clean`).

    `claims` come in the order of `claim_headers.parquet` (by patient, then by date of the encounter: see
    `build_showcase`); the anadata and recete rows follow it, and `validate_clean_tables` compares them with the
    claims tables row by row. The vitals of a claim are those of the (patient_no, encounter_no) entry of
    `clinical`, its age and sex those of the claim's effective pins (`ComposedClaim.pins`).
    """
    cats = catalogs if catalogs is not None else CohortCatalogs()
    icd_map = icd_names if icd_names is not None else cats.icd_names_map
    titck_map = drug_crosswalk if drug_crosswalk is not None else cats.titck_names_map
    pathways_map = pathways if pathways is not None else load_all()
    siblings_map = siblings if siblings is not None else load_siblings()
    document = load_clinical() if clinical is None else clinical
    vitals_by_encounter = _resolve_vitals_map(document)
    routes_by_barcode = _resolve_drug_routes(document)

    siblings_by_story: dict[str, list[Pathway]] = {}
    for sib in siblings_map.values():
        siblings_by_story.setdefault(sib.showcase.story, []).append(sib)

    anadata_rows: list[dict[str, Any]] = []
    recete_rows: list[dict[str, Any]] = []

    for claim in claims:
        header = claim.header
        pid = header.patient_id
        pno = _patient_no_from_id(pid)
        encounter = _encounter_no_from_claim(header.claim_id)
        if (pno, encounter) not in vitals_by_encounter:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: missing clinical vitals for patient_no {pno}, "
                f"encounter {encounter}"
            )
        vitals = vitals_by_encounter[(pno, encounter)]

        if header.scenario_tag not in pathways_map:
            raise CleanTableError(
                f"anadata_clean.parquet for {pid}: pathway {header.scenario_tag!r} not found"
            )
        pathway = pathways_map[header.scenario_tag]
        pins = claim.pins if claim.pins is not None else pathway.showcase
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
            dozaj_ham = format_dozaj_ham(whole_units(drug_line.quantity), unit)
            verilis_yolu = resolve_drug_route(ilac_adi_ham, drug_line.barkod, routes_by_barcode)

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
                    "miktar": whole_units(drug_line.quantity),
                    "kohort": "showcase",
                    "donem": str(rec_dt.year),
                }
            )

    try:
        lab_df = build_lab_clean(
            claims,
            clinical=document,
            pathways=pathways_map,
            schema=LAB_CLEAN_SCHEMA,
        )
    except TableSchemaError as exc:
        raise CleanTableError(str(exc)) from exc

    return {
        "anadata_clean.parquet": pl.DataFrame(
            anadata_rows, schema=ANADATA_CLEAN_SCHEMA, strict=True
        ),
        "lab_clean.parquet": lab_df,
        "recete_clean.parquet": pl.DataFrame(recete_rows, schema=RECETE_CLEAN_SCHEMA, strict=True),
    }


def _describe_first(frame: pl.DataFrame) -> str:
    """The first key row of `frame` as one line (patient, episode, day, code and parameter)."""
    return (
        frame.head(1)
        .select(
            pl.concat_str(
                "HASTA_ID",
                "basvuru_id",
                "day",
                pl.concat_str("SUB_CODE", "parametre", separator="|"),
                separator=" ",
            )
        )
        .item()
    )


def _check_lab_rows_match_billed_lines(lab_df: pl.DataFrame, procs_df: pl.DataFrame) -> None:
    """`lab_clean` holds the result rows of the billed lab lines and nothing else, in the same order."""
    try:
        expected = expected_lab_keys(procs_df)
    except LabReferenceError as exc:
        raise CleanTableError(str(exc)) from exc
    actual = lab_df.select(
        "HASTA_ID",
        "basvuru_id",
        pl.col("tarih").dt.strftime("%Y-%m-%d").alias("day"),
        "SUB_CODE",
        "parametre",
    )
    if actual.equals(expected):
        return
    # Number the copies of one key (two troponin result sets share their keys) before comparing.
    keys = actual.columns
    numbered = [
        frame.with_columns(pl.int_range(pl.len()).over(keys).alias("copy"))
        for frame in (actual, expected)
    ]
    missing = numbered[1].join(numbered[0], on=[*keys, "copy"], how="anti")
    unexpected = numbered[0].join(numbered[1], on=[*keys, "copy"], how="anti")
    detail = f"{actual.height} rows for {expected.height} expected"
    if missing.is_empty() and unexpected.is_empty():
        detail += "; the rows are in a different order"
    if not missing.is_empty():
        detail += f"; {missing.height} missing, first {_describe_first(missing)}"
    if not unexpected.is_empty():
        detail += f"; {unexpected.height} unexpected, first {_describe_first(unexpected)}"
    raise CleanTableError(
        "lab_clean.parquet rows do not match the billed lab lines in "
        f"procedure_claim_lines.parquet ({detail})"
    )


def _quoted(column: str) -> pl.Expr:
    """`column` as Python's `repr` prints a string: in single quotes, and `None` for a missing value."""
    return (
        pl.when(pl.col(column).is_null())
        .then(pl.lit("None"))
        .otherwise(pl.concat_str(pl.lit("'"), pl.col(column), pl.lit("'")))
    )


def _first_message(frame: pl.DataFrame, bad: pl.Expr, message: pl.Expr) -> str | None:
    """`message` for the first row of `frame` where `bad` holds, or None when there is no such row."""
    found = frame.filter(bad.fill_null(False)).head(1)
    return None if found.is_empty() else found.select(message).item()


def _check_anadata_against_claims(
    ana_df: pl.DataFrame, headers_df: pl.DataFrame, diagnoses_df: pl.DataFrame
) -> None:
    """`anadata_clean` is one row per claim header, in the order of `claim_headers`, with its classification and diagnoses.

    Row i of `anadata_clean` is put next to row i of `claim_headers` and compared by expressions; the
    first mismatch (patient and episode, then GELIS_TIPI, SERVISADI, TANIKODU, then TUM_EPS_TANILAR
    against the diagnoses of the claim) is the error.
    """
    if ana_df.height != headers_df.height:
        raise CleanTableError(
            f"anadata_clean.parquet row count ({ana_df.height}) does not equal "
            f"claim_headers.parquet row count ({headers_df.height})"
        )
    pairs = pl.concat(
        [
            ana_df.select(
                "HASTA_ID", "SQ_EPISODE", "GELIS_TIPI", "SERVISADI", "TANIKODU", "TUM_EPS_TANILAR"
            ),
            headers_df.select(
                "patient_id", "episode_id", "claim_type", "department", "primary_icd10"
            ),
        ],
        how="horizontal",
    ).with_row_index("row")
    message = _first_message(
        pairs,
        pl.col("HASTA_ID").ne_missing(pl.col("patient_id"))
        | pl.col("SQ_EPISODE").ne_missing(pl.col("episode_id")),
        _fmt(
            "anadata_clean.parquet (HASTA_ID, SQ_EPISODE) mismatch against claim_headers.parquet "
            "at row {}: expected ({}, {}), got ({}, {})",
            "row",
            "patient_id",
            "episode_id",
            "HASTA_ID",
            "SQ_EPISODE",
        ),
    )
    for ana_col, hdr_col in (
        ("GELIS_TIPI", "claim_type"),
        ("SERVISADI", "department"),
        ("TANIKODU", "primary_icd10"),
    ):
        message = message or _first_message(
            pairs,
            pl.col(ana_col).ne_missing(pl.col(hdr_col)),
            _fmt(
                f"anadata_clean.parquet.{ana_col} for {{}}: expected {{}}, got {{}}",
                "HASTA_ID",
                _quoted(hdr_col),
                _quoted(ana_col),
            ),
        )
    expected_diagnoses = (
        diagnoses_df.group_by("episode_id", maintain_order=True)
        .agg(pl.col("icd10_code").str.join(",").alias("expected"))
        .rename({"episode_id": "SQ_EPISODE"})
    )
    with_expected = (
        pairs.join(expected_diagnoses, on="SQ_EPISODE", how="left")
        .sort("row")
        .with_columns(pl.col("expected").fill_null(""))
    )
    message = message or _first_message(
        with_expected,
        pl.col("TUM_EPS_TANILAR").ne_missing(pl.col("expected")),
        _fmt(
            "anadata_clean.parquet.TUM_EPS_TANILAR for {} ({}): expected {} from "
            "claim_diagnoses.parquet, got {}",
            "HASTA_ID",
            "SQ_EPISODE",
            _quoted("expected"),
            _quoted("TUM_EPS_TANILAR"),
        ),
    )
    if message is not None:
        raise CleanTableError(message)


def validate_clean_tables(
    clean: Mapping[str, pl.DataFrame],
    claims_tables: Mapping[str, pl.DataFrame] | None = None,
) -> None:
    """Validate the clean clinical tables: schemas, `lab_clean` coherence, and cross-checks with `claims_tables`.

    Without `claims_tables` only the schemas and `labs.check_lab_coherence(lab_clean, ana_df=anadata_clean)`
    run. That check never looks at the claims, so it cannot see a result set that is coherent but not
    billed: a set on another day or under another patient and episode, an extra, missing or duplicated
    set, or sets in another order. Only the call WITH `claims_tables` finds those: it compares the lab
    rows with the billed lab lines of `procedure_claim_lines` (`_check_lab_rows_match_billed_lines`),
    checks `anadata_clean` against `claim_headers` and `claim_diagnoses`, and `recete_clean` against
    `drug_claim_lines`. `clean_tables_digest` calls this function without claims.
    """
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

    ana_df = clean["anadata_clean.parquet"]
    lab_df = clean["lab_clean.parquet"]
    rec_df = clean["recete_clean.parquet"]

    try:
        check_lab_coherence(lab_df, ana_df=ana_df)
    except TableSchemaError as exc:
        raise CleanTableError(str(exc)) from exc

    if claims_tables is None:
        return

    headers_df = claims_tables["claim_headers.parquet"]
    diagnoses_df = claims_tables["claim_diagnoses.parquet"]
    procs_df = claims_tables["procedure_claim_lines.parquet"]
    drugs_df = claims_tables["drug_claim_lines.parquet"]

    _check_anadata_against_claims(ana_df, headers_df, diagnoses_df)
    _check_lab_rows_match_billed_lines(lab_df, procs_df)

    rec_projected = rec_df.select(
        pl.col("HASTA_ID").alias("patient_id"),
        pl.col("RF_EPISODE").alias("episode_id"),
        pl.col("RECETE_TARIH").dt.strftime("%Y-%m-%d").alias("drug_claim_date"),
        pl.col("ilac_adi").alias("drug_name"),
        pl.col("miktar").cast(pl.Float64).alias("quantity"),
    )
    billed_projected = drugs_df.select(
        "patient_id",
        "episode_id",
        "drug_claim_date",
        "drug_name",
        pl.col("quantity").cast(pl.Float64),
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
    """Return a SHA-256 hex digest per clean table over its canonical text serialization.

    The tables are validated WITHOUT the claims (the signature has no claims argument), so the digest
    of a lab table with a coherent but unbilled result set is computed all the same; see
    `validate_clean_tables`. Call that with the claims tables to catch those.
    """
    validate_clean_tables(tables)
    return {
        name: hashlib.sha256(
            _canonical_table_text(tables[name], dict(CLEAN_TABLE_SCHEMAS[name])).encode("utf-8")
        ).hexdigest()
        for name in CLEAN_TABLE_FILES
    }
