"""Explicit 499 -> final 3d29 source profile; prior profiles remain frozen.

All nineteen cache projections must match their own isolated source producer.
Only the reviewed organ quarantine, source inventory and name-scoped followup
receipts have transition permission. Private expected rows stay in memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.deploy import verify_source_refresh_transition as previous
from scripts.deploy import generate_candidate_source_roster as trace_parser
from scripts.deploy.generate_candidate_source_roster import validate_runtime_read_trace
from scripts.deploy.verify_candidate_cache import _parse_json, _stable_file_hash
from scripts.deploy.verify_same_input import _roster, normalize_attested_data_source

TRANSITION_CONTRACT = "bilun-source-refresh-499-3d29-v1"
BASELINE_CODE_SHA = previous.BASELINE_CODE_SHA
BASELINE_TREE = previous.BASELINE_TREE
PRODUCT_ANCHOR_SHA = "3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e"
PRODUCT_ANCHOR_TREE = "5c1ee20b6b2817de41e7f2ca5fcec68a1bbfe121"
INTEGRATION_SEED_SHA = "58e7a14294484de286bd6d98c677a10db8de800d"
INTEGRATION_SEED_TREE = "d04625ecb21e92b7fd8bafa6d80fd893f227b620"
SEED_PARENTS = ("de55a95ccb0032199c54a86244af990238ab5ebd", PRODUCT_ANCHOR_SHA)
PRODUCT_HISTORY = (
    (previous.PRODUCT_ANCHOR_SHA, previous.PRODUCT_ANCHOR_TREE, BASELINE_CODE_SHA),
    ("58b6ac345dc86884dafe0b2dd31689a8a1845bfb", "e3eca9741bc13d343459cb3fe31d5759d4937196", previous.PRODUCT_ANCHOR_SHA),
    (PRODUCT_ANCHOR_SHA, PRODUCT_ANCHOR_TREE, "58b6ac345dc86884dafe0b2dd31689a8a1845bfb"),
)
AUTHORIZED_TOOLING_PATHS = frozenset({
    "scripts/deploy/verify_final_source_refresh_transition.py",
    "scripts/deploy/verify_candidate_semantics.py",
    "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_private_rehearsal.py",
    "tests/unit/deploy/test_final_source_refresh_transition.py",
})
_SEED_TOOLING_EXCLUSIONS = AUTHORIZED_TOOLING_PATHS | {
    "scripts/deploy/verify_source_refresh_transition.py",
    "tests/unit/deploy/test_source_refresh_transition.py",
}
_OWNED_TABLES = frozenset({*previous._TABLES, "cohort_compliance_index"})
_STRICT_TABLES = frozenset({
    "patient_detail_cache", "patient_outcome_base", "cohort_optimization_summary",
    "patient_alerts_summary", "cohort_recovery_summary", "cohort_sut_summary",
    "validation_payload", "patient_meta", "cohort_sut_exposure", "patient_alerts_payload",
    "patient_diagnoses", "patient_alert_rows", "patient_billing_reports",
})
_TABLES = _OWNED_TABLES | _STRICT_TABLES
_ROW_TABLES = frozenset({"cohort_sut_summary", "validation_payload", "patient_meta",
    "cohort_sut_exposure", "patient_alerts_payload", "patient_diagnoses",
    "patient_alert_rows", "patient_billing_reports"})
FOLLOWUP_RULE_IDS = frozenset({"4.2.57.clinical_16_week_response", "4.2.46.clinical_annual_reassessment"})
FOLLOWUP_CONSTRAINT = "followup_source_constraints"
FOLLOWUP_VERSION = "followup.atomic.v2.2026-10-03"
_WITNESS_FIELDS = frozenset({"patient_id", "claim_id", "drug_claim_line_id", "drug_name",
    "source_rule_ids", "constraint_set", "outcome", "receipts"})
_SUMMARY_FIELDS = frozenset({"schema_version", "available", "instrumented_families",
    "input_facts_available_count", "input_facts_missing_count", "predicate_attempted_count",
    "predicate_evaluated_count", "predicate_passed_count", "predicate_failed_count",
    "predicate_missing_inputs_count", "routes_blocked_source_count", "routes_blocked_inputs_count",
    "routes_skipped_count", "source_metrics_available", "source_unavailable_reason",
    "unresolved_source_ref_count", "source_clauses_touched_count", "complete_clause_mapping_available",
    "complete_clause_mapping_unavailable_reason", "source_clauses_fully_evaluated_count",
    "source_clause_ids", "fully_evaluated_source_clause_ids", "receipt_count",
    "receipt_sha256", "clinical_eligibility_complete"})
_FOLLOWUP_ROUTES = frozenset({"followup.source_date", "followup.medicine_family",
    "dupilumab.continuation.indication", "dupilumab.continuation.phase",
    "nintedanib.continuation.phase", "nintedanib.continuation.indication"})
_FOLLOWUP_INPUTS = {"drug_name", "drug_claim_date", "verified_source_for_service_date"} | {
    "followup_evidence." + field for field in ("applies_on", "assessment_date", "indication", "phase",
        "treatment_start_date", "baseline_assessment_date", "response_assessment_date",
        "week16_checkpoint_documented", "baseline_easi", "response_easi", "baseline_dlqi", "response_dlqi",
        "baseline_pruritus_nrs", "response_pruritus_nrs", "previous_report_date", "current_report_date",
        "fvc_assessment_outside_exacerbation", "previous_fvc_percent_predicted", "current_fvc_percent_predicted",
        "report_documents_fvc_response")}
_PROOF_BINDINGS: dict[object, str] = {}
# Exact loader/device reads only. Other necessary runtime files must be
# explicitly supplied as dependencies; unknown OS paths remain blockers.
RUNTIME_FILE_PATHS = ("/etc/locale.alias", "/opt/Bilun/.venv/pyvenv.cfg")
_OS_RUNTIME_ROOTS = (Path("/usr/lib"), Path("/lib"), Path("/usr/share/locale"))
_OS_RUNTIME_FILES = frozenset(path.resolve(strict=False) for path in {
    Path("/etc/ld.so.cache"), Path("/etc/localtime"), Path("/usr/share/zoneinfo/UTC"), Path("/dev/null"),
    Path("/proc/meminfo"), Path("/proc/cpuinfo"), Path("/sys/devices/system/cpu/online"),
    Path("/sys/devices/system/cpu/possible"), Path("/proc/sys/vm/overcommit_memory"),
    Path("/proc/sys/kernel/osrelease")})
_same, _digest, _canonical, _git = previous._same, previous._digest, previous._canonical, previous._git
_SHA, _SHA256 = previous._SHA, previous._SHA256
historical = previous.historical
BASELINE_SOURCE_HASH = previous.BASELINE_SOURCE_HASH
BASELINE_CONFIG_HASH = previous.BASELINE_CONFIG_HASH
INPUT_BYTES_SHA256 = previous.INPUT_BYTES_SHA256
_replay_checkout_binding = previous._replay_checkout_binding


def validate_transition_request(value: Mapping | None) -> dict | None:
    if not isinstance(value, Mapping) or value.get("contract") != TRANSITION_CONTRACT:
        return previous.validate_transition_request(value)
    if (set(value) != {"contract", "expected_candidate_sha", "expected_verifier_sha"}
            or any(not isinstance(value.get(key), str) or not _SHA.fullmatch(value[key])
                   for key in ("expected_candidate_sha", "expected_verifier_sha"))
            or value["expected_candidate_sha"] != value["expected_verifier_sha"]):
        raise ValueError("Final source profile requires one explicit immutable candidate/verifier")
    return dict(value)


def _product_closure(checkout: Path, sha: str) -> bytes:
    # Filtering a finite tooling roster preserves every product mode/type/blob.
    return b"\0".join(row for row in _git(checkout, "ls-tree", "-r", "-z", sha).split(b"\0")
                       if row and os.fsdecode(row.split(b"\t", 1)[1]) not in _SEED_TOOLING_EXCLUSIONS)


def _verify_candidate_history(checkout: Path, expected_candidate_sha: str) -> dict:
    if (not isinstance(expected_candidate_sha, str) or not _SHA.fullmatch(expected_candidate_sha)
            or _git(checkout, "rev-parse", "HEAD").decode().strip() != expected_candidate_sha):
        raise ValueError("Final profile checkout differs from reviewed candidate")
    for sha, tree in ((BASELINE_CODE_SHA, BASELINE_TREE),
                      (INTEGRATION_SEED_SHA, INTEGRATION_SEED_TREE),
                      *((sha, tree) for sha, tree, _ in PRODUCT_HISTORY)):
        if _git(checkout, "rev-parse", f"{sha}^{{tree}}").decode().strip() != tree:
            raise ValueError("Final profile pinned product/seed tree differs")
    for sha, _, parent in PRODUCT_HISTORY:
        if _git(checkout, "show", "-s", "--format=%P", sha).decode().split() != [parent]:
            raise ValueError("Final product has unknown ancestry")
    if tuple(_git(checkout, "show", "-s", "--format=%P", INTEGRATION_SEED_SHA).decode().split()) != SEED_PARENTS:
        raise ValueError("Final integration seed has unknown parents")
    product = _product_closure(checkout, PRODUCT_ANCHOR_SHA)
    if _product_closure(checkout, INTEGRATION_SEED_SHA) != product:
        raise ValueError("Final integration seed changes product bytes")
    for path in _SEED_TOOLING_EXCLUSIONS - AUTHORIZED_TOOLING_PATHS:
        _same(_git(checkout, "rev-parse", f"{INTEGRATION_SEED_SHA}:{path}").decode().strip(),
              _git(checkout, "rev-parse", f"{expected_candidate_sha}:{path}").decode().strip(),
              "frozen prior seed tooling blob")
    ancestor = subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor",
                               INTEGRATION_SEED_SHA, expected_candidate_sha], capture_output=True)
    if ancestor.returncode:
        raise ValueError("Final candidate is not a reviewed seed descendant")
    commits = _git(checkout, "rev-list", "--reverse", "--ancestry-path",
                   f"{INTEGRATION_SEED_SHA}..{expected_candidate_sha}").decode().splitlines()
    parent, changed = INTEGRATION_SEED_SHA, set()
    for sha in commits:
        if _git(checkout, "show", "-s", "--format=%P", sha).decode().split() != [parent]:
            raise ValueError("Final profile requires linear tooling-only descendants")
        paths = {os.fsdecode(row) for row in _git(checkout, "diff-tree", "--no-commit-id",
                 "--name-only", "-r", "-z", parent, sha).split(b"\0") if row}
        if not paths or not paths <= AUTHORIZED_TOOLING_PATHS or _product_closure(checkout, sha) != product:
            raise ValueError("Final descendant changes unauthorized product/tooling bytes")
        changed.update(paths)
        parent = sha
    if not commits or parent != expected_candidate_sha:
        raise ValueError("Final profile requires an immutable tooling descendant")
    return {"product_anchor_sha": PRODUCT_ANCHOR_SHA, "product_anchor_tree": PRODUCT_ANCHOR_TREE,
            "integration_seed_sha": INTEGRATION_SEED_SHA, "integration_seed_tree": INTEGRATION_SEED_TREE,
            "candidate_sha": expected_candidate_sha, "descendant_commits": commits,
            "authorized_changed_paths": sorted(changed),
            "product_closure_sha256": hashlib.sha256(product).hexdigest()}


def _guard_code_binding(checkout: Path, expected_sha: str) -> dict:
    binding = previous._guard_code_binding(checkout, expected_sha)
    if "scripts/deploy/verify_final_source_refresh_transition.py" not in binding["files"]:
        raise ValueError("Final verifier is absent from reviewed executing closure")
    return binding


_WORKER = r'''
import contextlib, dataclasses, json, sys
from pathlib import Path
root = Path.cwd().resolve()
sys.path[:0] = [str(root), *json.loads(sys.argv[4])]
with contextlib.redirect_stdout(sys.stderr):
    from src.bilun.cache.context import load_sut_build_context
    from src.bilun.cache.builder import _without_wavea_detail, _collect_wavea_bill_details
    from src.bilun.cache.build_streaming import json_ready
    from src.bilun.domain.claims.config import resolve_sut_data_source
    from src.bilun.domain.claims.loader import load_sut_claim_dataset
    from src.bilun.domain.claims.patient_context import build_patient_claim_context, build_bill_claim_context
    from src.bilun.domain.claims.provenance import attach_bilun_data_source_metadata
    from src.bilun.domain.billing.treatment_pricing_evaluations import evaluate_treatment_pricing
    from src.bilun.domain.prose_rules.treatment_pricing import load_treatment_pricing_rules
    from src.bilun.domain.prose_rules.drug_indication import drug_indication_coverage_scope
    from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope
    from src.bilun.domain.billing.wavea_full_evidence import build_full_wavea_evidence_index
    from src.bilun.domain.billing.broad_rule_classification import load_broad_classification_policy
    from src.bilun.domain.billing.focused_rule_projection import FOCUSED_RULE_SPECS
    cfg = resolve_sut_data_source(mode=sys.argv[3], claims_dir=Path(sys.argv[1]),
                                 clean_dir=Path(sys.argv[2]), environ={})
    # Fail directly: the analytics assembler's unavailable fallback cannot
    # turn an invalid dataset into a source proof.
    dataset = load_sut_claim_dataset(cfg.claims_dir, mode=cfg.mode)
    ctx = load_sut_build_context(billing_workers=1, sut_data_source_config=cfg)
    raw_patients, raw_bills = ctx['billing_reports'], ctx['bill_billing_reports']
    if not raw_patients or set(raw_patients) != set(ctx['patient_ids']):
        raise ValueError('Source replay patient cohort is incomplete')
    expected_bills = {pid + '::' + row.claim_id for pid, rows in dataset.claims_by_patient.items() for row in rows}
    if set(raw_bills) != expected_bills:
        raise ValueError('Source replay bill cohort is incomplete')
    metadata = cfg.metadata.as_dict()
    def attach(value):
        return attach_bilun_data_source_metadata(value, metadata)
    patients = {pid: attach(json_ready(_without_wavea_detail(report))) for pid, report in raw_patients.items()}
    bills = {key: attach(json_ready(_without_wavea_detail(report))) for key, report in raw_bills.items()}
    details = {pid: json_ready(report.get('wavea_evidence_detail') if isinstance(report, dict)
                 else report.wavea_evidence_detail) for pid, report in raw_patients.items()}
    bill_details = _collect_wavea_bill_details(raw_bills, '@source-replay-build')
    for detail in bill_details.values():
        del detail['build_id']
    index = attach(build_full_wavea_evidence_index(details))
    tables = {'patient_billing_report_rows': patients,
              'patient_bill_billing_report_rows': bills,
              'wavea_evidence_detail': {pid: attach(detail) for pid, detail in details.items()},
              'wavea_bill_evidence_detail': {key: attach(detail) for key, detail in bill_details.items()},
              'wavea_evidence_index': index}
    raw = {'patients': {}, 'bills': {}}
    for pid in sorted(raw_patients):
        patient_ctx = build_patient_claim_context(pid, dataset)
        if patient_ctx is None or not patient_ctx.claims:
            raise ValueError('Source replay lacks a patient claim context')
        batch = evaluate_treatment_pricing(pid, patient_ctx)
        raw['patients'][pid] = {'claims': sorted(row.claim_id for row in patient_ctx.claims),
            'evaluations': [dataclasses.asdict(row) for row in batch.evaluations],
            'legacy_rows': [dataclasses.asdict(row) for row in batch.legacy_rows],
            'matches': [dataclasses.asdict(row) for row in batch.matches]}
        for claim in patient_ctx.claims:
            key = pid + '::' + claim.claim_id
            batch = evaluate_treatment_pricing(pid, build_bill_claim_context(pid, claim.claim_id, dataset))
            raw['bills'][key] = {'claims': [claim.claim_id],
                'evaluations': [dataclasses.asdict(row) for row in batch.evaluations],
                'legacy_rows': [dataclasses.asdict(row) for row in batch.legacy_rows],
                'matches': [dataclasses.asdict(row) for row in batch.matches]}
    groups = {spec.rule_id: spec.group for spec in FOCUSED_RULE_SPECS}
    groups.update({key: row.family for key, row in load_broad_classification_policy().items()})
    result = {'tables': tables, 'coverage': {'drug': drug_indication_coverage_scope(),
              'materials': specialty_materials_coverage_scope()}, 'neutral_raw': raw,
              'rules': load_treatment_pricing_rules(), 'rule_groups': groups}

    import hashlib
    import pandas as pd
    import polars as pl
    from src.bilun.cache.payloads import (build_sut_patient_detail_payload,
        build_sut_patient_outcome_payload, build_patient_diagnoses_df)
    from src.bilun.db.patient_alerts import (_normalize_patient_alert_row,
        _patient_alert_row_schema, _patient_alert_row_columns)
    from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
    from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules
    from src.bilun.domain.prose_rules._drug_indication.clinical import evaluate_clinical_restrictions
    from src.bilun.domain.prose_rules._drug_indication.clinical_followup import evaluate_followup
    from src.bilun.domain.prose_rules._drug_indication.matching import _drug_name_matches
    from src.bilun.domain.prose_rules._drug_indication.runtime_observations import ClinicalObservationCollector
    from scripts.sut.prose.gate_b_generic import build_manifest, export_candidates
    from scripts.sut.prose.gate_b_sections import SECTION_COPAY_18
    from scripts.sut.prose.coverage import build_sut_coverage
    from src.bilun.domain.sut.coverage_evidence import build_drug_coverage_evidence, coverage_dependency_hashes
    from src.bilun.domain.sut import rules_catalog

    def canonical(value):
        return json.dumps(json_ready(value), sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    def digest(value):
        return hashlib.sha256(canonical(value).encode()).hexdigest()
    def same(left, right, label):
        if canonical(left) != canonical(right):
            raise ValueError('Own source projection differs: ' + label)
    def rows(frame):
        values = frame.to_dicts()
        for value in values:
            for field in value:
                if field.endswith('_json') and value[field] is not None:
                    value[field] = json.loads(value[field])
        return sorted(values, key=digest)

    # Mirror the pure serialization immediately preceding each canonical DB
    # writer; never call a DB writer, rebuild, backfill or read a cache oracle.
    ctx['data_source'] = metadata
    tables['cohort_compliance_index'] = attach(build_cohort_compliance_index(
        json_ready({pid: _without_wavea_detail(report) for pid, report in raw_patients.items()})))
    tables['cohort_optimization_summary'] = attach(ctx['optimization_summary'])
    tables['cohort_recovery_summary'] = attach(json_ready(ctx.get('revenue_recovery', {})))
    alerts = attach(ctx['patient_alerts_cache'])
    if not isinstance(alerts.get('summary'), dict) or not isinstance(alerts.get('patients'), list):
        raise ValueError('Own source alerts assembly is unavailable')
    tables['patient_alerts_summary'] = alerts['summary']
    alert_rows = [value for patient in alerts['patients']
                  if (value := _normalize_patient_alert_row(patient)) is not None]
    tables['patient_alert_rows'] = rows(pl.DataFrame(alert_rows,
        schema=_patient_alert_row_schema(), strict=False).select(_patient_alert_row_columns()))
    meta_columns = ('patient_id', 'age', 'sex', 'sex_raw', 'weight_kg', 'doctor_code',
                    'comorbidity_conditions_json', 'data_completeness', 'regime_state')
    meta_rows = []
    for value in ctx.get('patient_meta', []):
        row = {key: value.get(key) for key in meta_columns}
        for key in ('age', 'weight_kg', 'data_completeness'):
            if row[key] is not None:
                row[key] = float(row[key])
        # Canonical writer inserts the raw frame positionally: its seventh
        # field is the SUT producer's empty list, cast to TEXT then JSON-read.
        same(value['comorbidity_conditions'], [], 'SUT patient metadata list')
        row['comorbidity_conditions_json'] = []
        meta_rows.append(row)
    tables['patient_meta'] = sorted(meta_rows, key=digest)
    diagnoses = build_patient_diagnoses_df(ctx)
    tables['patient_diagnoses'] = rows(diagnoses) if diagnoses.height else []
    tables['patient_detail_cache'] = {pid: json_ready(build_sut_patient_detail_payload(pid, ctx))
                                      for pid in ctx['patient_ids']}
    tables['patient_outcome_base'] = {pid: json_ready(build_sut_patient_outcome_payload(pid, ctx))
                                    for pid in ctx['patient_ids']}
    # A fresh canonical build has no writer for these five legacy tables.
    for table in ('cohort_sut_summary', 'validation_payload', 'cohort_sut_exposure',
                  'patient_alerts_payload', 'patient_billing_reports'):
        tables[table] = []

    clauses_path = root / 'data/gazette/sut_clauses.parquet'
    clauses = pl.read_parquet(clauses_path)
    authored = json.loads((root / 'data/gazette/prose_rules/drug_indication_prose.json').read_text())
    namespaces = {'4.2.57.clinical_16_week_response', '4.2.46.clinical_annual_reassessment'}
    followup_rules = [row for row in authored['rules'] if row.get('clinical_constraint_set') == 'followup_source_constraints']
    if {row['rule_id'] for row in followup_rules} != namespaces or len(followup_rules) != 2:
        raise ValueError('Own source followup namespaces differ')
    loaded_rules = list_drug_indication_rules()
    same([row for row in loaded_rules if row.get('clinical_constraint_set') == 'followup_source_constraints'],
         followup_rules, 'compiled followup rules')
    witnesses = []
    for pid in sorted(dataset.drug_lines_by_patient):
        for line in dataset.drug_lines_by_patient[pid]:
            selected = [row['rule_id'] for row in followup_rules
                if _drug_name_matches(line.drug_name, row.get('drug_names') or [])
                and _drug_name_matches(line.drug_name, row.get('clinical_constraint_drugs') or row.get('drug_names') or [])]
            if not selected:
                continue
            outcomes = [row for row in evaluate_clinical_restrictions(line, loaded_rules)
                        if row['constraint_set'] == 'followup_source_constraints']
            if len(outcomes) != 1:
                raise ValueError('Own source followup outcome ownership is ambiguous')
            outcome, receipts = outcomes[0], []
            if sys.argv[5] == 'candidate':
                observer = ClinicalObservationCollector(line, 'followup', 'followup.atomic.v2.2026-10-03')
                observer.context('drug_name')
                observed = evaluate_followup(line, observer=observer)
                observed['runtime_coverage'] = observer.summary(clauses)
                same(outcome, observed, 'dispatcher and direct followup receipt projection')
                receipts = observer.receipts
            elif 'runtime_coverage' in outcome:
                raise ValueError('Baseline followup unexpectedly contains measured coverage')
            witnesses.append({'patient_id': pid, 'claim_id': line.claim_id,
                'drug_claim_line_id': line.drug_claim_line_id, 'drug_name': line.drug_name,
                'source_rule_ids': sorted(selected), 'constraint_set': 'followup_source_constraints',
                'outcome': outcome, 'receipts': receipts})

    # Verify the committed manifest before any coverage producer can consume it.
    manifest_path = root / 'data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json'
    copay_rules = json.loads((root / 'data/gazette/prose_rules/copay_general_1_8.json').read_text())
    manifest = build_manifest(export_candidates(clauses_path, SECTION_COPAY_18),
        copay_rules['rules'], SECTION_COPAY_18, effective_date='2026-08-01', resolve_clauses=clauses)
    same(manifest, json.loads(manifest_path.read_text()), 'fresh canonical copay manifest')
    artifact_paths = rules_catalog._coverage_artifact_paths()
    def artifact_stats():
        return {str(path.relative_to(root)): [path.stat().st_size, path.stat().st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest()] for path in artifact_paths}
    stats = artifact_stats()
    fresh_frames = build_sut_coverage(pd.read_parquet(clauses_path))
    names = ('sut_clause_coverage.parquet', 'sut_coverage_by_rule.parquet',
             'sut_coverage_by_section.parquet', 'sut_registry_coverage.parquet')
    keys = (('clause_id',), ('primary_rule_id', 'primary_rule_category', 'coverage_status'),
            ('section_id', 'section_title'), ('rule_id',))
    def frame_identity(frame, key_fields):
        if not set(key_fields) <= set(frame.columns):
            raise ValueError('Coverage frame lacks its compound identity')
        unique = set()
        for row in frame.select(list(key_fields)).to_dicts():
            key = canonical(row)
            if key in unique:
                raise ValueError('Coverage frame has duplicate compound identities')
            unique.add(key)
        return {'columns': frame.columns, 'schema': {key: str(dtype) for key, dtype in frame.schema.items()},
                'row_count': frame.height, 'key_fields': list(key_fields),
                'rows_sha256': digest(sorted(frame.to_dicts(), key=lambda row: canonical({key: row[key] for key in key_fields})))}
    frames = {}
    for name, fresh, key_fields in zip(names, fresh_frames, keys, strict=True):
        fresh_frame = pl.from_pandas(fresh)
        identity = frame_identity(fresh_frame, key_fields)
        same(identity, frame_identity(pl.read_parquet(root / 'data/gazette' / name), key_fields),
             'fresh coverage artifact')
        frames[name] = identity
    evidence = build_drug_coverage_evidence(pl.from_pandas(fresh_frames[0]), loaded_rules)
    evidence['file_sha256'] = coverage_dependency_hashes(root, clauses_path)
    same(evidence, json.loads((root / 'data/gazette/sut_coverage_evidence.json').read_text()),
         'fresh source coverage evidence')
    rules_catalog.reset_cache()
    public_summary = rules_catalog.coverage_summary()
    same(stats, artifact_stats(), 'source coverage before/after file binding')
    copay = {'manifest_sha256': digest(manifest), 'frames': frames, 'evidence_sha256': digest(evidence),
             'artifact_stats_sha256': digest(stats), 'public_summary': public_summary,
             'canonical_manifest_verified': True, 'fresh_coverage_verified': True}
    result['source_witnesses'] = {'followup': witnesses, 'followup_rules': followup_rules,
        'followup_source_clauses': json_ready(clauses.to_dicts()), 'copay': copay}

    for name, module in tuple(sys.modules.items()):
        if name in ('src', 'scripts') or name.startswith(('src.', 'scripts.')):
            source = getattr(module, '__file__', None)
            if source and not Path(source).resolve().is_relative_to(root):
                raise ValueError('Source replay imported outside the pinned checkout')
print(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
'''


def _replay_projection(checkout: Path, claims_dir: Path, clean_dir: Path, mode: str,
                       python_executable: Path, *, roster: dict,
                       dependency_roots: tuple[Path, ...]) -> dict:
    if (not python_executable.is_absolute() or not python_executable.is_file()
            or not dependency_roots or any(not path.is_absolute() or not (path.is_file() or path.is_dir())
                                          for path in dependency_roots)):
        raise ValueError("Final replay requires an explicit existing runtime and dependency roots")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
                   "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1"}
    runtime_files = tuple(path for path in dependency_roots if path.is_file())
    bindings = _runtime_file_bindings(runtime_files)
    os_bindings = _snapshot_runtime_files()
    with tempfile.TemporaryDirectory(prefix="bilun-final-source-") as directory:
        trace = Path(directory) / "replay.trace"
        command = ["strace", "-f", "-yy", "-s", "4096", "-e",
                   "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
                   "-o", str(trace), str(python_executable), "-I", "-S", "-B", "-X",
                   f"pycache_prefix={directory}/bytecode", "-c", _WORKER,
                   str(claims_dir), str(clean_dir), mode,
                   json.dumps([str(path) for path in dependency_roots]),
                   "baseline" if roster.get("code_sha") == BASELINE_CODE_SHA else "candidate"]
        result = subprocess.run(command, cwd=checkout, env=environment, capture_output=True,
                                timeout=1800, check=False)
        if result.returncode:
            raise ValueError("Final independent replay failed; no transition permission was issued")
        value = _parse_json(result.stdout.decode(), context="independent final source replay")
        if not isinstance(value, dict) or set(value) != {
            "tables", "coverage", "neutral_raw", "rules", "rule_groups", "source_witnesses",
        }:
            raise ValueError("Final replay has an unknown ownership contract")
        _same(os_bindings, _snapshot_runtime_files(), "post-worker fixed runtime OS files")
        _validate_pure_read_trace(trace, roster=roster, dependency_roots=dependency_roots,
                                  runtime_os_bindings=os_bindings)
        parsed = validate_runtime_read_trace(trace, roster=roster,
                    candidate_db=Path(directory) / "unused.duckdb", dependency_roots=dependency_roots)
        if parsed.get("trace_parse_ok") is not True:
            raise ValueError("Final replay read closure is unverified")
        _same(bindings, _runtime_file_bindings(runtime_files), "before/after explicit runtime file bindings")
        _same(os_bindings, _snapshot_runtime_files(), "final fixed runtime OS files")
        return value


def _runtime_file_bindings(paths: tuple[Path, ...]) -> list:
    return [[str(path), str(path.resolve(strict=True)), path.stat().st_dev, path.stat().st_ino,
             path.stat().st_size, path.stat().st_mtime_ns, _stable_file_hash(path.resolve(strict=True))]
            for path in paths]


def _snapshot_runtime_file(literal: str) -> dict:
    def metadata(value):
        return {"file_type": "regular_file", "uid": value.st_uid, "gid": value.st_gid,
                "mode": stat.S_IMODE(value.st_mode), "size_bytes": value.st_size,
                "device": value.st_dev, "inode": value.st_ino, "nlink": value.st_nlink,
                "mtime_ns": value.st_mtime_ns, "ctime_ns": value.st_ctime_ns}

    if literal not in RUNTIME_FILE_PATHS:
        raise ValueError("Runtime OS file is outside the two reviewed literals")
    path = Path(literal)
    initial_stat = os.lstat(literal)
    if (not stat.S_ISREG(initial_stat.st_mode) or path.is_symlink() or path.resolve(strict=True) != path
            or initial_stat.st_uid != 0 or initial_stat.st_mode & 0o022):
        raise ValueError("Runtime OS file has an unreviewed type/owner/mode")
    initial = metadata(initial_stat)
    descriptor = os.open(literal, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened_stat = os.fstat(descriptor)
        if not stat.S_ISREG(opened_stat.st_mode) or metadata(opened_stat) != initial:
            raise ValueError("Runtime OS file changed before its readonly descriptor")
        digest, size = hashlib.sha256(), 0
        while block := os.read(descriptor, 65536):
            size += len(block)
            if size > initial["size_bytes"]:
                raise ValueError("Runtime OS file changed while hashing")
            digest.update(block)
        if metadata(os.fstat(descriptor)) != initial or size != initial["size_bytes"]:
            raise ValueError("Runtime OS file descriptor changed while hashing")
    finally:
        os.close(descriptor)
    if path.is_symlink() or path.resolve(strict=True) != path or metadata(os.lstat(literal)) != initial:
        raise ValueError("Runtime OS path changed after hashing")
    return {"path": literal, **initial, "sha256": digest.hexdigest()}


def _snapshot_runtime_files() -> dict:
    return {literal: _snapshot_runtime_file(literal) for literal in RUNTIME_FILE_PATHS}


def _validate_pure_read_trace(trace: Path, *, roster: dict, dependency_roots: tuple[Path, ...],
                             runtime_os_bindings: dict | None = None) -> None:
    sources = {Path(row["path"]).resolve(strict=True) for row in roster["sources"]}
    checkout = Path(roster["checkout"]).resolve(strict=True)
    dependencies = tuple(path.resolve(strict=True) for path in dependency_roots)
    for line in trace_parser._completed_trace_lines(trace):
        if not trace_parser._OPEN.match(line) or " = -1 " in line:
            continue
        match = trace_parser._OPEN_RESULT.search(line)
        if match is None:
            raise ValueError("Final successful open lacks a decoded absolute path")
        observed = trace_parser._decoded_trace_path(match.group(2))
        if not observed.is_absolute():
            raise ValueError("Final read path is not absolute")
        path = observed.resolve(strict=False)
        if any(flag in line for flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND")):
            raise ValueError("Pure final replay attempted a successful file write")
        for candidate in (observed, path):
            if (any(part == ".env" or part.startswith(".env.") for part in candidate.parts)
                    or any(part in {".ssh", ".aws", ".gnupg"} for part in candidate.parts)
                    or candidate.name in {"credentials", "credential", "id_rsa", "id_ed25519"}
                    or re.search(r"\.(?:duckdb|db|sqlite3?|wal|key|pem|p12|pfx)(?:[.-](?:wal|shm))?$", candidate.name.lower())):
                raise ValueError("Pure final replay accessed a cache/environment/credential oracle")
        if path in {Path(literal) for literal in RUNTIME_FILE_PATHS}:
            if not isinstance(runtime_os_bindings, dict) or set(runtime_os_bindings) != set(RUNTIME_FILE_PATHS):
                raise ValueError("Fixed runtime OS read lacks its complete readonly binding")
            _same(runtime_os_bindings, _snapshot_runtime_files(), "trace exact fixed runtime OS files")
            continue
        if any(path == root or root.is_dir() and path.is_relative_to(root) for root in dependencies):
            continue
        if "O_DIRECTORY" in line:
            if not (path == checkout or path.is_relative_to(checkout)
                    or any(path == root or path.is_relative_to(root) for root in _OS_RUNTIME_ROOTS)):
                raise ValueError("Pure final replay opened an unrostered directory")
            continue
        proc_status = bool(re.fullmatch(r"/proc/[0-9]+/(?:status|stat|statm)", str(path)))
        os_library = path.suffix not in trace_parser._RUNTIME_EXTENSIONS and any(
            path == root or path.is_relative_to(root) for root in _OS_RUNTIME_ROOTS)
        if path not in sources and path not in _OS_RUNTIME_FILES and not proc_status and not os_library:
            raise ValueError("Pure final replay read outside its explicit source/runtime closure")


def _check_source_witnesses(projection: dict, *, candidate: bool) -> dict[tuple, dict]:
    import polars as pl
    from src.bilun.domain.prose_rules._drug_indication.matching import _drug_name_matches
    from src.bilun.domain.sut.runtime_coverage import build_runtime_coverage
    from src.bilun.domain.sut.runtime_coverage_contract import bounded_runtime_coverage

    sources = projection.get("source_witnesses")
    if not isinstance(sources, dict) or set(sources) != {
        "followup", "followup_rules", "followup_source_clauses", "copay",
    }:
        raise ValueError("Final source witnesses have unknown ownership")
    rules = sources["followup_rules"]
    if (not isinstance(rules, list) or len(rules) != 2
            or any(not isinstance(row, dict) for row in rules)
            or {row.get("rule_id") for row in rules} != FOLLOWUP_RULE_IDS
            or any(row.get("clinical_constraint_set") != FOLLOWUP_CONSTRAINT for row in rules)):
        raise ValueError("Final followup authored rule roster differs")
    frame = sources["followup_source_clauses"]
    if not isinstance(frame, list) or not frame or any(not isinstance(row, dict) for row in frame):
        raise ValueError("Followup source corpus is unavailable")
    clauses = pl.DataFrame(frame, infer_schema_length=None)
    witnesses = sources["followup"]
    if not isinstance(witnesses, list):
        raise ValueError("Final followup witnesses are unavailable")
    owned = {}
    for row in witnesses:
        if (not isinstance(row, dict) or set(row) != _WITNESS_FIELDS
                or any(not isinstance(row.get(key), str) or not row[key]
                       for key in ("patient_id", "claim_id", "drug_claim_line_id", "drug_name"))
                or row["constraint_set"] != FOLLOWUP_CONSTRAINT
                or not isinstance(row["outcome"], dict) or not isinstance(row["receipts"], list)):
            raise ValueError("Final followup witness has foreign line/constraint ownership")
        identity = tuple(row[key] for key in ("patient_id", "claim_id", "drug_claim_line_id"))
        if identity in owned:
            raise ValueError("Final followup has duplicate line ownership")
        expected = sorted(rule["rule_id"] for rule in rules
            if _drug_name_matches(row["drug_name"], rule.get("drug_names") or [])
            and _drug_name_matches(row["drug_name"], rule.get("clinical_constraint_drugs") or rule.get("drug_names") or []))
        if not expected:
            raise ValueError("Final followup line lacks a name-scoped authored rule")
        _same(row["source_rule_ids"], expected, "followup name-scoped source selection")
        outcome = row["outcome"]
        if (outcome.get("constraint_set") != FOLLOWUP_CONSTRAINT
                or outcome.get("clinical_eligibility_complete") is not False
                or outcome.get("verification_status") != "ai_generated_pending_review"):
            raise ValueError("Final followup outcome changed clinical authority")
        if not candidate:
            if row["receipts"] or "runtime_coverage" in outcome:
                raise ValueError("Baseline followup has an unexpected measured summary")
        else:
            summary = outcome.get("runtime_coverage")
            if (not isinstance(summary, dict) or set(summary) != _SUMMARY_FIELDS
                    or summary.get("available") is not True
                    or summary.get("clinical_eligibility_complete") is not False
                    or summary.get("complete_clause_mapping_available") is not False
                    or not row["receipts"]):
                raise ValueError("Final followup lacks its exact typed measured summary")
            _same(summary, bounded_runtime_coverage(summary), "all typed followup summary fields")
            scopes, receipt_ids = set(), set()
            for receipt in row["receipts"]:
                if (not isinstance(receipt, dict) or receipt.get("family") != "followup"
                        or receipt.get("claim_id") != row["claim_id"]
                        or receipt.get("drug_claim_line_id") != row["drug_claim_line_id"]
                        or receipt.get("evaluator_version") != FOLLOWUP_VERSION
                        or not isinstance(receipt.get("execution_scope"), str)
                        or not receipt["execution_scope"]):
                    raise ValueError("Followup receipt has foreign execution ownership")
                scopes.add(receipt["execution_scope"])
                rid = (receipt.get("kind"), receipt.get("predicate_id", receipt.get("route_id")))
                if rid in receipt_ids:
                    raise ValueError("Followup receipt has duplicate execution identity")
                receipt_ids.add(rid)
                if receipt.get("kind") == "predicate" and receipt.get("clause_predicate_complete") is not False:
                    raise ValueError("Followup receipt claims unsupported clause completeness")
                if not all(isinstance(receipt.get(key), list) and set(receipt[key]) <= _FOLLOWUP_INPUTS
                           for key in ("observed_input_fields", "missing_input_fields")):
                    raise ValueError("Followup receipt contains an unauthored input field")
                if receipt.get("kind") == "predicate":
                    references = _followup_predicate_refs(outcome.get("sut_section"))
                    predicate = receipt.get("predicate_id")
                    if predicate not in references:
                        raise ValueError("Followup receipt contains an unauthored predicate")
                    _same(receipt.get("source_refs"), references[predicate], "exact followup predicate source mapping")
                    if outcome.get("criterion_status") == "not_evaluated":
                        raise ValueError("Unsupported followup date attempted a clinical predicate")
                elif receipt.get("kind") != "route" or receipt.get("route_id") not in _FOLLOWUP_ROUTES:
                    raise ValueError("Followup receipt contains an unauthored route")
            if len(scopes) != 1:
                raise ValueError("Followup receipts mix execution scopes")
            measured = build_runtime_coverage(row["receipts"], instrumented_families=["followup"],
                allowed_contexts={(row["claim_id"], row["drug_claim_line_id"])},
                execution_scope=next(iter(scopes)), source_clauses=clauses)
            _same(summary, measured, "independently receipt-derived complete followup summary")
        owned[identity] = row
    _check_copay_witness(sources["copay"])
    return owned


def _followup_predicate_refs(section: str) -> dict:
    if section == "4.2.57":
        checkpoint = ["4.2.57.(2)#af1ccf61"]
        return {"dupilumab.response_window." + name: checkpoint for name in
                ("dates", "week16_elapsed", "week16_checkpoint_documented")} | {
            "dupilumab.response.easi_threshold": ["4.2.57.(1)#d711a1b9"],
            "dupilumab.response.dlqi_threshold": ["4.2.57.(2)#62f546f9"],
            "dupilumab.response.pruritus_nrs_threshold": ["4.2.57.(3)#6147427c"]}
    if section in {"4.2.46.B", "4.2.46.C"}:
        return {"nintedanib.reassessment." + name: [section + ".(3)#cac79ad7"]
                for name in ("report_dates", "twelve_month_interval")} | {
            "nintedanib.fvc.assessment_outside_exacerbation": [section + ".a#89e9c50d"],
            "nintedanib.fvc.response_threshold": [section + ".a#89e9c50d"],
            "nintedanib.fvc.report_documents_response": [section + ".b#aa27b4a1"]}
    return {}


def _check_copay_witness(value: dict) -> None:
    keys = {"manifest_sha256", "frames", "evidence_sha256", "artifact_stats_sha256",
            "public_summary", "canonical_manifest_verified", "fresh_coverage_verified"}
    frame_keys = {
        "sut_clause_coverage.parquet": ["clause_id"],
        "sut_coverage_by_rule.parquet": ["primary_rule_id", "primary_rule_category", "coverage_status"],
        "sut_coverage_by_section.parquet": ["section_id", "section_title"],
        "sut_registry_coverage.parquet": ["rule_id"],
    }
    if (not isinstance(value, dict) or set(value) != keys
            or value.get("canonical_manifest_verified") is not True
            or value.get("fresh_coverage_verified") is not True
            or not isinstance(value.get("public_summary"), dict)
            or value["public_summary"].get("meta", {}).get("artifacts_available") is not True
            or not isinstance(value.get("frames"), dict) or set(value["frames"]) != set(frame_keys)):
        raise ValueError("Copay lacks a fresh own-source closure")
    for key in ("manifest_sha256", "evidence_sha256", "artifact_stats_sha256"):
        if not isinstance(value[key], str) or not _SHA256.fullmatch(value[key]):
            raise ValueError("Copay source digest is malformed")
    for name, keys in frame_keys.items():
        row = value["frames"][name]
        if (not isinstance(row, dict) or set(row) != {"columns", "schema", "row_count", "key_fields", "rows_sha256"}
                or not isinstance(row["columns"], list) or not row["columns"]
                or any(not isinstance(field, str) for field in row["columns"])
                or len(set(row["columns"])) != len(row["columns"])
                or not isinstance(row["schema"], dict) or set(row["schema"]) != set(row["columns"])
                or any(not isinstance(dtype, str) or not dtype for dtype in row["schema"].values())
                or row["key_fields"] != keys or not set(keys) <= set(row["columns"])
                or type(row["row_count"]) is not int or row["row_count"] <= 0
                or not isinstance(row["rows_sha256"], str) or not _SHA256.fullmatch(row["rows_sha256"])):
            raise ValueError("Copay fresh frame identity is malformed")


def _strip_followup(value: Any, owned: dict[tuple, dict], *, context: tuple = (None, None, None),
                    restriction: bool = False, seen: set | None = None) -> Any:
    """Remove only a freshly witnessed annotation at its actual line's outcome."""
    if isinstance(value, list):
        return [_strip_followup(row, owned, context=context, restriction=restriction, seen=seen)
                for row in value]
    if not isinstance(value, dict):
        return value
    pid, claim, line = context
    pid = value.get("patient_id", pid)
    claim = value.get("claim_id", claim)
    line = value.get("drug_claim_line_id", line)
    if value.get("line_kind") == "drug":
        line = value.get("line_id", line)
    context = (pid, claim, line)
    remove = False
    if restriction and value.get("constraint_set") == FOLLOWUP_CONSTRAINT and "runtime_coverage" in value:
        witness = owned.get(context)
        if witness is None:
            raise ValueError("Followup summary lacks exact patient/claim/drug-line ownership")
        _same(value["runtime_coverage"], witness["outcome"]["runtime_coverage"], "source-owned followup annotation")
        if seen is not None:
            seen.add(context)
        remove = True
    return {key: _strip_followup(row, owned, context=context,
                restriction=(key == "clinical_restrictions"), seen=seen)
            for key, row in value.items() if not (remove and key == "runtime_coverage")}


