"""Annex reference entries must not masquerade as evaluated claim findings."""

from src.bilun.api.routes.validation import get_bundled_consumables_endpoint
from src.bilun.api.schemas import BundledConsumablesResponse


def test_annex_catalog_preserves_exceptions_without_inventing_effective_dates():
    payload = BundledConsumablesResponse.model_validate(
        get_bundled_consumables_endpoint()
    ).model_dump()
    bundled = payload["bundled_consumables"]["items"]
    excluded = payload["exclusion_categories"]["categories"]
    assert bundled and excluded
    assert all(row["evaluation_status"] == "not_evaluated" for row in [*bundled, *excluded])
    assert all(row["effective_date"] is None for row in [*bundled, *excluded])
    assert any("cerrahi steril eldiven hariç" in row["item_name"] for row in bundled)
    visco = next(row for row in excluded if "Viskos" in row["material_name"])
    assert "hariç" in visco["material_name"]
    assert visco["section"] == "EK-3B-2 Madde 1"
