#!/usr/bin/env python3
"""Complete package ingestion only after source, raw tables and corpus match.

The workflow calls this after curation and dated reports succeed. Completion is
an ingestion receipt, not a finding of legal or clinical applicability.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.convert_xlsx_to_parquet import (
    DEFAULT_OUTPUT_DIR, PROJECT_ROOT, add_metadata, clean_sheet, frames_equal,
    is_mulga_path, normalize_for_parquet, parse_annex_code, parse_annex_family,
    parse_effective_date, source_identity, stored_path,
)
from scripts.sut.prose.extractor import add_identity_columns, extract_sut_clauses
from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides_pandas


def inventory_sources(input_dir: Path, inventory_path: Path, as_of: dt.date) -> tuple[dict, list[Path], Path]:
    inventory = json.loads(inventory_path.read_text())
    publication = dt.date.fromisoformat(inventory["teblig_date"])
    origin = urlparse(inventory["download_url"])
    if (inventory["schema_version"] != 1 or publication > as_of
            or input_dir.name[:10] != publication.strftime("%Y.%m.%d")
            or origin.scheme != "https" or not origin.hostname
            or not (origin.hostname == "sgk.gov.tr" or origin.hostname.endswith(".sgk.gov.tr"))
            or not re.fullmatch(r"[0-9a-f]{64}", inventory["zip_sha256"])):
        raise ValueError("Invalid, future or unpinned official package inventory")
    sources = []
    seen = set()
    for member in inventory["files"]:
        name = member["path"]
        relative = PurePosixPath(name)
        path = input_dir / name
        if (not name or "\\" in name or relative.is_absolute() or ".." in relative.parts
                or name in seen or path.is_symlink() or not path.resolve().is_relative_to(input_dir.resolve())):
            raise ValueError(f"Unsafe or duplicate inventory member: {name}")
        seen.add(name)
        content = path.read_bytes()
        if len(content) != member["size_bytes"] or hashlib.sha256(content).hexdigest() != member["sha256"]:
            raise ValueError(f"Source bytes do not match inventory: {name}")
        sources.append(path)
    workbooks = [p for p in sources if p.suffix.lower() in {".xlsx", ".xls"} and not is_mulga_path(p)]
    actual = {p for p in input_dir.rglob("*") if p.suffix.lower() in {".xlsx", ".xls"} and not is_mulga_path(p)}
    if not workbooks or set(workbooks) != actual:
        raise ValueError("Empty or incomplete workbook inventory")
    docxs = [p for p in sources if p.suffix.lower() == ".docx" and not is_mulga_path(p)
             and "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT" in p.stem]
    if len(docxs) != 1:
        raise ValueError("Inventory must pin exactly one consolidated SUT DOCX")
    return inventory, workbooks, docxs[0]


def extracted_corpus(docx: Path) -> pd.DataFrame:
    # Preserve the source snapshot. Authored clause-type overrides are applied
    # by the compiler; materializing them here would change a same-source rerun.
    return add_identity_columns(extract_sut_clauses(docx))


def corpus_frames_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Compare every field after applying the same existing authored normalizer."""
    return frames_equal(apply_clause_type_overrides_pandas(left), apply_clause_type_overrides_pandas(right))


def prepare_corpus(docx: Path, output_dir: Path) -> None:
    from scripts.sut.convert_xlsx_to_parquet import write_parquet_if_changed

    path = output_dir / "sut_clauses.parquet"
    source = extracted_corpus(docx)
    if path.exists() and corpus_frames_equal(pd.read_parquet(path), source):
        return
    write_parquet_if_changed(source, path)


