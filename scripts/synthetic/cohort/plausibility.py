"""Plausibility checks for the generated showcase bills (plan D5, slice E1: patient to anaesthesia).

The checks read the nine claims tables and the clean `anadata_clean` table of one dataset and report
what an auditor would call implausible: a diagnosis that cannot exist on its day or for this patient,
codes that do not belong to the claim's care pathway, a stay without a bed for every day, a
performed procedure that was never billed, a package claim that carries a bed, an operation without
its anaesthesia.

`check_plausibility(tables, clean_tables)` is a pure function of the tables it is given: it knows no
fault and calls no engine. It has one small function per check id (`CHECK_FUNCTIONS`) and runs all
of them, or only the ids of `only`. `CHECKS` is the stable registry of ids; a test requires a
mutation case for each id. Slices E2 (materials, prices, money, labels) and E3 (clinical content of
the clean tables) add ids to the same registry: put the id and its meaning in `CHECKS`, write
`check_<name>(bill) -> list[Problem]`, list it in `CHECK_FUNCTIONS`, and add a mutation `Case` (and,
for a defect that shows on a committed faulty bill, the pinned row) to the test file.

`Problem.where` starts with the claim id (then `table[line id]` or a detail, after a space).

The reference data (EK-2B/EK-2C history, chapters, ICD-10, code sets, the care pathways and their
fault siblings) are read once, lazily, by a `PlausibilityContext`.

Everything is vectorised Polars. A `Problem` is built only from the finished findings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
import re

import polars as pl

from scripts.synthetic.faults import FaultRegistry, load_registry, load_siblings
from scripts.synthetic.faults.schema import UseSiblingPathway
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.checks import Catalogs, _group_expr
from scripts.synthetic.pathways.expand import expand
from scripts.synthetic.pathways.schema import Problem as _PathwayProblem

REPO = Path(__file__).resolve().parents[3]

TABLE_CLAIM_HEADERS = "claim_headers.parquet"
TABLE_DIAGNOSES = "claim_diagnoses.parquet"
TABLE_PROCEDURES = "procedure_claim_lines.parquet"
TABLE_MATERIALS = "material_claim_lines.parquet"
TABLE_DRUGS = "drug_claim_lines.parquet"
TABLE_PERFORMED = "performed_procedure_lines.parquet"
TABLE_COPAY = "patient_copay_profiles.parquet"
TABLE_ANADATA = "anadata_clean.parquet"

# Every check id a plausibility Problem may carry, with a one-line meaning (at most 120 characters).
# A meta-test requires an implementation and an in-memory mutation case for each id.
CHECKS: dict[str, str] = {
    # patient: the diagnoses against the ICD table and the patient
    "patient.icd_valid": "a diagnosis that is unknown, inactive, not a leaf, not yet created or already passive on its date",
    "patient.sex_gate": "a diagnosis or a procedure name that is limited to one sex, on a patient of the other sex",
    "patient.age_gate": "a diagnosis or a procedure name that the age (or sex) of the patient excludes",
    "patient.age_arithmetic": "a TANI_YASI that is not the year of the claim minus the patient's birth year",
    # fit: the lines against the care pathway and the setting
    "fit.pathway_membership": "a code outside the expansion of the claim's pathway, or of a fault sibling that targets it",
    "fit.operation_department": "an operation line whose EK-2A branch is not a surgical branch",
    "fit.operation_setting": "a major operation (group A1, A2, A3 or B) on a poliklinik or acil claim",
    "fit.visit_code": "an examination line whose code does not fit the claim type (acil, poliklinik, yatis)",
    # stay: beds, companions and dates
    "stay.bed_coverage": "an itemised stay without exactly one bed line of quantity 1 on each day from admission to discharge",
    "stay.companion_coverage": "a companion line of quantity not 1, twice on a day, or outside admission..discharge-1",
    "stay.dates_in_window": "a header whose dates contradict the claim type, or a line date outside the claim window",
    # bill: performed against billed
    "bill.performed_billed": "a performed procedure with no billed line of the same code on the same day",
    # package: the billing mode
    "package.mode": "package_candidate that disagrees with the package lines, or a package claim with a bed or anaesthesia line",
    # anaesthesia: one per operation date, in the right group
    "anaesthesia.operation_pairing": "an operation date without exactly one anaesthesia line, or an anaesthesia line without an operation",
    "anaesthesia.group": "an anaesthesia code that is not the code of the puan band of the day's operations",
}

# --- judgment tables -------------------------------------------------------------------------
# These are decisions of the author, not facts of the SUT. They are a starting point: a word that
# trips a line of a clean twin must be narrowed or removed (and the change reported).

# patient.sex_gate: words of a procedure name that limit it to one sex. A word matches inside a word
# (prostat -> prostatektomi), written lower case or upper case, with or without Turkish letters.
MALE_ONLY_WORDS: tuple[str, ...] = (
    "prostat", "penil", "penis", "penektomi", "testis", "orşiektomi", "orsiektomi", "skrotum",
    "hidrosel", "varikosel", "vazektomi", "sünnet", "sunnet", "epididim",
)  # fmt: skip
FEMALE_ONLY_WORDS: tuple[str, ...] = (
    "uterus", "rahim", "histerektomi", "histeroskopi", "vajin", "vulva", "serviks", "ooferektomi",
    "salpenjektomi", "jinekolojik", "gebelik", "doğum", "sezaryen", "inseminasyon", "kürtaj",
)  # fmt: skip
FEMALE_ONLY_WHOLE_WORDS: tuple[str, ...] = ("over",)  # not "overdoz", "recover"

# Phrases that contain one of the sex or age words without the meaning (checked against the EK-2B and
# EK-2C names): they are blanked out of a name before its words are looked for. A test requires every
# phrase to occur in a catalog name.
NAME_EXCEPTIONS: tuple[str, ...] = (
    "Yenidoğan/Çocuk/Erişkin",  # one code for every age
    "Yenidoğan/Çocuk",  # one code for newborn and child
    "Çocuk-büyük",  # EEG for child and adult
    "sağlam çocuk doğmasına",  # IVF and preimplantation tests: the patients are the parents
    "cross-over",  # a venous graft, not the ovary
    "Meme/Over Kanseri",  # BRCA analysis, also done for men
    "penisil",  # penicillin (Penisilin G IgE antikoru), penisilyum
    "doğumsal",  # congenital (heart disease), not birth
    "invajinasyon",  # intussusception of the bowel, not the vagina
)


@dataclass(frozen=True)
class AgeGate:
    """One age rule: `words` are ICD code prefixes (source icd) or name words (source name)."""

    source: str
    words: tuple[str, ...]
    min_age: int | None
    max_age: int | None
    sex: str | None
    why: str

    @property
    def limits(self) -> str:
        """The rule in words, for a message: `sex F, age 10..55`."""
        low, high = self.min_age, self.max_age
        age = (
            f"age {low}..{high}" if low is not None and high is not None
            else f"age at least {low}" if low is not None
            else f"age at most {high}"
        )  # fmt: skip
        return f"sex {self.sex}, {age}" if self.sex else age


# patient.age_gate: the age is `anadata_clean` TANI_YASI; both limits are inclusive.
AGE_GATES: tuple[AgeGate, ...] = (
    AgeGate("icd", ("P",), None, 1, None, "a perinatal condition (ICD chapter P)"),
    AgeGate("icd", ("O",), 10, 55, "F", "a pregnancy condition (ICD chapter O)"),
    AgeGate("icd", ("Z38",), None, 1, None, "a liveborn infant code (Z38)"),
    AgeGate("name", ("yenidoğan", "neonatal", "prematüre"), None, 1, None, "a newborn procedure"),
    AgeGate("name", ("pediatrik", "çocuk"), None, 17, None, "a paediatric procedure"),
    AgeGate("name", ("erişkin",), 18, None, None, "an adult procedure"),
)  # fmt: skip

# fit.operation_department: EK-2A branches (specialty_code) a surgeon of an operation may have.
SURGICAL_SPECIALTY_CODES: frozenset[str] = frozenset(
    {
        "1900",  # Genel Cerrahi
        "1901",  # El Cerrahisi (Genel Cerrahi)
        "1910",  # Cerrahi Onkoloji
        "1975",  # Gastroenteroloji Cerrahisi
        "2000",  # Çocuk Cerrahisi
        "2200",  # Göğüs Cerrahisi
        "2300",  # Kalp ve Damar Cerrahisi
        "2387",  # Çocuk Kalp ve Damar Cerrahisi
        "2400",  # Beyin ve Sinir Cerrahisi
        "2500",  # Plastik, Rekonstrüktif ve Estetik Cerrahi
        "2579",  # El Cerrahisi (Plastik, Rekonstrüktif ve Estetik Cerrahi)
        "2600",  # Ortopedi ve Travmatoloji
        "2679",  # El Cerrahisi (Ortopedi ve Travmatoloji)
        "2700",  # Üroloji
        "2781",  # Çocuk Ürolojisi
        "2800",  # Kulak Burun Boğaz Hastalıkları
        "2900",  # Göz Hastalıkları
        "3000",  # Kadın Hastalıkları ve Doğum
        "3010",  # Jinekolojik Onkoloji Cerrahisi
        "5100",  # Ağız, Diş ve Çene Cerrahisi
        "5350",  # Ağız, Yüz ve Çene Cerrahisi
    }
)

# fit.operation_setting: the surgical groups of an operation that needs a ward, not an ER or clinic.
MAJOR_GROUPS: tuple[str, ...] = ("A1", "A2", "A3", "B")

# fit.visit_code: the code_sets.yaml `visits` entry each claim type may bill.
VISIT_KEYS: dict[str, str] = {"acil": "acil", "poliklinik": "poliklinik", "yatis": "consultation"}

# Chapter 6 of EK-2B holds the operations.
OPERATION_GROUP_ID = "6"

_DATE_FORMAT = "%Y-%m-%d"


# --- the Problem ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Problem(_PathwayProblem):
    """One finding: a stable check id, where (the claim id, then a detail) and what is wrong."""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")

    @property
    def claim_id(self) -> str:
        """The claim a finding is about: `where` starts with it."""
        return self.where.split(" ", 1)[0]


class PlausibilityError(ValueError):
    """The tables handed to `check_plausibility` lack a table the checks read."""


# --- Turkish-insensitive text ------------------------------------------------------------------

_TURKISH = str.maketrans("ıçğöşü", "icgosu")
_COMBINING_DOT = chr(0x0307)  # lower-casing the capital dotted I gives an i followed by this mark


def fold_text(text: str) -> str:
    """Lower case without Turkish letters: `İÇ` and `ic`, `Sünnet` and `sunnet` compare equal."""
    return text.lower().replace(_COMBINING_DOT, "").translate(_TURKISH)


def _fold(expr: pl.Expr) -> pl.Expr:
    """`fold_text` as an expression."""
    folded = expr.str.to_lowercase().str.replace_all(_COMBINING_DOT, "", literal=True)
    for turkish, plain in zip("ıçğöşü", "icgosu", strict=True):
        folded = folded.str.replace_all(turkish, plain, literal=True)
    return folded


def _without_exceptions(folded: pl.Expr) -> pl.Expr:
    """A folded name with the NAME_EXCEPTIONS phrases blanked out (longest phrase first)."""
    for phrase in sorted((fold_text(p) for p in NAME_EXCEPTIONS), key=len, reverse=True):
        folded = folded.str.replace_all(phrase, " ", literal=True)
    return folded


def _words_pattern(words: Iterable[str], *, whole: bool = False) -> str:
    """A regex that finds any of `words` (folded), inside words or, with `whole`, as whole words."""
    alternatives = "|".join(sorted({re.escape(fold_text(w)) for w in words}))
    return rf"\b(?:{alternatives})\b" if whole else f"(?:{alternatives})"


_MALE_PATTERN = _words_pattern(MALE_ONLY_WORDS)
_FEMALE_PATTERN = (
    f"{_words_pattern(FEMALE_ONLY_WORDS)}|{_words_pattern(FEMALE_ONLY_WHOLE_WORDS, whole=True)}"
)


# --- the reference data -----------------------------------------------------------------------


class PlausibilityContext:
    """The reference data the checks compare with; each part is read once, on first use."""

    def __init__(
        self,
        root: Path = REPO,
        *,
        catalogs: Catalogs | None = None,
        pathways: Mapping[str, Pathway] | None = None,
        siblings: Mapping[str, Pathway] | None = None,
        fault_registry: FaultRegistry | None = None,
    ) -> None:
        self.root = Path(root)
        self._catalogs = catalogs
        self._pathways = pathways
        self._siblings = siblings
        self._fault_registry = fault_registry

    @cached_property
    def catalogs(self) -> Catalogs:
        return self._catalogs if self._catalogs is not None else Catalogs(self.root)

    @cached_property
    def code_sets(self) -> dict:
        return self.catalogs.code_sets

    @cached_property
    def icd(self) -> pl.DataFrame:
        """code, is_active, is_leaf, sex (M, F or null), created_on, passive_on (Date), known."""
        path = self.root / "data/synthetic/reference/icd10_tr.parquet"
        dates = pl.read_parquet(path, columns=["code", "created_on", "passive_on"])
        base = self.catalogs.icd.select("code", "is_active", "is_leaf", "sex")
        return base.join(dates, on="code", how="left").with_columns(pl.lit(True).alias("known"))

    @cached_property
    def operation_codes(self) -> list[str]:
        """The EK-2B codes of chapter 6 (surgery)."""
        chapters = self.catalogs.chapters
        return chapters.filter(pl.col("group_id") == OPERATION_GROUP_ID)["code"].to_list()

    @cached_property
    def icu_codes(self) -> list[str]:
        """The ICU packages (adult and newborn): paket lines that do not make a package claim."""
        packages = self.code_sets["icu_packages"]
        return [tier["code"] for kind in packages.values() for tier in kind.values()]

    @cached_property
    def bed_day_codes(self) -> list[str]:
        """The codes of one bed-day line: ward day, day bed, ICU day fee, and the ICU packages."""
        beds = self.code_sets["beds"]
        fee = [
            beds["ward_day"]["code"],
            beds["day_bed"]["code"],
            beds["icu_day_fee_for_service"]["code"],
        ]
        return [*fee, *self.icu_codes]

    @cached_property
    def companion_code(self) -> str:
        return self.code_sets["beds"]["companion"]["code"]

    @cached_property
    def anaesthesia_codes(self) -> list[str]:
        sets = self.code_sets["anaesthesia"]
        return [*sets["single"].values(), *sets["multiple_operations"].values()]

    @cached_property
    def anaesthesia_by_group(self) -> pl.DataFrame:
        """group, single, multiple: the anaesthesia code of a surgical group."""
        sets = self.code_sets["anaesthesia"]
        groups = list(sets["single"])
        return pl.DataFrame(
            {
                "group": groups,
                "single": [sets["single"][g] for g in groups],
                "multiple": [sets["multiple_operations"][g] for g in groups],
            }
        )

    @cached_property
    def visit_codes(self) -> pl.DataFrame:
        """claim_type, visit_code: the one examination code each claim type may bill."""
        visits = self.code_sets["visits"]
        types = list(VISIT_KEYS)
        return pl.DataFrame(
            {"claim_type": types, "visit_code": [visits[VISIT_KEYS[t]]["code"] for t in types]}
        )

    @cached_property
    def bands(self) -> list[dict]:
        """The surgical group band tables, oldest first."""
        return sorted(self.code_sets["surgical_group_bands"], key=lambda b: b["effective_from"])

    def band_group(self, day: pl.Expr, total: pl.Expr) -> pl.Expr:
        """The surgical group of a puan total on an ISO day: the band table in force that day."""
        group = pl.lit(None, dtype=pl.String)
        for table in self.bands:
            in_force = day >= table["effective_from"]
            group = (
                pl.when(in_force).then(_group_expr(total, table["lower_bounds"])).otherwise(group)
            )
        return group

    @cached_property
    def specialties(self) -> set[str]:
        return self.catalogs.specialties

    @cached_property
    def pathways(self) -> Mapping[str, Pathway]:
        if self._pathways is not None:
            return self._pathways
        return load_all(self.root / "data/synthetic/pathways")

    @cached_property
    def siblings(self) -> Mapping[str, Pathway]:
        if self._siblings is not None:
            return self._siblings
        return load_siblings(self.root / "data/synthetic/faults/siblings")

    @cached_property
    def fault_registry(self) -> FaultRegistry:
        if self._fault_registry is not None:
            return self._fault_registry
        return load_registry(self.root / "data/synthetic/faults/fault_registry.yaml")

    @cached_property
    def sibling_ids(self) -> dict[str, list[str]]:
        """pathway id -> the sibling pathways the faults that target it swap in."""
        found: dict[str, list[str]] = {}
        for fault in self.fault_registry.faults:
            for op in fault.mutations:
                if isinstance(op, UseSiblingPathway):
                    found.setdefault(fault.target_pathway, []).append(op.sibling_pathway_id)
        return found

    @cached_property
    def vocabulary(self) -> pl.DataFrame:
        """scenario_tag, family, code: what the clean bill of each pathway (and its siblings) holds."""
        tags: list[str] = []
        families: list[str] = []
        codes: list[str] = []
        for pathway_id, pathway in self.pathways.items():
            bills = [expand(pathway)]
            bills += [
                expand(self.siblings[sid], pathway.showcase)
                for sid in self.sibling_ids.get(pathway_id, [])
            ]
            for bill in bills:
                held = {
                    "procedure": [p["code"] for p in bill["procedures"]],
                    "material": [m["code"] for m in bill["materials"]],
                    "drug": [d["barcode"] for d in bill["drugs"]],
                    "diagnosis": [d["icd10"] for d in bill["diagnoses"]],
                }
                for family, family_codes in held.items():
                    tags += [pathway_id] * len(family_codes)
                    families += [family] * len(family_codes)
                    codes += family_codes
        schema = {"scenario_tag": pl.String, "family": pl.String, "code": pl.String}
        frame = pl.DataFrame(
            {"scenario_tag": tags, "family": families, "code": codes}, schema=schema
        )
        return frame.unique()


@lru_cache(maxsize=1)
def default_context() -> PlausibilityContext:
    """The context `check_plausibility` uses when it is given none (shared, so data load once)."""
    return PlausibilityContext()


# --- small expression helpers ------------------------------------------------------------------


def _date(name: str) -> pl.Expr:
    """An ISO date string column as a Date (null when it is missing or not an ISO date)."""
    return pl.col(name).str.to_date(_DATE_FORMAT, strict=False)


def _format(template: str, *args: pl.Expr) -> pl.Expr:
    """`pl.format`, writing `(none)` for a missing value: `pl.format` makes the whole text null."""
    return pl.format(template, *[arg.cast(pl.String).fill_null("(none)") for arg in args])


def _where(claim: str, kind: str, key: str) -> pl.Expr:
    """`where` of a finding about one line: the claim id, then `kind[key]`."""
    return _format("{} {}[{}]", pl.col(claim), pl.lit(kind), pl.col(key))


def _other_than(sex: str | pl.Expr) -> pl.Expr:
    """The patient's sex (column `sex`) is not `sex`; a patient of unknown sex is not either."""
    return (pl.col("sex") != sex).fill_null(True)


