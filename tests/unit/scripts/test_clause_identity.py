"""Unit tests for clause_identity dual-read (god plan Track A1 / A3)."""

from __future__ import annotations

import polars as pl
import pytest

from scripts.sut.prose.clause_identity import (
    CONTENT_HASH_LENGTH,
    AmbiguousClauseCiteError,
    NonEncodeEligibleCiteError,
    UnknownClauseCiteError,
    assert_gate_b_sources_resolvable,
    clause_key,
    content_hash,
    encoded_clause_ids_from_rules,
    filter_encode_eligible,
    is_clause_coordinate,
    is_clause_id,
    is_clause_key,
    is_encode_eligible_row,
    is_gate_b_source_ref,
    normalize_for_hash,
    resolve_gate_b_ref_to_clause_ids,
    resolve_gate_b_sources_to_clause_ids,
)


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "clause_id": ["C000001", "C000002", "C000003", "C000004", "C000005"],
            "clause_coordinate": [
                "1.1.(1)",
                "4.2.14.C.a",
                "4.2.14.C.a",
                "1.2",
                None,
            ],
            "clause_type": ["fikra", "bent", "bent", "section_heading", "chapter"],
            "clause_number": [1, None, None, None, None],
            "clause_letter": [None, "a", "a", None, None],
            "is_in_force": [True, True, True, True, True],
        }
    )


def test_ref_classifiers() -> None:
    assert is_clause_id("C000646")
    assert is_clause_id("F000001")
    assert not is_clause_id("4.2.24.B.(3)")
    assert is_clause_coordinate("4.2.24.B.(3)")
    assert is_clause_coordinate("4.2.24.B.(3).a")
    assert is_clause_coordinate("2.6.1.B-1.(1)")
    assert is_clause_coordinate("1.1")
    assert not is_clause_coordinate("C000646")
    assert is_gate_b_source_ref("C000646")
    assert is_gate_b_source_ref("1.8.2.(1)")
    assert not is_gate_b_source_ref("not-a-cite")


def test_encode_eligible_predicate() -> None:
    frame = _frame()
    eligible = filter_encode_eligible(frame)
    assert set(eligible["clause_id"].to_list()) == {"C000001", "C000002", "C000003"}
    assert is_encode_eligible_row(frame.row(0, named=True))
    assert not is_encode_eligible_row(frame.row(3, named=True))


def test_resolve_clause_id_passthrough() -> None:
    assert resolve_gate_b_ref_to_clause_ids("C000001", _frame()) == ["C000001"]


def test_resolve_unique_coordinate() -> None:
    assert resolve_gate_b_ref_to_clause_ids("1.1.(1)", _frame()) == ["C000001"]


def test_resolve_ambiguous_coordinate_raises() -> None:
    with pytest.raises(AmbiguousClauseCiteError, match="4.2.14.C.a"):
        resolve_gate_b_ref_to_clause_ids("4.2.14.C.a", _frame())


def test_resolve_ambiguous_allowed() -> None:
    ids = resolve_gate_b_ref_to_clause_ids(
        "4.2.14.C.a",
        _frame(),
        allow_ambiguous=True,
    )
    assert ids == ["C000002", "C000003"]


def test_resolve_unknown_raises() -> None:
    with pytest.raises(UnknownClauseCiteError):
        resolve_gate_b_ref_to_clause_ids("9.9.9.(1)", _frame())


def test_resolve_unknown_clause_id_passthrough() -> None:
    assert resolve_gate_b_ref_to_clause_ids("C999999", _frame()) == ["C999999"]


def test_encoded_clause_ids_from_rules_resolves_coordinates() -> None:
    rules = [
        {"rule_id": "r1", "gate_b_sources": ["C000001", "1.1.(1)"]},
    ]
    assert encoded_clause_ids_from_rules(rules, _frame()) == {"C000001"}


def test_encoded_clause_ids_without_frame_keeps_opaque_strings() -> None:
    rules = [{"rule_id": "r1", "gate_b_sources": ["1.1.(1)", "C000001"]}]
    assert encoded_clause_ids_from_rules(rules, None) == {"1.1.(1)", "C000001"}


def test_assert_gate_b_sources_resolvable_flags_ambiguous() -> None:
    rules = [{"rule_id": "r_bad", "gate_b_sources": ["4.2.14.C.a"]}]
    with pytest.raises(AmbiguousClauseCiteError, match="r_bad"):
        assert_gate_b_sources_resolvable(rules, _frame(), rule_set_id="demo")


def test_a3_ambiguous_error_lists_candidate_c_ids() -> None:
    with pytest.raises(AmbiguousClauseCiteError, match=r"C000002\(bent\).*C000003\(bent\)"):
        resolve_gate_b_ref_to_clause_ids(
            "4.2.14.C.a",
            _frame(),
            encode_eligible_only=True,
        )