def validate_tables(workbooks: list[Path], manifest: pd.DataFrame, as_of: dt.date) -> int:
    sheets = 0
    for workbook in workbooks:
        rows = manifest[manifest["source_file"].map(source_identity) == source_identity(stored_path(workbook))]
        effective = parse_effective_date(workbook)
        if effective and dt.date.fromisoformat(effective) > as_of:
            raise ValueError(f"Future effective workbook: {workbook.name}")
        expected_sheets = []
        with pd.ExcelFile(workbook) as excel:
            for sheet in excel.sheet_names:
                source = clean_sheet(pd.read_excel(excel, sheet_name=sheet, dtype=object))
                if source.empty:
                    continue
                expected_sheets.append(sheet)
                matches = rows[rows["sheet_name"] == sheet]
                if len(matches) != 1:
                    raise ValueError(f"Missing or duplicate manifest sheet: {workbook.name}/{sheet}")
                row = matches.iloc[0]
                path = Path(row["parquet_path"])
                path = path if path.is_absolute() else PROJECT_ROOT / path
                actual = pd.read_parquet(path)
                annex = parse_annex_code(workbook)
                expected = normalize_for_parquet(add_metadata(source, annex, parse_annex_family(annex),
                    effective, stored_path(workbook), sheet, False))
                if (row["row_count"] != len(actual) or row["column_count"] != len(actual.columns)
                        or row["annex_code"] != annex or bool(row["is_mulga"])
                        or row["annex_family"] != parse_annex_family(annex)
                        or (None if pd.isna(row["effective_date"]) else str(row["effective_date"])) != effective
                        or not frames_equal(actual, expected, raw=True)):
                    raise ValueError(f"Raw table does not match source/manifest: {workbook.name}/{sheet}")
        if not expected_sheets or sorted(rows["sheet_name"]) != sorted(expected_sheets):
            raise ValueError(f"Incomplete manifest workbook: {workbook.name}")
        sheets += len(expected_sheets)
    return sheets


def complete_ingestion(input_dir: Path, inventory_path: Path, output_dir: Path, as_of: dt.date) -> dict:
    inventory, workbooks, docx = inventory_sources(input_dir, inventory_path, as_of)
    manifest = pd.read_parquet(output_dir / "version_manifest.parquet")
    sheets = validate_tables(workbooks, manifest, as_of)
    corpus_path = output_dir / "sut_clauses.parquet"
    corpus = pd.read_parquet(corpus_path)
    if corpus.empty or not corpus_frames_equal(corpus, extracted_corpus(docx)):
        raise ValueError("Corpus does not match the pinned consolidated source")
    if set(corpus["source_effective_date"]) != {inventory["teblig_date"]}:
        raise ValueError("Corpus source date does not match the package publication")
    state_path = output_dir / "ingest_state.json"
    old = json.loads(state_path.read_text()) if state_path.exists() else {"pipeline_version": 2}
    if old.get("last_ingested_date", "") > inventory["teblig_date"]:
        raise ValueError("An older input cannot replace complete-package state")
    state = dict(old, last_ingested_folder=input_dir.name, last_ingested_date=inventory["teblig_date"],
        manifest_row_count=len(manifest), manifest_sha256=hashlib.sha256(
            (output_dir / "version_manifest.parquet").read_bytes()).hexdigest()[:16],
        completed_package={"inventory_sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            "zip_sha256": inventory["zip_sha256"], "workbook_count": len(workbooks), "sheet_count": sheets,
            "source_docx_sha256": hashlib.sha256(docx.read_bytes()).hexdigest(),
            "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest()})
    state["completion_scope"] = "complete"
    for field in ("pending_full_package_date", "pending_full_package_workbook_count", "component_receipts"):
        state.pop(field, None)
    if state != old:
        state["last_ingested_at"] = dt.datetime.now(dt.UTC).isoformat()
        tmp = state_path.with_suffix(".json.tmp")
        with tmp.open("w") as stream:
            json.dump(state, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, state_path)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.datetime.now(dt.UTC).date())
    parser.add_argument("--prepare-corpus", action="store_true")
    args = parser.parse_args()
    if args.prepare_corpus:
        _, _, docx = inventory_sources(args.input_dir, args.inventory, args.as_of)
        prepare_corpus(docx, args.output_dir)
    else:
        complete_ingestion(args.input_dir, args.inventory, args.output_dir, args.as_of)


if __name__ == "__main__":
    main()