def _days_text(column: str = "day") -> pl.Expr:
    """In an aggregation: the Dates of the group as one sorted text, `2026-03-13, 2026-03-14`."""
    return pl.col(column).sort().cast(pl.String).str.join(", ")


def _problems(check: str, found: pl.DataFrame) -> list[Problem]:
    """Problems for findings with the columns `where` and `message`, in a stable order."""
    ordered = found.select(pl.col("where").fill_null("(no-claim-id)"), "message").sort(
        "where", "message"
    )
    return [
        Problem(check, where, message)
        for where, message in zip(ordered["where"], ordered["message"], strict=True)
    ]


def _as_of(
    frame: pl.DataFrame,
    history: pl.DataFrame,
    take: Mapping[str, str],
    *,
    code: str,
    day: str,
) -> pl.DataFrame:
    """Add the `take` columns (history name -> new name) of the history row in force on `day`."""
    in_force = (pl.col("valid_from") <= pl.col(day)) & (
        pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col(day))
    )
    hit = (
        frame.select("_n", code, day)
        .join(
            history.select("code", "valid_from", "valid_to", *take), left_on=code, right_on="code"
        )
        .filter(in_force)
        .unique(subset="_n", keep="first", maintain_order=True)
        .select("_n", *[pl.col(old).alias(new) for old, new in take.items()])
    )
    return frame.join(hit, on="_n", how="left")


