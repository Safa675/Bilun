"""EK-2/C prose-mandated package codes (§2.2.2 proviso) — catalog + SUT seed."""

from __future__ import annotations

import json
from functools import lru_cache


from ..constants import _PROSE_RULES_DIR


def normalize_procedure_code(raw: str) -> str:
    code = str(raw or "").strip().replace(".", "").replace(" ", "").replace("-", "")
    if code.startswith(("P", "p")):
        code = code[1:]
    return code

_SEED_PATH = _PROSE_RULES_DIR / "ek2c_prose_drg_locked_codes.json"


@lru_cache(maxsize=1)
def load_prose_drg_locked_code_set() -> frozenset[str]:
    if not _SEED_PATH.is_file():
        return frozenset()
    try:
        payload = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    raw = payload.get("normalized_codes") or []
    return frozenset(
        normalize_procedure_code(str(code)) for code in raw if str(code).strip()
    ) - {""}


def procedure_in_prose_drg_locked_seed(procedure_code: str) -> bool:
    normalized = normalize_procedure_code(procedure_code)
    return bool(normalized) and normalized in load_prose_drg_locked_code_set()
