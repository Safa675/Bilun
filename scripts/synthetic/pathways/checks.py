"""Validity checks for care pathways.

Each check is a pure function (pathway, catalogs) -> list[Problem]; the ids it can emit are
registered in schema.CHECKS and each has a mutation test. `run_all` runs every check. Catalogs are
read once with Polars; nothing here imports the engine or the harness in reports/.

"In force" means the catalog has a row covering the day. A pathway is checked on EVERY day of its
service window, found by testing the window's edges and every day a catalog row begins or ends
inside it (the in-force set cannot change anywhere else).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Callable
from datetime import date, timedelta
from functools import cached_property
from pathlib import Path

import polars as pl
import yaml

from .loader import PATHWAYS_DIR, PathwayLoadError, load_pathway
from .schema import (
    BED_KINDS,
    BLOOD_PACKAGE_SHARES,
    ICU_KINDS,
    Pathway,
    Pins,
    Problem,
    anchors_for,
    course_overrun,
    day_expressions,
    included,
    last_day,
    pin_problems,
    resolve_days,
)

REPO = Path(__file__).resolve().parents[3]

# The curated EK-3/F-1 list is one snapshot in force from 13.12.2025
# (reports/synthetic-data/2026-10-15-showcase-proofs/harness.py, EK3F1_FROM).
EK3F1_FROM = "2025-12-13"
# The curated EK-3/C-2 list is the latest raw partition (scripts/sut/catalogs/hierarchical_materials.py, raw_latest):
# annex=EK-3C-2/effective_date=2026-01-24, the list "Yür. 24.01.2026" of the 2026-10-02 SUT. It carries no end date.
EK3C2_FROM = "2026-01-24"

# Line kinds of an EK-2B procedure that may stand beside an EK-2C package of its session (C000672, C000673; slice G15).
EK2B_SESSION_KINDS: tuple[str, ...] = ("procedure", "operation")

# Package window in days, counted from the day of the package (SUT 2.2.2.B-1(3): C000702-C000706).
PACKAGE_WINDOW_DAYS = {"A": 15, "B": 10, "C": 8, "D": 5, "E": 3}

# The EK-2B chapter group (ek2b_code_chapter.parquet group_id) of a `procedure` line that carries a session role.
SESSION_PROCEDURE_GROUP = "7"

# EK-2B chapter groups (ek2b_code_chapter.parquet group_id) a line kind may sit in.
KIND_GROUPS = [
    ("1", "bed"), ("1", "newborn_bed"), ("1", "icu_day"), ("1", "companion"), ("2", "exam"), ("3", "procedure"), ("4", "procedure"),
    ("5", "anaesthesia"), ("5", "procedure"), ("6", "operation"), ("7", "procedure"),
    ("8", "imaging"), ("8", "radiotherapy"), ("9", "lab"), ("10", "lab"),
]  # fmt: skip

# The EK-2B chapter (ek2b_code_chapter.parquet chapter_id) of a `radiotherapy` line, radyasyon onkolojisi; an `imaging`
# line is any other chapter of group 8 (nuclear medicine 8.2, radiological imaging 8.3).
RADIOTHERAPY_CHAPTER = "8.1"


def norm(text: str) -> str:
    """Whitespace-normalized text: names are compared in this form."""
    return " ".join(text.split())


def _norm(expr: pl.Expr) -> pl.Expr:
    return expr.str.replace_all(r"\s+", " ").str.strip_chars()


def _frame(rows: list[tuple], *columns: str) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=dict.fromkeys(columns, pl.String), orient="row")


def _named(rows: list[tuple[str, str, str]]) -> pl.DataFrame:
    """(code, name, where) rows as a frame, names whitespace-normalized."""
    return _frame(
        [(code, norm(name), where) for code, name, where in rows], "code", "name", "where"
    )


class Catalogs:
    """The catalog tables the checks compare with; each is read once, on first use."""

    def __init__(self, root: Path = REPO) -> None:
        self.root = Path(root)

    def _parquet(self, relative: str, columns: list[str]) -> pl.DataFrame:
        return pl.read_parquet(self.root / relative, columns=columns)

    @cached_property
    def code_sets(self) -> dict:
        path = self.root / "data/synthetic/reference/code_sets.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    @property
    def window(self) -> tuple[str, str]:
        return self.code_sets["window"]["start"], self.code_sets["window"]["end"]

    @cached_property
    def ek2b(self) -> pl.DataFrame:  # code, name, puan, valid_from, valid_to
        columns = ["code", "name", "puan", "valid_from", "valid_to"]
        frame = self._parquet("data/gazette/curated/ek2b_catalog_history.parquet", columns)
        return frame.with_columns(_norm(pl.col("name")))

    @cached_property
    def ek2c(self) -> pl.DataFrame:  # code, name, group, puan, valid_from, valid_to
        columns = ["package_code", "name", "group", "puan", "valid_from", "valid_to"]
        frame = self._parquet("data/gazette/curated/ek2c_catalog_history.parquet", columns)
        return frame.rename({"package_code": "code"}).with_columns(_norm(pl.col("name")))

    @cached_property
    def ek3f1(self) -> pl.DataFrame:  # code, name ("site | description"), valid_from, valid_to
        columns = ["sut_code", "material_name", "description"]
        frame = self._parquet("data/gazette/curated/ek3f1_arthroplasty_materials.parquet", columns)
        parts = [pl.when(pl.col(c) != "").then(pl.col(c)) for c in ("material_name", "description")]
        return frame.select(
            pl.col("sut_code").alias("code"),
            _norm(pl.concat_str(parts, separator=" | ", ignore_nulls=True)).alias("name"),
            pl.lit(EK3F1_FROM).alias("valid_from"),
            pl.lit(None, dtype=pl.String).alias("valid_to"),
        )

    @cached_property
    def ek3c2(self) -> pl.DataFrame:  # code, name (the device's name), valid_from, valid_to
        # The description of an EK-3/C-2 row is the report it needs, not part of the name.
        columns = ["sut_code", "material_name"]
        frame = self._parquet("data/gazette/curated/ek3c2_materials.parquet", columns)
        return frame.select(
            pl.col("sut_code").alias("code"),
            _norm(pl.col("material_name")).alias("name"),
            pl.lit(EK3C2_FROM).alias("valid_from"),
            pl.lit(None, dtype=pl.String).alias("valid_to"),
        )

    def ek3(self, annex: str) -> pl.DataFrame:
        """The catalog frame of an EK-3 annex a material line names (`Material.annex`)."""
        return {"EK-3F-1": self.ek3f1, "EK-3C-2": self.ek3c2}[annex]

    @cached_property
    def ek4a(self) -> pl.DataFrame:  # code (the barcode), name, valid_from, valid_to (last day)
        columns = ["barcode", "drug_name", "valid_from", "valid_until"]
        frame = self._parquet("data/gazette/curated/ek4a_history.parquet", columns)
        # EK-4A rows are half-open, [valid_from, valid_until): the last day in force is the day before.
        last_day = pl.col("valid_until").str.to_date().dt.offset_by("-1d").cast(pl.String)
        renamed = {"barcode": "code", "drug_name": "name"}
        return (
            frame.with_columns(last_day.alias("valid_to"))
            .drop("valid_until")
            .rename(renamed)
            .with_columns(_norm(pl.col("name")))
        )

    @cached_property
    def crosswalk(self) -> pl.DataFrame:  # barcode, active_ingredient
        path = "data/synthetic/reference/drug_crosswalk.parquet"
        return self._parquet(path, ["barcode", "active_ingredient"])

    @cached_property
    def icd(self) -> pl.DataFrame:  # code, name_tr, is_active, sex, is_leaf
        path = "data/synthetic/reference/icd10_tr.parquet"
        columns = ["code", "name_tr", "is_active", "sex", "is_leaf"]
        return self._parquet(path, columns).with_columns(_norm(pl.col("name_tr")))

    @cached_property
    def labs(self) -> pl.DataFrame:  # ek2b_code, catalog_name
        path = self.root / "data/synthetic/reference/lab_reference.csv"
        table = pl.read_csv(path, infer_schema=False)
        return table.select("ek2b_code", _norm(pl.col("catalog_name"))).unique()

    @cached_property
    def specialties(self) -> set[str]:
        path = "data/gazette/curated/ek2a_outpatient_visits.parquet"
        return set(self._parquet(path, ["specialty_code"])["specialty_code"])

    @cached_property
    def chapters(self) -> pl.DataFrame:  # code, group_id, chapter_id
        path = "data/synthetic/reference/ek2b_code_chapter.parquet"
        return self._parquet(path, ["code", "group_id", "chapter_id"])

    @cached_property
    def clause_ids(self) -> set[str]:
        clauses = self._parquet("data/gazette/sut_clauses.parquet", ["clause_id", "is_in_force"])
        return set(clauses.filter(pl.col("is_in_force"))["clause_id"])


# --- catalog coverage over the window ----------------------------------------------------------


def probe_days(rows: pl.DataFrame, start: str, end: str) -> list[str]:
    """The window's edges and every day a row begins or ends inside it."""
    ends = rows["valid_to"].drop_nulls()
    day_after = ends.str.to_date().dt.offset_by("1d").cast(pl.String)
    inside = [d for d in (*rows["valid_from"], *ends, *day_after) if start <= d <= end]
    return sorted({start, end, *inside})


