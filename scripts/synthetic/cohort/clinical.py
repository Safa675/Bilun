"""Showcase clinical context (vitals, lab states, product routes): Pydantic v2 schema, strict YAML loader and cross-checks.

`data/synthetic/cohort/showcase_clinical.yaml` declares the admission/visit vitals and optional lab
state profiles for each of the 8 showcase patients (`patient_no` 1..8, story S1..S8), with
`basis: judgment` and a short `source` note referencing clinician review in issue #309. Its
`drug_routes` block gives the route of administration of the billed products whose TITCK product
name states none. No prices, amounts or totals exist in this schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

import polars as pl
from pydantic import (
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
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
    """Plausible admission/visit vital signs and anthropometrics for one showcase patient."""

    sbp: StrictInt
    dbp: StrictInt
    pulse: StrictInt
    spo2: StrictInt
    height_cm: StrictInt
    weight_kg: StrictFloat | StrictInt

    @field_validator("sbp")
    @classmethod
    def _sbp_range(cls, value: int) -> int:
        if not 70 <= value <= 260:
            raise PydanticCustomError(
                "vitals.sbp_range",
                "sbp {value} mmHg is outside plausible range 70..260",
                {"value": value},
            )
        return value

    @field_validator("dbp")
    @classmethod
    def _dbp_range(cls, value: int) -> int:
        if not 40 <= value <= 150:
            raise PydanticCustomError(
                "vitals.dbp_range",
                "dbp {value} mmHg is outside plausible range 40..150",
                {"value": value},
            )
        return value

    @field_validator("pulse")
    @classmethod
    def _pulse_range(cls, value: int) -> int:
        if not 30 <= value <= 220:
            raise PydanticCustomError(
                "vitals.pulse_range",
                "pulse {value}/min is outside plausible range 30..220",
                {"value": value},
            )
        return value

    @field_validator("spo2")
    @classmethod
    def _spo2_range(cls, value: int) -> int:
        if not 60 <= value <= 100:
            raise PydanticCustomError(
                "vitals.spo2_range",
                "spo2 {value}% is outside plausible range 60..100",
                {"value": value},
            )
        return value

    @field_validator("height_cm")
    @classmethod
    def _height_range(cls, value: int) -> int:
        if not 120 <= value <= 210:
            raise PydanticCustomError(
                "vitals.height_range",
                "height_cm {value} cm is outside plausible range 120..210",
                {"value": value},
            )
        return value

    @field_validator("weight_kg")
    @classmethod
    def _weight_range(cls, value: float | int) -> float:
        val = float(value)
        if not math.isfinite(val) or not 30.0 <= val <= 200.0:
            raise PydanticCustomError(
                "vitals.weight_range",
                "weight_kg {value} kg is outside plausible range 30..200",
                {"value": value},
            )
        return val

    @model_validator(mode="after")
    def _bp_order(self) -> Self:
        if 70 <= self.sbp <= 260 and 40 <= self.dbp <= 150 and self.sbp <= self.dbp:
            raise PydanticCustomError(
                "vitals.bp_order",
                "sbp ({sbp}) must be strictly above dbp ({dbp})",
                {"sbp": self.sbp, "dbp": self.dbp},
            )
        return self


ShowcaseVitals = Vitals


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
