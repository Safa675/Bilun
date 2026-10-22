"""Plausibility checks for the generated showcase bills (plan D5, slices E1 and E2).

The checks read the nine claims tables and the clean `anadata_clean` table of one dataset and report
what an auditor would call implausible: a diagnosis that cannot exist on its day or for this patient,
codes that do not belong to the claim's care pathway, a stay without a bed for every day, a
performed procedure that was never billed, a package claim that carries a bed, an operation without
its anaesthesia (slice E1); a material that hangs on no operation or carries a stray compliance
flag, a unit price that is not the price in force on the day, a bill that does not add up, answer
rows and fault records that contradict the bill (slice E2).

`check_plausibility(tables, clean_tables)` is a pure function of the tables it is given: it knows no
fault. It has one small function per check id (`CHECK_FUNCTIONS`) and runs all of them, or only
the ids of `only`. `CHECKS` is the stable registry of ids; a test requires a mutation case for each
id. Slice E3 (clinical content of the clean tables) adds ids to the same registry: put the id and
its meaning in `CHECKS`, write `check_<name>(bill) -> list[Problem]`, list it in `CHECK_FUNCTIONS`,
and add a mutation `Case` (and, for a defect that shows on a committed faulty bill, the pinned row)
to the test file.

The two `labels.*` ids compare the bill with the fault records of the dataset's registry
(`cohort_registry.json`, parsed): they run only when `check_plausibility` is given `registry=`.

`Problem.where` starts with the claim id (then `table[line id]` or a detail, after a space): a
finding about one line names the line, and a row with no claim id starts with `(no-claim-id)`, in
every check. The only findings that belong to no claim are two of `labels.answer_rows`, about the
registry as a whole and the columns of the answer table: they start with `(registry)` or
`(expected_rule_outputs)`. The findings of one check come sorted by `where`, then `message`.

The reference data (EK-2B/EK-2C history, chapters, ICD-10, code sets, the care pathways and their
fault siblings, the EK-3/F-1 and EK-4A lists) are read once, lazily, by a `PlausibilityContext`.

INDEPENDENCE: the price checks know nothing of the generator. They never use `CohortCatalogs` or a
helper the generator uses: EK-2B and EK-2C prices come from the engine's as-of lookups
(`src/bilun/domain/pricing/temporal.py`), EK-3/F-1 and EK-4A from direct Polars reads of the curated
files.

Everything is vectorised Polars. A `Problem` is built only from the finished findings. Python
loops walk small lists, never the rows of a table: the distinct (code, day) pairs of the procedure
lines (the engine's lookup is scalar, so it is asked once for each pair and the answer is joined
back), and the entries of the registry's list of fault records.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import cached_property, lru_cache
from pathlib import Path
import re
from typing import Any

import polars as pl
from pydantic import ValidationError

from scripts.synthetic.faults import (
    EXPECTED_OUTPUT_COLUMNS,
    FaultInjectionRecord,
    FaultRegistry,
    build_expected_rule_outputs,
    load_registry,
    load_siblings,
)
from scripts.synthetic.faults.schema import UseSiblingPathway
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.checks import Catalogs, _group_expr
from scripts.synthetic.pathways.expand import expand
from scripts.synthetic.pathways.schema import Pins, Problem as _PathwayProblem

REPO = Path(__file__).resolve().parents[3]

TABLE_CLAIM_HEADERS = "claim_headers.parquet"
TABLE_DIAGNOSES = "claim_diagnoses.parquet"
TABLE_PROCEDURES = "procedure_claim_lines.parquet"
TABLE_MATERIALS = "material_claim_lines.parquet"
TABLE_DRUGS = "drug_claim_lines.parquet"
TABLE_PERFORMED = "performed_procedure_lines.parquet"
TABLE_COPAY = "patient_copay_profiles.parquet"
TABLE_ANSWERS = "expected_rule_outputs.parquet"
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
    "stay.bed_coverage": "one bed line a day, admission..discharge (ICU: ..discharge-1; none on the day an ICU bill ends); no day bed on a stay",
    "stay.companion_coverage": "a companion line of quantity not 1, twice on a day, or outside admission..discharge-1",
    "stay.dates_in_window": "a header whose dates contradict the claim type, or a line date outside the claim window",
    # bill: performed against billed
    "bill.performed_billed": "a performed procedure with no billed line of the same code on the same day",
    # package: the billing mode
    "package.mode": "package_candidate that disagrees with the package lines, or a package claim with a bed or anaesthesia line",
    # anaesthesia: one per operation date, in the right group
    "anaesthesia.operation_pairing": "an operation date without exactly one anaesthesia line, or an anaesthesia line without an operation",
    "anaesthesia.group": "an anaesthesia code that is not the code of the puan band of the day's operations",
    # material: the material lines against their operation and the compliance flags
    "material.operation_link": "a material line not linked to an operation of its own claim, or not dated on that operation's day",
    "material.stray_flag": "a material compliance flag off its healthy value (registration flags true, every other flag false)",
    # price: unit prices against the lists in force on the day of the line
    "price.procedure_in_force": "a procedure line whose unit price is not the engine's EK-2B or EK-2C price in force on its day",
    "price.material_in_force": "a material line that is not in the EK-3/F-1 list, is dated before the list, or is not at its price",
    "price.drug_in_force": "a drug line whose barcode has no EK-4A row in force on its day (drug prices are not checked)",
    # money: the arithmetic of the bill
    "money.line_arithmetic": "a line whose billed amount is not unit price x quantity x 1, 0.5 or 0.25, to the cent",
    "money.payable_equals_billed": "a line whose expected payable is not its billed amount, or on a copay-flagged line not billed x (1 - copay_rate)",
    "money.totals": "a claim header whose billed or payable total is not the sum of its procedure, material and drug lines",
    # labels: the answer key and the fault records against the bill (they need the registry)
    "labels.answer_rows": "answer rows that differ from the ones the registry's fault records produce (needs the registry)",
    "labels.amounts": "a fault record whose totals, target line or amount contradict the bill (needs the registry)",
}

# The ids that compare the bill with the registry's fault records: skipped when there is no registry.
REGISTRY_CHECKS: frozenset[str] = frozenset({"labels.answer_rows", "labels.amounts"})

# --- judgment tables -------------------------------------------------------------------------
# These are decisions of the author, not facts of the SUT. They are a starting point: a word that
# trips a line of a clean twin must be narrowed or removed (and the change reported).

# patient.sex_gate: words of a procedure name that limit it to one sex. A word matches inside a word
# (prostat -> prostatektomi), written lower case or upper case, with or without Turkish letters, and
# several words may be one phrase (`tüp ligasyonu`). "orşi" alone is no word: it is inside torsiyon
# and dorsi. The review of 7,706 EK-2B and EK-2C names found no name that these lists get wrong,
# once the NAME_EXCEPTIONS below are blanked out. Four words match no catalog name today (the
# catalog spells it orşiyektomi; no name has rahim or salpenjektomi): they stay as a defence for a
# name outside the catalog, and the tests pin that list of four, so a catalog change cannot hide.
MALE_ONLY_WORDS: tuple[str, ...] = (
    "prostat", "penil", "penis", "penektomi", "testis", "orşiektomi", "orsiektomi", "skrotum",
    "hidrosel", "varikosel", "vazektomi", "sünnet", "sunnet", "epididim",
    "orşiyektomi", "orşiyopeksi", "fimoz", "hipospad", "epispad", "peyronie", "testik", "seminal",
    "sperm", "vazovazo", "ejakül",
)  # fmt: skip
FEMALE_ONLY_WORDS: tuple[str, ...] = (
    "uterus", "rahim", "histerektomi", "histeroskopi", "vajin", "vulva", "serviks", "ooferektomi",
    "salpenjektomi", "jinekolojik", "gebelik", "doğum", "sezaryen", "inseminasyon", "kürtaj",
    "histerosalping", "kolposkop", "bartholin", "obstetrik", "amniyo", "abortus", "endometri",
    "miyom", "myom", "plasenta", "tüp ligasyonu",
)  # fmt: skip
FEMALE_ONLY_WHOLE_WORDS: tuple[str, ...] = ("over",)  # not "overdoz", "recover"

# patient.sex_gate: ICD-10 blocks that only one sex can have, in addition to the `sex` column of
# icd10_tr (which gates 83 leaf codes, all in chapters C and D, and none in chapters E, I, N, Q, Z).
# A block is `first-last`, or one category or subcategory; a code is in it when its first characters
# (as many as the block's ends have) lie between the ends: `N41.0` is in `N40-N53`, `D07.5` in
# `D07.4-D07.6`. Source: the block structure of ICD-10 (WHO), which icd10_tr follows.
ICD_SEX_GATES: dict[str, tuple[str, ...]] = {
    "M": (
        "C60-C63",  # malignant neoplasms of male genital organs: penis, prostate, testis, other
        "D07.4-D07.6",  # carcinoma in situ of penis, prostate, other male genital organs
        "N40-N53",  # diseases of male genital organs: prostate, hydrocele, orchitis, phimosis, ...
        "E29",  # testicular dysfunction
        "Q53-Q56",  # congenital malformations of male genital organs: undescended testis, hypospadias, ...
        "I86.1",  # scrotal varices (varicocele)
    ),
    "F": (
        "C51-C58",  # malignant neoplasms of female genital organs: vulva, cervix, ovary, ...
        "D06",  # carcinoma in situ of cervix uteri
        "D07.0-D07.3",  # carcinoma in situ of endometrium, vulva, vagina, other female genital organs
        "N70-N98",  # inflammatory diseases and noninflammatory disorders of female genital organs
        "E28",  # ovarian dysfunction (polycystic ovary syndrome, ...)
        "Q50-Q52",  # congenital malformations of ovaries, tubes, uterus, vagina, vulva
        "Z32-Z37",  # pregnancy test, supervision of pregnancy, antenatal screening, outcome of delivery
        "Z39",  # postpartum care and examination
    ),
}

# Phrases that contain one of the sex or age words without the meaning (checked against the EK-2B and
# EK-2C names): they are blanked out of a name before its words are looked for. A test requires every
# phrase to occur in a catalog name and to change the verdict on at least one.
NAME_EXCEPTIONS: tuple[str, ...] = (
    "Yenidoğan/Çocuk/Erişkin",  # one code for every age
    "Yenidoğan/Çocuk",  # one code for newborn and child
    "Yeni doğan/geriatrik",  # the anaesthesia add-on for a newborn or an elderly patient
    "Çocuk-büyük",  # EEG for child and adult
    "Çocuk ve Genç",  # ÇÖZGEM, the child and youth mental-health centre: its patients may be 18
    "sağlam çocuk doğmasına",  # IVF and preimplantation tests: the patients are the parents
    "cross-over",  # a venous graft, not the ovary
    "Meme/Over Kanseri",  # BRCA analysis, also done for men
    "penisil",  # penicillin (Penisilin G IgE antikoru), penisilyum
    "doğumsal",  # congenital (heart disease), not birth
    "invajinasyon",  # intussusception of the bowel, not the vagina
    "hipospadias-epispadias dışı",  # a urethroplasty for any other cause, in either sex
    "Antisperm",  # the antibody test is also done on a woman's serum
    "Sperm yıkama",  # IUI/IVF steps are billed on either partner's file (judgment) ...
    "Sperm- oosit",  # ... as is the preparation of sperm and oocyte together
    "Özel sperm",  # ... and the special sperm technique
)


@dataclass(frozen=True)
class AgeGate:
    """One age rule: `words` are ICD code prefixes (source icd) or name words (source name).

    `whole` makes a name word match as a whole word only (`2 yaş altı` is not inside `12 yaş altı`).
    """

    source: str
    words: tuple[str, ...]
    min_age: int | None
    max_age: int | None
    sex: str | None
    why: str
    whole: bool = False

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


# patient.age_gate: the age is `anadata_clean` TANI_YASI; both limits are inclusive. No catalog name
# has the word `erişkin` today (the adult gate is kept for a name outside the catalog, and a test
# pins that it matches none).
AGE_GATES: tuple[AgeGate, ...] = (
    AgeGate("icd", ("P",), None, 1, None, "a perinatal condition (ICD chapter P)"),
    AgeGate("icd", ("O",), 10, 55, "F", "a pregnancy condition (ICD chapter O)"),
    AgeGate("icd", ("Z38",), None, 1, None, "a liveborn infant code (Z38)"),
    AgeGate(
        "name", ("yenidoğan", "yeni doğan", "neonatal", "prematüre", "bebek"), None, 1, None,
        "a newborn or infant procedure",
    ),
    AgeGate("name", ("2 yaş altı",), None, 1, None, "a procedure for a child under 2", whole=True),
    AgeGate("name", ("10 yaş altı",), None, 9, None, "a procedure for a child under 10", whole=True),
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

# material.operation_link: the categories a procedure line that carries materials may have (an
# operation is billed as an `islem`, or as a `paket` when it is an EK-2C package).
OPERATION_CATEGORIES: tuple[str, ...] = ("islem", "paket")

# material.stray_flag: the flags are the Boolean columns of material_claim_lines except the two
# structural ones. A flag is healthy when it is false (or missing), except the registration flags,
# which are healthy when true (or missing). Decisions of the author, from the data audit.
STRUCTURAL_FLAGS: tuple[str, ...] = ("is_bundled", "requires_pre_auth")
REGISTRATION_FLAGS: tuple[str, ...] = ("titubb_registered", "uts_registered")

# price.material_in_force: the curated EK-3/F-1 list is one list, in force from its Yürürlük date
# 13.12.2025 (raw folder annex=EK-3F-1/effective_date=2025-12-13). It carries no end date.
EK3F1_FROM = date(2025, 12, 13)

# money.line_arithmetic: the multiple-surgery ladder bills the full price, half of it or a quarter of
# it; a ratio is written as quarters of the full price so that the test stays in whole numbers.
LADDER_QUARTERS: tuple[int, ...] = (4, 2, 1)

# labels.*: the text columns the fault entries of the registry are read into, and the table of each
# line type of a fault record.
FAULT_COLUMNS: tuple[str, ...] = (
    "fault_id", "claim_id", "line_type", "line_id", "effect_kind",
    "amount_try", "billed_clean_try", "billed_faulty_try",
)  # fmt: skip
LINE_TABLES: dict[str, str] = {
    "islem": "procedure_claim_lines",
    "malzeme": "material_claim_lines",
    "ilac": "drug_claim_lines",
}
ANSWER_MONEY_COLUMNS: tuple[str, ...] = ("expected_payable_try", "expected_savings_try")

_DATE_FORMAT = "%Y-%m-%d"

# Written in `where` for a row that has no claim id (in every check), and in a message for any other
# missing value the text is `(none)`.
NO_CLAIM = "(no-claim-id)"


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


def _without_exceptions(folded: pl.Expr, phrases: Iterable[str] = NAME_EXCEPTIONS) -> pl.Expr:
    """A folded name with the exception `phrases` blanked out (longest phrase first)."""
    for phrase in sorted((fold_text(p) for p in phrases), key=len, reverse=True):
        folded = folded.str.replace_all(phrase, " ", literal=True)
    return folded


def _words_pattern(words: Iterable[str], *, whole: bool = False) -> str:
    """A regex that finds any of `words` (folded), inside words or, with `whole`, as whole words."""
    # re.escape writes a space as `\ `; a phrase (`tüp ligasyonu`) keeps its plain spaces
    escaped = {re.escape(fold_text(w)).replace("\\ ", " ") for w in words}
    alternatives = "|".join(sorted(escaped))
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
        """The codes of one bed-day line: ward day, day bed, the newborn beds (incubator, cot), ICU day fee, and the ICU packages."""
        beds = self.code_sets["beds"]
        fee = [
            beds["ward_day"]["code"],
            beds["day_bed"]["code"],
            beds["incubator"]["code"],
            beds["cot"]["code"],
            beds["icu_day_fee_for_service"]["code"],
        ]
        return [*fee, *self.icu_codes]

    @cached_property
    def icu_day_codes(self) -> list[str]:
        """The codes of an ICU day: the day rate 510090 and the ICU packages (the bed lines of an ICU stay)."""
        return [self.code_sets["beds"]["icu_day_fee_for_service"]["code"], *self.icu_codes]

    @cached_property
    def day_bed_code(self) -> str:
        """The day bed (510120): a bed day only on a stay of less than 24 hours."""
        return self.code_sets["beds"]["day_bed"]["code"]

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

    def bill_codes(self, pathway_id: str, pins: Pins | None = None) -> list[tuple[str, str]]:
        """(family, code) of the clean bill of a pathway with `pins` (its own showcase pins by default).

        The siblings that the faults aimed at the pathway swap in are expanded with the same pins.
        """
        pathway = self.pathways[pathway_id]
        effective = pins if pins is not None else pathway.showcase
        bills = [expand(pathway, effective)]
        bills += [
            expand(self.siblings[sid], effective) for sid in self.sibling_ids.get(pathway_id, [])
        ]
        found: list[tuple[str, str]] = []
        for bill in bills:
            held = {
                "procedure": [p["code"] for p in bill["procedures"]],
                "material": [m["code"] for m in bill["materials"]],
                "drug": [d["barcode"] for d in bill["drugs"]],
                "diagnosis": [d["icd10"] for d in bill["diagnoses"]],
            }
            found += [(family, code) for family, family_codes in held.items() for code in family_codes]
        return found

    @cached_property
    def vocabulary(self) -> pl.DataFrame:
        """scenario_tag, family, code: what the clean bill of each pathway (and its siblings) holds."""
        tags: list[str] = []
        families: list[str] = []
        codes: list[str] = []
        for pathway_id in self.pathways:
            for family, code in self.bill_codes(pathway_id):
                tags.append(pathway_id)
                families.append(family)
                codes.append(code)
        schema = {"scenario_tag": pl.String, "family": pl.String, "code": pl.String}
        frame = pl.DataFrame(
            {"scenario_tag": tags, "family": families, "code": codes}, schema=schema
        )
        return frame.unique()

    @cached_property
    def ek3f1(self) -> pl.DataFrame:
        """sut_code, price_try: the EK-3/F-1 arthroplasty materials list (read directly)."""
        path = self.root / "data/gazette/curated/ek3f1_arthroplasty_materials.parquet"
        return pl.read_parquet(path, columns=["sut_code", "price_try"])

    @cached_property
    def ek4a(self) -> pl.DataFrame:
        """barcode, valid_from, valid_until (Dates) of the EK-4A history (read directly).

        `valid_until` is exclusive and null means the row is still open. The dates of a reference
        list must parse: a malformed one raises instead of silently opening a row.
        """
        path = self.root / "data/gazette/curated/ek4a_history.parquet"
        return pl.read_parquet(path, columns=["barcode", "valid_from", "valid_until"]).with_columns(
            pl.col("valid_from").str.to_date(_DATE_FORMAT),
            pl.col("valid_until").str.to_date(_DATE_FORMAT),
        )


@lru_cache(maxsize=1)
def default_context() -> PlausibilityContext:
    """The context `check_plausibility` uses when it is given none (shared, so data load once)."""
    return PlausibilityContext()


# --- small expression helpers ------------------------------------------------------------------


def _date(name: str) -> pl.Expr:
    """An ISO date string column as a Date (null when it is missing or not an ISO date)."""
    return pl.col(name).str.to_date(_DATE_FORMAT, strict=False)


def _format(template: str, *args: pl.Expr) -> pl.Expr:
    """`pl.format`, writing `(none)` for a missing value: `pl.format` makes the whole text null.

    The text is joined with `+` and not with `pl.format`: in polars 2.0.0 a `pl.format` of two
    columns panics (`assertion failed: i < self.len()`) on a table of a few thousand rows that a
    filter has cut down to a few findings. The result is the same text.
    """
    pieces = template.split("{}")
    if len(pieces) != len(args) + 1:
        raise ValueError(f"{template!r} has {len(pieces) - 1} placeholders for {len(args)} values")
    text = pl.lit(pieces[0])
    for arg, piece in zip(args, pieces[1:], strict=True):
        text = text + arg.cast(pl.String).fill_null("(none)") + pl.lit(piece)
    return text


def _claim_text(claim: str | pl.Expr = "claim_id") -> pl.Expr:
    """A claim id as the text a `where` starts with: `(no-claim-id)` when the row has none."""
    expr = pl.col(claim) if isinstance(claim, str) else claim
    return expr.cast(pl.String).fill_null(NO_CLAIM)


def _where(claim: str, kind: str | pl.Expr, key: str) -> pl.Expr:
    """`where` of a finding about one line: the claim id, then `kind[key]` (`kind` may be a column)."""
    return _format(
        "{} {}[{}]",
        _claim_text(claim),
        pl.lit(kind) if isinstance(kind, str) else kind,
        pl.col(key),
    )


def _other_than(sex: str | pl.Expr) -> pl.Expr:
    """The patient's sex (column `sex`) is not `sex`; a patient of unknown sex is not either."""
    return (pl.col("sex") != sex).fill_null(True)