def _check_followup_pair(old: dict, new: dict) -> tuple[dict, int]:
    left = _check_source_witnesses(old, candidate=False)
    right = _check_source_witnesses(new, candidate=True)
    if left.keys() != right.keys():
        raise ValueError("Followup source input line inventory changed")
    for identity in left:
        _same(previous._without(left[identity], {"outcome", "receipts"}),
              previous._without(right[identity], {"outcome", "receipts"}), "followup input/source identity")
        _same(left[identity]["outcome"], previous._without(right[identity]["outcome"], {"runtime_coverage"}),
              "followup clinical criteria/status/authority/date/missing facts")
    output = json.loads(_canonical(new))
    seen = set()
    for table in _OWNED_TABLES:
        value = new["tables"][table]
        if table in previous._REPORT_TABLES or table in previous._REPORT_TABLES.values():
            stripped = {}
            for key, row in value.items():
                pid, _, claim = key.partition("::")
                stripped[key] = _strip_followup(row, right, context=(pid, claim or None, None), seen=seen)
        else:
            stripped = _strip_followup(value, right, seen=seen)
        output["tables"][table] = stripped
    if seen != set(right):
        raise ValueError("Full cohort projection lacks a witnessed followup line")
    return output, len(right)


def _check_projection_pair(old: dict, new: dict) -> dict:
    fields = {"tables", "coverage", "neutral_raw", "rules", "rule_groups", "source_witnesses"}
    if (not isinstance(old, dict) or not isinstance(new, dict) or set(old) != fields or set(new) != fields
            or not isinstance(old["tables"], dict) or not isinstance(new["tables"], dict)
            or set(old["tables"]) != _TABLES or set(new["tables"]) != _TABLES):
        raise ValueError("Final replay lacks the exact nineteen source projections")
    stripped, changed = _check_followup_pair(old, new)
    reduced = []
    for value in (old, stripped):
        reduced.append({**previous._without(value, {"source_witnesses", "tables"}),
                        "tables": {name: value["tables"][name] for name in previous._TABLES}})
    counts = previous._check_projection_pair(*reduced)
    for table in _STRICT_TABLES | {"cohort_compliance_index"}:
        _same(old["tables"][table], stripped["tables"][table], "remaining full-cohort table fields")
    return {**counts, "followup_line_count": changed,
            "source_projected_table_count": len(_TABLES), "strict_table_count": len(_STRICT_TABLES)}


