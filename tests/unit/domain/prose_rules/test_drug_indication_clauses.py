"""Per-clause drug-indication checks: one table row per clause group.

A row holds what that clause group's own test file used to assert: how many
rules the batch keeps, which rule ids and gate-B sources it names, what its
gate-B manifest says, and how the engine answers its golden samples. Checks
that only one clause group makes sit below the table.

The drug-indication evaluator reads neither the claim department nor the line
prices, so one claim builder and one line builder serve every row.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import polars as pl
import pytest

from scripts.sut.prose.clause_identity import (
    STRUCTURAL_NON_LINKABLE_TYPES,
    resolve_gate_b_sources_to_clause_ids,
)
from scripts.sut.prose.manifest_index import encoded_like_clause_ids
from scripts.sut.rule_sources import load_drug_sections_rules, load_legacy_drug_batch
from src.bilun.domain.claims.clinical_evidence import IndicationEvidence
from src.bilun.domain.claims.growth_hormone import GROWTH_HORMONE_INPUT_FIELDS
from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line,
    list_drug_indication_rules,
)
from tests.unit._helpers.brittle_guards import soft_floor
from tests.unit._helpers.gate_b_cites import (
    cite_in_sources,
    cites_covered_by_encoded,
    resolve_gate_b_cites_to_clause_ids,
)
from tests.unit._helpers.reviewed_clause_ids import reviewed_clause_id

pytestmark = pytest.mark.unit

_DATA = Path(__file__).resolve().parents[4] / "data/gazette"
_ROUTE_VIOLATIONS = frozenset({"indication_mismatch", "ambiguous_route"})


def _legacy(batch: str) -> Callable[[], list[dict]]:
    return lambda: load_legacy_drug_batch(batch)


def _sections(*section_ids: str) -> Callable[[], list[dict]]:
    return lambda: load_drug_sections_rules(list(section_ids))


def _json_rules(name: str, *sections: str) -> Callable[[], list[dict]]:
    """The rules of a prose JSON, one per rule id, only those of ``sections`` if given."""

    def load() -> list[dict]:
        payload = json.loads((_DATA / "prose_rules" / name).read_text(encoding="utf-8"))
        return list({
            str(rule["rule_id"]): rule
            for rule in payload.get("rules") or []
            if not sections or str(rule.get("sut_section") or "").startswith(sections)
        }.values())

    return load


@dataclass(frozen=True, kw_only=True)
class Golden:
    """How the engine must answer a golden file's samples."""

    file: str
    # Rules each sample is evaluated against: "rule" the sample's rule from the
    # row's batch, "batch" the whole batch, "corpus" the default corpus,
    # "corpus_rule" the sample's rule from the default corpus.
    scope: str
    # A mismatch or ambiguous-route hit names its eligible routes instead of a rule.
    routes: bool = True
    # Sample keys copied as they are onto the drug line.
    line_fields: tuple[str, ...] = ()
    # Rules that may answer instead of the sample's rule.
    alternates: Mapping[str, frozenset[str]] = field(default_factory=dict)
    # Constraint set checked when a sample expects a clinical status.
    clinical_set: str | None = None


@dataclass(frozen=True, kw_only=True)
class Clause:
    """One clause group: its rules, its manifest facts and its golden samples."""

    id: str
    rules: Callable[[], list[dict]]
    rule_floor: int | None = None
    rule_count: int | None = None
    rule_ids: frozenset[str] = frozenset()
    only_rule_ids: bool = False
    gate_b_on_every_rule: bool = False
    gate_b_count: int | None = None
    gate_b_resolves_to: tuple[str, ...] = ()
    manifest: str | None = None
    # Where every gate-B source must be encoded: "encoded_like" (the manifest's
    # encoded_like_clause_ids), "encoded_ids" (its encoded_clause_ids),
    # "resolved" (resolved cites within encoded_like), "prose_json" (the rule JSON).
    covered_by: str | None = None
    count_covers_gate_b: bool = False
    # Manifest facts; a name is a field, ``len(<list field>)`` or ``len(set(<list field>))``.
    values: Mapping[str, object] = field(default_factory=dict)
    floors: Mapping[str, int] = field(default_factory=dict)
    pairs: tuple[tuple[str, str], ...] = ()
    encodes: tuple[str, ...] = ()
    in_coverage_union: bool = False
    golden: Golden | None = None


