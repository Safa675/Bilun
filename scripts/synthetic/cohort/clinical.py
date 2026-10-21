"""Showcase clinical context (vitals, lab states, product routes): Pydantic v2 schema, strict YAML loader and cross-checks.

`data/synthetic/cohort/showcase_clinical.yaml` declares the admission/visit vitals and optional lab
state profiles for each showcase patient (`patient_no` 1, 2, 3 ... as in `showcase_recipes.yaml`: 1..8 are the
stories S1..S8, 9 is S9), with `basis: judgment` and a short `source` note referencing clinician review in
issue #309. Its
`drug_routes` block gives the route of administration of the billed products whose TITCK product
name states none. No prices, amounts or totals exist in this schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import polars as pl
from pydantic import (
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
)
from pydantic_core import PydanticCustomError
import yaml

from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.loader import PathwayLoadError, _StrictLoader, hygiene
from scripts.synthetic.pathways.schema import (
    Barcode,
    Problem as _PathwayProblem,
    Source,
    _Model,
)

from .catalogs import CohortCatalogs
from .recipes import RECIPES_PATH, PatientNo, ShowcaseRecipes, load_recipes

if TYPE_CHECKING:
    from .labs import LabReference

SCHEMA_VERSION = 1

REPO = Path(__file__).resolve().parents[3]
CLINICAL_DIR = REPO / "data" / "synthetic" / "cohort"
CLINICAL_PATH = CLINICAL_DIR / "showcase_clinical.yaml"

# Every check id a clinical Problem may carry. A meta-test requires an in-memory mutation case for each.
CHECKS: tuple[str, ...] = (
    # YAML syntax and raw-document hygiene
    "yaml.invalid",
    "hygiene.forbidden_key",
    "hygiene.anon_text",
    "hygiene.price_text",
    "hygiene.id_like_number",
    # Pydantic v2 schema validation
    "schema.unknown_field",
    "schema.missing_field",
    "schema.bad_enum",
    "schema.bad_value",
    # Plausible vital-sign ranges and systolic > diastolic ordering
    "vitals.sbp_range",
    "vitals.dbp_range",
    "vitals.bp_order",
    "vitals.pulse_range",
    "vitals.spo2_range",
    "vitals.height_range",
    "vitals.weight_range",
    # Lab context cross-checks against lab_reference.csv and L103900 blood-gas rules
    "labs.unknown_key",
    "labs.unknown_state",
    "labs.blood_gas",
    # Per-product route of administration barcode cross-check against drug_crosswalk.parquet
    "drug_routes.unknown_barcode",
    # Cross-reference with showcase_recipes.yaml
    "clinical.patient_numbers",
)

_PYDANTIC_IDS = {
    "extra_forbidden": "schema.unknown_field",
    "missing": "schema.missing_field",
    "literal_error": "schema.bad_enum",
}


@dataclass(frozen=True)
class Problem(_PathwayProblem):
    """One finding in showcase_clinical.yaml: a stable check id, where in the document, and why."""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")


class ClinicalLoadError(PathwayLoadError):
    """Raised when showcase_clinical.yaml fails YAML syntax, hygiene, or schema validation."""


class Vitals(_Model):
    """Admission/visit vital signs and anthropometrics for one showcase patient.

    The model holds the types only. How plausible a value is depends on the patient's age, which the
    recipe's pathway pins and this document does not know, so `check_clinical` judges the ranges
    (`VITALS_RANGES`, the `vitals.*` ids) once it can read the age.
    """

    sbp: StrictInt
    dbp: StrictInt
    pulse: StrictInt
    spo2: StrictInt
    height_cm: StrictInt
    weight_kg: StrictFloat | StrictInt

    @field_validator("weight_kg")
    @classmethod
    def _weight_is_finite(cls, value: float | int) -> float:
        val = float(value)
        if not math.isfinite(val):
            raise PydanticCustomError(
                "vitals.weight_range",
                "weight_kg {value} kg is not a finite number",
                {"value": value},
            )
        return val


ShowcaseVitals = Vitals

# The plausible ranges of the vital signs by age band, inclusive (judgment: outside can only be a bug).
# The band is the age that the recipe's pathway pins: age 0 (a baby under one year, the newborn
# included) is the infant band, every other age the adult one. A child of 1 to 17 years has no band yet.
AGE_BAND_ADULT = "adult"
AGE_BAND_INFANT = "infant"
VITALS_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    AGE_BAND_ADULT: {
        "sbp": (70, 260),
        "dbp": (40, 150),
        "pulse": (30, 220),
        "spo2": (60, 100),
        "height_cm": (120, 210),
        "weight_kg": (30.0, 200.0),
    },
    AGE_BAND_INFANT: {
        "sbp": (40, 130),
        "dbp": (20, 90),
        "pulse": (80, 220),
        "spo2": (60, 100),
        "height_cm": (30, 85),
        "weight_kg": (0.4, 12.0),
    },
}
_VITALS_UNITS = {
    "sbp": "mmHg",
    "dbp": "mmHg",
    "pulse": "/min",
    "spo2": "%",
    "height_cm": "cm",
    "weight_kg": "kg",
}
_VITALS_RANGE_IDS = {
    "sbp": "vitals.sbp_range",
    "dbp": "vitals.dbp_range",
    "pulse": "vitals.pulse_range",
    "spo2": "vitals.spo2_range",
    "height_cm": "vitals.height_range",
    "weight_kg": "vitals.weight_range",
}


def age_band(age: int | None) -> str:
    """The vital-sign band of a patient's age in years: infant for a baby under one year, else adult."""
    return AGE_BAND_INFANT if age is not None and age < 1 else AGE_BAND_ADULT