# --- the tables of one run ---------------------------------------------------------------------


class _Bill:
    """The tables of one run and the frames several checks share, each built on first use."""

    def __init__(
        self,
        tables: Mapping[str, pl.DataFrame],
        clean_tables: Mapping[str, pl.DataFrame],
        ctx: PlausibilityContext,
    ) -> None:
        self.tables = tables
        self.clean_tables = clean_tables
        self.ctx = ctx

    def table(self, name: str) -> pl.DataFrame:
        """A claims table, or (the `*_clean.parquet` files) a clean table, by file name."""
        source = self.clean_tables if name.endswith("_clean.parquet") else self.tables
        if name not in source:
            raise PlausibilityError(f"table {name} is missing; the checks read it")
        return source[name]

    @cached_property
    def lines(self) -> pl.DataFrame:
        """Procedure lines: the flags of what a line is, and the surgical group of an operation."""
        ctx = self.ctx
        frame = (
            self.table(TABLE_PROCEDURES)
            .select(
                "claim_id",
                "patient_id",
                "episode_id",
                "procedure_line_id",
                "procedure_date",
                "procedure_code",
                "procedure_name",
                "procedure_category",
                "quantity",
                "procedure_specialty_code",
            )  # fmt: skip
            .with_row_index("_n")
        )
        code = pl.col("procedure_code")
        frame = frame.with_columns(
            [
                flag.fill_null(False).alias(name)
                for name, flag in {
                    "is_icu": code.is_in(ctx.icu_codes),
                    "is_paket": pl.col("procedure_category") == "paket",
                    "is_bed_day": code.is_in(ctx.bed_day_codes),
                    "is_companion": code == ctx.companion_code,
                    "is_anaesthesia": code.is_in(ctx.anaesthesia_codes),
                    "is_chapter6": code.is_in(ctx.operation_codes),
                    "is_pcode": code.str.starts_with("P"),
                }.items()
            ]
        )
        frame = _as_of(
            frame, ctx.catalogs.ek2b, {"puan": "puan"}, code="procedure_code", day="procedure_date"
        )
        packages = ctx.catalogs.ek2c.rename({"group": "pkg_group"})
        frame = _as_of(
            frame, packages, {"pkg_group": "pkg_group"}, code="procedure_code", day="procedure_date"
        )
        surgical_package = (
            pl.col("is_pcode") & ~pl.col("is_icu") & (pl.col("pkg_group").fill_null("") != "")
        )
        group = (
            pl.when(pl.col("is_chapter6"))
            .then(ctx.band_group(pl.col("procedure_date"), pl.col("puan")))
            .when(surgical_package)
            .then(pl.col("pkg_group"))
        )
        return frame.with_columns(
            (pl.col("is_chapter6") | surgical_package).alias("is_operation"),
            group.alias("surgical_group"),
            (pl.col("is_paket") & ~pl.col("is_icu")).alias("is_package_line"),
        )

    @cached_property
    def headers(self) -> pl.DataFrame:
        """Headers with parsed dates and `package_lines`, the count of their package lines."""
        counts = (
            self.lines.group_by("claim_id")
            .agg(pl.col("is_package_line").sum().alias("package_lines"))
            .select("claim_id", pl.col("package_lines").cast(pl.Int64))
        )
        return (
            self.table(TABLE_CLAIM_HEADERS)
            .select(
                "claim_id",
                "patient_id",
                "episode_id",
                "claim_type",
                "package_candidate",
                "scenario_tag",
                "admission_date",
                "discharge_date",
                _date("admission_date").alias("adm"),
                _date("discharge_date").alias("dis"),
                _date("claim_start_date").alias("start"),
                _date("claim_end_date").alias("end"),
            )  # fmt: skip
            .join(counts, on="claim_id", how="left")
            .with_columns(pl.col("package_lines").fill_null(0))
            .with_columns((pl.col("package_lines") > 0).alias("is_package_claim"))
        )

    @cached_property
    def diagnoses(self) -> pl.DataFrame:
        return self.table(TABLE_DIAGNOSES).select(
            "claim_id", "patient_id", "episode_id", "diagnosis_id", "icd10_code", "diagnosis_date"
        )

    @cached_property
    def patients(self) -> pl.DataFrame:
        """patient_id, episode_id, sex (M, F or null) and age (TANI_YASI) from anadata_clean."""
        sex = pl.col("CINSIYET")
        return (
            self.table(TABLE_ANADATA)
            .select(
                pl.col("HASTA_ID").alias("patient_id"),
                pl.col("SQ_EPISODE").alias("episode_id"),
                pl.when(sex == "E")
                .then(pl.lit("M"))
                .when(sex == "K")
                .then(pl.lit("F"))
                .alias("sex"),
                pl.col("TANI_YASI").alias("age"),
            )
            .unique(subset=["patient_id", "episode_id"], keep="first", maintain_order=True)
        )

    @cached_property
    def named_lines(self) -> pl.DataFrame:
        """Procedure lines with the patient's sex and age and the folded name without exceptions."""
        return self.lines.join(
            self.patients, on=["patient_id", "episode_id"], how="left"
        ).with_columns(_without_exceptions(_fold(pl.col("procedure_name"))).alias("folded_name"))


