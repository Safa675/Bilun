"""API tests for the MEDULA rejection queue endpoint.

The committed demo cohort (`data/synthetic/sut/claims`) has a `medula_rejection_events` table with
no rows, so the queue is tested on a tmp copy of the committed claim tables whose events table holds
the five rows of `_EVENTS`. The rows are schema-valid (the columns and dtypes of the committed table)
and sit on real claims of the cohort: the claim comes from a registry role, its patient, episode and
date are read from the copy. What each row must produce (playbook entry, rebill flag) is written
next to it in `_EVENTS`, and every filter, facet, stat, order and page expectation is computed from
those five events, never from the cohort's own contents.

`synthetic_demo` mode only accepts paths under data/synthetic/sut, so the route (which loads the
dataset without arguments) is pointed at the copy through `real_claims` mode and the environment,
the way `tests/unit/domain/claims/test_loader.py` does it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
from typing import Any

import polars as pl
import pytest

from src.bilun.domain.claims import clear_sut_claim_dataset_cache
from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR
from src.bilun.domain.prose_rules.medula_rejection import load_medula_rejection_playbook
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_EVENTS_FILE = "medula_rejection_events.parquet"
_UNAVAILABLE_FACETS = {"sonuc_kodu": [], "medula_stage": []}
_UNAVAILABLE_STATS = {"n_events": 0, "n_matched": 0, "n_rebill_permitted": 0}


@dataclass(frozen=True)
class _Event:
    """One hand-made rejection event and what the queue must answer for it."""

    role: str  # registry role of the claim that carries the event
    medula_stage: str
    sonuc_kodu: str
    hata_mesaji: str
    line_kind: str  # "procedure" or "material" (the claim's first such line), or "claim" (no line)
    playbook_key: str | None  # the playbook entry that must match; None: no entry matches
    rebill_permitted: bool | None  # that entry's flag; None when no entry matches
    dated: bool = True  # False: the row has an empty rejection_timestamp


_EVENTS = (
    _Event(
        "showcase_S1",
        "fatura_kayit",
        "1688",
        "Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik",
        "procedure",
        "1688_molecular_microbiology",
        True,
    ),
    _Event(
        "showcase_S2",
        "fatura_kayit",
        "0612",
        "Uzmanlık sağlık kurulu raporu eksik — işlem faturalanamaz",
        "procedure",
        "0612_board_report_missing",
        True,
    ),
    # The playbook entry of 0521 does not allow a rebill, and applies at the provizyon stage too.
    _Event(
        "showcase_S3",
        "provizyon",
        "0521",
        "Provizyon onay alınmamış — işlem faturalanamaz",
        "claim",
        "0521_provision_not_obtained",
        False,
    ),
    _Event(
        "showcase_S5",
        "fatura_kayit",
        "0704",
        "Malzeme ÜTS barkod kaydı eksik veya geçersiz",
        "material",
        "0704_uts_barcode_missing",
        True,
        dated=False,
    ),
    # Same code as the first event, but none of the keywords of its playbook entry is in the
    # message: no entry matches.
    _Event(
        "showcase_S6",
        "fatura_kayit",
        "1688",
        "Ağ geçidi zaman aşımı",
        "claim",
        None,
        None,
        dated=False,
    ),
)


@dataclass(frozen=True)
class _Written:
    """An event of `_EVENTS` and the row written to the events table for it."""

    spec: _Event
    row: dict[str, str]

    @property
    def event_id(self) -> str:
        return self.row["rejection_event_id"]


@dataclass(frozen=True)
class _EventsDataset:
    """The tmp copy of the committed claim tables and the events written to it."""

    claims_dir: Path
    written: tuple[_Written, ...]


def _build_rows(claims_dir: Path) -> tuple[_Written, ...]:
    """The five event rows, on the claims named by the registry roles, read from the copy."""
    headers = pl.read_parquet(claims_dir / "claim_headers.parquet")
    procedures = pl.read_parquet(claims_dir / "procedure_claim_lines.parquet")
    materials = pl.read_parquet(claims_dir / "material_claim_lines.parquet")
    written = []
    for spec in _EVENTS:
        claim_id = cohort.role(spec.role).claim_id
        header = headers.filter(pl.col("claim_id") == claim_id).row(0, named=True)
        procedure_line_id, procedure_code, material_line_id = "", "", ""
        if spec.line_kind == "procedure":
            line = (
                procedures.filter(pl.col("claim_id") == claim_id)
                .sort("procedure_line_id")
                .row(0, named=True)
            )
            procedure_line_id, procedure_code = line["procedure_line_id"], line["procedure_code"]
        elif spec.line_kind == "material":
            material_line_id = (
                materials.filter(pl.col("claim_id") == claim_id)
                .sort("material_line_id")
                .row(0, named=True)["material_line_id"]
            )
        written.append(
            _Written(
                spec,
                {
                    "rejection_event_id": f"MEDULA-{claim_id}-001",
                    "claim_id": claim_id,
                    "patient_id": header["patient_id"],
                    "episode_id": header["episode_id"],
                    "medula_stage": spec.medula_stage,
                    "sonuc_kodu": spec.sonuc_kodu,
                    "hata_kodu": spec.sonuc_kodu,
                    "hata_mesaji": spec.hata_mesaji,
                    "rejection_timestamp": header["claim_end_date"] if spec.dated else "",
                    "related_procedure_code": procedure_code,
                    "related_procedure_line_id": procedure_line_id,
                    "related_line_type": spec.line_kind,
                    "related_line_id": procedure_line_id or material_line_id,
                },
            )
        )
    return tuple(written)


def _write_events(claims_dir: Path, rows: Sequence[dict[str, str]]) -> None:
    """Replace the events table of the copy by `rows`, with the schema of the committed table."""
    schema = pl.read_parquet(claims_dir / _EVENTS_FILE).schema
    pl.DataFrame(
        {name: [row[name] for row in rows] for name in schema}, schema=schema
    ).write_parquet(claims_dir / _EVENTS_FILE)


def _copy_claims(directory: Path) -> Path:
    claims_dir = directory / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    return claims_dir


def _point_route_at(monkeypatch: pytest.MonkeyPatch, claims_dir: Path | None) -> None:
    """Make the route (it loads the dataset without arguments) read `claims_dir`.

    `None`: the committed cohort through the default mode and directory.
    """
    for name in ("BILUN_DATA_MODE", "SUT_DATA_MODE", "BILUN_CLAIMS_DIR", "SUT_CLAIMS_DIR"):
        monkeypatch.delenv(name, raising=False)
    if claims_dir is not None:
        assert "synthetic" not in claims_dir.as_posix().lower(), (
            "real_claims mode rejects a claims directory whose path contains 'synthetic'"
        )
        monkeypatch.setenv("BILUN_DATA_MODE", "real_claims")
        monkeypatch.setenv("BILUN_CLAIMS_DIR", str(claims_dir))
    clear_sut_claim_dataset_cache()


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by directory and mode: every test starts and ends empty."""
    clear_sut_claim_dataset_cache()
    yield
    clear_sut_claim_dataset_cache()