def _source_intent(baseline: dict, candidate: dict, old: dict, new: dict) -> dict:
    import polars as pl
    from src.bilun.cache.build_streaming import json_ready

    organ = previous._source_intent(baseline, candidate, old, new)
    for roster, sha, projection in ((baseline, BASELINE_CODE_SHA, old), (candidate, PRODUCT_ANCHOR_SHA, new)):
        checkout = Path(roster["checkout"])
        document = _parse_json(_git(checkout, "show", f"{sha}:data/gazette/prose_rules/drug_indication_prose.json").decode(),
                               context="public followup authored rules")
        _same(projection["source_witnesses"]["followup_rules"],
              [row for row in document["rules"] if row.get("clinical_constraint_set") == FOLLOWUP_CONSTRAINT],
              "own compiled followup source namespaces")
        _same(projection["source_witnesses"]["followup_source_clauses"],
              json_ready(pl.read_parquet(checkout / "data/gazette/sut_clauses.parquet").to_dicts()),
              "own source-bound public corpus for receipt resolution")
    _same(organ, _expected_source_intent()["organ"], "pinned neutral organ source intent")
    return _expected_source_intent()


def _expected_source_intent() -> dict:
    return {"organ": {"source_path": previous.SOURCE_PATH,
            "baseline_blob": previous.BASELINE_SOURCE_BLOB, "product_blob": previous.PRODUCT_SOURCE_BLOB,
            "neutral_rule_ids": sorted(previous.NEUTRAL_RULE_IDS),
            "clinical_eligibility_complete": False, "quarantine_is_payment_neutral": True},
            "followup": {"rule_ids": sorted(FOLLOWUP_RULE_IDS),
            "constraint_set": FOLLOWUP_CONSTRAINT, "evaluator_version": FOLLOWUP_VERSION,
            "summary_fields": sorted(_SUMMARY_FIELDS), "clinical_eligibility_complete": False},
            "copay": {"canonical_manifest_verified": True, "fresh_coverage_verified": True,
                      "payment_permission_added": False}}