# --- patient -----------------------------------------------------------------------------------


def check_icd_valid(bill: _Bill) -> list[Problem]:
    """patient.icd_valid: each diagnosis exists, is active, is a leaf, is created and not passive."""
    joined = bill.diagnoses.join(bill.ctx.icd, left_on="icd10_code", right_on="code", how="left")
    known = pl.col("known").fill_null(False)
    day = _date("diagnosis_date")
    reasons = pl.concat_str(
        pl.when(~known).then(pl.lit("is not in icd10_tr")),
        pl.when(known & ~pl.col("is_active").fill_null(False)).then(pl.lit("is inactive")),
        pl.when(known & ~pl.col("is_leaf").fill_null(False)).then(pl.lit("is not a leaf code")),
        pl.when(known & (pl.col("created_on") > day)).then(
            _format("was created on {}, after the diagnosis date", pl.col("created_on"))
        ),
        pl.when(known & (pl.col("passive_on") <= day)).then(
            _format("has been passive since {}", pl.col("passive_on"))
        ),
        separator=", ",
        ignore_nulls=True,
    )
    found = (
        joined.with_columns(reasons.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _where("claim_id", "claim_diagnoses", "diagnosis_id").alias("where"),
            _format(
                "diagnosis {} dated {}: the code {}",
                pl.col("icd10_code"),
                pl.col("diagnosis_date"),
                pl.col("why"),
            ).alias("message"),
        )
    )
    return _problems("patient.icd_valid", found)