@pytest.fixture(scope="module")
def events_dataset(tmp_path_factory: pytest.TempPathFactory) -> _EventsDataset:
    claims_dir = _copy_claims(tmp_path_factory.mktemp("queue_claims"))
    written = _build_rows(claims_dir)
    _write_events(claims_dir, [item.row for item in written])
    return _EventsDataset(claims_dir=claims_dir, written=written)


@pytest.fixture
def queue_events(
    events_dataset: _EventsDataset, monkeypatch: pytest.MonkeyPatch
) -> tuple[_Written, ...]:
    """The five written events; the route reads the copy that holds them for the test."""
    _point_route_at(monkeypatch, events_dataset.claims_dir)
    return events_dataset.written


def _queue(**params: Any) -> dict[str, Any]:
    """The route function called directly, like the other API tests of this folder.

    Imported inside the call, as the tests of this file always did: importing `src.bilun.api` at
    collection time makes `python -W error -m pytest` fail on a ResourceWarning of the logging
    set-up in `src/bilun/shared/state.py`.
    """
    from src.bilun.api.routes.medula_rejections import get_medula_rejection_queue

    return get_medula_rejection_queue(**params)


def _ingest_status() -> dict[str, bool]:
    from src.bilun.api.routes.medula_rejections import get_medula_rejection_ingest_status

    return get_medula_rejection_ingest_status()