_M4201 = "L4.2_drug_indication_4201_manifest.json"
_M4206 = "L4.2_drug_indication_4206_manifest.json"
_M4213 = "L4.2_drug_indication_4213_4216_manifest.json"

ROWS = (
    Clause(
        id="4201_a1", rules=_legacy("drug_indication_4201_pilot_batch_rules.py:BATCH_A1_RULES"),
        rule_floor=14, manifest=_M4201, floors={"len(encoded_clause_ids)": 14},
        values={"section_id": "4.2.1", "tier_a_pending_count": 0, "tier_b_pending_count": 0},
        golden=Golden(file="drug_indication_4.2.1_a1.json", scope="batch"),
    ),
    Clause(
        id="4201_a2", rules=_legacy("drug_indication_4201_a2_batch_rules.py:BATCH_A2_RULES"),
        rule_floor=15, manifest=_M4201, covered_by="encoded_like", count_covers_gate_b=True,
        golden=Golden(file="drug_indication_4.2.1_a2.json", scope="rule"),
    ),
    Clause(
        id="4201_a3", rules=_legacy("drug_indication_4201_a3_batch_rules.py:BATCH_A3_RULES"),
        rule_floor=15, gate_b_on_every_rule=True,
        manifest=_M4201, covered_by="encoded_like", count_covers_gate_b=True,
        golden=Golden(file="drug_indication_4.2.1_a3.json", scope="rule"),
    ),
    Clause(
        id="4201_a4", rules=_sections("4.2.1.C-1", "4.2.1.C-2", "4.2.1.C-5", "4.2.1.C-7"),
        rule_floor=75, manifest=_M4201, covered_by="encoded_like", count_covers_gate_b=True,
    ),
    Clause(
        id="4201_a4_c1", rules=_sections("4.2.1.C-1"), rule_floor=33,
        manifest=_M4201, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.1_a4_c1.json", scope="rule", routes=False),
    ),
    Clause(
        id="4201_a4_c2", rules=_sections("4.2.1.C-2"), rule_floor=12, gate_b_count=10,
        golden=Golden(file="drug_indication_4.2.1_a4_c2.json", scope="rule"),
    ),
    Clause(
        id="4201_a4_c5", rules=_sections("4.2.1.C-5"), rule_floor=14, gate_b_on_every_rule=True,
        manifest=_M4201, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.1_a4_c5.json", scope="rule"),
    ),
    Clause(
        id="4201_a4_c7", rules=_sections("4.2.1.C-7"), rule_floor=16,
        manifest=_M4201, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.1_a4_c7.json", scope="rule"),
    ),
    Clause(
        id="4201_a5", rules=_sections("4.2.1.C-10", "4.2.1.C-11", "4.2.1.C-12", "4.2.1.C-14"),
        rule_floor=10,
        golden=Golden(file="drug_indication_4.2.1_a5_c10_14.json", scope="rule", routes=False),
    ),
    Clause(
        # C003658 moved from tier_a_pending to tier_c_deferred via deferral_table.
        id="4201_a5_all", rules=_sections(*(f"4.2.1.C-{n}" for n in range(2, 15))),
        manifest=_M4201, covered_by="encoded_like", values={"tier_a_pending_count": 0},
    ),
    Clause(
        id="4201_a5_c2_c5",
        rules=_legacy("drug_indication_4201_a5_c2_c5_batch_rules.py:BATCH_A5_C2_C5_RULES"),
        rule_floor=2, manifest=_M4201, covered_by="encoded_ids",
        golden=Golden(file="drug_indication_4.2.1_a5_c2_c5.json", scope="rule", routes=False),
    ),
    Clause(
        id="4201_a5_c6", rules=_sections("4.2.1.C-6"), rule_floor=23,
        manifest=_M4201, covered_by="encoded_ids",
        golden=Golden(file="drug_indication_4.2.1_a5_c6.json", scope="rule", routes=False),
    ),
    Clause(
        id="4201_a5_c7", rules=_sections("4.2.1.C-7"), rule_floor=16,
        manifest=_M4201, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.1_a5_c7.json", scope="rule", routes=False),
    ),
    Clause(
        id="4201_a5_c8", rules=_sections("4.2.1.C-8"), rule_floor=2,
        manifest=_M4201, covered_by="encoded_ids",
        golden=Golden(file="drug_indication_4.2.1_a5_c8.json", scope="rule", routes=False),
    ),
    Clause(
        id="4201_a5_c9_c13",
        rules=_legacy("drug_indication_4201_a5_c9_c13_batch_rules.py:BATCH_A5_C9_C13_RULES"),
        rule_floor=5, manifest=_M4201, covered_by="encoded_ids",
        golden=Golden(file="drug_indication_4.2.1_a5_c9_c13.json", scope="rule", routes=False),
    ),
    Clause(
        # C003756 / C003834 moved from tier_b_pending to tier_c_deferred via deferral_table.yaml.
        id="4201_w4_tier_b",
        rules=_legacy("drug_indication_4201_w4_tier_b_batch_rules.py:BATCH_4201_W4_TIER_B_RULES"),
        rule_floor=8,
        gate_b_resolves_to=(
            "C003677", "C003698", "C003715", "C003745", "C003760",
            "C003766", "C003828", "C003831", "C003916",
        ),
        manifest=_M4201, covered_by="resolved",
        values={"tier_b_pending_count": 0}, floors={"section_clause_total": 200},
        golden=Golden(file="drug_indication_4.2.1_w4_tier_b.json", scope="rule", routes=False),
    ),
    Clause(
        # Golden samples: test_drug_indication_4206.py (adult somatropin branch).
        id="4206", rules=_legacy("drug_indication_4206_batch_rules.py:BATCH_A6_RULES"),
        rule_floor=3, only_rule_ids=True,
        rule_ids=frozenset({
            "4.2.6.adult_somatropin_board_report",
            "4.2.6.turner_somatropin_pediatric_board",
            "4.2.6.laron_mecasermin_continuation_board",
        }),
        manifest=_M4206, values={"section_id": "4.2.6", "tier_b_pending_count": 0},
        pairs=(("encoded_clause_count", "len(set(encoded_clause_ids))"),),
        encodes=("C003995", "C003996", "C004020"),
    ),
    Clause(
        id="4206_a2", rules=_legacy("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES"),
        rule_floor=7, gate_b_on_every_rule=True,
        manifest=_M4206, covered_by="encoded_like", count_covers_gate_b=True,
        golden=Golden(
            file="drug_indication_4.2.6_a2.json", scope="rule", routes=False,
            line_fields=GROWTH_HORMONE_INPUT_FIELDS,
        ),
    ),
    Clause(
        id="4209_4227", rules=_legacy("drug_indication_4209_4227_batch_rules.py:BATCH_A6_RULES"),
        rule_count=14, gate_b_on_every_rule=True,
        golden=Golden(file="drug_indication_4.2.9_4.2.27_a6.json", scope="rule"),
    ),
    Clause(
        id="4209_a7", rules=_legacy("drug_indication_4209_a7_batch_rules.py:BATCH_A7_RULES"),
        rule_floor=6, gate_b_on_every_rule=True,
        golden=Golden(file="drug_indication_4.2.9_a7.json", scope="rule"),
    ),
    Clause(
        # C004257 is tier_c_deferred and C004299 non_actionable via deferral_table.yaml,
        # so no tier-A candidate remains pending.
        id="4210",
        rules=_sections(
            "4.2.10.A", "4.2.10.A-3", "4.2.10.A-4", "4.2.10.B-3",
            "4.2.10.C-2", "4.2.10.C-3", "4.2.10.D-2", "4.2.10.Ç-2",
        ),
        rule_floor=11, gate_b_on_every_rule=True,
        manifest="L4.2_drug_indication_4210_manifest.json",
        values={"section_id": "4.2.10", "tier_a_pending_count": 0},
        floors={"section_clause_total": 100},
        pairs=(
            ("encoded_clause_count", "len(encoded_clause_ids)"),
            ("tier_c_deferred_count", "len(tier_c_deferred_clause_ids)"),
        ),
        golden=Golden(file="drug_indication_4.2.10.json", scope="batch"),
    ),
    Clause(
        id="4213_4216", rules=_json_rules("drug_indication_prose.json", "4.2.13", "4.2.16"),
        rule_floor=12, gate_b_on_every_rule=True,
        rule_ids=frozenset({
            "4.2.13.hbv_entekavir_board", "4.2.16.cystic_fibrosis_formula_report",
        }),
        manifest=_M4213, encodes=("C004557", "C006069"), in_coverage_union=True,
        golden=Golden(
            file="drug_indication_4.2.13_4.2.16_a2.json", scope="corpus",
            # Several HBV antiviral rules flag the same violation for one drug and ICD.
            alternates={"4.2.13.hbv_entekavir_board": frozenset({
                "4.2.13.hbv_antiviral_report_renewal_initiation_f7",
                "4.2.13.1.2.immunosuppressed_occult_hbv_prophylaxis",
            })},
        ),
    ),
    Clause(
        id="4213_a2a", rules=_legacy("BATCH_A2A_RULES"), rule_floor=12, gate_b_on_every_rule=True,
        manifest=_M4213, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.13_a2a.json", scope="rule", routes=False),
    ),
    Clause(
        id="4213_tier_b", rules=_legacy("BATCH_4213_TIER_B_RULES"),
        rule_floor=4, gate_b_on_every_rule=True, manifest=_M4213, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.13_tier_b.json", scope="rule"),
    ),
    Clause(
        id="4215", rules=_legacy("BATCH_A15_RULES"), rule_floor=8,
        manifest="L4.2_drug_indication_4215_manifest.json", values={"section_id": "4.2.15"},
        pairs=(("encoded_clause_count", "len(set(encoded_clause_ids))"),),
        golden=Golden(file="drug_indication_4.2.15_a15.json", scope="batch"),
    ),
    Clause(
        # The shared manifest's encoded_clause_ids can lag the rule JSON, which coverage reads.
        id="4216_a2b", rules=_legacy("BATCH_A2B_4216_RULES"),
        rule_floor=10, gate_b_on_every_rule=True, covered_by="prose_json",
        golden=Golden(file="drug_indication_4.2.16_a2b.json", scope="rule", routes=False),
    ),
    Clause(
        id="4216_tier_b", rules=_legacy("BATCH_4216_TIER_B_RULES"),
        rule_floor=2, gate_b_on_every_rule=True, manifest=_M4213, covered_by="encoded_like",
        golden=Golden(file="drug_indication_4.2.16_tier_b.json", scope="rule", routes=False),
    ),
    Clause(
        id="4217", rules=_json_rules("drug_indication_prose.json", "4.2.17"), rule_floor=9,
        manifest="L4.2_drug_indication_4217_manifest.json",
        values={"section_id": "4.2.17"}, floors={"len(encoded_clause_ids)": 9},
        golden=Golden(
            file="drug_indication_4.2.17_a3.json", scope="corpus",
            clinical_set="other_indication_source_constraints",
        ),
    ),
    Clause(
        id="4218_4236", rules=_legacy("drug_indication_4218_4236_batch_rules.py:BATCH_A5_RULES"),
        rule_floor=5,
        rule_ids=frozenset({
            "4.2.18.orlistat_monthly_prescription",
            "4.2.36.parkinson_dopamine_agonists_report",
            "4.2.36.tolcapone_tertiary_neurology_report",
            "4.2.36.amantadine_sulfate_report",
            "4.2.36.amantadine_hcl_parkinson_report",
        }),
        manifest="L4.2_drug_indication_4218_4236_manifest.json",
        values={
            "section_id": "4.2.18,4.2.36",
            "section_4.2.18_clause_total": 5,
            "section_4.2.18_tier_a_count": 1,
            "section_4.2.18_tier_c_count": 4,
            "section_4.2.36_clause_total": 6,
            "section_4.2.36_tier_a_count": 4,
            "section_4.2.36_tier_c_count": 2,
            "encoded_clause_count": 5,
        },
        golden=Golden(file="drug_indication_4.2.18_4.2.36_a5.json", scope="batch"),
    ),
    Clause(
        id="4219", rules=_json_rules("drug_indication_prose.json", "4.2.19"),
        rule_ids=frozenset({
            "4.2.19.triptan_neurology_prescriber", "4.2.19.topiramate_migraine_prophylaxis",
        }),
        manifest="L4.2_drug_indication_4219_manifest.json",
        floors={"encoded_clause_count": 2}, encodes=("C006150", "C006151"),
        golden=Golden(file="drug_indication_4.2.19_a4.json", scope="corpus"),
    ),
    Clause(
        id="4224", rules=_legacy("BATCH_A24_RULES"), rule_floor=8,
        manifest="L4.2_drug_indication_4224_manifest.json",
        values={"section_id": "4.2.24", "len(set(encoded_clause_ids))": 30},
        golden=Golden(file="drug_indication_4.2.24_a24.json", scope="batch"),
    ),
    Clause(
        id="4227_a8", rules=_legacy("drug_indication_4227_a8_batch_rules.py:BATCH_A8_RULES"),
        rule_floor=10, gate_b_on_every_rule=True,
        golden=Golden(
            file="drug_indication_4.2.27_a8.json", scope="rule",
            line_fields=("drug_inpatient_supply",),
        ),
    ),
    Clause(
        id="4233", rules=_json_rules("anti_vegf_prose.json"),
        rule_ids=frozenset({
            "4.2.33.A.bevacizumab_first_line_wet_amd",
            "4.2.33.A.anti_vegf_switch_after_bevacizumab_failure",
            "4.2.33.C.anti_vegf_switch_after_bevacizumab_pm_knv",
            "4.2.33.general_ranibizumab_aflibersept_loading_protocol",
            "4.2.33.general_switch_to_bevacizumab",
            "4.2.33.Ç.deksametazon_timing_after_anti_vegf",
            "4.2.33.E.siklosporin_dry_eye_annual_report",
            "4.2.33.B.ranibizumab_rvdt_loading_protocol",
        }),
        manifest="L4.33_anti_vegf_4.2.33_manifest.json", floors={"rules_in_json": 27},
        encodes=("C006616", "C006617", "C006618"), in_coverage_union=True,
        golden=Golden(
            file="drug_indication_4.2.33_a2c.json", scope="corpus_rule", routes=False,
            line_fields=("annual_application_count", "is_loading_phase"),
        ),
    ),
    Clause(
        id="4234", rules=_legacy("drug_indication_4234_batch_rules.py:BATCH_MS4234_RULES"),
        rule_floor=6,
        gate_b_resolves_to=("C006716", "C006724", "C006730", "C006736", "C006760", "C006766"),
        manifest="L4.2_drug_indication_4234_manifest.json",
        values={
            "section_id": "4.2.34", "section_clause_total": 48, "tier_a_pending_count": 0,
            "rules_in_json": 18, "tier_c_deferred_count": 34,
        },
        pairs=(("encoded_clause_count", "len(encoded_clause_ids)"),),
        golden=Golden(file="drug_indication_4.2.34.json", scope="batch"),
    ),
    Clause(
        id="4235_4237", rules=_legacy("drug_indication_4235_4237_batch_rules.py:BATCH_A5_RULES"),
        rule_floor=5,
        rule_ids=frozenset({
            "4.2.35.pregabalin_fibromyalgia_board_6mo", "4.2.37.pegvisomant_endocrine_prescriber",
        }),
        manifest="L4.2_drug_indication_4235_4237_manifest.json",
        values={"section_id": "4.2.35,4.2.37"},
        pairs=(("encoded_clause_count", "len(set(encoded_clause_ids))"),), encodes=("C006784",),
        golden=Golden(file="drug_indication_4.2.35_4.2.37_a5.json", scope="batch"),
    ),
    Clause(
        id="4238", rules=_legacy("drug_indication_4238_batch_rules.py:BATCH_A5_RULES"),
        rule_floor=5,
        rule_ids=frozenset({
            "4.2.38.first_line_oral_antidiabetic", "4.2.38.dpp4_gliptin_specialist_report",
        }),
        manifest="L4.2_drug_indication_4238_manifest.json",
        values={"section_id": "4.2.38", "section_clause_total": 21, "tier_a_pending_count": 0},
        pairs=(
            ("encoded_clause_count", "len(set(encoded_clause_ids))"),
            ("tier_c_deferred_count", "len(tier_c_deferred_clause_ids)"),
        ),
        golden=Golden(file="drug_indication_4.2.38_a5.json", scope="batch"),
    ),
)
_BY_ID = {row.id: row for row in ROWS}