@dataclass(frozen=True)
class FinalSourceRefreshProof:
    _report_json: str = field(repr=False)
    _projections_json: str = field(repr=False)
    _seal: object = field(repr=False)

    @property
    def report(self) -> dict:
        return json.loads(self._report_json)

    @property
    def projections(self) -> dict:
        return json.loads(self._projections_json)


def _issue_proof(report: dict, projections: dict) -> FinalSourceRefreshProof:
    seal = object()
    proof = FinalSourceRefreshProof(_canonical(report), _canonical(projections), seal)
    _PROOF_BINDINGS[seal] = _digest([proof._report_json, proof._projections_json])
    return proof


def _require_proof(proof: FinalSourceRefreshProof) -> None:
    if (not isinstance(proof, FinalSourceRefreshProof) or type(proof._seal) is not object
            or proof._seal not in _PROOF_BINDINGS
            or _PROOF_BINDINGS[proof._seal] != _digest([proof._report_json, proof._projections_json])):
        raise ValueError("Final source content lacks a fresh sealed replay proof")
    validate_transition_report_contract(proof.report)


def verify_transition(*, request: Mapping, baseline_roster: Path, candidate_roster: Path,
                      baseline_meta: Mapping, candidate_meta: Mapping, same_input: Mapping,
                      python_executable: Path, expected_candidate_sha: str,
                      dependency_roots: tuple[Path, ...], expected_verifier_sha: str | None = None
                      ) -> Any:
    requested = validate_transition_request(request)
    if requested is None:
        raise ValueError("An explicit source transition request is required")
    verifier_sha = expected_verifier_sha or expected_candidate_sha
    if (requested["expected_candidate_sha"] != expected_candidate_sha
            or requested["expected_verifier_sha"] != verifier_sha):
        raise ValueError("Transition request differs from explicitly reviewed candidate/verifier")
    args = {"baseline_roster": baseline_roster, "candidate_roster": candidate_roster,
            "baseline_meta": baseline_meta, "candidate_meta": candidate_meta,
            "same_input": same_input, "python_executable": python_executable,
            "expected_candidate_sha": expected_candidate_sha, "dependency_roots": dependency_roots,
            "expected_verifier_sha": verifier_sha}
    if requested["contract"] != TRANSITION_CONTRACT:
        return previous.verify_transition(request=requested, **args)
    if (baseline_meta.get("code_sha") != BASELINE_CODE_SHA
            or candidate_meta.get("code_sha") != expected_candidate_sha
            or verifier_sha != expected_candidate_sha
            or baseline_meta.get("source_hash") != BASELINE_SOURCE_HASH
            or baseline_meta.get("config_hash") != BASELINE_CONFIG_HASH
            or candidate_meta.get("config_hash") != BASELINE_CONFIG_HASH):
        raise ValueError("Source refresh cache/source/config identities differ")
    if (same_input.get("status") != "same_input_bytes_verified"
            or same_input.get("input_bytes_sha256") != INPUT_BYTES_SHA256
            or type(same_input.get("input_file_count")) is not int or same_input["input_file_count"] != 12
            or same_input.get("data_mode") != "synthetic_demo"):
        raise ValueError("Source refresh requires the exact reviewed twelve same-input files")
    old_roster, old_data = _roster(baseline_roster, BASELINE_CODE_SHA)
    new_roster, new_data = _roster(candidate_roster, expected_candidate_sha)
    if old_data.keys() != new_data.keys() or len(old_data) != 12:
        raise ValueError("Source refresh input roster differs")
    for label in old_data:
        _same({key: old_data[label][key] for key in ("sha256", "size_bytes")},
              {key: new_data[label][key] for key in ("sha256", "size_bytes")}, "each protected input file")
    for side, path, meta in (("baseline", baseline_roster, baseline_meta),
                             ("candidate", candidate_roster, candidate_meta)):
        _same(same_input.get(side), {"roster_sha256": _stable_file_hash(path),
              "source_hash": meta["source_hash"], "config_hash": meta["config_hash"]},
              "source/config/input binding")
    history = _verify_candidate_history(Path(new_roster["checkout"]), expected_candidate_sha)
    verifier_checkout = Path(__file__).resolve().parents[2]
    binding = _guard_code_binding(verifier_checkout, verifier_sha)
    rosters = {"baseline": old_roster, "candidate": new_roster}
    replay_bindings = {side: _replay_checkout_binding(roster) for side, roster in rosters.items()}
    runtime_os_bindings = _snapshot_runtime_files()
    projections = {}
    for side, roster, data in (("baseline", old_roster, old_data), ("candidate", new_roster, new_data)):
        claims = Path(next(row["path"] for label, row in data.items() if label.startswith("claim:"))).parent
        clean = Path(next(row["path"] for label, row in data.items() if label.startswith("clean:"))).parent
        projections[side] = _replay_projection(Path(roster["checkout"]), claims, clean,
            roster["data_mode"], python_executable, roster=roster, dependency_roots=dependency_roots)
        for name, pinned in rosters.items():
            _same(_replay_checkout_binding(pinned), replay_bindings[name], "post-replay pinned source bytes")
        if (_roster(baseline_roster, BASELINE_CODE_SHA)[0] != old_roster
                or _roster(candidate_roster, expected_candidate_sha)[0] != new_roster):
            raise ValueError("Source refresh inputs changed during replay")
    intent = _source_intent(old_roster, new_roster, projections["baseline"], projections["candidate"])
    # Attest physical paths before comparing own source models. Nothing else
    # in source metadata is discarded or inferred from a cache.
    normalized = {side: normalize_attested_data_source(value, same_input["paths"][side])
                  for side, value in projections.items()}
    counts = _check_projection_pair(normalized["baseline"], normalized["candidate"])
    _same(_verify_candidate_history(Path(new_roster["checkout"]), expected_candidate_sha), history,
          "final immutable history")
    _same(_guard_code_binding(verifier_checkout, verifier_sha), binding, "final verifier bytes")
    for side, roster in rosters.items():
        _same(_replay_checkout_binding(roster), replay_bindings[side], "final replay source bytes")
    _same(runtime_os_bindings, _snapshot_runtime_files(), "whole-replay fixed runtime OS files")
    if (_roster(baseline_roster, BASELINE_CODE_SHA)[0] != old_roster
            or _roster(candidate_roster, expected_candidate_sha)[0] != new_roster):
        raise ValueError("Source refresh inputs changed before proof issuance")
    identity = {"contract": TRANSITION_CONTRACT, "baseline_code_sha": BASELINE_CODE_SHA,
                "baseline_tree": BASELINE_TREE, "candidate_code_sha": expected_candidate_sha,
                "history": history, "verifier": binding, "replay_checkouts": replay_bindings,
                "same_input": dict(same_input), "source_intent": intent,
                "baseline_replay_sha256": _digest(projections["baseline"]),
                "candidate_replay_sha256": _digest(projections["candidate"]), **counts,
              "patient_count": len(projections["baseline"]["tables"]["patient_billing_report_rows"]),
              "bill_count": len(projections["baseline"]["tables"]["patient_bill_billing_report_rows"]),
              "protected_fields": "all_other_fields_type_exact_unchanged",
              "source_cache_witnesses": {table: {side + "_sha256": _digest(normalized[side]["tables"][table])
                  for side in ("baseline", "candidate")} for table in sorted(_TABLES)},
              "source_api_witnesses": {side: {"coverage_summary_sha256":
                  _digest(projections[side]["source_witnesses"]["copay"]["public_summary"]),
                  "coverage_closure_sha256": _digest(projections[side]["source_witnesses"]["copay"])}
                  for side in ("baseline", "candidate")},
              "cache_comparison_contract": "all19_own_source_exact_before_admission"}
    report = {"status": "final_source_refresh_transition_verified", **identity,
              "transition_sha256": _digest(identity)}
    validate_transition_report_contract(report)
    # Expected source values remain private. Every table is still compared to
    # its own actual cache before this proof can normalize that table.
    expected_tables = {side: {"tables": projection["tables"],
        "followup": projection["source_witnesses"]["followup"]}
        for side, projection in projections.items()}
    return _issue_proof(report, expected_tables)


