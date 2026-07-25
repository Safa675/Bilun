"""Restamp SUT prose manifests to canonical-v1 (Track C1).

Skips fatura (non-SUT). Preserves encoded + emr/non_actionable/deferred
buckets and any other ``*_clause_ids`` lists that coverage's
``encoded_like_clause_ids`` already counted. L1.8 copay is canonical after Track F.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.sut.prose.manifest_index import (
    build_canonical_encoded_shell,
    encoded_like_clause_ids,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"

# Documented exceptions — not restamped in C1.
_SKIP = frozenset(
    {
        "fatura_inceleme_prose_manifest.json",
    }
)

_REQUIRED = (
    "manifest_version",
    "rule_set_id",
    "section_id",
    "section_clause_total",
    "encoded_clause_ids",
    "tier_c_deferred_clause_ids",
    "emr_blocked_clause_ids",
    "non_actionable_clause_ids",
    "tier_a_pending_clause_ids",
    "tier_b_pending_clause_ids",
    "clause_traces",
)

_STANDARD_BUCKETS = frozenset(
    {
        "encoded_clause_ids",
        "tier_c_deferred_clause_ids",
        "emr_blocked_clause_ids",
        "non_actionable_clause_ids",
        "tier_a_pending_clause_ids",
        "tier_b_pending_clause_ids",
    }
)

# Legacy key → canonical rule_set_id when rule_set_id is missing.
_RULE_SET_ALIASES: dict[str, str] = {
    "L2.2_gazette_repricing_encoded_manifest.json": "gazette_repricing_prose",
    "L2.2_procedure_pairing_encoded_manifest.json": "procedure_pairing_prose",
    "L3.1_material_pairing_encoded_manifest.json": "material_pairing_prose",
    "L2_payment_pricing_r6_manifest.json": "payment_pricing_r6",
    "L4.2_drug_indication_eye_mid_a_r6_manifest.json": "drug_indication_eye_mid_a_r6",
    "L4.2_drug_indication_eye_mid_b_r6_manifest.json": "drug_indication_eye_mid_b_r6",
    "L4.2_drug_indication_tail_a_r6_manifest.json": "drug_indication_tail_a_r6",
    "L4_drug_ek4a_r6_manifest.json": "drug_ek4a_r6",
    "L_r6_billing_def_encoded_manifest.json": "billing_def_r6",
    "L_r6_referral_encoded_manifest.json": "referral_r6",
    "L_r6_specialty_leftover_manifest.json": "specialty_leftover_r6",
}


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x) for x in value if x]


def _rule_set_id(path: Path, payload: dict) -> str:
    for key in ("rule_set_id", "rule_id"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    alias = _RULE_SET_ALIASES.get(path.name)
    if alias:
        return alias
    return path.stem


def _needs_restamp(payload: dict) -> bool:
    if payload.get("manifest_version") != "canonical-v1":
        return True
    return any(key not in payload for key in _REQUIRED)


def _extra_clause_id_lists(payload: dict) -> dict[str, list[str]]:
    """Preserve non-standard ``*_clause_ids`` that feed encoded_like coverage."""
    extras: dict[str, list[str]] = {}
    for key, value in payload.items():
        if key in _STANDARD_BUCKETS:
            continue
        if not isinstance(value, list):
            continue
        if not key.endswith("_clause_ids"):
            continue
        if key.endswith(("_deferred_clause_ids", "_pending_clause_ids")):
            # Still preserve for load_drug_bucket / encoded_like exclusion edge cases
            # but deferred/pending suffixes are excluded from encoded_like — keep anyway.
            extras[key] = _as_str_list(value)
            continue
        extras[key] = _as_str_list(value)
    return extras


def _pad_canonical(path: Path, payload: dict) -> dict[str, Any]:
    """Fill missing required keys without dropping Track F extra lists."""
    out = dict(payload)
    out["manifest_version"] = "canonical-v1"
    out["rule_set_id"] = _rule_set_id(path, out)
    out.setdefault("section_id", "")
    out.setdefault("encoded_clause_ids", [])
    out.setdefault("tier_c_deferred_clause_ids", [])
    out.setdefault("emr_blocked_clause_ids", [])
    out.setdefault("non_actionable_clause_ids", [])
    out.setdefault("tier_a_pending_clause_ids", [])
    out.setdefault("tier_b_pending_clause_ids", [])
    for key in (
        "encoded_clause_ids",
        "tier_c_deferred_clause_ids",
        "emr_blocked_clause_ids",
        "non_actionable_clause_ids",
        "tier_a_pending_clause_ids",
        "tier_b_pending_clause_ids",
    ):
        out[key] = _as_str_list(out.get(key))
    out.setdefault("encoded_clause_count", len(out["encoded_clause_ids"]))
    out.setdefault("tier_c_deferred_count", len(out["tier_c_deferred_clause_ids"]))
    out.setdefault("emr_blocked_count", len(out["emr_blocked_clause_ids"]))
    out.setdefault("non_actionable_count", len(out["non_actionable_clause_ids"]))
    out.setdefault("tier_a_pending_count", len(out["tier_a_pending_clause_ids"]))
    out.setdefault("tier_b_pending_count", len(out["tier_b_pending_clause_ids"]))
    if "section_clause_total" not in out or not isinstance(out["section_clause_total"], int):
        out["section_clause_total"] = len(encoded_like_clause_ids(out))
    if "clause_traces" not in out or not isinstance(out["clause_traces"], list):
        traces: list[dict[str, Any]] = []
        for cid in out["encoded_clause_ids"]:
            traces.append({"clause_id": cid, "manifest_status": "encoded"})
        for cid in out["tier_c_deferred_clause_ids"]:
            traces.append({"clause_id": cid, "manifest_status": "tier_c_deferred"})
        for cid in out["emr_blocked_clause_ids"]:
            traces.append({"clause_id": cid, "manifest_status": "emr_blocked"})
        for cid in out["non_actionable_clause_ids"]:
            traces.append({"clause_id": cid, "manifest_status": "non_actionable"})
        out["clause_traces"] = traces
    return out


def restamp_payload(path: Path, payload: dict) -> dict:
    """Build or pad canonical manifest preserving coverage-critical lists."""
    if payload.get("manifest_version") == "canonical-v1":
        return _pad_canonical(path, payload)

    encoded = _as_str_list(payload.get("encoded_clause_ids"))
    tier_c = _as_str_list(payload.get("tier_c_deferred_clause_ids"))
    emr = _as_str_list(payload.get("emr_blocked_clause_ids"))
    non_actionable = _as_str_list(payload.get("non_actionable_clause_ids"))
    tier_a = _as_str_list(payload.get("tier_a_pending_clause_ids"))
    tier_b = _as_str_list(payload.get("tier_b_pending_clause_ids"))

    section_id = str(payload.get("section_id") or "")
    rules_in_json = payload.get("rules_in_json")
    if not isinstance(rules_in_json, int):
        rules_in_json = payload.get("rule_count") if isinstance(payload.get("rule_count"), int) else None
    effective_date = payload.get("effective_date")
    if not isinstance(effective_date, str):
        effective_date = None

    total = payload.get("section_clause_total")
    if not isinstance(total, int):
        total = None

    extras = _extra_clause_id_lists(payload)
    return build_canonical_encoded_shell(
        rule_set_id=_rule_set_id(path, payload),
        encoded_clause_ids=encoded,
        section_id=section_id,
        rules_in_json=rules_in_json,
        effective_date=effective_date,
        section_clause_total=total,
        tier_c_deferred_clause_ids=tier_c,
        emr_blocked_clause_ids=emr,
        non_actionable_clause_ids=non_actionable,
        tier_a_pending_clause_ids=tier_a,
        tier_b_pending_clause_ids=tier_b,
        extra_keys=extras or None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    parser.add_argument("--force", action="store_true", help="Restamp even if already complete")
    args = parser.parse_args(argv)

    changed = 0
    skipped = 0
    for path in sorted(_MANIFEST_DIR.glob("*.json")):
        if path.name in _SKIP:
            skipped += 1
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not args.force and not _needs_restamp(payload):
            continue
        before_like = encoded_like_clause_ids(payload)
        new_payload = restamp_payload(path, payload)
        after_like = encoded_like_clause_ids(new_payload)
        if before_like != after_like:
            missing = sorted(before_like - after_like)
            extra = sorted(after_like - before_like)
            print(
                f"ERROR {path.name}: encoded_like drift "
                f"missing={missing[:8]} (n={len(missing)}) "
                f"extra={extra[:8]} (n={len(extra)})",
                file=sys.stderr,
            )
            return 1
        print(
            f"{'[dry] ' if args.dry_run else ''}"
            f"{path.name}: {payload.get('manifest_version')!r} → canonical-v1 "
            f"(encoded={len(_as_str_list(new_payload.get('encoded_clause_ids')))}, "
            f"like={len(after_like)})"
        )
        if not args.dry_run:
            path.write_text(
                json.dumps(new_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        changed += 1

    print(f"restamped={changed} skipped_exceptions={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
