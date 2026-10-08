"""Source-bound package completion, partial failure and byte-preserving reruns."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut import convert_xlsx_to_parquet as converter
from scripts.sut import sut_ingest_state as completion
from scripts.sut.prose import clause_type_overrides

pytestmark = pytest.mark.unit
AS_OF = dt.date(2026, 10, 5)


def receipt_for(source: Path, receipt: Path, *, date: str = "2026-10-02") -> None:
    files = [{"path": p.relative_to(source).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "size_bytes": p.stat().st_size} for p in sorted(source.rglob("*")) if p.is_file() and p != receipt]
    receipt.write_text(json.dumps({"schema_version": 1, "teblig_date": date,
        "download_url": "https://www.sgk.gov.tr/Download/DownloadFile?f=official.zip&d=official",
        "zip_sha256": "a" * 64, "files": files}))


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "2026.10.02-consolidated"
    source.mkdir()
    output = tmp_path / "gazette"
    output.mkdir()
    workbook = source / "EK-4A.xlsx"
    with pd.ExcelWriter(workbook) as excel:
        pd.DataFrame({"barcode": ["00123", "00001"], "name": ["A", "B"]}).to_excel(excel, sheet_name="EK-4A", index=False)
        pd.DataFrame().to_excel(excel, sheet_name="empty", index=False)
    docx = source / "02.10.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx"
    docx.write_bytes(b"canonical clause text")
    receipt = source / ".sut_package_inventory.json"
    receipt_for(source, receipt)
    manifest = converter.build_manifest(converter.convert_one_workbook(workbook, output))
    manifest.to_parquet(output / "version_manifest.parquet", index=False)
    state = {"pipeline_version": 2, "last_ingested_date": "2026-08-29", "completion_scope": "partial",
        "pending_full_package_date": "2026-10-02", "pending_full_package_workbook_count": 318,
        "component_receipts": {"prose": {"corpus_sha256": "stale"}}}
    (output / "ingest_state.json").write_text(json.dumps(state))
    # Substitute only the DOCX parser; the inventory, bytes, sheets, raw tables,
    # manifest and complete-state writes exercise the production implementation.
    def extract(pinned_docx: Path) -> pd.DataFrame:
        text = pinned_docx.read_bytes().decode()
        return pd.DataFrame({"source_docx": [str(pinned_docx)], "source_effective_date": ["2026-10-02"],
            "text_tr": [text], "in_force_text": [text], "clause_coordinate": ["1.1"],
            "clause_type": ["prose"], "is_heading": [False]})
    monkeypatch.setattr(completion, "extract_sut_clauses", extract)
    completion.prepare_corpus(docx, output)
    return source, receipt, output, workbook, docx


def test_complete_exact_package_clears_partial_markers_and_is_idempotent(package) -> None:
    source, receipt, output, _, docx = package
    state = completion.complete_ingestion(source, receipt, output, AS_OF)
    assert state["last_ingested_date"] == "2026-10-02"
    assert state["completion_scope"] == "complete"
    assert not {"pending_full_package_date", "pending_full_package_workbook_count", "component_receipts"} & state.keys()
    assert state["completed_package"]["workbook_count"] == 1
    assert state["completed_package"]["sheet_count"] == 1
    assert state["completed_package"]["source_docx_sha256"] == hashlib.sha256(docx.read_bytes()).hexdigest()
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    completion.prepare_corpus(docx, output)
    assert completion.complete_ingestion(source, receipt, output, AS_OF) == state
    assert all(p.read_bytes() == content for p, content in before.items())


@pytest.mark.parametrize("corruption", ["source", "raw-value", "raw-dtype", "raw-count", "manifest-count",
    "manifest-date", "manifest-family", "duplicate-sheet", "missing-sheet", "corpus-text", "corpus-date",
    "corpus-source", "corpus-schema", "corpus-annotation", "omitted-source"])
def test_mismatches_never_advance_state(package, corruption: str) -> None:
    source, receipt, output, workbook, docx = package
    manifest_path = output / "version_manifest.parquet"
    manifest = pd.read_parquet(manifest_path)
    raw_path = Path(manifest.iloc[0]["parquet_path"])
    if corruption == "source":
        docx.write_bytes(b"changed source after download")
    elif corruption.startswith("raw-"):
        raw = pd.read_parquet(raw_path)
        if corruption == "raw-value":
            raw.loc[0, "barcode"] = "123"
        elif corruption == "raw-dtype":
            raw["barcode"] = raw["barcode"].astype(int)
        else:
            raw = raw.iloc[:1]
        raw.to_parquet(raw_path, index=False)
    elif corruption.startswith("manifest-"):
        column, value = {"manifest-count": ("row_count", 99),
            "manifest-date": ("effective_date", "2026-10-01"),
            "manifest-family": ("annex_family", "EK-2")}[corruption]
        manifest.loc[0, column] = value
        manifest.to_parquet(manifest_path, index=False)
    elif corruption == "duplicate-sheet":
        pd.concat([manifest, manifest]).to_parquet(manifest_path, index=False)
    elif corruption == "missing-sheet":
        manifest.iloc[:0].to_parquet(manifest_path, index=False)
    elif corruption.startswith("corpus-"):
        path = output / "sut_clauses.parquet"
        frame = pd.read_parquet(path)
        if corruption == "corpus-schema":
            frame = frame.drop(columns=["text_tr"])
        else:
            column = {"corpus-text": "text_tr", "corpus-date": "source_effective_date",
                "corpus-source": "source_docx", "corpus-annotation": "clause_type"}[corruption]
            frame.loc[0, column] = "wrong"
        frame.to_parquet(path, index=False)
    else:
        receipt_data = json.loads(receipt.read_text())
        receipt_data["files"] = [f for f in receipt_data["files"] if f["path"] != workbook.name]
        receipt.write_text(json.dumps(receipt_data))
    before = (output / "ingest_state.json").read_bytes()
    with pytest.raises(ValueError):
        completion.complete_ingestion(source, receipt, output, AS_OF)
    assert (output / "ingest_state.json").read_bytes() == before


def test_docx_only_partial_capture_cannot_complete(package) -> None:
    source, receipt, output, workbook, _ = package
    workbook.unlink()
    receipt_for(source, receipt)
    before = (output / "ingest_state.json").read_bytes()
    with pytest.raises(ValueError, match="workbook inventory"):
        completion.complete_ingestion(source, receipt, output, AS_OF)
    assert (output / "ingest_state.json").read_bytes() == before


def test_existing_authored_normalizer_preserves_same_source_corpus_bytes(package, monkeypatch: pytest.MonkeyPatch) -> None:
    source, receipt, output, _, docx = package
    path = output / "sut_clauses.parquet"
    frame = pd.read_parquet(path)
    key = frame.iloc[0]["clause_key"]
    monkeypatch.setattr(clause_type_overrides, "load_clause_type_overrides", lambda: {
        key: {"clause_type": "bent"}})
    frame["clause_type"] = "bent"
    frame.to_parquet(path, index=False)
    before = path.read_bytes()
    completion.prepare_corpus(docx, output)
    assert path.read_bytes() == before
    assert completion.complete_ingestion(source, receipt, output, AS_OF)["last_ingested_date"] == "2026-10-02"
    # The authored correction cannot conceal a changed clause body or provenance.
    for column in ("in_force_text", "source_docx"):
        changed = frame.copy()
        changed.loc[0, column] = "wrong"
        assert not completion.corpus_frames_equal(changed, completion.extracted_corpus(docx))


def test_repealed_workbooks_remain_pinned_but_are_excluded_from_required_conversion(package) -> None:
    source, receipt, output, _, _ = package
    repealed = source / "MÜLGA"
    repealed.mkdir()
    (repealed / "EK-4A.xls").write_bytes(b"excluded workbook")
    receipt_for(source, receipt)
    state = completion.complete_ingestion(source, receipt, output, AS_OF)
    assert state["completed_package"]["workbook_count"] == 1


def test_future_publication_and_effective_workbook_cannot_complete(package) -> None:
    source, receipt, output, workbook, _ = package
    with pytest.raises(ValueError, match="future"):
        completion.complete_ingestion(source, receipt, output, dt.date(2026, 10, 1))
    future = workbook.with_name("EK-4A (10.10.2026).xlsx")
    workbook.rename(future)
    converter.build_manifest(converter.convert_one_workbook(future, output)).to_parquet(
        output / "version_manifest.parquet", index=False)
    receipt_for(source, receipt)
    before = (output / "ingest_state.json").read_bytes()
    with pytest.raises(ValueError, match="Future effective"):
        completion.complete_ingestion(source, receipt, output, AS_OF)
    assert (output / "ingest_state.json").read_bytes() == before


@pytest.mark.parametrize("member", ["../escape", "/absolute", "back\\slash"])
def test_unsafe_inventory_member_is_rejected(package, member: str) -> None:
    source, receipt, output, _, _ = package
    inventory = json.loads(receipt.read_text())
    inventory["files"][0]["path"] = member
    receipt.write_text(json.dumps(inventory))
    with pytest.raises(ValueError, match="Unsafe"):
        completion.complete_ingestion(source, receipt, output, AS_OF)