def test_a3_heading_coordinate_refused() -> None:
    with pytest.raises(NonEncodeEligibleCiteError, match="section_heading"):
        resolve_gate_b_ref_to_clause_ids(
            "1.2",
            _frame(),
            encode_eligible_only=True,
        )


def test_a3_heading_clause_id_refused() -> None:
    with pytest.raises(NonEncodeEligibleCiteError, match="C000004"):
        resolve_gate_b_ref_to_clause_ids(
            "C000004",
            _frame(),
            encode_eligible_only=True,
        )


def test_a3_prose_clause_id_allowed() -> None:
    """Opaque C* may still target ``prose`` rows; only structural types are banned."""
    frame = pl.DataFrame(
        {
            "clause_id": ["C000099"],
            "clause_coordinate": [None],
            "clause_type": ["prose"],
            "clause_number": [None],
            "clause_letter": [None],
            "is_in_force": [True],
        }
    )
    assert resolve_gate_b_ref_to_clause_ids(
        "C000099",
        frame,
        encode_eligible_only=True,
    ) == ["C000099"]


def test_clause_type_overrides_flip_heading_to_prose() -> None:
    from scripts.sut.prose.clause_type_overrides import apply_clause_type_overrides

    frame = pl.DataFrame(
        {
            "clause_id": ["C000852", "C000001"],
            "clause_type": ["section_heading", "fikra"],
            "is_heading": [True, False],
        }
    )
    out = apply_clause_type_overrides(
        frame,
        {"C000852": {"clause_type": "prose"}},
    )
    assert out.filter(pl.col("clause_id") == "C000852")["clause_type"][0] == "prose"
    assert out.filter(pl.col("clause_id") == "C000852")["is_heading"][0] is False
    assert out.filter(pl.col("clause_id") == "C000001")["clause_type"][0] == "fikra"


def test_a3_assert_rejects_heading_cite() -> None:
    rules = [{"rule_id": "r_head", "gate_b_sources": ["1.2"]}]
    with pytest.raises(NonEncodeEligibleCiteError, match="r_head"):
        assert_gate_b_sources_resolvable(rules, _frame(), rule_set_id="demo")


def test_a3_assert_rejects_clause_id_absent_from_corpus() -> None:
    """Track E — a C* cite removed by re-extraction must fail loud, not pass."""
    rules = [{"rule_id": "r_gone", "gate_b_sources": ["C999999"]}]
    with pytest.raises(UnknownClauseCiteError, match="C999999"):
        assert_gate_b_sources_resolvable(rules, _frame(), rule_set_id="demo")


def test_a3_assert_accepts_clause_id_present_in_corpus() -> None:
    rules = [{"rule_id": "r_ok", "gate_b_sources": ["C000001"]}]
    assert_gate_b_sources_resolvable(rules, _frame(), rule_set_id="demo")


def test_a3_encode_eligible_disambiguates_mixed_types() -> None:
    """Coordinate with one encode-eligible + one heading → unique after filter."""
    frame = pl.DataFrame(
        {
            "clause_id": ["C000010", "C000011"],
            "clause_coordinate": ["2.1.(1)", "2.1.(1)"],
            "clause_type": ["fikra", "section_heading"],
            "clause_number": [1, None],
            "clause_letter": [None, None],
            "is_in_force": [True, True],
        }
    )
    assert resolve_gate_b_ref_to_clause_ids(
        "2.1.(1)",
        frame,
        encode_eligible_only=True,
    ) == ["C000010"]


def test_resolve_gate_b_sources_batch() -> None:
    assert resolve_gate_b_sources_to_clause_ids(
        ["C000001", "1.1.(1)"],
        _frame(),
    ) == {"C000001"}


# ---------------------------------------------------------------------------
# Track E — stable clause identity (content hash) tests.
# Golden fixtures lock the normalization: any change to normalize_for_hash
# flips these hashes and fails CI. Texts are real clauses from
# sut_clauses.parquet (source_effective_date=2026-05-23), hardcoded so the
# test does not depend on reading the corpus.
# ---------------------------------------------------------------------------