def in_force(rows: pl.DataFrame, codes: list[str], days: list[str], *extra: str) -> pl.DataFrame:
    """Per code and probe day: rows in force (n), their names, and the first value of `extra`."""
    hit = (pl.col("valid_from") <= pl.col("day")) & (
        pl.col("valid_to").is_null() | (pl.col("valid_to") >= pl.col("day"))
    )
    grid = pl.DataFrame({"code": codes}, schema={"code": pl.String}).join(
        pl.DataFrame({"day": days}), how="cross"
    )
    aggregates = [
        hit.sum().alias("n"),
        pl.col("name").filter(hit).unique().sort().alias("names"),
        *[pl.col(c).filter(hit).first().alias(c) for c in extra],
    ]
    joined = grid.join(rows.filter(pl.col("code").is_in(codes)), on="code", how="left")
    return joined.group_by("code", "day", maintain_order=True).agg(aggregates)


def identity_problems(
    occurrences: pl.DataFrame, rows: pl.DataFrame, window: tuple[str, str], prefix: str
) -> list[Problem]:
    """`occurrences` has code, name (normalized) and where; emits <prefix>.in_force and .name."""
    if occurrences.is_empty():
        return []
    codes = occurrences["code"].unique().sort().to_list()
    used = rows.filter(pl.col("code").is_in(codes))
    coverage = in_force(used, codes, probe_days(used, *window))
    gone = (
        coverage.filter(pl.col("n") == 0)
        .group_by("code")
        .agg(pl.col("day").min().alias("first"), pl.len().alias("days"))
    )
    wrong = (
        coverage.filter(pl.col("n") > 0)
        .join(occurrences, on="code")
        .filter(
            (pl.col("names").list.len() != 1) | (pl.col("names").list.first() != pl.col("name"))
        )
        .group_by("where", "code", "name", maintain_order=True)
        .agg(pl.col("day").first(), pl.col("names").first().alias("catalog"))
    )
    out = [
        Problem(
            f"{prefix}.in_force",
            r["where"],
            f"{r['code']} is not in force on {r['first']} ({r['days']} probe day(s) of the window)",
        )
        for r in occurrences.join(gone, on="code").iter_rows(named=True)
    ]
    out += [
        Problem(
            f"{prefix}.name",
            r["where"],
            f"{r['code']}: name {r['name']!r}; the catalog says {r['catalog']} on {r['day']}",
        )
        for r in wrong.iter_rows(named=True)
    ]
    return out


