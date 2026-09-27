"""Authored broad prose-rule inventory, without runtime rule evaluation.

The catalog records what each of the seven existing JSON corpora says. Its
candidate labels are not findings: predicate matching, claim applicability,
source authority, and monetary qualification belong to later checkpoints.
"""

from __future__ import annotations

import json
from hashlib import sha256
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.bilun.domain.constants import _PROSE_RULES_DIR

CandidateClassification = Literal[
    "adverse_candidate",
    "positive_or_permission_candidate",
    "review_candidate",
    "information_only",
]

_FAMILY_FILES: tuple[tuple[str, str], ...] = (
    ("dental_2_4_1", "dental_2_4_1.json"),
    ("drug_combination_4_2", "drug_combination_4_2.json"),
    ("fatura_inceleme_prose", "fatura_inceleme_prose.json"),
    ("gap_closing_misc", "gap_closing_misc.json"),
    ("gap_closing_treatment_2", "gap_closing_treatment_2.json"),
    ("payment_method_2_2", "payment_method_2_2.json"),
    ("treatment_pricing_2_4", "treatment_pricing_2_4.json"),
)
_INFORMATION_ONLY_FAMILY = "payment_method_2_2"
_FATURA_FAMILY = "fatura_inceleme_prose"
_EXPECTED_AUTHORED_RULE_COUNT = 496
# SHA-256 of the authored sequence "family<TAB>rule_id", joined with LF. An
# intentional source edit needs review and an explicit digest update.
_EXPECTED_AUTHORED_SEQUENCE_SHA256 = (
    "58a2e2fe15e15d113a0c0c41732b3808d8d0457bfb5fb1811ec7d8ee9aa146e3"
)


@dataclass(frozen=True)
class BroadRuleCatalogEntry:
    """One authored row, including its original ordering and source evidence."""

    family: str
    rule_id: str
    family_rule_index: int
    source_corpus: str
    source_file: str
    source_locators: tuple[str, ...]
    fatura_inceleme_ref: str | None
    condition: dict[str, Any]
    action: dict[str, Any]
    billable: bool | None
    candidate_classification: CandidateClassification


def _classification(family: str, billable: bool | None) -> CandidateClassification:
    if family == _INFORMATION_ONLY_FAMILY:
        return "information_only"
    if billable is False:
        return "adverse_candidate"
    if billable is True:
        return "positive_or_permission_candidate"
    return "review_candidate"


def load_broad_rule_catalog(
    *, prose_rules_dir: Path | None = None
) -> tuple[BroadRuleCatalogEntry, ...]:
    """Read all seven active corpora and reject ambiguous authored identities.

    No detector is invoked and no row is promoted to a confirmed violation.
    The optional directory lets direct tests validate malformed corpus inputs.
    """
    directory = prose_rules_dir or _PROSE_RULES_DIR
    entries: list[BroadRuleCatalogEntry] = []
    seen_rule_ids: set[str] = set()
    authored_identity_sequence: list[str] = []

    for family, filename in _FAMILY_FILES:
        payload = json.loads((directory / filename).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("rule_set_id") != family:
            raise ValueError(f"Unexpected rule_set_id in {filename}")
        rules = payload.get("rules")
        if not isinstance(rules, list):
            raise ValueError(f"Missing rules list in {filename}")

        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise ValueError(f"Invalid rule at {filename}:{index}")
            rule_id = rule.get("rule_id")
            if not isinstance(rule_id, str) or not rule_id or rule_id != rule_id.strip():
                raise ValueError(f"Invalid rule_id at {filename}:{index}")
            if rule_id in seen_rule_ids:
                raise ValueError(f"Duplicate broad rule_id: {rule_id}")
            seen_rule_ids.add(rule_id)
            authored_identity_sequence.append(f"{family}\t{rule_id}")

            action = rule.get("action")
            if not isinstance(action, dict) or not action:
                raise ValueError(f"Invalid action for {rule_id}")
            if family == _INFORMATION_ONLY_FAMILY:
                for required_key in ("payment_method", "payment_method_tr"):
                    value = action.get(required_key)
                    if not isinstance(value, str) or not value.strip():
                        raise ValueError(f"Missing authored {required_key} for {rule_id}")
            elif not any(
                isinstance(action.get(key), str) and action[key].strip()
                for key in ("denial_tr", "payment_tr", "message_tr")
            ):
                raise ValueError(f"Missing authored action message for {rule_id}")
            if family != _INFORMATION_ONLY_FAMILY and "billable" not in action:
                raise ValueError(f"Missing billable flag for {rule_id}")
            billable = action.get("billable")
            if billable is not None and type(billable) is not bool:
                raise ValueError(f"Invalid billable flag for {rule_id}")

            condition = rule.get("condition")
            if not isinstance(condition, dict):
                raise ValueError(f"Invalid condition for {rule_id}")
            locators = rule.get("gate_b_sources")
            if (
                not isinstance(locators, list)
                or not locators
                or any(not isinstance(ref, str) or not ref.strip() for ref in locators)
            ):
                raise ValueError(f"Missing source locator for {rule_id}")

            fatura_ref = rule.get("fatura_inceleme_ref")
            if family == _FATURA_FAMILY:
                if not isinstance(fatura_ref, str) or not fatura_ref.strip():
                    raise ValueError(f"Missing Fatura İnceleme reference for {rule_id}")
            elif fatura_ref is not None:
                raise ValueError(f"Unexpected Fatura İnceleme reference for {rule_id}")

            entries.append(
                BroadRuleCatalogEntry(
                    family=family,
                    rule_id=rule_id,
                    family_rule_index=index,
                    source_corpus=family,
                    source_file=f"data/gazette/prose_rules/{filename}",
                    source_locators=tuple(locators),
                    fatura_inceleme_ref=fatura_ref,
                    condition=deepcopy(condition),
                    action=deepcopy(action),
                    billable=billable,
                    candidate_classification=_classification(family, billable),
                )
            )

    if len(entries) != _EXPECTED_AUTHORED_RULE_COUNT:
        raise ValueError(
            "Broad prose corpus count changed: "
            f"expected {_EXPECTED_AUTHORED_RULE_COUNT}, found {len(entries)}"
        )
    actual_digest = sha256("\n".join(authored_identity_sequence).encode("utf-8")).hexdigest()
    if actual_digest != _EXPECTED_AUTHORED_SEQUENCE_SHA256:
        raise ValueError("Broad prose authored identity sequence changed")
    return tuple(entries)