def vitals_problems(vitals: Vitals, band: str, where: str) -> list[Problem]:
    """`vitals.*_range` and `vitals.bp_order` for one patient's vitals in the ranges of `band`.

    The blood-pressure order is only judged when both pressures are inside their ranges, so one
    defect is reported once.
    """
    ranges = VITALS_RANGES[band]
    out: list[Problem] = []
    inside: dict[str, bool] = {}
    for name, (low, high) in ranges.items():
        value = getattr(vitals, name)
        inside[name] = low <= value <= high
        if not inside[name]:
            out.append(
                Problem(
                    _VITALS_RANGE_IDS[name],
                    f"{where}.{name}",
                    f"{name} {value} {_VITALS_UNITS[name]} is outside plausible range "
                    f"{low:g}..{high:g} for the {band} band",
                )
            )
    if inside["sbp"] and inside["dbp"] and vitals.sbp <= vitals.dbp:
        out.append(
            Problem(
                "vitals.bp_order",
                where,
                f"sbp ({vitals.sbp}) must be strictly above dbp ({vitals.dbp})",
            )
        )
    return out


class PatientLabs(_Model):
    """Optional per-patient laboratory state profile (`blood_gas`, `states`, `basis`, `source`)."""

    blood_gas: Literal["arterial"] | None = None
    states: dict[StrictStr, StrictStr | list[StrictStr]] = Field(default_factory=dict)
    basis: Literal["judgment"]
    source: Source

    @field_validator("states")
    @classmethod
    def _non_empty_states(
        cls,
        value: dict[str, str | list[str]],
    ) -> dict[str, str | list[str]]:
        for k, v in value.items():
            if not k.strip():
                raise PydanticCustomError(
                    "schema.bad_value",
                    "labs.states key must not be empty",
                    {},
                )
            if isinstance(v, list):
                if not v:
                    raise PydanticCustomError(
                        "schema.bad_value",
                        "labs.states[{key}] list must not be empty",
                        {"key": k},
                    )
                for item in v:
                    if not item.strip():
                        raise PydanticCustomError(
                            "schema.bad_value",
                            "labs.states[{key}] state item must not be empty",
                            {"key": k},
                        )
            elif not v.strip():
                raise PydanticCustomError(
                    "schema.bad_value",
                    "labs.states[{key}] state value must not be empty",
                    {"key": k},
                )
        return value


Labs = PatientLabs
ShowcaseLabs = PatientLabs

# The routes `clean.derive_route_from_titck` can return (it is annotated with this type, and a test
# reads its `return` statements), so a declared route uses the same words as a derived one.
DrugRoute = Literal[
    "İntramusküler/İntravenöz",
    "Intravenöz",
    "Ağızdan (Oral)",
    "İnhalasyon",
    "Subkütan",
]