def effective_window(pathway: Pathway, catalogs: Catalogs) -> tuple[str, str]:
    w = pathway.window
    return (w.start, w.end) if w else catalogs.window


def _procedure_occurrences(pathway: Pathway) -> pl.DataFrame:
    """Every EK-2B/EK-2C code the pathway names, as code, name, where, kind."""
    rows = []
    for line in pathway.procedures:
        if line.items:
            where = f"procedures[{line.id}].items"
            rows += [(i.code, norm(i.name), f"{where}[{i.code}]", line.kind) for i in line.items]
        else:
            rows.append((line.code, norm(line.name), f"procedures[{line.id}]", line.kind))
    rows += [(p.code, norm(p.name), f"performed[{p.id}]", "performed") for p in pathway.performed]
    return _frame(rows, "code", "name", "where", "kind")


# --- identity checks ---------------------------------------------------------------------------


def check_procedures(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """procedure.in_force, procedure.name: EK-2B codes, and EK-2C packages (P-codes)."""
    occ = _procedure_occurrences(pathway)
    window = effective_window(pathway, cat)
    package = pl.col("code").str.starts_with("P")
    packages = identity_problems(occ.filter(package), cat.ek2c, window, "procedure")
    return packages + identity_problems(occ.filter(~package), cat.ek2b, window, "procedure")


def check_procedure_kinds(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """procedure.kind: the declared kind must fit the code's EK-2B chapter and the code sets.

    The two ICU kinds are bed-day lines of their own: `icu_day` is the day rate 510090 (EK-2B chapter 1)
    and `icu_package` an EK-2C ICU package (P552001-3, P552006-8; a package has no EK-2B chapter). The
    newborn bed (`newborn_bed`) is the incubator 510070 or the cot 510081, never the ward bed. In group 8 a
    `radiotherapy` line is a code of chapter 8.1 (radiation oncology) and an `imaging` line a code of any other chapter.
    """
    beds, anaesthesia = cat.code_sets["beds"], cat.code_sets["anaesthesia"]
    ward_beds = [beds["ward_day"]["code"], beds["day_bed"]["code"]]
    newborn_beds = [beds["incubator"]["code"], beds["cot"]["code"]]
    icu_packages = [
        tier["code"] for group in cat.code_sets["icu_packages"].values() for tier in group.values()
    ]
    anaesthesia_codes = [
        *anaesthesia["single"].values(),
        *anaesthesia["multiple_operations"].values(),
    ]
    kind, code = pl.col("kind"), pl.col("code")
    fits_code = (
        pl.when(kind == "bed").then(code.is_in(ward_beds))
        .when(kind == "newborn_bed").then(code.is_in(newborn_beds))
        .when(kind == "icu_day").then(code == beds["icu_day_fee_for_service"]["code"])
        .when(kind == "icu_package").then(code.is_in(icu_packages))
        .when(kind == "companion").then(code == beds["companion"]["code"])
        .when(kind == "anaesthesia").then(code.is_in(anaesthesia_codes))
        .when(kind == "package").then(code.str.starts_with("P"))
        .when(kind == "radiotherapy").then(pl.col("chapter_id") == RADIOTHERAPY_CHAPTER)
        .when(kind == "imaging").then(pl.col("chapter_id") != RADIOTHERAPY_CHAPTER)
        .otherwise(~code.str.starts_with("P"))
    )  # fmt: skip
    allowed = _frame(KIND_GROUPS, "group_id", "kind").with_columns(pl.lit(True).alias("paired"))
    occ = _procedure_occurrences(pathway).filter(kind != "performed")
    bad = (
        occ.join(cat.chapters, on="code", how="left")
        .join(allowed, on=["group_id", "kind"], how="left")
        # a code missing from the chapter table is procedure.in_force's business
        .filter(kind.is_in(["package", "icu_package"]) | pl.col("group_id").is_not_null())
        .filter(~fits_code | (~kind.is_in(["package", "icu_package"]) & pl.col("paired").is_null()))
    )
    out = [
        Problem(
            "procedure.kind",
            r["where"],
            f"{r['code']} (EK-2B group {r['group_id']}) does not fit kind {r['kind']}",
        )
        for r in bad.iter_rows(named=True)
    ]
    # A procedure that carries a session role is the add-on of a session: a chapter 7 code (EK-2B group 7).
    roled = _frame(
        [
            (line.code, f"procedures[{line.id}]")
            for line in pathway.procedures
            if line.kind == "procedure" and line.session_role
        ],
        "code",
        "where",
    )
    off_chapter = roled.join(cat.chapters, on="code", how="left").filter(
        pl.col("group_id") != SESSION_PROCEDURE_GROUP
    )
    why = f"cannot carry a session_role: only operations, packages and group {SESSION_PROCEDURE_GROUP} procedures can"
    return out + [
        Problem("procedure.kind", r["where"], f"{r['code']} (EK-2B group {r['group_id']}) {why}")
        for r in off_chapter.iter_rows(named=True)
    ]


def check_materials(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """material.in_force, material.name: each code in its annex's list (EK-3/F-1 from 2025-12-13, EK-3/C-2 from
    2026-01-24; each one list without an end date)."""
    out: list[Problem] = []
    for annex in sorted({m.annex for m in pathway.materials}):
        rows = [(m.code, m.name, f"materials[{m.id}]") for m in pathway.materials if m.annex == annex]
        out += identity_problems(_named(rows), cat.ek3(annex), effective_window(pathway, cat), "material")
    return out


def check_drugs(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """drug.in_force, drug.name (EK-4A) and drug.inn (the crosswalk's active ingredient)."""
    occ = _named([(d.barcode, d.name, f"drugs[{d.id}]") for d in pathway.drugs])
    out = identity_problems(occ, cat.ek4a, effective_window(pathway, cat), "drug")
    declared = _named([(d.barcode, d.inn, f"drugs[{d.id}]") for d in pathway.drugs]).rename(
        {"code": "barcode", "name": "inn"}
    )
    known = cat.crosswalk.select("barcode", _norm(pl.col("active_ingredient")).alias("catalog"))
    wrong = declared.join(known, on="barcode", how="left").filter(
        pl.col("catalog").is_null() | (pl.col("catalog") != pl.col("inn"))
    )
    out += [
        Problem(
            "drug.inn",
            r["where"],
            f"inn {r['inn']!r}; the crosswalk's active ingredient for {r['barcode']} is {r['catalog']!r}",
        )
        for r in wrong.iter_rows(named=True)
    ]
    return out


def check_icd(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """icd.exists, icd.active, icd.leaf, icd.name, icd.sex_gate against the SKRS table."""
    occ = _named([(d.icd10, d.name, f"diagnoses[{d.icd10}]") for d in pathway.diagnoses])
    joined = occ.join(cat.icd, on="code", how="left")
    sexes = pathway.patient.sex.values
    only = sexes[0] if len(sexes) == 1 else None
    tests = {
        "icd.exists": (pl.col("name_tr").is_null(), "is not in the SKRS table"),
        "icd.active": (pl.col("is_active").not_().fill_null(False), "is not active in the SKRS table"),
        "icd.leaf": (pl.col("is_leaf").not_().fill_null(False), "is not a leaf code; code the specific one"),
        "icd.name": (pl.col("name_tr").is_not_null() & (pl.col("name_tr") != pl.col("name")), "has another name_tr"),
        "icd.sex_gate": (
            pl.col("sex").is_not_null() & (pl.lit(only).is_null() | (pl.col("sex") != pl.lit(only))),
            f"is limited to one sex, but the pathway allows {sexes}",
        ),
    }  # fmt: skip
    return [
        Problem(
            check,
            r["where"],
            f"{r['code']} {what}" + (f" (name_tr {r['name_tr']!r})" if check == "icd.name" else ""),
        )
        for check, (condition, what) in tests.items()
        for r in joined.filter(condition).iter_rows(named=True)
    ]


def check_labs(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """lab.in_table, lab.name: every L-code must be in lab_reference.csv under its catalog name."""
    occ = _procedure_occurrences(pathway).filter(pl.col("code").str.contains(r"^L[0-9]{6}$"))
    joined = occ.join(cat.labs, left_on="code", right_on="ek2b_code", how="left")
    missing = joined.filter(pl.col("catalog_name").is_null())
    renamed = joined.filter(
        pl.col("catalog_name").is_not_null() & (pl.col("catalog_name") != pl.col("name"))
    )
    return [
        Problem("lab.in_table", r["where"], f"{r['code']} is not in lab_reference.csv")
        for r in missing.iter_rows(named=True)
    ] + [
        Problem("lab.name", r["where"], f"{r['code']}: the table says {r['catalog_name']!r}")
        for r in renamed.iter_rows(named=True)
    ]


def check_specialties(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """specialty.exists: every EK-2A branch code the pathway uses."""
    used = [("department.specialty", pathway.department.specialty)]
    used += [
        (f"procedures[{p.id}].specialty", p.specialty) for p in pathway.procedures if p.specialty
    ]
    return [
        Problem("specialty.exists", where, f"{code} is not an EK-2A branch code")
        for where, code in used
        if code not in cat.specialties
    ]


# --- billing logic -----------------------------------------------------------------------------


def dialysis_package_codes(cat: Catalogs) -> list[str]:
    """The EK-2C haemodialysis session packages of `code_sets.yaml` (P704230 chronic, P704210 emergency)."""
    return [entry["code"] for entry in cat.code_sets["dialysis_packages"].values()]


def check_package_mode(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """package.mode: a package bill holds package lines (and linked materials), nothing else.

    An ICU package (kind icu_package) is no surgical package: it is a per-day bed line billed beside
    itemized lines (SUT 2.4.4.H.(2)), so an itemized pathway may hold it. A package bill may not hold
    an ICU line of either kind: the engine prices a package stay by the package, not by ICU days. The
    same goes for a newborn bed line (kind newborn_bed): the package includes the bed (C000685 to C000699).
    A bill of haemodialysis session packages only (P704230, P704210) may hold drug lines: the session
    price includes the tests, the drugs of a complication of the session, heparin and the day bed
    (C000969, C004117), not an erythropoiesis-stimulating agent, which is billed apart (SUT 4.2.9.A-1).
    A blood component of C000694 (red cells 705371 and the others of `BLOOD_PACKAGE_SHARES`) is inside the package
    too, but the provider bills it apart at a share of its puan (SUT 2.2.2.B-1.(1).e, 4.6.(4): C000694, C007927), so a
    package bill may hold it as a line of kind procedure; `expand` bills it at that share (slice G14).
    An EK-2B procedure done in the session of an EK-2C package (a line of kind procedure or operation with the role
    same_incision or separate_incision, beside a package line with the role primary) is billed beside the package at
    30 % or 50 % of its own puan (SUT 2.2.2.B(3)(c), (ç): C000672, C000673; slice G15); `expand` bills it at that share
    and `session.order` checks that the package's puan leads (else the whole session goes itemized, C000672).
    """
    if pathway.billing_mode == "itemized":
        return [
            Problem(
                "package.mode", f"procedures[{p.id}]", "an itemized pathway has no package line"
            )
            for p in pathway.procedures
            if p.kind == "package"
        ]
    why = "inside the package (SUT 2.2.2.B-1(1): C000685 to C000699); remove it"
    dialysis = set(dialysis_package_codes(cat))
    sessions_only = all(p.code in dialysis for p in pathway.procedures if p.kind == "package")
    led = any(p.kind == "package" and p.session_role == "primary" for p in pathway.procedures)

    def beside_the_package(p) -> bool:  # an EK-2B line of the package's session (C000672, C000673)
        return led and p.kind in EK2B_SESSION_KINDS and p.session_role in ("same_incision", "separate_incision")

    return [
        Problem("package.mode", f"procedures[{p.id}]", f"a {p.kind} line is {why}")
        for p in pathway.procedures
        if p.kind != "package"
        and not (p.kind == "procedure" and p.code in BLOOD_PACKAGE_SHARES)
        and not beside_the_package(p)
    ] + [
        Problem("package.mode", f"drugs[{d.id}]", f"drugs are {why}")
        for d in pathway.drugs
        if not sessions_only
    ]


def check_package_window(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """package.window: the longest stay ends inside the package window of each package's group.

    An ICU package (kind icu_package) has no EK-2C group and no window: it is one bed day, and the
    days it may sit on are `icu.day_pattern`'s business. A haemodialysis session package (P704230,
    P704210) has no group either: it is one session. Only the surgical packages are tested here.
    """
    dialysis = set(dialysis_package_codes(cat))
    packages = [p for p in pathway.procedures if p.kind == "package" and p.code and p.code not in dialysis]
    if pathway.billing_mode != "package" or pathway.nights is None or not packages:
        return []
    codes = sorted({p.code for p in packages})
    used = cat.ek2c.filter(pl.col("code").is_in(codes))
    groups = in_force(used, codes, probe_days(used, *effective_window(pathway, cat)), "group")
    anchors = anchors_for(pathway, pathway.nights.max)
    out = []
    for line in packages:
        needs = pathway.nights.max - resolve_days(line.days[0], anchors)[0] + 1
        mine = groups.filter(pl.col("code") == line.code)["group"].drop_nulls()
        letters = {g[:1] for g in mine if g}
        where = f"procedures[{line.id}]"
        if not letters:
            out.append(Problem("package.window", where, f"{line.code} has no group in EK-2C"))
            continue
        allowed = min(PACKAGE_WINDOW_DAYS[letter] for letter in letters)
        if needs > allowed:
            why = f"{needs} days from the package day to the longest discharge; its window is {allowed} days"
            out.append(Problem("package.window", where, f"{why} (C000702 to C000706)"))
    return out


def _group_expr(total: pl.Expr, lower_bounds: dict[str, int]) -> pl.Expr:
    """The anaesthesia group whose puan band holds `total` (surgical_group_bands, highest first)."""
    bands = sorted(lower_bounds.items(), key=lambda item: -item[1])
    chain = pl.when(total >= bands[0][1]).then(pl.lit(bands[0][0]))
    for group, low in bands[1:]:
        chain = chain.when(total >= low).then(pl.lit(group))
    return chain


def _with_groups(totals: pl.DataFrame, bands: list[dict]) -> pl.DataFrame:
    """Add `group` to (day, total) rows, using the band table in force on each day."""
    parts = []
    for index, table in enumerate(bands):
        until = bands[index + 1]["effective_from"] if index + 1 < len(bands) else "9999-12-31"
        in_table = (pl.col("day") >= table["effective_from"]) & (pl.col("day") < until)
        chunk = totals.filter(in_table)
        parts.append(
            chunk.with_columns(_group_expr(pl.col("total"), table["lower_bounds"]).alias("group"))
        )
    return pl.concat(parts)


def check_anaesthesia(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """anaesthesia.code (belongs to its group), anaesthesia.group (the puan band, every probe day)."""
    lines = [p for p in pathway.procedures if p.kind == "anaesthesia"]
    if not lines:
        return []
    sets = cat.code_sets
    start, end = effective_window(pathway, cat)
    bands = sets["surgical_group_bands"]
    by_id = {p.id: p for p in pathway.procedures}
    codes = sorted({by_id[i].code for line in lines for i in line.operations})
    used = cat.ek2b.filter(pl.col("code").is_in(codes))
    switches = [b["effective_from"] for b in bands if start <= b["effective_from"] <= end]
    puan = in_force(used, codes, sorted({*probe_days(used, start, end), *switches}), "puan")
    out = []
    for line in lines:
        mode = "single" if len(line.operations) == 1 else "multiple_operations"
        expected = sets["anaesthesia"][mode][line.group]
        where = f"procedures[{line.id}]"
        if line.code != expected:
            out.append(
                Problem(
                    "anaesthesia.code",
                    where,
                    f"group {line.group} ({mode}) is {expected}, not {line.code}",
                )
            )
        mine = puan.filter(pl.col("code").is_in([by_id[i].code for i in line.operations]))
        totals = (
            mine.group_by("day")
            .agg(pl.col("puan").sum().alias("total"), pl.col("puan").count().alias("seen"))
            # a day on which an operation is not in force is procedure.in_force's business
            .filter(pl.col("seen") == len(line.operations))
        )
        wrong = _with_groups(totals, bands).filter(pl.col("group") != line.group).sort("day")
        out += [
            Problem(
                "anaesthesia.group",
                where,
                f"on {r['day']} puan {r['total']:.2f} is group {r['group']}, not {line.group}",
            )
            for r in wrong.head(1).iter_rows(named=True)
        ]
    return out


def check_sessions(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """session.primary (one primary per session day), session.order (it has the top puan)."""
    pins = pathway.showcase
    if pathway.claim_type == "yatis" and pins.nights is None:
        return []  # pins.missing says so
    anchors = anchors_for(pathway, pins.nights)
    sessions: dict[int, list] = {}
    for line in pathway.procedures:
        if line.session_role and included(line, pins):
            sessions.setdefault(resolve_days(line.days[0], anchors)[0], []).append(line)
    # each code's puan from its own list: EK-2C for a package code, EK-2B for the others (a session of a package bill
    # may hold EK-2B lines beside the package, C000672 and C000673: slice G15)
    columns = ["code", "name", "puan", "valid_from", "valid_to"]
    history = pl.concat(
        [
            cat.ek2c.select(columns).filter(pl.col("code").str.starts_with("P")),
            cat.ek2b.select(columns).filter(~pl.col("code").str.starts_with("P")),
        ]
    )
    window = effective_window(pathway, cat)
    out = []
    for day, lines in sorted(sessions.items()):
        primaries = [line for line in lines if line.session_role == "primary"]
        where = f"procedures[{', '.join(line.id for line in lines)}]"
        if len(primaries) != 1:
            out.append(
                Problem(
                    "session.primary",
                    where,
                    f"day {day}: {len(primaries)} primary operations; exactly one is needed",
                )
            )
            continue
        codes = sorted({line.code for line in lines})
        used = history.filter(pl.col("code").is_in(codes))
        puan = in_force(used, codes, probe_days(used, *window), "puan")
        top = puan.group_by("day").agg(pl.col("puan").max().alias("top"))
        below = (
            puan.filter(pl.col("code") == primaries[0].code)
            .join(top, on="day")
            .filter(pl.col("puan") < pl.col("top"))
            .sort("day")
        )
        out += [
            Problem(
                "session.order",
                where,
                f"on {r['day']} the primary {primaries[0].code} (puan {r['puan']:.2f}) is below another operation ({r['top']:.2f})",
            )
            for r in below.head(1).iter_rows(named=True)
        ]
    return out


# --- days, courses, pins, window, sources (no catalog needed) ----------------------------------


def _stay_cases(pathway: Pathway) -> list[int | None]:
    """The nights to test: shortest, longest and the showcase's; [None] for a pathway without a stay."""
    if pathway.nights is None:
        return [None]
    shown = [pathway.showcase.nights] if pathway.showcase.nights is not None else []
    return sorted({pathway.nights.min, pathway.nights.max, *shown})


def _day_cases(pathway: Pathway) -> list[int | None]:
    """The last days to test: the nights of a stay, the span of a session claim (shortest, longest, the showcase's);
    [None] for a visit of one date."""
    if pathway.span is None:
        return _stay_cases(pathway)
    shown = [pathway.showcase.span] if pathway.showcase.span is not None else []
    return sorted({pathway.span.min, pathway.span.max, *shown})


_DAY_FAULTS = {
    "days.in_stay": "reaches outside the stay (day 0 is admit, the last day is discharge) or is an empty range",
    "days.duplicate": "puts a line on one day twice",
}


def check_days(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """days.in_stay (every day inside the stay, or the span of a session claim), days.duplicate (a line twice on one day)."""
    failures: dict[tuple[str, str, str], list[int | None]] = {}
    for nights in _day_cases(pathway):
        anchors = anchors_for(pathway, nights)
        for where, expr in day_expressions(pathway):
            days = resolve_days(expr, anchors)
            if not days or any(not 0 <= d <= (nights or 0) for d in days):
                failures.setdefault(("days.in_stay", where, expr), []).append(nights)
        for line in pathway.procedures:
            seen = [d for expr in line.days for d in resolve_days(expr, anchors)]
            if len(seen) != len(set(seen)):
                failures.setdefault(
                    ("days.duplicate", f"procedures[{line.id}]", str(line.days)), []
                ).append(nights)
    return [
        Problem(check, where, f"{expr!r} {_DAY_FAULTS[check]}; nights tested: {nights}")
        for (check, where, expr), nights in failures.items()
    ]


# A stay line covers admit..discharge + offset: a bed every calendar day, a companion every night. A
# newborn bed line is a bed line (the day's one bed): its coverage is judged together with the ward
# bed lines (`_bed_coverage_problems`), not line by line.
STAY_LINE_END = {"bed": 0, "companion": -1}


def _icu_lines(pathway: Pathway) -> list:
    return [line for line in pathway.procedures if line.kind in ICU_KINDS]


def _days_of(lines: list, anchors: dict[str, int]) -> list[int]:
    return sorted(d for line in lines for expr in line.days for d in resolve_days(expr, anchors))


def _icu_coverage_problems(pathway: Pathway) -> list[Problem]:
    """The ICU lines are the bed lines of an ICU stay: admit..discharge-1, once each, none on the transfer day.

    Intensive care is billed for `discharge - admission` days (src/bilun/domain/prose_rules/icu_puani.py),
    so the discharge day is the transfer day and carries no ICU line. A ward bed beside ICU days would
    make the engine count the whole stay as ICU days, so a ward bed line is a defect on an ICU stay.
    """
    lines = _icu_lines(pathway)
    ids = ", ".join(line.id for line in lines)
    out = [
        Problem(
            "stay.coverage",
            f"procedures[{line.id}]",
            f"a {'newborn' if line.kind == 'newborn_bed' else 'ward'} bed line on an ICU stay: "
            "the ICU lines are the bed lines of the bill",
        )
        for line in pathway.procedures
        if line.kind in BED_KINDS
    ]
    if pathway.nights is None:
        return out + [
            Problem("stay.coverage", f"procedures[{ids}]", "an ICU line needs a stay, not a visit")
        ]
    faults = []
    for nights in _stay_cases(pathway):
        seen = Counter(_days_of(lines, anchors_for(pathway, nights)))
        missing = [d for d in range(nights) if not seen[d]]
        twice = sorted(d for d, n in seen.items() if n > 1)
        transfer = seen[nights]
        if missing or twice or transfer:
            parts = [
                (f"no ICU line on days {missing}", bool(missing)),
                (f"two ICU lines on days {twice}", bool(twice)),
                ("an ICU line on the discharge day", bool(transfer)),
            ]
            faults.append(f"{nights} nights: " + ", ".join(text for text, bad in parts if bad))
    if faults:
        why = "ICU lines must cover admit..discharge-1 once each and not the discharge day (the transfer day)"
        out.append(Problem("stay.coverage", f"procedures[{ids}]", f"{why}; {'; '.join(faults)}"))
    return out


def _bed_coverage_problems(pathway: Pathway) -> list[Problem]:
    """The ward and the newborn bed lines of a newborn stay are the day's one bed: admit..discharge, once each.

    EK-2B gives 510010, 510070 and 510081 the same text (yemek + yatak + vizit): they are alternatives
    for one patient-day, so a day holds exactly one of them (the engine reads a ward bed beside a newborn
    bed as double billing, `claim_yatak_newborn_overlap`), and the discharge day is billed like any other.
    """
    lines = [line for line in pathway.procedures if line.kind in BED_KINDS]
    ids = ", ".join(line.id for line in lines)
    if pathway.nights is None:
        return [Problem("stay.coverage", f"procedures[{ids}]", "a newborn bed line needs a stay, not a visit")]
    faults = []
    for nights in _stay_cases(pathway):
        seen = Counter(_days_of(lines, anchors_for(pathway, nights)))
        missing = [d for d in range(nights + 1) if not seen[d]]
        twice = sorted(d for d, n in seen.items() if n > 1)
        outside = sorted(d for d in seen if not 0 <= d <= nights)
        if missing or twice or outside:
            parts = [
                (f"no bed line on days {missing}", bool(missing)),
                (f"two bed lines on days {twice}", bool(twice)),
                (f"a bed line on days {outside}, outside the stay", bool(outside)),
            ]
            faults.append(f"{nights} nights: " + ", ".join(text for text, bad in parts if bad))
    if not faults:
        return []
    why = "ward and newborn bed lines must cover admit..discharge once each"
    return [Problem("stay.coverage", f"procedures[{ids}]", f"{why}; {'; '.join(faults)}")]


def check_stay_coverage(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """stay.coverage: a bed line covers admit..discharge, a companion admit..discharge-1, at every stay.

    On a newborn stay (a line of kind newborn_bed) the ward and newborn bed lines together cover
    admit..discharge once each. On an ICU stay (a line of kind icu_day or icu_package) the ICU lines take
    the bed lines' place: they cover admit..discharge-1 once each, and a ward or newborn bed line is a
    defect. A ward stay that arrives from an ICU bill (`arrives_from_icu`) has its first day's bed paid by
    that bill: its bed line covers admit+1..discharge, and it has no ICU or newborn line of its own.
    """
    icu_stay = bool(_icu_lines(pathway))
    newborn_stay = any(line.kind == "newborn_bed" for line in pathway.procedures)
    out = _icu_coverage_problems(pathway) if icu_stay else []
    if newborn_stay and not icu_stay:
        out += _bed_coverage_problems(pathway)
    arrival = pathway.arrives_from_icu
    if arrival and (icu_stay or newborn_stay):
        out.append(
            Problem(
                "stay.coverage",
                "arrives_from_icu",
                "a ward stay that arrives from an ICU bill has no ICU or newborn bed line of its own",
            )
        )
    for line in pathway.procedures:
        if line.kind not in STAY_LINE_END or (line.kind == "bed" and (icu_stay or newborn_stay)):
            continue
        first = 1 if arrival and line.kind == "bed" else 0
        faults = []
        for nights in _stay_cases(pathway):
            if nights is None:
                continue
            anchors = anchors_for(pathway, nights)
            got = {d for expr in line.days for d in resolve_days(expr, anchors)}
            want = set(range(first, nights + 1 + STAY_LINE_END[line.kind]))
            if got != want:
                faults.append(f"{nights} nights: days {sorted(got)}, expected {sorted(want)}")
        if faults:
            start = "admit+1" if first else "admit"
            end = "discharge" + ("-1" if line.kind == "companion" else "")
            message = f"a {line.kind} line must cover {start}..{end}; {'; '.join(faults)}"
            out.append(Problem("stay.coverage", f"procedures[{line.id}]", message))
    return out


def check_icu_day_pattern(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """icu.day_pattern: 510090 on the first and the last ICU day, one package tier on every day between.

    SUT 2.4.4.H.(8) (C001243): the first day and the day the patient leaves intensive care are billed
    per service (510090), the days between from EK-2/C. The engine prices the intermediate days at the
    tier of the first package line it finds, so one tier per stay. The ICU days of a bill are
    admit..discharge-1; a one-night stay has one day (the first is the last), a two-night stay has no
    day between.
    """
    day_lines = [line for line in pathway.procedures if line.kind == "icu_day"]
    package_lines = [line for line in pathway.procedures if line.kind == "icu_package"]
    if pathway.nights is None or not (day_lines or package_lines):
        return []  # stay.coverage says an ICU line needs a stay
    faults = []
    for nights in _stay_cases(pathway):
        anchors = anchors_for(pathway, nights)
        expected = {
            "510090": sorted({0, nights - 1}),
            "package": list(range(1, nights - 1)),
        }
        got = {"510090": _days_of(day_lines, anchors), "package": _days_of(package_lines, anchors)}
        for name, want in expected.items():
            if got[name] != want:
                faults.append(f"{nights} nights: {name} on days {got[name]}, expected {want}")
    out = []
    if faults:
        where = f"procedures[{', '.join(line.id for line in (*day_lines, *package_lines))}]"
        out.append(Problem("icu.day_pattern", where, "; ".join(faults)))
    codes = sorted({line.code for line in package_lines})
    if len(codes) > 1:
        message = f"{', '.join(codes)}: one package tier per stay (the engine prices every day at the first)"
        out.append(Problem("icu.day_pattern", f"procedures[{', '.join(l.id for l in package_lines)}]", message))
    return out


def check_drug_courses(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """drug.course: a per_night drug starts on admit; the shortest course fits the shortest stay.

    A pinned course that outlasts the pinned stay is pin_problems' business (check_pins).
    """
    out = []
    for drug in pathway.drugs:
        where = f"drugs[{drug.id}]"
        starts = (resolve_days(drug.day, anchors_for(pathway, n))[0] for n in _stay_cases(pathway))
        if drug.per_night and any(starts):
            out.append(Problem("drug.course", where, "a per_night drug starts on admit"))
        if drug.per_day:
            # the shortest stay, the shortest span of a session claim; a visit is one day
            span = pathway.nights or pathway.span
            shortest = span.min if span is not None else None
            days = drug.course_days.min
            late = course_overrun(pathway, drug, shortest, days)
            if late > 0:
                last = shortest or 0
                message = (
                    f"shortest stay: {days} days end {late} day(s) after the discharge (day {last})"
                )
                out.append(Problem("drug.course", where, message))
    return out


def check_drug_indications(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """drug.indication: the diagnosis a drug names is in the pathway and is never optional."""
    diagnoses = {d.icd10: d for d in pathway.diagnoses}
    out = []
    for drug in pathway.drugs:
        found = diagnoses.get(drug.indication) if drug.indication else None
        if drug.indication and found is None:
            problem = f"{drug.indication} is not a diagnosis of this pathway"
        elif found is not None and found.optional:
            problem = (
                f"{drug.indication} is optional: the drug could be billed without its indication"
            )
        else:
            continue
        out.append(Problem("drug.indication", f"drugs[{drug.id}]", problem))
    return out


def pins_problems(pathway: Pathway, pins: Pins, cat: Catalogs) -> list[Problem]:
    """pins.*: `pins` obey the declared ranges of `pathway`, and the stay is inside the window.

    The pins are the pathway's own showcase block (`check_pins`) or the pins of one encounter of a recipe
    (a recipe may override them): the rules are the same.
    """
    out = pin_problems(pathway, pins)
    start, end = effective_window(pathway, cat)
    last = (date.fromisoformat(pins.admit) + timedelta(days=last_day(pathway, pins))).isoformat()
    if pins.admit < start or last > end:
        out.append(
            Problem(
                "pins.window",
                "showcase.admit",
                f"{pins.admit}..{last} is outside the window {start}..{end}",
            )
        )
    return out


def check_pins(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """pins.*: the showcase pins obey the declared ranges, and the stay is inside the window."""
    return pins_problems(pathway, pathway.showcase, cat)


def check_window(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """window.valid: a pathway may narrow the default window, not widen it."""
    start, end = cat.window
    w = pathway.window
    if w and (w.start < start or w.end > end):
        return [
            Problem(
                "window.valid",
                "window",
                f"{w.start}..{w.end} is outside the default window {start}..{end}",
            )
        ]
    return []


def _sources(node: object, where: str = "") -> list[tuple[str, str | None, str]]:
    """(where, basis, source) for every item of a dumped pathway that has a source (a window: no basis)."""
    found = []
    if isinstance(node, dict):
        if "source" in node:
            found.append((where, node.get("basis"), node["source"]))
        for key, value in node.items():
            found += _sources(value, f"{where}.{key}" if where else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            label = (value.get("id") or value.get("icd10")) if isinstance(value, dict) else None
            found += _sources(value, f"{where}[{label or index}]")
    return found


def check_sources(pathway: Pathway, cat: Catalogs) -> list[Problem]:
    """source.clause_exists (every cited C000000 is an in-force SUT clause), source.sut_cites."""
    out = []
    for where, basis, source in _sources(pathway.model_dump(exclude={"showcase"})):
        clauses = sorted(set(re.findall(r"\bC[0-9]{6}\b", source)))
        out += [
            Problem(
                "source.clause_exists",
                where,
                f"{c} is not an in-force clause of sut_clauses.parquet",
            )
            for c in clauses
            if c not in cat.clause_ids
        ]
        if basis == "sut" and not clauses and not re.search(r"\bEK-[0-9]", source):
            out.append(
                Problem(
                    "source.sut_cites",
                    where,
                    "basis sut needs a clause id (C000000) or an annex (EK-2B)",
                )
            )
    return out


CHECK_FUNCTIONS: tuple[Callable[[Pathway, Catalogs], list[Problem]], ...] = (
    check_procedures,
    check_procedure_kinds,
    check_materials,
    check_drugs,
    check_icd,
    check_labs,
    check_specialties,
    check_package_mode,
    check_package_window,
    check_anaesthesia,
    check_sessions,
    check_days,
    check_stay_coverage,
    check_icu_day_pattern,
    check_drug_courses,
    check_drug_indications,
    check_pins,
    check_window,
    check_sources,
)


def run_all(pathway: Pathway, catalogs: Catalogs) -> list[Problem]:
    """Every problem every check finds; an empty list means the pathway is valid."""
    return [problem for check in CHECK_FUNCTIONS for problem in check(pathway, catalogs)]


def main(argv: list[str] | None = None) -> int:
    """`python -m scripts.synthetic.pathways.checks [file ...]`: load and check files (default: all)."""
    paths = [Path(a) for a in (sys.argv[1:] if argv is None else argv)] or sorted(
        PATHWAYS_DIR.glob("*.yaml")
    )
    catalogs, failed = Catalogs(), 0
    for path in paths:
        try:
            problems = run_all(load_pathway(path), catalogs)
        except PathwayLoadError as exc:
            problems = exc.problems
        failed += bool(problems)
        print(f"{path.name}: {'ok' if not problems else f'{len(problems)} problem(s)'}")
        for problem in problems:
            print(f"  {problem}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