def _ids(result: dict[str, Any]) -> list[str]:
    return [row["rejection_event_id"] for row in result["rows"]]


def _selected(written: Sequence[_Written], keep: Callable[[_Event], bool]) -> set[str]:
    """Ids of the events `keep` selects; the filter under test must keep some and drop some."""
    ids = {item.event_id for item in written if keep(item.spec)}
    assert 0 < len(ids) < len(written), "the premise of the test: a filter that splits the events"
    return ids


def test_queue_lists_every_written_event_in_the_response_model(
    queue_events: tuple[_Written, ...],
) -> None:
    from src.bilun.api.schemas import MedulaRejectionQueueResponse

    result = _queue()

    assert result["ingest_available"] is True
    assert _ingest_status() == {"ingest_available": True}
    assert result["total"] == len(queue_events)
    assert sorted(_ids(result)) == sorted(item.event_id for item in queue_events)
    assert (result["page"], result["page_size"]) == (1, 50)
    MedulaRejectionQueueResponse.model_validate(result)


@pytest.mark.parametrize(
    "spec",
    _EVENTS,
    ids=[f"{spec.sonuc_kodu}-{spec.playbook_key or 'no-playbook'}" for spec in _EVENTS],
)
def test_queue_row_carries_the_event_and_its_playbook_entry(
    queue_events: tuple[_Written, ...], spec: _Event
) -> None:
    written = next(item for item in queue_events if item.spec == spec)
    row = next(row for row in _queue()["rows"] if row["rejection_event_id"] == written.event_id)

    event = written.row
    assert row["claim_id"] == cohort.role(spec.role).claim_id
    for field in (
        "patient_id",
        "claim_id",
        "episode_id",
        "medula_stage",
        "sonuc_kodu",
        "hata_mesaji",
        "related_procedure_code",
        "related_procedure_line_id",
        "related_line_type",
        "related_line_id",
    ):
        assert row[field] == event[field], field
    assert row["rejection_timestamp"] == (event["rejection_timestamp"] or None)
    assert row["playbook_matched"] is (spec.playbook_key is not None)
    assert row["playbook_key"] == spec.playbook_key
    assert row["rebill_permitted"] is spec.rebill_permitted
    if spec.playbook_key is None:
        assert row["sut_anchor"] is None
        assert row["corrective_steps_tr"] == []
    else:
        entry = next(
            entry
            for entry in load_medula_rejection_playbook()["entries"]
            if entry["playbook_key"] == spec.playbook_key
        )
        assert row["sut_anchor"] == entry["sut_anchor"]
        assert row["corrective_steps_tr"] == entry["corrective_steps_tr"] != []


def test_queue_filters_by_sonuc_kodu(queue_events: tuple[_Written, ...]) -> None:
    result = _queue(sonuc_kodu="1688")

    expected = _selected(queue_events, lambda spec: spec.sonuc_kodu == "1688")
    assert set(_ids(result)) == expected
    assert result["total"] == len(expected)
    # An exact match, not a prefix.
    assert _queue(sonuc_kodu="168")["total"] == 0


