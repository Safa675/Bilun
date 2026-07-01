"""Single parsing path for §4.2 drug indication prose manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.sut.audit_manifest_parity import (  # noqa: E402
    _BUCKET_LIST_KEYS,
    _STATUS_TO_LIST_KEY,
)

DEFAULT_MANIFEST_DIR = Path(__file__).resolve().parents[3] / "data/gazette/prose_manifests"
DRUG_MANIFEST_GLOBS: tuple[str, ...] = (
    "L4.2_drug_indication_*.json",
    "L4.33_anti_vegf_*.json",
)
_MANIFEST_CLAUSE_ID_KEYS = frozenset({"gate_b_sources_encoded", "encoded_clause_ids"})
_EXCLUDED_MANIFEST_CLAUSE_LIST_SUFFIXES = ("_deferred_clause_ids", "_pending_clause_ids")
_TRACE_BUCKET_KEYS: tuple[str, ...] = (
    "encoded_clause_ids",
    "tier_c_deferred_clause_ids",
    "emr_blocked_clause_ids",
    "non_actionable_clause_ids",
    "tier_a_pending_clause_ids",
    "tier_b_pending_clause_ids",
)


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def trace_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map clause_id → trace dict (list or dict ``clause_traces`` shapes)."""
    traces = payload.get("clause_traces")
    if isinstance(traces, list):
        return {
            str(t.get("clause_id")): dict(t)
            for t in traces
            if isinstance(t, dict) and t.get("clause_id")
        }
    if isinstance(traces, dict):
        return {str(k): dict(v) for k, v in traces.items() if isinstance(v, dict)}
    return {}


def write_traces(
    payload: dict[str, Any],
    traces: list | dict | None,
    trace_by_id: dict[str, dict[str, Any]],
) -> None:
    if isinstance(traces, list):
        payload["clause_traces"] = sorted(
            trace_by_id.values(),
            key=lambda t: str(t.get("clause_id", "")),
        )
    elif isinstance(traces, dict):
        payload["clause_traces"] = trace_by_id


def trace_index_with_shape(
    payload: dict[str, Any],
) -> tuple[list | dict | None, dict[str, dict[str, Any]]]:
    """Return raw ``clause_traces`` container plus indexed traces."""
    traces = payload.get("clause_traces")
    return traces, trace_index(payload)


def bucket_clause_ids(
    payload: dict[str, Any],
    *,
    status: str | None = None,
) -> frozenset[str]:
    """Clause IDs from bucket lists, optionally filtered by ``manifest_status``."""
    if status is not None:
        list_key = _STATUS_TO_LIST_KEY.get(status)
        if list_key is None:
            return frozenset()
        return frozenset(str(cid) for cid in (payload.get(list_key) or []))

    ids: set[str] = set()
    for key in _TRACE_BUCKET_KEYS:
        ids.update(str(cid) for cid in (payload.get(key) or []))
    return frozenset(ids)


def traced_clause_ids(payload: dict[str, Any]) -> frozenset[str]:
    """Union of all bucket lists plus ``clause_traces`` IDs (A1 semantics)."""
    traced = set(bucket_clause_ids(payload))
    for clause_id in trace_index(payload):
        traced.add(clause_id)
    return frozenset(traced)


def encoded_like_clause_ids(payload: dict[str, Any]) -> frozenset[str]:
    """Coverage semantics: encoded + gate_b_sources + non-deferred ``*_clause_ids``."""
    ids: set[str] = set()
    encoded = payload.get("encoded_clause_ids")
    if isinstance(encoded, list):
        ids.update(str(clause_id) for clause_id in encoded)
    for key, value in payload.items():
        if not isinstance(value, list):
            continue
        if key.endswith(_EXCLUDED_MANIFEST_CLAUSE_LIST_SUFFIXES):
            continue
        if key in _MANIFEST_CLAUSE_ID_KEYS or key.endswith("_clause_ids"):
            ids.update(str(clause_id) for clause_id in value)
    return frozenset(ids)


