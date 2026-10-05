"""Opt in to the exact 499 -> d033 source refresh, with independent replay.

The historical inventory contract is delegated unchanged. This second contract
admits source-derived inventory counts and three authored organ quarantines;
it does not admit a payment, rule selection, provenance or unrelated status
change. Protected inputs and replay payloads remain in local process memory.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.deploy import verify_clinical_semantic_transition as historical
from scripts.deploy.generate_candidate_source_roster import validate_runtime_read_trace
from scripts.deploy.verify_candidate_cache import _parse_json, _stable_file_hash
from scripts.deploy.verify_same_input import _roster, normalize_attested_data_source

TRANSITION_CONTRACT = "bilun-source-refresh-499-d033-v1"
BASELINE_CODE_SHA = "499dff4c40298075d9c90d6254baf903266b6611"
BASELINE_TREE = "a8b1f10c977da1fab5fd05ed605ac0853be84397"
PRODUCT_ANCHOR_SHA = "d0337600f45a17aa635f6bbe8d584095a6f3e82e"
PRODUCT_ANCHOR_TREE = "cab00a2d077ab15fdbcf37a52533f4b85f21de76"
SOURCE_PATH = "data/gazette/prose_rules/treatment_pricing_2_4.json"
BASELINE_SOURCE_BLOB = "fe9a8a060db1788e330a8ff29b4f0d5cbf7db9a6"
PRODUCT_SOURCE_BLOB = "f0b0e0a5be44e0ad6ac470bd4859325be469984c"
INPUT_BYTES_SHA256 = "84efa030d2c5e927f8afb94ce8c494647e398e236d02b560a3d281531231d1f3"
BASELINE_SOURCE_HASH = "317d1bcf092e6f3e4b37b317d54e8d9ed76affd631f062e73ab320270f1ab4be"
BASELINE_CONFIG_HASH = "34befe4f0a98b6a36b2e8f3816daaaa0e8f501e34278ea4d7de1c0b27efff735"
NEUTRAL_RULE_IDS = frozenset({
    "2.4.2.A.(4).domestic_organ_transfer_per_2_6",
    "2.4.2.A.(2).non_covered_donor_organ_tissue_no_pay",
    "2.4.2.A.(5).cadaver_donor_procurement_p911146_ek2c",
})
AUTHORIZED_TOOLING_PATHS = frozenset({
    "scripts/deploy/verify_source_refresh_transition.py",
    "scripts/deploy/verify_candidate_semantics.py",
    "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_private_rehearsal.py",
    "tests/unit/deploy/test_source_refresh_transition.py",
    "tests/unit/deploy/test_verify_candidate_semantics.py",
    "tests/unit/deploy/test_prepare_single_vps_release.py",
    "tests/unit/deploy/test_issue_wavea_activation.py",
    "tests/unit/deploy/test_same_port_rehearsal.py",
    "tests/unit/deploy/test_verify_private_rehearsal.py",
    "docs/operations/source-refresh-transition-499-d033.md",
    "tasks/todo.md",
    "tasks/lessons.md",
})
DRUG_COVERAGE_DELTA_PATHS = frozenset({
    ("emr_blocked_count",), ("encode_tier_C_deferred_count",),
    ("encode_tier_c_deferred_count",), ("encoded_clause_count",),
    ("encoded_clause_pct",), ("inn_named_actionable_pct",),
    ("inn_named_clause_count",), ("non_actionable_count",), ("pilot_rule_count",),
    ("registry_promotion_gate", "classified_rows"),
    ("registry_promotion_gate", "deferred_rows"),
    ("registry_promotion_gate", "deontic_unencoded_gap_count"),
    ("registry_promotion_gate", "encoded_rows"),
    ("registry_promotion_gate", "substantive_closure_pct"),
    ("registry_promotion_gate", "true_gap_count"),
    ("section_4.2.14.C_clause_total",), ("section_4.2.14.C_rule_count",),
    ("section_4.2.14.C_tier_c_deferred_count",),
    ("subsection_coverage", "4.2.14.C", "clause_total"),
    ("subsection_coverage", "4.2.14.C", "encoded_clause_count"),
    ("subsection_coverage", "4.2.14.C", "encoded_clause_pct"),
    ("tier_a_pending_count",), ("tier_b_pending_count",), ("tier_b_rule_count",),
    ("v1_stop_conditions", "inn_named_actionable_pct"),
})
EVALUATION_DELTA_FIELDS = frozenset({
    "decision", "disposition", "disposition_reason", "evaluation_status",
    "missing_inputs", "reason", "required_inputs",
})
_STATUSES = ("evaluated", "missing_inputs", "unavailable")
_REPORT_TABLES = {
    "patient_billing_report_rows": "wavea_evidence_detail",
    "patient_bill_billing_report_rows": "wavea_bill_evidence_detail",
}
_TABLES = frozenset({*_REPORT_TABLES, *_REPORT_TABLES.values(), "wavea_evidence_index"})
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PROOF_BINDINGS: dict[object, str] = {}
_git = historical._git
_replay_checkout_binding = historical._replay_checkout_binding


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _same(left: Any, right: Any, context: str) -> None:
    if _canonical(left) != _canonical(right):
        # Contexts are static/public. Never put a private row key or value here.
        raise ValueError(f"Source refresh changes protected {context}")


def _without(value: Mapping, fields: set | frozenset) -> dict:
    return {key: item for key, item in value.items() if key not in fields}


def _changed_paths(old: Any, new: Any, path: tuple = ()) -> set[tuple]:
    if isinstance(old, dict) and isinstance(new, dict):
        changed = set()
        for key in old.keys() | new.keys():
            if key not in old or key not in new:
                changed.add((*path, key))
            else:
                changed.update(_changed_paths(old[key], new[key], (*path, key)))
        return changed
    return set() if _canonical(old) == _canonical(new) else {path}


def validate_transition_request(value: Mapping | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, Mapping) and value.get("contract") == historical.TRANSITION_CONTRACT:
        return historical.validate_transition_request(value)
    if (not isinstance(value, Mapping)
            or set(value) != {"contract", "expected_candidate_sha", "expected_verifier_sha"}
            or value.get("contract") != TRANSITION_CONTRACT
            or any(not isinstance(value.get(key), str) or not _SHA.fullmatch(value[key])
                   for key in ("expected_candidate_sha", "expected_verifier_sha"))
            or value["expected_candidate_sha"] != value["expected_verifier_sha"]):
        raise ValueError("Source refresh requires one explicit immutable candidate/verifier identity")
    return dict(value)


def _verify_candidate_history(checkout: Path, expected_candidate_sha: str) -> dict:
    if not isinstance(expected_candidate_sha, str) or not _SHA.fullmatch(expected_candidate_sha):
        raise ValueError("Source refresh requires a full candidate SHA")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != expected_candidate_sha:
        raise ValueError("Source refresh checkout differs from reviewed candidate")
    for sha, tree in ((BASELINE_CODE_SHA, BASELINE_TREE),
                      (PRODUCT_ANCHOR_SHA, PRODUCT_ANCHOR_TREE)):
        if _git(checkout, "rev-parse", f"{sha}^{{tree}}").decode().strip() != tree:
            raise ValueError("Source refresh pinned product tree differs")
    if _git(checkout, "show", "-s", "--format=%P", PRODUCT_ANCHOR_SHA).decode().split() != [BASELINE_CODE_SHA]:
        raise ValueError("Source refresh product anchor has unknown ancestry")
    ancestor = subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor",
                               PRODUCT_ANCHOR_SHA, expected_candidate_sha], capture_output=True)
    if ancestor.returncode:
        raise ValueError("Source refresh candidate is not a pinned product descendant")
    commits = _git(checkout, "rev-list", "--reverse", "--ancestry-path",
                   f"{PRODUCT_ANCHOR_SHA}..{expected_candidate_sha}").decode().splitlines()
    previous = PRODUCT_ANCHOR_SHA
    for sha in commits:
        if _git(checkout, "show", "-s", "--format=%P", sha).decode().split() != [previous]:
            raise ValueError("Source refresh requires linear tooling-only history")
        names = {os.fsdecode(item) for item in _git(checkout, "diff-tree", "--no-commit-id",
                    "--name-only", "-r", "-z", previous, sha).split(b"\0") if item}
        if not names or not names <= AUTHORIZED_TOOLING_PATHS:
            raise ValueError("Source refresh descendant changes an unauthorized path")
        previous = sha
    if not commits or previous != expected_candidate_sha:
        raise ValueError("Source refresh requires a new immutable tooling descendant")
    changed = {os.fsdecode(item) for item in _git(checkout, "diff", "--name-only", "-z",
                   PRODUCT_ANCHOR_SHA, expected_candidate_sha).split(b"\0") if item}
    if not changed or not changed <= AUTHORIZED_TOOLING_PATHS:
        raise ValueError("Source refresh candidate changes pinned product/source bytes")
    return {"product_anchor_sha": PRODUCT_ANCHOR_SHA,
            "product_anchor_tree": PRODUCT_ANCHOR_TREE,
            "candidate_sha": expected_candidate_sha, "descendant_commits": commits,
            "authorized_changed_paths": sorted(changed)}


def _guard_code_binding(checkout: Path, expected_sha: str) -> dict:
    # The byte-frozen historical helper binds the complete executing closure,
    # including this new file, to Git independently of index/stat shortcuts.
    binding = historical._guard_code_binding(checkout, expected_sha)
    if "scripts/deploy/verify_source_refresh_transition.py" not in binding["files"]:
        raise ValueError("Source refresh verifier is absent from reviewed Git tooling")
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
    for name, module in tuple(sys.modules.items()):
        if name == 'src' or name.startswith('src.'):
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
        raise ValueError("Source replay requires an explicit existing runtime and dependency roots")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
                   "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1"}
    with tempfile.TemporaryDirectory(prefix="bilun-source-refresh-") as directory:
        trace = Path(directory) / "replay.trace"
        command = ["strace", "-f", "-yy", "-s", "4096", "-e",
                   "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
                   "-o", str(trace), str(python_executable), "-I", "-S", "-B", "-X",
                   f"pycache_prefix={directory}/bytecode", "-c", _WORKER,
                   str(claims_dir), str(clean_dir), mode,
                   json.dumps([str(path) for path in dependency_roots])]
        result = subprocess.run(command, cwd=checkout, env=environment, capture_output=True,
                                timeout=1800, check=False)
        if result.returncode:
            raise ValueError("Independent source replay failed; no transition permission was issued")
        value = _parse_json(result.stdout.decode(), context="independent source refresh replay")
        if not isinstance(value, dict) or set(value) != {
            "tables", "coverage", "neutral_raw", "rules", "rule_groups",
        }:
            raise ValueError("Source replay has an unknown ownership contract")
        # A dependency/OS-file allowance must never hide secret environment or
        # cache/oracle reads. No candidate DB is available to this pure worker.
        for line in trace.read_text().splitlines():
            if " = -1 " not in line and re.search(r"/(?:\.env|\.env\.[^/\"<>]*)[\"<>]", line):
                raise ValueError("Independent source replay read an environment file")
            if " = -1 " not in line and re.search(r"\.(?:duckdb|db|sqlite3?)(?:-wal|-shm)?[\"<>]", line):
                raise ValueError("Independent source replay read a database oracle")
        parsed = validate_runtime_read_trace(trace, roster=roster,
                    candidate_db=Path(directory) / "unused.duckdb", dependency_roots=dependency_roots)
        if parsed.get("trace_parse_ok") is not True:
            raise ValueError("Independent source replay read closure is unverified")
        return value


def _check_coverage_pair(old: dict, new: dict) -> None:
    if not isinstance(old, dict) or set(old) != {"drug", "materials"} or old.keys() != new.keys():
        raise ValueError("Source coverage has an unknown ownership boundary")
    if (not _changed_paths(old["drug"], new["drug"]) <= DRUG_COVERAGE_DELTA_PATHS
            or not _changed_paths(old["materials"], new["materials"]) <= {("encoded_corpus_rows",)}):
        raise ValueError("Source refresh changes unreviewed coverage metadata")


def _status_counts() -> dict[str, int]:
    return dict.fromkeys(_STATUSES, 0)


def _check_counts(detail: dict, rule_groups: dict) -> None:
    by_rule = {key: _status_counts() for key in rule_groups}
    by_group = {key: _status_counts() for key in set(rule_groups.values())}
    rows = detail.get("evaluations")
    if not isinstance(rows, list) or not isinstance(detail.get("counts"), dict):
        raise ValueError("Source refresh lacks complete evaluation counts")
    identities = set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("rule_id") not in rule_groups
                or row.get("evaluation_status") not in _STATUSES
                or not isinstance(row.get("evaluation_id"), str)
                or row["evaluation_id"] in identities):
            raise ValueError("Source refresh evaluation ownership/counts are malformed")
        identities.add(row["evaluation_id"])
        by_rule[row["rule_id"]][row["evaluation_status"]] += 1
        by_group[rule_groups[row["rule_id"]]][row["evaluation_status"]] += 1
    counts = detail["counts"]
    _same(counts.get("by_rule"), by_rule, "independently counted rule statuses")
    _same(counts.get("by_group"), by_group, "independently counted group statuses")
    _same(counts.get("evaluation_count"), len(rows), "complete evaluation cardinality")
    for collection, prefix in (("reviews", "review"), ("advisories", "advisory"),
                               ("financial_rows", "financial")):
        items = detail.get(collection)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ValueError("Source refresh sparse evidence is malformed")
        _same(counts.get(prefix + "_count"), len(items), "sparse evidence cardinality")
        _same(counts.get(prefix + "_by_rule"), dict(Counter(item["rule_id"] for item in items)),
              "sparse evidence rule counts")


def _neutral_evaluation(row: dict) -> None:
    for key, expected in (("evaluation_status", "unavailable"), ("decision", None),
                          ("reason", "source_review_required"), ("required_inputs", []),
                          ("missing_inputs", [])):
        if key not in row:
            raise ValueError("Source quarantine evaluation is incomplete")
        _same(row[key], expected, "neutral organ evaluation")


def _check_detail_pair(old: dict, new: dict, rule_groups: dict) -> int:
    for detail in (old, new):
        _check_counts(detail, rule_groups)
    left, right = old["evaluations"], new["evaluations"]
    if len(left) != len(right):
        raise ValueError("Source refresh changes evaluation inventory")
    changed = 0
    for row, other in zip(left, right, strict=True):
        # Equality of all identity fields proves stable ownership AND order;
        # an ordered-array diff alone cannot authorize a quarantine.
        if row.get("rule_id") in NEUTRAL_RULE_IDS:
            if row.get("claim_id") is None:
                # The adapter's no-header branch precedes the quarantine. Its
                # missing-context result remains exact, without new permission.
                _same(row, other, "organ observation without claim headers")
                continue
            if (row.get("patient_id") != old.get("patient_id")
                    or not isinstance(row.get("claim_id"), str) or not row["claim_id"]
                    or row.get("line_kind") != "claim" or row.get("line_id") is not None):
                raise ValueError("Neutral organ evaluation has foreign claim ownership")
            _same(_without(row, EVALUATION_DELTA_FIELDS), _without(other, EVALUATION_DELTA_FIELDS),
                  "organ identity/selection/money/provenance/ordering")
            _neutral_evaluation(other)
            _same(other.get("disposition"), "unavailable", "neutral organ disposition")
            _same(other.get("disposition_reason"), "source_review_required", "neutral organ disposition reason")
            changed += _canonical(row) != _canonical(other)
        else:
            _same(row, other, "unrelated evaluation")
    _same(_without(old, {"evaluations", "counts"}), _without(new, {"evaluations", "counts"}),
          "detail sparse evidence/source/clinical/money")
    before, after = old["counts"], new["counts"]
    _same(_without(before, {"by_rule", "by_group"}), _without(after, {"by_rule", "by_group"}),
          "remaining detail counts")
    _same(_without(before["by_rule"], NEUTRAL_RULE_IDS), _without(after["by_rule"], NEUTRAL_RULE_IDS),
          "unrelated rule counters")
    _same(_without(before["by_group"], {"treatment_pricing_2_4"}),
          _without(after["by_group"], {"treatment_pricing_2_4"}), "unrelated group counters")
    return changed


def _check_report_coverage(report: dict, detail: dict) -> None:
    expected = {"schema_version": detail["schema_version"], "available": detail["available"],
                "unavailable_reason": detail["unavailable_reason"],
                "tracked_rule_count": len(detail["counts"]["by_rule"]),
                "evaluation_count": detail["counts"]["evaluation_count"],
                "by_group": detail["counts"]["by_group"]}
    _same(report.get("wavea_coverage"), expected, "report coverage derived from its own complete detail")


def _check_report_pair(old: dict, new: dict, old_coverage: dict, new_coverage: dict) -> None:
    for report, coverage in ((old, old_coverage), (new, new_coverage)):
        _same(report.get("drug_indication", {}).get("coverage_scope"), coverage["drug"],
              "own-source drug coverage")
        _same(report.get("materials", {}).get("specialty_coverage_scope"), coverage["materials"],
              "own-source material coverage")
    left, right = json.loads(_canonical(old)), json.loads(_canonical(new))
    for value in (left, right):
        del value["drug_indication"]["coverage_scope"]
        del value["materials"]["specialty_coverage_scope"]
        value["wavea_coverage"].pop("by_group")
    _same(left, right, "report status/clinical/selection/actions/money/provenance")


def _expected_neutral_raw(rule: dict) -> dict:
    return {"rule": "treatment_pricing_2_4", "severity": "review",
            "message": "Kaynak incelemesi tamamlanmadığı için bu kuralın değerlendirmesi ertelendi.",
            "savings_try": 0.0, "risk_amount": 0.0, "sut_section": rule.get("sut_section", ""),
            "rule_id": rule["rule_id"], "billable": None, "material_outcome": "review_required",
            "annex_basis": None, "details": {"prose_rule_set": "treatment_pricing_2_4",
                "source_status": "review_required", "clinical_eligibility_complete": False}}


def _check_neutral_raw(old: dict, new: dict, rules: dict, details: dict) -> int:
    if old.keys() != new.keys() or old.keys() != details.keys():
        raise ValueError("Source replay raw claim inventory differs")
    total = 0
    for key in old:
        before, after = old[key], new[key]
        _same(before["claims"], after["claims"], "raw claim ownership")
        claims = after["claims"]
        if not isinstance(claims, list) or not claims or claims != sorted(set(claims)):
            raise ValueError("Neutral source replay lacks stable claims")
        owned = {(claim, rule) for claim in claims for rule in NEUTRAL_RULE_IDS}
        rows = [row for row in after["legacy_rows"] if row.get("rule_id") in NEUTRAL_RULE_IDS]
        if {(row.get("claim_id"), row.get("rule_id")) for row in rows} != owned or len(rows) != len(owned):
            raise ValueError("Source replay lacks exactly three neutral organ rows per claim")
        for row in rows:
            _same(row.get("patient_id"), details[key]["patient_id"], "raw organ patient ownership")
            _same(row.get("family"), "treatment_pricing_2_4", "raw organ family")
            _same(row.get("legacy_row"), _expected_neutral_raw(rules[row["rule_id"]]),
                  "source-neutral payment classification")
        raw_evals = [row for row in after["evaluations"] if row.get("rule_id") in NEUTRAL_RULE_IDS]
        if {(row.get("claim_id"), row.get("rule_id")) for row in raw_evals} != owned or len(raw_evals) != len(owned):
            raise ValueError("Source replay lacks complete neutral organ observations")
        by_identity = {row["evaluation_id"]: row for row in details[key]["evaluations"]}
        for row in raw_evals:
            _neutral_evaluation(row)
            _same(row.get("patient_id"), details[key]["patient_id"], "raw evaluation ownership")
            projected = by_identity.get(row.get("evaluation_id"))
            if not isinstance(projected, dict):
                raise ValueError("Source replay raw evaluation has no owned full-detail projection")
            _same(row, {field: projected[field] for field in row}, "raw-to-full organ projection")
        for collection in ("evaluations", "legacy_rows", "matches"):
            _same([row for row in before[collection] if row.get("rule_id") not in NEUTRAL_RULE_IDS],
                  [row for row in after[collection] if row.get("rule_id") not in NEUTRAL_RULE_IDS],
                  "unrelated raw treatment observation")
        if any(row.get("rule_id") in NEUTRAL_RULE_IDS for row in after["matches"]):
            raise ValueError("Neutral organ quarantine produced a payable or selected match")
        total += len(rows)
    return total


def _check_index_pair(old: dict, new: dict) -> None:
    def protected(value: dict) -> dict:
        output = json.loads(_canonical(value))
        for counts in (output["counts"], *(row["counts"] for row in output["patients"].values())):
            for rule in NEUTRAL_RULE_IDS:
                del counts["by_rule"][rule]
            del counts["by_group"]["treatment_pricing_2_4"]
        return output
    _same(protected(old), protected(new), "index inventory/sparse evidence/remaining counts")


def _check_index(index: dict, details: dict, rule_groups: dict) -> None:
    """Recount the complete patient-only index without trusting index values."""
    if not details:
        raise ValueError("Source refresh index lacks its full patient detail inventory")
    aggregate_rule = {key: _status_counts() for key in rule_groups}
    aggregate_group = {key: _status_counts() for key in set(rule_groups.values())}
    patients, evidence = {}, []
    totals = {key: 0 for key in ("review_count", "advisory_count", "financial_count")}
    first = next(iter(details.values()))
    for key in sorted(details):
        detail = details[key]
        _check_counts(detail, rule_groups)
        _same(detail.get("patient_id"), key, "patient-only index ownership")
        for name in ("schema_version", "roster_version", "data_source"):
            _same(detail[name], first[name], "index own-source detail contract")
        counts = detail["counts"]
        for source, destination in ((counts["by_rule"], aggregate_rule),
                                    (counts["by_group"], aggregate_group)):
            for identity, statuses in source.items():
                for status in _STATUSES:
                    destination[identity][status] += statuses[status]
        for name in totals:
            totals[name] += counts[name]
        for collection in ("reviews", "advisories", "financial_rows"):
            evidence.extend(detail[collection])
        patients[key] = {"available": detail["available"],
                         "unavailable_reason": detail["unavailable_reason"],
                         "counts": {field: counts[field] for field in (
                             "by_rule", "by_group", "evaluation_count", "review_count",
                             "advisory_count", "financial_count")}}
    expected = {"schema_version": first["schema_version"], "roster_version": first["roster_version"],
                "capability": "draft", "available": True, "n_patients": len(patients),
                "n_patients_unavailable": sum(not row["available"] for row in patients.values()),
                "patients": patients, "counts": {"by_rule": aggregate_rule,
                    "by_group": aggregate_group, **totals},
                "evidence_rows": sorted(evidence, key=lambda row: row["evidence_id"]),
                "data_source": first["data_source"]}
    _same(index, expected, "complete patient-only index independently recounted from detail")


def _check_projection_pair(old: dict, new: dict) -> dict:
    expected = {"tables", "coverage", "neutral_raw", "rules", "rule_groups"}
    if set(old) != expected or set(new) != expected or set(old["tables"]) != _TABLES or set(new["tables"]) != _TABLES:
        raise ValueError("Source replay has unknown tables or projections")
    _same(old["rule_groups"], new["rule_groups"], "source rule/group roster")
    _check_coverage_pair(old["coverage"], new["coverage"])
    changed = neutral = 0
    compiled_rules = {row["rule_id"]: row for row in new["rules"]["rules"]}
    for table, detail_table in _REPORT_TABLES.items():
        left, right = old["tables"][table], new["tables"][table]
        old_details, new_details = old["tables"][detail_table], new["tables"][detail_table]
        if not left or left.keys() != right.keys() or left.keys() != old_details.keys() or left.keys() != new_details.keys():
            raise ValueError("Source replay patient/bill/detail ownership differs")
        for key in left:
            changed += _check_detail_pair(old_details[key], new_details[key], old["rule_groups"])
            _check_report_coverage(left[key], old_details[key])
            _check_report_coverage(right[key], new_details[key])
            _check_report_pair(left[key], right[key], old["coverage"], new["coverage"])
        family = "patients" if table == "patient_billing_report_rows" else "bills"
        neutral += _check_neutral_raw(old["neutral_raw"][family], new["neutral_raw"][family],
                                      compiled_rules, new_details)
    for value in (old, new):
        _check_index(value["tables"]["wavea_evidence_index"], value["tables"]["wavea_evidence_detail"],
                     value["rule_groups"])
    _check_index_pair(old["tables"]["wavea_evidence_index"], new["tables"]["wavea_evidence_index"])
    return {"changed_organ_evaluations": changed, "neutral_raw_rows": neutral}


def _source_intent(baseline: dict, candidate: dict, old: dict, new: dict) -> dict:
    for roster, sha, blob, projected in (
        (baseline, BASELINE_CODE_SHA, BASELINE_SOURCE_BLOB, old),
        (candidate, PRODUCT_ANCHOR_SHA, PRODUCT_SOURCE_BLOB, new),
    ):
        checkout = Path(roster["checkout"])
        if _git(checkout, "rev-parse", f"{sha}:{SOURCE_PATH}").decode().strip() != blob:
            raise ValueError("Source refresh authored organ blob differs")
        authored = _parse_json(_git(checkout, "show", f"{sha}:{SOURCE_PATH}").decode(),
                               context="public authored organ source")
        _same(projected["rules"], authored, "compiled own-source treatment rules")
    rules = {row["rule_id"]: row for row in new["rules"]["rules"]}
    marked = {key for key, row in rules.items() if row.get("source_review_required") is True}
    if marked != NEUTRAL_RULE_IDS:
        raise ValueError("Source refresh does not quarantine exactly the three reviewed organ rules")
    for key in NEUTRAL_RULE_IDS:
        if rules[key].get("gate_b_sources") != []:
            raise ValueError("Neutral organ rule acquired unsupported payment authority")
    return {"source_path": SOURCE_PATH, "baseline_blob": BASELINE_SOURCE_BLOB,
            "product_blob": PRODUCT_SOURCE_BLOB, "neutral_rule_ids": sorted(NEUTRAL_RULE_IDS),
            "clinical_eligibility_complete": False, "quarantine_is_payment_neutral": True}


@dataclass(frozen=True)
class SourceRefreshProof:
    _report_json: str
    _projections_json: str = field(repr=False)
    _seal: object | None = field(default=None, repr=False, compare=False)

    @property
    def report(self) -> dict:
        return json.loads(self._report_json)

    @property
    def projections(self) -> dict:
        return json.loads(self._projections_json)


def _issue_proof(report: dict, projections: dict) -> SourceRefreshProof:
    seal = object()
    proof = SourceRefreshProof(_canonical(report), _canonical(projections), seal)
    _PROOF_BINDINGS[seal] = _digest([proof._report_json, proof._projections_json])
    return proof


def _require_proof(proof: SourceRefreshProof) -> None:
    if (not isinstance(proof, SourceRefreshProof) or type(proof._seal) is not object
            or proof._seal not in _PROOF_BINDINGS
            or _PROOF_BINDINGS[proof._seal] != _digest([proof._report_json, proof._projections_json])):
        raise ValueError("Source refresh content lacks a fresh sealed replay proof")
    validate_transition_report_contract(proof.report)


def verify_transition(*, request: Mapping, baseline_roster: Path, candidate_roster: Path,
                      baseline_meta: Mapping, candidate_meta: Mapping, same_input: Mapping,
                      python_executable: Path, expected_candidate_sha: str,
                      dependency_roots: tuple[Path, ...], expected_verifier_sha: str | None = None
                      ) -> SourceRefreshProof | historical.ClinicalTransitionProof:
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
    if requested["contract"] == historical.TRANSITION_CONTRACT:
        return historical.verify_clinical_semantic_transition(**args)
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
              "protected_fields": "all_other_fields_type_exact_unchanged"}
    report = {"status": "source_refresh_transition_verified", **identity,
              "transition_sha256": _digest(identity)}
    validate_transition_report_contract(report)
    # Raw adapters and rule documents were checked above. Keep only the five
    # private expected cache projections for subsequent admission, reducing
    # memory without weakening the report's full-replay digests.
    expected_tables = {side: {"tables": projection["tables"]} for side, projection in projections.items()}
    return _issue_proof(report, expected_tables)


def validate_transition_report_contract(report: Mapping) -> None:
    if not isinstance(report, Mapping):
        raise ValueError("Transition report is malformed")
    if report.get("contract") == historical.TRANSITION_CONTRACT:
        if report.get("status") != "clinical_semantic_transition_verified":
            raise ValueError("Historical transition report has unknown status")
        return
    required = {"status", "contract", "baseline_code_sha", "baseline_tree", "candidate_code_sha",
                "history", "verifier", "replay_checkouts", "same_input", "source_intent",
                "baseline_replay_sha256", "candidate_replay_sha256", "transition_sha256",
                "changed_organ_evaluations", "neutral_raw_rows", "patient_count", "bill_count",
                "protected_fields"}
    if (set(report) != required or report.get("contract") != TRANSITION_CONTRACT
            or report.get("status") != "source_refresh_transition_verified"
            or report.get("baseline_code_sha") != BASELINE_CODE_SHA or report.get("baseline_tree") != BASELINE_TREE
            or not isinstance(report.get("candidate_code_sha"), str) or not _SHA.fullmatch(report["candidate_code_sha"])
            or report.get("protected_fields") != "all_other_fields_type_exact_unchanged"):
        raise ValueError("Source refresh report has an unknown contract or identity")
    candidate = report["candidate_code_sha"]
    history, binding, source, inputs, checkouts = (report[key] for key in
        ("history", "verifier", "source_intent", "same_input", "replay_checkouts"))
    if (not all(isinstance(value, dict) for value in (history, binding, source, inputs, checkouts))
            or set(history) != {"product_anchor_sha", "product_anchor_tree", "candidate_sha",
                                "descendant_commits", "authorized_changed_paths"}
            or history.get("product_anchor_sha") != PRODUCT_ANCHOR_SHA
            or history.get("product_anchor_tree") != PRODUCT_ANCHOR_TREE
            or history.get("candidate_sha") != candidate
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
    _same(source, {"source_path": SOURCE_PATH, "baseline_blob": BASELINE_SOURCE_BLOB,
        "product_blob": PRODUCT_SOURCE_BLOB, "neutral_rule_ids": sorted(NEUTRAL_RULE_IDS),
        "clinical_eligibility_complete": False, "quarantine_is_payment_neutral": True},
        "typed source intent")
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
    excluded = {"status", "transition_sha256"}
    _same(report["transition_sha256"], _digest(_without(report, excluded)), "transition identity digest")


def _without_build_ids(table: str, value: Any) -> Any:
    if table == "wavea_evidence_index":
        return _without(value, {"build_id"})
    if table in _REPORT_TABLES.values():
        return {key: _without(row, {"build_id"}) for key, row in value.items()}
    return value


def normalize_transition_content(table: str, value: Any, *, side: str, proof: Any,
                                 patient_reports: dict | None = None) -> Any:
    if isinstance(proof, historical.ClinicalTransitionProof):
        return historical.normalize_transition_content(table, value, side=side, proof=proof,
                                                       patient_reports=patient_reports)
    _require_proof(proof)
    if side not in {"baseline", "candidate"}:
        raise ValueError("Source refresh content side is unknown")
    if table not in _TABLES:
        return value
    projections = proof.projections
    expected = projections[side]["tables"][table]
    _same(_without_build_ids(table, value), expected, "cache against its own independent full-cohort replay")
    if side == "baseline":
        return value
    output = json.loads(_canonical(projections["baseline"]["tables"][table]))
    # Preserve the selected build identity for the existing structural gate,
    # and each side's attested paths for the existing path normalization.
    if table == "wavea_evidence_index":
        output["build_id"] = value["build_id"]
        output["data_source"] = value["data_source"]
    else:
        for key, row in output.items():
            row["data_source"] = value[key]["data_source"]
            if table in _REPORT_TABLES.values():
                row["build_id"] = value[key]["build_id"]
    return output


def normalize_transition_http_reports(reports: dict[str, dict], *, side: str, proof: Any,
                                      transport: Any, baseline_transport: Any,
                                      view: str = "draft") -> dict[str, dict]:
    if isinstance(proof, historical.ClinicalTransitionProof):
        return historical.normalize_transition_http_reports(reports, side=side, proof=proof,
            transport=transport, baseline_transport=baseline_transport, view=view)
    from scripts.deploy.rehearse_wavea_same_port import PinnedReportTransport
    from scripts.deploy.verify_candidate_semantics import _legacy_report

    _require_proof(proof)
    if side not in {"baseline", "candidate"} or view not in {"draft", "legacy"}:
        raise ValueError("Source refresh HTTP side or view is unknown")
    for label, package in (("baseline", baseline_transport), (side, transport)):
        if (not isinstance(package, PinnedReportTransport)
                or package.code_sha != proof.report[label + "_code_sha"]
                or package.contract != "wavea-evidence-v2"):
            raise ValueError("Source refresh HTTP transport differs from its pinned source")
        package.validate()
        raw, _ = historical._http_report_scopes(package.raw_reports)
        for table, rows in raw.items():
            normalize_transition_content(table, rows, side=label, proof=proof)
    expected = transport.draft_reports if view == "draft" else {
        path: _legacy_report(row) for path, row in transport.complete_reports.items()}
    baseline = baseline_transport.draft_reports if view == "draft" else {
        path: _legacy_report(row) for path, row in baseline_transport.complete_reports.items()}
    _same(reports, expected, "HTTP exact pinned serializer/model projection")
    if reports.keys() != baseline.keys():
        raise ValueError("Source refresh HTTP inventory differs")
    if side == "baseline":
        return reports
    output = json.loads(_canonical(reports))
    for path, row in output.items():
        previous = baseline[path]
        row["drug_indication"]["coverage_scope"] = previous["drug_indication"]["coverage_scope"]
        row["materials"]["specialty_coverage_scope"] = previous["materials"]["specialty_coverage_scope"]
        if "wavea_coverage" in row:
            row["wavea_coverage"] = previous["wavea_coverage"]
    return output
