"""Audit a corpus replacement against the installed clinical binding evidence.

This mechanical comparison preserves the installed family/version/date contract.
It does not admit new service dates, attest source currentness, or approve clinical
eligibility. Only an explicitly requested JSON report is written.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import polars as pl

from scripts.sut import verify_clinical_source_authority as baseline_verifier
from scripts.sut.prose.clause_identity import (
    normalize_for_hash,
    resolve_gate_b_ref_to_clause_ids,
)
from src.bilun.domain.prose_rules._drug_indication import source_authority as authority

_CORPUS_PATH = "data/gazette/sut_clauses.parquet"
_CONTRACT_COLUMNS = (
    "clause_key", "clause_coordinate", "section_id", "parent_section_id",
    "section_path", "section_title", "clause_type", "is_in_force",
)
_REQUIRED_COLUMNS = {*_CONTRACT_COLUMNS, "clause_id", "paragraph_index", "in_force_text"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_bytes(commit: str, path: str, git_root: Path) -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Corpus provenance requires an exact lowercase 40-hex Git commit")
    result = subprocess.run(
        ["git", "-C", str(git_root), "show", f"{commit}:{path}"],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError(f"Pinned Git artifact blob is unavailable: {commit}:{path}")
    return result.stdout


def _git_corpus_bytes(commit: str, git_root: Path) -> bytes:
    return _git_blob_bytes(commit, _CORPUS_PATH, git_root)


def _source_documents(frame: pl.DataFrame, commit: str, git_root: Path) -> list[dict]:
    if "source_docx" not in frame.columns or frame["source_docx"].null_count():
        raise ValueError("Corpus source document provenance is missing")
    return [{"path": path, "sha256": _sha256(_git_blob_bytes(commit, path, git_root))}
            for path in sorted(frame["source_docx"].unique().to_list())]


def _row_snapshot(row: dict) -> dict:
    return {
        **{name: row[name] for name in _CONTRACT_COLUMNS},
        "normalized_text_sha256": _sha256(normalize_for_hash(row["in_force_text"]).encode()),
        "clause_id": row["clause_id"],
        "paragraph_index": row["paragraph_index"],
    }


def _content_contract(snapshot: dict) -> dict:
    return {key: value for key, value in snapshot.items()
            if key not in {"clause_id", "paragraph_index"}}


def _exact_active_anchor(reference: str, frame: pl.DataFrame) -> dict:
    rows = frame.filter((pl.col("clause_key") == reference) & pl.col("is_in_force"))
    if rows.height != 1:
        raise ValueError(f"Context anchor must resolve to one active row: {reference}")
    row = rows.row(0, named=True)
    if frame.filter(pl.col("clause_id") == row["clause_id"]).height != 1:
        raise ValueError(f"Context anchor clause_id is duplicated: {reference}")
    return _row_snapshot(row)


def _context_snapshot(reference: str, frame: pl.DataFrame) -> dict:
    for separator in ("@under:", "@between:", "@within:"):
        if separator not in reference:
            continue
        anchors = reference.partition(separator)[2].split("|")
        snapshots = [_exact_active_anchor(anchor, frame) for anchor in anchors]
        result = {"kind": separator, "anchors": snapshots}
        if separator == "@within:":
            start = snapshots[0]["paragraph_index"]
            later = frame.filter(
                pl.col("is_in_force") & (pl.col("clause_type") == "section_heading")
                & (pl.col("paragraph_index") > start)
            ).sort("paragraph_index").head(1)
            result["next_heading"] = (
                _row_snapshot(later.row(0, named=True)) if later.height else None
            )
        return result
    return {"kind": "exact_clause", "anchors": []}


def _context_contract(context: dict) -> dict:
    result = {"kind": context["kind"],
              "anchors": [_content_contract(row) for row in context["anchors"]]}
    if "next_heading" in context:
        heading = context["next_heading"]
        result["next_heading"] = _content_contract(heading) if heading else None
    return result


def _positions(snapshot: dict) -> dict:
    return {key: snapshot[key] for key in ("clause_id", "paragraph_index")}


def _paired_context_report(old: dict, new: dict) -> dict:
    result = {"kind": old["kind"], "anchors": [
        {"verified_contract": _content_contract(before),
         "old_position": _positions(before), "new_position": _positions(after)}
        for before, after in zip(old["anchors"], new["anchors"], strict=True)
    ]}
    if "next_heading" in old:
        before, after = old["next_heading"], new["next_heading"]
        result["next_heading"] = (
            {"verified_contract": _content_contract(before),
             "old_position": _positions(before), "new_position": _positions(after)}
            if before else None
        )
    return result


def _binding_snapshot(binding: authority.ClauseBinding, frame: pl.DataFrame) -> dict:
    if binding.context_anchor:
        ids = frame.filter((pl.col("clause_key") == binding.source_ref)
                           & pl.col("is_in_force"))["clause_id"].to_list()
    else:
        ids = resolve_gate_b_ref_to_clause_ids(
            binding.source_ref, frame, encode_eligible_only=False,
        )
    if len(ids) != 1:
        raise ValueError(f"Binding must resolve to one clause_id: {binding.source_ref}")
    rows = frame.filter(pl.col("clause_id") == ids[0])
    if rows.height != 1:
        raise ValueError(f"Binding clause_id must identify one row: {binding.source_ref}")
    snapshot = _row_snapshot(rows.row(0, named=True))
    if (snapshot["normalized_text_sha256"] != binding.text_sha256
            or snapshot["section_id"] != binding.section_id
            or snapshot["clause_coordinate"] != binding.clause_coordinate
            or snapshot["is_in_force"] is not True):
        raise ValueError(f"Binding content contract differs: {binding.source_ref}")
    return {"row": snapshot, "context": _context_snapshot(binding.source_ref, frame)}


def _check_candidate_documents(
    snapshot: dict, frame: pl.DataFrame, document_hashes: dict[str, str], expected: str,
) -> None:
    context = snapshot["context"]
    rows = [snapshot["row"], *context["anchors"]]
    if context.get("next_heading"):
        rows.append(context["next_heading"])
    for row in rows:
        path = frame.filter(pl.col("clause_id") == row["clause_id"])["source_docx"].item()
        if document_hashes.get(path) != expected:
            raise ValueError(f"Candidate bound row source document differs: {row['clause_key']}")


def audit_corpus_migration(
    old_corpus: Path, new_corpus: Path, *, baseline_commit: str,
    candidate_commit: str, git_root: Path | None = None,
) -> dict:
    """Return exact artifact/unique binding proof; reject any content/context drift."""
    root = git_root if git_root is not None else authority._ROOT
    old_bytes, new_bytes = Path(old_corpus).read_bytes(), Path(new_corpus).read_bytes()
    for label, commit, payload in (
        ("baseline", baseline_commit, old_bytes), ("candidate", candidate_commit, new_bytes),
    ):
        if _sha256(_git_corpus_bytes(commit, root)) != _sha256(payload):
            raise ValueError(f"{label.capitalize()} corpus differs from its exact Git blob")

    catalog_bytes = authority._CATALOG.read_bytes()
    catalog_path = authority._CATALOG.relative_to(authority._ROOT).as_posix()
    if _git_blob_bytes(baseline_commit, catalog_path, root) != catalog_bytes:
        raise ValueError("Installed catalog differs from its exact baseline Git blob")
    catalog = authority.AuthorityCatalog.model_validate_json(catalog_bytes)
    if _sha256(old_bytes) != catalog.deployed_source_corpus_sha256:
        raise ValueError("Old corpus does not match the installed reviewed catalog pin")
    closure = baseline_verifier.verify()
    if closure["family_count"] != len(catalog.versions):
        raise ValueError("Installed asset closure and catalog family counts differ")
    frames = [pl.read_parquet(io.BytesIO(payload)) for payload in (old_bytes, new_bytes)]
    if any(not _REQUIRED_COLUMNS.issubset(frame.columns) for frame in frames):
        raise ValueError("Corpus lacks required binding/context columns")
    documents = [_source_documents(frame, commit, root) for frame, commit in
                 zip(frames, (baseline_commit, candidate_commit), strict=True)]
    candidate_document_hashes = {document["path"]: document["sha256"]
                                 for document in documents[1]}

    groups = []
    for evidence_path in sorted({version.evidence.path for version in catalog.versions}):
        versions = [version for version in catalog.versions
                    if version.evidence.path == evidence_path]
        evidence = versions[0].evidence
        binding_bytes = authority._read_evidence(evidence)
        bindings = authority.SourceBindings.model_validate_json(binding_bytes)
        if bindings.source_docx_sha256 not in candidate_document_hashes.values():
            raise ValueError(f"Candidate source document differs from binding evidence: {evidence_path}")
        for version in versions:
            if (version.evidence.sha256 != evidence.sha256
                    or bindings.permitted_family_versions.get(version.family_id) != version.version_id
                    or bindings.established_history_from.get(version.family_id) != version.legal_effective_from
                    or bindings.source_observed_on != version.source_observed_on
                    or bindings.source_docx_sha256 != version.source_docx_sha256):
                raise ValueError(f"Evidence family/version contract differs: {version.family_id}")
        rows = []
        for binding in bindings.bindings:
            old, new = [_binding_snapshot(binding, frame) for frame in frames]
            _check_candidate_documents(
                new, frames[1], candidate_document_hashes, bindings.source_docx_sha256,
            )
            if (_content_contract(old["row"]) != _content_contract(new["row"])
                    or _context_contract(old["context"]) != _context_contract(new["context"])):
                raise ValueError(f"Binding parent/context changed: {binding.source_ref}")
            rows.append({"source_ref": binding.source_ref,
                         "context_anchor": binding.context_anchor,
                         "verified_contract": _content_contract(old["row"]),
                         "old_position": _positions(old["row"]),
                         "new_position": _positions(new["row"]),
                         "context": _paired_context_report(old["context"], new["context"])})
        groups.append({"evidence_path": evidence_path, "evidence_sha256": evidence.sha256,
                       "source_docx_sha256": bindings.source_docx_sha256,
                       "family_ids": [version.family_id for version in versions],
                       "bindings": rows})

    # Evidence is read again by the closure check even when runtime parsing is warm.
    if baseline_verifier.verify() != closure or authority._CATALOG.read_bytes() != catalog_bytes:
        raise ValueError("Installed authority assets changed during the migration audit")
    return {
        "schema_version": 1, "status": "verified",
        "scope": "mechanical_clinical_corpus_compatibility",
        "baseline": {"commit": baseline_commit, "corpus_sha256": _sha256(old_bytes),
                     "corpus_rows": frames[0].height, "catalog_sha256": _sha256(catalog_bytes),
                     "assets": closure["assets"], "source_documents": documents[0]},
        "candidate": {"commit": candidate_commit, "corpus_sha256": _sha256(new_bytes),
                      "corpus_rows": frames[1].height, "source_documents": documents[1]},
        "family_count": len(catalog.versions), "binding_file_count": len(groups),
        "binding_count": sum(len(group["bindings"]) for group in groups),
        "family_binding_membership_count": sum(
            len(group["bindings"]) * len(group["family_ids"]) for group in groups
        ),
        "family_contracts": [
            {"family_id": version.family_id, "version_id": version.version_id,
             "version_contract_sha256": _sha256(json.dumps(
                 version.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
             ).encode()),
             "legal_effective_from": version.legal_effective_from,
             "known_successor_from": version.known_successor_from,
             "windows": [window.model_dump(mode="json", exclude_none=True)
                         for window in version.windows]}
            for version in catalog.versions
        ],
        "binding_groups": groups,
        "currentness_extended": False, "clinical_eligibility_complete": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_corpus", type=Path)
    parser.add_argument("new_corpus", type=Path)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--candidate-commit", required=True)
    parser.add_argument("--git-root", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_corpus_migration(
            args.old_corpus, args.new_corpus, baseline_commit=args.baseline_commit,
            candidate_commit=args.candidate_commit, git_root=args.git_root,
        )
        if args.json_output:
            args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError, pl.exceptions.PolarsError) as exc:
        print(f"Clinical corpus migration verification failed: {exc}")
        return 1
    print(f"Clinical corpus compatibility verified: {report['family_count']} families, "
          f"{report['binding_count']} unique bindings; no date/currentness extension.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
