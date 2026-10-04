"""One source/input-bound inventory transition; ordinary releases stay strict.

This contract does not authorize changed eligibility, clinical evidence, money,
status or selected rules. It verifies the reviewed darbepoetin alias inventory
correction independently of each cache's producer, then replays both pinned
producers in isolated subprocesses. Only their bounded inventory/narrative
projections may differ; every remaining cached field still compares exactly.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from scripts.deploy.generate_candidate_source_roster import (
    _REPO_FILES, _REPO_ROOTS, _selected, validate_runtime_read_trace,
)
from scripts.deploy.verify_candidate_cache import _parse_json, _stable_file_hash
from scripts.deploy.verify_same_input import _roster

TRANSITION_CONTRACT = "bilun-pr143-drug-inventory-transition-v1"
BASELINE_CODE_SHA = "3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b"
BASELINE_TREE = "7acefd250cf56d06ff92ddd2e9933d28695f615a"
PRODUCT_ANCHOR_SHA = "3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea"
PRODUCT_ANCHOR_TREE = "6f102905fc1e150de89eefdac91fddbfdff10d10"
SOURCE_PATH = "data/gazette/prose_rule_sources/drug_indication/4.2.9.A-2.yaml"
BASELINE_SOURCE_BLOB = "8b04c74434acfcdc3af6db2ee31070c32eb495df"
PRODUCT_SOURCE_BLOB = "7b574b32f24e143ef46100894f741a9bdd224878"
REVIEW_PACKET_PATH = "data/gazette/clinical_sources/source_context_repairs_2026_10.json"
REVIEW_PACKET_BLOB = "3ed83b036669f35c2c421e87e5c0bff14a080e21"
INPUT_BYTES_SHA256 = "84efa030d2c5e927f8afb94ce8c494647e398e236d02b560a3d281531231d1f3"
BASELINE_SOURCE_HASH = "c211fa8490d12db89b5456a071e6a20775c271ade49270776374c0f292b49b92"
BASELINE_CONFIG_HASH = "474642a8400d820435d8dbe3f40524ffd357edf8d40cc77a9621fd56b6b5921b"
# Source-only public corpus generators, executed independently at both pinned
# Git trees. These are expected metadata, never hashes copied from a cache.
BASELINE_COVERAGE_SHA256 = "6ff61763030de04a3a49167da8c0cead216d726a22ae628b9b8c75d8348b3413"
PRODUCT_COVERAGE_SHA256 = "375aed0840d735c9c53ab910e6cccfeb4b9d9868ea93449fface1696f95290ac"
SOURCE_ROUTE_SHA256 = {
    "4.2.9.mds_esa_hematology_report": "4c0fb00d67a3dee24b4979969313190e995beca7d1fbabeced9de834ac823dbd",
    "4.2.9.mds_esa_initiation_hematology_report": "2e50b850e7218ff61e66aa29353eef8a4f48ac59e2204416264aad1ac7087ed6",
    "4.2.9.A-2.darbepoetin_mds_source_review": "79aa08813f1438289817d97da02ecbc61535296cd536a2095c342b83d70e2b24",
}
COVERAGE_DELTA_PATHS = frozenset({
    ("pilot_rule_count",), ("temporal_source_review_count",), ("temporal_source_correction_count",),
    ("section_4.2.14.C_rule_count",), ("tier_b_rule_count",), ("encode_tier_c_deferred_count",),
    ("encode_tier_C_deferred_count",), ("encoded_clause_count",), ("encoded_clause_pct",),
    ("tier_a_pending_count",), ("non_actionable_count",),
    ("subsection_coverage", "4.2.6", "clause_total"),
    ("subsection_coverage", "4.2.6", "encoded_clause_count"),
    ("subsection_coverage", "4.2.6", "encoded_clause_pct"),
    ("subsection_coverage", "4.2.9", "encoded_clause_count"),
    ("subsection_coverage", "4.2.9", "encoded_clause_pct"),
    ("subsection_coverage", "4.2.14.C", "encoded_clause_count"),
    ("subsection_coverage", "4.2.14.C", "encoded_clause_pct"),
    ("subsection_coverage", "4.2.17", "encoded_clause_count"),
    ("subsection_coverage", "4.2.17", "encoded_clause_pct"),
    ("registry_promotion_gate", "deferred_rows"),
    ("registry_promotion_gate", "deontic_unencoded_gap_count"),
    ("registry_promotion_gate", "substantive_closure_pct"),
    ("registry_promotion_gate", "encoded_rows"),
    ("registry_promotion_gate", "true_gap_count"),
})
ADDED_RULE_ID = "4.2.9.A-2.darbepoetin_mds_source_review"
REMOVED_RULE_IDS = frozenset({
    "4.2.9.mds_esa_hematology_report",
    "4.2.9.mds_esa_initiation_hematology_report",
})
FRONTEND_CONFIG_PATH = "frontend/next.config.ts"
FRONTEND_CONFIG_BASELINE_BLOB = "d4b1241ba2e8a2bef5fbfb69e1a0a05c652182cc"
FRONTEND_CONFIG_CANDIDATE_BLOB = "cbc2b7e615dba97135d1221375eac00c41e2ca05"
_FRONTEND_CONFIG_SHA256 = {
    FRONTEND_CONFIG_BASELINE_BLOB: "fd6785328e47d801e0ff70e715b42f5823dacce290f2df81ac94b4ca6f526d1a",
    FRONTEND_CONFIG_CANDIDATE_BLOB: "b5c2bf140e79eb8f0cb19f713f26e53a09ea32ebef8338c29ff3752c70669da3",
}
AUTHORIZED_TOOLING_PATHS = frozenset({
    "scripts/deploy/verify_clinical_semantic_transition.py",
    "scripts/deploy/verify_candidate_semantics.py",
    "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_private_rehearsal.py",
    "scripts/deploy/build_wavea_sidecar.py",
    "scripts/deploy/paired_release.py",
    "scripts/deploy/probe_auth.py",
    "scripts/deploy/recover_old_pair.py",
    "scripts/deploy/rehearse_wavea_pair.py",
    "scripts/deploy/run_wavea_route_transaction.py",
    "scripts/deploy/verify_legacy_equivalence.py",
    "src/bilun/api/wavea_activation.py",
    "tests/unit/deploy/test_clinical_semantic_transition.py",
    "tests/unit/deploy/test_verify_candidate_semantics.py",
    "tests/unit/deploy/test_same_port_rehearsal.py",
    "tests/unit/deploy/test_issue_wavea_activation.py",
    "tests/unit/deploy/test_prepare_single_vps_release.py",
    "tests/unit/deploy/test_verify_private_rehearsal.py",
    "tests/unit/deploy/probe_auth_fixtures.py",
    "tests/unit/deploy/test_probe_auth.py",
    "tests/unit/deploy/test_health_request.py",
    "tests/unit/deploy/test_recover_old_pair.py",
    "tests/unit/deploy/test_rehearsal_auth_contexts.py",
    "tests/unit/deploy/test_rehearse_wavea_pair.py",
    "tests/unit/deploy/test_single_vps_release_integration.py",
    "tests/unit/deploy/test_serving_activation.py",
    "tests/integration/deploy/test_generated_launcher_startup.py",
    "tests/integration/deploy/test_signed_transition_startup.py",
    "docs/operations/semantic-transition-3f5540cf-3e0e0c6d.md",
})
_REPORT_TABLES = {
    "patient_billing_report_rows": "patients",
    "patient_bill_billing_report_rows": "bills",
}
_SHA = re.compile(r"[0-9a-f]{40}\Z")


def validate_transition_request(value: Mapping | None) -> dict | None:
    """The operator must opt in with externally supplied immutable identities."""
    if value is None:
        return None
    if (not isinstance(value, Mapping)
            or set(value) != {"contract", "expected_candidate_sha", "expected_verifier_sha"}
            or value.get("contract") != TRANSITION_CONTRACT
            or any(not isinstance(value.get(key), str) or not _SHA.fullmatch(value[key])
                   for key in ("expected_candidate_sha", "expected_verifier_sha"))):
        raise ValueError("Clinical transition request has an unknown contract or identity")
    return dict(value)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _git(checkout: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError("Transition requires complete retained Git identities/history")
    return result.stdout


def _frontend_config_blob(checkout: Path, sha: str) -> str | None:
    parent = _git(checkout, "ls-tree", "-z", sha, "--", "frontend").split(b"\0")[0]
    if parent and parent.split(b"\t", 1)[0].decode().split()[:2] != ["040000", "tree"]:
        raise ValueError("Transition frontend config Git parent is not a directory")
    records = [row for row in _git(checkout, "ls-tree", "-z", sha,
                                  "--", FRONTEND_CONFIG_PATH).split(b"\0") if row]
    if not records:
        return None
    if len(records) != 1:
        raise ValueError("Transition frontend config Git locator is ambiguous")
    metadata, name = records[0].split(b"\t", 1)
    mode, kind, blob = metadata.decode().split()
    if mode != "100644" or kind != "blob" or os.fsdecode(name) != FRONTEND_CONFIG_PATH:
        raise ValueError("Transition frontend config requires the exact regular Git file")
    return blob


def _bind_frontend_config(checkout: Path, sha: str) -> dict[str, str] | None:
    """Bind only the two reviewed config blobs, independently of index flags."""
    blob = _frontend_config_blob(checkout, sha)
    source = checkout / FRONTEND_CONFIG_PATH
    if blob is None:
        if os.path.lexists(source) or source.parent.is_symlink():
            raise ValueError("Transition frontend config disk path has no reviewed Git file")
        return None
    if blob not in _FRONTEND_CONFIG_SHA256:
        raise ValueError("Transition frontend config has an unreviewed Git blob")
    if (source.is_symlink() or not source.is_file() or source != source.resolve(strict=True)
            or source.stat().st_nlink != 1 or source.stat().st_mode & 0o111):
        raise ValueError("Transition frontend config is not an independent regular disk file")
    before = _stable_file_hash(source)
    contents = source.read_bytes()
    if (hashlib.sha1(f"blob {len(contents)}\0".encode() + contents).hexdigest() != blob
            or hashlib.sha256(contents).hexdigest() != _FRONTEND_CONFIG_SHA256[blob]
            or _stable_file_hash(source) != before):
        raise ValueError("Transition frontend config disk bytes differ from reviewed Git")
    return {"path": FRONTEND_CONFIG_PATH, "git_mode": "100644", "git_blob": blob,
            "sha256": before}


def _verify_candidate_history(checkout: Path, expected_candidate_sha: str) -> dict[str, Any]:
    """Check every descendant commit, including changes later reverted."""
    if not _SHA.fullmatch(expected_candidate_sha):
        raise ValueError("Transition requires an explicit full candidate SHA")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != expected_candidate_sha:
        raise ValueError("Transition checkout differs from explicit candidate SHA")
    for sha, tree in ((BASELINE_CODE_SHA, BASELINE_TREE), (PRODUCT_ANCHOR_SHA, PRODUCT_ANCHOR_TREE)):
        if _git(checkout, "rev-parse", f"{sha}^{{tree}}").decode().strip() != tree:
            raise ValueError("Transition approved source tree differs")
    ancestry = subprocess.run(["git", "-C", str(checkout), "merge-base", "--is-ancestor",
                              PRODUCT_ANCHOR_SHA, expected_candidate_sha], capture_output=True)
    if ancestry.returncode:
        raise ValueError("Transition candidate is not an approved product descendant")
    commits = _git(checkout, "rev-list", "--reverse", "--ancestry-path",
                   f"{PRODUCT_ANCHOR_SHA}..{expected_candidate_sha}").decode().splitlines()
    previous = PRODUCT_ANCHOR_SHA
    config_transition = None
    for sha in commits:
        parents = _git(checkout, "show", "-s", "--format=%P", sha).decode().split()
        if parents != [previous]:
            raise ValueError("Transition requires a linear tooling-only descendant history")
        names = {os.fsdecode(name) for name in _git(checkout, "diff-tree", "--no-commit-id",
                    "--name-only", "-r", "-z", previous, sha).split(b"\0") if name}
        if FRONTEND_CONFIG_PATH in names:
            if (config_transition is not None
                    or (_frontend_config_blob(checkout, previous), _frontend_config_blob(checkout, sha))
                    != (FRONTEND_CONFIG_BASELINE_BLOB, FRONTEND_CONFIG_CANDIDATE_BLOB)):
                raise ValueError("Transition frontend config is not the single reviewed blob change")
            config_transition = {"commit_sha": sha, "path": FRONTEND_CONFIG_PATH,
                                 "baseline_blob": FRONTEND_CONFIG_BASELINE_BLOB,
                                 "candidate_blob": FRONTEND_CONFIG_CANDIDATE_BLOB}
        if not names or not names - {FRONTEND_CONFIG_PATH} <= AUTHORIZED_TOOLING_PATHS:
            raise ValueError("Transition descendant contains an unauthorized change")
        previous = sha
    if previous != expected_candidate_sha:
        raise ValueError("Transition descendant history is incomplete")
    changed = {os.fsdecode(name) for name in _git(checkout, "diff", "--name-only", "-z",
               PRODUCT_ANCHOR_SHA, expected_candidate_sha).split(b"\0") if name}
    if not changed - {FRONTEND_CONFIG_PATH} <= AUTHORIZED_TOOLING_PATHS:
        raise ValueError("Transition candidate changes product/source/catalog bytes")
    if ((FRONTEND_CONFIG_PATH in changed) != (config_transition is not None)
            or config_transition is not None
            and (_frontend_config_blob(checkout, PRODUCT_ANCHOR_SHA),
                 _frontend_config_blob(checkout, expected_candidate_sha))
            != (FRONTEND_CONFIG_BASELINE_BLOB, FRONTEND_CONFIG_CANDIDATE_BLOB)):
        raise ValueError("Transition aggregate frontend config differs from reviewed history")
    report = {"product_anchor_sha": PRODUCT_ANCHOR_SHA, "product_anchor_tree": PRODUCT_ANCHOR_TREE,
              "candidate_sha": expected_candidate_sha, "descendant_commits": commits,
              "authorized_changed_paths": sorted(changed)}
    config = _bind_frontend_config(checkout, expected_candidate_sha)
    if config is not None:
        report["frontend_config"] = config
    if config_transition is not None:
        report["frontend_config_transition"] = config_transition
    return report


def _guard_code_binding(checkout: Path, expected_sha: str) -> dict[str, Any]:
    """Pin the running verifier closure to Git bytes, without a self hash constant."""
    running_root = Path(__file__).resolve().parents[2]
    if _git(running_root, "rev-parse", "HEAD").decode().strip() != expected_sha:
        raise ValueError("Running transition verifier HEAD differs from the explicit reviewed identity")
    entries = {}
    prefixes = ("scripts/deploy", "src", "data", "scripts/bilun", "scripts/sut")
    exact = ("scripts/__init__.py", "pyproject.toml", "requirements.txt")
    for record in _git(checkout, "ls-tree", "-r", "-z", expected_sha,
                       "--", *prefixes, *exact).split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        relative = os.fsdecode(name)
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Reviewed controller closure has a link or non-file")
        source = running_root / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError("Running transition verifier differs from reviewed Git tooling")
        before = _stable_file_hash(source)
        contents = source.read_bytes()
        if (hashlib.sha1(f"blob {len(contents)}\0".encode() + contents).hexdigest() != blob
                or _stable_file_hash(source) != before):
            raise ValueError("Running transition controller source/catalog bytes differ from reviewed Git")
        entries[relative] = _stable_file_hash(source)
    for prefix in prefixes:
        if (running_root / prefix).is_symlink():
            raise ValueError("Running transition controller root is a link")
        for source in (running_root / prefix).rglob("*"):
            if source.is_symlink():
                raise ValueError("Running transition controller has an unreviewed source link")
            if "__pycache__" in source.parts or source.suffix in {".md", ".pyc"} or source.is_dir():
                continue
            if source.relative_to(running_root).as_posix() not in entries:
                raise ValueError("Running transition verifier has an unreviewed Python/source closure")
    if "scripts/deploy/verify_clinical_semantic_transition.py" not in entries:
        raise ValueError("Reviewed tooling does not include this transition guard")
    binding = {"verifier_sha": expected_sha, "source_sha256": _digest(entries), "files": entries}
    config = _bind_frontend_config(running_root, expected_sha)
    if config is not None:
        # The signed transition includes this exact config binding. Keep it
        # separate from the existing Python/source verifier locator contract.
        binding["frontend_config"] = config
        binding["source_sha256"] = _digest({"files": entries, "frontend_config": config})
    return binding


def _replay_checkout_binding(roster: dict) -> dict[str, Any]:
    """Bind replay disk bytes to pinned Git blobs independently of the index."""
    checkout = Path(roster["checkout"])
    code_sha = roster["code_sha"]
    if (checkout.is_symlink() or not checkout.is_dir() or checkout != checkout.resolve(strict=True)
            or _git(checkout, "rev-parse", "HEAD").decode().strip() != code_sha):
        raise ValueError("Transition replay checkout differs from its pinned Git identity")
    rows = [row for row in roster["sources"] if row["label"].startswith("repo:")]
    sources = {row["label"][5:]: row for row in rows}
    if len(rows) != len(sources):
        raise ValueError("Transition replay roster repeats a Git source identity")
    entries = {}
    for record in _git(checkout, "ls-tree", "-r", "-z", code_sha,
                       "--", *_REPO_ROOTS, *_REPO_FILES).split(b"\0"):
        if not record:
            continue
        metadata, name = record.split(b"\t", 1)
        relative = os.fsdecode(name)
        if not _selected(relative):
            continue
        mode, kind, blob = metadata.decode().split()
        if kind != "blob" or mode not in {"100644", "100755"} or relative not in sources:
            raise ValueError("Transition replay roster differs from pinned Git sources")
        row = sources[relative]
        source = checkout / relative
        if (Path(row["path"]) != source or source.is_symlink() or not source.is_file()
                or source != source.resolve(strict=True) or source.stat().st_nlink != 1):
            raise ValueError("Transition replay Git source is not an independent canonical file")
        before = _stable_file_hash(source)
        contents = source.read_bytes()
        # Git's object identity hashes the blob header and exact contents. This
        # comparison never asks the index or its stat/assume-unchanged flags.
        if (hashlib.sha1(f"blob {len(contents)}\0".encode() + contents).hexdigest() != blob
                or before != row["sha256"] or len(contents) != row["size_bytes"]
                or _stable_file_hash(source) != before):
            raise ValueError("Transition replay source bytes differ from pinned Git objects")
        entries[relative] = before
    if not entries or set(entries) != set(sources):
        raise ValueError("Transition replay roster has an unknown or missing Git source")
    if _git(checkout, "rev-parse", "HEAD").decode().strip() != code_sha:
        raise ValueError("Transition replay checkout identity changed during Git binding")
    return {"code_sha": code_sha, "source_sha256": _digest(entries), "file_count": len(entries)}


_WORKER = r'''
import contextlib, json, sys
from pathlib import Path
with contextlib.redirect_stdout(sys.stderr):
    from src.bilun.domain.claims.loader import load_sut_claim_dataset
    from src.bilun.domain.claims.patient_context import build_patient_claim_context, build_bill_claim_context
    from src.bilun.domain.billing.claim_drug_indication import validate_drug_indication_from_claims
    from src.bilun.domain.billing.billing_actions import collect_billing_actions
    from src.bilun.domain.billing.types import BillingActionReport
    from src.bilun.domain.billing.drug_indication_findings import _route_evidence
    from src.bilun.domain.prose_rules import drug_indication as prose
    dataset = load_sut_claim_dataset(Path(sys.argv[1]), mode=sys.argv[2])
    rules = prose.list_drug_indication_rules()
    def project(ctx):
        review = validate_drug_indication_from_claims(ctx)
        report = BillingActionReport(patient_id=ctx.patient_id, drug_indication=review)
        predicates = {}
        for line in ctx.drug_lines:
            predicates[line.drug_claim_line_id] = {
                rule['rule_id']: prose._drug_name_matches(line.drug_name, rule.get('drug_names') or [])
                for rule in rules if rule['rule_id'] in {
                    '4.2.9.mds_esa_hematology_report', '4.2.9.mds_esa_initiation_hematology_report',
                    '4.2.9.A-2.darbepoetin_mds_source_review'}
            }
        return {'drug_indication': review.to_dict(), 'recommended_actions': [
            row for row in collect_billing_actions(report) if row.get('surface') == 'drug_indication'],
            'alias_predicates': predicates}
    patients, bills = {}, {}
    for pid in sorted(dataset.claims_by_patient):
        ctx = build_patient_claim_context(pid, dataset)
        if ctx is None:
            raise ValueError('Transition patient source context is absent')
        patients[pid] = project(ctx)
        for claim in ctx.claims:
            key = pid + '::' + claim.claim_id
            if key in bills:
                raise ValueError('Transition source repeats a bill')
            bills[key] = project(build_bill_claim_context(pid, claim.claim_id, dataset))
    root = Path.cwd().resolve()
    for name, module in tuple(sys.modules.items()):
        if name == 'src' or name.startswith('src.'):
            source = getattr(module, '__file__', None)
            if source and not Path(source).resolve().is_relative_to(root):
                raise ValueError('Transition imported source outside pinned checkout')
result = {'patients': patients, 'bills': bills, 'rules': {r['rule_id']: r for r in rules},
          'coverage_scope': prose.drug_indication_coverage_scope(),
          'source_routes': {r['rule_id']: _route_evidence([r])[0][0].to_dict() for r in rules}}
print(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
'''


def _replay_projection(checkout: Path, claims_dir: Path, mode: str, python_executable: Path,
                       *, roster: dict, dependency_roots: tuple[Path, ...]) -> dict:
    """Fresh, traced pure projection with a fixed nonsecret environment."""
    if not python_executable.is_absolute() or not python_executable.is_file() or not dependency_roots:
        raise ValueError("Transition replay needs an explicit existing runtime and dependency roots")
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC",
                   "PYTHONDONTWRITEBYTECODE": "1", "POLARS_MAX_THREADS": "1"}
    with tempfile.TemporaryDirectory(prefix="bilun-transition-") as directory:
        trace = Path(directory) / "replay.trace"
        command = ["strace", "-f", "-yy", "-s", "4096", "-e",
                   "trace=open,openat,openat2,clone,clone3,fork,vfork,exit_group,execve",
                   "-o", str(trace), str(python_executable), "-X",
                   f"pycache_prefix={directory}/bytecode", "-c", _WORKER, str(claims_dir), mode]
        result = subprocess.run(command, cwd=checkout, env=environment, capture_output=True,
                                timeout=600, check=False)
        if result.returncode:
            raise ValueError("Independent transition replay failed; no cache permission was issued")
        value = _parse_json(result.stdout.decode(), context="independent transition replay")
        if not isinstance(value, dict) or set(value) != {"patients", "bills", "rules", "coverage_scope", "source_routes"}:
            raise ValueError("Independent transition replay has an unknown contract")
        # .env has no useful suffix and can live above a worktree. Do not let
        # the general trace parser's OS-file tolerance hide credential reads.
        for line in trace.read_text().splitlines():
            if " = -1 " not in line and re.search(r"/(?:\.env|\.env\.[^/\"<>]*)[\"<>]", line):
                raise ValueError("Independent transition replay read an environment file")
        parsed = validate_runtime_read_trace(trace, roster=roster,
                    candidate_db=Path(directory) / "unused.duckdb", dependency_roots=dependency_roots)
        if parsed.get("trace_parse_ok") is not True:
            raise ValueError("Independent transition replay read closure is unverified")
        return value


@dataclass(frozen=True)
class ClinicalTransitionProof:
    _report_json: str
    _projections_json: str = field(repr=False)

    @property
    def report(self) -> dict:
        return json.loads(self._report_json)

    @property
    def projections(self) -> dict:
        return json.loads(self._projections_json)


def _without(value: Mapping, fields: frozenset[str]) -> dict:
    return {key: item for key, item in value.items() if key not in fields}


def _same(left: Any, right: Any, context: str) -> None:
    if _canonical(left) != _canonical(right):
        raise ValueError(f"Transition changes protected {context}")


def _routes(row: Mapping) -> dict[str, dict]:
    result = {}
    values = row.get("eligible_routes")
    if not isinstance(values, list):
        raise ValueError("Transition route inventory is malformed")
    for route in values:
        if not isinstance(route, dict) or not isinstance(route.get("rule_id"), str) or route["rule_id"] in result:
            raise ValueError("Transition repeats or omits a route identity")
        result[route["rule_id"]] = route
    return result


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


def _check_coverage_pair(old: Any, new: Any) -> None:
    if (_digest(old) != BASELINE_COVERAGE_SHA256 or _digest(new) != PRODUCT_COVERAGE_SHA256
            or not _changed_paths(old, new) <= COVERAGE_DELTA_PATHS):
        raise ValueError("Transition coverage metadata differs from the pinned source generators")


def _inventory_narrative(row: Mapping) -> str:
    """Independent reviewed mismatch prose; no eligibility decision is added."""
    codes, name = row.get("observed_icd10_codes"), row.get("drug_name")
    if (not isinstance(codes, list) or any(not isinstance(code, str) for code in codes)
            or not isinstance(name, str) or row.get("applicability_status") != "indication_mismatch"):
        raise ValueError("Transition narrative lacks its unchanged mismatch inputs")
    observed = ", ".join(codes) or "tanı kodu"
    eligible = ", ".join(code for route in row["eligible_routes"]
                        for code in [*route["icd10_codes"], *route["icd10_ranges"]]) or "kodlanmış tanı yolu"
    return (f"Faturada {observed} tanıları bulundu. {name} için kodlanmış SGK "
            f"geri ödeme yolları {eligible} tanılarını kapsıyor. Mevcut tanılar "
            "bu yollarla eşleşmiyor.")


def _inventory_delta(old: Mapping, new: Mapping, predicates: dict) -> None:
    before, after = _routes(old), _routes(new)
    if set(before) - set(after) != REMOVED_RULE_IDS or set(after) - set(before) != {ADDED_RULE_ID}:
        raise ValueError("Transition route inventory is not the reviewed alias retargeting")
    for key in REMOVED_RULE_IDS:
        if _digest(before[key]) != SOURCE_ROUTE_SHA256[key]:
            raise ValueError("Transition retired route differs from its reviewed source projection")
    if _digest(after[ADDED_RULE_ID]) != SOURCE_ROUTE_SHA256[ADDED_RULE_ID]:
        raise ValueError("Transition added route differs from its reviewed source projection")
    _same({key: before[key] for key in before.keys() & after.keys()},
          {key: after[key] for key in before.keys() & after.keys()}, "shared route objects")
    _same([row["rule_id"] for row in old["eligible_routes"] if row["rule_id"] in after],
          [row["rule_id"] for row in new["eligible_routes"] if row["rule_id"] in before], "shared route ordering")
    if (type(old.get("eligible_route_count")) is not int
            or type(new.get("eligible_route_count")) is not int
            or old["eligible_route_count"] != len(before)
            or new["eligible_route_count"] != len(after)
            or new["eligible_route_count"] != old["eligible_route_count"] - 1):
        raise ValueError("Transition route count does not follow the reviewed inventory")
    line = old.get("drug_claim_line_id")
    left, right = predicates["baseline"].get(line), predicates["candidate"].get(line)
    if (not isinstance(left, dict) or not isinstance(right, dict)
            or any(left.get(key) is not True or right.get(key) is not False for key in REMOVED_RULE_IDS)
            or right.get(ADDED_RULE_ID) is not True):
        raise ValueError("Transition does not match the independently replayed medicine alias predicates")


def _check_projection_pair(old: dict, new: dict) -> None:
    """A separate permission boundary, even when both replay outputs agree."""
    if set(old) != set(new) or set(old) != {"drug_indication", "recommended_actions", "alias_predicates"}:
        raise ValueError("Transition projection has an unknown ownership boundary")
    before, after = old["drug_indication"], new["drug_indication"]
    if not isinstance(before, dict) or not isinstance(after, dict) or before.keys() != after.keys():
        raise ValueError("Transition drug review shape differs")
    _check_coverage_pair(before.get("coverage_scope"), after.get("coverage_scope"))
    collections = {
        "evaluations": frozenset({"eligible_routes", "eligible_route_count"}),
        "findings": frozenset({"eligible_routes", "eligible_route_count", "explanation_tr"}),
        "violations": frozenset({"eligible_route_rule_ids", "eligible_route_count", "detail", "message", "message_tr"}),
    }
    _same(_without(before, frozenset({"coverage_scope", *collections})),
          _without(after, frozenset({"coverage_scope", *collections})), "drug review totals/status/inputs")
    predicates = {"baseline": old["alias_predicates"], "candidate": new["alias_predicates"]}
    changed_lines = set()
    changed_findings = {}
    for collection, allowed in collections.items():
        left, right = before.get(collection), after.get(collection)
        if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
            raise ValueError("Transition changes drug finding/evaluation inventory")
        for row, other in zip(left, right, strict=True):
            if not isinstance(row, dict) or not isinstance(other, dict):
                raise ValueError("Transition drug row is malformed")
            _same(_without(row, allowed), _without(other, allowed), "drug row identity/clinical/status/severity/money")
            if _canonical(row) == _canonical(other):
                continue
            if collection == "violations":
                left_ids, right_ids = row.get("eligible_route_rule_ids"), other.get("eligible_route_rule_ids")
                if (not isinstance(left_ids, list) or not isinstance(right_ids, list)
                        or len(set(left_ids)) != len(left_ids) or len(set(right_ids)) != len(right_ids)
                        or set(left_ids) - set(right_ids) != REMOVED_RULE_IDS
                        or set(right_ids) - set(left_ids) != {ADDED_RULE_ID}):
                    raise ValueError("Transition legacy route IDs differ from reviewed retargeting")
                if row.get("drug_claim_line_id") not in changed_lines:
                    raise ValueError("Transition legacy narrative lacks an independently verified route delta")
                finding, newer_finding = changed_findings[row["drug_claim_line_id"]]
                for item, authored in ((row, finding), (other, newer_finding)):
                    for key in ("detail", "message", "message_tr"):
                        _same(item.get(key), authored["explanation_tr"], "legacy inventory narrative")
                    _same(item.get("eligible_route_count"), authored["eligible_route_count"], "legacy route count")
                    _same(item.get("eligible_route_rule_ids"), [r["rule_id"] for r in authored["eligible_routes"]],
                          "legacy route ordering")
            else:
                # Diagnosis selection belongs to evaluations. Finding/action
                # projections retain their own shape and all clinical fields.
                if collection == "evaluations" and (
                    row.get("applicability_status") != "indication_mismatch"
                    or "selected_rule_id" not in row or row["selected_rule_id"] is not None
                ):
                    raise ValueError("Transition inventory must remain a nonselected indication mismatch")
                _inventory_delta(row, other, predicates)
                changed_lines.add(row["drug_claim_line_id"])
                if collection == "findings":
                    for item in (row, other):
                        _same(item.get("explanation_tr"), _inventory_narrative(item), "source-derived inventory narrative")
                    changed_findings[row["drug_claim_line_id"]] = (row, other)
    actions, newer = old["recommended_actions"], new["recommended_actions"]
    if not isinstance(actions, list) or not isinstance(newer, list) or len(actions) != len(newer):
        raise ValueError("Transition changes the drug action inventory")
    allowed = frozenset({"eligible_routes", "eligible_route_count", "detail", "sut_section_id"})
    for row, other in zip(actions, newer, strict=True):
        _same(_without(row, allowed), _without(other, allowed), "drug action identity/status/severity/amounts")
        if _canonical(row) != _canonical(other):
            _inventory_delta(row, other, predicates)
            if row.get("drug_claim_line_id") not in changed_lines:
                raise ValueError("Transition drug action lacks an independently verified finding")
            if row.get("drug_claim_line_id") not in changed_findings:
                raise ValueError("Transition drug action has no owned finding")
            finding, newer_finding = changed_findings[row["drug_claim_line_id"]]
            for item, authored in ((row, finding), (other, newer_finding)):
                _same(item.get("detail"), authored["explanation_tr"], "drug action inventory narrative")
                _same(item.get("sut_section_id"), next((r["sut_section"] for r in authored["eligible_routes"]
                                                       if r.get("sut_section")), None), "drug action source section")


def _source_intent(baseline: dict, candidate: dict, old: dict, new: dict) -> dict:
    import yaml

    for roster, sha, blob in ((baseline, BASELINE_CODE_SHA, BASELINE_SOURCE_BLOB),
                              (candidate, PRODUCT_ANCHOR_SHA, PRODUCT_SOURCE_BLOB)):
        checkout = Path(roster["checkout"])
        if _git(checkout, "rev-parse", f"{sha}:{SOURCE_PATH}").decode().strip() != blob:
            raise ValueError("Transition source-review intent blob differs")
    root = Path(candidate["checkout"])
    if _git(root, "rev-parse", f"{PRODUCT_ANCHOR_SHA}:{REVIEW_PACKET_PATH}").decode().strip() != REVIEW_PACKET_BLOB:
        raise ValueError("Transition independent source-review packet differs")
    reviewed = yaml.safe_load(_git(root, "show", f"{PRODUCT_ANCHOR_SHA}:{SOURCE_PATH}"))
    rules = {rule["rule_id"]: rule for rule in reviewed["rules"]}
    historical = yaml.safe_load(_git(Path(baseline["checkout"]), "show", f"{BASELINE_CODE_SHA}:{SOURCE_PATH}"))
    historical_rules = {rule["rule_id"]: rule for rule in historical["rules"]}
    quarantine = rules[ADDED_RULE_ID]
    if (quarantine.get("source_review_quarantine") is not True
            or quarantine.get("source_clinical_scope_incomplete") is not True
            or quarantine.get("source_review_change_date") != "2024-05-17"
            or quarantine.get("source_review_verified_through") != "2026-10-02"
            or quarantine.get("drug_names") != ["darbepoetin", "aranesp"]
            or quarantine.get("icd10_ranges") != ["D46", "D47"]):
        raise ValueError("Transition quarantine/source window differs from reviewed intent")
    for key in (*REMOVED_RULE_IDS, ADDED_RULE_ID):
        if key not in new["rules"]:
            raise ValueError("Transition candidate omits a reviewed source rule")
        for name, value in rules[key].items():
            _same(new["rules"][key].get(name), value, "compiled source-review rule")
    if any(key not in old["rules"] for key in REMOVED_RULE_IDS) or ADDED_RULE_ID in old["rules"]:
        raise ValueError("Transition baseline source rule inventory differs")
    for key in REMOVED_RULE_IDS:
        if key not in historical_rules:
            raise ValueError("Transition historical reviewed source omits a retired alias rule")
        for name, value in historical_rules[key].items():
            _same(old["rules"][key].get(name), value, "compiled historical source-review rule")
    return {"source_path": SOURCE_PATH, "baseline_blob": BASELINE_SOURCE_BLOB,
            "product_blob": PRODUCT_SOURCE_BLOB, "review_packet_blob": REVIEW_PACKET_BLOB,
            "review_window": ["2024-05-17", "2026-10-02"],
            "inventory_is_before_diagnosis": True, "clinical_eligibility_complete": False}


def verify_clinical_semantic_transition(
    *, baseline_roster: Path, candidate_roster: Path, baseline_meta: Mapping,
    candidate_meta: Mapping, same_input: Mapping, python_executable: Path,
    expected_candidate_sha: str, dependency_roots: tuple[Path, ...],
    expected_verifier_sha: str | None = None,
) -> ClinicalTransitionProof:
    if baseline_meta.get("code_sha") != BASELINE_CODE_SHA or candidate_meta.get("code_sha") != expected_candidate_sha:
        raise ValueError("Transition cache code identities differ from explicit reviewed identities")
    if (baseline_meta.get("source_hash") != BASELINE_SOURCE_HASH
            or baseline_meta.get("config_hash") != BASELINE_CONFIG_HASH):
        raise ValueError("Transition baseline source/config differs from the reviewed retained baseline")
    if (same_input.get("status") != "same_input_bytes_verified"
            or same_input.get("input_bytes_sha256") != INPUT_BYTES_SHA256
            or same_input.get("input_file_count") != 12
            or same_input.get("data_mode") != "synthetic_demo"):
        raise ValueError("Transition requires the exact reviewed same-input dataset")
    old_roster, old_data = _roster(baseline_roster, BASELINE_CODE_SHA)
    new_roster, new_data = _roster(candidate_roster, expected_candidate_sha)
    for label, roster_path, meta in (("baseline", baseline_roster, baseline_meta),
                                     ("candidate", candidate_roster, candidate_meta)):
        expected = {"roster_sha256": _stable_file_hash(roster_path),
                    "source_hash": meta["source_hash"], "config_hash": meta["config_hash"]}
        _same(same_input.get(label), expected, "source/config/input binding")
    history = _verify_candidate_history(Path(new_roster["checkout"]), expected_candidate_sha)
    verifier_sha = expected_verifier_sha or expected_candidate_sha
    verifier_checkout = Path(__file__).resolve().parents[2]
    if verifier_sha != expected_candidate_sha:
        _verify_candidate_history(verifier_checkout, verifier_sha)
    binding = _guard_code_binding(verifier_checkout, verifier_sha)
    replay_rosters = {"baseline": old_roster, "candidate": new_roster}
    replay_bindings = {side: _replay_checkout_binding(roster) for side, roster in replay_rosters.items()}
    projections = {}
    for label, roster, data in (("baseline", old_roster, old_data), ("candidate", new_roster, new_data)):
        claims = Path(next(row["path"] for name, row in data.items() if name.startswith("claim:"))).parent
        projections[label] = _replay_projection(Path(roster["checkout"]), claims, roster["data_mode"],
                    python_executable, roster=roster, dependency_roots=dependency_roots)
        for side, bound_roster in replay_rosters.items():
            _same(_replay_checkout_binding(bound_roster), replay_bindings[side], "post-replay pinned Git source bytes")
    intent = _source_intent(old_roster, new_roster, projections["baseline"], projections["candidate"])
    _check_coverage_pair(projections["baseline"]["coverage_scope"], projections["candidate"]["coverage_scope"])
    for side, projected in projections.items():
        for key, route in projected["source_routes"].items():
            if key in SOURCE_ROUTE_SHA256 and _digest(route) != SOURCE_ROUTE_SHA256[key]:
                raise ValueError("Transition source route generator differs from reviewed source intent")
    for collection in ("patients", "bills"):
        left, right = projections["baseline"][collection], projections["candidate"][collection]
        if not left or left.keys() != right.keys():
            raise ValueError("Transition replay patient/bill inventory differs")
        for key in left:
            _same(left[key]["drug_indication"]["coverage_scope"], projections["baseline"]["coverage_scope"],
                  "independent baseline coverage generator")
            _same(right[key]["drug_indication"]["coverage_scope"], projections["candidate"]["coverage_scope"],
                  "independent candidate coverage generator")
            _check_projection_pair(left[key], right[key])
    if _roster(baseline_roster, BASELINE_CODE_SHA)[0] != old_roster or _roster(candidate_roster, expected_candidate_sha)[0] != new_roster:
        raise ValueError("Transition source bytes changed during independent replay")
    for side, roster in replay_rosters.items():
        _same(_replay_checkout_binding(roster), replay_bindings[side], "final pinned Git source bytes")
    _same(_verify_candidate_history(Path(new_roster["checkout"]), expected_candidate_sha), history,
          "final candidate history/config binding")
    _same(_guard_code_binding(verifier_checkout, verifier_sha), binding, "verifier source binding")
    identity = {"contract": TRANSITION_CONTRACT, "baseline_code_sha": BASELINE_CODE_SHA,
                "candidate_code_sha": expected_candidate_sha, "history": history,
                "verifier": binding, "replay_checkouts": replay_bindings,
                "same_input": dict(same_input), "source_intent": intent,
                "baseline_replay_sha256": _digest(projections["baseline"]),
                "candidate_replay_sha256": _digest(projections["candidate"])}
    report = {"status": "clinical_semantic_transition_verified", **identity,
              "transition_sha256": _digest(identity),
              "patient_count": len(projections["baseline"]["patients"]),
              "bill_count": len(projections["baseline"]["bills"]),
              "protected_clinical_status_identity_money": "type_exact_unchanged"}
    return ClinicalTransitionProof(_canonical(report), _canonical(projections))


def normalize_transition_content(table: str, value: Any, *, side: str,
                                 proof: ClinicalTransitionProof, patient_reports: dict | None = None) -> Any:
    """Validate each cache against its own replay before normalizing ownership."""
    if (not isinstance(proof, ClinicalTransitionProof) or side not in {"baseline", "candidate"}
            or proof.report.get("status") != "clinical_semantic_transition_verified"
            or proof.report.get("contract") != TRANSITION_CONTRACT):
        raise ValueError("Transition content lacks a verified bound proof")
    if table in _REPORT_TABLES:
        scopes = proof.projections
        owned = scopes[side][_REPORT_TABLES[table]]
        baseline = scopes["baseline"][_REPORT_TABLES[table]]
        if not isinstance(value, dict) or value.keys() != owned.keys():
            raise ValueError("Transition cache report inventory differs from pinned inputs")
        output = json.loads(_canonical(value))
        for key, report in value.items():
            expected = owned[key]
            _same(report.get("drug_indication"), expected["drug_indication"], "cached drug producer replay")
            actions = report.get("recommended_actions")
            if not isinstance(actions, list) or any(not isinstance(row, dict) for row in actions):
                raise ValueError("Transition cached action inventory is malformed")
            drug = [row for row in actions if row.get("surface") == "drug_indication"]
            _same(drug, expected["recommended_actions"], "cached drug action producer replay")
            if side == "candidate":
                output[key]["drug_indication"] = baseline[key]["drug_indication"]
                previous = iter(baseline[key]["recommended_actions"])
                output[key]["recommended_actions"] = [next(previous) if row.get("surface") == "drug_indication" else row
                                                       for row in actions]
        return output
    if table == "cohort_compliance_index":
        from src.bilun.domain.billing.cohort_compliance import build_cohort_compliance_index
        if patient_reports is None or not isinstance(value, dict):
            raise ValueError("Transition cohort requires its complete owned patient reports")
        expected = build_cohort_compliance_index(patient_reports)
        _same(_without(value, frozenset({"data_source"})), expected, "cached cohort producer replay")
        normalized = normalize_transition_content("patient_billing_report_rows", patient_reports, side=side, proof=proof)
        return {**build_cohort_compliance_index(normalized),
                **({"data_source": value["data_source"]} if "data_source" in value else {})}
    return value


def _http_report_scopes(reports: dict[str, dict]) -> tuple[dict, dict]:
    """Decode the complete HTTP inventory without changing report contents."""
    if not isinstance(reports, dict):
        raise ValueError("Transition HTTP report inventory is malformed")
    scopes = {"patient_billing_report_rows": {}, "patient_bill_billing_report_rows": {}}
    identities = {}
    for path, report in reports.items():
        if not isinstance(path, str) or not isinstance(report, dict):
            raise ValueError("Transition HTTP report inventory is malformed")
        matched = re.fullmatch(r"/api/billing-report/([^/]+)(?:/bills/([^/]+))?", path)
        if not matched:
            raise ValueError("Transition HTTP report has an unknown ownership path")
        patient, bill = (unquote(value) if value is not None else None for value in matched.groups())
        table = "patient_billing_report_rows" if bill is None else "patient_bill_billing_report_rows"
        key = patient if bill is None else patient + "::" + bill
        if key in scopes[table]:
            raise ValueError("Transition HTTP report repeats a source identity")
        scopes[table][key] = report
        identities[path] = (table, key)
    return scopes, identities


def normalize_transition_http_reports(reports: dict[str, dict], *, side: str,
                                      proof: ClinicalTransitionProof,
                                      transport: Any, baseline_transport: Any,
                                      view: str = "draft") -> dict[str, dict]:
    """Bind wire DTOs to their own source model before normalizing ownership.

    The independently pinned serializer may add model defaults to raw cache
    rows. They are validated as that source's exact transport output, never
    stripped heuristically or accepted by the raw producer-replay normalizer.
    """
    from scripts.deploy.rehearse_wavea_same_port import PinnedReportTransport
    from scripts.deploy.verify_candidate_semantics import _legacy_report

    if (not isinstance(proof, ClinicalTransitionProof)
            or proof.report.get("status") != "clinical_semantic_transition_verified"
            or proof.report.get("contract") != TRANSITION_CONTRACT
            or side not in {"baseline", "candidate"} or view not in {"draft", "legacy"}):
        raise ValueError("Transition HTTP content lacks a verified bound proof or view")
    for label, package in (("baseline", baseline_transport), (side, transport)):
        expected_sha = proof.report.get(label + "_code_sha")
        if (not isinstance(package, PinnedReportTransport)
                or not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha)
                or package.code_sha != expected_sha or package.contract != "wavea-evidence-v2"):
            raise ValueError("Transition HTTP transport differs from pinned source identity")
        package.validate()
        raw_scopes, _ = _http_report_scopes(package.raw_reports)
        for table, raw in raw_scopes.items():
            # Preserve strict raw semantics. Even a self-consistent transport
            # cannot authorize raw clinical fields absent from the fresh proof.
            normalize_transition_content(table, raw, side=label, proof=proof)

    def projected(package: Any) -> dict[str, dict]:
        return (package.draft_reports if view == "draft" else
                {path: _legacy_report(row) for path, row in package.complete_reports.items()})

    expected = projected(transport)
    baseline = projected(baseline_transport)
    scopes, identities = _http_report_scopes(reports)
    expected_scopes, _ = _http_report_scopes(expected)
    baseline_scopes, _ = _http_report_scopes(baseline)
    _same(reports, expected, "HTTP pinned serializer/model projection")
    projections = proof.projections
    for table, family in _REPORT_TABLES.items():
        if (scopes[table].keys() != projections[side][family].keys()
                or baseline_scopes[table].keys() != projections["baseline"][family].keys()):
            raise ValueError("Transition HTTP report inventory differs from pinned inputs")
    output = json.loads(_canonical(reports))
    for path, (table, key) in identities.items():
        row = expected_scopes[table][key]
        old = baseline_scopes[table][key]
        actions = row.get("recommended_actions")
        old_actions = old.get("recommended_actions")
        if (not isinstance(row.get("drug_indication"), dict)
                or not isinstance(old.get("drug_indication"), dict)
                or not isinstance(actions, list) or not isinstance(old_actions, list)
                or any(not isinstance(action, dict) for action in (*actions, *old_actions))):
            raise ValueError("Transition HTTP transport drug/action projection is malformed")
        drug = [action for action in actions if action.get("surface") == "drug_indication"]
        old_drug = [action for action in old_actions if action.get("surface") == "drug_indication"]
        if len(drug) != len(old_drug):
            raise ValueError("Transition HTTP transport action ownership differs")
        if side == "candidate":
            output[path]["drug_indication"] = old["drug_indication"]
            replacements = iter(old_drug)
            output[path]["recommended_actions"] = [
                next(replacements) if action.get("surface") == "drug_indication" else action
                for action in actions
            ]
    return output