def test_queue_filters_ignore_case_and_surrounding_spaces(
    queue_events: tuple[_Written, ...],
) -> None:
    by_code = _queue(sonuc_kodu=" 1688 ")
    by_stage = _queue(medula_stage=" PROVIZYON ")

    assert set(_ids(by_code)) == _selected(queue_events, lambda spec: spec.sonuc_kodu == "1688")
    assert set(_ids(by_stage)) == _selected(
        queue_events, lambda spec: spec.medula_stage == "provizyon"
    )


def test_queue_filters_by_medula_stage(queue_events: tuple[_Written, ...]) -> None:
    for stage in ("fatura_kayit", "provizyon"):
        result = _queue(medula_stage=stage)

        expected = _selected(queue_events, lambda spec, stage=stage: spec.medula_stage == stage)
        assert set(_ids(result)) == expected
        assert result["total"] == len(expected)


def test_queue_filters_by_rebill_permitted(queue_events: tuple[_Written, ...]) -> None:
    allowed = _queue(rebill_permitted=True)
    refused = _queue(rebill_permitted=False)

    allowed_ids = _selected(queue_events, lambda spec: spec.rebill_permitted is True)
    refused_ids = _selected(queue_events, lambda spec: spec.rebill_permitted is False)
    assert set(_ids(allowed)) == allowed_ids
    assert set(_ids(refused)) == refused_ids
    # A row with no playbook entry has no rebill flag: it is in neither answer.
    unmatched = _selected(queue_events, lambda spec: spec.rebill_permitted is None)
    assert unmatched.isdisjoint(allowed_ids | refused_ids)


def test_queue_filters_by_playbook_matched(queue_events: tuple[_Written, ...]) -> None:
    matched = _queue(playbook_matched=True)
    unmatched = _queue(playbook_matched=False)

    matched_ids = _selected(queue_events, lambda spec: spec.playbook_key is not None)
    unmatched_ids = _selected(queue_events, lambda spec: spec.playbook_key is None)
    assert set(_ids(matched)) == matched_ids
    assert set(_ids(unmatched)) == unmatched_ids
    assert matched["total"] + unmatched["total"] == len(queue_events)


def test_queue_filters_by_free_text_query(queue_events: tuple[_Written, ...]) -> None:
    rows = {item.spec.role: item.row for item in queue_events}
    searches = [  # (field the query must be found in, query, role of the one event it finds)
        ("sonuc_kodu", "0612", "showcase_S2"),
        # The ids are searched case-insensitively.
        ("patient_id", rows["showcase_S3"]["patient_id"].lower(), "showcase_S3"),
        ("claim_id", rows["showcase_S2"]["claim_id"].lower(), "showcase_S2"),
        ("episode_id", rows["showcase_S1"]["episode_id"].lower(), "showcase_S1"),
        # So is the message (the one of the 0521 event starts with "Provizyon").
        ("hata_mesaji", "PROVIZYON", "showcase_S3"),
    ]

    for field, query, role in searches:
        result = _queue(q=query)
        assert _ids(result) == [rows[role]["rejection_event_id"]], field
        assert result["total"] == 1, field
    nothing = _queue(q="no-such-text")
    assert (nothing["total"], nothing["rows"]) == (0, [])


def test_queue_exposes_facets_and_unfiltered_stats(queue_events: tuple[_Written, ...]) -> None:
    result = _queue(sonuc_kodu="1688")
    nothing = _queue(q="no-such-text")

    specs = [item.spec for item in queue_events]
    facets = {
        "sonuc_kodu": sorted({spec.sonuc_kodu for spec in specs}),
        "medula_stage": sorted({spec.medula_stage for spec in specs}),
    }
    stats = {
        "n_events": len(specs),
        "n_matched": sum(spec.playbook_key is not None for spec in specs),
        "n_rebill_permitted": sum(spec.rebill_permitted is True for spec in specs),
    }
    # The filter narrows `total` and the rows; facets and stats still describe every event.
    assert result["total"] == sum(spec.sonuc_kodu == "1688" for spec in specs) < stats["n_events"]
    assert result["facets"] == nothing["facets"] == facets
    assert result["stats"] == nothing["stats"] == stats