def check_sex_gate(bill: _Bill) -> list[Problem]:
    """patient.sex_gate: an ICD sex gate, or a sex word in a procedure name, against the sex."""
    gated = (
        bill.diagnoses.join(bill.patients, on=["patient_id", "episode_id"], how="left")
        .join(
            bill.ctx.icd.select("code", pl.col("sex").alias("icd_sex")),
            left_on="icd10_code",
            right_on="code",
            how="left",
        )
        .filter(pl.col("icd_sex").is_not_null() & _other_than(pl.col("icd_sex")))
        .select(
            _where("claim_id", "claim_diagnoses", "diagnosis_id").alias("where"),
            _format(
                "diagnosis {} is limited to sex {} but the patient is {}",
                pl.col("icd10_code"),
                pl.col("icd_sex"),
                pl.col("sex").fill_null("of unknown sex"),
            ).alias("message"),
        )
    )
    name = pl.col("folded_name")
    named = bill.named_lines.with_columns(
        name.str.contains(_MALE_PATTERN).alias("male_word"),
        name.str.contains(_FEMALE_PATTERN).alias("female_word"),
    )
    male_name = named.filter(pl.col("male_word") & _other_than("M")).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "procedure {} ({}) is a male-only word ({}) but the patient is {}",
            pl.col("procedure_code"),
            pl.col("procedure_name"),
            pl.col("folded_name").str.extract(_MALE_PATTERN, 0),
            pl.col("sex").fill_null("of unknown sex"),
        ).alias("message"),
    )
    female_name = named.filter(pl.col("female_word") & _other_than("F")).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "procedure {} ({}) is a female-only word ({}) but the patient is {}",
            pl.col("procedure_code"),
            pl.col("procedure_name"),
            pl.col("folded_name").str.extract(_FEMALE_PATTERN, 0),
            pl.col("sex").fill_null("of unknown sex"),
        ).alias("message"),
    )
    return _problems("patient.sex_gate", pl.concat([gated, male_name, female_name]))


def check_age_gate(bill: _Bill) -> list[Problem]:
    """patient.age_gate: the AGE_GATES table, for diagnosis codes and procedure names."""
    diagnoses = bill.diagnoses.join(bill.patients, on=["patient_id", "episode_id"], how="left")
    lines = bill.named_lines
    found = []
    for gate in AGE_GATES:
        if gate.source == "icd":
            source = diagnoses
            prefix = pl.col("icd10_code").str.contains(
                "^(?:" + "|".join(map(re.escape, gate.words)) + ")"
            )
            hit, subject = prefix, pl.col("icd10_code")
            where = _where("claim_id", "claim_diagnoses", "diagnosis_id")
        else:
            source = lines
            pattern = _words_pattern(gate.words)
            hit, subject = pl.col("folded_name").str.contains(pattern), pl.col("procedure_name")
            where = _where("claim_id", "procedure_claim_lines", "procedure_line_id")
        too_young = pl.col("age") < gate.min_age if gate.min_age is not None else pl.lit(False)
        too_old = pl.col("age") > gate.max_age if gate.max_age is not None else pl.lit(False)
        wrong_sex = _other_than(gate.sex) if gate.sex is not None else pl.lit(False)
        found.append(
            source.filter(
                hit & (too_young.fill_null(False) | too_old.fill_null(False) | wrong_sex)
            ).select(
                where.alias("where"),
                _format(
                    "{} is {} and needs {}; the patient is {} aged {}",
                    subject,
                    pl.lit(gate.why),
                    pl.lit(gate.limits),
                    pl.col("sex").fill_null("of unknown sex"),
                    pl.col("age").cast(pl.String).fill_null("unknown"),
                ).alias("message"),
            )
        )
    return _problems("patient.age_gate", pl.concat(found))


def check_age_arithmetic(bill: _Bill) -> list[Problem]:
    """patient.age_arithmetic: TANI_YASI = year of claim_start_date - birth_year."""
    profiles = bill.table(TABLE_COPAY).select("patient_id", "birth_year")
    joined = (
        bill.headers.join(profiles, on="patient_id", how="left")
        .join(bill.patients, on=["patient_id", "episode_id"], how="left")
        .with_columns((pl.col("start").dt.year() - pl.col("birth_year")).alias("expected_age"))
    )
    found = joined.filter(~(pl.col("age") == pl.col("expected_age")).fill_null(False)).select(
        pl.col("claim_id").alias("where"),
        _format(
            "TANI_YASI is {}; the claim year is {} and the birth year {}, which makes the age {}",
            pl.col("age").cast(pl.String).fill_null("missing"),
            pl.col("start").dt.year().cast(pl.String).fill_null("unknown"),
            pl.col("birth_year").cast(pl.String).fill_null("missing"),
            pl.col("expected_age").cast(pl.String).fill_null("unknown"),
        ).alias("message"),
    )
    return _problems("patient.age_arithmetic", found)