class DrugRoutes(_Model):
    """Route of administration per product for the billed products whose TITCK name states none."""

    by_barcode: dict[Barcode, DrugRoute] = Field(min_length=1)
    basis: Literal["judgment"]
    source: Source


class PatientClinical(_Model):
    """One showcase patient's clinical vitals and optional lab profile with provenance (`basis: judgment` and `source`)."""

    patient_no: PatientNo
    vitals: Vitals
    labs: PatientLabs | None = None
    basis: Literal["judgment"]
    source: Source


ClinicalPatient = PatientClinical


class ShowcaseClinical(_Model):
    """Top-level showcase clinical document (`data/synthetic/cohort/showcase_clinical.yaml`)."""

    schema_version: Literal[1]
    drug_routes: DrugRoutes | None = None
    patients: list[PatientClinical] = Field(min_length=1)

    def by_patient_no(self) -> dict[int, PatientClinical]:
        """Return a mapping from `patient_no` to `PatientClinical`."""
        return {p.patient_no: p for p in self.patients}


ClinicalRegistry = ShowcaseClinical


def _where(loc: tuple[Any, ...], raw: Any) -> str:
    """Format a Pydantic error location, substituting `patient_no` for a patient list index."""
    parts: list[str] = []
    node = raw
    for step in loc:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(step, int) and parts:
            label = node.get("patient_no") if isinstance(node, dict) else None
            parts[-1] += f"[{label if label is not None else step}]"
        else:
            parts.append(str(step))
    return ".".join(parts) or "(clinical)"


def _schema_problems(exc: ValidationError, raw: Any) -> list[Problem]:
    out: list[Problem] = []
    for err in exc.errors():
        err_type = err["type"]
        if err_type in CHECKS:
            check = err_type
        else:
            check = _PYDANTIC_IDS.get(err_type, f"schema.{err_type}")
            if check not in CHECKS:
                check = "schema.bad_value"
        message = str(err["msg"]).removeprefix("Value error, ")
        out.append(Problem(check, _where(err["loc"], raw), message))
    return out


