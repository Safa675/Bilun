"""Test-only extra encounters for the cohort builder: the committed inputs plus a second (or third) bill of a patient.

No committed patient has more than one bill (the first multi-bill patients come with later packages), so the tests
of the multi-encounter builder (`scripts/synthetic/cohort`, G2) build a dataset in memory from the committed
recipes and clinical entries plus the encounters declared here. Nothing is committed from it.

    recipes, clinical = with_encounters(Extra(4, 2, "pyelonephritis_dementia_delirium_ward", {"admit": "2026-05-12"}))
    built = build_showcase(recipes=recipes, clinical=clinical)

`STANDARD_EXTRAS` is the dataset most tests use: patient 4 gets a stay that starts the day after its first one (its
lab days interleave with the first stay's), patient 7 gets an earlier visit of the same pathway (a precursor: the
later claim number, the earlier date).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from scripts.synthetic.cohort.clinical import PatientClinical, ShowcaseClinical, load_clinical
from scripts.synthetic.cohort.recipes import (
    EncounterPins,
    ShowcaseRecipe,
    ShowcaseRecipes,
    load_recipes,
)

_SOURCE = "Test fixture only: an extra encounter that no committed patient has."


@dataclass(frozen=True)
class Extra:
    """One extra encounter: the recipe (patient, encounter, pathway, fault, pins) and, optionally, its clinical entry."""

    patient_no: int
    encounter_no: int
    pathway: str
    pins: Mapping[str, Any] | None = None
    fault: str | None = None
    labs: Mapping[str, Any] | None = None  # a `PatientLabs` payload; None: no lab profile (every value normal)
    pulse_shift: int = 3  # the vitals are the first encounter's with the pulse moved, so the rows differ


def with_encounters(*extras: Extra) -> tuple[ShowcaseRecipes, ShowcaseClinical]:
    """The committed recipes and clinical document with `extras` inserted after the last encounter of their patient."""
    recipes = load_recipes()
    clinical = load_clinical()
    recipe_list = list(recipes.recipes)
    entry_list = list(clinical.patients)
    first = {entry.patient_no: entry for entry in entry_list if entry.encounter_no == 1}

    for extra in extras:
        recipe = ShowcaseRecipe(
            patient_no=extra.patient_no,
            encounter_no=extra.encounter_no,
            pathway=extra.pathway,
            fault=extra.fault,
            pins=EncounterPins.model_validate(dict(extra.pins)) if extra.pins else None,
        )
        vitals = first[extra.patient_no].vitals
        entry = PatientClinical.model_validate(
            {
                "patient_no": extra.patient_no,
                "encounter_no": extra.encounter_no,
                "vitals": {**vitals.model_dump(), "pulse": vitals.pulse + extra.pulse_shift},
                "labs": dict(extra.labs) if extra.labs else None,
                "basis": "judgment",
                "source": _SOURCE,
            }
        )
        recipe_list.append(recipe)
        entry_list.append(entry)

    recipe_list.sort(key=lambda r: (r.patient_no, r.encounter_no))
    entry_list.sort(key=lambda e: (e.patient_no, e.encounter_no))
    return (
        recipes.model_copy(update={"recipes": recipe_list}),
        clinical.model_copy(update={"patients": entry_list}),
    )


# patient 4 (S4, a woman of 86): the same stay one day later, its lab days between the first stay's;
# patient 7 (S7, a woman of 58): the same ER visit nine days earlier, so claim 002 is dated before claim 001.
# A story belongs to one bill, so each second bill names a story of its own (the program's S39 and up are
# the real follow-up bills; S90 and S91 exist only here).
STANDARD_EXTRAS = (
    Extra(4, 2, "pyelonephritis_dementia_delirium_ward", {"admit": "2026-05-12", "story": "S90"}),
    Extra(7, 2, "pleuritic_chest_pain_er_pulmonary_embolism_ruled_out", {"admit": "2026-02-10", "story": "S91"}),
)
