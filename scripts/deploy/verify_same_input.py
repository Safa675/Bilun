"""Prove byte-identical claim inputs across isolated baseline/candidate builds.

Build metadata's historical source hash includes absolute path and mtime. Two
independent checkouts therefore need a stronger byte proof rather than a raw
hash equality shortcut. This module still verifies each stored historical
hash against its own exact source paths and the build configuration hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.deploy.generate_candidate_source_roster import generate_source_roster
from scripts.deploy.verify_candidate_cache import _parse_json, _stable_file_hash
from src.bilun.cache.builder import SUT_CLAIM_FILENAMES, SUT_CLEAN_FILENAMES
from src.bilun.db.hashing import source_hash_from_files

_CONFIG_KEYS = (
    "PIPELINE_MODE", "PIPELINE_SUT_MODE", "BILUN_DATA_MODE",
    "BILUN_CLAIMS_DIR", "BILUN_CLEAN_DIR",
)


def _roster(path: Path, code_sha: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    before = _stable_file_hash(path)
    value = _parse_json(path.read_text(encoding="utf-8"), context="source roster")
    if (
        not isinstance(value, dict)
        or value.get("roster_version") != "wavea-source-v1"
        or value.get("code_sha") != code_sha
        or value.get("data_mode") not in {"synthetic_demo", "real_claims"}
        or not isinstance(value.get("sources"), list)
    ):
        raise ValueError("Same-input source roster identity is invalid")
    rows = value["sources"]
    data = {
        row["label"]: row for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("label"), str)
        and row["label"].startswith(("claim:", "clean:"))
    }
    if len(data) != sum(
        isinstance(row, dict)
        and isinstance(row.get("label"), str)
        and row["label"].startswith(("claim:", "clean:"))
        for row in rows
    ):
        raise ValueError("Same-input source roster repeats an input identity")
    for prefix, names in (("claim", SUT_CLAIM_FILENAMES), ("clean", SUT_CLEAN_FILENAMES)):
        if not {f"{prefix}:{name}" for name in names} <= set(data):
            raise ValueError("Same-input source roster omits required build inputs")
    claim_dirs = {str(Path(row["path"]).parent) for label, row in data.items() if label.startswith("claim:")}
    clean_dirs = {str(Path(row["path"]).parent) for label, row in data.items() if label.startswith("clean:")}
    if len(claim_dirs) != 1 or len(clean_dirs) != 1:
        raise ValueError("Same-input source roster has ambiguous input directories")
    regenerated = generate_source_roster(
        Path(value["checkout"]), code_sha=code_sha,
        data_mode=value["data_mode"],
        claims_dir=Path(next(iter(claim_dirs))),
        clean_dir=Path(next(iter(clean_dirs))),
    )
    if value != regenerated or _stable_file_hash(path) != before:
        raise ValueError("Same-input source roster differs from current pinned bytes")
    return value, data


def _config_hash(
    values: Mapping[str, str], *, mode: str, claims_dir: str, clean_dir: str,
) -> str:
    base = hashlib.sha256()
    for key in sorted(_CONFIG_KEYS):
        base.update(f"{key}={values[key]}\n".encode())
    effective = {
        "BILUN_DATA_MODE": mode,
        "BILUN_CLAIMS_DIR": claims_dir,
        "BILUN_CLEAN_DIR": clean_dir,
    }
    digest = hashlib.sha256()
    digest.update(base.hexdigest().encode())
    for key, value in sorted(effective.items()):
        digest.update(f"{key}={value}\n".encode())
    return digest.hexdigest()


def verify_same_input_rosters(
    baseline_roster: Path,
    candidate_roster: Path,
    *,
    baseline_meta: Mapping[str, str],
    candidate_meta: Mapping[str, str],
    build_config_environment: Mapping[str, str],
) -> dict[str, Any]:
    """Re-read every pinned source and reconcile each build's stored hashes."""
    if set(build_config_environment) != set(_CONFIG_KEYS) or any(
        not isinstance(value, str) for value in build_config_environment.values()
    ):
        raise ValueError("Same-input build configuration environment is incomplete")
    if baseline_roster.resolve() == candidate_roster.resolve():
        raise ValueError("Same-input rosters must be independent")
    old, old_data = _roster(baseline_roster, baseline_meta["code_sha"])
    new, new_data = _roster(candidate_roster, candidate_meta["code_sha"])
    if old["checkout"] == new["checkout"]:
        raise ValueError("Same-input proof needs independent source checkouts")
    if old["data_mode"] != new["data_mode"] or set(old_data) != set(new_data):
        raise ValueError("Same-input data mode or file roster differs")
    for label in old_data:
        if any(old_data[label][key] != new_data[label][key] for key in ("sha256", "size_bytes")):
            raise ValueError(f"Same-input bytes differ: {label}")
    identities = []
    paths: dict[str, dict[str, str]] = {}
    for name, roster, data, meta in (
        ("baseline", old, old_data, baseline_meta),
        ("candidate", new, new_data, candidate_meta),
    ):
        claims_dir = str(Path(data[f"claim:{SUT_CLAIM_FILENAMES[0]}"]["path"]).parent)
        clean_dir = str(Path(data[f"clean:{SUT_CLEAN_FILENAMES[0]}"]["path"]).parent)
        checkout = Path(roster["checkout"])

        def display_path(path: str) -> str:
            source = Path(path)
            return source.relative_to(checkout).as_posix() if source.is_relative_to(checkout) else path

        claim_source = display_path(claims_dir)
        clinical_source = display_path(clean_dir)
        hashed_paths = [
            Path(data[f"clean:{filename}"]["path"]) for filename in SUT_CLEAN_FILENAMES
        ] + [
            Path(data[f"claim:{filename}"]["path"]) for filename in SUT_CLAIM_FILENAMES
        ]
        if (
            source_hash_from_files(hashed_paths) != meta["source_hash"]
            or _config_hash(
                build_config_environment,
                mode=roster["data_mode"],
                claims_dir=claim_source,
                clean_dir=clinical_source,
            ) != meta["config_hash"]
        ):
            raise ValueError(f"Same-input {name} stored source/config identity differs")
        identities.append({"roster_sha256": _stable_file_hash(
            baseline_roster if name == "baseline" else candidate_roster
        ), "source_hash": meta["source_hash"], "config_hash": meta["config_hash"]})
        paths[name] = {
            "claim_source": claim_source,
            "clinical_source": clinical_source,
        }
    canonical = [
        (label, old_data[label]["sha256"], old_data[label]["size_bytes"])
        for label in sorted(old_data)
    ]
    return {
        "status": "same_input_bytes_verified",
        "data_mode": old["data_mode"],
        "input_file_count": len(canonical),
        "input_bytes_sha256": hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest(),
        "baseline": identities[0],
        "candidate": identities[1],
        "paths": paths,
    }


def normalize_attested_data_source(value: Any, paths: Mapping[str, str]) -> Any:
    """Replace only the two attested physical input paths for semantic parity."""
    if isinstance(value, list):
        return [normalize_attested_data_source(item, paths) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {}
    for key, item in value.items():
        if key == "data_source" and isinstance(item, dict):
            source = dict(item)
            for field, expected, marker in (
                ("claim_source", paths["claim_source"], "@attested_claim_inputs"),
                ("clinical_source", paths["clinical_source"], "@attested_clinical_inputs"),
            ):
                if source.get(field) != expected:
                    raise ValueError(f"Cached data_source {field} differs from attested input")
                source[field] = marker
            normalized[key] = {k: normalize_attested_data_source(v, paths) for k, v in source.items()}
        else:
            normalized[key] = normalize_attested_data_source(item, paths)
    return normalized
