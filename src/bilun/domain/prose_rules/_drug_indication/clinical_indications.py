"""Source-scoped SC immunoglobulin, hepatitis and denosumab necessary facts.

Distinct treatment routes require explicit selection. Partial route checks never
adjudicate other indications or authorize payment; absent facts stay unknown.
"""

from datetime import date
import math
from typing import Any
from dateutil.relativedelta import relativedelta

from ...claims.clinical_evidence import IndicationEvidence, parse_clinical_evidence
from ...turkish_fold import TurkishFold, fold_turkish
from .clinical_common import Predicate, Reader, all_of, any_of, result, scope_missing
from .matching import _drug_name_matches, _specialty_matches

SC_IG_DRUGS = ["immünglobulin", "immunglobulin", "immunoglobulin", "scig"]
HBV_DRUGS = [
    "entekavir",
    "tenofovir",
    "lamivudin",
    "telbivudin",
    "adefovir",
    "peginterferon",
    "pegile interferon",
]
HCV_DRUGS = ["interferon", "peginterferon", "pegile interferon", "ribavirin"]
BONE_DRUGS = ["denosumab", "prolia"]


def unknown(*fields: str) -> Predicate:
    return Predicate(None, tuple("indication_evidence." + f for f in fields))


def _record(reader: Reader, field: str, predicate: Predicate) -> Predicate:
    """Keep derived and flat-input outcomes visible without disclosing values."""
    reader.checks.append(
        {
            "field": field,
            "status": "unknown"
            if predicate.value is None
            else "pass"
            if predicate.value
            else "fail",
        }
    )
    return predicate


def _sc_ig(reader: Reader, line: Any) -> Predicate:
    if reader.get("administration_route") != "subcutaneous":
        return unknown("administration_route")
    branch = reader.get("indication")
    if branch not in ("sc_ig_cll", "sc_ig_mm", "sc_ig_allogeneic_hsct"):
        return unknown("indication")
    hypo = reader.bool("hypogammaglobulinemia")
    if branch == "sc_ig_cll":
        patient = all_of(
            hypo,
            reader.bool("recurrent_bacterial_infections"),
            any_of(
                reader.bool("prophylactic_antibiotics_failed"),
                reader.bool("prophylactic_antibiotics_contraindicated"),
            ),
        )
    elif branch == "sc_ig_mm":
        patient = all_of(hypo, reader.bool("recurrent_bacterial_infections"))
    elif branch == "sc_ig_allogeneic_hsct":
        patient = all_of(hypo, reader.bool("allogeneic_hsct_before_or_after"))
    else:
        return unknown("indication")
    author = reader.one_of(
        "report_author_specialty", ("hematology", "pediatric_hematology_oncology")
    )
    specialty = getattr(line, "prescriber_specialty", None)
    prescriber = (
        Predicate(None, ("prescriber_specialty",))
        if not specialty
        else Predicate(
            _specialty_matches(specialty, ["hematoloji", "çocuk hematolojisi ve onkolojisi"])
        )
    )
    duration = getattr(line, "drug_report_duration_months", None)
    try:
        valid_duration = (
            type(duration) in (int, float) and math.isfinite(float(duration)) and duration > 0
        )
    except (ValueError, OverflowError):
        valid_duration = False
    duration_check = (
        Predicate(duration <= 12)
        if valid_duration
        else Predicate(None, ("drug_report_duration_months",))
    )
    supply = reader.get("prescribed_supply_months")
    supply_check = (
        unknown("prescribed_supply_months")
        if supply is None or supply <= 0
        else reader.number("prescribed_supply_months", "<=", 1)
    )
    return all_of(
        patient,
        author,
        _record(reader, "prescriber_specialty", prescriber),
        _record(reader, "drug_report_duration_months", duration_check),
        supply_check,
    )


def _hbv(reader: Reader, service: date) -> Predicate:
    if reader.get("indication") != "hbv_initiation_path_a" or reader.get("phase") != "initiation":
        return unknown("indication", "phase")
    age = reader.get("age_group")
    scale = (
        reader.one_of("biopsy_scoring_system", ("ishak_modified_hai", "knodell_hai", "metavir"))
        if reader.get("biopsy_scoring_system") in ("ishak_modified_hai", "knodell_hai", "metavir")
        else _record(
            reader, "indication_evidence.biopsy_scoring_system", unknown("biopsy_scoring_system")
        )
    )
    if age == "adult":
        # Compare the reported numbers, but instrument-domain validity alone
        # does not prove that the named method is the SUT-incorporated scale.
        # Never equate ordinal scores across instruments to clear or deny a route.
        all_of(
            scale,
            any_of(
                reader.number("biopsy_hai", ">=", 6),
                reader.number("biopsy_fibrosis_stage", ">=", 2),
            ),
        )
        first, second = reader.get("first_alt_date"), reader.get("second_alt_date")
        if first is None or second is None or first > second or second > service:
            repeat = unknown("first_alt_date", "second_alt_date")
        else:
            repeat = Predicate(second >= first + relativedelta(months=3))
        alt = all_of(
            _record(reader, "indication_evidence.alt_retest_interval", repeat),
            reader.number("first_alt_uln_ratio", ">", 1),
            reader.number("second_alt_uln_ratio", ">", 1),
        )
        fib4 = reader.number("fib4_score", ">", 1.45)
        apri = reader.number("apri_score", ">", 0.5)
        noninvasive = all_of(alt, any_of(fib4, apri))
        # Art13(b) is unparenthesized: ALT AND (FIB4 OR APRI) and
        # (ALT AND FIB4) OR APRI share sufficient cases but disagree here.
        if apri.value is True and alt.value is not True:
            noninvasive = _record(
                reader,
                "indication_evidence.hbv_noninvasive_boolean_grouping",
                unknown("hbv_noninvasive_boolean_grouping"),
            )
        histology = _record(
            reader,
            "indication_evidence.histology_scoring_source_compatibility",
            unknown("histology_scoring_source_compatibility"),
        )
        pathway = any_of(histology, noninvasive)
    elif age == "age_2_18":
        all_of(
            scale,
            any_of(
                all_of(
                    reader.number("second_alt_uln_ratio", ">", 2),
                    reader.number("biopsy_hai", ">=", 4),
                ),
                reader.number("biopsy_fibrosis_stage", ">=", 2),
            ),
        )
        pathway = _record(
            reader,
            "indication_evidence.histology_scoring_source_compatibility",
            unknown("histology_scoring_source_compatibility"),
        )
    else:
        return unknown("age_group")
    return all_of(reader.number("hbv_dna_iu_ml", ">=", 2000), pathway)


