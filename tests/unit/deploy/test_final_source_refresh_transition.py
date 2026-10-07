"""Independent public fixtures for the explicit 499 to final 3d29 profile.

These tests use authored public projections and synthetic Git histories. They
do not read retained patient caches or issue a production admission receipt.
The wrapper tests replace only the strace child; Git and read-trace gates run.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import zlib
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scripts.deploy import verify_final_source_refresh_transition as final
from scripts.deploy import verify_source_refresh_transition as frozen
from scripts.deploy import issue_wavea_activation as issuer
from scripts.deploy import prepare_single_vps_release as preparation
from scripts.deploy import rehearse_wavea_same_port as rehearsal
from scripts.deploy import verify_candidate_semantics as semantics
from scripts.deploy.verify_private_rehearsal import verify_private_rehearsal
from tests.integration.deploy import test_signed_transition_startup as signed_startup
from tests.integration.deploy.test_signed_transition_startup import signed_bundle as signed_bundle
from tests.unit.deploy.test_issue_wavea_activation import _issuer_transition_fixture
from tests.unit.deploy.test_prepare_single_vps_release import machine as machine
from tests.unit.deploy.test_same_port_rehearsal import (
    fabricated_transport, fixture_rehearsal, private_json, sealed_rehearsal,
)
from tests.unit.deploy.test_verify_candidate_semantics import _current_fixture
from tests.unit.deploy.test_source_refresh_transition import (
    _git,
    _public_projection_pair,
    _report as _old_report,
    source_projection_wrapper_case as source_projection_wrapper_case,
)

# Deliberately authored here rather than obtained from the verifier inventory.
TABLES = (
    "patient_billing_report_rows", "patient_detail_cache", "patient_outcome_base",
    "patient_bill_billing_report_rows", "cohort_compliance_index",
    "cohort_optimization_summary", "patient_alerts_summary", "cohort_recovery_summary",
    "cohort_sut_summary", "validation_payload", "patient_meta", "cohort_sut_exposure",
    "patient_alerts_payload", "patient_diagnoses", "patient_alert_rows",
    "patient_billing_reports", "wavea_evidence_detail", "wavea_bill_evidence_detail",
    "wavea_evidence_index",
)
STRICT_TABLES = (
    "patient_detail_cache", "patient_outcome_base", "cohort_optimization_summary",
    "patient_alerts_summary", "cohort_recovery_summary", "cohort_sut_summary",
    "validation_payload", "patient_meta", "cohort_sut_exposure", "patient_alerts_payload",
    "patient_diagnoses", "patient_alert_rows", "patient_billing_reports",
)
OWNED_TABLES = (
    "patient_billing_report_rows", "patient_bill_billing_report_rows",
    "wavea_evidence_detail", "wavea_bill_evidence_detail", "wavea_evidence_index",
    "cohort_compliance_index",
)
CONTRACT = "bilun-source-refresh-499-3d29-v1"
PUBLIC_SCOPE = "/user.slice/user-0.slice/session-900.scope"
PUBLIC_REGULAR_FILES = (
    "/etc/locale.alias", "/opt/Bilun/.venv/pyvenv.cfg", "/etc/nsswitch.conf",
    "/etc/passwd", "/etc/ssl/openssl.cnf",
)
PUBLIC_KERNEL_PATHS = {
    "transparent_hugepage_enabled": "/sys/kernel/mm/transparent_hugepage/enabled",
    "user_slice_cpu_max": "/sys/fs/cgroup/user.slice/cpu.max",
    "root_user_slice_cpu_max": "/sys/fs/cgroup/user.slice/user-0.slice/cpu.max",
    "own_session_cpu_max": "/sys/fs/cgroup" + PUBLIC_SCOPE + "/cpu.max",
    "own_session_memory_max": "/sys/fs/cgroup" + PUBLIC_SCOPE + "/memory.max",
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _public_descriptor(path, *, kernel=False, number=1, body=b"public bytes"):
    value = {"path": path, "file_type": "kernel_resource" if kernel else "regular_file",
        "uid": 0, "gid": 0, "mode": 0o644, "size_bytes": 0 if kernel else len(body),
        "device": 1, "inode": number, "nlink": 1, "mtime_ns": 100, "ctime_ns": 100,
        "sha256": hashlib.sha256(body).hexdigest()}
    if kernel:
        value["read_byte_count"] = len(body)
    return value


def _public_runtime_resources():
    return {"membership": {"descriptor": _public_descriptor("/proc/800/cgroup", kernel=True,
        body=("0::" + PUBLIC_SCOPE + "\n").encode()), "scope": PUBLIC_SCOPE},
        "kernel_files": {label: _public_descriptor(path, kernel=True, number=index + 2,
            body=b"max 100000\n") for index, (label, path) in enumerate(PUBLIC_KERNEL_PATHS.items())}}


def _request(sha="a" * 40):
    return {"contract": CONTRACT, "expected_candidate_sha": sha, "expected_verifier_sha": sha}


def _commit(checkout, message):
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-q", "-m", message)
    return _git(checkout, "rev-parse", "HEAD")


def test_final_request_is_explicit_and_old_profiles_remain_separate():
    assert final.validate_transition_request(None) is None
    assert final.validate_transition_request(_request()) == _request()
    old = {"contract": frozen.TRANSITION_CONTRACT,
           "expected_candidate_sha": "b" * 40, "expected_verifier_sha": "b" * 40}
    assert final.validate_transition_request(old) == frozen.validate_transition_request(old)
    with pytest.raises(ValueError):
        frozen.validate_transition_request(_request())
    assert final.PRODUCT_ANCHOR_SHA == "3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e"
    assert frozen.PRODUCT_ANCHOR_SHA == "d0337600f45a17aa635f6bbe8d584095a6f3e82e"


@pytest.mark.parametrize("mutation", [
    "unknown", "partial", "extra", "candidate_none", "candidate_short", "verifier_wrong",
    "candidate_upper", "candidate_bool", "verifier_none",
])
def test_request_rejects_unknown_partial_or_unbound_pins(mutation):
    request = _request()
    if mutation == "unknown":
        request["contract"] = "future-unreviewed-profile"
    elif mutation == "partial":
        request.pop("expected_verifier_sha")
    elif mutation == "extra":
        request["future_permission"] = True
    elif mutation == "candidate_none":
        request["expected_candidate_sha"] = None
    elif mutation == "candidate_short":
        request["expected_candidate_sha"] = "a" * 39
    elif mutation == "candidate_upper":
        request["expected_candidate_sha"] = "A" * 40
    elif mutation == "candidate_bool":
        request["expected_candidate_sha"] = True
    elif mutation == "verifier_none":
        request["expected_verifier_sha"] = None
    else:
        request["expected_verifier_sha"] = "b" * 40
    with pytest.raises(ValueError):
        final.validate_transition_request(request)


@pytest.mark.parametrize("table", TABLES)
def test_no_opt_in_keeps_every_table_type_exact_and_detached(table):
    value = {"money": 0.0, "null": None, "flag": False, "order": ["b", "a"],
             "selected_rule_id": "public.unrelated", "data_source": {"mode": "synthetic_demo"}}
    before = copy.deepcopy(value)
    with pytest.raises(ValueError):
        final.normalize_transition_content(table, value, side="candidate", proof=None)
    assert value == before


@pytest.fixture
def final_wrapper(source_projection_wrapper_case, monkeypatch):
    case = source_projection_wrapper_case
    # The child response is public; the real wrapper must require the new key.
    case["output"] = {**copy.deepcopy(case["expected"]), "source_witnesses": {}}
    case["expected"] = copy.deepcopy(case["output"])
    original_validator = final.validate_runtime_read_trace
    child_spy = final.subprocess.run
    case["trace_transform"] = None
    case["runtime_snapshots"] = []
    case["runtime_snapshot_mutation"] = None
    case["os_bindings"] = {literal: _public_descriptor(literal, number=index + 1)
                           for index, literal in enumerate(PUBLIC_REGULAR_FILES)}
    case["resource_bindings"] = _public_runtime_resources()
    case["resource_snapshots"] = []
    case["resource_snapshot_mutation"] = None
    case["complete_trace_transform"] = None

    def snapshot():
        # A metadata seam for these VPS-only paths; descriptor behavior has
        # separate public-file tests below. This is not a VPS observation.
        value = copy.deepcopy(case["os_bindings"])
        if case["runtime_snapshots"] and case["runtime_snapshot_mutation"] is not None:
            field, replacement = case["runtime_snapshot_mutation"]
            value["/etc/locale.alias"][field] = replacement
        case["runtime_snapshots"].append(value)
        return value

    def resources(expected_membership=None):
        value = copy.deepcopy(case["resource_bindings"])
        if case["resource_snapshots"] and case["resource_snapshot_mutation"] is not None:
            target, field, replacement = case["resource_snapshot_mutation"]
            descriptor = value["membership"]["descriptor"] if target == "membership" else value["kernel_files"][target]
            descriptor[field] = replacement
        case["resource_snapshots"].append((copy.deepcopy(expected_membership), copy.deepcopy(value)))
        return value

    def run(command, **kwargs):
        result = child_spy(command, **kwargs)
        if command[0] == "strace":
            trace = Path(command[command.index("-o") + 1])
            value = trace.read_text()
            if case["trace_transform"] is not None:
                value = case["trace_transform"](value)
            lines = value.splitlines()
            # Public process IDs, not observations of the coordinator or VPS.
            # The child double emits a complete parent/clone/exit lifecycle.
            complete = ["700 clone(child_stack=NULL, flags=CLONE_VM) = 701",
                *["700 " + line for line in lines[:-1]], "701 +++ exited with 0 +++",
                "700 " + lines[-1]]
            value = "\n".join(complete) + "\n"
            if case["complete_trace_transform"] is not None:
                value = case["complete_trace_transform"](value)
            trace.write_text(value, encoding="utf-8")
        return result

    def validate(trace, **kwargs):
        case["trace_calls"].append(kwargs.copy())
        return original_validator(trace, **kwargs)

    monkeypatch.setattr(final, "validate_runtime_read_trace", validate)
    monkeypatch.setattr(final.subprocess, "run", run)
    monkeypatch.setattr(final, "_snapshot_runtime_files", snapshot)
    monkeypatch.setattr(final, "_snapshot_runtime_resources", resources)
    monkeypatch.setattr(final.os, "getpid", lambda: 800)

    def invoke():
        return final._replay_projection(case["checkout"], case["claims"], case["clean"],
            "synthetic_demo", case["executable"], roster=case["roster"],
            dependency_roots=case["dependencies"])

    case["invoke"] = invoke
    return case


@pytest.mark.parametrize("dependency_kind", ["file", "directory", "file_directory", "directory_file", "alias"])
def test_final_wrapper_forwards_runtime_dependencies_in_order(final_wrapper, dependency_kind):
    case = final_wrapper
    deps, reads = {
        "file": ((case["file"],), [case["file"]]),
        "directory": ((case["directory"],), [case["directory_module"]]),
        "file_directory": ((case["file"], case["directory"]), [case["file"], case["directory_module"]]),
        "directory_file": ((case["directory"], case["file"]), [case["directory_module"], case["file"]]),
        "alias": ((case["alias"],), [case["file"]]),
    }[dependency_kind]
    case["dependencies"], case["reads"] = deps, reads
    assert case["invoke"]() == case["expected"]
    command, options = case["worker_calls"][0]
    assert command[-5:] == [str(case["claims"]), str(case["clean"]), "synthetic_demo",
                           json.dumps([str(path) for path in deps]), "candidate"]
    assert command[command.index("-c") + 1] == final._WORKER
    assert options["cwd"] == case["checkout"]
    assert options["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert len(case["trace_calls"]) == 1
    assert case["trace_calls"][0]["dependency_roots"] == deps


@pytest.mark.parametrize("filename", [".env", ".env.production", "cache.duckdb", "cache.db", "cache.sqlite3-wal"])
def test_final_wrapper_rejects_secret_or_database_even_if_explicitly_listed(final_wrapper, filename):
    case = final_wrapper
    forbidden = case["runtime"] / filename
    forbidden.write_text("public synthetic forbidden file")
    case["dependencies"], case["reads"] = (forbidden,), [forbidden]
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("flag", ["O_RDWR", "O_WRONLY", "O_RDONLY|O_CREAT", "O_RDONLY|O_TRUNC", "O_RDONLY|O_APPEND"])
def test_final_readonly_producer_cannot_write_even_an_explicit_runtime_dependency(final_wrapper, flag):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("O_RDONLY)", flag + ")")
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("path,flag", [
    ("/etc/bilun-public-unknown-config", "O_RDONLY"),
    ("/tmp/public-unlisted-directory", "O_RDONLY|O_DIRECTORY"),
    ("/root/public-fixture.key", "O_RDONLY"),
    ("/tmp/public-cache.wal", "O_RDONLY"),
    ("/dev/urandom", "O_RDONLY"),
])
def test_final_trace_rejects_unknown_os_directory_key_and_wal_reads(final_wrapper, path, flag):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", {flag}) = 50<{path}>\n+++ exited with 0 +++')
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("path", [
    "/etc/ld.so.cache", "/dev/null", "/usr/lib/public.so.1", "/lib/public.so.1",
    "/usr/share/locale/en/LC_MESSAGES/public.mo", "/proc/700/status", "/proc/700/stat", "/proc/700/statm",
    "/etc/locale.alias", "/opt/Bilun/.venv/pyvenv.cfg", "/etc/nsswitch.conf", "/etc/passwd", "/etc/ssl/openssl.cnf",
])
def test_final_wrapper_preserves_reviewed_startup_os_reads_with_exact_closed_bindings(final_wrapper, path):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", O_RDONLY) = 50<{path}>\n+++ exited with 0 +++')
    assert case["invoke"]() == case["expected"]
    assert len(case["runtime_snapshots"]) >= 3
    assert all(value == case["runtime_snapshots"][0] for value in case["runtime_snapshots"])


@pytest.mark.parametrize("field,replacement", [
    ("sha256", "f" * 64), ("mode", 0o666), ("uid", 1), ("size_bytes", 13),
    ("inode", 999), ("mtime_ns", 101), ("file_type", "symlink"),
])
def test_runtime_os_file_change_between_child_and_final_binding_is_rejected(final_wrapper, field, replacement):
    case = final_wrapper
    case["runtime_snapshot_mutation"] = field, replacement
    with pytest.raises(ValueError):
        case["invoke"]()


def test_explicit_runtime_dependency_byte_mutation_during_child_is_rejected(final_wrapper):
    case = final_wrapper
    def mutate(text):
        case["file"].write_text('{"public_runtime_fixture": false}\n')
        return text
    case["trace_transform"] = mutate
    with pytest.raises(ValueError):
        case["invoke"]()


class _StatView:
    def __init__(self, observed, **overrides):
        self.observed, self.overrides = observed, overrides
    def __getattr__(self, name):
        return self.overrides.get(name, getattr(self.observed, name))
    def __getitem__(self, key):
        return self.observed[key]


@pytest.fixture
def public_os_file(tmp_path, monkeypatch):
    path = tmp_path / "public-os-metadata.cfg"
    path.write_bytes(b"public immutable runtime fixture\n")
    path.chmod(0o644)
    monkeypatch.setattr(final, "RUNTIME_FILE_PATHS", (str(path),))
    original_lstat, original_fstat = final.os.lstat, final.os.fstat
    original_open, original_read = final.os.open, final.os.read
    case = {"path": path, "uid": 0, "fstat_mutation": None, "fstats": 0,
            "stat_size": None, "open_calls": [], "read_calls": [], "descriptors": set(),
            "swap_after_open": False, "swap_after_read": False}

    def observed_metadata(observed):
        overrides = {"st_uid": case["uid"]}
        if case["stat_size"] is not None:
            overrides["st_size"] = case["stat_size"]
        return overrides

    def replace_path():
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(b"public replacement bytes\n")
        replacement.chmod(0o644)
        replacement.replace(path)

    def lstat(value, *args, **kwargs):
        observed = original_lstat(value, *args, **kwargs)
        return _StatView(observed, **observed_metadata(observed)) if str(value) == str(path) else observed
    def fstat(fd):
        observed = original_fstat(fd)
        if fd not in case["descriptors"]:
            return observed
        case["fstats"] += 1
        overrides = observed_metadata(observed)
        if case["fstat_mutation"] is not None:
            key, value = case["fstat_mutation"]
            overrides[key] = value
        return _StatView(observed, **overrides)

    def open_file(literal, flags, *args, **kwargs):
        descriptor = original_open(literal, flags, *args, **kwargs)
        if str(literal) == str(path):
            case["open_calls"].append((str(literal), flags))
            case["descriptors"].add(descriptor)
            if case["swap_after_open"]:
                replace_path()
        return descriptor

    def read_file(fd, count):
        value = original_read(fd, count)
        if fd in case["descriptors"]:
            case["read_calls"].append(count)
            if value and case["swap_after_read"]:
                case["swap_after_read"] = False
                replace_path()
        return value

    monkeypatch.setattr(final.os, "lstat", lstat)
    monkeypatch.setattr(final.os, "fstat", fstat)
    monkeypatch.setattr(final.os, "open", open_file)
    monkeypatch.setattr(final.os, "read", read_file)
    return case


def test_runtime_descriptor_snapshot_hashes_real_public_bytes_with_metadata_seam(public_os_file):
    case = public_os_file
    value = final._snapshot_runtime_file(str(case["path"]))
    assert value["sha256"] == hashlib.sha256(b"public immutable runtime fixture\n").hexdigest()
    assert value["size_bytes"] == len(b"public immutable runtime fixture\n")
    assert value["uid"] == 0 and value["mode"] == 0o644
    assert case["fstats"] == 2
    assert case["open_calls"] == [(str(case["path"]), final.os.O_RDONLY | final.os.O_NOFOLLOW | final.os.O_CLOEXEC)]


@pytest.mark.parametrize("mutation", ["foreign_literal", "wrong_uid", "group_write", "world_write", "symlink", "directory", "fd_size", "fd_inode"])
def test_runtime_descriptor_snapshot_rejects_unbound_owner_type_mode_or_descriptor(public_os_file, mutation):
    case = public_os_file
    path = case["path"]
    literal = str(path)
    if mutation == "foreign_literal":
        literal += ".unreviewed"
    elif mutation == "wrong_uid":
        case["uid"] = 1000
    elif mutation in {"group_write", "world_write"}:
        path.chmod(0o664 if mutation == "group_write" else 0o646)
    elif mutation == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    elif mutation == "directory":
        path.unlink()
        path.mkdir()
    else:
        key = "st_size" if mutation == "fd_size" else "st_ino"
        case["fstat_mutation"] = key, getattr(path.stat(), key) + 1
    with pytest.raises(ValueError):
        final._snapshot_runtime_file(literal)


@pytest.mark.parametrize("kernel", [False, True])
@pytest.mark.parametrize("when", ["swap_after_open", "swap_after_read"])
def test_runtime_real_public_path_replacement_cannot_hide_behind_old_descriptor(public_os_file, kernel, when):
    case = public_os_file
    case[when] = True
    if kernel:
        case["stat_size"] = 0
    with pytest.raises(ValueError):
        (final._read_kernel_resource if kernel else final._snapshot_runtime_file)(str(case["path"]))


@pytest.mark.parametrize("count", [1, 65536, 65537])
def test_kernel_pseudo_resource_bounds_actual_read_bytes_independently_of_stat_size(public_os_file, count):
    case = public_os_file
    body = b"x" * count
    case["path"].write_bytes(body)
    case["stat_size"] = 0
    if count > 65536:
        with pytest.raises(ValueError):
            final._read_kernel_resource(str(case["path"]))
    else:
        descriptor, read_body = final._read_kernel_resource(str(case["path"]))
        assert read_body == body
        assert descriptor["size_bytes"] == 0
        assert descriptor["read_byte_count"] == count
        assert descriptor["sha256"] == hashlib.sha256(body).hexdigest()
        assert descriptor["file_type"] == "kernel_resource"
    assert case["open_calls"] == [(str(case["path"]), final.os.O_RDONLY | final.os.O_NOFOLLOW | final.os.O_CLOEXEC)]
    assert all(0 < request <= 65536 for request in case["read_calls"])


@pytest.mark.parametrize("mutation", ["wrong_uid", "group_write", "symlink", "fd_inode", "fd_size", "missing"])
def test_kernel_pseudo_resource_rejects_owner_mode_type_descriptor_and_io_failure(public_os_file, mutation):
    case = public_os_file
    path = case["path"]
    case["stat_size"] = 0
    if mutation == "wrong_uid":
        case["uid"] = 1
    elif mutation == "group_write":
        path.chmod(0o664)
    elif mutation == "symlink":
        target = path.with_suffix(".target")
        path.rename(target)
        path.symlink_to(target)
    elif mutation == "missing":
        path.unlink()
    else:
        case["fstat_mutation"] = ("st_ino", path.stat().st_ino + 1) if mutation == "fd_inode" else ("st_size", 1)
    with pytest.raises(ValueError):
        final._read_kernel_resource(str(path))


@pytest.mark.parametrize("boundary", ["claims", "clean", "checkout", "foreign_source", "unlisted"])
def test_final_wrapper_enforces_real_read_trace_ownership(final_wrapper, boundary):
    case = final_wrapper
    if boundary in {"claims", "clean", "checkout"}:
        case["dependencies"] = (case[boundary],)
    else:
        path = case["runtime"] / ("src/foreign.py" if boundary == "foreign_source" else "unlisted.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PUBLIC = True")
        case["extra_reads"] = [path]
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("invalid", ["missing", "relative", "empty", "fifo", "bad_child", "missing_witness", "extra_key"])
def test_final_wrapper_rejects_bad_runtime_or_child_contract(final_wrapper, invalid):
    case = final_wrapper
    if invalid == "missing":
        case["dependencies"] = (case["runtime"] / "absent.json",)
    elif invalid == "relative":
        case["dependencies"] = (Path("public-runtime.json"),)
    elif invalid == "empty":
        case["dependencies"] = ()
    elif invalid == "fifo":
        import os
        path = case["runtime"] / "fifo"
        os.mkfifo(path)
        case["dependencies"] = (path,)
    elif invalid == "bad_child":
        case["returncode"] = 1
    elif invalid == "missing_witness":
        case["output"].pop("source_witnesses")
    else:
        case["output"]["future_permission"] = True
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("leaf", ["status", "stat", "statm", "maps", "cgroup"])
@pytest.mark.parametrize("pid", [700, 701, 999])
def test_runtime_proc_read_requires_completed_authentic_trace_process_owner(final_wrapper, leaf, pid):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", O_RDONLY) = 60</proc/{pid}/{leaf}>\n+++ exited with 0 +++')
    if pid == 999:
        with pytest.raises(ValueError):
            case["invoke"]()
    else:
        assert case["invoke"]() == case["expected"]


@pytest.mark.parametrize("mutation", [
    "missing_child_exit", "missing_parent_exit", "failed_child", "killed_child", "detached",
    "unprefixed_proc_owner", "unmatched_unfinished", "unmatched_resumed", "strace_error",
])
def test_runtime_proc_permissions_require_complete_successful_trace(final_wrapper, mutation):
    case = final_wrapper
    def change(text):
        if mutation == "missing_child_exit":
            return text.replace("701 +++ exited with 0 +++\n", "")
        if mutation == "missing_parent_exit":
            return text.replace("700 +++ exited with 0 +++\n", "")
        if mutation == "failed_child":
            return text.replace("701 +++ exited with 0 +++", "701 +++ exited with 1 +++")
        if mutation == "killed_child":
            return text.replace("701 +++ exited with 0 +++", "701 +++ killed by SIGKILL +++")
        if mutation == "detached":
            return text.replace("700 +++ exited with 0 +++", "700 detached\n700 +++ exited with 0 +++")
        if mutation == "unprefixed_proc_owner":
            without_ids = "\n".join(line[4:] for line in text.splitlines() if "clone(" not in line
                                    and not line.startswith("701 ")) + "\n"
            return without_ids.replace("+++ exited with 0 +++",
                'openat(AT_FDCWD, "public", O_RDONLY) = 60</proc/700/maps>\n+++ exited with 0 +++')
        if mutation == "unmatched_unfinished":
            extra = '700 openat(AT_FDCWD, "public", O_RDONLY <unfinished ...>'
        elif mutation == "unmatched_resumed":
            extra = '700 <... openat resumed>) = 60</proc/700/maps>'
        else:
            extra = "strace: public fixture incomplete"
        return text.replace("700 +++ exited with 0 +++", extra + "\n700 +++ exited with 0 +++")
    case["complete_trace_transform"] = change
    with pytest.raises(ValueError):
        case["invoke"]()


def test_runtime_complete_trace_rejoins_interleaved_proc_open_and_keeps_pid_owner(final_wrapper):
    case = final_wrapper
    case["complete_trace_transform"] = lambda text: text.replace("701 +++ exited with 0 +++",
        '700 openat(AT_FDCWD, "public", O_RDONLY <unfinished ...>\n'
        '701 openat(AT_FDCWD, "public", O_RDONLY) = 61</proc/701/status>\n'
        '700 <... openat resumed>) = 60</proc/700/maps>\n701 +++ exited with 0 +++')
    assert case["invoke"]() == case["expected"]


@pytest.mark.parametrize("path", [
    *PUBLIC_KERNEL_PATHS.values(),
])
def test_runtime_exact_fixed_and_own_session_kernel_resource_reads_are_bound(final_wrapper, path):
    case = final_wrapper
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", O_RDONLY) = 60<{path}>\n+++ exited with 0 +++')
    assert case["invoke"]() == case["expected"]
    assert len(case["resource_snapshots"]) >= 4


@pytest.mark.parametrize("path,flag", [
    ("/proc/700/environ", "O_RDONLY"), ("/proc/700/cmdline", "O_RDONLY"),
    ("/proc/700/mem", "O_RDONLY"), ("/proc/700/fd/3", "O_RDONLY"),
    ("/proc/self/cgroup", "O_RDONLY"), ("/proc/thread-self/maps", "O_RDONLY"),
    ("/proc/700/mountinfo", "O_RDONLY"), ("/proc/700/status", "O_RDONLY|O_DIRECTORY"),
    ("/sys/fs/cgroup/user.slice/user-0.slice/session-901.scope/cpu.max", "O_RDONLY"),
    ("/sys/fs/cgroup" + PUBLIC_SCOPE + "/memory.current", "O_RDONLY"),
    ("/sys/fs/cgroup" + PUBLIC_SCOPE + "/cpu.weight", "O_RDONLY"),
    ("/sys/fs/cgroup" + PUBLIC_SCOPE + "/../session-900.scope/cpu.max", "O_RDONLY"),
    ("/sys/fs/cgroup/user.slice", "O_RDONLY|O_DIRECTORY"),
    ("/sys/kernel/mm/transparent_hugepage/defrag", "O_RDONLY"),
    ("/etc/ssl/private/public.key.backup", "O_RDONLY"),
    ("/sys/fs/cgroup" + PUBLIC_SCOPE + "/memory.max", "O_RDWR"),
])
def test_runtime_closed_proc_kernel_and_secret_policy_precedes_dependency_allowance(final_wrapper, path, flag):
    case = final_wrapper
    # The native source/resources are never read: only a public trace contains
    # these paths. An explicit broad dependency cannot override proc/kernel rules.
    if path.startswith("/proc/"):
        case["dependencies"] = (*case["dependencies"], Path("/proc"))
    elif path.startswith("/sys/"):
        case["dependencies"] = (*case["dependencies"], Path("/sys"))
    case["trace_transform"] = lambda text: text.replace("+++ exited with 0 +++",
        f'openat(AT_FDCWD, "public", {flag}) = 60<{path}>\n+++ exited with 0 +++')
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("mutation", [
    "none", "extra", "missing", "member_none", "scope_none", "foreign_member_pid", "scope_foreign",
    "kernel_missing", "kernel_extra", "foreign_kernel_path", "descriptor_extra", "uid_bool",
    "size_float", "read_count_bool", "read_count_float", "read_count_oversize", "sha_upper", "sha_null",
])
def test_runtime_resource_binding_has_closed_typed_schema_before_any_recheck_open(monkeypatch, mutation):
    expected = _public_runtime_resources()
    monkeypatch.setattr(final.os, "getpid", lambda: 800)
    descriptor = expected["kernel_files"]["own_session_cpu_max"]
    if mutation == "none":
        expected = None
    elif mutation == "extra":
        expected["process_ids"] = ["999"]
    elif mutation == "missing":
        expected.pop("membership")
    elif mutation == "member_none":
        expected["membership"] = None
    elif mutation == "scope_none":
        expected["membership"]["scope"] = None
    elif mutation == "foreign_member_pid":
        expected["membership"]["descriptor"]["path"] = "/proc/801/cgroup"
    elif mutation == "scope_foreign":
        expected["membership"]["scope"] = "/user.slice/user-1000.slice/session-900.scope"
    elif mutation == "kernel_missing":
        expected["kernel_files"].pop("own_session_memory_max")
    elif mutation == "kernel_extra":
        expected["kernel_files"]["memory_current"] = copy.deepcopy(descriptor)
    elif mutation == "foreign_kernel_path":
        descriptor["path"] = "/sys/fs/cgroup/user.slice/user-0.slice/session-901.scope/cpu.max"
    elif mutation == "descriptor_extra":
        descriptor["future_permission"] = True
    else:
        field, value = {
            "uid_bool": ("uid", False), "size_float": ("size_bytes", 0.0),
            "read_count_bool": ("read_byte_count", True), "read_count_float": ("read_byte_count", 11.0),
            "read_count_oversize": ("read_byte_count", 65537), "sha_upper": ("sha256", "A" * 64),
            "sha_null": ("sha256", None),
        }[mutation]
        descriptor[field] = value
    monkeypatch.setattr(final, "_snapshot_runtime_resources", lambda *_: pytest.fail("Invalid binding reached runtime reads"))
    with pytest.raises(ValueError):
        final._check_runtime_resources_stability(expected)


@pytest.mark.parametrize("mutation", ["missing_file", "extra_file", "path_key", "uid_bool", "size_float", "descriptor_extra"])
def test_runtime_regular_bindings_reject_missing_forged_or_untyped_record_before_fd(final_wrapper, monkeypatch, mutation):
    case = final_wrapper
    bindings = copy.deepcopy(case["os_bindings"])
    row = bindings["/etc/passwd"]
    if mutation == "missing_file":
        bindings.pop("/etc/passwd")
    elif mutation == "extra_file":
        bindings["/etc/group"] = copy.deepcopy(row)
    elif mutation == "path_key":
        row["path"] = "/etc/group"
    elif mutation == "uid_bool":
        row["uid"] = False
    elif mutation == "size_float":
        row["size_bytes"] = 12.0
    else:
        row["future_permission"] = True
    monkeypatch.setattr(final, "_snapshot_runtime_files", lambda: pytest.fail("Invalid regular binding reached FD reads"))
    with pytest.raises(ValueError):
        final._validate_pure_read_trace(Path("/unread-public-trace"), roster=case["roster"],
            dependency_roots=case["dependencies"], runtime_os_bindings=bindings,
            runtime_resource_bindings=case["resource_bindings"])


@pytest.mark.parametrize("target,field,value", [
    ("membership", "sha256", "f" * 64), ("membership", "inode", 999),
    ("user_slice_cpu_max", "sha256", "f" * 64), ("own_session_memory_max", "read_byte_count", 12),
    ("own_session_cpu_max", "uid", 1), ("own_session_memory_max", "mode", 0o666),
])
def test_runtime_member_and_kernel_binding_rechecks_reject_changed_metadata(final_wrapper, target, field, value):
    case = final_wrapper
    case["resource_snapshot_mutation"] = target, field, value
    with pytest.raises(ValueError):
        case["invoke"]()


@pytest.mark.parametrize("newline", ["", "\n"])
def test_runtime_own_cgroup_membership_is_numeric_and_exact_ascii_one_line(monkeypatch, newline):
    monkeypatch.setattr(final.os, "getpid", lambda: 800)
    body = ("0::" + PUBLIC_SCOPE + newline).encode()
    descriptor = _public_descriptor("/proc/800/cgroup", kernel=True, body=body)
    reads = []
    def read(literal):
        reads.append(literal)
        return descriptor, body
    monkeypatch.setattr(final, "_read_kernel_resource", read)
    assert final._load_own_cgroup_membership() == {"descriptor": descriptor, "scope": PUBLIC_SCOPE}
    assert reads == ["/proc/800/cgroup"]


@pytest.mark.parametrize("body", [
    b"", b"\n", b"0::/user.slice/user-0.slice/session-900.scope\n\n",
    b"0::/user.slice/user-0.slice/session-900.scope\n0::/another.scope\n",
    b"2:cpu:/user.slice/user-0.slice/session-900.scope\n",
    b"0::/user.slice/user-1000.slice/session-900.scope\n",
    b"0::/user.slice/user-0.slice/session-other.scope\n",
    b"0::/user.slice/user-0.slice/session-900.scope/../session-901.scope\n",
    b" 0::/user.slice/user-0.slice/session-900.scope\n",
    b"0::/user.slice/user-0.slice/session-900.scope \n",
    b"0::/user.slice/user-0.slice/session-900.scope\r\n",
    b"0::/user.slice/user-0.slice/session-\xff.scope\n",
])
def test_runtime_membership_rejects_malformed_multiple_foreign_or_nonascii_lines(monkeypatch, body):
    monkeypatch.setattr(final.os, "getpid", lambda: 800)
    monkeypatch.setattr(final, "_read_kernel_resource", lambda literal: (
        _public_descriptor(literal, kernel=True, body=body), body))
    with pytest.raises(ValueError):
        final._load_own_cgroup_membership()


@pytest.mark.parametrize("pid", [None, True, 0, -1, 800.0, "800"])
def test_runtime_membership_rejects_non_numeric_coordinator_before_read(monkeypatch, pid):
    monkeypatch.setattr(final.os, "getpid", lambda: pid)
    monkeypatch.setattr(final, "_read_kernel_resource", lambda *_: pytest.fail("Bad coordinator reached proc read"))
    with pytest.raises(ValueError):
        final._load_own_cgroup_membership()


def test_runtime_changed_membership_is_checked_before_any_kernel_resource_open(monkeypatch):
    current = _public_runtime_resources()["membership"]
    old = copy.deepcopy(current)
    old["scope"] = "/user.slice/user-0.slice/session-901.scope"
    monkeypatch.setattr(final, "_load_own_cgroup_membership", lambda: copy.deepcopy(current))
    monkeypatch.setattr(final, "_snapshot_kernel_resource", lambda *_: pytest.fail("Changed scope reached kernel open"))
    with pytest.raises(ValueError):
        final._snapshot_runtime_resources(old)


@pytest.mark.parametrize("mutation", ["foreign_literal", "foreign_label", "missing", "extra", "wrong_fixed", "wrong_session", "traversal"])
def test_runtime_kernel_resource_catalog_cannot_be_supplied_or_widened_by_caller(monkeypatch, mutation):
    paths = copy.deepcopy(PUBLIC_KERNEL_PATHS)
    literal, label = paths["own_session_cpu_max"], "own_session_cpu_max"
    if mutation == "foreign_literal":
        literal = "/sys/fs/cgroup/user.slice/user-0.slice/session-901.scope/cpu.max"
    elif mutation == "foreign_label":
        label = "memory_current"
    elif mutation == "missing":
        paths.pop("own_session_memory_max")
    elif mutation == "extra":
        paths["memory_current"] = literal
    elif mutation == "wrong_fixed":
        paths["user_slice_cpu_max"] = "/sys/fs/cgroup/cpu.max"
    elif mutation == "wrong_session":
        paths["own_session_memory_max"] = "/sys/fs/cgroup/user.slice/user-0.slice/session-901.scope/memory.max"
    else:
        literal = "/sys/fs/cgroup" + PUBLIC_SCOPE + "/../session-900.scope/cpu.max"
    monkeypatch.setattr(final, "_read_kernel_resource", lambda *_: pytest.fail("Forged catalog reached FD read"))
    with pytest.raises(ValueError):
        final._snapshot_kernel_resource(literal, label, paths)


@pytest.fixture
def public_history(tmp_path, monkeypatch):
    checkout = tmp_path / "public-git"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "public@example.invalid")
    _git(checkout, "config", "user.name", "Public fixture")
    frozen_paths = ["scripts/deploy/verify_source_refresh_transition.py",
                    "tests/unit/deploy/test_source_refresh_transition.py"]
    for path in frozen_paths:
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("FROZEN = True\n")
    product = checkout / "data/public_product.json"
    product.parent.mkdir(parents=True)
    product.write_text('{"version": 0}')
    baseline = _commit(checkout, "public baseline")
    product.write_text('{"version": 1}')
    first = _commit(checkout, "public source product")
    _git(checkout, "checkout", "-q", "-b", "old-tooling")
    (checkout / frozen_paths[0]).write_text("FROZEN = 'old seed tooling'\n")
    old_tool = _commit(checkout, "frozen old tooling")
    _git(checkout, "checkout", "-q", "-b", "product", first)
    product.write_text('{"version": 2}')
    middle = _commit(checkout, "public followup product")
    product.write_text('{"version": 3}')
    anchor = _commit(checkout, "public copay product")
    _git(checkout, "checkout", "-q", "old-tooling")
    _git(checkout, "merge", "--no-ff", "-m", "reviewed public integration seed", anchor)
    seed = _git(checkout, "rev-parse", "HEAD")
    tree = lambda sha: _git(checkout, "rev-parse", sha + "^{tree}")
    for key, value in {
        "BASELINE_CODE_SHA": baseline, "BASELINE_TREE": tree(baseline),
        "PRODUCT_ANCHOR_SHA": anchor, "PRODUCT_ANCHOR_TREE": tree(anchor),
        "INTEGRATION_SEED_SHA": seed, "INTEGRATION_SEED_TREE": tree(seed),
        "SEED_PARENTS": (old_tool, anchor),
        "PRODUCT_HISTORY": ((first, tree(first), baseline), (middle, tree(middle), first),
                            (anchor, tree(anchor), middle)),
    }.items():
        monkeypatch.setattr(final, key, value)
    new_tool = checkout / "scripts/deploy/verify_final_source_refresh_transition.py"
    new_tool.write_text("PUBLIC = True\n")
    candidate = _commit(checkout, "public new tooling")
    return {"checkout": checkout, "product": product, "candidate": candidate,
            "seed": seed, "anchor": anchor, "new_tool": new_tool, "frozen_paths": frozen_paths}


def test_only_reviewed_seed_linear_tooling_descendant_is_admitted(public_history):
    case = public_history
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result["integration_seed_sha"] == case["seed"]
    assert result["product_anchor_sha"] == case["anchor"]
    assert result["descendant_commits"] == [case["candidate"]]
    assert result["authorized_changed_paths"] == ["scripts/deploy/verify_final_source_refresh_transition.py"]


@pytest.mark.parametrize("mutation", [
    "wrong_head", "seed_itself", "wrong_seed_tree", "wrong_seed_parents", "product",
    "product_then_revert", "frozen_verifier", "frozen_test", "unauthorized_asset", "merge",
])
def test_final_history_rejects_unknown_product_ancestry_or_intermediate_edit(public_history, monkeypatch, mutation):
    case = public_history
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation == "seed_itself":
        _git(checkout, "checkout", "-q", case["seed"])
        candidate = case["seed"]
    elif mutation == "wrong_seed_tree":
        monkeypatch.setattr(final, "INTEGRATION_SEED_TREE", "f" * 40)
    elif mutation == "wrong_seed_parents":
        monkeypatch.setattr(final, "SEED_PARENTS", tuple(reversed(final.SEED_PARENTS)))
    elif mutation in {"product", "product_then_revert"}:
        old = case["product"].read_bytes()
        case["product"].write_text('{"version": 99}')
        candidate = _commit(checkout, "unreviewed product change")
        if mutation.endswith("revert"):
            case["product"].write_bytes(old)
            candidate = _commit(checkout, "reverted product does not erase history")
    elif mutation in {"frozen_verifier", "frozen_test"}:
        path = case["frozen_paths"][0 if mutation == "frozen_verifier" else 1]
        (checkout / path).write_text("UNREVIEWED = True\n")
        candidate = _commit(checkout, "frozen profile mutation")
    elif mutation == "unauthorized_asset":
        (checkout / "data/extra.json").write_text("{}")
        candidate = _commit(checkout, "unreviewed extra asset")
    else:
        _git(checkout, "checkout", "-q", "-b", "side", case["seed"])
        (checkout / "scripts/deploy/verify_candidate_semantics.py").write_text("SIDE = True\n")
        side = _commit(checkout, "side tooling")
        _git(checkout, "checkout", "-q", "old-tooling")
        _git(checkout, "merge", "--no-ff", "-m", "unknown later merge", side)
        candidate = _git(checkout, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        final._verify_candidate_history(checkout, candidate)


def _public_blob(body):
    return ("100644", "blob", hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest())


@pytest.fixture
def normal_squash(public_history, monkeypatch):
    case = public_history
    checkout = case["checkout"]
    prior = {path: (checkout / path).read_bytes() for path in case["frozen_paths"]}
    # Public literals are independently authored, not copied from the producer.
    consumers = [
        "scripts/deploy/verify_candidate_semantics.py",
        "scripts/deploy/prepare_single_vps_release.py",
        "scripts/deploy/issue_wavea_activation.py",
        "scripts/deploy/rehearse_wavea_same_port.py",
        "scripts/deploy/verify_private_rehearsal.py",
        "tests/unit/deploy/test_final_source_refresh_transition.py",
    ]
    tooling = {path: ("PUBLIC_TOOL = " + repr(path) + "\n").encode() for path in consumers}
    slot = b"0" * 64
    normalized = b'_REVIEWED_SQUASH_SELF_SHA256 = "' + slot + b'"\nPUBLIC = True\n'
    digest = hashlib.sha256(normalized).hexdigest()
    source = normalized.replace(slot, digest.encode(), 1)
    _git(checkout, "checkout", "-q", "-b", "public-squash", case["anchor"])
    for path, body in {**prior, **tooling, "scripts/deploy/verify_final_source_refresh_transition.py": source}.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    candidate = _commit(checkout, "public reviewed normal squash")
    monkeypatch.setattr(final, "_FROZEN_PRIOR_TOOLING", {path: _public_blob(body) for path, body in prior.items()})
    monkeypatch.setattr(final, "_REVIEWED_SQUASH_TOOLING", {path: _public_blob(body) for path, body in tooling.items()})
    monkeypatch.setattr(final, "_REVIEWED_SQUASH_SELF_SHA256", digest)
    return {**case, "candidate": candidate, "source": source, "digest": digest,
            "tooling": tooling, "prior": prior}


def _amend_public_squash(case):
    _git(case["checkout"], "add", ".")
    _git(case["checkout"], "commit", "--amend", "-q", "--no-edit")
    return _git(case["checkout"], "rev-parse", "HEAD")


def test_normal_squash_admits_only_reviewed_anchor_and_exact_tooling(normal_squash):
    case = normal_squash
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result == {
        "product_anchor_sha": case["anchor"], "product_anchor_tree": final.PRODUCT_ANCHOR_TREE,
        "integration_seed_sha": None, "integration_seed_tree": None,
        "candidate_sha": case["candidate"], "descendant_commits": [case["candidate"]],
        "authorized_changed_paths": sorted([*case["tooling"], "scripts/deploy/verify_final_source_refresh_transition.py"]),
        "product_closure_sha256": hashlib.sha256(final._product_closure(case["checkout"], case["anchor"])).hexdigest(),
    }


def test_normal_squash_fresh_clone_does_not_need_discarded_seed(normal_squash, tmp_path):
    case = normal_squash
    fresh = tmp_path / "fresh-main"
    _git(tmp_path, "clone", "--no-local", "--single-branch", "--branch", "public-squash", str(case["checkout"]), str(fresh))
    with pytest.raises(ValueError):
        final._git(fresh, "cat-file", "-e", case["seed"])
    result = final._verify_candidate_history(fresh, case["candidate"])
    assert result["integration_seed_sha"] is None
    assert result["descendant_commits"] == [case["candidate"]]


@pytest.mark.parametrize("path", [
    "scripts/deploy/verify_candidate_semantics.py", "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/issue_wavea_activation.py", "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_private_rehearsal.py", "tests/unit/deploy/test_final_source_refresh_transition.py",
    "scripts/deploy/verify_source_refresh_transition.py", "tests/unit/deploy/test_source_refresh_transition.py",
])
@pytest.mark.parametrize("mutation", ["body", "mode", "type"])
def test_normal_squash_rejects_every_changed_reviewed_tool_entry(normal_squash, path, mutation):
    target = normal_squash["checkout"] / path
    if mutation == "body":
        target.write_text("UNREVIEWED = True\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        target.symlink_to("/public-unreviewed-target")
    candidate = _amend_public_squash(normal_squash)
    with pytest.raises(ValueError):
        final._verify_candidate_history(normal_squash["checkout"], candidate)


@pytest.mark.parametrize("mutation", [
    "wrong_head", "wrong_anchor", "future_commit", "mutate_revert", "two_parents",
    "product_body", "product_mode", "product_type", "extra_product", "extra_tooling",
    "self_body", "self_mode", "self_type",
])
def test_normal_squash_rejects_unknown_identity_history_or_closure(normal_squash, mutation):
    case = normal_squash
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation == "wrong_anchor":
        candidate = _git(checkout, "commit-tree", candidate + "^{tree}", "-p", case["anchor"] + "^", "-m", "wrong anchor parent")
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation == "future_commit":
        case["new_tool"].write_bytes(case["source"] + b"# future\n")
        candidate = _commit(checkout, "unreviewed future descendant")
    elif mutation == "mutate_revert":
        body = case["product"].read_bytes()
        case["product"].write_text('{"version": 99}')
        _commit(checkout, "unreviewed product intermediate")
        case["product"].write_bytes(body)
        candidate = _commit(checkout, "revert does not restore reviewed parent")
    elif mutation == "two_parents":
        _git(checkout, "checkout", "-q", "-b", "unreviewed-side", case["anchor"])
        (checkout / "data/side.json").write_text("{}")
        side = _commit(checkout, "unreviewed side")
        _git(checkout, "checkout", "-q", "public-squash")
        _git(checkout, "merge", "--no-ff", "-m", "ordinary two parent merge", side)
        candidate = _git(checkout, "rev-parse", "HEAD")
    else:
        target = case["product"] if mutation.startswith("product_") else case["new_tool"]
        if mutation.endswith("body"):
            target.write_bytes(target.read_bytes() + b"# changed\n")
        elif mutation.endswith("mode"):
            target.chmod(0o755)
        elif mutation.endswith("type"):
            target.unlink()
            target.symlink_to("/public-unreviewed-target")
        else:
            extra = checkout / ("data/extra.json" if mutation == "extra_product" else "scripts/deploy/extra.py")
            extra.write_text("{}")
        candidate = _amend_public_squash(case)
    with pytest.raises(ValueError):
        final._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["missing", "multiple", "malformed", "mismatch", "other_bytes", "resealed"])
def test_normal_squash_self_pin_rejects_unknown_slot_or_other_source_bytes(normal_squash, mutation):
    case = normal_squash
    source, digest = case["source"], case["digest"].encode()
    if mutation == "missing":
        source = source.replace(b"_REVIEWED_SQUASH_SELF_SHA256", b"OTHER_DIGEST")
    elif mutation == "multiple":
        source += source.splitlines(keepends=True)[0]
    elif mutation == "malformed":
        source = source.replace(digest, b"x" * 64)
    elif mutation == "mismatch":
        source = source.replace(digest, b"f" * 64)
    else:
        source += b"# unreviewed bytes\n"
        if mutation == "resealed":
            new_digest = hashlib.sha256(source.replace(digest, b"0" * 64)).hexdigest().encode()
            source = source.replace(digest, new_digest)
    with pytest.raises(ValueError):
        final._verify_squash_self_source(source)


@pytest.mark.parametrize("mutation", [None, "wrong_sha", "disk_bytes", "missing_final"])
def test_normal_squash_keeps_actual_executing_verifier_binding(normal_squash, monkeypatch, mutation):
    case = normal_squash
    checkout = case["checkout"]
    historical_path = checkout / "scripts/deploy/verify_clinical_semantic_transition.py"
    historical_path.write_text("PUBLIC_HISTORICAL = True\n")
    candidate = _commit(checkout, "public fixture for executing-byte binding only")
    monkeypatch.setattr(final.historical, "__file__", str(historical_path))
    if mutation == "wrong_sha":
        candidate = case["candidate"]
    elif mutation == "disk_bytes":
        case["new_tool"].write_text("UNREVIEWED = True\n")
    elif mutation == "missing_final":
        case["new_tool"].unlink()
    if mutation is None:
        binding = final._guard_code_binding(checkout, candidate)
        assert binding["verifier_sha"] == candidate
        assert "scripts/deploy/verify_final_source_refresh_transition.py" in binding["files"]
    else:
        with pytest.raises(ValueError):
            final._guard_code_binding(checkout, candidate)


_PUBLIC_OLD_REPLAY_PATHS = (
    "scripts/deploy/prepare_single_vps_release.py",
    "scripts/deploy/rehearse_wavea_same_port.py",
    "scripts/deploy/verify_final_source_refresh_transition.py",
    "tests/unit/deploy/fixtures/final_source_refresh_main00128_tooling.json",
    "tests/unit/deploy/test_final_source_refresh_transition.py",
    "tests/unit/deploy/test_prepare_single_vps_release.py",
    "tests/unit/deploy/test_same_port_rehearsal.py",
    "tests/unit/deploy/test_source_refresh_transition.py",
)


def _public_old_replay_closure(checkout, sha):
    records = _git(checkout, "ls-tree", "-r", "-z", sha).encode().split(b"\0")
    return b"\0".join(record for record in records if record
        and record.split(b"\t", 1)[1].decode() not in _PUBLIC_OLD_REPLAY_PATHS)


@pytest.fixture
def old_replay_squash(normal_squash, monkeypatch):
    """Authored tooling, a reviewed main parent, and an unreachable PR history."""
    case = normal_squash
    checkout, base = case["checkout"], case["candidate"]
    base_tree = _git(checkout, "rev-parse", base + "^{tree}")
    closure = _public_old_replay_closure(checkout, base)
    tooling = {path: ("PUBLIC_REPLAY_TOOL = " + repr(path) + "\n").encode()
               for path in _PUBLIC_OLD_REPLAY_PATHS
               if path != "scripts/deploy/verify_final_source_refresh_transition.py"}
    slot = b"0" * 64
    normalized = b'_REVIEWED_OLD_REPLAY_SELF_SHA256 = "' + slot + b'"\nPUBLIC_REPLAY = True\n'
    digest = hashlib.sha256(normalized).hexdigest()
    source = normalized.replace(slot, digest.encode(), 1)
    sources = {**tooling, "scripts/deploy/verify_final_source_refresh_transition.py": source}
    _git(checkout, "checkout", "-q", "-b", "public-replay-feature", base)
    (checkout / "scripts/deploy/prepare_single_vps_release.py").write_bytes(tooling[
        "scripts/deploy/prepare_single_vps_release.py"])
    _commit(checkout, "public feature intermediate")
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    feature = _commit(checkout, "public reviewed feature tree")
    _git(checkout, "checkout", "-q", "-b", "public-replay-squash", base)
    for path, body in sources.items():
        target = checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    candidate = _commit(checkout, "public normal squash with independent commit identity")
    pins = {path: _public_blob(body) for path, body in tooling.items()}
    for name, value in {
        "OLD_REPLAY_BASE_SHA": base, "OLD_REPLAY_BASE_TREE": base_tree,
        "_REVIEWED_OLD_REPLAY_PRODUCT_CLOSURE_SHA256": hashlib.sha256(closure).hexdigest(),
        "_REVIEWED_OLD_REPLAY_TOOLING": pins, "_REVIEWED_OLD_REPLAY_SELF_SHA256": digest,
    }.items():
        monkeypatch.setattr(final, name, value)
    return {**case, "base": base, "base_tree": base_tree, "candidate": candidate,
            "feature": feature, "tooling": tooling, "pins": pins, "source": source,
            "digest": digest, "product_closure": closure}


def _public_old_replay_tooling_digest(case):
    return _digest({"profile": "bilun-old-replay-tooling-main00128-v1",
        "base_sha": case["base"], "base_tree": case["base_tree"],
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "files": case["pins"],
        "verifier": {"path": "scripts/deploy/verify_final_source_refresh_transition.py",
                     "mode": "100644", "type": "blob", "normalized_sha256": case["digest"]}})


def test_old_replay_normal_squash_binds_the_whole_tree_and_exact_eight_paths(old_replay_squash):
    case = old_replay_squash
    assert final.OLD_REPLAY_TOOLING_PATHS == frozenset(_PUBLIC_OLD_REPLAY_PATHS)
    assert _git(case["checkout"], "rev-parse", case["candidate"] + "^{tree}") == _git(
        case["checkout"], "rev-parse", case["feature"] + "^{tree}")
    assert case["candidate"] != case["feature"]
    result = final._verify_candidate_history(case["checkout"], case["candidate"])
    assert result == {
        "product_anchor_sha": case["anchor"], "product_anchor_tree": final.PRODUCT_ANCHOR_TREE,
        "integration_seed_sha": None, "integration_seed_tree": None,
        "candidate_sha": case["candidate"], "descendant_commits": [case["candidate"]],
        "authorized_changed_paths": list(_PUBLIC_OLD_REPLAY_PATHS),
        "product_closure_sha256": hashlib.sha256(case["product_closure"]).hexdigest(),
        "tooling_profile": "bilun-old-replay-tooling-main00128-v1",
        "tooling_base_sha": case["base"], "tooling_base_tree": case["base_tree"],
        "reviewed_tooling_sha256": _public_old_replay_tooling_digest(case),
    }


def test_old_replay_normal_squash_accepts_unknown_commit_identity_for_the_same_tree(old_replay_squash):
    case = old_replay_squash
    first = final._verify_candidate_history(case["checkout"], case["candidate"])
    replacement = _git(case["checkout"], "commit-tree", case["candidate"] + "^{tree}",
                       "-p", case["base"], "-m", "different public squash metadata")
    assert replacement not in {case["candidate"], case["feature"]}
    _git(case["checkout"], "checkout", "-q", "--detach", replacement)
    second = final._verify_candidate_history(case["checkout"], replacement)
    assert second == {**first, "candidate_sha": replacement, "descendant_commits": [replacement]}


def test_old_replay_profile_preserves_the_reviewed_main_parent_and_historical_permissions(old_replay_squash):
    case = old_replay_squash
    _git(case["checkout"], "checkout", "-q", "--detach", case["base"])
    result = final._verify_candidate_history(case["checkout"], case["base"])
    assert "tooling_profile" not in result
    assert result["integration_seed_sha"] is None
    assert result["authorized_changed_paths"] == sorted([
        "scripts/deploy/verify_candidate_semantics.py", "scripts/deploy/prepare_single_vps_release.py",
        "scripts/deploy/issue_wavea_activation.py", "scripts/deploy/rehearse_wavea_same_port.py",
        "scripts/deploy/verify_private_rehearsal.py", "tests/unit/deploy/test_final_source_refresh_transition.py",
        "scripts/deploy/verify_final_source_refresh_transition.py",
    ])
    for path in (
        "tests/unit/deploy/test_prepare_single_vps_release.py",
        "tests/unit/deploy/test_same_port_rehearsal.py",
        "tests/unit/deploy/fixtures/final_source_refresh_main00128_tooling.json",
    ):
        assert path not in final.AUTHORIZED_TOOLING_PATHS
        assert path not in final._SEED_TOOLING_EXCLUSIONS


def test_old_replay_normal_squash_fresh_clone_needs_no_seed_or_feature_head(old_replay_squash, tmp_path):
    case = old_replay_squash
    fresh = tmp_path / "fresh-replay-main"
    _git(tmp_path, "clone", "--no-local", "--single-branch", "--branch", "public-replay-squash",
         str(case["checkout"]), str(fresh))
    for discarded in (case["seed"], case["feature"]):
        with pytest.raises(ValueError):
            final._git(fresh, "cat-file", "-e", discarded)
    result = final._verify_candidate_history(fresh, case["candidate"])
    assert result["tooling_base_sha"] == case["base"]
    assert result["integration_seed_sha"] is None
    assert result["descendant_commits"] == [case["candidate"]]


@pytest.mark.parametrize("path", _PUBLIC_OLD_REPLAY_PATHS)
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_old_replay_normal_squash_rejects_every_changed_reviewed_entry(old_replay_squash, path, mutation):
    case = old_replay_squash
    target = case["checkout"] / path
    if mutation == "body":
        target.write_bytes(target.read_bytes() + b"# changed public bytes\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        if mutation == "type":
            target.symlink_to("/public-unreviewed-target")
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("path", [
    "data/public_product.json", "scripts/deploy/verify_source_refresh_transition.py",
    "scripts/deploy/verify_candidate_semantics.py", "scripts/deploy/issue_wavea_activation.py",
    "scripts/deploy/verify_private_rehearsal.py",
])
@pytest.mark.parametrize("mutation", ["body", "mode", "type", "missing"])
def test_old_replay_normal_squash_preserves_every_other_tree_entry(old_replay_squash, path, mutation):
    case = old_replay_squash
    target = case["checkout"] / path
    if mutation == "body":
        target.write_bytes(target.read_bytes() + b"# changed public product\n")
    elif mutation == "mode":
        target.chmod(0o755)
    else:
        target.unlink()
        if mutation == "type":
            target.symlink_to("/public-unreviewed-target")
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError, match="whole-tree"):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("path", [
    "data/unreviewed.json", "scripts/deploy/extra.py", "scripts/deploy/rehearse_wavea_same_port_extra.py",
    "tests/unit/deploy/test_extra.py", "tests/unit/deploy/fixtures/extra.json",
])
def test_old_replay_normal_squash_rejects_extra_or_similarly_named_paths(old_replay_squash, path):
    case = old_replay_squash
    target = case["checkout"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("PUBLIC_UNREVIEWED = True\n")
    candidate = _amend_public_squash(case)
    with pytest.raises(ValueError, match="whole-tree"):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("mutation", [
    "wrong_head", "wrong_base_sha", "wrong_base_tree", "wrong_parent", "two_parents",
    "future_commit", "product_then_revert", "feature_history", "wrong_closure_pin",
    "missing_tooling_pin", "extra_tooling_pin", "unchanged_tooling_path",
])
def test_old_replay_normal_squash_rejects_other_identity_history_or_roster(old_replay_squash, monkeypatch, mutation):
    case = old_replay_squash
    checkout, candidate = case["checkout"], case["candidate"]
    if mutation == "wrong_head":
        candidate = "f" * 40
    elif mutation in {"wrong_base_sha", "wrong_base_tree", "wrong_closure_pin"}:
        name = {"wrong_base_sha": "OLD_REPLAY_BASE_SHA", "wrong_base_tree": "OLD_REPLAY_BASE_TREE",
                "wrong_closure_pin": "_REVIEWED_OLD_REPLAY_PRODUCT_CLOSURE_SHA256"}[mutation]
        monkeypatch.setattr(final, name, "f" * (64 if mutation == "wrong_closure_pin" else 40))
    elif mutation in {"wrong_parent", "two_parents"}:
        parents = [case["anchor"]] if mutation == "wrong_parent" else [case["base"], case["seed"]]
        arguments = ["commit-tree", candidate + "^{tree}"]
        for parent in parents:
            arguments += ["-p", parent]
        candidate = _git(checkout, *arguments, "-m", "unreviewed squash ancestry")
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation == "future_commit":
        case["new_tool"].write_bytes(case["source"] + b"# future\n")
        candidate = _commit(checkout, "unreviewed replay descendant")
    elif mutation == "product_then_revert":
        body = case["product"].read_bytes()
        case["product"].write_text('{"version": 99}')
        _commit(checkout, "public unreviewed product intermediate")
        case["product"].write_bytes(body)
        candidate = _commit(checkout, "product revert does not restore the exact parent")
    elif mutation == "feature_history":
        candidate = case["feature"]
        _git(checkout, "checkout", "-q", "--detach", candidate)
    elif mutation in {"missing_tooling_pin", "extra_tooling_pin"}:
        pins = dict(case["pins"])
        if mutation == "missing_tooling_pin":
            pins.pop("scripts/deploy/prepare_single_vps_release.py")
        else:
            pins["scripts/deploy/extra.py"] = _public_blob(b"PUBLIC = True\n")
        monkeypatch.setattr(final, "_REVIEWED_OLD_REPLAY_TOOLING", pins)
    else:
        path = "tests/unit/deploy/test_source_refresh_transition.py"
        body = final._git(checkout, "show", case["base"] + ":" + path)
        (checkout / path).write_bytes(body)
        pins = {**case["pins"], path: _public_blob(body)}
        monkeypatch.setattr(final, "_REVIEWED_OLD_REPLAY_TOOLING", pins)
        candidate = _amend_public_squash(case)
    with pytest.raises(ValueError):
        final._verify_candidate_history(checkout, candidate)


@pytest.mark.parametrize("mutation", ["missing", "multiple", "malformed", "mismatch", "other_bytes", "resealed"])
def test_old_replay_self_pin_rejects_changed_slot_or_resealed_candidate(old_replay_squash, mutation):
    case = old_replay_squash
    source, digest = case["source"], case["digest"].encode()
    if mutation == "missing":
        source = source.replace(b"_REVIEWED_OLD_REPLAY_SELF_SHA256", b"OTHER_DIGEST")
    elif mutation == "multiple":
        source += source.splitlines(keepends=True)[0]
    elif mutation == "malformed":
        source = source.replace(digest, b"x" * 64)
    elif mutation == "mismatch":
        source = source.replace(digest, b"f" * 64)
    else:
        source += b"# changed public verifier policy\n"
        if mutation == "resealed":
            replacement = hashlib.sha256(source.replace(digest, b"0" * 64)).hexdigest().encode()
            source = source.replace(digest, replacement)
    case["new_tool"].write_bytes(source)
    candidate = _amend_public_squash(case)
    assert final._REVIEWED_OLD_REPLAY_SELF_SHA256 == case["digest"]
    with pytest.raises(ValueError):
        final._verify_candidate_history(case["checkout"], candidate)


@pytest.mark.parametrize("mutation", [None, "wrong_sha", "disk_bytes", "missing_final"])
def test_old_replay_profile_keeps_actual_executing_verifier_binding(old_replay_squash, monkeypatch, mutation):
    case = old_replay_squash
    checkout = case["checkout"]
    path = checkout / "scripts/deploy/verify_clinical_semantic_transition.py"
    path.write_text("PUBLIC_HISTORICAL = True\n")
    candidate = _commit(checkout, "public executing closure fixture only")
    monkeypatch.setattr(final.historical, "__file__", str(path))
    if mutation == "wrong_sha":
        candidate = case["candidate"]
    elif mutation == "disk_bytes":
        case["new_tool"].write_text("PUBLIC_UNREVIEWED = True\n")
    elif mutation == "missing_final":
        case["new_tool"].unlink()
    if mutation is None:
        binding = final._guard_code_binding(checkout, candidate)
        assert binding["verifier_sha"] == candidate
        assert binding["files"]["scripts/deploy/verify_final_source_refresh_transition.py"] == hashlib.sha256(
            case["source"]).hexdigest()
    else:
        with pytest.raises(ValueError):
            final._guard_code_binding(checkout, candidate)


_HISTORICAL_MAIN00128_TOOLING = {
    "scripts/deploy/verify_final_source_refresh_transition.py": (
        "b6af23d0203acede37132e89ebdf29b6b768d5bd",
        "ece116123fc9ba24893231957c9e2c6e19b37bfa59bcc8140b7fbe1f7fb1361a",
        91418,
    ),
    "scripts/deploy/prepare_single_vps_release.py": (
        "90c22af28b7ac63dc540dc2dc72e798764a44f37",
        "01eedc41193be4306e1682d584be75ed672aad701bae43b8ef44c490b4db38a1",
        60596,
    ),
    "scripts/deploy/rehearse_wavea_same_port.py": (
        "24166ec87faa0637af934cec9eff380c0b039484",
        "f4880f79646e99d16374a724aec09a529225f9927577f333686fc05329ee2b8d",
        54396,
    ),
    "tests/unit/deploy/test_final_source_refresh_transition.py": (
        "b3e5ee0a4493ff43d56f9deb4b03c96eb002d29a",
        "d34914cda1a7284ef42e7e95fd721c5e9034408f94acac9643822c92cdcd4291",
        101077,
    ),
    "tests/unit/deploy/test_source_refresh_transition.py": (
        "3e543f7c6b00f1f91800a5efb53b3f84a4615467",
        "f9aaf6c111470758d5abe59a6ce100c9c99f57a06c9a937c97ab3f0c16e7fca3",
        83093,
    ),
}


def _historical_main00128_tooling_bytes(path):
    """Read five immutable historical sources; never grant a later head admission."""
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Historical tooling fixture repeats a field")
            result[key] = value
        return result

    fixture = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_fields)
    if (not isinstance(fixture, dict)
            or set(fixture) != {"schema_version", "purpose", "source_commit", "source_tree",
                                "encoding", "sources"}
            or type(fixture["schema_version"]) is not int or fixture["schema_version"] != 1
            or fixture["source_commit"] != "00128c6001c7921621b44537fcecefc22236b1f3"
            or fixture["source_tree"] != "ba09db1023be8ae17b5605145caefec771a7fbe5"
            or fixture["encoding"] != "zlib-base64"
            or fixture["purpose"] != "Historical reviewed tooling source bytes only; this fixture "
                                    "grants no deployment admission to a later head."
            or not isinstance(fixture["sources"], dict)
            or set(fixture["sources"]) != set(_HISTORICAL_MAIN00128_TOOLING)):
        raise ValueError("Historical tooling fixture has unknown provenance or roles")
    decoded = {}
    for source_path, (blob_sha1, sha256, size) in _HISTORICAL_MAIN00128_TOOLING.items():
        row = fixture["sources"][source_path]
        if (not isinstance(row, dict)
                or set(row) != {"mode", "type", "blob_sha1", "sha256", "size_bytes",
                                "zlib_base64_chunks"}
                or row["mode"] != "100644" or row["type"] != "blob"
                or row["blob_sha1"] != blob_sha1 or row["sha256"] != sha256
                or type(row["size_bytes"]) is not int or row["size_bytes"] != size):
            raise ValueError("Historical tooling fixture changes pinned source metadata")
        chunks = row["zlib_base64_chunks"]
        if (not isinstance(chunks, list) or not 1 <= len(chunks) <= 2048
                or any(not isinstance(chunk, str) or not 1 <= len(chunk) <= 76 for chunk in chunks)
                or any(len(chunk) != 76 for chunk in chunks[:-1])):
            raise ValueError("Historical tooling fixture encoding is malformed")
        try:
            compressed = base64.b64decode("".join(chunks), validate=True)
            decoder = zlib.decompressobj()
            body = decoder.decompress(compressed, size + 1)
        except (ValueError, zlib.error) as error:
            raise ValueError("Historical tooling fixture encoding is malformed") from error
        if (len(body) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
                or hashlib.sha256(body).hexdigest() != sha256
                or _public_blob(body) != ("100644", "blob", blob_sha1)):
            raise ValueError("Historical tooling fixture source bytes differ from reviewed pins")
        decoded[source_path] = body
    return decoded


def test_normal_squash_published_literals_match_reviewed_local_file_bytes():
    """Keep main00128 pins historical while checking every unchanged current source."""
    from tests.unit.deploy.test_shared_interpreter_source_profile import _historical_mainc44_tooling_bytes

    checkout = Path(final.__file__).resolve().parents[2]
    fixture_path = Path(__file__).parent / "fixtures/final_source_refresh_main00128_tooling.json"
    historical = _historical_main00128_tooling_bytes(fixture_path)
    mainc44 = _historical_mainc44_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainc44_tooling.json")
    for path, expected in {**final._FROZEN_PRIOR_TOOLING, **final._REVIEWED_SQUASH_TOOLING}.items():
        body = (historical[path] if path in historical else mainc44[path] if path in mainc44
                else (checkout / path).read_bytes())
        assert _public_blob(body) == expected
    final._verify_squash_self_source(historical["scripts/deploy/verify_final_source_refresh_transition.py"])


def test_old_replay_published_pins_match_every_current_tooling_body_and_new_self_source():
    from tests.unit.deploy.test_raw_report_transport_source_profile import _historical_mainf28_tooling_bytes

    checkout = Path(final.__file__).resolve().parents[2]
    historical = _historical_mainf28_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainf28_tooling.json")
    assert final.OLD_REPLAY_BASE_SHA == "00128c6001c7921621b44537fcecefc22236b1f3"
    assert final.OLD_REPLAY_BASE_TREE == "ba09db1023be8ae17b5605145caefec771a7fbe5"
    assert final.OLD_REPLAY_TOOLING_PATHS == frozenset(_PUBLIC_OLD_REPLAY_PATHS)
    assert set(final._REVIEWED_OLD_REPLAY_TOOLING) == set(_PUBLIC_OLD_REPLAY_PATHS) - {
        "scripts/deploy/verify_final_source_refresh_transition.py"}
    for path, entry in final._REVIEWED_OLD_REPLAY_TOOLING.items():
        body = historical[path] if path in historical else (checkout / path).read_bytes()
        assert _public_blob(body) == entry
    final._verify_old_replay_self_source(historical["scripts/deploy/verify_final_source_refresh_transition.py"])


@pytest.mark.parametrize("source_path,mutation", [
    ("scripts/deploy/prepare_single_vps_release.py", mutation) for mutation in (
        "body", "rehashed_body", "mode", "type", "missing_role", "extra_role",
        "forged_commit", "forged_tree", "extra_field", "extra_source_field", "schema_bool",
        "encoding", "size_bool", "sha256", "blob_sha1", "truncated_stream", "trailing_stream",
        "nonstring_chunk", "invalid_base64", "oversized_chunk", "missing_chunks",
    )
] + [
    ("tests/unit/deploy/test_source_refresh_transition.py", mutation) for mutation in (
        "body", "rehashed_body", "mode", "type", "missing_role", "sha256", "blob_sha1",
        "extra_source_field",
    )
] + [
    ("scripts/deploy/verify_final_source_refresh_transition.py", mutation) for mutation in (
        "body", "rehashed_body", "mode", "type", "missing_role", "sha256", "blob_sha1",
        "extra_source_field", "truncated_stream", "trailing_stream",
    )
])
def test_historical_main00128_tooling_fixture_rejects_tampering(tmp_path, source_path, mutation):
    fixture_path = Path(__file__).parent / "fixtures/final_source_refresh_main00128_tooling.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    row = fixture["sources"][source_path]
    chunks = row["zlib_base64_chunks"]
    if mutation in {"body", "rehashed_body", "truncated_stream", "trailing_stream"}:
        compressed = base64.b64decode("".join(chunks), validate=True)
        if mutation in {"body", "rehashed_body"}:
            body = zlib.decompress(compressed)
            body = bytes([body[0] ^ 1]) + body[1:]
            compressed = zlib.compress(body)
            if mutation == "rehashed_body":
                row.update(sha256=hashlib.sha256(body).hexdigest(), blob_sha1=_public_blob(body)[2])
        elif mutation == "truncated_stream":
            compressed = compressed[:-1]
        else:
            compressed += b"unreviewed trailing bytes"
        encoded = base64.b64encode(compressed).decode("ascii")
        row["zlib_base64_chunks"] = [encoded[index:index + 76] for index in range(0, len(encoded), 76)]
    elif mutation in {"mode", "type", "sha256", "blob_sha1", "size_bool"}:
        key = "size_bytes" if mutation == "size_bool" else mutation
        row[key] = {"mode": "100755", "type": "tree", "sha256": "f" * 64,
                    "blob_sha1": "f" * 40, "size_bool": True}[mutation]
    elif mutation == "missing_role":
        del fixture["sources"][source_path]
    elif mutation == "extra_role":
        fixture["sources"]["scripts/deploy/unreviewed.py"] = copy.deepcopy(row)
    elif mutation in {"forged_commit", "forged_tree"}:
        fixture["source_commit" if mutation == "forged_commit" else "source_tree"] = "f" * 40
    elif mutation == "extra_field":
        fixture["admit_later_heads"] = True
    elif mutation == "extra_source_field":
        row["allow_changed_source"] = True
    elif mutation == "schema_bool":
        fixture["schema_version"] = True
    elif mutation == "encoding":
        fixture["encoding"] = "raw-base64"
    elif mutation == "nonstring_chunk":
        chunks[0] = None
    elif mutation == "invalid_base64":
        chunks[0] = "!" + chunks[0][1:]
    elif mutation == "oversized_chunk":
        chunks[0] += "A"
    else:
        row["zlib_base64_chunks"] = []
    mutated = tmp_path / "historical-tooling.json"
    mutated.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(ValueError):
        _historical_main00128_tooling_bytes(mutated)


def test_historical_main00128_tooling_fixture_rejects_duplicate_fields(tmp_path):
    fixture_path = Path(__file__).parent / "fixtures/final_source_refresh_main00128_tooling.json"
    raw = fixture_path.read_text(encoding="utf-8")
    assert raw.count('"schema_version": 1') == 1
    mutated = tmp_path / "historical-tooling.json"
    mutated.write_text(raw.replace('"schema_version": 1', '"schema_version": 0, "schema_version": 1'),
                       encoding="utf-8")
    with pytest.raises(ValueError, match="repeats a field"):
        _historical_main00128_tooling_bytes(mutated)


def _copay():
    frames = {}
    for name, keys in (
        ("sut_clause_coverage.parquet", ["clause_id"]),
        ("sut_coverage_by_rule.parquet", ["primary_rule_id", "primary_rule_category", "coverage_status"]),
        ("sut_coverage_by_section.parquet", ["section_id", "section_title"]),
        ("sut_registry_coverage.parquet", ["rule_id"]),
    ):
        frames[name] = {"columns": keys, "schema": dict.fromkeys(keys, "String"),
                        "row_count": 1, "key_fields": keys, "rows_sha256": _digest({"public": name})}
    return {"manifest_sha256": _digest({"public": "canonical copay manifest"}),
            "frames": frames, "evidence_sha256": _digest({"public": "coverage evidence"}),
            "artifact_stats_sha256": _digest({"public": "immutable source file stats"}),
            "public_summary": {"meta": {"artifacts_available": True}},
            "canonical_manifest_verified": True, "fresh_coverage_verified": True}


def _followup_row(drug, line, rule, *, measured):
    receipt = {
        "kind": "route", "family": "followup", "claim_id": "C1", "drug_claim_line_id": line,
        "evaluator_version": "followup.atomic.v2.2026-10-03", "execution_scope": "public-scope-" + line,
        "route_id": "followup.source_date", "status": "blocked_source",
        "reasons": ["unsupported_source_date"],
        "observed_input_fields": ["drug_claim_date", "drug_name"], "missing_input_fields": [],
    }
    outcome = {
        "constraint_set": "followup_source_constraints", "criterion_status": "not_evaluated",
        "missing_inputs": ["verified_source_for_service_date"], "checks": [],
        "source_refs": ["public-reviewed-followup-source"], "sut_section": rule.split(".clinical")[0],
        "clinical_eligibility_complete": False, "verification_status": "ai_generated_pending_review",
        "source_authority": {"status": "uncovered_service_date", "service_date": "2026-10-06",
                             "reviewed_through": "2026-10-05", "clinical_eligibility_complete": False},
    }
    if measured:
        # Authored from this single blocked route, not from the runtime builder.
        summary = {
            "schema_version": 1, "available": True, "instrumented_families": ["followup"],
            "input_facts_available_count": 2, "input_facts_missing_count": 0,
            "predicate_attempted_count": 0, "predicate_evaluated_count": 0,
            "predicate_passed_count": 0, "predicate_failed_count": 0, "predicate_missing_inputs_count": 0,
            "routes_blocked_source_count": 1, "routes_blocked_inputs_count": 0, "routes_skipped_count": 0,
            "source_metrics_available": True, "source_unavailable_reason": None,
            "unresolved_source_ref_count": 0, "source_clauses_touched_count": 0,
            "complete_clause_mapping_available": False,
            "complete_clause_mapping_unavailable_reason": "No reviewed complete-clause predicate mapping supplied.",
            "source_clauses_fully_evaluated_count": None, "source_clause_ids": [],
            "fully_evaluated_source_clause_ids": None, "receipt_count": 1,
            "receipt_sha256": _digest([{k: v for k, v in receipt.items() if k != "execution_scope"}]),
            "clinical_eligibility_complete": False,
        }
        assert len(summary) == 25
        outcome["runtime_coverage"] = summary
    return {"patient_id": "P1", "claim_id": "C1", "drug_claim_line_id": line, "drug_name": drug,
            "source_rule_ids": [rule], "constraint_set": "followup_source_constraints",
            "outcome": outcome, "receipts": [receipt] if measured else []}


def _public_final_pair():
    old, new = _public_projection_pair()
    rules = [
        {"rule_id": "4.2.57.clinical_16_week_response", "drug_names": ["dupilumab"],
         "clinical_constraint_drugs": ["dupilumab"], "clinical_constraint_set": "followup_source_constraints"},
        {"rule_id": "4.2.46.clinical_annual_reassessment", "drug_names": ["nintedanib"],
         "clinical_constraint_drugs": ["nintedanib"], "clinical_constraint_set": "followup_source_constraints"},
    ]
    for projection, measured in ((old, False), (new, True)):
        witnesses = [
            _followup_row("dupilumab", "L-DUP", rules[0]["rule_id"], measured=measured),
            _followup_row("nintedanib", "L-NINT", rules[1]["rule_id"], measured=measured),
        ]
        for table, key in (("patient_billing_report_rows", "P1"),
                           ("patient_bill_billing_report_rows", "P1::C1")):
            report = projection["tables"][table][key]
            report["drug_indication"]["findings"] = [{
                "patient_id": "P1", "claim_id": "C1", "drug_claim_line_id": row["drug_claim_line_id"],
                "drug_name": row["drug_name"], "selected_rule_id": row["source_rule_ids"][0],
                "savings_try": None, "risk_amount": None, "evaluation_status": "review_required",
                "clinical_restrictions": [copy.deepcopy(row["outcome"])],
            } for row in witnesses]
        # The index is also a source projection, including null monetary fields.
        projection["tables"]["cohort_compliance_index"] = {
            "n_patients": 1, "n_findings": 2, "n_patients_with_findings": 1,
            "billed_at_risk_try": 0.0, "artifacts_available": True,
            "rows": [{"patient_id": "P1", "claim_id": "C1",
                      "drug_claim_line_id": row["drug_claim_line_id"], "drug_name": row["drug_name"],
                      "surface": "drug_indication", "billed_try": None,
                      "selected_rule_id": row["source_rule_ids"][0],
                      "clinical_restrictions": [copy.deepcopy(row["outcome"])]} for row in witnesses],
            "by_surface": {"drug_indication": {"n": 2, "billed_try": None, "n_patients": 1}},
            "claim_compliance": {"counts_by_patient": {"P1": {"evaluated": 0, "missing_inputs": 0, "unavailable": 0}},
                                 "details": [], "detail_limit": 20},
            "data_source": {"mode": "synthetic_demo", "is_synthetic": True,
                            "claim_source": "claims", "clinical_source": "clean"},
        }
        for table in STRICT_TABLES:
            row = {"patient_id": "P1", "claim_id": "C1", "public_surface": table,
                   "money": 0.0, "null": None, "flag": False, "order": ["a", "b"],
                   "selected_rule_id": "public.unrelated", "data_source": {"mode": "synthetic_demo",
                       "claim_source": "claims", "clinical_source": "clean"}}
            projection["tables"][table] = [row] if table in {
                "cohort_sut_summary", "validation_payload", "patient_meta", "cohort_sut_exposure",
                "patient_alerts_payload", "patient_diagnoses", "patient_alert_rows", "patient_billing_reports",
            } else {"P1": row}
        projection["source_witnesses"] = {
            "followup": witnesses, "followup_rules": copy.deepcopy(rules),
            "followup_source_clauses": [{"clause_id": "CF000001", "section_id": "4.2.57",
                "clause_type": "fikra", "text": "Public authored normative source fixture.",
                "is_in_force": True, "is_heading": False, "is_amendment": False}],
            "copay": _copay(),
        }
    assert set(old["tables"]) == set(new["tables"]) == set(TABLES)
    return old, new


def test_full_nineteen_source_projections_allow_only_witnessed_neutral_annotations():
    old, new = _public_final_pair()
    before = copy.deepcopy((old, new))
    assert final._check_projection_pair(old, new) == {
        "changed_organ_evaluations": 6, "neutral_raw_rows": 6, "followup_line_count": 2,
        "source_projected_table_count": 19, "strict_table_count": 13,
    }
    assert (old, new) == before
    outcome = new["source_witnesses"]["followup"][0]["outcome"]
    assert outcome["criterion_status"] == "not_evaluated"
    assert outcome["source_authority"]["status"] == "uncovered_service_date"
    assert outcome["runtime_coverage"]["predicate_attempted_count"] == 0
    assert outcome["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("table", STRICT_TABLES)
@pytest.mark.parametrize("field,value", [
    ("money", 0), ("money", None), ("null", 0.0), ("flag", 0), ("order", ["b", "a"]),
    ("selected_rule_id", "4.2.57.clinical_16_week_response"), ("data_source", {"mode": "real"}),
])
def test_all_thirteen_other_source_tables_keep_money_null_type_order_and_identity(table, field, value):
    old, new = _public_final_pair()
    rows = new["tables"][table]
    row = rows[0] if isinstance(rows, list) else rows["P1"]
    row[field] = value
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("table", TABLES)
def test_no_source_table_may_be_dropped(table):
    old, new = _public_final_pair()
    new["tables"].pop(table)
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("field,value", [
    ("schema_version", True), ("available", 1), ("instrumented_families", ["renal"]),
    ("input_facts_available_count", 2.0), ("input_facts_missing_count", None),
    ("predicate_attempted_count", 1), ("predicate_evaluated_count", 1),
    ("predicate_passed_count", 1), ("predicate_failed_count", 1), ("predicate_missing_inputs_count", 1),
    ("routes_blocked_source_count", 0), ("routes_blocked_inputs_count", 1), ("routes_skipped_count", 1),
    ("source_metrics_available", 1), ("source_unavailable_reason", "stale"),
    ("unresolved_source_ref_count", 1), ("source_clauses_touched_count", 1),
    ("complete_clause_mapping_available", True), ("complete_clause_mapping_unavailable_reason", None),
    ("source_clauses_fully_evaluated_count", 0), ("source_clause_ids", ["CF000099"]),
    ("fully_evaluated_source_clause_ids", []), ("receipt_count", 2),
    ("receipt_sha256", "f" * 64), ("clinical_eligibility_complete", 0),
])
def test_every_measured_summary_field_is_independently_typed_and_receipt_derived(field, value):
    _, new = _public_final_pair()
    new["source_witnesses"]["followup"][0]["outcome"]["runtime_coverage"][field] = value
    with pytest.raises(ValueError):
        final._check_source_witnesses(new, candidate=True)


@pytest.mark.parametrize("mutation", [
    "patient", "claim", "line", "drug", "rule", "constraint", "foreign_family", "foreign_claim",
    "foreign_line", "wrong_version", "duplicate_line", "duplicate_receipt", "mixed_scope",
    "complete_clause", "receipt_extra", "summary_extra", "empty_receipts", "baseline_measurement",
    "clinical_true", "source_rule_extra", "source_rules_duplicate",
])
def test_receipts_and_summaries_require_exact_source_and_execution_ownership(mutation):
    old, new = _public_final_pair()
    source = new["source_witnesses"]
    row = source["followup"][0]
    receipt = row["receipts"][0]
    if mutation in {"patient", "claim", "line", "drug", "rule", "constraint"}:
        field = {"patient": "patient_id", "claim": "claim_id", "line": "drug_claim_line_id",
                 "drug": "drug_name", "rule": "source_rule_ids", "constraint": "constraint_set"}[mutation]
        row[field] = ["4.2.46.clinical_annual_reassessment"] if mutation == "rule" else "foreign"
    elif mutation in {"foreign_family", "foreign_claim", "foreign_line", "wrong_version"}:
        field = {"foreign_family": "family", "foreign_claim": "claim_id", "foreign_line": "drug_claim_line_id",
                 "wrong_version": "evaluator_version"}[mutation]
        receipt[field] = "foreign"
    elif mutation == "duplicate_line":
        source["followup"].append(copy.deepcopy(row))
    elif mutation in {"duplicate_receipt", "mixed_scope"}:
        extra = copy.deepcopy(receipt)
        if mutation == "mixed_scope":
            extra.update(route_id="another.route", execution_scope="foreign-scope")
        row["receipts"].append(extra)
    elif mutation == "complete_clause":
        receipt.update(kind="predicate", predicate_id="unsupported.complete", source_refs=["CF000001"],
                       clause_predicate_complete=True)
        receipt.pop("route_id")
        receipt.pop("reasons")
    elif mutation == "receipt_extra":
        receipt["patient_value"] = "not permitted"
    elif mutation == "summary_extra":
        row["outcome"]["runtime_coverage"]["future_counter"] = 0
    elif mutation == "empty_receipts":
        row["receipts"] = []
    elif mutation == "baseline_measurement":
        old["source_witnesses"]["followup"][0] = copy.deepcopy(row)
    elif mutation == "clinical_true":
        row["outcome"]["clinical_eligibility_complete"] = True
    elif mutation == "source_rule_extra":
        source["followup_rules"].append(copy.deepcopy(source["followup_rules"][0]))
    else:
        source["followup_rules"][1] = copy.deepcopy(source["followup_rules"][0])
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("field,value", [
    ("criterion_status", "criterion_clear"), ("checks", [{"passed": True}]),
    ("missing_inputs", []), ("source_refs", ["unreviewed-source"]),
    ("verification_status", "primary_verified"), ("sut_section", "4.2.99"),
    ("source_authority", {"status": "admitted", "service_date": "2026-10-06"}),
])
def test_source_review_window_and_all_clinical_outcome_fields_stay_unchanged(field, value):
    old, new = _public_final_pair()
    row = new["source_witnesses"]["followup"][0]
    row["outcome"][field] = value
    # Keep projected payload and witness coherent; pair comparison must still reject it.
    for table, key in (("patient_billing_report_rows", "P1"), ("patient_bill_billing_report_rows", "P1::C1")):
        new["tables"][table][key]["drug_indication"]["findings"][0]["clinical_restrictions"][0][field] = value
    new["tables"]["cohort_compliance_index"]["rows"][0]["clinical_restrictions"][0][field] = value
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("table", ["patient_billing_report_rows", "patient_bill_billing_report_rows", "cohort_compliance_index"])
@pytest.mark.parametrize("mutation", ["wrong_owner", "wrong_summary", "money", "null", "rule", "order", "outside_restriction"])
def test_nested_metadata_permission_does_not_cover_other_fields_or_locations(table, mutation):
    old, new = _public_final_pair()
    root = new["tables"][table]
    rows = root["rows"] if table == "cohort_compliance_index" else root[next(iter(root))]["drug_indication"]["findings"]
    row = rows[0]
    if mutation == "wrong_owner":
        row["drug_claim_line_id"] = "foreign"
    elif mutation == "wrong_summary":
        row["clinical_restrictions"][0]["runtime_coverage"]["receipt_sha256"] = "f" * 64
    elif mutation == "money":
        row["billed_try" if table == "cohort_compliance_index" else "savings_try"] = 0.0
    elif mutation == "null":
        row["billed_try" if table == "cohort_compliance_index" else "risk_amount"] = False
    elif mutation == "rule":
        row["selected_rule_id"] = "public.unrelated"
    elif mutation == "order":
        rows.reverse()
    else:
        row["runtime_coverage"] = row["clinical_restrictions"][0].pop("runtime_coverage")
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


def test_coherent_unrelated_row_mutation_after_five_hundred_is_not_sampled():
    old, new = _public_final_pair()
    rows = [{"patient_id": "P1", "public_id": str(index), "money": None, "flag": False}
            for index in range(601)]
    old["tables"]["patient_billing_reports"] = copy.deepcopy(rows)
    new["tables"]["patient_billing_reports"] = copy.deepcopy(rows)
    new["tables"]["patient_billing_reports"][600]["money"] = 0.0
    with pytest.raises(ValueError):
        final._check_projection_pair(old, new)


@pytest.mark.parametrize("mutation", [
    "missing_manifest", "deferred_upgrade", "stale_digest", "missing_frame", "duplicate_columns",
    "wrong_keys", "count_bool", "count_float", "count_zero", "schema_missing", "row_hash_short",
    "evidence_null", "artifact_stats_wrong_type", "summary_unavailable", "extra_field",
])
def test_copay_witness_requires_complete_fresh_typed_derivation(mutation):
    witness = _copay()
    frame = witness["frames"]["sut_clause_coverage.parquet"]
    if mutation == "missing_manifest":
        witness.pop("manifest_sha256")
    elif mutation == "deferred_upgrade":
        witness["canonical_manifest_verified"] = False
    elif mutation == "stale_digest":
        witness["fresh_coverage_verified"] = False
    elif mutation == "missing_frame":
        witness["frames"].pop("sut_registry_coverage.parquet")
    elif mutation == "duplicate_columns":
        frame["columns"] *= 2
    elif mutation == "wrong_keys":
        frame["key_fields"] = ["positional_id"]
    elif mutation.startswith("count_"):
        frame["row_count"] = {"count_bool": True, "count_float": 1.0, "count_zero": 0}[mutation]
    elif mutation == "schema_missing":
        frame["schema"] = {}
    elif mutation == "row_hash_short":
        frame["rows_sha256"] = "f" * 63
    elif mutation == "evidence_null":
        witness["evidence_sha256"] = None
    elif mutation == "artifact_stats_wrong_type":
        witness["artifact_stats_sha256"] = 0
    elif mutation == "summary_unavailable":
        witness["public_summary"]["meta"]["artifacts_available"] = False
    else:
        witness["defer_verification_until_after_upgrade"] = True
    with pytest.raises(ValueError):
        final._check_copay_witness(witness)


def _attested(value):
    if isinstance(value, list):
        return [_attested(row) for row in value]
    if not isinstance(value, dict):
        return value
    result = {key: _attested(row) for key, row in value.items()}
    if "data_source" in result:
        result["data_source"].update(claim_source="@attested_claim_inputs",
                                     clinical_source="@attested_clinical_inputs")
    return result


def _final_report(projections, candidate="a" * 40):
    report = _old_report(projections, candidate=candidate)
    report.update(contract=CONTRACT, status="final_source_refresh_transition_verified",
        followup_line_count=2, source_projected_table_count=19, strict_table_count=13,
        cache_comparison_contract="all19_own_source_exact_before_admission")
    report["history"].update(product_anchor_sha="3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e",
        product_anchor_tree="5c1ee20b6b2817de41e7f2ca5fcec68a1bbfe121",
        integration_seed_sha="58e7a14294484de286bd6d98c677a10db8de800d",
        integration_seed_tree="d04625ecb21e92b7fd8bafa6d80fd893f227b620",
        product_closure_sha256=_digest({"public": "full product closure"}),
        authorized_changed_paths=["scripts/deploy/verify_final_source_refresh_transition.py"])
    files = {"scripts/deploy/verify_final_source_refresh_transition.py": "e" * 64,
             "scripts/deploy/verify_source_refresh_transition.py": "c" * 64}
    report["verifier"].update(files=files, source_sha256=_digest(files))
    source = report["source_intent"]
    report["source_intent"] = {
        "organ": source,
        "followup": {"rule_ids": ["4.2.46.clinical_annual_reassessment", "4.2.57.clinical_16_week_response"],
            "constraint_set": "followup_source_constraints", "evaluator_version": "followup.atomic.v2.2026-10-03",
            "summary_fields": sorted(projections["candidate"]["source_witnesses"]["followup"][0]["outcome"]["runtime_coverage"]),
            "clinical_eligibility_complete": False},
        "copay": {"canonical_manifest_verified": True, "fresh_coverage_verified": True,
                  "payment_permission_added": False},
    }
    report["source_cache_witnesses"] = {table: {
        side + "_sha256": _digest(_attested(projections[side]["tables"][table]))
        for side in ("baseline", "candidate")} for table in TABLES}
    report["source_api_witnesses"] = {side: {
        "coverage_summary_sha256": _digest(projections[side]["source_witnesses"]["copay"]["public_summary"]),
        "coverage_closure_sha256": _digest(projections[side]["source_witnesses"]["copay"]),
    } for side in ("baseline", "candidate")}
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    return report


def _old_replay_public_report():
    """Public cache projections retain their existing source and money contracts."""
    from tests.unit.deploy.test_raw_report_transport_source_profile import _historical_mainf28_tooling_bytes

    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    checkout = Path(final.__file__).resolve().parents[2]
    historical = _historical_mainf28_tooling_bytes(
        Path(__file__).parent / "fixtures/final_source_refresh_mainf28_tooling.json")
    pins = {path: _public_blob(historical[path] if path in historical else (checkout / path).read_bytes())
            for path in _PUBLIC_OLD_REPLAY_PATHS
            if path != "scripts/deploy/verify_final_source_refresh_transition.py"}
    manifest = {"profile": "bilun-old-replay-tooling-main00128-v1",
        "base_sha": "00128c6001c7921621b44537fcecefc22236b1f3",
        "base_tree": "ba09db1023be8ae17b5605145caefec771a7fbe5",
        "product_closure_sha256": "5236c656fe4d1989e8ec3a4e584c763928b00cb9f8a52053bac23f59b99ff9a3",
        "files": pins,
        "verifier": {"path": "scripts/deploy/verify_final_source_refresh_transition.py",
                     "mode": "100644", "type": "blob",
                     "normalized_sha256": final._REVIEWED_OLD_REPLAY_SELF_SHA256}}
    report["history"].update(
        integration_seed_sha=None, integration_seed_tree=None,
        descendant_commits=[report["candidate_code_sha"]],
        authorized_changed_paths=list(_PUBLIC_OLD_REPLAY_PATHS),
        product_closure_sha256=manifest["product_closure_sha256"],
        tooling_profile=manifest["profile"], tooling_base_sha=manifest["base_sha"],
        tooling_base_tree=manifest["base_tree"], reviewed_tooling_sha256=_digest(manifest))
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    return report


def test_old_replay_report_has_only_the_closed_twelve_field_tooling_addendum():
    report = _old_replay_public_report()
    final.validate_transition_report_contract(report)
    assert set(report["history"]) == {
        "product_anchor_sha", "product_anchor_tree", "candidate_sha", "descendant_commits",
        "authorized_changed_paths", "integration_seed_sha", "integration_seed_tree",
        "product_closure_sha256", "tooling_profile", "tooling_base_sha", "tooling_base_tree",
        "reviewed_tooling_sha256",
    }
    assert report["source_intent"]["followup"]["clinical_eligibility_complete"] is False
    assert report["source_intent"]["copay"]["payment_permission_added"] is False
    assert report["source_projected_table_count"] == 19
    assert report["strict_table_count"] == 13


@pytest.mark.parametrize("mutation", [
    "wrong_profile", "profile_bool", "missing_profile", "wrong_base", "base_bool",
    "wrong_base_tree", "base_tree_none", "wrong_anchor", "wrong_anchor_tree", "wrong_closure",
    "closure_bool", "wrong_tooling_digest", "tooling_digest_none", "missing_addendum_field",
    "old_seed", "mixed_seed", "false_seed", "seed_tree_only", "extra_descendant", "empty_descendants",
    "wrong_candidate", "candidate_bool", "missing_path", "extra_path", "duplicate_path",
    "unsorted_paths", "roster_tuple", "candidate_tree", "extra_field", "wrong_verifier",
    "wrong_replay_candidate",
])
def test_old_replay_report_rejects_resealed_history_or_execution_authority(mutation):
    report = _old_replay_public_report()
    history = report["history"]
    if mutation in {"wrong_profile", "profile_bool"}:
        history["tooling_profile"] = "future-profile" if mutation == "wrong_profile" else True
    elif mutation == "missing_profile":
        history.pop("tooling_profile")
    elif mutation in {"wrong_base", "base_bool", "wrong_base_tree", "base_tree_none"}:
        key = "tooling_base_tree" if "tree" in mutation else "tooling_base_sha"
        history[key] = True if mutation == "base_bool" else None if mutation == "base_tree_none" else "f" * 40
    elif mutation in {"wrong_anchor", "wrong_anchor_tree"}:
        history["product_anchor_tree" if mutation.endswith("tree") else "product_anchor_sha"] = "f" * 40
    elif mutation in {"wrong_closure", "closure_bool", "wrong_tooling_digest", "tooling_digest_none"}:
        key = "product_closure_sha256" if mutation.startswith("wrong_closure") or mutation == "closure_bool" else "reviewed_tooling_sha256"
        history[key] = True if mutation == "closure_bool" else None if mutation == "tooling_digest_none" else "f" * 64
    elif mutation == "missing_addendum_field":
        history.pop("tooling_base_tree")
    elif mutation in {"old_seed", "mixed_seed", "false_seed"}:
        history["integration_seed_sha"] = False if mutation == "false_seed" else final.INTEGRATION_SEED_SHA
        if mutation == "old_seed":
            history["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    elif mutation == "seed_tree_only":
        history["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    elif mutation in {"extra_descendant", "empty_descendants"}:
        history["descendant_commits"] = [] if mutation == "empty_descendants" else ["b" * 40, report["candidate_code_sha"]]
    elif mutation in {"wrong_candidate", "candidate_bool"}:
        history["candidate_sha"] = False if mutation == "candidate_bool" else "b" * 40
    elif mutation in {"missing_path", "extra_path", "duplicate_path", "unsorted_paths", "roster_tuple"}:
        paths = history["authorized_changed_paths"]
        if mutation == "missing_path":
            paths.pop()
        elif mutation == "extra_path":
            paths.append("scripts/deploy/extra.py")
            paths.sort()
        elif mutation == "duplicate_path":
            paths.append(paths[-1])
        elif mutation == "unsorted_paths":
            paths.reverse()
        else:
            history["authorized_changed_paths"] = tuple(paths)
    elif mutation in {"candidate_tree", "extra_field"}:
        history["candidate_tree" if mutation == "candidate_tree" else "future_permission"] = "f" * 40
    elif mutation == "wrong_verifier":
        report["verifier"]["verifier_sha"] = "b" * 40
    else:
        report["replay_checkouts"]["candidate"]["code_sha"] = "b" * 40
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


@pytest.mark.parametrize("mutation", ["new_paths_only", "partial_addendum", "old_seed_new_profile"])
def test_historical_reports_cannot_inherit_new_tooling_permissions_by_resealing(mutation):
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    if mutation == "new_paths_only":
        report["history"]["authorized_changed_paths"] = list(_PUBLIC_OLD_REPLAY_PATHS)
    elif mutation == "partial_addendum":
        report["history"]["tooling_profile"] = "bilun-old-replay-tooling-main00128-v1"
    else:
        fresh = _old_replay_public_report()
        report["history"] = fresh["history"]
        report["history"]["integration_seed_sha"] = final.INTEGRATION_SEED_SHA
        report["history"]["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
        if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


def _public_proof():
    old, new = _public_final_pair()
    pair = {"baseline": old, "candidate": new}
    projections = {side: {"tables": row["tables"], "followup": row["source_witnesses"]["followup"]}
                   for side, row in pair.items()}
    return final._issue_proof(_final_report(pair), projections)


def _cached(proof, table, side):
    value = copy.deepcopy(proof.projections[side]["tables"][table])
    if table == "wavea_evidence_index":
        value["build_id"] = side + "-build"
    elif table in {"wavea_evidence_detail", "wavea_bill_evidence_detail"}:
        for row in value.values():
            row["build_id"] = side + "-build"
    return value


def test_final_proof_is_detached_and_immutable():
    proof = _public_proof()
    final.validate_transition_report_contract(proof.report)
    proof.report["status"] = "forged"
    proof.projections["candidate"]["tables"].clear()
    assert proof.report["status"] == "final_source_refresh_transition_verified"
    assert len(proof.projections["candidate"]["tables"]) == 19
    with pytest.raises(FrozenInstanceError):
        proof._report_json = "{}"


@pytest.mark.parametrize("mutation", [
    None, "mixed_seed_sha", "mixed_seed_tree", "false_seed_sha", "false_seed_tree",
    "descendant_chain", "empty_descendants", "wrong_candidate", "extra_history_key", "prior_tooling_permission",
])
def test_normal_squash_report_has_only_closed_product_anchor_history(mutation):
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    history = report["history"]
    history.update(integration_seed_sha=None, integration_seed_tree=None,
                   descendant_commits=[report["candidate_code_sha"]])
    if mutation == "mixed_seed_sha":
        history["integration_seed_sha"] = final.INTEGRATION_SEED_SHA
    elif mutation == "mixed_seed_tree":
        history["integration_seed_tree"] = final.INTEGRATION_SEED_TREE
    elif mutation == "false_seed_sha":
        history["integration_seed_sha"] = False
    elif mutation == "false_seed_tree":
        history["integration_seed_tree"] = False
    elif mutation == "descendant_chain":
        history["descendant_commits"].insert(0, "b" * 40)
    elif mutation == "empty_descendants":
        history["descendant_commits"] = []
    elif mutation == "wrong_candidate":
        history["candidate_sha"] = "b" * 40
    elif mutation == "extra_history_key":
        history["squash_permission"] = True
    elif mutation == "prior_tooling_permission":
        history["authorized_changed_paths"] = ["scripts/deploy/verify_source_refresh_transition.py"]
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    if mutation is None:
        final.validate_transition_report_contract(report)
        assert set(history) == {"product_anchor_sha", "product_anchor_tree", "candidate_sha",
                               "descendant_commits", "authorized_changed_paths", "integration_seed_sha",
                               "integration_seed_tree", "product_closure_sha256"}
    else:
        with pytest.raises(ValueError):
            final.validate_transition_report_contract(report)


@pytest.mark.parametrize("table", TABLES)
def test_actual_cache_is_checked_against_its_own_source_before_normalization(table):
    proof = _public_proof()
    value = _cached(proof, table, "candidate")
    before = copy.deepcopy(value)
    result = final.normalize_transition_content(table, value, side="candidate", proof=proof)
    assert value == before
    expected = _cached(proof, table, "baseline") if table in OWNED_TABLES else before
    if table == "wavea_evidence_index":
        expected["build_id"] = "candidate-build"
    elif table in {"wavea_evidence_detail", "wavea_bill_evidence_detail"}:
        for row in expected.values():
            row["build_id"] = "candidate-build"
    assert result == expected


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("mutation", ["extra", "dropped", "wrong_type"])
def test_even_six_owned_tables_reject_cache_not_produced_by_its_own_source(table, mutation):
    proof = _public_proof()
    value = _cached(proof, table, "candidate")
    if mutation == "extra":
        if isinstance(value, list):
            value.append({"unproduced_row": True})
        else:
            value["unproduced_field"] = True
    elif mutation == "dropped":
        if isinstance(value, list):
            value.pop()
        else:
            value.pop(next(iter(value)))
    else:
        value = [] if isinstance(value, dict) else {}
    with pytest.raises(ValueError):
        final.normalize_transition_content(table, value, side="candidate", proof=proof)


@pytest.mark.parametrize("mutation", ["manual", "report", "projections", "seal", "copied"])
def test_manual_or_tampered_proof_is_rejected_before_any_cache_permission(mutation):
    proof = _public_proof()
    value = _cached(proof, "cohort_compliance_index", "candidate")
    if mutation == "manual":
        proof = final.FinalSourceRefreshProof(proof._report_json, proof._projections_json, object())
    elif mutation == "report":
        object.__setattr__(proof, "_report_json", "{}")
    elif mutation == "projections":
        object.__setattr__(proof, "_projections_json", "{}")
    elif mutation == "seal":
        object.__setattr__(proof, "_seal", object())
    else:
        proof = copy.deepcopy(proof)
    with pytest.raises(ValueError):
        final.normalize_transition_content("cohort_compliance_index", value, side="candidate", proof=proof)


@pytest.mark.parametrize("mutation", [
    "unknown_contract", "wrong_status", "candidate", "verifier", "seed", "anchor", "closure",
    "old_tool_path", "source_counter", "clinical_true", "copay_permission", "input_config",
    "input_count_float", "input_source", "cache_missing", "cache_extra", "cache_digest_type",
    "api_missing", "api_extra", "api_digest_short", "strict_count_bool", "table_count_float",
    "future_contract", "report_extra", "missing_digest", "protected_fields",
])
def test_saved_report_cannot_gain_authority_by_resealing_changed_metadata(mutation):
    old, new = _public_final_pair()
    report = _final_report({"baseline": old, "candidate": new})
    if mutation == "unknown_contract":
        report["contract"] = "future-unknown-profile"
    elif mutation == "wrong_status":
        report["status"] = "source_refresh_transition_verified"
    elif mutation == "candidate":
        report["candidate_code_sha"] = "b" * 40
    elif mutation == "verifier":
        report["verifier"]["verifier_sha"] = "b" * 40
    elif mutation in {"seed", "anchor", "closure"}:
        key = {"seed": "integration_seed_sha", "anchor": "product_anchor_sha", "closure": "product_closure_sha256"}[mutation]
        report["history"][key] = "b" * (64 if mutation == "closure" else 40)
        if mutation == "closure":
            report["history"][key] = None
    elif mutation == "old_tool_path":
        report["history"]["authorized_changed_paths"] = ["scripts/deploy/verify_source_refresh_transition.py"]
    elif mutation == "source_counter":
        report["source_intent"]["followup"]["summary_fields"].append("future_counter")
    elif mutation == "clinical_true":
        report["source_intent"]["followup"]["clinical_eligibility_complete"] = True
    elif mutation == "copay_permission":
        report["source_intent"]["copay"]["payment_permission_added"] = True
    elif mutation == "input_config":
        report["same_input"]["candidate"]["config_hash"] = "b" * 64
    elif mutation == "input_count_float":
        report["same_input"]["input_file_count"] = 12.0
    elif mutation == "input_source":
        report["same_input"]["baseline"]["source_hash"] = "b" * 64
    elif mutation == "cache_missing":
        report["source_cache_witnesses"].pop("patient_meta")
    elif mutation == "cache_extra":
        report["source_cache_witnesses"]["new_table"] = {"baseline_sha256": "a" * 64, "candidate_sha256": "b" * 64}
    elif mutation == "cache_digest_type":
        report["source_cache_witnesses"]["patient_meta"]["candidate_sha256"] = 0
    elif mutation == "api_missing":
        report["source_api_witnesses"].pop("candidate")
    elif mutation == "api_extra":
        report["source_api_witnesses"]["candidate"]["future_digest"] = "b" * 64
    elif mutation == "api_digest_short":
        report["source_api_witnesses"]["candidate"]["coverage_summary_sha256"] = "b" * 63
    elif mutation == "strict_count_bool":
        report["strict_table_count"] = True
    elif mutation == "table_count_float":
        report["source_projected_table_count"] = 19.0
    elif mutation == "future_contract":
        report["cache_comparison_contract"] = "defer_own_source_checks"
    elif mutation == "report_extra":
        report["future_permission"] = True
    elif mutation == "protected_fields":
        report["protected_fields"] = "all_fields_unchanged"
    else:
        report.pop("candidate_replay_sha256")
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    with pytest.raises(ValueError):
        final.validate_transition_report_contract(report)


@pytest.mark.parametrize("field,value", [
    ("status", "unverified"), ("input_bytes_sha256", "f" * 64), ("input_file_count", 12.0),
    ("input_file_count", 11), ("data_mode", "real_claims"),
])
def test_wrong_same_input_stops_before_source_reads(tmp_path, monkeypatch, field, value):
    proof = _public_proof()
    inputs = proof.report["same_input"]
    inputs[field] = value
    monkeypatch.setattr(final, "_roster", lambda *_: pytest.fail("Unbound inputs reached source reads"))
    with pytest.raises(ValueError):
        final.verify_transition(request=_request(), baseline_roster=tmp_path / "old.json",
            candidate_roster=tmp_path / "new.json",
            baseline_meta={"code_sha": final.BASELINE_CODE_SHA, "source_hash": final.BASELINE_SOURCE_HASH,
                           "config_hash": final.BASELINE_CONFIG_HASH},
            candidate_meta={"code_sha": "a" * 40, "config_hash": final.BASELINE_CONFIG_HASH},
            same_input=inputs, python_executable=Path(sys.executable), dependency_roots=(),
            expected_candidate_sha="a" * 40)


@pytest.mark.parametrize("wrong", ["request_candidate", "request_verifier", "argument_verifier", "baseline", "candidate", "config"])
def test_wrong_request_or_cache_pin_stops_before_source_reads(tmp_path, monkeypatch, wrong):
    proof = _public_proof()
    args = dict(request=_request(), baseline_roster=tmp_path / "old.json", candidate_roster=tmp_path / "new.json",
        baseline_meta={"code_sha": final.BASELINE_CODE_SHA, "source_hash": final.BASELINE_SOURCE_HASH,
                       "config_hash": final.BASELINE_CONFIG_HASH},
        candidate_meta={"code_sha": "a" * 40, "config_hash": final.BASELINE_CONFIG_HASH},
        same_input=proof.report["same_input"], python_executable=Path(sys.executable), dependency_roots=(),
        expected_candidate_sha="a" * 40)
    if wrong == "request_candidate":
        args["request"].update(expected_candidate_sha="b" * 40, expected_verifier_sha="b" * 40)
    elif wrong == "request_verifier":
        args["request"]["expected_verifier_sha"] = "b" * 40
    elif wrong == "argument_verifier":
        args["expected_verifier_sha"] = "b" * 40
    elif wrong == "baseline":
        args["baseline_meta"]["code_sha"] = "b" * 40
    elif wrong == "candidate":
        args["candidate_meta"]["code_sha"] = "b" * 40
    else:
        args["candidate_meta"]["config_hash"] = "b" * 64
    monkeypatch.setattr(final, "_roster", lambda *_: pytest.fail("Wrong pin reached source reads"))
    with pytest.raises(ValueError):
        final.verify_transition(**args)


def test_prepare_carries_exact_final_opt_in_to_semantics_rehearsal_and_issuer(machine, monkeypatch):
    """Existing fabricated prepare boundaries; no real child or live service."""
    manifest, spec, _, original = machine
    request = _request(spec["target_sha"])
    spec["clinical_transition"] = request
    private_json(manifest, spec)
    calls = []
    semantic, rehearse, issue = (preparation.verify_candidate_semantic_checkpoint,
                               preparation._rehearse, preparation.issue_wavea_activation)
    def verify(*args, **kwargs):
        assert kwargs["clinical_transition"] == request
        calls.append("semantic")
        return semantic(*args, **kwargs)
    def namespace(*args):
        assert args[0]["clinical_transition"] == request
        calls.append("rehearsal")
        return rehearse(*args)
    def receipt(**kwargs):
        assert kwargs["clinical_transition"] == request
        calls.append("issuer")
        return issue(**kwargs)
    monkeypatch.setattr(preparation, "verify_candidate_semantic_checkpoint", verify)
    monkeypatch.setattr(preparation, "_rehearse", namespace)
    monkeypatch.setattr(preparation, "issue_wavea_activation", receipt)
    result = preparation.prepare_release_bundle(manifest)
    assert result["production_mutated"] is False
    assert calls == ["semantic", "rehearsal", "issuer"]
    assert Path(spec["live_cache_path"]).read_bytes() == original


def test_semantic_checkpoint_dispatches_final_proof_and_keeps_release_unready(tmp_path, monkeypatch):
    """Controller seam only; full source/cache values have separate tests."""
    baseline, candidate, roster = _current_fixture(tmp_path)
    proof = _public_proof()
    request = _request(proof.report["candidate_code_sha"])
    calls = []
    monkeypatch.setattr(semantics, "verify_same_input_rosters", lambda *_args, **_kw: proof.report["same_input"])
    def replay(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == "a" * 40
        calls.append("replay")
        return proof
    def parity(*_args, **kwargs):
        assert kwargs["clinical_transition"] is proof
        calls.append("parity")
        return {"candidate_code_sha": "a" * 40, "source_hash": "c" * 64}, {}
    monkeypatch.setattr(final, "verify_transition", replay)
    monkeypatch.setattr(semantics, "_check_legacy_parity", parity)
    monkeypatch.setattr(semantics, "_check_evidence", lambda *_args: ({}, []))
    before = {path: path.read_bytes() for path in (baseline, candidate)}
    report = semantics.verify_candidate_semantic_checkpoint(baseline, baseline_build_id="baseline",
        candidate_db=candidate, candidate_build_id="candidate", source_roster=roster,
        baseline_roster=tmp_path / "old-roster.json", build_config_environment={},
        clinical_transition=request, python_executable=Path(sys.executable), dependency_roots=(Path(sys.base_prefix),))
    assert report["clinical_transition"] == proof.report
    assert report["release_ready"] is False
    assert calls == ["replay", "parity"]
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("mutation", [None, "saved", "saved_hash", "relative_locator", "wrong_head"])
def test_issuer_requires_fresh_final_proof_matching_saved_mirror(tmp_path, monkeypatch, mutation):
    arguments, request, fresh, source_path, raw_path = _issuer_transition_fixture(tmp_path, monkeypatch)
    request["contract"] = CONTRACT
    fresh["clinical_transition"] = _public_proof().report
    raw = json.loads(raw_path.read_text())
    raw["source_report_sha256"] = private_json(source_path, fresh)
    if mutation == "saved":
        saved = copy.deepcopy(fresh)
        saved["clinical_transition"]["neutral_raw_rows"] += 1
        saved["clinical_transition"]["transition_sha256"] = _digest({key: value
            for key, value in saved["clinical_transition"].items() if key not in {"status", "transition_sha256"}})
        raw["source_report_sha256"] = private_json(source_path, saved)
    elif mutation == "saved_hash":
        raw["source_report_sha256"] = "f" * 64
    elif mutation == "relative_locator":
        raw["source_report_path"] = source_path.name
    elif mutation == "wrong_head":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    private_json(raw_path, raw)
    if mutation is None:
        assert issuer.issue_wavea_activation(**arguments)["status"] == "private_activation_receipt_issued"
    else:
        with pytest.raises(ValueError):
            issuer.issue_wavea_activation(**arguments)
        assert not arguments["key_path"].exists()
        assert not arguments["receipt_path"].exists()


@pytest.mark.parametrize("mutation", [None, "unknown", "wrong_pin"])
def test_namespace_rehearsal_carries_final_request_and_stops_wrong_pin_before_children(tmp_path, monkeypatch, mutation):
    args, work, events, _ = fixture_rehearsal(tmp_path, monkeypatch)
    request = _request()
    if mutation == "unknown":
        request["contract"] = "unreviewed-profile"
    elif mutation == "wrong_pin":
        request.update(expected_candidate_sha="f" * 40, expected_verifier_sha="f" * 40)
    path = tmp_path / "request.json"
    private_json(path, request)
    args.extend(("--clinical-transition", str(path)))
    proof, calls = _public_proof(), []
    class Database:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
    monkeypatch.setattr(rehearsal.duckdb, "connect", lambda *_args, **_kw: Database())
    monkeypatch.setattr(rehearsal, "_build_metadata", lambda *_: {"code_sha": "a" * 40})
    def verify(**kwargs):
        assert kwargs["request"] == request
        assert kwargs["expected_candidate_sha"] == kwargs["expected_verifier_sha"] == "a" * 40
        calls.append("replay")
        return proof
    def normalize(reports, **kwargs):
        assert kwargs["proof"] is proof
        calls.append(kwargs["side"])
        return reports
    monkeypatch.setattr(final, "verify_transition", verify)
    monkeypatch.setattr(final, "normalize_transition_http_reports", normalize)
    if mutation is None:
        rehearsal.main(args)
        assert calls == ["replay", "baseline", "candidate"]
        assert json.loads((work / "clinical-transition-rehearsal.json").read_text()) == proof.report
    else:
        with pytest.raises(ValueError):
            rehearsal.main(args)
        assert calls == []
        assert not any(event.startswith("start:") for event in events)


def _private_final_fixture(tmp_path):
    path, observed, candidate, runtime, rehearsal_report, observation = sealed_rehearsal(tmp_path)
    fresh = _public_proof().report
    candidate["source_hash"] = fresh["same_input"]["candidate"]["source_hash"]
    observation["logical_tuple"]["cache"]["source_hash"] = candidate["source_hash"]
    observation["tuple_sha256"] = _digest(observation["logical_tuple"])
    rehearsal_report["candidate_tuple_sha256"] = observation["tuple_sha256"]
    rehearsal_report["candidate_tuple_observation_sha256"] = private_json(observed, observation)
    files = {}
    for name in ("verify_final_source_refresh_transition.py", "verify_source_refresh_transition.py"):
        producer = runtime / "scripts/deploy" / name
        producer.write_text("# public reviewed fixture producer\n")
        files["scripts/deploy/" + name] = hashlib.sha256(producer.read_bytes()).hexdigest()
    name = "scripts/deploy/rehearse_wavea_same_port.py"
    files[name] = hashlib.sha256((runtime / name).read_bytes()).hexdigest()
    fresh["verifier"] = {"verifier_sha": candidate["code_sha"], "files": files, "source_sha256": _digest(files)}
    fresh["transition_sha256"] = _digest({key: value for key, value in fresh.items()
                                         if key not in {"status", "transition_sha256"}})
    rehearsal_report["same_input_proof_sha256"] = private_json(tmp_path / "same-input-rehearsal.json", fresh["same_input"])
    rehearsal_report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, rehearsal_report)
    return path, observed, candidate, runtime, rehearsal_report, fresh


@pytest.mark.parametrize("mutation", [None, "unknown", "wrong_status", "wrong_pin", "changed_source", "saved_mirror", "saved_hash", "unrequested"])
def test_private_rehearsal_accepts_only_fresh_final_source_input_and_saved_proof(tmp_path, mutation):
    path, observed, candidate, runtime, report, fresh = _private_final_fixture(tmp_path)
    supplied = fresh
    if mutation == "unknown":
        fresh["contract"] = "unknown-profile"
    elif mutation == "wrong_status":
        fresh["status"] = "source_refresh_transition_verified"
    elif mutation == "wrong_pin":
        fresh["candidate_code_sha"] = "f" * 40
    elif mutation == "changed_source":
        (runtime / "scripts/deploy/verify_final_source_refresh_transition.py").write_text("# changed\n")
    elif mutation == "saved_mirror":
        saved = copy.deepcopy(fresh)
        saved["followup_line_count"] += 1
        saved["transition_sha256"] = _digest({key: value for key, value in saved.items()
                                             if key not in {"status", "transition_sha256"}})
        report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", saved)
    elif mutation == "saved_hash":
        report["clinical_transition_report_sha256"] = "f" * 64
    elif mutation == "unrequested":
        supplied = None
    if mutation in {"unknown", "wrong_status", "wrong_pin"}:
        fresh["transition_sha256"] = _digest({key: value for key, value in fresh.items()
                                             if key not in {"status", "transition_sha256"}})
        report["clinical_transition_report_sha256"] = private_json(tmp_path / "clinical-transition-rehearsal.json", fresh)
    private_json(path, report)
    if mutation is None:
        assert verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime,
            clinical_transition=fresh)["status"] == "private_pair_rehearsal_verified"
    else:
        with pytest.raises(ValueError):
            verify_private_rehearsal(path, observed, candidate=candidate, backend_runtime=runtime, clinical_transition=supplied)


@pytest.mark.parametrize("mutation", ["partial", "wrong_status", "wrong_seed", "unknown_source_closure"])
def test_real_signed_loader_rejects_resealed_final_profile_with_unbound_metadata(signed_bundle, mutation):
    source_path = signed_bundle.root / "semantic.json"
    source = json.loads(source_path.read_text())
    report = _public_proof().report
    if mutation == "partial":
        report.pop("source_cache_witnesses")
    elif mutation == "wrong_status":
        report["status"] = "clinical_semantic_transition_verified"
    elif mutation == "wrong_seed":
        report["history"]["integration_seed_sha"] = "f" * 40
    else:
        report["verifier"]["files"] = {}
        report["verifier"]["source_sha256"] = _digest({})
    report["transition_sha256"] = _digest({key: value for key, value in report.items()
                                          if key not in {"status", "transition_sha256"}})
    source["clinical_transition"] = report
    private_json(source_path, source)
    signed_startup._reseal_semantic(signed_bundle, mirror_rehearsal=True)
    with pytest.raises(ValueError):
        signed_startup._candidate_load(signed_bundle)


@pytest.mark.parametrize("view", ["draft", "legacy"])
def test_http_serializer_keeps_same_line_owned_final_annotations_payment_neutral(monkeypatch, view):
    proof, packages = _public_proof(), {}
    for side in ("baseline", "candidate"):
        tables = proof.projections[side]["tables"]
        packages[side] = fabricated_transport(monkeypatch, {
            "/api/billing-report/P1": copy.deepcopy(tables["patient_billing_report_rows"]["P1"]),
            "/api/billing-report/P1/bills/C1": copy.deepcopy(tables["patient_bill_billing_report_rows"]["P1::C1"]),
        }, code_sha=proof.report[side + "_code_sha"], repository=Path("/public-fixture") / side)
    old, new = packages["baseline"], packages["candidate"]
    old_reports = old.draft_reports if view == "draft" else {path: semantics._legacy_report(row) for path, row in old.complete_reports.items()}
    new_reports = new.draft_reports if view == "draft" else {path: semantics._legacy_report(row) for path, row in new.complete_reports.items()}
    actual = final.normalize_transition_http_reports(new_reports, side="candidate", proof=proof,
        transport=new, baseline_transport=old, view=view)
    assert actual == old_reports


@pytest.fixture
def authored_final_source(tmp_path, monkeypatch):
    """Public Git objects and public corpus bytes, independently of cache values."""
    import polars as pl
    old, new = _public_final_pair()
    checkout = tmp_path / "public-authored-source"
    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "config", "user.email", "source@example.invalid")
    _git(checkout, "config", "user.name", "Public source fixture")
    organ = checkout / "data/gazette/prose_rules/treatment_pricing_2_4.json"
    followup = checkout / "data/gazette/prose_rules/drug_indication_prose.json"
    corpus = checkout / "data/gazette/sut_clauses.parquet"
    organ.parent.mkdir(parents=True)
    organ.write_text(json.dumps(old["rules"]))
    followup.write_text(json.dumps({"rules": old["source_witnesses"]["followup_rules"]}))
    pl.DataFrame(old["source_witnesses"]["followup_source_clauses"]).write_parquet(corpus)
    baseline = _commit(checkout, "public authored baseline")
    organ.write_text(json.dumps(new["rules"]))
    anchor = _commit(checkout, "public source quarantine")
    for module in (final, frozen):
        monkeypatch.setattr(module, "BASELINE_CODE_SHA", baseline)
        monkeypatch.setattr(module, "PRODUCT_ANCHOR_SHA", anchor)
    monkeypatch.setattr(frozen, "BASELINE_SOURCE_BLOB", _git(checkout, "rev-parse", baseline + ":" + frozen.SOURCE_PATH))
    monkeypatch.setattr(frozen, "PRODUCT_SOURCE_BLOB", _git(checkout, "rev-parse", anchor + ":" + frozen.SOURCE_PATH))
    return {"checkout": str(checkout)}, old, new


def test_followup_authored_rules_and_full_public_corpus_match_own_checkout(authored_final_source):
    roster, old, new = authored_final_source
    intent = final._source_intent(roster, roster, old, new)
    assert intent["followup"]["clinical_eligibility_complete"] is False
    assert intent["copay"]["payment_permission_added"] is False
    assert intent["followup"]["rule_ids"] == [
        "4.2.46.clinical_annual_reassessment", "4.2.57.clinical_16_week_response"]


@pytest.mark.parametrize("side", ["old", "new"])
@pytest.mark.parametrize("mutation", ["authored_rule", "source_body", "source_hash", "source_id", "source_status", "source_missing"])
def test_forged_source_inventory_cannot_be_resealed_as_own_rules_or_corpus(authored_final_source, side, mutation):
    roster, old, new = authored_final_source
    sources = (old if side == "old" else new)["source_witnesses"]
    if mutation == "authored_rule":
        sources["followup_rules"][0]["drug_names"] = ["unrelated drug"]
    elif mutation == "source_missing":
        sources["followup_source_clauses"] = []
    else:
        row = sources["followup_source_clauses"][0]
        field, value = {
            "source_body": ("text", "Forged payment authority"),
            "source_hash": ("content_hash", "f" * 64),
            "source_id": ("clause_id", "CF000099"),
            "source_status": ("is_in_force", False),
        }[mutation]
        row[field] = value
    with pytest.raises(ValueError):
        final._source_intent(roster, roster, old, new)


def _copay_source_rows():
    keys = [
        "1.8.5.(7)#fb187fbe", "1.8.2.(3)#04043a39", "1.8.5.(8)#2c30921a",
        "1.8.5.(5)#424f9787", "1.8.5.(6)#989e2ee8", "1.8.5.(1)#27612764",
        "1.8.5.(11)#4c5d2bce", "1.8.5.(12)#b67e143b", "1.8.5.(13)#3697a89c",
        "1.8.5.(15)#05de89cd", "1.8.5.(16)#89cd1467", "1.8.5.a#a2615b26",
    ]
    return [{"clause_id": f"C{index:06}", "clause_key": key, "is_in_force": True}
            for index, key in enumerate(keys, 1)]


def test_real_copay_resolver_uses_stable_keys_and_never_promotes_deferred_runtime_traces():
    import polars as pl
    from scripts.sut.prose.gate_b_generic import _resolve_copay_compositor_clause_traces
    traces, encoded = _resolve_copay_compositor_clause_traces(pl.DataFrame(_copay_source_rows()))
    assert traces == {
        "copay_exemption_ek1a": ["C000001"], "copay_exemption_ek4d": ["C000002", "C000003"],
        "copay_exemption_visit_type": ["C000004", "C000005"],
        "copay_exemption_occupational": ["C000006"],
        "copay_exemption_patient_status": ["C000007", "C000008", "C000009", "C000010", "C000011", "C000012"],
    }
    assert encoded == set()


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "stale_key", "inactive", "inactive_type", "missing_key"])
def test_copay_current_key_resolution_rejects_stale_duplicate_or_nonactive_source(mutation):
    import polars as pl
    from scripts.sut.prose.gate_b_generic import _resolve_copay_compositor_clause_traces
    rows = _copay_source_rows()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "stale_key":
        rows[0]["clause_key"] = "1.8.5.(7)#00000000"
    elif mutation == "inactive":
        rows[0]["is_in_force"] = False
    elif mutation == "inactive_type":
        for row in rows:
            row["is_in_force"] = 1
    else:
        for row in rows:
            row.pop("clause_key")
    with pytest.raises(ValueError):
        _resolve_copay_compositor_clause_traces(pl.DataFrame(rows))
