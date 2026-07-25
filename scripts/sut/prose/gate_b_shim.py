"""Compatibility shim layer — delegates old per-section gate_b module APIs to gate_b_generic.

Each old module (drug_indication_XXXX_gate_b.py) becomes a thin file that calls
make_shim("XXXX") from this module. This eliminates ~5,000 lines of duplicate logic
while preserving the exact function signatures tests depend on.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.gate_b_generic import (  # noqa: E402
    GateBSection,
    export_candidates as _export_candidates,
    build_manifest as _build_manifest,
)
from scripts.sut.prose.gate_b_sections import ALL_SECTIONS  # noqa: E402


def _section_for(name: str) -> GateBSection:
    """Get the GateBSection config for a section name."""
    if name not in ALL_SECTIONS:
        raise KeyError(f"Unknown gate_b section: {name!r}. Known: {sorted(ALL_SECTIONS)}")
    return ALL_SECTIONS[name]


def shim_export_candidates(name: str, clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None) -> pl.DataFrame:
    """Generic export_candidates delegation."""
    return _export_candidates(clauses_path, _section_for(name), encoded_clause_ids=encoded_clause_ids)


def shim_build_manifest(name: str, gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str, resolve_clauses: pl.DataFrame | None = None) -> dict[str, Any]:
    """Generic build_manifest delegation."""
    manifest = _build_manifest(
        gate_b_frame,
        rules,
        _section_for(name),
        effective_date=effective_date,
        resolve_clauses=resolve_clauses,
    )
    return manifest


def shim_write_artifacts(
    name: str,
    *,
    clauses_path: Path,
    corpus_csv: Path | None = None,
    manifest_path: Path | None = None,
    shared_manifest_path: Path | None = None,
    effective_date: str,
    rules_path: Path | None = None,
    rules: list[dict[str, Any]] | None = None,
    batch_rules: list[dict[str, Any]] | None = None,
    write_corpus: bool = False,
    **_kwargs: Any,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Generic write_artifacts delegation — handles all 4 kwarg flavors.

    Resolves rules from: batch_rules > rules > rules_path (JSON load).
    Resolves manifest path from: manifest_path > shared_manifest_path.
    Corpus CSV is optional (Track C4 — default off; pass write_corpus=True for human export).
    """
    section = _section_for(name)

    # Resolve rules list
    resolved_rules: list[dict[str, Any]] = []
    if batch_rules is not None:
        resolved_rules = batch_rules
    elif rules is not None:
        resolved_rules = rules
    elif rules_path is not None:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        resolved_rules = [
            r for r in (payload.get("rules") or [])
            if any(str(r.get("sut_section") or "").startswith(p) for p in section.match.prefixes)
        ]

    # Resolve manifest path
    resolved_manifest_path = manifest_path or shared_manifest_path
    if resolved_manifest_path is None:
        resolved_manifest_path = _PROJECT_ROOT / section.manifest_path

    # Build manifest against full parquet so coordinate cites resolve.
    resolve_clauses = pl.read_parquet(clauses_path)
    frame = _export_candidates(clauses_path, section)
    manifest = _build_manifest(
        frame,
        resolved_rules,
        section,
        effective_date=effective_date,
        resolve_clauses=resolve_clauses,
    )

    # Write artifacts
    resolved_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    encoded = frozenset(manifest["encoded_clause_ids"])
    frame = _export_candidates(clauses_path, section, encoded_clause_ids=encoded)
    if write_corpus and corpus_csv is not None:
        corpus_csv.parent.mkdir(parents=True, exist_ok=True)
        frame.write_csv(corpus_csv)
    resolved_manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return frame, manifest


def make_shim(name: str) -> dict[str, Any]:
    """Return a dict of shimmed functions for a section name.

    Usage in thin module files:
        from scripts.sut.prose.gate_b_shim import make_shim
        _s = make_shim("4219")
        export_4219_candidates = _s["export"]
        build_4219_manifest = _s["build"]
        write_gate_b_artifacts = _s["write"]
    """
    return {
        "export": lambda clauses_path, *, encoded_clause_ids=None: shim_export_candidates(
            name, clauses_path, encoded_clause_ids=encoded_clause_ids
        ),
        "build": lambda gate_b_frame, rules, *, effective_date: shim_build_manifest(
            name, gate_b_frame, rules, effective_date=effective_date
        ),
        "write": lambda **kwargs: shim_write_artifacts(name, **kwargs),
    }
