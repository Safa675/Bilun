"""Every runtime EK-4A reader goes through the service-date history."""

from datetime import date
from pathlib import Path

import pytest

from src.bilun.api.routes.billing import get_drug_catalog
from src.bilun.domain.drugs.ek4d_exempt import _normalize_drug_query
from src.bilun.domain.materials import get_ek4a_drugs, lookup_drug, lookup_drug_bulk
from src.bilun.domain.materials.ek4a_as_of import ek4a_as_of

pytestmark = pytest.mark.unit

ON = date(2026, 6, 1)
ENSPRYNG = "ENSPRYNG 120 MG/ML ENJEKSİYONLUK ÇÖZELTİ İÇEREN KULLANIMA HAZIR ENJEKTÖR"
SRC = Path(__file__).resolve().parents[4] / "src" / "bilun"


def _drug(state: str, passivated: bool) -> dict:
    return next(d for d in ek4a_as_of(ON).drugs()
                if d["state"] == state and bool(d["passivation_date"]) == passivated and d["status"] == "ok")


def test_name_lookup_finds_reactivated_drugs_and_skips_passive_ones() -> None:
    reactivated = _drug("active", passivated=True)  # hidden by the old passivation-cell filter
    assert lookup_drug(reactivated["drug_name"], ON)["kamu_no"] == reactivated["kamu_no"]
    passive = _drug("passive", passivated=True)
    found = lookup_drug(passive["drug_name"], ON)
    assert found is None or found["kamu_no"] != passive["kamu_no"]
    bulk = lookup_drug_bulk([reactivated["drug_name"], "NO SUCH DRUG XYZ"], ON)
    assert bulk[reactivated["drug_name"]]["kamu_no"] == reactivated["kamu_no"]
    assert bulk["NO SUCH DRUG XYZ"] is None


def test_name_lookup_follows_the_service_date() -> None:
    assert lookup_drug(ENSPRYNG, date(2026, 10, 5)) is None  # (*) entry date 10/10/2026
    assert lookup_drug(ENSPRYNG, date(2026, 10, 11))["kamu_no"] == "A20335"
    assert get_ek4a_drugs(ON) == ek4a_as_of(ON).drugs()
    assert get_ek4a_drugs()  # default: the list in force today


def test_ek4d_resolves_a_code_only_in_the_list_of_the_claim_date() -> None:
    drug = _drug("active", passivated=False)
    assert _normalize_drug_query("Given name", "", drug["barcode"], ON) == "Given name"
    assert _normalize_drug_query("", "", drug["barcode"], ON) == drug["drug_name"]
    assert _normalize_drug_query("", drug["kamu_no"], "", ON) == drug["drug_name"]
    assert _normalize_drug_query("", "", drug["barcode"], None) == ""  # no date, no name
    assert _normalize_drug_query("", "", drug["barcode"], date(2025, 4, 1)) == ""  # gap
    assert _normalize_drug_query("", "A19661", "", date(2025, 5, 1)) == ""  # SGK gave it to two drugs


def test_drug_catalog_reports_the_list_and_coverage_it_used() -> None:
    page = get_drug_catalog(q="", page=1, per_page=5, service_date=ON)
    assert (page["total"], page["as_of"], page["coverage"], page["list_valid_from"]) == (
        8078, "2026-06-01", "covered", "2026-05-23")
    assert {"state", "status"} <= set(page["drugs"][0])
    gap = get_drug_catalog(q="", page=1, per_page=5, service_date=date(2025, 4, 1))
    assert (gap["total"], gap["coverage"], gap["list_valid_from"]) == (0, "gap", None)
    search = get_drug_catalog(q="ENSPRYNG", page=1, per_page=5, service_date=date(2025, 10, 5))
    assert search["total"] == 0  # not in any list before 2026-10-02
    upcoming = get_drug_catalog(q="ENSPRYNG", page=1, per_page=5, service_date=date(2026, 10, 5))
    assert [d["state"] for d in upcoming["drugs"]] == ["not_yet_listed"]


def test_no_runtime_module_reads_the_single_snapshot_catalog() -> None:
    # constants.py defines the path; ek4a_as_of.py only derives the history paths next to it.
    allowed = {"domain/constants.py", "domain/materials/ek4a_as_of.py"}
    readers = [path.relative_to(SRC).as_posix() for path in SRC.rglob("*.py")
               if "EK4A_PARQUET_PATH" in path.read_text() or "ek4a_drugs.parquet" in path.read_text()]
    assert sorted(set(readers) - allowed) == []
    assert "read_parquet(EK4A_PARQUET_PATH" not in (SRC / "domain/materials/ek4a_as_of.py").read_text()
