#!/usr/bin/env python3
"""Build EK-2C prose DRG-locked procedure code seed from SUT §2.2 prose lists."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code  # noqa: E402

_CLAUSES_PATH = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_OUTPUT_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/ek2c_prose_drg_locked_codes.json"
_PAYMENT_METHOD_PATH = _PROJECT_ROOT / "data/gazette/prose_rules/payment_method_2_2.json"


def mine_prose_drg_locked_from_sut(df: pd.DataFrame) -> set[str]:
    """Codes explicitly listed in §2.2 prose as EK-2/C-only (override barred)."""
    locked: set[str] = set()
    section_mask = df["section_id"].astype(str).str.match(r"^2\.2")
    work = df[section_mask]
    for text in work["text_tr"].astype(str):
        lower = text.casefold()
        if "ek-2/c" not in lower:
            continue
        if not any(
            token in lower
            for token in (
                "üçüncü",
                "ucuncu",
                "hariç",
                "haric",
                "faturalandırılamaz",
                "faturalandirilamaz",
                "yalnızca",
                "yalnizca",
            )
        ):
            continue
        for match in re.findall(r"P\d{5,6}", text, flags=re.IGNORECASE):
            locked.add(normalize_procedure_code(match))
    locked.discard("")
    return locked


def load_json_extra_codes() -> set[str]:
    if not _PAYMENT_METHOD_PATH.is_file():
        return set()
    payload = json.loads(_PAYMENT_METHOD_PATH.read_text(encoding="utf-8"))
    raw = payload.get("prose_drg_locked_codes") or []
    return {
        normalize_procedure_code(str(code)) for code in raw if str(code).strip()
    } - {""}


def build_seed(*, write_payment_method: bool = False) -> dict[str, object]:
    df = pd.read_parquet(_CLAUSES_PATH)
    from_sut = mine_prose_drg_locked_from_sut(df)
    from_json = load_json_extra_codes()
    codes = sorted(from_sut | from_json)
    payload = {
        "title": "EK-2/C procedures prose-mandated to package (§2.2.2 proviso)",
        "source": "sut_clauses.parquet §2.2 explicit P-code lists + payment_method_2_2.json",
        "normalized_codes": codes,
        "count": len(codes),
    }
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if write_payment_method and from_sut:
        pm = json.loads(_PAYMENT_METHOD_PATH.read_text(encoding="utf-8"))
        pm["prose_drg_locked_codes"] = [f"P{code}" for code in codes]
        _PAYMENT_METHOD_PATH.write_text(
            json.dumps(pm, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return payload


def main() -> None:
    payload = build_seed(write_payment_method=True)
    print(f"Wrote {payload['count']} codes → {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