def manifest_clause_ids_and_tiers(path: Path) -> tuple[frozenset[str], dict[str, str]]:
    """All traced clause IDs plus encode_tier by clause (A0 semantics)."""
    if not path.is_file():
        return frozenset(), {}
    payload = load_manifest(path)
    manifest_ids: set[str] = set()
    tier_by_clause: dict[str, str] = {}

    traces_raw = payload.get("clause_traces") or []
    if isinstance(traces_raw, dict):
        for clause_ids in traces_raw.values():
            for clause_id in clause_ids or []:
                cid = str(clause_id)
                if cid:
                    manifest_ids.add(cid)
    else:
        for trace in traces_raw:
            if not isinstance(trace, dict):
                continue
            clause_id = str(trace.get("clause_id") or "")
            if not clause_id:
                continue
            manifest_ids.add(clause_id)
            tier = str(trace.get("encode_tier") or "")
            if tier:
                tier_by_clause[clause_id] = tier

    if not manifest_ids:
        manifest_ids.update(bucket_clause_ids(payload))

    return frozenset(manifest_ids), tier_by_clause


def iter_drug_manifest_paths(
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for pattern in DRUG_MANIFEST_GLOBS:
        for path in sorted(manifest_dir.glob(pattern)):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def load_all_drug_clause_ids(
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
) -> tuple[frozenset[str], dict[str, str]]:
    """Union clause IDs and encode tiers across all drug manifests."""
    manifest_ids: set[str] = set()
    tier_by_clause: dict[str, str] = {}
    for path in iter_drug_manifest_paths(manifest_dir):
        ids, tiers = manifest_clause_ids_and_tiers(path)
        manifest_ids |= ids
        tier_by_clause.update(tiers)
    return frozenset(manifest_ids), tier_by_clause


def load_drug_bucket_clause_ids(
    *,
    status: str,
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
) -> frozenset[str]:
    """Aggregate one manifest status bucket across all drug manifests."""
    ids: set[str] = set()
    for path in iter_drug_manifest_paths(manifest_dir):
        try:
            payload = load_manifest(path)
        except (OSError, json.JSONDecodeError):
            continue
        ids.update(bucket_clause_ids(payload, status=status))
    return frozenset(ids)


@dataclass(frozen=True)
class ClauseManifestRef:
    clause_id: str
    manifest_name: str
    manifest_status: str
    encode_tier: str
    trace: dict[str, Any]


@dataclass
class DrugManifestIndex:
    by_clause: dict[str, ClauseManifestRef] = field(default_factory=dict)
    all_clause_ids: frozenset[str] = frozenset()
    tier_by_clause: dict[str, str] = field(default_factory=dict)
    manifests_loaded: tuple[str, ...] = ()

    def get(self, clause_id: str) -> ClauseManifestRef | None:
        return self.by_clause.get(clause_id)


def build_drug_manifest_index(
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
) -> DrugManifestIndex:
    """Load all drug manifests indexed by clause_id."""
    by_clause: dict[str, ClauseManifestRef] = {}
    tier_by_clause: dict[str, str] = {}
    loaded: list[str] = []

    for path in iter_drug_manifest_paths(manifest_dir):
        try:
            payload = load_manifest(path)
        except (OSError, json.JSONDecodeError):
            continue
        loaded.append(path.name)
        for clause_id, trace in trace_index(payload).items():
            tier = str(trace.get("encode_tier") or "")
            if tier:
                tier_by_clause[clause_id] = tier
            by_clause[clause_id] = ClauseManifestRef(
                clause_id=clause_id,
                manifest_name=path.name,
                manifest_status=str(trace.get("manifest_status") or ""),
                encode_tier=tier,
                trace=trace,
            )

    all_ids, tiers_from_buckets = load_all_drug_clause_ids(manifest_dir)
    tier_by_clause.update(tiers_from_buckets)

    return DrugManifestIndex(
        by_clause=by_clause,
        all_clause_ids=all_ids,
        tier_by_clause=tier_by_clause,
        manifests_loaded=tuple(loaded),
    )


__all__ = [
    "BUCKET_LIST_KEYS",
    "DEFAULT_MANIFEST_DIR",
    "DRUG_MANIFEST_GLOBS",
    "STATUS_TO_LIST_KEY",
    "ClauseManifestRef",
    "DrugManifestIndex",
    "bucket_clause_ids",
    "build_drug_manifest_index",
    "encoded_like_clause_ids",
    "iter_drug_manifest_paths",
    "load_all_drug_clause_ids",
    "load_drug_bucket_clause_ids",
    "load_manifest",
    "manifest_clause_ids_and_tiers",
    "trace_index",
    "trace_index_with_shape",
    "traced_clause_ids",
    "write_traces",
]

# Re-export audit constants under stable names for callers.
BUCKET_LIST_KEYS = _BUCKET_LIST_KEYS
STATUS_TO_LIST_KEY = _STATUS_TO_LIST_KEY