def _rows(selected: Callable[[Clause], object]) -> list:
    return [pytest.param(row, id=row.id) for row in ROWS if selected(row)]


@cache
def _rules(row_id: str) -> list[dict]:
    return _BY_ID[row_id].rules()


def _gate_b_sources(row_id: str) -> frozenset[str]:
    return frozenset(cid for rule in _rules(row_id) for cid in rule.get("gate_b_sources") or [])


@cache
def _manifest(name: str) -> dict:
    return json.loads((_DATA / "prose_manifests" / name).read_text(encoding="utf-8"))


def _measure(manifest: dict, name: str) -> object:
    if name.startswith("len(set("):
        return len(set(manifest.get(name[len("len(set("):-2]) or []))
    if name.startswith("len("):
        return len(manifest.get(name[len("len("):-1]) or [])
    return manifest.get(name)


def _claim(primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-1",
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="dahiliye",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 1),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-drug-indication-clauses",
    )


def _drug_line(
    *,
    drug_name: str,
    report_present: bool | None,
    report_duration_months: int | None = None,
    prescriber_specialty: str | None = None,
    service_date: date = date(2026, 1, 2),
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-1",
        prescription_id="RX-1",
        claim_id="C-1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=service_date,
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("720"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=report_duration_months,
        prescriber_specialty=prescriber_specialty,
    )


@pytest.mark.parametrize(
    "row", _rows(lambda r: r.rule_floor is not None or r.rule_count is not None or r.rule_ids)
)
def test_rule_set(row: Clause) -> None:
    rules = _rules(row.id)
    rule_ids = {str(rule["rule_id"]) for rule in rules}
    if row.rule_floor is not None:
        soft_floor(len(rules), row.rule_floor, label=row.id)
    if row.rule_count is not None:
        assert len(rules) == row.rule_count
    if row.only_rule_ids:
        assert rule_ids == row.rule_ids
    else:
        assert row.rule_ids <= rule_ids


@pytest.mark.parametrize(
    "row",
    _rows(lambda r: r.gate_b_on_every_rule or r.gate_b_count is not None or r.gate_b_resolves_to),
)
def test_gate_b_sources(row: Clause) -> None:
    sources = _gate_b_sources(row.id)
    if row.gate_b_on_every_rule:
        assert sources
        assert all(rule.get("gate_b_sources") for rule in _rules(row.id))
    if row.gate_b_count is not None:
        assert len(sources) == row.gate_b_count
    if row.gate_b_resolves_to:
        expected = frozenset(reviewed_clause_id(cid) for cid in row.gate_b_resolves_to)
        assert resolve_gate_b_cites_to_clause_ids(sources) == expected


@pytest.mark.parametrize("row", _rows(lambda r: r.covered_by))
def test_gate_b_sources_are_encoded(row: Clause) -> None:
    sources = _gate_b_sources(row.id)
    if row.covered_by == "prose_json":
        path = _DATA / "prose_rules/drug_indication_prose.json"
        rules = json.loads(path.read_text(encoding="utf-8"))["rules"]
        assert sources <= {cid for rule in rules for cid in rule.get("gate_b_sources") or []}
        return
    manifest = _manifest(row.manifest)
    if row.covered_by == "resolved":
        assert resolve_gate_b_cites_to_clause_ids(sources) <= encoded_like_clause_ids(manifest)
    elif row.covered_by == "encoded_ids":
        encoded = frozenset(manifest.get("encoded_clause_ids") or [])
        assert cites_covered_by_encoded(sources, encoded)
    else:
        assert row.covered_by == "encoded_like"
        assert cites_covered_by_encoded(sources, encoded_like_clause_ids(manifest))
    if row.count_covers_gate_b:
        assert manifest.get("encoded_clause_count", 0) >= len(sources)


@pytest.mark.parametrize("row", _rows(lambda r: r.values or r.floors or r.pairs or r.encodes))
def test_manifest_facts(row: Clause) -> None:
    manifest = _manifest(row.manifest)
    for name, value in row.values.items():
        assert _measure(manifest, name) == value, name
    for name, floor in row.floors.items():
        soft_floor(int(_measure(manifest, name) or 0), floor, label=f"{row.id} {name}")
    for left, right in row.pairs:
        assert _measure(manifest, left) == _measure(manifest, right), (left, right)
    encoded = set(manifest.get("encoded_clause_ids") or [])
    for baseline_id in row.encodes:
        assert reviewed_clause_id(baseline_id) in encoded, baseline_id


@pytest.mark.parametrize("row", _rows(lambda r: r.in_coverage_union))
def test_manifest_encoded_clauses_are_in_the_coverage_union(row: Clause) -> None:
    from scripts.sut.prose.coverage import _load_drug_indication_encoded_clause_ids

    # Heading/chapter ids may linger on older manifests; the coverage union keeps
    # only the encode-eligible cites of the rule JSON.
    clauses = pl.read_parquet(_DATA / "sut_clauses.parquet")
    structural = set(
        clauses.filter(pl.col("clause_type").is_in(list(STRUCTURAL_NON_LINKABLE_TYPES)))[
            "clause_id"
        ].to_list()
    )
    encoded = set(_manifest(row.manifest).get("encoded_clause_ids") or [])
    assert (encoded - structural).issubset(_load_drug_indication_encoded_clause_ids())


def _golden_cases() -> list:
    cases = []
    for row in ROWS:
        if row.golden is not None:
            path = _DATA / "prose_rules/golden" / row.golden.file
            samples = json.loads(path.read_text(encoding="utf-8"))["samples"]
            cases += [pytest.param(row, s, id=f"{row.id}-{i}") for i, s in enumerate(samples)]
    return cases


def _golden_rules(row: Clause, sample: dict) -> list[dict] | None:
    scope = row.golden.scope
    if scope == "corpus":
        return None
    if scope == "batch":
        return [dict(rule) for rule in _rules(row.id)]
    assert scope in {"rule", "corpus_rule"}, scope
    pool = _rules(row.id) if scope == "rule" else list_drug_indication_rules()
    if scope == "rule":
        assert sample["rule_id"] in {str(rule["rule_id"]) for rule in pool}, sample
    rule = next(rule for rule in pool if rule["rule_id"] == sample["rule_id"])
    if sample.get("gate_b_source"):
        assert cite_in_sources(sample["gate_b_source"], rule.get("gate_b_sources") or []), sample
    return [dict(rule)]


@pytest.mark.parametrize(("row", "sample"), _golden_cases())
def test_golden_sample(row: Clause, sample: dict) -> None:
    golden = row.golden
    rule_id = sample["rule_id"]
    line = _drug_line(
        drug_name=sample["drug_name"],
        report_present=sample.get("report_present"),
        report_duration_months=sample.get("report_duration_months"),
        prescriber_specialty=sample.get("prescriber_specialty"),
        service_date=date.fromisoformat(sample.get("service_date", "2026-01-02")),
    )
    hit = evaluate_drug_indication_line(
        drug_line=replace(line, **{name: sample.get(name) for name in golden.line_fields}),
        claim=_claim(sample["primary_icd10"]),
        diagnoses=(),
        rules=_golden_rules(row, sample),
    )
    expected = sample.get("expect_violation")
    if expected is None:
        assert hit is None, sample
    else:
        assert hit is not None, sample
        assert hit["violation_kind"] == expected, sample
        if golden.routes and expected in _ROUTE_VIOLATIONS:
            assert hit["rule_id"] is None, sample
            assert rule_id in hit["eligible_route_rule_ids"], sample
        else:
            assert hit["rule_id"] in {rule_id, *golden.alternates.get(rule_id, ())}, sample
    if golden.clinical_set and sample.get("expect_clinical_status"):
        assert hit["severity"] == sample["expect_severity"]
        observed = next(
            restriction for restriction in hit["clinical_restrictions"]
            if restriction["constraint_set"] == golden.clinical_set
        )
        assert observed["criterion_status"] == sample["expect_clinical_status"]
        assert sample["expect_missing_input"] in observed["missing_inputs"]
        assert hit["clinical_eligibility_complete"] is sample["expect_clinical_eligibility_complete"]
        money = ("payable_try", "risk_amount", "savings_try", "recoverable_uplift_try")
        assert not any(key in hit for key in money)


# Checks only one clause group makes.


def test_4201_w4_manifest_trace_completeness() -> None:
    manifest = _manifest(_M4201)
    traces = manifest["clause_traces"]
    total = manifest["section_clause_total"]
    assert len(traces) == total
    status_counts = Counter(trace["manifest_status"] for trace in traces)
    # C003756 / C003834 moved from tier_b_pending to tier_c_deferred via deferral_table.yaml.
    assert status_counts["tier_b_pending"] == 0
    assert sum(status_counts.values()) == total
    for trace in traces:
        if trace["manifest_status"] == "tier_c_deferred":
            assert trace.get("defer_reason")


def test_4210_inn_list_covers_lsd_drugs() -> None:
    inns = {name for rule in _rules("4210") for name in rule.get("drug_names") or []}
    for inn in ("imiglucerase", "eliglustat", "agalsidase", "laronidase", "alglucosidase",
                "miglustat"):
        assert inn in inns


def test_4213_tier_b_oral_switch_in_force_sources() -> None:
    oral_switch = [
        rule for rule in _rules("4213_tier_b") if str(rule["rule_id"]) in {
            "4.2.13.hbv_oral_antiviral_switch_adult_report",
            "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
        }
    ]
    sources = {cid for rule in oral_switch for cid in rule.get("gate_b_sources") or []}
    assert cite_in_sources(reviewed_clause_id("C004638"), sources)
    assert cite_in_sources(reviewed_clause_id("C004647"), sources)
    assert resolve_gate_b_cites_to_clause_ids(sources) >= frozenset(
        {reviewed_clause_id("C004638"), reviewed_clause_id("C004647")}
    )


def test_4217_denosumab_supported_source_date_retains_missing_report_enforcement() -> None:
    day = date(2026, 10, 2)
    drug = replace(
        _drug_line(
            drug_name="PROLIA 60 MG (DENOSUMAB)", report_present=False,
            prescriber_specialty="endokrinoloji", service_date=day,
        ),
        indication_evidence=IndicationEvidence(
            applies_on=day, assessment_date=day, indication="glucocorticoid_bone_loss",
            age_group="adult", osteoporosis_diagnosed=True, high_fracture_risk=True,
            long_term_glucocorticoid_treatment=True, glucocorticoid_associated_bone_loss=True,
            bisphosphonate_intolerant=True,
        ),
    )
    hit = evaluate_drug_indication_line(drug_line=drug, claim=_claim("M81.0"), diagnoses=())
    assert hit["violation_kind"] == "missing_board_report"
    assert hit["severity"] == "error"
    assert hit["clinical_restrictions"][0]["criterion_status"] == "criterion_clear"
    assert hit["clinical_eligibility_complete"] is False


def test_4218_4236_gate_b_sources_cover_all_tier_a_clauses() -> None:
    clauses = pl.read_parquet(_DATA / "sut_clauses.parquet")
    refs = [cid for rule in _rules("4218_4236") for cid in rule.get("gate_b_sources") or []]
    encoded = resolve_gate_b_sources_to_clause_ids(
        refs, clauses, in_force_only=True, allow_ambiguous=True
    )
    assert encoded == {
        reviewed_clause_id(cid)
        for cid in ("C006147", "C006797", "C006798", "C006799", "C006801")
    }


def test_4234_report_rules_cite_six_tier_a_clauses() -> None:
    tier_a = {
        str(rule["gate_b_sources"][0]) for rule in _rules("4234") if rule.get("report_required")
    }
    assert len(tier_a) == 6