def test_queue_orders_newest_first_then_undated_by_claim_id(
    queue_events: tuple[_Written, ...],
) -> None:
    dated = sorted(
        (item for item in queue_events if item.spec.dated),
        key=lambda item: item.row["rejection_timestamp"],
        reverse=True,
    )
    # Events with no timestamp come last, and tie by claim id, descending.
    undated = sorted(
        (item for item in queue_events if not item.spec.dated),
        key=lambda item: item.row["claim_id"],
        reverse=True,
    )

    assert len({item.row["rejection_timestamp"] for item in dated}) == len(dated) > 1
    assert len(undated) > 1
    assert _ids(_queue()) == [item.event_id for item in dated + undated]


def test_queue_pagination_splits_the_rows_and_counts_the_filtered_total(
    queue_events: tuple[_Written, ...],
) -> None:
    full = _ids(_queue())
    pages = [_queue(page=number, page_size=2) for number in (1, 2, 3, 4)]

    assert [len(page["rows"]) for page in pages] == [
        len(full[(number - 1) * 2 : number * 2]) for number in (1, 2, 3, 4)
    ]
    assert [row_id for page in pages for row_id in _ids(page)] == full
    assert [(page["page"], page["page_size"], page["total"]) for page in pages] == [
        (number, 2, len(queue_events)) for number in (1, 2, 3, 4)
    ]
    one_row = _queue(sonuc_kodu="1688", page=1, page_size=1)
    assert len(one_row["rows"]) == 1
    assert one_row["total"] == sum(item.spec.sonuc_kodu == "1688" for item in queue_events) > 1


def test_queue_of_the_committed_cohort_follows_its_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _point_route_at(monkeypatch, None)
    result = _queue()

    expected = cohort.counts()[_EVENTS_FILE]
    # The events table is part of the committed claim tables, so the ingest is available.
    assert result["ingest_available"] is True
    assert result["total"] == result["stats"]["n_events"] == expected
    assert {row["claim_id"] for row in result["rows"]} <= set(cohort.claim_ids())


def test_queue_with_an_ingested_but_empty_events_table_is_available_and_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claims_dir = _copy_claims(tmp_path)
    _write_events(claims_dir, [])
    _point_route_at(monkeypatch, claims_dir)

    result = _queue()

    assert result == {
        "ingest_available": True,
        "rows": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
        "facets": _UNAVAILABLE_FACETS,
        "stats": _UNAVAILABLE_STATS,
    }
    assert _ingest_status() == {"ingest_available": True}


@pytest.mark.parametrize("damage", ["no_events_table", "event_on_unknown_claim"])
def test_queue_is_unavailable_instead_of_failing_when_the_events_cannot_be_ingested(
    damage: str,
    events_dataset: _EventsDataset,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    claims_dir = _copy_claims(tmp_path)
    if damage == "no_events_table":
        (claims_dir / _EVENTS_FILE).unlink()
    else:
        _write_events(
            claims_dir, [{**events_dataset.written[0].row, "claim_id": "F-NO-SUCH-CLAIM-001"}]
        )
    _point_route_at(monkeypatch, claims_dir)

    with caplog.at_level(logging.WARNING):
        result = _queue(page=2, page_size=7)
        status = _ingest_status()

    assert result == {
        "ingest_available": False,
        "rows": [],
        "total": 0,
        "page": 2,
        "page_size": 7,
        "facets": _UNAVAILABLE_FACETS,
        "stats": _UNAVAILABLE_STATS,
    }
    assert status == {"ingest_available": False}
    # A table that is absent is not an error; an invalid one is logged, not swallowed silently.
    assert ("unknown claim_id" in caplog.text) is (damage == "event_on_unknown_claim")
