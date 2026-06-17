#!/usr/bin/env python3
"""Sync data/medula/known_codes.json from rejection_playbook.json entries."""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PLAYBOOK_PATH = _REPO / "data/medula/rejection_playbook.json"
_KNOWN_CODES_PATH = _REPO / "data/medula/known_codes.json"


def build_known_codes_from_playbook(
    playbook: dict,
    *,
    preserve_codes: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Derive chat/KB known-code entries from playbook templates."""
    preserve_codes = preserve_codes or {}
    merged: dict[str, dict] = dict(preserve_codes)
    for entry in playbook.get("entries", []):
        code = str(entry.get("sonuc_kodu", "")).strip()
        if not code:
            continue
        steps_tr = list(entry.get("corrective_steps_tr") or [])
        merged[code] = {
            "meaning_tr": str(entry.get("problem_summary_tr") or ""),
            "meaning_en": str(entry.get("problem_summary_en") or ""),
            "action": steps_tr[0] if steps_tr else "",
            "is_error": True,
            "playbook_key": str(entry.get("playbook_key") or ""),
        }
    return dict(sorted(merged.items(), key=lambda item: item[0]))


def main() -> None:
    playbook = json.loads(_PLAYBOOK_PATH.read_text(encoding="utf-8"))
    existing = json.loads(_KNOWN_CODES_PATH.read_text(encoding="utf-8"))
    preserved = {
        code: payload
        for code, payload in existing.items()
        if code not in {
            str(entry.get("sonuc_kodu", "")).strip()
            for entry in playbook.get("entries", [])
        }
    }
    payload = build_known_codes_from_playbook(playbook, preserve_codes=preserved)
    _KNOWN_CODES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(payload)} known codes to {_KNOWN_CODES_PATH}")


if __name__ == "__main__":
    main()