def _hcv(reader: Reader) -> Predicate:
    if reader.get("indication") != "pediatric_chronic_hcv" or reader.get("phase") != "initiation":
        return unknown("indication", "phase")
    if reader.get("age_group") not in ("child", "age_2_18"):
        return unknown("age_group")
    return all_of(reader.bool("hcv_rna_positive"), reader.bool("hcv_genotype_result_present"))


def _bone(reader: Reader) -> Predicate:
    if reader.get("indication") != "glucocorticoid_bone_loss":
        return unknown("indication")
    if reader.get("age_group") not in ("adult", "age_2_18", "child"):
        return unknown("age_group")
    return all_of(
        reader.one_of("age_group", ("adult",)),
        reader.bool("osteoporosis_diagnosed"),
        reader.bool("high_fracture_risk"),
        reader.bool("long_term_glucocorticoid_treatment"),
        reader.bool("glucocorticoid_associated_bone_loss"),
        any_of(
            reader.bool("bisphosphonate_intolerant"),
            reader.bool("bisphosphonate_inadequate_response"),
            reader.bool("bisphosphonate_renal_contraindication"),
        ),
    )


def evaluate_indications(line: Any) -> dict[str, Any]:
    evidence = parse_clinical_evidence(
        getattr(line, "indication_evidence", None), IndicationEvidence
    )
    reader = Reader(evidence, "indication_evidence")
    families = [
        name
        for name, drugs in [
            ("sc_ig", SC_IG_DRUGS),
            ("hbv", HBV_DRUGS),
            ("hcv", HCV_DRUGS),
            ("bone", BONE_DRUGS),
        ]
        if _drug_name_matches(line.drug_name, drugs)
    ]
    refs = {
        "sc_ig": ["4.2.12.B-2.b#34366508", "4.2.12.B-2#954d11cb"],
        "hbv": ["4.2.13.1.a#3a85da7e", "4.2.13.1#2076b8bd", "4.2.13.1#50f88a7d"],
        "hcv": ["4.2.13.3.2.B.(1)#d4fbff46"],
        "bone": ["4.2.17.A.(2)#ec5a2641", "4.2.17.A.b#21d7b36c"],
    }
    # Peginterferon is explicitly present in both source families; a clinical
    # indication, not corpus ordering, selects that shared-medicine branch.
    if set(families) == {"hbv", "hcv"} and _drug_name_matches(
        line.drug_name, ["peginterferon", "pegile interferon"]
    ):
        remainder = (
            fold_turkish(line.drug_name or "", TurkishFold.ACCENTLESS_DOTLESS_I)
            .replace("pegile interferon", "")
            .replace("peginterferon", "")
        )
        additional_medicine = _drug_name_matches(remainder, HBV_DRUGS + HCV_DRUGS)
        if not additional_medicine and reader.get("indication") == "hbv_initiation_path_a":
            families = ["hbv"]
        elif not additional_medicine and reader.get("indication") == "pediatric_chronic_hcv":
            families = ["hcv"]
    if len(families) != 1:
        return result(
            "other_indication_source_constraints",
            reader,
            unknown("single_supported_medicine_family"),
            [],
        )
    family = families[0]
    # Official RG02/11/2024-32710 articles12/13(b), commencement32(a),
    # corroborated by SGK consolidated annotations:09/11/2024. These dates
    # govern the unchanged necessary branches, not every current report rule.
    missing_dates = scope_missing(
        evidence, "indication_evidence", line.drug_claim_date, 'indication_' + family, reader=reader
    )
    section = {"sc_ig": "4.2.12.B-2", "hbv": "4.2.13.1", "hcv": "4.2.13.3.2.B", "bone": "4.2.17.A"}[
        family
    ]
    if missing_dates:
        return {
            **result(
                "other_indication_source_constraints",
                reader,
                Predicate(None),
                refs[family],
                date_missing=missing_dates,
            ),
            "sut_section": section,
        }
    predicate = (
        _sc_ig(reader, line)
        if family == "sc_ig"
        else _hbv(reader, line.drug_claim_date)
        if family == "hbv"
        else _hcv(reader)
        if family == "hcv"
        else _bone(reader)
    )
    return {
        **result("other_indication_source_constraints", reader, predicate, refs[family]),
        "sut_section": section,
    }