def _in_blocks(code: pl.Expr, blocks: Iterable[str]) -> pl.Expr:
    """`code` lies in one of the ICD-10 `blocks` (`N40-N53`, `D07.4-D07.6`, `E29`); no code: False.

    The first characters of the code, as many as the ends of the block have, lie between the ends.
    """
    tests = []
    for block in blocks:
        low, _, high = block.partition("-")
        tests.append(code.str.slice(0, len(low)).is_between(pl.lit(low), pl.lit(high or low)))
    return pl.any_horizontal(tests).fill_null(False)


def _days_text(column: str = "day") -> pl.Expr:
    """In an aggregation: the Dates of the group as one sorted text, `2026-03-13, 2026-03-14`."""
    return pl.col(column).sort().cast(pl.String).str.join(", ")


def _cents(amount: pl.Expr) -> pl.Expr:
    """An amount in lira (a number or the text of one) as whole cents: Int64, null when it is no number."""
    return (amount.cast(pl.Float64, strict=False) * 100).round(0).cast(pl.Int64, strict=False)


def _tl(cents: pl.Expr) -> pl.Expr:
    """Whole cents as text with two decimals (null stays null): 539189 -> 5391.89."""
    sign = pl.when(cents < 0).then(pl.lit("-")).otherwise(pl.lit(""))
    absolute = cents.abs()
    return pl.concat_str(
        sign,
        (absolute // 100).cast(pl.String),
        pl.lit("."),
        (absolute % 100).cast(pl.String).str.pad_start(2, "0"),
    )


def _is_cent_price_of(price: pl.Expr, billed: pl.Expr) -> pl.Expr:
    """`billed` is `price` to the cent: the nearest cent, and for a tie either neighbour.

    The test is in millionths of a lira, so it is exact in whole numbers: billed cents u fit a price
    of m millionths when 10000u - 5000 <= m <= 10000u + 5000. The half-up cent always fits. A price
    within a millionth of a half cent is a tie, and both neighbours fit, because the lists are
    floats with binary noise: the EK-3/F-1 price 15076.214999999998 is meant as 15076.215 and is
    billed as 15076.21 by `Decimal(str(price))` half up and as 15076.22 by an exact half up. No
    price a cent away from the list price fits.
    """
    micro = (price * 1_000_000).round(0).cast(pl.Int64, strict=False)
    offset = micro - _cents(billed) * 10_000
    return (offset >= -5_000) & (offset <= 5_000)


def _differs(left: pl.Expr, right: pl.Expr) -> pl.Expr:
    """`left` and `right` are not equal; a missing value on either side counts as different."""
    return ~(left == right).fill_null(False)


def _engine_price(code: str, day: date) -> float | None:
    """The engine's price of an EK-2B code, or of an EK-2C package (a P-code), in force on `day`.

    The engine module is imported on first use: it loads pandas, which nothing else here needs. A
    `date` (not text) is handed over, so the engine never parses a string.
    """
    from src.bilun.domain.pricing.temporal import get_ek2b_price_for_date, get_ek2c_price_for_date

    lookup = get_ek2c_price_for_date if code.strip().startswith("P") else get_ek2b_price_for_date
    return lookup(code, day)


def _problems(check: str, found: pl.DataFrame) -> list[Problem]:
    """Problems for findings with the columns `where` and `message`, in a stable order."""
    ordered = found.select(pl.col("where").fill_null(NO_CLAIM), "message").sort("where", "message")
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
        registry: Mapping[str, Any] | None = None,
    ) -> None:
        self.tables = tables
        self.clean_tables = clean_tables
        self.ctx = ctx
        self.registry = registry

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
                    "is_icu_day": code.is_in(ctx.icu_day_codes),
                    "is_day_bed": code == ctx.day_bed_code,
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
    def pinned_vocabulary(self) -> pl.DataFrame:
        """claim_id, family, code: what the clean bill of an encounter holds whose recipe overrides the pins.

        The registry's `encounters` carry the overrides (`pins`, only where a recipe has some); an encounter
        with none is judged by the vocabulary of its pathway's own pins (`PlausibilityContext.vocabulary`).
        An override the pathway cannot expand (a registry that was edited by hand) is left out, so the
        codes of that bill are judged by the pathway's own pins.
        """
        claims: list[str] = []
        families: list[str] = []
        codes: list[str] = []
        for encounter in (self.registry or {}).get("encounters", []):
            overrides = encounter.get("pins")
            pathway = self.ctx.pathways.get(encounter.get("pathway_id"))
            if not overrides or pathway is None:
                continue
            try:
                pins = Pins.model_validate({**pathway.showcase.model_dump(), **overrides})
                held = self.ctx.bill_codes(pathway.id, pins)
            except ValueError:  # ValidationError and ExpandError
                continue
            for family, code in held:
                claims.append(encounter["claim_id"])
                families.append(family)
                codes.append(code)
        schema = {"claim_id": pl.String, "family": pl.String, "code": pl.String}
        frame = pl.DataFrame({"claim_id": claims, "family": families, "code": codes}, schema=schema)
        return frame.unique()

    @cached_property
    def named_lines(self) -> pl.DataFrame:
        """Procedure lines with the patient's sex and age and the folded name without exceptions."""
        return self.lines.join(
            self.patients, on=["patient_id", "episode_id"], how="left"
        ).with_columns(_without_exceptions(_fold(pl.col("procedure_name"))).alias("folded_name"))

    @cached_property
    def priced(self) -> pl.DataFrame:
        """The procedure, material and drug lines in one frame: the columns the money checks read.

        `copay_rate_applicable` and `copay_rate` are the procedure line's patient share (slice G5b); a material
        or drug line has none (False, null).
        """
        sources = (
            (TABLE_PROCEDURES, "islem", "procedure_line_id"),
            (TABLE_MATERIALS, "malzeme", "material_line_id"),
            (TABLE_DRUGS, "ilac", "drug_claim_line_id"),
        )

        def share(table: str) -> list[pl.Expr]:
            if table == TABLE_PROCEDURES:
                return [
                    pl.col("copay_rate_applicable").cast(pl.Boolean, strict=False),
                    pl.col("copay_rate").cast(pl.Float64, strict=False),
                ]
            return [
                pl.lit(False).alias("copay_rate_applicable"),
                pl.lit(None, dtype=pl.Float64).alias("copay_rate"),
            ]

        return pl.concat(
            [
                self.table(table).select(
                    "claim_id",
                    pl.lit(line_type).alias("line_type"),
                    pl.lit(table.removesuffix(".parquet")).alias("table"),
                    pl.col(key).alias("line_id"),
                    "quantity",
                    "unit_price_try",
                    "billed_amount_try",
                    "expected_payable_try",
                    *share(table),
                )
                for table, line_type, key in sources
            ]
        )

    @cached_property
    def fault_entries(self) -> list[Mapping[str, Any]]:
        """The entries of `registry["faults"]` that are mappings (none when it is no list)."""
        faults = (self.registry or {}).get("faults")
        if not isinstance(faults, list):
            return []
        return [entry for entry in faults if isinstance(entry, Mapping)]

    @cached_property
    def fault_records(
        self,
    ) -> tuple[list[FaultInjectionRecord], list[tuple[str, str | None, str]]]:
        """The fault records re-created from the registry, and each entry that is none: (where, claim, message)."""
        faults = (self.registry or {}).get("faults")
        if not isinstance(faults, list):
            return [], [("(registry)", None, "the registry has no list of faults")]
        records: list[FaultInjectionRecord] = []
        invalid: list[tuple[str, str | None, str]] = []
        for index, entry in enumerate(faults):
            try:
                records.append(FaultInjectionRecord.model_validate(entry))
            except ValidationError as error:
                claim = entry.get("claim_id") if isinstance(entry, Mapping) else None
                claim = claim if isinstance(claim, str) and claim else None
                why = "; ".join(
                    (f"{'.'.join(map(str, found['loc']))}: " if found["loc"] else "")
                    + found["msg"].removeprefix("Value error, ")
                    for found in error.errors()
                )
                invalid.append(
                    (
                        f"{claim or NO_CLAIM} registry faults[{index}]",
                        claim,
                        f"the entry is no valid fault record: {why}",
                    )
                )
        return records, invalid

    @cached_property
    def faults(self) -> pl.DataFrame:
        """The fault entries of the registry as text columns (FAULT_COLUMNS); a missing value is null."""
        columns = {
            name: [
                None if entry.get(name) is None else str(entry[name])
                for entry in self.fault_entries
            ]
            for name in FAULT_COLUMNS
        }
        return pl.DataFrame(columns, schema={name: pl.String for name in FAULT_COLUMNS})


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
    """patient.sex_gate: an ICD sex gate (column or block), or a sex word in a name, vs the sex."""
    code = pl.col("icd10_code")
    block_sex = (
        pl.when(_in_blocks(code, ICD_SEX_GATES["M"]))
        .then(pl.lit("M"))
        .when(_in_blocks(code, ICD_SEX_GATES["F"]))
        .then(pl.lit("F"))
    )
    gated = (
        bill.diagnoses.join(bill.patients, on=["patient_id", "episode_id"], how="left")
        .join(
            bill.ctx.icd.select("code", pl.col("sex").alias("icd_sex")),
            left_on="icd10_code",
            right_on="code",
            how="left",
        )
        .with_columns(pl.coalesce(pl.col("icd_sex"), block_sex).alias("gate_sex"))
        .filter(pl.col("gate_sex").is_not_null() & _other_than(pl.col("gate_sex")))
        .select(
            _where("claim_id", "claim_diagnoses", "diagnosis_id").alias("where"),
            _format(
                "diagnosis {} is limited to sex {} but the patient is {}",
                pl.col("icd10_code"),
                pl.col("gate_sex"),
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
            pattern = _words_pattern(gate.words, whole=gate.whole)
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
        _claim_text().alias("where"),
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
        (
            bill.table(TABLE_PROCEDURES),
            "procedure",
            "procedure_code",
            "procedure_line_id",
            "procedure_claim_lines",
        ),
        (
            bill.table(TABLE_MATERIALS),
            "material",
            "material_code",
            "material_line_id",
            "material_claim_lines",
        ),
        (bill.table(TABLE_DRUGS), "drug", "barkod", "drug_claim_line_id", "drug_claim_lines"),
        (bill.diagnoses, "diagnosis", "icd10_code", "diagnosis_id", "claim_diagnoses"),
    ]
    held = pl.concat(
        [
            frame.select(
                "claim_id",
                pl.lit(family).alias("family"),
                pl.lit(table).alias("table"),
                pl.col(key).alias("line_id"),
                pl.col(column).alias("code"),
            )
            for frame, family, column, key, table in sources
        ]
    ).join(tags, on="claim_id", how="left")
    pathway_ids = list(ctx.pathways)
    unknown = tags.filter(~pl.col("scenario_tag").is_in(pathway_ids).fill_null(False)).select(
        _claim_text().alias("where"),
        _format(
            "scenario_tag {} is not a care pathway of data/synthetic/pathways",
            pl.col("scenario_tag").fill_null("(missing)"),
        ).alias("message"),
    )
    pinned_claims = bill.pinned_vocabulary["claim_id"].unique().to_list()
    in_pathway = pl.col("scenario_tag").is_in(pathway_ids).fill_null(False)
    # A claim whose recipe overrides the pins is judged by the expansion of the pathway with those pins,
    # every other claim by the expansion with the pathway's own.
    off_vocabulary = pl.concat(
        [
            held.filter(in_pathway & ~pl.col("claim_id").is_in(pinned_claims)).join(
                ctx.vocabulary, on=["scenario_tag", "family", "code"], how="anti"
            ),
            held.filter(in_pathway & pl.col("claim_id").is_in(pinned_claims)).join(
                bill.pinned_vocabulary, on=["claim_id", "family", "code"], how="anti"
            ),
        ]
    )
    extra = off_vocabulary.select(
        _where("claim_id", pl.col("table"), "line_id").alias("where"),
        _format(
            "{} code {} is not in the expansion of {} or of a sibling that a fault swaps in",
            pl.col("family"),
            pl.col("code"),
            pl.col("scenario_tag"),
        ).alias("message"),
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
    """stay.bed_coverage: one bed line of quantity 1 on every day admission..discharge, none else.

    A day bed (510120) takes its day like any bed line, but it is for a day case: on a stay whose
    discharge date is not its admission date it is a defect of its own.

    An ICU stay (a claim with a 510090 or an ICU package line) is billed for `discharge - admission`
    days (icu_puani.py): its ICU lines are its bed lines and cover admission..discharge-1; the
    discharge day is the transfer day and carries none. A ward bed line on an ICU stay is a defect.

    A stay that begins on the day the same patient leaves an ICU stay (the ward bill after the ICU
    bill) has that day's bed paid by the ICU bill (EK-2B 510090 covers the bed; yatak_icu_overlap.py):
    it needs no bed line for that day, and a bed line there is double billing.
    """
    icu_claims = (
        bill.lines.filter(pl.col("is_icu_day"))
        .select("claim_id")
        .unique()
        .with_columns(pl.lit(True).alias("is_icu_stay"))
    )
    stays = (
        bill.headers.filter(
            (pl.col("claim_type") == "yatis")
            & ~pl.col("is_package_claim")
            & pl.col("adm").is_not_null()
            & pl.col("dis").is_not_null()
        )
        .select("claim_id", "patient_id", "adm", "dis")
        .join(icu_claims, on="claim_id", how="left")
        .with_columns(pl.col("is_icu_stay").fill_null(False))
    )
    # The transfer day: a stay's admission day that is the discharge day of an ICU stay of the same patient.
    arrivals = (
        stays.select("claim_id", "patient_id", pl.col("adm").alias("day"))
        .join(
            stays.filter(pl.col("is_icu_stay")).select(
                "patient_id", pl.col("claim_id").alias("icu_claim_id"), pl.col("dis").alias("day")
            ),
            on=["patient_id", "day"],
        )
        .filter(pl.col("claim_id") != pl.col("icu_claim_id"))
        .sort("icu_claim_id")
        .unique(subset=["claim_id"], keep="first")
        .select("claim_id", "day", "icu_claim_id")
    )
    stay_days = (
        stays.with_columns(pl.date_ranges("adm", "dis").alias("day"))
        .explode("day")
        .filter(pl.col("day").is_not_null())
        .filter(~pl.col("is_icu_stay") | (pl.col("day") < pl.col("dis")))
        .select("claim_id", "day")
    )
    days = stay_days.join(arrivals.select("claim_id", "day"), on=["claim_id", "day"], how="anti")
    beds = (
        bill.lines.filter(pl.col("is_bed_day"))
        .join(stays.select("claim_id"), on="claim_id", how="semi")
        .with_columns(_date("procedure_date").alias("day"))
    )
    per_day = beds.group_by("claim_id", "day").agg(pl.len().alias("n"))
    expected_days = days.group_by("claim_id").agg(pl.len().alias("stay_days"))

    missing = (
        days.join(per_day, on=["claim_id", "day"], how="anti")
        .group_by("claim_id")
        .agg(_days_text().alias("days"), pl.len().alias("count"))
        .join(expected_days, on="claim_id")
        .select(
            _claim_text().alias("where"),
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
            _claim_text().alias("where"),
            _format("more than one bed line on: {}", pl.col("days")).alias("message"),
        )
    )
    quantity = beds.filter(pl.col("quantity").fill_null(0) != 1).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format(
            "bed line {} has the quantity {}; a bed line is one day",
            pl.col("procedure_code"),
            pl.col("quantity"),
        ).alias("message"),
    )
    day_bed = (
        beds.filter(pl.col("is_day_bed"))
        .join(stays, on="claim_id")
        .filter(pl.col("adm") != pl.col("dis"))
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "day bed line {} on the stay {}..{}; the day bed is for a day case, "
                "admitted and discharged on the same date",
                pl.col("procedure_code"),
                pl.col("adm"),
                pl.col("dis"),
            ).alias("message"),
        )
    )
    paid_by_icu = (
        beds.join(arrivals, on=["claim_id", "day"])
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "bed line {} on {}, the day the patient leaves the ICU stay {}; "
                "that stay's 510090 already pays the bed (double billing)",
                pl.col("procedure_code"),
                pl.col("procedure_date"),
                pl.col("icu_claim_id"),
            ).alias("message"),
        )
    )
    outside = (
        beds.join(stay_days, on=["claim_id", "day"], how="anti")
        .group_by("claim_id")
        .agg(pl.col("procedure_date").sort().str.join(", ").alias("dates"))
        .select(
            _claim_text().alias("where"),
            _format("bed line(s) outside admission..discharge: {}", pl.col("dates")).alias(
                "message"
            ),
        )
    )
    ward_on_icu = (
        beds.filter(~pl.col("is_icu_day"))
        .join(stays.filter(pl.col("is_icu_stay")).select("claim_id"), on="claim_id", how="semi")
        .select(
            _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
            _format(
                "ward bed line {} on an ICU stay; the ICU lines are the bed lines of the bill",
                pl.col("procedure_code"),
            ).alias("message"),
        )
    )
    return _problems(
        "stay.bed_coverage",
        pl.concat([missing, twice, quantity, day_bed, outside, ward_on_icu, paid_by_icu]),
    )


