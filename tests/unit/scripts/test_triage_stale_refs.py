"""Unit tests for scripts/sut/triage_stale_refs.py (TIER-1 triage proposals).

Hermetic fixtures only — no parquet dependency. The C006549-style anti-VEGF
example from plans/update/2026-08-06-stale-clause-triage-plan.md is the
golden fixture: the clause is in force but carries a mülga sentence about
"yükleme dozu"; a rule with loading_dose_count must land in class A via the
KEY_TOKEN_MAP, and a rule quoting the struck phrase verbatim must land in A
via token overlap.
"""

from __future__ import annotations

import polars as pl
import pytest

from scripts.sut.triage_stale_refs import (
    A_THRESHOLD,
    REVIEW_THRESHOLD,
    build_triage,
    drug_name_hit,
    extract_struck_content,
    normalize_tokens,
    propose_class,
    render_report,
    rule_tokens,
    score_overlap,
)

pytestmark = pytest.mark.unit

# Golden fixture: real shape of clause C006549 (4.2.33.(7)) — in-force text
# with an internally mülga'd sentence about loading doses.
_TEXT_TR = (
    "(7) Ranibizumab veya aflibersept etkin maddeli ilaçlar arasında ilaç "
    "değişimi gereken hallerde tedaviye bevacizumab etkin maddeli ilaç ile "
    "yükleme dozu tamamlanmak suretiyle devam edilecektir. Bevacizumab etkin "
    "maddeli ilaçla tedaviye cevapsızlık/yetersiz cevap alınması durumunda "
    "diğer etkin maddeli ilaç ile tedaviye (Mülga:RG-16/06/2020-31157/19-c md. "
    "Yürürlük: 24/06/2020) yükleme dozu yapılarak devam edilebilir."
)
_IN_FORCE = (
    "(7) Ranibizumab veya aflibersept etkin maddeli ilaçlar arasında ilaç "
    "değişimi gereken hallerde tedaviye bevacizumab etkin maddeli ilaç ile "
    "yükleme dozu tamamlanmak suretiyle devam edilecektir. Bevacizumab etkin "
    "maddeli ilaçla tedaviye cevapsızlık/yetersiz cevap alınması durumunda "
    "diğer etkin maddeli ilaç ile tedaviye (Mülga:RG-16/06/2020-31157/19-c md. "
    "Yürürlük: 24/06/2020)  devam edilebilir."
)


# --------------------------------------------------------------------------- #
# Diff extraction
# --------------------------------------------------------------------------- #
def test_extract_struck_content_returns_only_removed_words() -> None:
    struck = extract_struck_content(_TEXT_TR, _IN_FORCE)
    assert "yükleme" in struck and "yapılarak" in struck
    # amendment metadata is shared by both texts → NOT part of the diff
    assert "Mülga" not in struck
    # in-force content must not leak into the diff
    assert "tamamlanmak" not in struck


def test_extract_struck_content_identical_texts_empty() -> None:
    assert extract_struck_content(_TEXT_TR, _TEXT_TR) == ""
    assert extract_struck_content(None, None) == ""


# --------------------------------------------------------------------------- #
# Token normalization
# --------------------------------------------------------------------------- #
def test_normalize_tokens_folds_turkish_case() -> None:
    assert normalize_tokens("İŞĞÜÖÇ") == ["işğüöç"]
    assert normalize_tokens("Yükleme Dozu") == ["yükleme", "dozu"]


def test_normalize_tokens_drops_amendment_metadata() -> None:
    tokens = normalize_tokens(
        "(Mülga:RG-16/06/2020-31157/19-c md. Yürürlük: 24/06/2020) yükleme dozu"
    )
    assert "mülga" not in tokens
    assert "yürürlük" not in tokens
    assert not any(t.startswith("16") or t.startswith("2020") for t in tokens)
    assert "yükleme" in tokens and "dozu" in tokens


# --------------------------------------------------------------------------- #
# Rule tokenization
# --------------------------------------------------------------------------- #
def test_rule_tokens_include_semantic_key_tokens() -> None:
    """loading_dose_count is numeric — its semantics only reach the clause
    text via KEY_TOKEN_MAP. This is the C006549/anti-VEGF path."""
    tokens = rule_tokens({"loading_dose_count": 3, "rule_id": "x"})
    assert {"yükleme", "dozu", "doz"} <= tokens


def test_rule_tokens_skip_structural_fields() -> None:
    tokens = rule_tokens(
        {
            "rule_id": "4.2.33.some_rule",
            "gate_b_sources": ["4.2.33.(7)"],
            "sut_section": "4.2.33",
            "message_tr": "Bevacizumab raporu",
        }
    )
    assert "bevacizumab" in tokens and "raporu" in tokens
    assert "4" not in tokens  # sut_section / coordinates excluded


def test_rule_tokens_collect_list_strings() -> None:
    tokens = rule_tokens({"drug_names": ["Bevacizumab"], "icd10_codes": ["H35.3"]})
    assert "bevacizumab" in tokens


