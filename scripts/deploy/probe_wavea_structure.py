"""Read populated old-backend Wave A structure; never export patient payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request

from scripts.deploy.health_request import open_probe, read_loopback_health
from scripts.deploy.capture_release_preflight import _runtime_digest, observe_service
from scripts.deploy.probe_auth import old_probe_context, probe_cookie
from scripts.deploy.rehearse_wavea_pair import environment
from scripts.deploy.verify_candidate_cache import _parse_json, _stable_file_hash
from scripts.deploy.prepare_isolated_semantic_stage import _path, _save

_KINDS = ("reviews", "advisories", "financial_rows")
_EXACTNESS = {"exact", "partial_exact", "missing_exact_inputs", "not_applicable"}


def _count(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Structural count is invalid")
    return value


def summarize_page(payload: Any) -> dict[str, Any]:
    if (not isinstance(payload, dict) or type(payload.get("available")) is not bool
            or not isinstance(payload.get("rows"), list)
            or not isinstance(payload.get("pagination"), dict)):
        raise ValueError("Evidence response shape is invalid")
    rows = payload["rows"]
    if len(rows) > 1 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Structural probe returned an unbounded page")
    total = payload["pagination"].get("total_matching")
    if payload["available"] is True and total is None:
        raise ValueError("Available evidence page lacks an exact count")
    return {"available": payload["available"], "sample_rows": len(rows),
            "total_rows": _count(total) if total is not None else None,
            "sample_has_patient_identity": bool(rows and isinstance(rows[0].get("patient_id"), str)),
            "sample_has_rule_identity": bool(rows and isinstance(rows[0].get("rule_id"), str)),
            "sample_has_evidence_identity": bool(rows and isinstance(rows[0].get("evidence_id"), str))}


def summarize_billing(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Billing response shape is invalid")
    result = {"header_has_patient_identity": isinstance(payload.get("patient_id"), str),
              "exactness_status": payload.get("exactness_status")
              if payload.get("exactness_status") in _EXACTNESS else "unknown", "blocks": {}}
    for name in ("claim_reviews", "claim_advisories", "financial_findings"):
        block = payload.get(name)
        if not isinstance(block, dict) or not isinstance(block.get("rows"), list):
            raise ValueError("Billing evidence block structure is invalid")
        result["blocks"][name] = {"available": block.get("available") is True,
            "sample_rows": len(block["rows"]),
            "total_rows": _count(block["total_rows"]) if block.get("total_rows") is not None else None}
    return result


def _probe_values(*, runtime: Path, runtime_sha256: str, values: dict[str, str],
                  code_sha: str, build_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise ValueError("Protected release expectation differs")
    context = old_probe_context(runtime, expected_runtime_sha256=runtime_sha256)
    cookie = probe_cookie(values, old_context=context)
    health = read_loopback_health(values)
    if health.get("code_sha") != code_sha or health.get("active_build") != build_id:
        raise ValueError("Running release identity differs")
    capability = health.get("wavea_capability")
    if capability not in {"complete-25-v1", "draft", "unavailable", None}:
        raise ValueError("Wave A capability identity is unknown")
    receipt = health.get("wavea_receipt_sha256")
    if receipt is not None and (not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt)):
        raise ValueError("Wave A receipt identity is malformed")

    def fetch(path: str) -> dict[str, Any]:
        request = Request("http://127.0.0.1:8001" + path, headers={"Cookie": cookie})
        with open_probe(request, timeout=5) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Structural API response exceeds its bound")
        return _parse_json(raw.decode(), context="private structural probe")

    pages, patient_id = {}, None
    for kind in _KINDS:
        raw = fetch("/api/wavea-evidence-rows?kind=" + kind + "&limit=1")
        pages[kind] = summarize_page(raw)
        if patient_id is None and raw["rows"]:
            patient_id = raw["rows"][0].get("patient_id")
        del raw
    billing = summarize_billing(fetch("/api/billing-report/" + quote(patient_id, safe=""))) \
        if isinstance(patient_id, str) and patient_id else None
    if old_probe_context(runtime, expected_runtime_sha256=runtime_sha256) != context:
        raise ValueError("Protected old runtime changed")
    return {"status": "old_backend_wavea_structure_observed", "code_sha": code_sha,
            "active_build": build_id, "wavea_capability": capability,
            "wavea_receipt_sha256": receipt, "pages": pages, "billing_sample": billing,
            "new_candidate_admitted": False, "signed_hybrid_pair_verified": False}


def probe_structure(*, runtime: Path, runtime_sha256: str, environment_path: Path,
                    environment_sha256: str, code_sha: str, build_id: str) -> dict[str, Any]:
    """Compatibility read of an already-existing private environment artifact."""
    from src.bilun.api.wavea_activation import _private_file

    _private_file(environment_path)
    if (not re.fullmatch(r"[0-9a-f]{64}", environment_sha256)
            or _stable_file_hash(environment_path) != environment_sha256):
        raise ValueError("Protected environment expectation differs")
    result = _probe_values(runtime=runtime, runtime_sha256=runtime_sha256,
        values=environment(environment_path), code_sha=code_sha, build_id=build_id)
    if _stable_file_hash(environment_path) != environment_sha256:
        raise ValueError("Protected environment changed")
    return result


def environment_values(raw: bytes) -> dict[str, str]:
    """Apply existing NUL environment semantics to bounded in-memory content."""
    if not isinstance(raw, bytes) or len(raw) > 65536 or not raw.endswith(b"\0"):
        raise ValueError("Current process environment is not bounded NUL content")
    values = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        key, separator, value = item.partition(b"=")
        name = key.decode()
        if not separator or not name or name in values:
            raise ValueError("Current process environment identity is ambiguous")
        values[name] = value.decode("utf-8", "surrogateescape")
    return values


def validate_capture_stage(parent: Path, stage: Path) -> None:
    parent = _path(str(parent))
    stage = _path(str(stage), existing=False)
    if (not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077
            or stage.parent != parent or stage.exists() or stage.is_symlink()):
        raise ValueError("Capture must be an absent direct child of the approved private parent")


def capture_and_probe(*, parent: Path, stage: Path, code_sha: str, build_id: str) -> dict[str, Any]:
    """Capture the currently running process, never a previous release inventory."""
    validate_capture_stage(parent, stage)
    observed = observe_service("bilun-backend.service", 8001)
    runtime = observed.process_working_directory
    protected = [runtime, observed.process_executable, *observed.unit_files, *observed.environment_files]
    if any(stage == path or stage.is_relative_to(path) or path.is_relative_to(stage) for path in protected):
        raise ValueError("Capture stage overlaps serving runtime or configuration")
    runtime_sha = _runtime_digest(runtime, backend=True)
    with Path(f"/proc/{observed.listener_pid}/environ").open("rb") as handle:
        raw = handle.read(65537)
    values = environment_values(raw)
    effective_sha = hashlib.sha256(b"\0".join(sorted(item for item in raw.split(b"\0") if item))).hexdigest()
    if effective_sha != observed.environment_sha256 or observe_service(observed.unit, 8001) != observed:
        raise ValueError("Current service changed during private capture")
    del raw
    result = _probe_values(runtime=runtime, runtime_sha256=runtime_sha, values=values,
        code_sha=code_sha, build_id=build_id)
    values.clear()
    if observe_service(observed.unit, 8001) != observed or _runtime_digest(runtime, backend=True) != runtime_sha:
        raise ValueError("Current service changed after structural probe")
    capture = {"source": "current-systemd-listener-proc-environ", "unit": observed.unit,
        "listener_pid": observed.listener_pid, "main_pid": observed.main_pid,
        "process_started_at_utc": observed.process_started_at_utc.isoformat(),
        "runtime_path": str(runtime), "runtime_sha256": runtime_sha,
        "effective_environment_sha256": effective_sha, "unit_sha256": observed.unit_sha256,
        "code_sha": code_sha, "active_build": build_id}
    stage.mkdir(mode=0o700)
    _save(stage / "current-capture.json", capture)
    result["current_capture"] = capture
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--runtime-sha256")
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--environment-sha256")
    parser.add_argument("--capture-parent", type=Path)
    parser.add_argument("--capture-stage", type=Path)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--build-id", required=True)
    args = parser.parse_args()
    try:
        if os.getuid() != 0:
            raise ValueError("This protected structural probe is root-coordinator/VPS only")
        explicit = (args.runtime, args.runtime_sha256, args.environment, args.environment_sha256)
        if args.capture_parent is not None or args.capture_stage is not None:
            if args.capture_parent is None or args.capture_stage is None or any(item is not None for item in explicit):
                raise ValueError("Capture and explicit inventory modes cannot be mixed")
            result = capture_and_probe(parent=args.capture_parent, stage=args.capture_stage,
                code_sha=args.code_sha, build_id=args.build_id)
        else:
            if any(item is None for item in explicit):
                raise ValueError("Explicit current inventory is incomplete")
            result = probe_structure(runtime=args.runtime, runtime_sha256=args.runtime_sha256,
                environment_path=args.environment, environment_sha256=args.environment_sha256,
                code_sha=args.code_sha, build_id=args.build_id)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "old_backend_structure_probe_failed", "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