_C006549_IN_FORCE = (
    "(7) Ranibizumab veya aflibersept etkin maddeli ilaçlar arasında ilaç değişimi "
    "gereken hallerde tedaviye bevacizumab etkin maddeli ilaç ile yükleme dozu "
    "tamamlanmak suretiyle devam edilecektir. Bevacizumab etkin maddeli ilaçla "
    "tedaviye cevapsızlık/yetersiz cevap alınması durumunda diğer etkin maddeli ilaç "
    "ile tedaviye (Mülga:RG-16/06/2020-31157/19-c md. Yürürlük: 24/06/2020)  devam "
    "edilebilir."
)
_C006549_TEXT_TR = (
    "(7) Ranibizumab veya aflibersept etkin maddeli ilaçlar arasında ilaç değişimi "
    "gereken hallerde tedaviye bevacizumab etkin maddeli ilaç ile yükleme dozu "
    "tamamlanmak suretiyle devam edilecektir. Bevacizumab etkin maddeli ilaçla "
    "tedaviye cevapsızlık/yetersiz cevap alınması durumunda diğer etkin maddeli ilaç "
    "ile tedaviye (Mülga:RG-16/06/2020-31157/19-c md. Yürürlük: 24/06/2020) yükleme "
    "dozu yapılarak devam edilebilir."
)
_C006575_IN_FORCE = (
    "(1) Siklosporin içeren immünsupresif göz damlaları, göz hastalıkları uzman "
    "hekimi tarafından düzenlenen bir yıl süreli uzman hekim raporuna dayanılarak göz "
    "hastalıkları uzman hekimlerince reçete edilebilir."
)

GOLDEN_CONTENT_HASHES = [
    ("C006549 in_force", _C006549_IN_FORCE, "797a956a"),
    ("C006549 text_tr", _C006549_TEXT_TR, "79b53d74"),
    ("C006575 in_force", _C006575_IN_FORCE, "c14348d7"),
]


def test_normalize_is_deterministic() -> None:
    text = "  Siklosporin   içeren\n\ngöz damlaları  "
    assert normalize_for_hash(text) == normalize_for_hash(text)


def test_normalize_folds_whitespace_and_line_endings() -> None:
    assert normalize_for_hash("a  b\n\nc\r\nd") == "a b c d"


def test_normalize_strips_edges() -> None:
    assert normalize_for_hash("  x  ") == "x"


def test_normalize_preserves_case() -> None:
    # Legal text is case-sensitive; no casefolding.
    assert normalize_for_hash("SUT EK-2/C") != normalize_for_hash("sut ek-2/c")


def test_normalize_preserves_turkish_chars() -> None:
    # NFKC must not mangle Turkish letters.
    assert normalize_for_hash("İlaç, şişe, değişim, sağlık") == "İlaç, şişe, değişim, sağlık"


def test_content_hash_stable_under_cosmetic_variation() -> None:
    a = content_hash("Siklosporin içeren immünsupresif göz damlaları")
    b = content_hash("Siklosporin   içeren\nimmünsupresif  göz damlaları")
    assert a == b


def test_content_hash_flips_on_substantive_change() -> None:
    a = content_hash("Siklosporin içeren göz damlaları")
    b = content_hash("Siklosporin içeren göz damlaları uzman hekim raporu")
    assert a != b


def test_content_hash_length() -> None:
    assert len(content_hash("x")) == CONTENT_HASH_LENGTH


def test_golden_content_hashes_lock_normalization() -> None:
    for label, text, expected in GOLDEN_CONTENT_HASHES:
        assert content_hash(text) == expected, (
            f"{label}: content hash changed — normalize_for_hash drifted"
        )


def test_golden_in_force_differs_from_text_tr_when_struck() -> None:
    # C006549 has struck content, so in_force_text != text_tr -> different hash.
    assert content_hash(_C006549_IN_FORCE) != content_hash(_C006549_TEXT_TR)


def test_clause_key_uses_coordinate_and_hash() -> None:
    key = clause_key("4.2.33.D.(1)", _C006575_IN_FORCE)
    assert key == f"4.2.33.D.(1)#{content_hash(_C006575_IN_FORCE)}"


def test_clause_key_falls_back_to_hash_without_coordinate() -> None:
    assert clause_key(None, _C006575_IN_FORCE) == content_hash(_C006575_IN_FORCE)
    assert clause_key("", _C006575_IN_FORCE) == content_hash(_C006575_IN_FORCE)


def test_add_identity_columns_adds_stable_columns() -> None:
    import pandas as pd

    from scripts.sut.prose.extractor import add_identity_columns

    frame = pd.DataFrame(
        {
            "clause_coordinate": ["4.2.33.D.(1)", None],
            "in_force_text": ["metin a", "metin b"],
        }
    )
    out = add_identity_columns(frame)
    assert "content_hash" in out.columns
    assert "clause_key" in out.columns
    assert out["content_hash"][0] == content_hash("metin a")
    assert out["clause_key"][0] == f"4.2.33.D.(1)#{content_hash('metin a')}"
    # no coordinate -> hash-only key
    assert out["clause_key"][1] == content_hash("metin b")