# --------------------------------------------------------------------------- #
# Drug-name hit
# --------------------------------------------------------------------------- #
def test_drug_name_hit_matches_struck_content() -> None:
    struck = set(normalize_tokens("bevacizumab ile tedaviye devam edilebilir"))
    assert drug_name_hit({"drug_names": ["Bevacizumab"]}, struck) is True
    assert drug_name_hit({"drug_names": ["Ranibizumab"]}, struck) is False
    assert drug_name_hit({}, struck) is False
    assert drug_name_hit({"drug_names": ["Bevacizumab"]}, set()) is False


# --------------------------------------------------------------------------- #
# Scoring + classification thresholds
# --------------------------------------------------------------------------- #
def test_score_overlap_fraction_and_matches() -> None:
    diff = {"yükleme", "dozu", "yapılarak", "devam"}
    score, matched = score_overlap(diff, {"yükleme", "dozu", "rapor"})
    assert matched == {"yükleme", "dozu"}
    assert score == pytest.approx(0.5)
    assert score_overlap(set(), {"yükleme"}) == (0.0, set())


def test_propose_class_thresholds() -> None:
    diff = {"a", "b", "c", "d"}
    assert propose_class(A_THRESHOLD, False, diff) == "A"
    assert propose_class(REVIEW_THRESHOLD, False, diff) == "REVIEW"
    assert propose_class(REVIEW_THRESHOLD - 0.01, False, diff) == "B"
    # drug hit forces A regardless of score
    assert propose_class(0.0, True, diff) == "A"
    # empty diff is always B (marker without removed text)
    assert propose_class(1.0, True, set()) == "B"


# --------------------------------------------------------------------------- #
# build_triage end-to-end (synthetic frames)
# --------------------------------------------------------------------------- #
def _t1_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "rule_set_id": ["anti_vegf_prose", "anti_vegf_prose", "benign_set"],
            "rule_id": ["loading_rule", "quote_rule", "unrelated_rule"],
            "gate_b_ref": ["4.2.33.(7)"] * 3,
            "clause_id": ["C006549"] * 3,
        }
    )


def _clauses_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "clause_id": ["C006549"],
            "clause_coordinate": ["4.2.33.(7)"],
            "text_tr": [_TEXT_TR],
            "in_force_text": [_IN_FORCE],
            "amendment_refs": ['["RG-16/06/2020/31157"]'],
        }
    )


_RULES = {
    ("anti_vegf_prose", "loading_rule"): {
        "rule_id": "loading_rule",
        "loading_dose_count": 3,
        "message_tr": "bevacizumab ile devam",
    },
    ("anti_vegf_prose", "quote_rule"): {
        "rule_id": "quote_rule",
        "message_tr": "yükleme dozu yapılarak devam edilebilir",
    },
    ("benign_set", "unrelated_rule"): {
        "rule_id": "unrelated_rule",
        "message_tr": "diyaliz seans ücreti ek ödeme",
    },
}


def test_build_triage_classifies_golden_fixture() -> None:
    triage = build_triage(_t1_frame(), _clauses_frame(), rules=_RULES)
    assert triage.height == 3
    by_rule = {r["rule_id"]: r for r in triage.iter_rows(named=True)}

    # The C006549 loading-dose case: "yükleme dozu" tokens survive in the
    # in-force text (forward switch), so only "yapılarak" is effectively
    # repealed — loading_rule does not touch it → B. This matches the
    # Phase-2 human verdict (KEEP) for 4.2.33.general_switch_to_bevacizumab.
    assert by_rule["loading_rule"]["proposed_class"] == "B"
    assert by_rule["loading_rule"]["drug_name_hit"] is False
    # verbatim quote of the struck phrase → covers the effective token → A
    assert by_rule["quote_rule"]["proposed_class"] == "A"
    assert by_rule["quote_rule"]["overlap_score"] >= A_THRESHOLD
    assert by_rule["quote_rule"]["matched_tokens"] == "yapılarak"
    # zero overlap with struck content → B
    assert by_rule["unrelated_rule"]["proposed_class"] == "B"
    assert by_rule["unrelated_rule"]["overlap_score"] == 0.0
    # amendment metadata survives for RG grouping
    assert by_rule["loading_rule"]["amendment_refs"] == "RG-16/06/2020/31157"


def test_build_triage_empty_input() -> None:
    empty = _t1_frame().head(0)
    triage = build_triage(empty, _clauses_frame(), rules=_RULES)
    assert triage.height == 0
    assert "proposed_class" in triage.columns


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def test_render_report_contains_all_class_sections() -> None:
    triage = build_triage(_t1_frame(), _clauses_frame(), rules=_RULES)
    md = render_report(triage, "2026-08-06")
    assert "Sınıf A" in md
    assert "Sınıf REVIEW" in md
    assert "Sınıf B" in md
    assert "Amendment RG grupları" in md
    assert "RG-16/06/2020/31157" in md
    assert "quote_rule" in md