# --- fit ---------------------------------------------------------------------------------------


def check_pathway_membership(bill: _Bill) -> list[Problem]:
    """fit.pathway_membership: every code is in the expansion of the claim's pathway or sibling."""
    ctx = bill.ctx
    tags = bill.headers.select("claim_id", "scenario_tag")
    sources = [
        (bill.table(TABLE_PROCEDURES), "procedure", "procedure_code", "procedure_claim_lines"),
        (bill.table(TABLE_MATERIALS), "material", "material_code", "material_claim_lines"),
        (bill.table(TABLE_DRUGS), "drug", "barkod", "drug_claim_lines"),
        (bill.diagnoses, "diagnosis", "icd10_code", "claim_diagnoses"),
    ]
    held = pl.concat(
        [
            frame.select(
                "claim_id",
                pl.lit(family).alias("family"),
                pl.lit(table).alias("table"),
                pl.col(column).alias("code"),
            )
            for frame, family, column, table in sources
        ]
    ).join(tags, on="claim_id", how="left")
    pathway_ids = list(ctx.pathways)
    unknown = tags.filter(~pl.col("scenario_tag").is_in(pathway_ids).fill_null(False)).select(
        pl.col("claim_id").alias("where"),
        _format(
            "scenario_tag {} is not a care pathway of data/synthetic/pathways",
            pl.col("scenario_tag").fill_null("(missing)"),
        ).alias("message"),
    )
    extra = (
        held.filter(pl.col("scenario_tag").is_in(pathway_ids).fill_null(False))
        .join(ctx.vocabulary, on=["scenario_tag", "family", "code"], how="anti")
        .group_by("claim_id", "scenario_tag", "family", "table")
        .agg(pl.col("code").unique().sort().str.join(", ").alias("codes"))
        .select(
            _format("{} {}", pl.col("claim_id"), pl.col("table")).alias("where"),
            _format(
                "{} code(s) {} are not in the expansion of {} or of a sibling that a fault swaps in",
                pl.col("family"),
                pl.col("codes"),
                pl.col("scenario_tag"),
            ).alias("message"),
        )
    )
    return _problems("fit.pathway_membership", pl.concat([unknown, extra]))


def check_operation_department(bill: _Bill) -> list[Problem]:
    """fit.operation_department: an operation line carries a surgical EK-2A branch."""
    surgical = pl.col("procedure_specialty_code").is_in(sorted(SURGICAL_SPECIALTY_CODES))
    found = bill.lines.filter(pl.col("is_operation") & ~surgical.fill_null(False)).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "operation {} ({}) has the specialty {}, which is not a surgical EK-2A branch",
            pl.col("procedure_code"),
            pl.col("procedure_name"),
            pl.col("procedure_specialty_code"),
        ).alias("message"),
    )
    return _problems("fit.operation_department", found)


def check_operation_setting(bill: _Bill) -> list[Problem]:
    """fit.operation_setting: no major operation on a poliklinik or acil claim."""
    found = (
        bill.lines.join(bill.headers.select("claim_id", "claim_type"), on="claim_id", how="left")
        .filter(
            pl.col("is_operation")
            & pl.col("surgical_group").is_in(MAJOR_GROUPS)
            & pl.col("claim_type").is_in(["poliklinik", "acil"])
        )
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "major operation {} ({}, group {}) on a claim of type {}",
                pl.col("procedure_code"),
                pl.col("procedure_name"),
                pl.col("surgical_group"),
                pl.col("claim_type"),
            ).alias("message"),
        )
    )
    return _problems("fit.operation_setting", found)


def check_visit_code(bill: _Bill) -> list[Problem]:
    """fit.visit_code: an examination line bills the visit code of its claim type."""
    found = (
        bill.lines.filter(pl.col("procedure_category") == "muayene")
        .join(bill.headers.select("claim_id", "claim_type"), on="claim_id", how="left")
        .join(bill.ctx.visit_codes, on="claim_type", how="left")
        .filter(
            pl.col("visit_code").is_not_null() & (pl.col("procedure_code") != pl.col("visit_code"))
        )
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "examination {} on a claim of type {}; {} is the examination of that type",
                pl.col("procedure_code"),
                pl.col("claim_type"),
                pl.col("visit_code"),
            ).alias("message"),
        )
    )
    return _problems("fit.visit_code", found)


# --- stay --------------------------------------------------------------------------------------


def check_bed_coverage(bill: _Bill) -> list[Problem]:
    """stay.bed_coverage: one bed line of quantity 1 on every day admission..discharge, none else."""
    stays = bill.headers.filter(
        (pl.col("claim_type") == "yatis")
        & ~pl.col("is_package_claim")
        & pl.col("adm").is_not_null()
        & pl.col("dis").is_not_null()
    ).select("claim_id", "adm", "dis")
    days = (
        stays.with_columns(pl.date_ranges("adm", "dis").alias("day"))
        .explode("day")
        .filter(pl.col("day").is_not_null())
        .select("claim_id", "day")
    )
    beds = (
        bill.lines.filter(pl.col("is_bed_day"))
        .join(stays.select("claim_id"), on="claim_id", how="semi")
        .with_columns(_date("procedure_date").alias("day"))
    )
    per_day = beds.group_by("claim_id", "day").agg(pl.len().alias("n"))
    stay_days = days.group_by("claim_id").agg(pl.len().alias("stay_days"))

    missing = (
        days.join(per_day, on=["claim_id", "day"], how="anti")
        .group_by("claim_id")
        .agg(_days_text().alias("days"), pl.len().alias("count"))
        .join(stay_days, on="claim_id")
        .select(
            pl.col("claim_id").alias("where"),
            _format(
                "no bed line on {} of {} day(s): {}",
                pl.col("count"),
                pl.col("stay_days"),
                pl.col("days"),
            ).alias("message"),
        )
    )
    twice = (
        per_day.filter(pl.col("n") > 1)
        .group_by("claim_id")
        .agg(_days_text().alias("days"))
        .select(
            pl.col("claim_id").alias("where"),
            _format("more than one bed line on: {}", pl.col("days")).alias("message"),
        )
    )
    quantity = beds.filter(pl.col("quantity") != 1).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "bed line {} has the quantity {}; a bed line is one day",
            pl.col("procedure_code"),
            pl.col("quantity"),
        ).alias("message"),
    )
    outside = (
        beds.join(days, on=["claim_id", "day"], how="anti")
        .group_by("claim_id")
        .agg(pl.col("procedure_date").sort().str.join(", ").alias("dates"))
        .select(
            pl.col("claim_id").alias("where"),
            _format("bed line(s) outside admission..discharge: {}", pl.col("dates")).alias(
                "message"
            ),
        )
    )
    return _problems("stay.bed_coverage", pl.concat([missing, twice, quantity, outside]))