def validate_transition_report_contract(report: Mapping) -> None:
    if not isinstance(report, Mapping):
        raise ValueError("Transition report is malformed")
    if report.get("contract") != TRANSITION_CONTRACT:
        return previous.validate_transition_report_contract(report)
    required = {"status", "contract", "baseline_code_sha", "baseline_tree", "candidate_code_sha",
                "history", "verifier", "replay_checkouts", "same_input", "source_intent",
                "baseline_replay_sha256", "candidate_replay_sha256", "transition_sha256",
                "changed_organ_evaluations", "neutral_raw_rows", "patient_count", "bill_count",
                "protected_fields", "followup_line_count", "source_projected_table_count", "strict_table_count",
                "source_cache_witnesses", "source_api_witnesses", "cache_comparison_contract"}
    if (set(report) != required or report.get("contract") != TRANSITION_CONTRACT
            or report.get("status") != "final_source_refresh_transition_verified"
            or report.get("baseline_code_sha") != BASELINE_CODE_SHA or report.get("baseline_tree") != BASELINE_TREE
            or not isinstance(report.get("candidate_code_sha"), str) or not _SHA.fullmatch(report["candidate_code_sha"])
            or report.get("protected_fields") != "all_other_fields_type_exact_unchanged"):
        raise ValueError("Source refresh report has an unknown contract or identity")
    candidate = report["candidate_code_sha"]
    history, binding, source, inputs, checkouts = (report[key] for key in
        ("history", "verifier", "source_intent", "same_input", "replay_checkouts"))
    if (not all(isinstance(value, dict) for value in (history, binding, source, inputs, checkouts))
            or set(history) != {"product_anchor_sha", "product_anchor_tree", "candidate_sha",
                                "descendant_commits", "authorized_changed_paths", "integration_seed_sha",
                                "integration_seed_tree", "product_closure_sha256"}
            or history.get("product_anchor_sha") != PRODUCT_ANCHOR_SHA
            or history.get("product_anchor_tree") != PRODUCT_ANCHOR_TREE
            or history.get("candidate_sha") != candidate
            or history.get("integration_seed_sha") != INTEGRATION_SEED_SHA
            or history.get("integration_seed_tree") != INTEGRATION_SEED_TREE
            or not isinstance(history.get("product_closure_sha256"), str)
            or not _SHA256.fullmatch(history["product_closure_sha256"])
            or not isinstance(history.get("descendant_commits"), list) or not history["descendant_commits"]
            or history["descendant_commits"][-1] != candidate
            or any(not isinstance(sha, str) or not _SHA.fullmatch(sha) for sha in history["descendant_commits"])
            or len(set(history["descendant_commits"])) != len(history["descendant_commits"])
            or not isinstance(history.get("authorized_changed_paths"), list)
            or not history["authorized_changed_paths"]
            or any(not isinstance(path, str) for path in history["authorized_changed_paths"])
            or history["authorized_changed_paths"] != sorted(set(history["authorized_changed_paths"]))
            or not set(history["authorized_changed_paths"]) <= AUTHORIZED_TOOLING_PATHS
            or binding.get("verifier_sha") != candidate
            or not isinstance(binding.get("files"), dict)
            or "scripts/deploy/verify_final_source_refresh_transition.py" not in binding["files"]
            or "scripts/deploy/verify_source_refresh_transition.py" not in binding["files"]
            or inputs.get("status") != "same_input_bytes_verified"
            or inputs.get("input_bytes_sha256") != INPUT_BYTES_SHA256
            or type(inputs.get("input_file_count")) is not int or inputs["input_file_count"] != 12
            or inputs.get("data_mode") != "synthetic_demo"
            or set(checkouts) != {"baseline", "candidate"}
            or any(not isinstance(row, dict) for row in checkouts.values())
            or checkouts["baseline"].get("code_sha") != BASELINE_CODE_SHA
            or checkouts["candidate"].get("code_sha") != candidate):
        raise ValueError("Source refresh report source/replay/tooling binding differs")
    _same(source, _expected_source_intent(), "typed final source intent")
    if set(inputs) != {"status", "data_mode", "input_file_count", "input_bytes_sha256",
                       "baseline", "candidate", "paths"}:
        raise ValueError("Source refresh same-input contract is malformed")
    for side in ("baseline", "candidate"):
        metadata = inputs.get(side)
        if (not isinstance(metadata, dict)
                or set(metadata) != {"roster_sha256", "source_hash", "config_hash"}
                or any(not isinstance(value, str) or not _SHA256.fullmatch(value)
                       for value in metadata.values())
                or metadata["config_hash"] != BASELINE_CONFIG_HASH
                or side == "baseline" and metadata["source_hash"] != BASELINE_SOURCE_HASH):
            raise ValueError("Source refresh same-input source/config binding differs")
    paths = inputs.get("paths")
    if (not isinstance(paths, dict) or set(paths) != {"baseline", "candidate"}
            or any(not isinstance(row, dict) or set(row) != {"claim_source", "clinical_source"}
                   or any(not isinstance(path, str) or not path for path in row.values())
                   for row in paths.values())):
        raise ValueError("Source refresh same-input path binding is malformed")
    for row in checkouts.values():
        if (set(row) != {"code_sha", "source_sha256", "file_count"}
                or not isinstance(row.get("source_sha256"), str) or not _SHA256.fullmatch(row["source_sha256"])
                or type(row.get("file_count")) is not int or row["file_count"] <= 0):
            raise ValueError("Source refresh replay checkout closure is malformed")
    if (set(binding) - {"frontend_config"} != {"verifier_sha", "source_sha256", "files"}
            or any(not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts
                   or not (path.startswith(("scripts/", "src/", "data/"))
                           or path in {"pyproject.toml", "requirements.txt"})
                   or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                   for path, digest in binding["files"].items())):
        raise ValueError("Source refresh verifier closure is malformed")
    contents = binding["files"]
    if "frontend_config" in binding:
        config = binding["frontend_config"]
        if config != {"path": historical.FRONTEND_CONFIG_PATH, "git_mode": "100644",
                      "git_blob": historical.FRONTEND_CONFIG_CANDIDATE_BLOB,
                      "sha256": historical._FRONTEND_CONFIG_SHA256[historical.FRONTEND_CONFIG_CANDIDATE_BLOB]}:
            raise ValueError("Source refresh frontend config differs from the pinned product")
        contents = {"files": contents, "frontend_config": config}
    _same(binding.get("source_sha256"), _digest(contents), "verifier closure digest")
    for key in ("baseline_replay_sha256", "candidate_replay_sha256", "transition_sha256"):
        if not isinstance(report.get(key), str) or not _SHA256.fullmatch(report[key]):
            raise ValueError("Source refresh report digest is malformed")
    for key in ("changed_organ_evaluations", "neutral_raw_rows", "patient_count", "bill_count"):
        if type(report[key]) is not int or report[key] <= 0:
            raise ValueError("Source refresh report cohort counts are incomplete")
    if (type(report["followup_line_count"]) is not int or report["followup_line_count"] < 0
            or type(report["source_projected_table_count"]) is not int or report["source_projected_table_count"] != 19
            or type(report["strict_table_count"]) is not int or report["strict_table_count"] != 13
            or report["cache_comparison_contract"] != "all19_own_source_exact_before_admission"):
        raise ValueError("Final source/cache witness predicates differ")
    cache = report["source_cache_witnesses"]
    api = report["source_api_witnesses"]
    if (not isinstance(cache, dict) or set(cache) != _TABLES
            or not isinstance(api, dict) or set(api) != {"baseline", "candidate"}):
        raise ValueError("Final source/cache/API witness roster differs")
    for row in cache.values():
        if not isinstance(row, dict) or set(row) != {"baseline_sha256", "candidate_sha256"}:
            raise ValueError("Final source/cache witness is malformed")
        if any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in row.values()):
            raise ValueError("Final source/cache witness digest is malformed")
    for row in api.values():
        if not isinstance(row, dict) or set(row) != {"coverage_summary_sha256", "coverage_closure_sha256"}:
            raise ValueError("Final source API witness is malformed")
        if any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in row.values()):
            raise ValueError("Final source API witness digest is malformed")
    for table in _STRICT_TABLES:
        _same(cache[table]["baseline_sha256"], cache[table]["candidate_sha256"], "thirteen strict source table digests")
    excluded = {"status", "transition_sha256"}
    _same(report["transition_sha256"], _digest(_without(report, excluded)), "transition identity digest")