def load_clinical_text(text: str, name: str = "<memory>") -> ShowcaseClinical:
    """Parse and validate showcase-clinical YAML text; `name` identifies the source in errors."""

    def fail(problems: list[Any]) -> ClinicalLoadError:
        return ClinicalLoadError([Problem(p.check, p.where, p.message, name) for p in problems])

    try:
        raw = yaml.load(text, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise fail([Problem("yaml.invalid", "(document)", str(exc).replace("\n", " "))]) from None
    if not isinstance(raw, dict):
        raise fail([Problem("yaml.invalid", "(document)", "the top level must be a mapping")])
    dirty = hygiene(raw, text)
    if dirty:
        raise fail(dirty)
    try:
        return ShowcaseClinical.model_validate(raw)
    except ValidationError as exc:
        raise fail(_schema_problems(exc, raw)) from None


def load_clinical(path: Path | str = CLINICAL_PATH) -> ShowcaseClinical:
    """Load and validate a showcase clinical YAML file."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClinicalLoadError([Problem("yaml.invalid", "(file)", str(exc), path.name)]) from None
    return load_clinical_text(text, path.name)


@lru_cache(maxsize=4)
def _cached_recipes(path: Path) -> ShowcaseRecipes:
    return load_recipes(path)


@lru_cache(maxsize=2)
def _cached_pathways() -> dict[str, Pathway]:
    return load_all()


@lru_cache(maxsize=1)
def _default_catalogs() -> CohortCatalogs:
    return CohortCatalogs()


def _drug_route_problems(routes: DrugRoutes | None, catalogs: CohortCatalogs) -> list[Problem]:
    """`drug_routes.unknown_barcode` for each declared barcode that is not in the drug crosswalk."""
    if routes is None:
        return []
    declared = pl.DataFrame({"barcode": list(routes.by_barcode)}, schema={"barcode": pl.String})
    unknown = declared.join(catalogs.drug_crosswalk.select("barcode"), on="barcode", how="anti")
    return [
        Problem(
            "drug_routes.unknown_barcode",
            f"drug_routes.by_barcode[{barcode!r}]",
            f"barcode {barcode!r} does not exist in drug_crosswalk.parquet",
        )
        for barcode in unknown["barcode"].to_list()
    ]


def _pathway_has_l103900(pathway: Pathway) -> bool:
    for proc in pathway.procedures:
        if proc.code == "L103900":
            return True
        if proc.items and any(item.code == "L103900" for item in proc.items):
            return True
    return False


def check_clinical(
    clinical: ShowcaseClinical,
    *,
    recipes: ShowcaseRecipes | None = None,
    reference: LabReference | None = None,
    catalogs: CohortCatalogs | None = None,
) -> list[Problem]:
    """Validate `clinical` against `showcase_recipes.yaml`, `lab_reference.csv`, and `drug_crosswalk.parquet`."""
    from .labs import load_lab_reference

    out: list[Problem] = []
    loaded_recipes = recipes if recipes is not None else _cached_recipes(RECIPES_PATH)
    ref = reference if reference is not None else load_lab_reference()
    pathways_map = _cached_pathways()

    out.extend(
        _drug_route_problems(
            clinical.drug_routes, catalogs if catalogs is not None else _default_catalogs()
        )
    )

    expected_nos = [r.patient_no for r in loaded_recipes.recipes]
    actual_nos = [p.patient_no for p in clinical.patients]
    dup_nos = sorted({n for n in actual_nos if actual_nos.count(n) > 1})
    if dup_nos:
        out.append(
            Problem(
                "clinical.patient_numbers",
                "patients",
                f"duplicate patient_no(s): {', '.join(str(n) for n in dup_nos)}; "
                f"expected unique {expected_nos} matching showcase_recipes.yaml",
            )
        )
    elif actual_nos != expected_nos:
        missing = sorted(set(expected_nos) - set(actual_nos))
        extra = sorted(set(actual_nos) - set(expected_nos))
        out.append(
            Problem(
                "clinical.patient_numbers",
                "patients",
                f"patient_no values must equal showcase_recipes.yaml {expected_nos} in order "
                f"(missing={missing}, extra={extra}, got={actual_nos})",
            )
        )

    recipe_by_no = {r.patient_no: r for r in loaded_recipes.recipes}

    for idx, patient in enumerate(clinical.patients):
        pno = patient.patient_no
        where_pat = f"patients[{pno if not dup_nos else idx}]"
        recipe = recipe_by_no.get(pno)
        pw = pathways_map.get(recipe.pathway) if recipe is not None else None
        has_l103900_line = _pathway_has_l103900(pw) if pw is not None else False
        band = age_band(pw.showcase.age if pw is not None else None)
        out.extend(vitals_problems(patient.vitals, band, f"{where_pat}.vitals"))

        if patient.labs is None:
            if has_l103900_line:
                out.append(
                    Problem(
                        "labs.blood_gas",
                        f"{where_pat}.labs",
                        f"patient {pno} has an L103900 blood gas line and must specify labs.blood_gas: 'arterial'",
                    )
                )
            continue

        where_labs = f"{where_pat}.labs"
        has_l103900_key = any(k.startswith("L103900|") for k in patient.labs.states)

        for key, raw_state in patient.labs.states.items():
            where_key = f"{where_labs}.states[{key!r}]"
            if key not in ref.by_key:
                out.append(
                    Problem(
                        "labs.unknown_key",
                        where_key,
                        f"unknown lab parameter key {key!r} (not in lab_reference.csv)",
                    )
                )
                continue
            spec = ref.by_key[key]
            state_items = raw_state if isinstance(raw_state, list) else [raw_state]
            for st in state_items:
                if st != "normal" and st not in spec.states_by_id:
                    out.append(
                        Problem(
                            "labs.unknown_state",
                            where_key,
                            f"state {st!r} does not exist for {key!r} in lab_reference.csv",
                        )
                    )

        if (has_l103900_key or has_l103900_line) and patient.labs.blood_gas is None:
            out.append(
                Problem(
                    "labs.blood_gas",
                    f"{where_labs}.blood_gas",
                    f"patient {pno} with L103900 blood gas must specify blood_gas: 'arterial'",
                )
            )
        elif patient.labs.blood_gas is not None and not (has_l103900_key or has_l103900_line):
            out.append(
                Problem(
                    "labs.blood_gas",
                    f"{where_labs}.blood_gas",
                    f"patient {pno} has no L103900 blood gas line or state key, so blood_gas must not be set",
                )
            )

    return out


run_all = check_clinical