def check_companion_coverage(bill: _Bill) -> list[Problem]:
    """stay.companion_coverage: quantity 1, one per day, on admission..discharge-1."""
    companions = (
        bill.lines.filter(pl.col("is_companion"))
        .join(bill.headers.select("claim_id", "adm", "dis"), on="claim_id", how="left")
        .with_columns(_date("procedure_date").alias("day"))
    )
    per_day = companions.group_by("claim_id", "day").agg(pl.len().alias("n"))
    quantity = companions.filter(pl.col("quantity") != 1).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format("companion line has the quantity {}", pl.col("quantity")).alias("message"),
    )
    twice = (
        per_day.filter(pl.col("n") > 1)
        .group_by("claim_id")
        .agg(_days_text().alias("days"))
        .select(
            pl.col("claim_id").alias("where"),
            _format("more than one companion line on: {}", pl.col("days")).alias("message"),
        )
    )
    last_night = pl.col("dis").dt.offset_by("-1d")
    inside = (
        pl.col("day").is_not_null()
        & pl.col("adm").is_not_null()
        & pl.col("dis").is_not_null()
        & (pl.col("day") >= pl.col("adm"))
        & (pl.col("day") <= last_night)
    )
    outside = companions.filter(~inside).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "companion line dated {} is outside the nights {}..{} of the stay",
            pl.col("procedure_date"),
            pl.col("adm").cast(pl.String).fill_null("(no admission)"),
            last_night.cast(pl.String).fill_null("(no discharge)"),
        ).alias("message"),
    )
    return _problems("stay.companion_coverage", pl.concat([quantity, twice, outside]))


def check_dates_in_window(bill: _Bill) -> list[Problem]:
    """stay.dates_in_window: the header fits the claim type; every line date is in the window."""
    h = bill.headers
    yatis = pl.col("claim_type") == "yatis"
    starts_on_admission = pl.col("start") == pl.col("adm")
    ends_on_discharge = pl.col("end") == pl.col("dis")
    ward_window = (starts_on_admission & ends_on_discharge).fill_null(False)
    visit_window = (
        (pl.col("start") == pl.col("end"))
        & pl.col("admission_date").is_null()
        & pl.col("discharge_date").is_null()
    ).fill_null(False)
    header = h.filter(
        (yatis & ~ward_window)
        | (pl.col("claim_type").is_in(["acil", "poliklinik"]) & ~visit_window)
    ).select(
        pl.col("claim_id").alias("where"),
        _format(
            "claim of type {} {}: admission {}, discharge {}, start {}, end {}",
            pl.col("claim_type"),
            pl.when(yatis)
            .then(pl.lit("starts on admission and ends on discharge"))
            .otherwise(pl.lit("is one day, with no admission and no discharge")),
            pl.col("admission_date").fill_null("none"),
            pl.col("discharge_date").fill_null("none"),
            pl.col("start").cast(pl.String).fill_null("none"),
            pl.col("end").cast(pl.String).fill_null("none"),
        ).alias("message"),
    )
    sources = [
        (
            bill.table(TABLE_PROCEDURES),
            "procedure_claim_lines",
            "procedure_line_id",
            "procedure_date",
        ),
        (bill.table(TABLE_MATERIALS), "material_claim_lines", "material_line_id", "material_date"),
        (bill.table(TABLE_DRUGS), "drug_claim_lines", "drug_claim_line_id", "drug_claim_date"),
        (bill.diagnoses, "claim_diagnoses", "diagnosis_id", "diagnosis_date"),
        (
            bill.table(TABLE_PERFORMED),
            "performed_procedure_lines",
            "performed_line_id",
            "service_date",
        ),
    ]
    window = h.select("claim_id", "start", "end")
    dated = pl.concat(
        [
            frame.select(
                "claim_id",
                pl.lit(table).alias("table"),
                pl.col(key).alias("key"),
                pl.col(day).alias("raw_day"),
                _date(day).alias("day"),
            )
            for frame, table, key, day in sources
        ]
    ).join(window, on="claim_id", how="left")
    inside = (
        pl.col("day").is_not_null()
        & pl.col("start").is_not_null()
        & pl.col("end").is_not_null()
        & (pl.col("day") >= pl.col("start"))
        & (pl.col("day") <= pl.col("end"))
    )
    lines = (
        dated.filter(~inside)
        .group_by("claim_id", "table")
        .agg(
            pl.len().alias("count"),
            pl.col("raw_day").fill_null("(missing)").unique().sort().str.join(", ").alias("dates"),
            pl.col("start").first(),
            pl.col("end").first(),
        )
        .select(
            _format("{} {}", pl.col("claim_id"), pl.col("table")).alias("where"),
            _format(
                "{} line(s) dated outside the claim window {}..{}: {}",
                pl.col("count"),
                pl.col("start").cast(pl.String).fill_null("(no header)"),
                pl.col("end").cast(pl.String).fill_null("(no header)"),
                pl.col("dates"),
            ).alias("message"),
        )
    )
    return _problems("stay.dates_in_window", pl.concat([header, lines]))


# --- bill, package ------------------------------------------------------------------------------


def check_performed_billed(bill: _Bill) -> list[Problem]:
    """bill.performed_billed: each performed procedure has a billed line, same code, same day."""
    billed = bill.lines.select(
        "claim_id", "procedure_code", pl.col("procedure_date").alias("service_date")
    )
    found = (
        bill.table(TABLE_PERFORMED)
        .join(billed, on=["claim_id", "procedure_code", "service_date"], how="anti")
        .select(
            _where("claim_id", "performed_procedure_lines", "performed_line_id").alias("where"),
            _format(
                "performed {} ({}) on {} has no billed procedure line",
                pl.col("procedure_code"),
                pl.col("procedure_name"),
                pl.col("service_date"),
            ).alias("message"),
        )
    )
    return _problems("bill.performed_billed", found)


