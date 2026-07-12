"""Unit tests for Medula known codes and rejection playbook data files.

Workstream D — material finalization codes 0963-0968.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "medula"
KNOWN_CODES_PATH = DATA_DIR / "known_codes.json"
PLAYBOOK_PATH = DATA_DIR / "rejection_playbook.json"

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def known_codes() -> dict:
    return json.loads(KNOWN_CODES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def playbook() -> dict:
    return json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", ["0963", "0964", "0965", "0966", "0967", "0968"])
def test_material_finalization_codes_present(known_codes: dict, code: str) -> None:
    """All 6 material finalization codes (0963-0968) exist in known_codes.json."""
    assert code in known_codes, f"code {code} missing from known_codes.json"
    entry = known_codes[code]
    # Match the existing entry structure.
    for key in ("meaning_tr", "meaning_en", "action", "is_error", "playbook_key"):
        assert key in entry, f"code {code} entry missing key {key}"
    assert entry["is_error"] is True


def test_playbook_has_material_finalization_template(playbook: dict) -> None:
    """The rejection playbook has a template matching the 096[3-8] family."""
    entries = playbook["entries"]
    matching = [
        e for e in entries
        if e.get("sonuc_kodu_pattern") == "096[3-8]"
        or e.get("category") == "material_finalization"
    ]
    assert matching, "no playbook template found for 096[3-8] / material_finalization"
    template = matching[0]
    assert template["sonuc_kodu_pattern"] == "096[3-8]"
    assert template["category"] == "material_finalization"
    assert template["rebill_permitted"] is True
    # Corrective steps must include the required guidance.
    steps = " ".join(template["corrective_steps_tr"]).lower()
    assert "kesinleştir" in steps or "kesinleştirme" in steps


def test_0963_0968_pattern_matches_correctly() -> None:
    """The 096[3-8] pattern matches 0963-0968 and rejects out-of-range codes."""
    pattern = r"096[3-8]"
    for code in ("0963", "0964", "0965", "0966", "0967", "0968"):
        assert re.search(pattern, code) is not None, f"{code} should match {pattern}"
    # Out-of-range neighbors must NOT match.
    assert re.search(pattern, "0962") is None
    assert re.search(pattern, "0969") is None


def test_playbook_keys_reference_back_to_known_codes(known_codes: dict, playbook: dict) -> None:
    """Every 0963-0968 known code points at the material finalization playbook."""
    for code in ("0963", "0964", "0965", "0966", "0967", "0968"):
        assert known_codes[code]["playbook_key"] == "0963_material_finalization"
    keys = {e["playbook_key"] for e in playbook["entries"]}
    assert "0963_material_finalization" in keys