def check_companion_coverage(bill: _Bill) -> list[Problem]:
    """stay.companion_coverage: quantity 1, one per day, on admission..discharge-1."""
    companions = (
        bill.lines.filter(pl.col("is_companion"))
        .join(bill.headers.select("claim_id", "adm", "dis"), on="claim_id", how="left")
        .with_columns(_date("procedure_date").alias("day"))
    )
    per_day = companions.group_by("claim_id", "day").agg(pl.len().alias("n"))
    quantity = companions.filter(pl.col("quantity").fill_null(0) != 1).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        _format("companion line has the quantity {}", pl.col("quantity")).alias("message"),
    )
    twice = (
        per_day.filter(pl.col("n") > 1)
        .group_by("claim_id")
        .agg(_days_text().alias("days"))
        .select(
            _claim_text().alias("where"),
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
        _claim_text().alias("where"),
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
    lines = dated.filter(~inside).select(
        _where("claim_id", pl.col("table"), "key").alias("where"),
        _format(
            "dated {} outside the claim window {}..{}",
            pl.col("raw_day").fill_null("(missing)"),
            pl.col("start").cast(pl.String).fill_null("(no header)"),
            pl.col("end").cast(pl.String).fill_null("(no header)"),
        ).alias("message"),
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
        _claim_text().alias("where"),
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
        _format("{} day[{}]", _claim_text(), pl.col("procedure_date")).alias("where"),
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


# --- material ----------------------------------------------------------------------------------


def check_operation_link(bill: _Bill) -> list[Problem]:
    """material.operation_link: a material hangs on an operation of its own claim, on its day."""
    operations = bill.lines.select(
        "claim_id",
        "procedure_line_id",
        pl.col("procedure_code").alias("link_code"),
        pl.col("procedure_name").alias("link_name"),
        pl.col("procedure_category").alias("link_category"),
        pl.col("procedure_date").alias("link_date"),
        (pl.col("is_operation") & pl.col("procedure_category").is_in(OPERATION_CATEGORIES))
        .fill_null(False)
        .alias("link_is_operation"),
        pl.lit(True).alias("link_found"),
    ).unique(subset=["claim_id", "procedure_line_id"], keep="first", maintain_order=True)
    joined = (
        bill.table(TABLE_MATERIALS)
        .select(
            "claim_id", "material_line_id", "procedure_line_id", "material_code", "material_date"
        )
        .join(operations, on=["claim_id", "procedure_line_id"], how="left")
        .with_columns(pl.col("link_found", "link_is_operation").fill_null(False))
    )
    other_day = (_date("material_date") != _date("link_date")).fill_null(False)
    reasons = pl.concat_str(
        pl.when(pl.col("procedure_line_id").is_null()).then(pl.lit("it has no procedure_line_id")),
        pl.when(pl.col("procedure_line_id").is_not_null() & ~pl.col("link_found")).then(
            _format(
                "its procedure_line_id {} is no procedure line of this claim",
                pl.col("procedure_line_id"),
            )
        ),
        pl.when(pl.col("link_found") & ~pl.col("link_is_operation")).then(
            _format(
                "the line {} ({}, category {}) it hangs on is not an operation",
                pl.col("link_code"),
                pl.col("link_name"),
                pl.col("link_category"),
            )
        ),
        pl.when(pl.col("link_found") & other_day).then(
            _format(
                "it is dated {} but the operation {} it hangs on is dated {}",
                pl.col("material_date"),
                pl.col("link_code"),
                pl.col("link_date"),
            )
        ),
        separator="; ",
        ignore_nulls=True,
    )
    found = (
        joined.with_columns(reasons.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _where("claim_id", "material_claim_lines", "material_line_id").alias("where"),
            _format("material {}: {}", pl.col("material_code"), pl.col("why")).alias("message"),
        )
    )
    return _problems("material.operation_link", found)


def check_stray_flag(bill: _Bill) -> list[Problem]:
    """material.stray_flag: each compliance flag of a material line has its healthy value or none."""
    materials = bill.table(TABLE_MATERIALS)
    stray = [
        pl.when(~pl.col(flag) if flag in REGISTRATION_FLAGS else pl.col(flag)).then(
            pl.lit(f"{flag} is {'false' if flag in REGISTRATION_FLAGS else 'true'}")
        )
        for flag, dtype in materials.schema.items()
        if dtype == pl.Boolean and flag not in STRUCTURAL_FLAGS
    ]
    if not stray:
        return []
    found = (
        materials.with_columns(pl.concat_str(stray, separator=", ", ignore_nulls=True).alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _where("claim_id", "material_claim_lines", "material_line_id").alias("where"),
            _format(
                "material {} has flag(s) off the healthy value: {}",
                pl.col("material_code"),
                pl.col("why"),
            ).alias("message"),
        )
    )
    return _problems("material.stray_flag", found)


# --- price -------------------------------------------------------------------------------------


def check_procedure_price(bill: _Bill) -> list[Problem]:
    """price.procedure_in_force: a procedure line bills the engine's price of its day, to the cent."""
    lines = bill.table(TABLE_PROCEDURES).select(
        "claim_id",
        "procedure_line_id",
        "procedure_code",
        "procedure_date",
        "unit_price_try",
        _date("procedure_date").alias("day"),
    )
    asked = (
        lines.filter(pl.col("day").is_not_null() & pl.col("procedure_code").is_not_null())
        .select("procedure_code", "day")
        .unique(maintain_order=True)
    )
    # the engine's lookup is scalar: ask it once for each distinct (code, day), then join back
    in_force = pl.Series(
        "in_force",
        [
            _engine_price(code, day)
            for code, day in zip(asked["procedure_code"], asked["day"], strict=True)
        ],
        dtype=pl.Float64,
    )
    priced = lines.join(asked.with_columns(in_force), on=["procedure_code", "day"], how="left")
    unit = _tl(_cents(pl.col("unit_price_try")))
    found = priced.filter(
        pl.col("day").is_not_null()
        & ~_is_cent_price_of(pl.col("in_force"), pl.col("unit_price_try")).fill_null(False)
    ).select(
        _where("claim_id", "procedure_claim_lines", "procedure_line_id").alias("where"),
        pl.when(pl.col("in_force").is_null())
        .then(
            _format(
                "procedure {} dated {} has no price in force on that day (unit price {})",
                pl.col("procedure_code"),
                pl.col("procedure_date"),
                unit,
            )
        )
        .otherwise(
            _format(
                "procedure {} dated {}: unit price {} but the price in force is {}",
                pl.col("procedure_code"),
                pl.col("procedure_date"),
                unit,
                _tl(_cents(pl.col("in_force"))),
            )
        )
        .alias("message"),
    )
    return _problems("price.procedure_in_force", found)


def check_material_price(bill: _Bill) -> list[Problem]:
    """price.material_in_force: a material is in the EK-3/F-1 list, dated from its start, at its price."""
    priced = (
        bill.table(TABLE_MATERIALS)
        .select("claim_id", "material_line_id", "material_code", "material_date", "unit_price_try")
        .join(bill.ctx.ek3f1, left_on="material_code", right_on="sut_code", how="left")
    )
    listed = pl.col("price_try").is_not_null()
    reasons = pl.concat_str(
        pl.when(~listed).then(pl.lit("is not in the EK-3/F-1 list")),
        pl.when(_date("material_date") < EK3F1_FROM).then(
            _format("is before the list is in force (from {})", pl.lit(EK3F1_FROM.isoformat()))
        ),
        pl.when(
            listed
            & ~_is_cent_price_of(pl.col("price_try"), pl.col("unit_price_try")).fill_null(False)
        ).then(
            _format(
                "has the unit price {} but the list price is {}",
                _tl(_cents(pl.col("unit_price_try"))),
                _tl(_cents(pl.col("price_try"))),
            )
        ),
        separator="; ",
        ignore_nulls=True,
    )
    found = (
        priced.with_columns(reasons.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _where("claim_id", "material_claim_lines", "material_line_id").alias("where"),
            _format(
                "material {} dated {} {}",
                pl.col("material_code"),
                pl.col("material_date"),
                pl.col("why"),
            ).alias("message"),
        )
    )
    return _problems("price.material_in_force", found)


def check_drug_price(bill: _Bill) -> list[Problem]:
    """price.drug_in_force: a drug line's barcode has an EK-4A row in force on the line's day."""
    drugs = bill.table(TABLE_DRUGS).select(
        "claim_id",
        "drug_claim_line_id",
        "drug_name",
        "barkod",
        "drug_claim_date",
        _date("drug_claim_date").alias("day"),
    )
    history = bill.ctx.ek4a
    in_force = (
        drugs.join(history, left_on="barkod", right_on="barcode")
        .filter(
            (pl.col("valid_from") <= pl.col("day"))
            & (pl.col("valid_until").is_null() | (pl.col("day") < pl.col("valid_until")))
        )
        .select("drug_claim_line_id", pl.lit(True).alias("in_force"))
        .unique()
    )
    known = history.select(pl.col("barcode").unique(), pl.lit(True).alias("known"))
    found = (
        drugs.filter(pl.col("day").is_not_null())
        .join(in_force, on="drug_claim_line_id", how="left")
        .join(known, left_on="barkod", right_on="barcode", how="left")
        .filter(~pl.col("in_force").fill_null(False))
        .select(
            _where("claim_id", "drug_claim_lines", "drug_claim_line_id").alias("where"),
            pl.when(pl.col("known").fill_null(False))
            .then(
                _format(
                    "drug {} (barcode {}) dated {} has no EK-4A row in force on that day",
                    pl.col("drug_name"),
                    pl.col("barkod"),
                    pl.col("drug_claim_date"),
                )
            )
            .otherwise(
                _format(
                    "drug {} (barcode {}) is not in the EK-4A history",
                    pl.col("drug_name"),
                    pl.col("barkod"),
                )
            )
            .alias("message"),
        )
    )
    return _problems("price.drug_in_force", found)


# --- money -------------------------------------------------------------------------------------


def _priced_where() -> pl.Expr:
    """`where` of a finding about a line of the `priced` frame: the claim id, then `table[line id]`."""
    return _format("{} {}[{}]", _claim_text(), pl.col("table"), pl.col("line_id"))


def check_line_arithmetic(bill: _Bill) -> list[Problem]:
    """money.line_arithmetic: billed = unit price x quantity x (1, 0.5 or 0.25), to the cent."""
    unit, billed = _cents(pl.col("unit_price_try")), _cents(pl.col("billed_amount_try"))
    full = unit * pl.col("quantity")
    # in quarter-cents: the billed amount is within half a cent of one rung (a tie fits either way)
    fits = pl.any_horizontal(
        *[(billed * 4 - full * quarters).abs() <= 2 for quarters in LADDER_QUARTERS]
    )
    found = bill.priced.filter(~fits.fill_null(False)).select(
        _priced_where().alias("where"),
        _format(
            "billed {} is not the unit price {} x quantity {} x 1, 0.5 or 0.25 ({}, {} or {})",
            _tl(billed),
            _tl(unit),
            pl.col("quantity"),
            _tl((full * 4 + 2) // 4),
            _tl((full * 2 + 2) // 4),
            _tl((full + 2) // 4),
        ).alias("message"),
    )
    return _problems("money.line_arithmetic", found)


def check_payable_equals_billed(bill: _Bill) -> list[Problem]:
    """money.payable_equals_billed: the payable of every line is its billed amount, except on a line with a
    patient share (slice G5b).

    A procedure line with the copay flag pays its billed amount less its share: billed x (1 - copay_rate),
    half up to the cent (the composer's arithmetic); the flag needs a rate above 0 and below 1, and a rate
    needs the flag (the engine reads no rate without it).
    """
    payable, billed = _cents(pl.col("expected_payable_try")), _cents(pl.col("billed_amount_try"))
    flagged = pl.col("copay_rate_applicable").fill_null(False)
    rate = pl.col("copay_rate")
    has_share = rate.is_not_null() & (rate > 0) & (rate < 1)
    percent = (rate * 100).round(0).cast(pl.Int64, strict=False)
    shared = (billed * (100 - percent) + 50) // 100  # half up, in whole cents (billed is not negative)
    rate_text = _tl(percent)  # the rate as text with two decimals: 0.20
    found = [
        bill.priced.filter(~flagged & _differs(payable, billed)).select(
            _priced_where().alias("where"),
            _format(
                "expected_payable_try is {} but billed_amount_try is {}; a line pays what it bills",
                _tl(payable),
                _tl(billed),
            ).alias("message"),
        ),
        bill.priced.filter(flagged & has_share & _differs(payable, shared)).select(
            _priced_where().alias("where"),
            _format(
                "expected_payable_try is {} but billed_amount_try {} less the copay share {} is {}",
                _tl(payable),
                _tl(billed),
                rate_text,
                _tl(shared),
            ).alias("message"),
        ),
        bill.priced.filter(flagged & ~has_share.fill_null(False)).select(
            _priced_where().alias("where"),
            _format(
                "copay_rate_applicable is true but copay_rate is {}; a line with the copay flag needs a share above 0 and below 1",
                rate_text,
            ).alias("message"),
        ),
        bill.priced.filter(~flagged & rate.is_not_null()).select(
            _priced_where().alias("where"),
            _format(
                "copay_rate is {} but copay_rate_applicable is false; a rate needs the copay flag",
                rate_text,
            ).alias("message"),
        ),
    ]
    return _problems("money.payable_equals_billed", pl.concat(found))


def check_totals(bill: _Bill) -> list[Problem]:
    """money.totals: the header totals are the sums of the procedure, material and drug lines."""
    sums = bill.priced.group_by("claim_id").agg(
        _cents(pl.col("billed_amount_try")).sum().alias("lines_billed"),
        _cents(pl.col("expected_payable_try")).sum().alias("lines_payable"),
    )
    headers = (
        bill.table(TABLE_CLAIM_HEADERS)
        .select(
            "claim_id",
            _cents(pl.col("expected_total_billed_try")).alias("total_billed"),
            _cents(pl.col("expected_total_payable_try")).alias("total_payable"),
        )
        .join(sums, on="claim_id", how="left")
        .with_columns(pl.col("lines_billed", "lines_payable").fill_null(0))
    )
    found = [
        headers.filter(_differs(pl.col(total), pl.col(lines))).select(
            _claim_text().alias("where"),
            _format(
                "{} is {} but the {} amounts of the claim's lines add up to {}",
                pl.lit(column),
                _tl(pl.col(total)),
                pl.lit(kind),
                _tl(pl.col(lines)),
            ).alias("message"),
        )
        for column, total, lines, kind in (
            ("expected_total_billed_try", "total_billed", "lines_billed", "billed"),
            ("expected_total_payable_try", "total_payable", "lines_payable", "payable"),
        )
    ]
    return _problems("money.totals", pl.concat(found))


# --- labels ------------------------------------------------------------------------------------


def _finding(where: str, message: str) -> pl.DataFrame:
    """One finding as a frame, for a finding that is not about the rows of a table."""
    schema = {"where": pl.String, "message": pl.String}
    return pl.DataFrame({"where": [where], "message": [message]}, schema=schema)


def _answer_where(claim: pl.Expr) -> pl.Expr:
    """`where` of a finding about an answer row: the claim id, then `expected_rule_outputs[id]`."""
    return _format("{} expected_rule_outputs[{}]", _claim_text(claim), pl.col("expected_output_id"))


def check_answer_rows(bill: _Bill) -> list[Problem]:
    """labels.answer_rows: expected_rule_outputs is what the registry's fault records produce."""
    records, invalid = bill.fault_records
    answers = bill.table(TABLE_ANSWERS)
    texts = {"where": pl.String, "message": pl.String}
    found = [
        pl.DataFrame(
            {
                "where": [where for where, _, _ in invalid],
                "message": [message for _, _, message in invalid],
            },
            schema=texts,
        )
    ]
    headerless = (
        pl.DataFrame(
            {
                "claim_id": [record.claim_id for record in records],
                "fault_id": [record.fault_id for record in records],
            },
            schema={"claim_id": pl.String, "fault_id": pl.String},
        )
        .join(bill.table(TABLE_CLAIM_HEADERS).select("claim_id"), on="claim_id", how="anti")
        .select(
            _format("{} registry faults[{}]", _claim_text(), pl.col("fault_id")).alias("where"),
            pl.lit("the fault record names a claim that has no header").alias("message"),
        )
    )
    found.append(headerless)
    if list(answers.columns) != list(EXPECTED_OUTPUT_COLUMNS):
        found.append(
            _finding(
                "(expected_rule_outputs)",
                f"the columns are {list(answers.columns)}, the answer key has {list(EXPECTED_OUTPUT_COLUMNS)}",
            )
        )
    try:
        produced = build_expected_rule_outputs(records)
    except ValueError as error:
        found.append(_finding("(registry)", f"the fault records produce no answer key: {error}"))
        produced = None
    if produced is None or not set(EXPECTED_OUTPUT_COLUMNS) <= set(answers.columns):
        return _problems("labels.answer_rows", pl.concat(found))

    expected = pl.DataFrame(
        {
            name: [None if row[name] is None else str(row[name]) for row in produced]
            for name in EXPECTED_OUTPUT_COLUMNS
        },
        schema={name: pl.String for name in EXPECTED_OUTPUT_COLUMNS},
    )
    shown = [
        (
            pl.col(name)
            if name in ANSWER_MONEY_COLUMNS
            else pl.col(name).cast(pl.String, strict=False)
        ).alias(name)
        for name in EXPECTED_OUTPUT_COLUMNS
    ]
    actual = answers.select(shown)
    repeated = (
        actual.group_by("expected_output_id")
        .agg(pl.col("claim_id").first(), pl.len().alias("n"))
        .filter(pl.col("n") > 1)
        .select(
            _answer_where(pl.col("claim_id")).alias("where"),
            _format(
                "{} rows share this answer id; there is one row per fault record", pl.col("n")
            ).alias("message"),
        )
    )
    found.append(repeated)
    actual = actual.unique(subset="expected_output_id", keep="first", maintain_order=True)

    names = [name for name in EXPECTED_OUTPUT_COLUMNS if name != "expected_output_id"]
    both = expected.with_columns(pl.lit(True).alias("in_records")).join(
        actual.with_columns(pl.lit(True).alias("in_table")),
        on="expected_output_id",
        how="full",
        coalesce=True,
        suffix="_table",
    )
    in_records, in_table = (
        pl.col("in_records").fill_null(False),
        pl.col("in_table").fill_null(False),
    )
    where = _answer_where(pl.coalesce("claim_id", "claim_id_table"))

    def differs(name: str) -> pl.Expr:
        mine, theirs = pl.col(name), pl.col(f"{name}_table")
        if name in ANSWER_MONEY_COLUMNS:
            return ~_cents(mine).eq_missing(_cents(theirs))
        return ~mine.eq_missing(theirs)

    why = pl.concat_str(
        [
            pl.when(differs(name)).then(
                _format(
                    "{} is {} but the fault record gives {}",
                    pl.lit(name),
                    pl.col(f"{name}_table"),
                    pl.col(name),
                )
            )
            for name in names
        ],
        separator="; ",
        ignore_nulls=True,
    )
    record_claims = sorted({record.claim_id for record in records})
    invalid_claims = sorted({claim for _, claim, _ in invalid if claim})
    found += [
        both.filter(in_records & ~in_table).select(
            where.alias("where"),
            _format("the fault record {} has no answer row", pl.col("scenario_tag")).alias(
                "message"
            ),
        ),
        both.filter(in_table & ~in_records).select(
            where.alias("where"),
            pl.when(pl.col("claim_id_table").is_in(record_claims))
            .then(pl.lit("no fault record of the claim produces this answer row"))
            .when(pl.col("claim_id_table").is_in(invalid_claims))
            .then(
                pl.lit(
                    "the claim's fault entry is no valid record, so nothing explains this answer row"
                )
            )
            .otherwise(pl.lit("the claim has no fault record, so nothing explains this answer row"))
            .alias("message"),
        ),
        both.filter(in_records & in_table)
        .with_columns(why.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            where.alias("where"),
            _format("the row differs from the fault record: {}", pl.col("why")).alias("message"),
        ),
    ]
    order = (
        expected.select("expected_output_id", "claim_id")
        .with_row_index("record_at")
        .join(
            actual.select("expected_output_id").with_row_index("table_at"),
            on="expected_output_id",
        )
        .sort("record_at")  # a join does not promise the order of its left side
    )
    found.append(
        order.filter(pl.col("table_at") < pl.col("table_at").cum_max().shift(1)).select(
            _answer_where(pl.col("claim_id")).alias("where"),
            pl.lit(
                "the row is out of order; the answer rows follow the records (claim id, fault id)"
            ).alias("message"),
        )
    )
    return _problems("labels.answer_rows", pl.concat(found))


def _line_table(line_type: pl.Expr) -> pl.Expr:
    """The table name of a fault record's line type (null for `fatura` and unknown types)."""
    table = pl.lit(None, dtype=pl.String)
    for kind, name in LINE_TABLES.items():
        table = pl.when(line_type == kind).then(pl.lit(name)).otherwise(table)
    return table


def check_label_amounts(bill: _Bill) -> list[Problem]:
    """labels.amounts: each fault record agrees with the bill: faulty total, target line, amount."""
    faults = bill.faults.with_columns(
        _cents(pl.col("amount_try")).alias("amount"),
        _cents(pl.col("billed_clean_try")).alias("clean"),
        _cents(pl.col("billed_faulty_try")).alias("faulty"),
    )
    headers = (
        bill.table(TABLE_CLAIM_HEADERS)
        .select("claim_id", _cents(pl.col("expected_total_billed_try")).alias("header_total"))
        .unique(subset="claim_id", keep="first")
    )
    sums = bill.priced.group_by("claim_id").agg(
        _cents(pl.col("billed_amount_try")).sum().alias("lines_total")
    )
    lines = bill.priced.select(
        "claim_id", "line_type", "line_id", _cents(pl.col("billed_amount_try")).alias("line_billed")
    ).unique(subset=["claim_id", "line_type", "line_id"], keep="first")
    joined = (
        faults.join(headers, on="claim_id", how="left")
        .join(sums, on="claim_id", how="left")
        .join(lines, on=["claim_id", "line_type", "line_id"], how="left")
    )
    where = _format("{} registry faults[{}]", _claim_text(), pl.col("fault_id"))
    has_header = pl.col("header_total").is_not_null()
    faulty, clean, amount = pl.col("faulty"), pl.col("clean"), pl.col("amount")
    kind, line_type = pl.col("effect_kind"), pl.col("line_type")
    line_id = pl.col("line_id").fill_null("")

    def finding(condition: pl.Expr, message: pl.Expr) -> pl.DataFrame:
        return joined.filter(condition.fill_null(False)).select(
            where.alias("where"), message.alias("message")
        )

    deduction = pl.when(faulty > clean).then(faulty - clean).otherwise(pl.col("line_billed"))
    expected_amount = (
        pl.when(kind == "revenue_uplift")
        .then(clean - faulty)
        .when(kind == "deduction_risk")
        .then(deduction)
        .when(kind == "compliance_error")
        .then(pl.lit(0, dtype=pl.Int64))
    )
    rule = (
        pl.when(kind == "revenue_uplift")
        .then(pl.lit("billed_clean_try - billed_faulty_try"))
        .when(kind == "deduction_risk")
        .then(pl.lit("the growth of the bill, or else the billed amount of the target line"))
        .otherwise(pl.lit("zero"))
    )
    kinds = ["revenue_uplift", "deduction_risk", "compliance_error"]
    typed_line = line_type.is_in(list(LINE_TABLES))
    found = [
        finding(
            has_header & _differs(faulty, pl.col("header_total")),
            _format(
                "billed_faulty_try is {} but expected_total_billed_try of the claim is {}",
                _tl(faulty),
                _tl(pl.col("header_total")),
            ),
        ),
        finding(
            has_header & _differs(faulty, pl.col("lines_total").fill_null(0)),
            _format(
                "billed_faulty_try is {} but the billed amounts of the claim's lines add up to {}",
                _tl(faulty),
                _tl(pl.col("lines_total").fill_null(0)),
            ),
        ),
        finding(
            ~line_type.is_in(["fatura", *LINE_TABLES]).fill_null(False),
            _format("line_type {} is none of fatura, islem, malzeme, ilac", line_type),
        ),
        finding(
            (line_type == "fatura") & (line_id != ""),
            _format("line_id {} must be empty for line_type fatura", line_id),
        ),
        finding(
            typed_line & (line_id == ""),
            _format("line_type {} needs the line_id of its target line", line_type),
        ),
        finding(
            typed_line & (line_id != "") & pl.col("line_billed").is_null(),
            _format("line_id {} is no line of {} of this claim", line_id, _line_table(line_type)),
        ),
        finding(
            ~kind.is_in(kinds).fill_null(False),
            _format("effect_kind {} is none of {}", kind, pl.lit(", ".join(kinds))),
        ),
        finding(
            expected_amount.is_not_null() & _differs(amount, expected_amount),
            _format(
                "{} amount_try is {} but must be {} ({})",
                kind,
                _tl(amount),
                _tl(expected_amount),
                rule,
            ),
        ),
    ]
    return _problems("labels.amounts", pl.concat(found))


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
    "material.operation_link": check_operation_link,
    "material.stray_flag": check_stray_flag,
    "price.procedure_in_force": check_procedure_price,
    "price.material_in_force": check_material_price,
    "price.drug_in_force": check_drug_price,
    "money.line_arithmetic": check_line_arithmetic,
    "money.payable_equals_billed": check_payable_equals_billed,
    "money.totals": check_totals,
    "labels.answer_rows": check_answer_rows,
    "labels.amounts": check_label_amounts,
}


def check_plausibility(
    tables: Mapping[str, pl.DataFrame],
    clean_tables: Mapping[str, pl.DataFrame],
    *,
    context: PlausibilityContext | None = None,
    only: Iterable[str] | str | None = None,
    registry: Mapping[str, Any] | None = None,
) -> list[Problem]:
    """Every plausibility problem of the claims `tables` (and `anadata_clean` of `clean_tables`).

    `only` restricts the run to some check ids. `registry` is the parsed `cohort_registry.json`
    of the dataset: the ids in `REGISTRY_CHECKS` (the `labels.*` ones) compare the bill with its
    fault records and are skipped when it is None. The problems come in the order of `CHECKS`,
    then by `where`.
    """
    if only is None:
        selected = list(CHECKS)
    else:
        wanted = {only} if isinstance(only, str) else set(only)
        unknown = sorted(wanted - set(CHECKS))
        if unknown:
            raise KeyError(f"unregistered check id(s) {unknown}")
        selected = [check for check in CHECKS if check in wanted]
    if registry is None:
        selected = [check for check in selected if check not in REGISTRY_CHECKS]
    bill = _Bill(
        tables, clean_tables, context if context is not None else default_context(), registry
    )
    return [problem for check in selected for problem in CHECK_FUNCTIONS[check](bill)]


run_all = check_plausibility