def _key_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "clause_id": ["C000001", "C000002", "C000003"],
            "clause_coordinate": ["4.2.14.C.(1)", "4.2.14.C.(1)", "1.1.(1)"],
            "clause_type": ["numbered_item", "numbered_item", "fikra"],
            "clause_number": [1, 1, 1],
            "clause_letter": [None, None, None],
            "is_in_force": [True, True, True],
            "content_hash": [
                content_hash("ilac A"),
                content_hash("ilac B"),
                content_hash("ilac C"),
            ],
        }
    )


def test_clause_key_disambiguates_collision() -> None:
    frame = _key_frame()
    ka = clause_key("4.2.14.C.(1)", "ilac A")
    kb = clause_key("4.2.14.C.(1)", "ilac B")
    assert resolve_gate_b_ref_to_clause_ids(ka, frame) == ["C000001"]
    assert resolve_gate_b_ref_to_clause_ids(kb, frame) == ["C000002"]


def test_clause_key_is_valid_gate_b_ref() -> None:
    ka = clause_key("4.2.14.C.(1)", "ilac A")
    assert is_clause_key(ka)
    assert is_gate_b_source_ref(ka)
    assert is_gate_b_source_ref(content_hash("ilac C"))  # bare hash


def test_clause_key_content_mismatch_raises() -> None:
    frame = _key_frame()
    with pytest.raises(UnknownClauseCiteError, match="content mismatch"):
        resolve_gate_b_ref_to_clause_ids("4.2.14.C.(1)#deadbeef", frame)


def test_clause_key_bare_hash_resolves() -> None:
    frame = _key_frame()
    assert resolve_gate_b_ref_to_clause_ids(content_hash("ilac C"), frame) == ["C000003"]


def test_clause_key_identical_content_returns_all() -> None:
    frame = pl.DataFrame(
        {
            "clause_id": ["C000001", "C000002"],
            "clause_coordinate": ["4.2.34.(1)", "4.2.34.(1)"],
            "clause_type": ["numbered_item", "numbered_item"],
            "clause_number": [1, 1],
            "clause_letter": [None, None],
            "is_in_force": [True, True],
            "content_hash": [content_hash("ayni"), content_hash("ayni")],
        }
    )
    key = clause_key("4.2.34.(1)", "ayni")
    assert resolve_gate_b_ref_to_clause_ids(key, frame) == ["C000001", "C000002"]


# --------------------------------------------------------------------------- #
# Track E Phase 5/6 — re-extraction stability.
#
# The whole point of clause_key = coord#content_hash is that an UNCHANGED clause
# keeps a byte-identical key across re-extraction, so references survive. These
# tests lock that guarantee: identity derivation must be deterministic.
# --------------------------------------------------------------------------- #
def test_add_identity_columns_is_deterministic() -> None:
    """Same input frame → byte-identical content_hash / clause_key columns."""
    import pandas as pd

    from scripts.sut.prose.extractor import add_identity_columns

    frame = pd.DataFrame(
        {
            "clause_coordinate": ["4.2.33.D.(1)", "1.8.1.a", None],
            "in_force_text": ["metin a", "50 TL", "metin c"],
        }
    )
    first = add_identity_columns(frame)
    second = add_identity_columns(frame)
    assert first["content_hash"].tolist() == second["content_hash"].tolist()
    assert first["clause_key"].tolist() == second["clause_key"].tolist()


def test_content_hash_whitespace_and_reextract_stable() -> None:
    """Cosmetic whitespace variation must NOT flip the content hash — otherwise
    re-extraction would produce false 'amended' signals for identical law."""
    a = "(1) Ranibizumab veya aflibersept etkin maddeli ilaçlar."
    b = "(1)  Ranibizumab veya aflibersept  etkin maddeli ilaçlar.\n"
    assert content_hash(a) == content_hash(b)


def _latest_sut_docx():
    """Return the newest consolidated SUT docx, or None when absent."""
    from scripts.sut._common import find_latest_consolidated_sut_docx

    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    return find_latest_consolidated_sut_docx(root / "raw data")


def test_double_extract_clause_keys_byte_identical(tmp_path) -> None:
    """Re-extracting the SAME docx twice yields byte-identical clause_keys.

    This is the Phase 6 're-extract stability' guarantee. Skipped when no
    consolidated SUT docx is available (e.g. a slim CI checkout).
    """
    docx = _latest_sut_docx()
    if docx is None:
        pytest.skip("no consolidated SUT docx under raw data/")

    from scripts.sut.prose.extractor import write_sut_clauses_parquet

    first = tmp_path / "first.parquet"
    second = tmp_path / "second.parquet"
    frame_a = write_sut_clauses_parquet(docx, first)
    frame_b = write_sut_clauses_parquet(docx, second)

    assert len(frame_a) == len(frame_b)
    assert frame_a["clause_key"].tolist() == frame_b["clause_key"].tolist()
    assert frame_a["content_hash"].tolist() == frame_b["content_hash"].tolist()
