"""Synthetic cohort composer (v3, P4): legacy-format ID builders, catalog lookups, claim composition and Parquet tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .build import (
        DATASET_ID,
        DEFAULT_OUT_DIR,
        BuildError,
        BuildResult,
        build_showcase,
        check_showcase,
        format_registry_json,
        validate_cohort_registry,
        write_showcase,
    )

from .catalogs import EK3F1_FROM, CatalogError, CatalogRow, CohortCatalogs
from .compose import ComposedClaim, ComposeError, EncounterContext, compose_claim, money
from .ids import (
    CLAIM_ID_RE,
    DIAGNOSIS_ID_RE,
    DRUG_CLAIM_LINE_ID_RE,
    EPISODE_ID_RE,
    MATERIAL_LINE_ID_RE,
    PATIENT_ID_RE,
    PERFORMED_LINE_ID_RE,
    PRESCRIPTION_ID_RE,
    PROCEDURE_LINE_ID_RE,
    claim_id,
    diagnosis_id,
    drug_claim_line_id,
    drug_line_id,
    episode_id,
    material_line_id,
    patient_id,
    performed_line_id,
    prescription_id,
    procedure_line_id,
)
from .recipes import (
    CHECKS as RECIPE_CHECKS,
    RECIPES_DIR,
    RECIPES_PATH,
    Problem as RecipeProblem,
    Recipe,
    RecipeLoadError,
    RecipeRegistry,
    ShowcaseRecipe,
    ShowcaseRecipes,
    check_recipes,
    load_recipes,
    load_recipes_text,
)
from .tables import (
    TABLE_FILES,
    TableSchemaError,
    build_tables,
    copay_profile,
    table_schemas,
    tables_digest,
    validate_tables,
    write_tables,
)

_BUILD_EXPORTS = frozenset(
    {
        "DATASET_ID",
        "DEFAULT_OUT_DIR",
        "BuildError",
        "BuildResult",
        "build_showcase",
        "check_showcase",
        "format_registry_json",
        "validate_cohort_registry",
        "write_showcase",
    }
)


def __getattr__(name: str) -> Any:
    if name in _BUILD_EXPORTS:
        from . import build as _build

        return getattr(_build, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BuildError",
    "BuildResult",
    "CLAIM_ID_RE",
    "CatalogError",
    "CatalogRow",
    "CohortCatalogs",
    "ComposeError",
    "ComposedClaim",
    "DATASET_ID",
    "DEFAULT_OUT_DIR",
    "DIAGNOSIS_ID_RE",
    "DRUG_CLAIM_LINE_ID_RE",
    "EK3F1_FROM",
    "EPISODE_ID_RE",
    "EncounterContext",
    "MATERIAL_LINE_ID_RE",
    "PATIENT_ID_RE",
    "PERFORMED_LINE_ID_RE",
    "PRESCRIPTION_ID_RE",
    "PROCEDURE_LINE_ID_RE",
    "RECIPES_DIR",
    "RECIPES_PATH",
    "RECIPE_CHECKS",
    "Recipe",
    "RecipeLoadError",
    "RecipeProblem",
    "RecipeRegistry",
    "ShowcaseRecipe",
    "ShowcaseRecipes",
    "TABLE_FILES",
    "TableSchemaError",
    "build_showcase",
    "build_tables",
    "check_recipes",
    "check_showcase",
    "claim_id",
    "compose_claim",
    "copay_profile",
    "diagnosis_id",
    "drug_claim_line_id",
    "drug_line_id",
    "episode_id",
    "format_registry_json",
    "load_recipes",
    "load_recipes_text",
    "material_line_id",
    "money",
    "patient_id",
    "performed_line_id",
    "prescription_id",
    "procedure_line_id",
    "table_schemas",
    "tables_digest",
    "validate_cohort_registry",
    "validate_tables",
    "write_showcase",
    "write_tables",
]
