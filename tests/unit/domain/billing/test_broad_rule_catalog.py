"""The seven broad corpora are inventory data, not confirmed claim findings."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from src.bilun.domain.billing.broad_rule_catalog import load_broad_rule_catalog
from src.bilun.domain.constants import _PROSE_RULES_DIR

pytestmark = pytest.mark.unit

_EXPECTED_FAMILY_COUNTS = {
    "dental_2_4_1": (19, 7, 12, 0),
    "drug_combination_4_2": (53, 37, 4, 12),
    "fatura_inceleme_prose": (91, 89, 2, 0),
    "gap_closing_misc": (46, 31, 15, 0),
    "gap_closing_treatment_2": (43, 24, 19, 0),
    "payment_method_2_2": (42, 9, 0, 33),
    "treatment_pricing_2_4": (202, 129, 73, 0),
}


def test_catalog_accounts_for_every_active_authored_id_without_promoting_it() -> None:
    rows = load_broad_rule_catalog()

    assert len(rows) == 496
    assert len({row.rule_id for row in rows}) == 496
    assert len({(row.source_corpus, row.rule_id) for row in rows}) == 496
    assert len({row.source_file for row in rows}) == 7
    assert Counter(row.billable for row in rows) == {False: 326, True: 125, None: 45}
    assert Counter(row.candidate_classification for row in rows) == {
        "adverse_candidate": 317,
        "positive_or_permission_candidate": 125,
        "review_candidate": 12,
        "information_only": 42,
    }

    for family, (count, no_pay, positive, review) in _EXPECTED_FAMILY_COUNTS.items():
        family_rows = [row for row in rows if row.family == family]
        assert len(family_rows) == count
        assert Counter(row.billable for row in family_rows) == {
            key: value
            for key, value in ((False, no_pay), (True, positive), (None, review))
            if value
        }
        assert [row.family_rule_index for row in family_rows] == list(range(count))


def test_catalog_preserves_raw_action_condition_and_provenance() -> None:
    rows = load_broad_rule_catalog()
    by_family: dict[str, list] = {}
    for row in rows:
        by_family.setdefault(row.family, []).append(row)

    for family, family_rows in by_family.items():
        source_file = Path(family_rows[0].source_file)
        authored = json.loads((_PROSE_RULES_DIR / source_file.name).read_text(encoding="utf-8"))
        assert authored["rule_set_id"] == family
        assert len(authored["rules"]) == len(family_rows)
        for row, rule in zip(family_rows, authored["rules"], strict=True):
            assert row.rule_id == rule["rule_id"]
            assert row.source_corpus == authored["rule_set_id"]
            assert row.source_file == f"data/gazette/prose_rules/{source_file.name}"
            assert row.source_locators == tuple(rule["gate_b_sources"])
            assert row.source_locators
            assert row.fatura_inceleme_ref == rule.get("fatura_inceleme_ref")
            assert row.condition == rule["condition"]
            assert row.action == rule["action"]

    fatura_rows = by_family["fatura_inceleme_prose"]
    assert all(row.fatura_inceleme_ref for row in fatura_rows)
    assert len({row.fatura_inceleme_ref for row in fatura_rows}) == 91
    assert all(row.fatura_inceleme_ref is None for row in rows if row.family != "fatura_inceleme_prose")


def test_special_action_meanings_are_conservative_candidates() -> None:
    by_id = {row.rule_id: row for row in load_broad_rule_catalog()}

    dental = by_id["2.4.1.(2).bone_implant_exception_board_report"]
    assert dental.billable is True
    assert dental.candidate_classification == "positive_or_permission_candidate"
    assert dental.action["surcharge_per_implant_try"] == 750

    fatura = by_id["KARDİYOLOJİ-2.spect_gated_ayri_ayri_odeme"]
    assert fatura.billable is True
    assert "denial_tr" in fatura.action  # Its field name does not make this an adverse row.
    assert fatura.candidate_classification == "positive_or_permission_candidate"
    assert fatura.fatura_inceleme_ref

    review = by_id["4.2.14.C.(pembro_nsclc_pdl1_lt_50).tier_c_review"]
    assert review.billable is None
    assert review.action["clinical_fields_needed"]
    assert review.candidate_classification == "review_candidate"

    payment_no_pay = by_id["2.2.(12).no_pay_without_documentation"]
    payment_unspecified = by_id["2.2.(13).health_report_single_bill"]
    assert payment_no_pay.billable is False
    assert payment_no_pay.candidate_classification == "information_only"
    assert payment_unspecified.billable is None
    assert "billable" not in payment_unspecified.action
    assert payment_unspecified.candidate_classification == "information_only"


def _copy_corpora(destination: Path) -> None:
    for source_file in {row.source_file for row in load_broad_rule_catalog()}:
        filename = Path(source_file).name
        shutil.copyfile(_PROSE_RULES_DIR / filename, destination / filename)


@pytest.mark.parametrize(
    ("corruption", "error"),
    [
        ("duplicate_rule_id", "Duplicate broad rule_id"),
        ("replacement_rule_id", "authored identity sequence changed"),
        ("swapped_rule_order", "authored identity sequence changed"),
        ("numeric_billable", "Invalid billable flag"),
        ("missing_billable", "Missing billable flag"),
        ("missing_action_message", "Missing authored action message"),
        ("blank_action_message", "Missing authored action message"),
        ("missing_locator", "Missing source locator"),
        ("wrong_corpus", "Unexpected rule_set_id"),
        ("missing_authored_row", "Broad prose corpus count changed"),
    ],
)
def test_catalog_rejects_ambiguous_or_unattributed_rows(
    tmp_path: Path, corruption: str, error: str
) -> None:
    _copy_corpora(tmp_path)
    path = tmp_path / "dental_2_4_1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "duplicate_rule_id":
        payload["rules"][1]["rule_id"] = payload["rules"][0]["rule_id"]
    elif corruption == "replacement_rule_id":
        payload["rules"][0]["rule_id"] = "new.unique.authored.id"
    elif corruption == "swapped_rule_order":
        payload["rules"][0], payload["rules"][1] = payload["rules"][1], payload["rules"][0]
    elif corruption == "numeric_billable":
        payload["rules"][0]["action"]["billable"] = 0
    elif corruption == "missing_billable":
        del payload["rules"][0]["action"]["billable"]
    elif corruption in {"missing_action_message", "blank_action_message"}:
        action = payload["rules"][0]["action"]
        for key in ("denial_tr", "payment_tr", "message_tr"):
            if key in action:
                if corruption == "missing_action_message":
                    del action[key]
                else:
                    action[key] = "  "
    elif corruption == "missing_locator":
        payload["rules"][0]["gate_b_sources"] = []
    elif corruption == "wrong_corpus":
        payload["rule_set_id"] = "not_dental"
    else:
        payload["rules"].pop()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_broad_rule_catalog(prose_rules_dir=tmp_path)


@pytest.mark.parametrize("field", ["payment_method", "payment_method_tr"])
def test_catalog_rejects_payment_rows_without_authored_traceability(
    tmp_path: Path, field: str
) -> None:
    _copy_corpora(tmp_path)
    path = tmp_path / "payment_method_2_2.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rules"][0]["action"][field] = "  "
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match=f"Missing authored {field}"):
        load_broad_rule_catalog(prose_rules_dir=tmp_path)
