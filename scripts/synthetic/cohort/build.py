"""Build the synthetic v3 showcase dataset (9 claim Parquet tables and cohort_registry.json)."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any

import polars as pl

from scripts.synthetic.faults import (
    FaultInjectionRecord,
    FaultRegistry,
    FaultSpec,
    apply_fault,
    build_expected_rule_outputs,
    load_registry,
    load_siblings,
    make_record,
)
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.expand import expand

from .catalogs import CohortCatalogs
from .clean import (
    CLEAN_TABLE_FILES,
    CleanTableError,
    build_clean_tables,
    clean_tables_digest,
    validate_clean_tables,
    write_clean_tables,
)
from .clinical import (
    CLINICAL_PATH,
    ClinicalLoadError,
    ShowcaseClinical,
    check_clinical,
    load_clinical,
)
from .compose import ComposedClaim, EncounterContext, compose_claim, money
from .ids import claim_id, episode_id, patient_id
from .labs import expected_lab_row_count
from .recipes import (
    RECIPES_PATH,
    RecipeLoadError,
    ShowcaseRecipes,
    check_recipes,
    load_recipes,
)
from .tables import (
    TABLE_FILES,
    build_tables,
    copay_profile,
    tables_digest,
    validate_tables,
    write_tables,
)

REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO / "data" / "synthetic" / "showcase"
SCHEMA_VERSION = 1
DATASET_ID = "showcase-v3"
_ZERO = Decimal("0.00")


class BuildError(ValueError):
    """Raised when building or validating the showcase cohort dataset fails."""


@dataclass(frozen=True)
class BuildResult:
    """In-memory result of `build_showcase()`: 9 claim tables, 3 clean tables, registry, and claims."""

    tables: dict[str, pl.DataFrame]
    clean_tables: dict[str, pl.DataFrame]
    registry: dict[str, Any]
    registry_json: str
    claims: tuple[ComposedClaim, ...]
    clean_claims: tuple[ComposedClaim, ...]
    records: tuple[FaultInjectionRecord, ...]
    answer_rows: tuple[dict[str, Any], ...]
    copay_profiles: tuple[dict[str, Any], ...]
    clinical: ShowcaseClinical

    @property
    def clean(self) -> dict[str, pl.DataFrame]:
        """Alias for `clean_tables`."""
        return self.clean_tables

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BuildResult):
            return NotImplemented
        if set(self.tables) != set(other.tables):
            return False
        for name, df in self.tables.items():
            other_df = other.tables[name]
            if dict(df.schema) != dict(other_df.schema) or not df.equals(other_df, null_equal=True):
                return False
        if set(self.clean_tables) != set(other.clean_tables):
            return False
        for name, df in self.clean_tables.items():
            other_df = other.clean_tables[name]
            if dict(df.schema) != dict(other_df.schema) or not df.equals(other_df, null_equal=True):
                return False
        return (
            self.registry == other.registry
            and self.registry_json == other.registry_json
            and self.claims == other.claims
            and self.clean_claims == other.clean_claims
            and self.records == other.records
            and self.answer_rows == other.answer_rows
            and self.copay_profiles == other.copay_profiles
            and self.clinical == other.clinical
        )


def format_registry_json(registry: Mapping[str, Any]) -> str:
    """Serialize `cohort_registry.json` deterministically (sorted keys, 2-space indent, UTF-8, newline)."""
    return json.dumps(dict(registry), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _resolve_target_line_id(fault: FaultSpec, faulty_claim: ComposedClaim) -> str:
    finding = fault.expected_finding
    if finding.line_type == "fatura":
        return ""
    target_entry = finding.target_entry_id
    if not target_entry:
        raise BuildError(
            f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
            f"line_type {finding.line_type!r} requires target_entry_id"
        )
    matches = faulty_claim.entry_line_ids.get(target_entry, ())
    if len(matches) != 1:
        raise BuildError(
            f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
            f"target_entry_id {target_entry!r} resolved to {len(matches)} lines (expected 1)"
        )
    return matches[0]


def _resolve_evidence_line_ids(fault: FaultSpec, faulty_claim: ComposedClaim) -> tuple[str, ...]:
    finding = fault.expected_finding
    resolved: list[str] = []
    for entry_id in finding.evidence_entry_ids:
        matches = faulty_claim.entry_line_ids.get(entry_id, ())
        if not matches:
            raise BuildError(
                f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
                f"evidence_entry_id {entry_id!r} resolved to 0 lines"
            )
        resolved.extend(matches)
    return tuple(resolved)


def _line_billed_amount(claim: ComposedClaim, line_id: str, *, fault_id: str) -> Decimal:
    for p in claim.procedures:
        if p.procedure_line_id == line_id:
            return p.billed_amount_try
    for m in claim.materials:
        if m.material_line_id == line_id:
            return m.billed_amount_try
    for d in claim.drugs:
        if d.drug_claim_line_id == line_id:
            return d.billed_amount_try
    raise BuildError(
        f"fault {fault_id} on {claim.header.claim_id}: target line_id {line_id!r} not found in claim"
    )


def _compute_effect_amount(
    fault: FaultSpec,
    clean_claim: ComposedClaim,
    faulty_claim: ComposedClaim,
    target_line_id: str,
) -> Decimal:
    effect_kind = fault.expected_finding.effect_kind
    clean_total = clean_claim.header.expected_total_billed_try
    faulty_total = faulty_claim.header.expected_total_billed_try

    if effect_kind == "revenue_uplift":
        diff = money(clean_total - faulty_total)
        if diff <= _ZERO:
            raise BuildError(
                f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
                f"revenue_uplift requires clean_total ({clean_total}) > faulty_total ({faulty_total})"
            )
        return diff

    if effect_kind == "deduction_risk":
        diff = money(faulty_total - clean_total)
        if diff > _ZERO:
            return diff
        if not target_line_id:
            raise BuildError(
                f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
                f"deduction_risk with zero total difference requires a target line_id"
            )
        line_amount = money(
            _line_billed_amount(faulty_claim, target_line_id, fault_id=fault.fault_id)
        )
        if line_amount <= _ZERO:
            raise BuildError(
                f"fault {fault.fault_id} on {faulty_claim.header.claim_id}: "
                f"deduction_risk target line {target_line_id!r} has non-positive billed amount {line_amount}"
            )
        return line_amount

    if effect_kind == "compliance_error":
        return _ZERO

    raise BuildError(f"fault {fault.fault_id}: unsupported effect_kind {effect_kind!r}")


def _make_injection_record(
    fault: FaultSpec,
    clean_claim: ComposedClaim,
    faulty_claim: ComposedClaim,
) -> FaultInjectionRecord:
    target_line_id = _resolve_target_line_id(fault, faulty_claim)
    evidence_line_ids = _resolve_evidence_line_ids(fault, faulty_claim)
    amount = _compute_effect_amount(fault, clean_claim, faulty_claim, target_line_id)
    clean_total = money(clean_claim.header.expected_total_billed_try)
    faulty_total = money(faulty_claim.header.expected_total_billed_try)

    return make_record(
        fault,
        patient_id=faulty_claim.header.patient_id,
        claim_id=faulty_claim.header.claim_id,
        line_id=target_line_id,
        line_ids=evidence_line_ids,
        amount_try=f"{amount:.2f}",
        billed_clean_try=f"{clean_total:.2f}",
        billed_faulty_try=f"{faulty_total:.2f}",
    )


def validate_cohort_registry(
    registry: Mapping[str, Any],
    tables: Mapping[str, pl.DataFrame],
    clean_tables: Mapping[str, pl.DataFrame] | None = None,
) -> None:
    """Verify consistency between `cohort_registry.json`, the 9 claim tables, and the 3 clean tables."""
    validate_tables(tables)

    if registry.get("schema_version") != SCHEMA_VERSION:
        raise BuildError(
            f"cohort_registry schema_version must be {SCHEMA_VERSION}, got {registry.get('schema_version')!r}"
        )
    if registry.get("dataset_id") != DATASET_ID:
        raise BuildError(
            f"cohort_registry dataset_id must be {DATASET_ID!r}, got {registry.get('dataset_id')!r}"
        )
    if "seed" not in registry or registry["seed"] is not None:
        raise BuildError(f"cohort_registry seed must be None, got {registry.get('seed')!r}")

    fresh_digest = tables_digest(tables)
    reg_digest = registry.get("tables_digest")
    if reg_digest != fresh_digest:
        mismatched = [
            k
            for k in TABLE_FILES
            if not isinstance(reg_digest, Mapping) or reg_digest.get(k) != fresh_digest[k]
        ]
        raise BuildError(f"cohort_registry tables_digest mismatch on: {mismatched}")

    expected_counts = {name: tables[name].height for name in TABLE_FILES}
    reg_counts = registry.get("counts")
    if reg_counts != expected_counts:
        raise BuildError(
            f"cohort_registry counts mismatch: expected {expected_counts}, got {reg_counts}"
        )

    lab_proc_codes = (
        tables["procedure_claim_lines.parquet"]
        .filter(pl.col("procedure_category") == "laboratuvar")["procedure_code"]
        .to_list()
    )
    expected_lab_count = (
        clean_tables["lab_clean.parquet"].height
        if clean_tables is not None
        else expected_lab_row_count(lab_proc_codes)
    )
    expected_clean_counts = {
        "anadata_clean.parquet": tables["claim_headers.parquet"].height,
        "lab_clean.parquet": expected_lab_count,
        "recete_clean.parquet": tables["drug_claim_lines.parquet"].height,
    }
    reg_clean_counts = registry.get("clean_counts")
    if reg_clean_counts != expected_clean_counts:
        raise BuildError(
            f"cohort_registry clean_counts mismatch: expected {expected_clean_counts}, "
            f"got {reg_clean_counts}"
        )

    reg_clean_digest = registry.get("clean_tables_digest")
    if not isinstance(reg_clean_digest, Mapping) or set(reg_clean_digest.keys()) != set(
        CLEAN_TABLE_FILES
    ):
        raise BuildError(
            f"cohort_registry clean_tables_digest must map {list(CLEAN_TABLE_FILES)}, "
            f"got {reg_clean_digest!r}"
        )
    for k, val in reg_clean_digest.items():
        if not isinstance(val, str) or len(val) != 64:
            raise BuildError(
                f"cohort_registry clean_tables_digest[{k!r}] must be a 64-char sha256 hex digest, "
                f"got {val!r}"
            )

    if clean_tables is not None:
        try:
            validate_clean_tables(clean_tables, tables)
        except CleanTableError as exc:
            raise BuildError(str(exc)) from exc
        fresh_clean_digest = clean_tables_digest(clean_tables)
        if reg_clean_digest != fresh_clean_digest:
            mismatched_clean = [
                k for k in CLEAN_TABLE_FILES if reg_clean_digest.get(k) != fresh_clean_digest[k]
            ]
            raise BuildError(f"cohort_registry clean_tables_digest mismatch on: {mismatched_clean}")

    headers_df = tables["claim_headers.parquet"]
    claim_to_patient = dict(
        zip(
            headers_df["claim_id"].to_list(),
            headers_df["patient_id"].to_list(),
            strict=True,
        )
    )

    roles = registry.get("roles")
    if not isinstance(roles, Mapping) or "default_landing" not in roles:
        raise BuildError("cohort_registry roles must be a mapping containing 'default_landing'")
    for role_name, target in roles.items():
        if not isinstance(target, Mapping) or set(target.keys()) != {"patient_id", "claim_id"}:
            raise BuildError(
                f"role {role_name!r} must map to {{'patient_id', 'claim_id'}}, got {target!r}"
            )
        cid = target["claim_id"]
        pid = target["patient_id"]
        if cid not in claim_to_patient:
            raise BuildError(f"role {role_name!r} references missing claim_id {cid!r}")
        if claim_to_patient[cid] != pid:
            raise BuildError(
                f"role {role_name!r} patient_id {pid!r} does not match claim {cid!r} "
                f"patient_id {claim_to_patient[cid]!r}"
            )

    encounters = registry.get("encounters")
    if not isinstance(encounters, list) or len(encounters) != headers_df.height:
        raise BuildError("cohort_registry encounters length does not match claim_headers count")
    for enc in encounters:
        cid = enc.get("claim_id")
        pid = enc.get("patient_id")
        if cid not in claim_to_patient or claim_to_patient[cid] != pid:
            raise BuildError(f"encounter {enc!r} does not resolve to an existing claim/patient")

    raw_faults = registry.get("faults")
    if not isinstance(raw_faults, list):
        raise BuildError("cohort_registry faults must be a list")
    try:
        records = [FaultInjectionRecord.model_validate(item) for item in raw_faults]
    except Exception as exc:
        raise BuildError(f"invalid FaultInjectionRecord in cohort_registry: {exc}") from exc

    if [r.claim_id for r in records] != sorted(r.claim_id for r in records):
        raise BuildError("cohort_registry faults must be ordered by claim_id")

    lines_df = pl.concat(
        [
            tables["procedure_claim_lines.parquet"].select(
                pl.lit("islem").alias("line_type"),
                pl.col("procedure_line_id").alias("line_id"),
                pl.col("billed_amount_try"),
            ),
            tables["material_claim_lines.parquet"].select(
                pl.lit("malzeme").alias("line_type"),
                pl.col("material_line_id").alias("line_id"),
                pl.col("billed_amount_try"),
            ),
            tables["drug_claim_lines.parquet"].select(
                pl.lit("ilac").alias("line_type"),
                pl.col("drug_claim_line_id").alias("line_id"),
                pl.col("billed_amount_try"),
            ),
        ]
    )
    line_keys = zip(
        lines_df["line_type"].to_list(),
        lines_df["line_id"].to_list(),
        strict=True,
    )
    line_amounts: dict[tuple[str, str], Decimal] = dict(
        zip(
            line_keys,
            map(money, lines_df["billed_amount_try"].to_list()),
            strict=True,
        )
    )
    performed_ids = set(tables["performed_procedure_lines.parquet"]["performed_line_id"].to_list())

    for rec in records:
        if rec.line_type != "fatura":
            key = (rec.line_type, rec.line_id)
            if key not in line_amounts:
                raise BuildError(
                    f"record {rec.injection_id}: target line {key} does not exist in tables"
                )
        for ev_id in rec.line_ids:
            if ev_id not in performed_ids:
                raise BuildError(
                    f"record {rec.injection_id}: evidence line_id {ev_id!r} does not exist in "
                    f"performed_procedure_lines.parquet"
                )
        clean_dec = Decimal(rec.billed_clean_try)
        faulty_dec = Decimal(rec.billed_faulty_try)
        amt_dec = Decimal(rec.amount_try)
        if rec.effect_kind == "revenue_uplift":
            if amt_dec != clean_dec - faulty_dec or amt_dec <= _ZERO:
                raise BuildError(
                    f"record {rec.injection_id}: revenue_uplift amount_try {rec.amount_try} "
                    f"does not equal clean - faulty ({clean_dec - faulty_dec:.2f})"
                )
        elif rec.effect_kind == "deduction_risk":
            expected_amt = (
                faulty_dec - clean_dec
                if faulty_dec > clean_dec
                else line_amounts[(rec.line_type, rec.line_id)]
            )
            if amt_dec != expected_amt:
                raise BuildError(
                    f"record {rec.injection_id}: deduction_risk amount_try {rec.amount_try} "
                    f"does not equal expected {expected_amt:.2f}"
                )
        elif rec.effect_kind == "compliance_error":
            if amt_dec != _ZERO:
                raise BuildError(
                    f"record {rec.injection_id}: compliance_error amount_try must be 0.00, "
                    f"got {rec.amount_try}"
                )

    expected_answer_df = build_tables(
        (),
        answer_rows=build_expected_rule_outputs(records),
        copay_profiles=(),
    )["expected_rule_outputs.parquet"]
    if not expected_answer_df.equals(tables["expected_rule_outputs.parquet"], null_equal=True):
        raise BuildError(
            "expected_rule_outputs.parquet does not match build_expected_rule_outputs(faults)"
        )


def build_showcase(
    recipes_path: Path | str | None = None,
    *,
    recipes: ShowcaseRecipes | None = None,
    clinical_path: Path | str | None = None,
    clinical: ShowcaseClinical | None = None,
    catalogs: CohortCatalogs | None = None,
    pathways: Mapping[str, Pathway] | None = None,
    siblings: Mapping[str, Pathway] | None = None,
    fault_registry: FaultRegistry | None = None,
) -> BuildResult:
    """Build the 8-patient showcase dataset and `cohort_registry.json` purely in memory."""
    loaded_recipes = recipes if recipes is not None else load_recipes(recipes_path or RECIPES_PATH)
    loaded_fault_reg = fault_registry if fault_registry is not None else load_registry()
    problems = check_recipes(loaded_recipes, fault_registry=loaded_fault_reg)
    if problems:
        raise RecipeLoadError(problems)

    cats = catalogs if catalogs is not None else CohortCatalogs()
    loaded_clinical = (
        clinical if clinical is not None else load_clinical(clinical_path or CLINICAL_PATH)
    )
    clinical_problems = check_clinical(loaded_clinical, recipes=loaded_recipes, catalogs=cats)
    if clinical_problems:
        raise ClinicalLoadError(clinical_problems)

    pathways_map = pathways if pathways is not None else load_all()
    siblings_map = siblings if siblings is not None else load_siblings()
    faults_by_id: dict[str, FaultSpec] = {f.fault_id: f for f in loaded_fault_reg.faults}

    faulty_claims: list[ComposedClaim] = []
    clean_claims: list[ComposedClaim] = []
    records_unsorted: list[FaultInjectionRecord] = []
    profiles: list[dict[str, Any]] = []
    encounters: list[dict[str, Any]] = []
    roles: dict[str, dict[str, str]] = {}

    for idx, recipe in enumerate(loaded_recipes.recipes):
        pathway = pathways_map[recipe.pathway]
        fault = faults_by_id[recipe.fault]
        pins = pathway.showcase

        clean_bill = expand(pathway, annotate=True)
        faulty_bill = apply_fault(fault, pathway, siblings=siblings_map, annotate=True)

        pid = patient_id(recipe.patient_no)
        cid = claim_id(pid, 1)
        eid = episode_id(pid, 1)
        ctx = EncounterContext(
            patient_id=pid,
            claim_id=cid,
            episode_id=eid,
            facility_tier="2_3_basamak_ozel",
            provider_type="Ozel",
            scenario_tag=pathway.id,
            occupational_context="none",
            package_candidate=(pathway.billing_mode == "package"),
        )

        clean_claim = compose_claim(clean_bill, ctx, cats)
        faulty_claim = compose_claim(faulty_bill, ctx, cats)

        record = _make_injection_record(fault, clean_claim, faulty_claim)

        ref_date = faulty_claim.header.admission_date or faulty_claim.header.claim_start_date
        birth_year = ref_date.year - pins.age
        profile = copay_profile(pid, birth_year)

        story = fault.story or pins.story
        role_target = {"patient_id": pid, "claim_id": cid}
        if idx == 0 or story == "S1":
            roles["default_landing"] = dict(role_target)
        roles[f"showcase_{story}"] = dict(role_target)

        encounters.append(
            {
                "patient_id": pid,
                "claim_id": cid,
                "pathway_id": pathway.id,
                "story": story,
                "tier": "showcase",
                "is_clean": False,
                "fault_id": fault.fault_id,
            }
        )

        clean_claims.append(clean_claim)
        faulty_claims.append(faulty_claim)
        records_unsorted.append(record)
        profiles.append(profile)

    ordered_records = tuple(sorted(records_unsorted, key=lambda r: (r.claim_id, r.fault_id)))
    answer_rows = tuple(build_expected_rule_outputs(ordered_records))

    tables = build_tables(
        faulty_claims,
        answer_rows=answer_rows,
        copay_profiles=profiles,
        medula_events=(),
    )
    validate_tables(tables)

    clean_tables = build_clean_tables(
        faulty_claims,
        clinical=loaded_clinical,
        pathways=pathways_map,
        siblings=siblings_map,
        catalogs=cats,
    )
    validate_clean_tables(clean_tables, tables)

    digest = tables_digest(tables)
    counts = {name: tables[name].height for name in TABLE_FILES}
    clean_digest = clean_tables_digest(clean_tables)
    clean_counts = {name: clean_tables[name].height for name in CLEAN_TABLE_FILES}

    registry: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "seed": None,
        "tables_digest": digest,
        "counts": counts,
        "clean_tables_digest": clean_digest,
        "clean_counts": clean_counts,
        "roles": roles,
        "encounters": encounters,
        "faults": [rec.model_dump(mode="json") for rec in ordered_records],
    }
    validate_cohort_registry(registry, tables, clean_tables)
    registry_json = format_registry_json(registry)

    return BuildResult(
        tables=tables,
        clean_tables=clean_tables,
        registry=registry,
        registry_json=registry_json,
        claims=tuple(faulty_claims),
        clean_claims=tuple(clean_claims),
        records=ordered_records,
        answer_rows=answer_rows,
        copay_profiles=tuple(profiles),
        clinical=loaded_clinical,
    )


def write_showcase(
    result: BuildResult,
    out_dir: Path | str = DEFAULT_OUT_DIR,
) -> dict[str, Path]:
    """Write the 9 claim tables, 3 clean tables, and `<out>/cohort_registry.json`."""
    validate_cohort_registry(result.registry, result.tables, result.clean_tables)
    out = Path(out_dir)
    claims_dir = out / "sut" / "claims"
    clean_dir = out / "sut" / "clean"
    written = write_tables(result.tables, claims_dir)
    written_clean = write_clean_tables(result.clean_tables, clean_dir, claims_tables=result.tables)
    written.update(written_clean)
    registry_path = out / "cohort_registry.json"
    registry_path.write_text(result.registry_json, encoding="utf-8")
    written["cohort_registry.json"] = registry_path
    return written


def check_showcase(
    out_dir: Path | str = DEFAULT_OUT_DIR,
    *,
    result: BuildResult | None = None,
) -> list[str]:
    """Compare a directory on disk against a fresh in-memory `build_showcase()` by content."""
    expected = result if result is not None else build_showcase()
    out = Path(out_dir)
    claims_dir = out / "sut" / "claims"
    clean_dir = out / "sut" / "clean"
    registry_path = out / "cohort_registry.json"
    diffs: list[str] = []

    if not registry_path.is_file():
        diffs.append(f"missing {registry_path}")
    else:
        try:
            actual_text = registry_path.read_text(encoding="utf-8")
            actual_json = json.loads(actual_text)
        except Exception as exc:
            diffs.append(f"unreadable {registry_path}: {exc}")
        else:
            if actual_json != expected.registry:
                diffs.append(f"content mismatch in {registry_path}")
            elif actual_text != expected.registry_json:
                diffs.append(f"formatting mismatch in {registry_path}")

    for name in TABLE_FILES:
        table_path = claims_dir / name
        if not table_path.is_file():
            diffs.append(f"missing {table_path}")
            continue
        try:
            actual_df = pl.read_parquet(table_path)
        except Exception as exc:
            diffs.append(f"unreadable {table_path}: {exc}")
            continue
        expected_df = expected.tables[name]
        if dict(actual_df.schema) != dict(expected_df.schema):
            diffs.append(
                f"schema mismatch in {table_path}: expected {dict(expected_df.schema)}, "
                f"got {dict(actual_df.schema)}"
            )
        elif not actual_df.equals(expected_df, null_equal=True):
            diffs.append(f"table content mismatch in {table_path}")

    for name in CLEAN_TABLE_FILES:
        clean_path = clean_dir / name
        if not clean_path.is_file():
            diffs.append(f"missing {clean_path}")
            continue
        try:
            actual_df = pl.read_parquet(clean_path)
        except Exception as exc:
            diffs.append(f"unreadable {clean_path}: {exc}")
            continue
        expected_df = expected.clean_tables[name]
        if dict(actual_df.schema) != dict(expected_df.schema):
            diffs.append(
                f"schema mismatch in {clean_path}: expected {dict(expected_df.schema)}, "
                f"got {dict(actual_df.schema)}"
            )
        elif not actual_df.equals(expected_df, null_equal=True):
            diffs.append(f"table content mismatch in {clean_path}")

    return diffs


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: `python -m scripts.synthetic.cohort.build [--out DIR] [--check]`."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.synthetic.cohort.build",
        description="Build or check the synthetic v3 showcase dataset.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Target output directory (default: data/synthetic/showcase).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build in memory and verify on-disk files match by content without writing.",
    )
    args = parser.parse_args(argv)

    result = build_showcase()
    if args.check:
        diffs = check_showcase(args.out, result=result)
        if diffs:
            for diff in diffs:
                print(f"FAIL: {diff}", file=sys.stderr)
            return 1
        print(f"{args.out}: ok ({len(result.claims)} claims, {len(TABLE_FILES)} tables)")
        return 0

    write_showcase(result, args.out)
    print(f"wrote {len(result.claims)} claims ({len(TABLE_FILES)} tables) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