def _without(value: Mapping, fields: set | frozenset) -> dict:
    return previous._without(value, fields)


def normalize_transition_content(table: str, value: Any, *, side: str, proof: Any,
                                 patient_reports: dict | None = None) -> Any:
    if not isinstance(proof, FinalSourceRefreshProof):
        return previous.normalize_transition_content(table, value, side=side, proof=proof,
                                                     patient_reports=patient_reports)
    _require_proof(proof)
    if side not in {"baseline", "candidate"}:
        raise ValueError("Final source content side is unknown")
    if table not in _TABLES:
        return value
    projections = proof.projections
    expected = projections[side]["tables"][table]
    actual = _without_build_ids(table, value)
    if table in _ROW_TABLES:
        if not isinstance(actual, list):
            raise ValueError("Final source row table has an unknown shape")
        # Existing semantic inventory sorts JSON row tables after attested-path
        # normalization. Canonical digest order is a lossless row permutation.
        actual = sorted(actual, key=_digest)
    _same(actual, expected, "actual cache against its own nineteen-table source replay")
    normalized = normalize_attested_data_source(expected, proof.report["same_input"]["paths"][side])
    _same(_digest(normalized), proof.report["source_cache_witnesses"][table][side + "_sha256"],
          "source/cache witness digest")
    if side == "baseline" or table in _STRICT_TABLES:
        return value
    output = json.loads(_canonical(projections["baseline"]["tables"][table]))
    # Existing independent input-path and selected-build checks still see the
    # actual side's metadata; no other source/money/identity field is ignored.
    if table in {"wavea_evidence_index", "cohort_compliance_index"}:
        output["data_source"] = value["data_source"]
        if table == "wavea_evidence_index":
            output["build_id"] = value["build_id"]
    else:
        for key, row in output.items():
            row["data_source"] = value[key]["data_source"]
            if table in previous._REPORT_TABLES.values():
                row["build_id"] = value[key]["build_id"]
    return output


