"""Track C1: every SUT prose manifest is canonical-v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST_DIR = _REPO / "data/gazette/prose_manifests"
_SCHEMA_PATH = _MANIFEST_DIR / "schemas/canonical_v1.schema.json"

# Documented exceptions (god-plan Track C1 / Track F).
_SKIP = frozenset(
    {
        "fatura_inceleme_prose_manifest.json",  # Fatura epic — not SUT Gate B
        "L1.8_copay_exemption_encoded_manifest.json",  # Track F compositor shape
    }
)


def _sut_manifests() -> list[Path]:
    return sorted(
        p for p in _MANIFEST_DIR.glob("*.json") if p.name not in _SKIP
    )


@pytest.fixture(scope="module")
def canonical_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", _sut_manifests(), ids=lambda p: p.name)
def test_sut_manifest_is_canonical_v1(path: Path, canonical_schema: dict) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("manifest_version") == "canonical-v1"
    jsonschema.validate(instance=payload, schema=canonical_schema)


def test_documented_exceptions_still_present() -> None:
    for name in _SKIP:
        assert (_MANIFEST_DIR / name).is_file(), f"missing exception fixture {name}"
