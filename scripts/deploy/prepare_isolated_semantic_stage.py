"""Build and measure private own-source caches without issuing release authority.

The root coordinator supplies an already checkpointed, independently captured
serving snapshot. This helper never opens the serving database or changes a
service, frontend, receipt, historical profile or source checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import signal
import stat
import subprocess
from pathlib import Path
from typing import Any

import duckdb

from scripts.deploy.build_traced_candidate import build_traced_candidate
from scripts.deploy.generate_candidate_source_roster import generate_source_roster
from scripts.deploy.verify_candidate_cache import (
    _candidate_db_hash,
    _parse_json,
    _stable_file_hash,
    verify_candidate_cache,
)
from scripts.deploy import verify_candidate_semantics as cache
from scripts.deploy import verify_final_source_refresh_transition as replay
from scripts.deploy.verify_same_input import normalize_attested_data_source, verify_same_input_rosters
from scripts.deploy.verify_traced_build_attestation import verify_traced_build_attestation

_FIELDS = frozenset({
    "approved_parent", "stage_root", "serving_snapshot", "serving_snapshot_sha256",
    "serving_build_id", "baseline", "candidate", "python", "dependency_roots",
    "address_space_mib", "wall_seconds",
})
_SIDE_FIELDS = frozenset({"checkout", "code_sha", "claims_dir", "clean_dir"})
_CONFIG = {key: "" for key in (
    "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
    "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
)}


def _path(value: Any, *, existing: bool = True, executable: bool = False) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Stage path is malformed")
    path = Path(value)
    canonical = path.parent == path.parent.resolve(strict=True) if executable else path == path.resolve(strict=existing)
    if not path.is_absolute() or ".." in path.parts or not canonical:
        raise ValueError("Stage path must be canonical and independent")
    return path


def validate_stage_spec(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("Stage manifest fields differ")
    spec = dict(value)
    for name in ("approved_parent", "serving_snapshot"):
        spec[name] = _path(spec[name])
    spec["python"] = _path(spec["python"], executable=True)
    spec["stage_root"] = _path(spec["stage_root"], existing=False)
    parent, stage = spec["approved_parent"], spec["stage_root"]
    if (not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077
            or stage.parent != parent or stage.exists() or stage.is_symlink()):
        raise ValueError("Stage must be one absent direct child of the approved private parent")
    if (not isinstance(spec["serving_build_id"], str) or not spec["serving_build_id"]
            or not isinstance(spec["serving_snapshot_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", spec["serving_snapshot_sha256"])):
        raise ValueError("Serving snapshot expectations are malformed")
    if not isinstance(spec["dependency_roots"], list) or not spec["dependency_roots"]:
        raise ValueError("Explicit dependency roots are required")
    spec["dependency_roots"] = tuple(_path(item) for item in spec["dependency_roots"])
    if len(set(spec["dependency_roots"])) != len(spec["dependency_roots"]):
        raise ValueError("Dependency roots are duplicated")
    protected = [spec["serving_snapshot"], spec["python"], *spec["dependency_roots"]]
    for side in ("baseline", "candidate"):
        row = spec[side]
        if (not isinstance(row, dict) or set(row) != _SIDE_FIELDS
                or not isinstance(row["code_sha"], str)
                or not re.fullmatch(r"[0-9a-f]{40}", row["code_sha"])):
            raise ValueError("Stage side identity is malformed")
        spec[side] = {key: _path(item) if key != "code_sha" else item for key, item in row.items()}
        protected.extend(spec[side][key] for key in ("checkout", "claims_dir", "clean_dir"))
    if spec["baseline"]["checkout"] == spec["candidate"]["checkout"]:
        raise ValueError("Own-source sides must use independent checkouts")
    if any(stage == path or stage.is_relative_to(path) or path.is_relative_to(stage) for path in protected):
        raise ValueError("Stage overlaps protected inputs or runtime")
    if any(type(spec[key]) is not int or not low <= spec[key] <= high for key, low, high in (
        ("address_space_mib", 1024, 16384), ("wall_seconds", 60, 3600),
    )):
        raise ValueError("Stage resource bounds are invalid")
    if (not spec["python"].is_file()
            or _candidate_db_hash(spec["serving_snapshot"]) != spec["serving_snapshot_sha256"]):
        raise ValueError("Serving snapshot or interpreter identity differs")
    with duckdb.connect(str(spec["serving_snapshot"]), read_only=True) as connection:
        old_meta = cache._build_metadata(connection, spec["serving_build_id"])
    if old_meta["code_sha"] != spec["baseline"]["code_sha"]:
        raise ValueError("Fresh old build must use the actual serving cache source commit")
    return spec


def _save(path: Path, value: dict[str, Any]) -> None:
    body = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def verify_own_source_tables(
    database: Path, build_id: str, projection: dict[str, Any],
) -> dict[str, str]:
    """Require every selected cache table to equal its own independent replay."""
    if (not isinstance(projection, dict) or not isinstance(projection.get("tables"), dict)
            or set(projection["tables"]) != replay._TABLES or len(replay._TABLES) != 19):
        raise ValueError("Own-source replay must contain exactly all nineteen tables")
    before = _candidate_db_hash(database)
    digests = {}
    with duckdb.connect(str(database), read_only=True) as connection:
        if cache._baseline_contract(connection, build_id) != cache.FULL_EVIDENCE_SCHEMA_VERSION:
            raise ValueError("Own-source cache is not the full evidence schema")
        cache._check_evidence(connection, build_id,
            cache._payload_rows(connection, "patient_billing_report_rows", build_id), None)
        for table in sorted(replay._TABLES):
            if table in cache._ROW_TABLES:
                actual = cache._legacy_row_table(connection, table, build_id)
            elif table in (*cache._SINGLETON_TABLES, "cohort_compliance_index", "wavea_evidence_index"):
                actual = cache._singleton(connection, table, build_id)
            else:
                actual = cache._payload_rows(connection, table, build_id)
            if table in cache._EVIDENCE_TABLES:
                rows = {"index": actual} if table == "wavea_evidence_index" else actual
                if any(row.get("build_id") != build_id for row in rows.values()):
                    raise ValueError("Own-source evidence build identity differs")
            actual = replay._without_build_ids(table, actual)
            replay._same(actual, projection["tables"][table], "own-source exact " + table)
            digests[table] = replay._digest(actual)
    if _candidate_db_hash(database) != before:
        raise ValueError("Own-source cache changed during comparison")
    return digests


def delta_classes(baseline: Any, candidate: Any) -> dict[str, int]:
    """Count typed differences without exporting paths, identities or raw values."""
    counts: dict[str, int] = {}

    def add(name: str, count: int = 1) -> None:
        counts[name] = counts.get(name, 0) + count

    def visit(old: Any, new: Any) -> None:
        if replay._canonical(old) == replay._canonical(new):
            return
        if old is None or new is None:
            add("nullability_changed")
        elif type(old) is not type(new):
            add("value_type_changed")
        elif isinstance(old, dict):
            if old.keys() != new.keys():
                add("mapping_keys_changed", len(old.keys() ^ new.keys()))
            for key in old.keys() & new.keys():
                visit(old[key], new[key])
        elif isinstance(old, list):
            if len(old) != len(new):
                add("sequence_length_changed")
            for left, right in zip(old, new):
                visit(left, right)
        elif isinstance(old, bool):
            add("boolean_changed")
        elif isinstance(old, (int, float)):
            add("known_number_changed")
        elif isinstance(old, str):
            add("string_changed")
        else:
            raise ValueError("Own-source delta contains an unsupported value type")

    visit(baseline, candidate)
    return counts


def prepare_isolated_stage(spec: dict[str, Any]) -> dict[str, Any]:
    """Produce actual traced builds and exact own-source evidence, never a receipt."""
    spec = validate_stage_spec(spec)
    replay._snapshot_runtime_files()
    replay._snapshot_runtime_resources()
    stage = spec["stage_root"]
    stage.mkdir(mode=0o700)
    snapshot_sha = _candidate_db_hash(spec["serving_snapshot"])
    rosters, results, projections, metadata, schemas = {}, {}, {}, {}, {}
    for side in ("baseline", "candidate"):
        row = spec[side]
        work = stage / side
        work.mkdir(mode=0o700)
        roster_path = work / "source-roster.json"
        rosters[side] = generate_source_roster(**row, data_mode="synthetic_demo")
        _save(roster_path, rosters[side])
        common = dict(**row, data_mode="synthetic_demo", python_executable=spec["python"],
                      dependency_roots=spec["dependency_roots"], payload_workers=1, billing_workers=1)
        build = build_traced_candidate(**common, roster_path=roster_path,
                    db_path=work / "cache.duckdb", trace_path=work / "build.trace",
                    log_path=work / "build.log", report_path=work / "traced-build.json")
        structural = verify_candidate_cache(work / "cache.duckdb", build_id=build["build_id"],
                    code_sha=row["code_sha"], input_manifest=roster_path)
        attestation = verify_traced_build_attestation(**common, record_path=work / "traced-build.json",
                    source_roster_path=roster_path, cache_path=work / "cache.duckdb",
                    trace_path=work / "build.trace", log_path=work / "build.log")
        _save(work / "structural.json", structural)
        _save(work / "trace-attestation.json", attestation)
        projections[side] = replay._replay_projection(
            row["checkout"], row["claims_dir"], row["clean_dir"], "synthetic_demo", spec["python"],
            roster=rosters[side], dependency_roots=spec["dependency_roots"])
        results[side] = {"build_id": build["build_id"], "code_sha": row["code_sha"],
            "cache_sha256": _candidate_db_hash(work / "cache.duckdb"),
            "own_source_table_digests": verify_own_source_tables(
                work / "cache.duckdb", build["build_id"], projections[side])}
        with duckdb.connect(str(work / "cache.duckdb"), read_only=True) as connection:
            metadata[side] = cache._build_metadata(connection, build["build_id"])
            schemas[side] = {table: connection.execute(f"PRAGMA table_info('{table}')").fetchall()
                             for table in sorted(replay._TABLES)}
        for name in results:
            if generate_source_roster(**spec[name], data_mode="synthetic_demo") != rosters[name]:
                raise ValueError("Protected source bytes changed during stage")
        if _candidate_db_hash(spec["serving_snapshot"]) != snapshot_sha:
            raise ValueError("Serving snapshot changed during stage")
    replay._same(schemas["baseline"], schemas["candidate"], "nineteen table physical schemas")
    same_input = verify_same_input_rosters(
        stage / "baseline/source-roster.json", stage / "candidate/source-roster.json",
        baseline_meta=metadata["baseline"], candidate_meta=metadata["candidate"],
        build_config_environment=_CONFIG, baseline_build_config_environment=_CONFIG)
    bridge = cache.verify_serving_baseline_equivalence(
        spec["serving_snapshot"], serving_build_id=spec["serving_build_id"],
        baseline_db=stage / "baseline/cache.duckdb", baseline_build_id=results["baseline"]["build_id"])
    _save(stage / "baseline-bridge.json", bridge)
    deltas = {}
    for table in sorted(replay._TABLES):
        values = [normalize_attested_data_source(projections[side]["tables"][table],
                  same_input["paths"][side]) for side in ("baseline", "candidate")]
        if table in cache._ROW_TABLES:
            values = [sorted(value, key=replay._digest) for value in values]
        counts = delta_classes(*values)
        if counts:
            deltas[table] = counts
    result = {"schema_version": "bilun-isolated-own-source-stage-v1",
        "status": "isolated_own_source_stage_verified", "deployment_admitted": False,
        "release_ready": False, "baseline_bridge_status": bridge["status"],
        "sides": results, "same_input": same_input, "table_delta_classes": deltas,
        "pending": ["reviewed_measured_delta_contract", "frozen_source_product_tooling_profile",
                    "paired_http_ui_rehearsal", "exact_current_main_push_ci", "signed_receipt"]}
    if _candidate_db_hash(spec["serving_snapshot"]) != snapshot_sha:
        raise ValueError("Serving snapshot changed after bridge")
    _save(stage / "stage-report.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    from src.bilun.api.wavea_activation import _private_file
    try:
        _private_file(args.manifest)
        manifest_sha = _stable_file_hash(args.manifest)
        raw = _parse_json(args.manifest.read_text(), context="stage manifest")
        spec = validate_stage_spec(raw)
        if not args.worker:
            command = [str(Path(os.sys.executable)), "-B", "-m",
                       "scripts.deploy.prepare_isolated_semantic_stage",
                       "--manifest", str(args.manifest), "--worker"]
            with subprocess.Popen(command, cwd=Path(__file__).resolve().parents[2],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  start_new_session=True) as worker:
                try:
                    output, _ = worker.communicate(timeout=spec["wall_seconds"])
                except subprocess.TimeoutExpired:
                    os.killpg(worker.pid, signal.SIGTERM)
                    try:
                        worker.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(worker.pid, signal.SIGKILL)
                        worker.communicate()
                    raise TimeoutError from None
                finally:
                    try:
                        os.killpg(worker.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if worker.returncode:
                    raise ValueError("Isolated stage worker failed")
            result = _parse_json(output.decode(), context="stage worker result")
        else:
            resource.setrlimit(resource.RLIMIT_AS, (spec["address_space_mib"] * 1024 ** 2,) * 2)
            result = prepare_isolated_stage(raw)
        if _stable_file_hash(args.manifest) != manifest_sha:
            raise ValueError("Stage manifest changed")
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "isolated_stage_failed", "error_type": type(exc).__name__,
                          "deployment_admitted": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
