"""Explicit material-family classification and material<->procedure compatibility table.

Matching is done on norm_key()/norm_expr() text: Turkish-aware upper-case, diacritics folded
(İ->I, Ş->S, Ğ->G, Ü->U, Ö->O, Ç->C), punctuation -> space.  JUDGMENT: the regexes encode
ordinary clinical practice (which operation a device is implanted/used in); they are deliberately
generous (any procedure on the same organ/system counts as compatible).
"""
import polars as pl

from common import norm_expr

# (family, polars predicate) evaluated in order; first hit wins.
# k = normalised material_name, t = normalised material_type, c = material_code
def material_family_expr() -> pl.Expr:
    k = norm_expr("material_name")
    t = norm_expr("material_type")
    c = pl.col("material_code")
    return (
        pl.when(k.str.contains(r"\bICD\b|KALP PILI|DEFIBRILAT")).then(pl.lit("CARDIAC_ICD"))
        .when(c.str.starts_with("AP")).then(pl.lit("ARTHROPLASTY_IMPLANT"))
        .when(k.str.contains("IMPLANT") | (t == "IMPLANT")).then(pl.lit("ORTHO_IMPLANT_GENERIC"))
        .when(k.str.contains("DESFERAL")).then(pl.lit("THALASSEMIA_PUMP_SET"))
        .when(c.str.starts_with("HO")).then(pl.lit("APHERESIS"))
        .when(c.str.starts_with("NF")).then(pl.lit("DIALYSIS_RRT"))
        .when(k.str.contains("OZEFAGUS STENT|OZOFAGUS STENT")).then(pl.lit("ESOPHAGEAL_STENT"))
        .when(c.str.starts_with("GHC") & k.str.contains(
            r"STENT|EBUS|TRANSBRONS|BRONKOSKOP|ENDOBRONS")).then(pl.lit("AIRWAY_BRONCHOSCOPY"))
        .when(c.str.starts_with("GHC")).then(pl.lit("THORACIC_SURGERY"))
        .when(c.str.starts_with("GS")).then(pl.lit("ERCP"))
        .when(c.str.starts_with("OP") | (t == "ORTEZ")).then(pl.lit("EXT_PROSTHESIS_ORTHOSIS"))
        .otherwise(pl.lit("OTHER"))
    )


# Family -> regex a linked procedure name must match to be clinically compatible.
FAMILY_PROC_RE: dict[str, str] = {
    "CARDIAC_ICD": r"\bICD\b|DEFIBRILAT|KARDIYOVERTER|PACEMAKER|KALP PILI|PIL (TAKILMASI|IMPLANT|DEGISIM)",
    "ARTHROPLASTY_IMPLANT": r"ARTROPLAST|HEMIARTROPLAST|EKLEM PROTEZ|(KALCA|DIZ|OMUZ|DIRSEK|BILEK) (TOTAL |PARSIYEL |UNIKONDILER )?PROTEZ|TOTAL (KALCA|DIZ|OMUZ|DIRSEK)|PROTEZ REVIZYON",
    "ORTHO_IMPLANT_GENERIC": r"ARTROPLAST|PROTEZ|OSTEOSENTEZ|FIKSASYON|PLAK|INTRAMEDULLER|KIRIK|FRAKTUR|ARTRODEZ|\bFUZYON|OSTEOTOMI",
    "APHERESIS": r"AFEREZ|FEREZ|PLAZMA DEGISIM|IMMUNADSORB|ADSORBSIYON|KOK HUCRE TOPLA|LDL",
    "THALASSEMIA_PUMP_SET": r"TALASEMI|DESFERAL|SELASYON|\bINFUZYON|TRANSFUZYON",
    "DIALYSIS_RRT": r"\bDIYALIZ|HEMODIYALIZ|PERITON DIYALIZ|HEMOFILTRASYON|HEMODIAFILTRASYON|HEMODIYAFILTRASYON|RENAL REPLASMAN|ULTRAFILTRASYON",
    "AIRWAY_BRONCHOSCOPY": r"BRONKOSKOP|TRAKE|BRONS|EBUS|LARENKS|LARING|HAVA YOLU",
    "ESOPHAGEAL_STENT": r"OZOFAG|OZEFAG|GASTROSKOP|UST GIS|OZOFAGOGASTRO",
    "THORACIC_SURGERY": r"TORAKOSKOP|VATS|TORAKOTOMI|STERNOTOMI|STERNUM|KOSTA|GOGUS DUVARI|PEKTUS|NUSS|PLEVR|TORAKOSTOMI|TORASENTEZ|DEKORTIKASYON|AMPIYEM",
    "ERCP": r"ERCP|KOLANJIYO|PAPILLOTOMI|SFINKTEROTOMI|SAFRA|ENDOSKOPIK RETROGRAD|KOLEDOK|BILIER",
    "EXT_PROSTHESIS_ORTHOSIS": r"AMPUTASYON|DEZARTIKULASYON|PROTEZ|ORTEZ|ATEL|ALCI|SPLINT|REHABILITASYON|FIZIK TEDAVI",
}

# Visits / bed-days that are not tied to any specialty: an implant/device cannot be "used in" them;
# for EXT_PROSTHESIS_ORTHOSIS (prescribed devices) a visit is tolerated (JUDGMENT).
GENERIC_VISIT_RE = (r"^(KONSULTASYON|BIRINCI BASAMAK POLIKLINIK MUAYENESI|ACIL POLIKLINIK MUAYENESI|"
                    r"YESIL ALAN MUAYENESI|GENEL ANESTEZI ALTINDA MUAYENE|STANDART YATAK TARIFESI|"
                    r"GUNDUZ YATAK TARIFESI|ACIL SERVISTE KRITIK HASTA YATAK)")
GENERIC_TOLERATED = {"EXT_PROSTHESIS_ORTHOSIS"}