def _without_build_ids(table: str, value: Any) -> Any:
    if table in _ROW_TABLES:
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise ValueError("Final row table lacks its typed payload shape")
    elif not isinstance(value, dict):
        raise ValueError("Final cache table lacks its typed payload shape")
    elif table in {*previous._REPORT_TABLES, *previous._REPORT_TABLES.values(),
                   "patient_detail_cache", "patient_outcome_base"}:
        if any(not isinstance(key, str) or not isinstance(row, dict) for key, row in value.items()):
            raise ValueError("Final patient/bill cache map has a malformed payload row")
    return previous._without_build_ids(table, value)


def normalize_transition_http_reports(reports: dict[str, dict], *, side: str, proof: Any,
                                      transport: Any, baseline_transport: Any,
                                      view: str = "draft") -> dict[str, dict]:
    if not isinstance(proof, FinalSourceRefreshProof):
        return previous.normalize_transition_http_reports(reports, side=side, proof=proof,
            transport=transport, baseline_transport=baseline_transport, view=view)
    from scripts.deploy.rehearse_wavea_same_port import PinnedReportTransport
    from scripts.deploy.verify_candidate_semantics import _legacy_report

    _require_proof(proof)
    if side not in {"baseline", "candidate"} or view not in {"draft", "legacy"}:
        raise ValueError("Final source HTTP side/view is unknown")
    for label, package in (("baseline", baseline_transport), (side, transport)):
        if (not isinstance(package, PinnedReportTransport)
                or package.code_sha != proof.report[label + "_code_sha"]
                or package.contract != "wavea-evidence-v2"):
            raise ValueError("Final HTTP transport differs from pinned source")
        package.validate()
        raw, _ = historical._http_report_scopes(package.raw_reports)
        for table, rows in raw.items():
            normalize_transition_content(table, rows, side=label, proof=proof)
    expected = transport.draft_reports if view == "draft" else {
        path: _legacy_report(row) for path, row in transport.complete_reports.items()}
    _same(reports, expected, "HTTP exact pinned serializer/model projection")
    baseline = baseline_transport.draft_reports if view == "draft" else {
        path: _legacy_report(row) for path, row in baseline_transport.complete_reports.items()}
    if reports.keys() != baseline.keys():
        raise ValueError("Final HTTP report inventory changed")
    if side == "baseline":
        return reports
    owned = {tuple(row[key] for key in ("patient_id", "claim_id", "drug_claim_line_id")): row
             for row in proof.projections["candidate"]["followup"]}
    output = {}
    for path, row in reports.items():
        # Match the complete pinned raw report's identity, not path segments or
        # positional IDs, before touching a measured clinical annotation.
        source = transport.raw_reports[path]
        pid = source.get("patient_id")
        claim = source.get("claim_id")
        current = _strip_followup(row, owned, context=(pid, claim, None))
        previous_row = baseline[path]
        current["drug_indication"]["coverage_scope"] = previous_row["drug_indication"]["coverage_scope"]
        current["materials"]["specialty_coverage_scope"] = previous_row["materials"]["specialty_coverage_scope"]
        if "wavea_coverage" in current:
            current["wavea_coverage"] = previous_row["wavea_coverage"]
        output[path] = current
    return output