def check_package_mode(bill: _Bill) -> list[Problem]:
    """package.mode: package_candidate = has a package line; a package claim: no bed, no anaesthesia."""
    mismatch = bill.headers.filter(
        (pl.col("package_candidate") != pl.col("is_package_claim")).fill_null(True)
    ).select(
        pl.col("claim_id").alias("where"),
        _format(
            "package_candidate is {} but the claim has {} package line(s)",
            pl.col("package_candidate").cast(pl.String).fill_null("missing"),
            pl.col("package_lines"),
        ).alias("message"),
    )
    on_package = bill.lines.join(
        bill.headers.filter(pl.col("is_package_claim")).select("claim_id"),
        on="claim_id",
        how="semi",
    )
    beds = on_package.filter(pl.col("procedure_category") == "yatak").select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "bed line {} on a package claim; the beds are inside the package",
            pl.col("procedure_code"),
        ).alias("message"),
    )
    anaesthesia = on_package.filter(pl.col("is_anaesthesia")).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "anaesthesia line {} on a package claim; the anaesthesia is inside the package",
            pl.col("procedure_code"),
        ).alias("message"),
    )
    return _problems("package.mode", pl.concat([mismatch, beds, anaesthesia]))


# --- anaesthesia -------------------------------------------------------------------------------


def _itemised_days(bill: _Bill) -> pl.DataFrame:
    """Per claim and day of an itemised claim: operations and anaesthesia lines, with puan."""
    itemised = bill.headers.filter(~pl.col("is_package_claim")).select("claim_id")
    lines = bill.lines.join(itemised, on="claim_id", how="semi")
    return lines.group_by("claim_id", "procedure_date").agg(
        pl.col("is_operation").sum().cast(pl.Int64).alias("operations"),
        pl.col("is_anaesthesia").sum().cast(pl.Int64).alias("anaesthesia"),
        pl.col("puan").filter(pl.col("is_operation")).sum().alias("total_puan"),
        pl.col("puan").filter(pl.col("is_operation")).count().cast(pl.Int64).alias("priced"),
    )


def check_operation_pairing(bill: _Bill) -> list[Problem]:
    """anaesthesia.operation_pairing: an operation day has one anaesthesia line; no orphan; none on a package."""
    days = _itemised_days(bill)
    wrong = days.filter(
        ((pl.col("operations") > 0) & (pl.col("anaesthesia") != 1))
        | ((pl.col("operations") == 0) & (pl.col("anaesthesia") > 0))
    ).select(
        _format("{} day[{}]", pl.col("claim_id"), pl.col("procedure_date")).alias("where"),
        _format(
            "{} operation line(s) and {} anaesthesia line(s); one anaesthesia line per operation day, none else",
            pl.col("operations"),
            pl.col("anaesthesia"),
        ).alias("message"),
    )
    on_package = (
        bill.lines.filter(pl.col("is_anaesthesia"))
        .join(
            bill.headers.filter(pl.col("is_package_claim")).select("claim_id"),
            on="claim_id",
            how="semi",
        )
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "anaesthesia line {} on a package claim; a package has none",
                pl.col("procedure_code"),
            ).alias("message"),
        )
    )
    return _problems("anaesthesia.operation_pairing", pl.concat([wrong, on_package]))


def check_anaesthesia_group(bill: _Bill) -> list[Problem]:
    """anaesthesia.group: the anaesthesia code is the one of the puan band of the day's operations."""
    ctx = bill.ctx
    days = _itemised_days(bill).filter(
        (pl.col("operations") > 0) & (pl.col("priced") == pl.col("operations"))
    )
    expected = (
        days.with_columns(
            ctx.band_group(pl.col("procedure_date"), pl.col("total_puan")).alias("group")
        )
        .join(ctx.anaesthesia_by_group, on="group", how="left")
        .select(
            "claim_id",
            "procedure_date",
            "operations",
            "total_puan",
            "group",
            pl.when(pl.col("operations") == 1)
            .then(pl.col("single"))
            .otherwise(pl.col("multiple"))
            .alias("expected_code"),
        )
    )
    found = (
        bill.lines.filter(pl.col("is_anaesthesia"))
        .join(expected, on=["claim_id", "procedure_date"])
        .filter(
            pl.col("expected_code").is_not_null()
            & (pl.col("procedure_code") != pl.col("expected_code"))
        )
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "anaesthesia {} on {}: {} operation(s) with puan {} are group {}, which is {}",
                pl.col("procedure_code"),
                pl.col("procedure_date"),
                pl.col("operations"),
                pl.col("total_puan").round(2),
                pl.col("group"),
                pl.col("expected_code"),
            ).alias("message"),
        )
    )
    return _problems("anaesthesia.group", found)


# --- the registry and the entry point ------------------------------------------------------------

CHECK_FUNCTIONS: dict[str, Callable[[_Bill], list[Problem]]] = {
    "patient.icd_valid": check_icd_valid,
    "patient.sex_gate": check_sex_gate,
    "patient.age_gate": check_age_gate,
    "patient.age_arithmetic": check_age_arithmetic,
    "fit.pathway_membership": check_pathway_membership,
    "fit.operation_department": check_operation_department,
    "fit.operation_setting": check_operation_setting,
    "fit.visit_code": check_visit_code,
    "stay.bed_coverage": check_bed_coverage,
    "stay.companion_coverage": check_companion_coverage,
    "stay.dates_in_window": check_dates_in_window,
    "bill.performed_billed": check_performed_billed,
    "package.mode": check_package_mode,
    "anaesthesia.operation_pairing": check_operation_pairing,
    "anaesthesia.group": check_anaesthesia_group,
}


def check_plausibility(
    tables: Mapping[str, pl.DataFrame],
    clean_tables: Mapping[str, pl.DataFrame],
    *,
    context: PlausibilityContext | None = None,
    only: Iterable[str] | str | None = None,
) -> list[Problem]:
    """Every plausibility problem of the claims `tables` (and `anadata_clean` of `clean_tables`).

    `only` restricts the run to some check ids. The problems come in the order of `CHECKS`, then
    by `where`.
    """
    if only is None:
        selected = list(CHECKS)
    else:
        wanted = {only} if isinstance(only, str) else set(only)
        unknown = sorted(wanted - set(CHECKS))
        if unknown:
            raise KeyError(f"unregistered check id(s) {unknown}")
        selected = [check for check in CHECKS if check in wanted]
    bill = _Bill(tables, clean_tables, context if context is not None else default_context())
    return [problem for check in selected for problem in CHECK_FUNCTIONS[check](bill)]


run_all = check_plausibility
