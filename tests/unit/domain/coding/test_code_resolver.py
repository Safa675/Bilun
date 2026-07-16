"""Tests for the hospital-code → SUT code resolver (Phase 2 coder).

Two test groups:
  1. Golden-set — 20 hand-verified finans→EK-2B mappings. Any resolver or
     frozen-table change must keep these green. These are the regression net.
  2. Mechanics — normalizer, candidate generator, frozen-table precedence,
     the ``reviewed=FALSE`` guard (unreviewed mappings never feed a motor).

The golden codes were verified against the live EK-2B parquet during the
2026-07-16 probe and LLM pass. If EK-2B is regenerated with different codes,
update these constants deliberately — do not relax them silently.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[4]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.bilun.domain.coding import (  # noqa: E402
    CategoryHint,
    ResolutionMethod,
    build_candidates,
    resolve_code,
)
from src.bilun.domain.coding.code_resolver import (  # noqa: E402
    clear_resolver_cache,
    normalize_name,
)


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """Each test starts with fresh caches so frozen-table changes are seen."""
    clear_resolver_cache()
    yield
    clear_resolver_cache()


# ═══════════════════════════════════════════════════════════════════════════
# Golden-set: hand-verified finans hospital code → expected SUT EK-2B code.
# Sourced from the 2026-07-16 probe + LLM pass, each verified in EK-2B.
# ═══════════════════════════════════════════════════════════════════════════

GOLDEN = [
    # (hospital_code, description, category, expected_sut_code)
    # Codes verified against EK-2B during the 2026-07-16 probe + LLM pass.
    # NOTE: 3 codes were corrected after ground-truth verification — see
    # plans/data/2026-07-16-finans-cleanup-and-coder-plan.md Review §6:
    #   ESR            L101110 → L106650 (L101110 is Arilsülfataz A, wrong)
    #   Rektosigmoidoskopi 701550 → 701400 (701550 is upper-GI, wrong)
    #   HbA1c          L102820 (correct, promoted after conf review)
    # Labs — common analytes
    ("C8446001", "Alanine Aminotransferase (ALT)", "LAB", "L100300"),
    ("C8256501", "Kreatinin", "LAB", "L104780"),
    ("C8413201", "Potasyum", "LAB", "L106150"),
    ("C8447801", "Trigliserid", "LAB", "L107250"),
    ("C8614001", "C reaktif protein (CRP)", "LAB", "L101850"),
    ("C8452001", "Üre Azotu (BUN)", "LAB", "L107420"),
    ("C8303601", "Hemoglobin A1c (HbA1c)", "LAB", "L102820"),
    ("C8565101", "Eritrosit Sedimentasyon Hızı (ESR)", "LAB", "L106650"),
    # Labs — microbiology
    ("C8704501", "Gaita Kültürü", "LAB", "905672"),
    ("C8708601", "İdrar Kültürü", "LAB", "905671"),
    ("C8706001", "Boğaz Kültürü", "LAB", "905670"),
    ("C8788001", "Streptococcus (grup A) Antijeni, Hızlı Test", "LAB", "905980"),
    # Labs — virology
    ("C8780219", "SARS-CoV-2 Antijen Testi (Hızlı Test)", "LAB", "907221"),
    ("C8740001", "Influenza Antijeni (A ve B)", "LAB", "907660"),
    # Procedures — consultations & exams
    ("07010001", "Poliklinik Muayene", "PROCEDURE", "520020"),
    ("07010012", "Konsültasyon (ASG DOKTORLARI)", "PROCEDURE", "520010"),
    ("01010093", "Acil Serviste Muayene", "PROCEDURE", "520020"),
    # Procedures — oncology
    ("70023926", "Otomatik/Robotik İnfüzyon Kemoterapisi (SGK)", "PROCEDURE", "704693"),
    # Procedures — endoscopy (rectum/lower GI, NOT upper-GI 701550)
    ("C4533001", "Rektosigmoidoskopi (sol kolonoskopi)", "PROCEDURE", "701400"),
    # Drugs — brand→EK-4A (Phase 3). Verified against ek4a_drugs.parquet.
    ("61490711", "Paracerol 10 mg/ml IV İnfüzyon İçin Çözelti İçeren 100 ml 12 Flak", "DRUG", "A14359"),
    ("61530388", "Zygosis 40 mg IV Enj. Çöz. Hazırlamak için Liyofilize Toz 1 Flako", "DRUG", "A17226"),
    ("61518547", "Osetron 8 mg/4 ml IM/IV Enjeksiyonluk Çözelti İçeren 1 Ampul", "DRUG", "A15230"),
    ("61469411", "Parol 10 mg/ml IV 100 ml İnf.İçin Çöz.İçeren 12 Flakon", "DRUG", "A12100"),
    # Materials — SKU→EK-3 category (Phase 3). SKU detail correctly discarded.
    # Foley urinary catheter → Sonda Foley family (OR1160), not angiography.
    ("61538266", "Üriner Kateter, Su Soketli, Hidrofilik, 14Fr, 40cm, Hi-Slip", "MATERIAL", "OR1160"),
    # Radiology — imaging → EK-2B (Phase 4). R-prefixed for CT/MR, numeric for X-ray.
    # Verified during Phase 4 LLM pass.
    ("C7125004", "BT, Toraks (düşük doz) (Kontrastsız)", "RADIOLOGY", "R100450"),
    ("C7101001", "Akciğer Grafisi (Arka Ön)", "RADIOLOGY", "801720"),
]


@pytest.mark.parametrize("hospital_code,description,category,expected", GOLDEN)
def test_golden_set_resolves_to_expected_sut_code(
    hospital_code: str, description: str, category: str, expected: str
) -> None:
    """Every golden finans code must resolve to its hand-verified SUT code."""
    res = resolve_code(hospital_code, description, CategoryHint(kind=category))
    assert res.sut_code == expected, (
        f"{hospital_code} ({description!r}) resolved to {res.sut_code} "
        f"via {res.method} (conf {res.confidence}), expected {expected}"
    )
    assert res.reviewed is True, f"{hospital_code} not marked reviewed (reviewed={res.reviewed})"


def test_golden_set_count() -> None:
    """Guard: the golden set must have exactly 20 cases — if someone adds or
    removes one, this test forces a deliberate acknowledgement."""
    assert len(GOLDEN) == 26


# ═══════════════════════════════════════════════════════════════════════════
# Normalizer
# ═══════════════════════════════════════════════════════════════════════════


def test_normalize_folds_turkish_chars() -> None:
    assert normalize_name("İŞĞÜÖÇ") == "isguoc"
    assert normalize_name("Muayenesi") == "muayenesi"


def test_normalize_strips_punctuation() -> None:
    assert normalize_name("Alanine Aminotransferase (ALT)") == "alanine aminotransferase alt"
    assert normalize_name("C reaktif protein (CRP)") == "c reaktif protein crp"


def test_normalize_handles_none_and_empty() -> None:
    assert normalize_name(None) == ""
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


# ═══════════════════════════════════════════════════════════════════════════
# Candidate generator
# ═══════════════════════════════════════════════════════════════════════════


def test_build_candidates_returns_list() -> None:
    cands = build_candidates("Kreatinin", CategoryHint(kind="LAB"))
    assert isinstance(cands, list)
    assert len(cands) >= 1
    assert all("code" in c and "confidence" in c for c in cands)


def test_build_candidates_lab_hint_filters_to_l_prefix() -> None:
    """A LAB hint must restrict candidates to L-prefixed SUT codes."""
    cands = build_candidates("Kreatinin", CategoryHint(kind="LAB"))
    assert all(c["code"].startswith("L") for c in cands), (
        f"LAB hint returned non-L codes: {[c['code'] for c in cands]}"
    )


def test_build_candidates_single_word_does_not_match_compound() -> None:
    """Regression: 'Kreatinin' must NOT match 'Albümin/Kreatinin' (compound,
    different test). Single-word queries require the entry name to start with
    the token."""
    cands = build_candidates("Kreatinin", CategoryHint(kind="LAB"))
    codes = [c["code"] for c in cands]
    assert "L100330" not in codes, (
        "Kreatinin falsely matched Albümin/Kreatinin — single-word guard failed"
    )


def test_build_candidates_empty_description() -> None:
    assert build_candidates("", CategoryHint(kind="LAB")) == []
    assert build_candidates(None) == []


# ═══════════════════════════════════════════════════════════════════════════
# Drug candidate generator (Phase 3.1)
# ═══════════════════════════════════════════════════════════════════════════


def test_build_drug_candidates_returns_full_identity() -> None:
    """Drug candidates must carry kamu_no + barcode + equivalence_group — the
    drug_indication motor needs all three, not just one code."""
    from src.bilun.domain.coding import build_drug_candidates

    cands = build_drug_candidates("Paracerol 10 mg/ml IV İnfüzyon")
    assert len(cands) >= 1
    di = cands[0]["drug_identity"]
    assert di["kamu_no"] == "A14359"
    assert di["barcode"]  # non-empty
    assert di["equivalence_group"]  # non-empty


def test_build_drug_candidates_single_entry_brand_match() -> None:
    """A brand with exactly one EK-4A entry must match at high confidence even
    with zero formulation overlap (EK-4A uses heavy abbreviations)."""
    from src.bilun.domain.coding import build_drug_candidates

    cands = build_drug_candidates("Paracerol 10 mg/ml IV")
    assert cands and cands[0]["code"] == "A14359"
    assert cands[0]["confidence"] >= 0.8


def test_drug_resolution_populates_drug_identity() -> None:
    """resolve_code with a DRUG hint must populate Resolution.drug_identity."""
    res = resolve_code(
        "61490711", "Paracerol 10 mg/ml IV İnfüzyon", CategoryHint(kind="DRUG")
    )
    assert res.drug_identity is not None
    assert res.drug_identity["kamu_no"] == "A14359"


# ═══════════════════════════════════════════════════════════════════════════
# Material candidate generator (Phase 3.2)
# ═══════════════════════════════════════════════════════════════════════════


def test_build_material_candidates_maps_to_category_not_sku() -> None:
    """Material matching discards SKU detail (brand, Ref, exact size) — only
    the material *type* matters. Foley catheter → Sonda Foley category."""
    from src.bilun.domain.coding import build_material_candidates

    cands = build_material_candidates(
        "Üriner Kateter, Su Soketli, Hidrofilik, 14Fr, 40cm, Foley"
    )
    assert len(cands) >= 1
    # Foley must map to the Sonda Foley family (OR1160-OR1270), not an
    # incidental "kateter" match like sialography.
    assert cands[0]["code"].startswith("OR11") or cands[0]["code"].startswith("OR12"), (
        f"Foley mapped to wrong category: {cands[0]['code']} '{cands[0]['name'][:40]}'"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Category classifier (Phase 3.0)
# ═══════════════════════════════════════════════════════════════════════════


def test_classify_category_iv_fluids_are_drugs() -> None:
    """Tightened DRUG regex must catch IV fluids that Phase 2 missed."""
    from src.bilun.domain.coding import classify_category

    assert classify_category("Pol. Polgyl %0,5 IV Perfüzyon 100 ml") == "DRUG"
    assert classify_category("İzotonik NaCl PP 50 ml (Osel)") == "DRUG"


def test_classify_category_consumables_are_materials() -> None:
    """Tightened MATERIAL regex must catch consumable devices."""
    from src.bilun.domain.coding import classify_category

    assert classify_category("Serum Seti, Broche") == "MATERIAL"
    assert classify_category("Üç Yollu Musluk, 72 PSI") == "MATERIAL"
    assert classify_category("Ven Valfi, Q-Style, BD") == "MATERIAL"


def test_classify_category_hotel_services_are_hotel() -> None:
    """Hotel/hospital services (bed fees, companion meals) are NOT SUT clinical
    items — v5 classifies them as HOTEL (explicitly excluded, not UNCLEAR)."""
    from src.bilun.domain.coding import classify_category

    assert classify_category("Normal Yatak Ücreti (MASLAK)") == "HOTEL"
    assert classify_category("Refakatci (Öğlen Yemeği)") == "HOTEL"


def test_classify_category_radiology() -> None:
    """v5 RADIOLOGY regex must catch imaging + nuclear med + physiotherapy."""
    from src.bilun.domain.coding import classify_category

    assert classify_category("Akciğer Grafisi (Arka Ön)") == "RADIOLOGY"
    assert classify_category("BT, Toraks (düşük doz) (Kontrastsız)") == "RADIOLOGY"
    assert classify_category("Ekokardiyografi (Doppler+Renkli+M+B Mode)") == "RADIOLOGY"


def test_classify_category_recovered_labs_and_sutures() -> None:
    """v5 broadened LAB (Folik Asit, Beta-hCG, Kan Gazı) and MATERIAL (sutures)."""
    from src.bilun.domain.coding import classify_category

    assert classify_category("Folik Asit") == "LAB"
    assert classify_category("Beta-hCG (İnsan Koryonik Gonadotropin)") == "LAB"
    assert classify_category("Kan Gazları, Arteriyel (Günlük)") == "LAB"
    assert classify_category("4/0 Vicryl, 17mm, Ethicon, W9106") == "MATERIAL"
    assert classify_category("3/0 Pegelak, 25mm, Doğsan, L4250") == "MATERIAL"


def test_option_b_drug_resolves_to_equivalence_group() -> None:
    """Option B: formerly-ambiguous IV-fluid drugs resolve at confidence 0.7 via
    the frozen table (option_b_eqgroup source). They carry a drug_identity with
    an equivalence_group — the exact SKU is uncertain but the group is right."""
    res = resolve_code(
        "61462182", "İzotonik NaCl PP 50 ml (Osel)", CategoryHint(kind="DRUG")
    )
    assert res.reviewed is True
    assert res.drug_identity is not None
    # The equivalence group must be populated (E219x = isotonic NaCl family).
    assert res.drug_identity["equivalence_group"].startswith("E219"), (
        f"Expected E219x equivalence group, got {res.drug_identity['equivalence_group']}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Resolver precedence + guards
# ═══════════════════════════════════════════════════════════════════════════


def test_frozen_table_takes_precedence_over_generator() -> None:
    """A code in the frozen table must resolve via FROZEN, not re-run the
    generator. This is the O(1) steady-state path."""
    res = resolve_code("C8446001", "Alanine Aminotransferase (ALT)", CategoryHint(kind="LAB"))
    assert res.method == ResolutionMethod.FROZEN
    assert res.sut_code == "L100300"
    assert res.confidence == 1.0


def test_unknown_code_falls_back_to_generator() -> None:
    """A code NOT in the frozen table falls through to the candidate generator."""
    res = resolve_code("FAKE99999", "Kreatinin", CategoryHint(kind="LAB"))
    assert res.method != ResolutionMethod.FROZEN
    # The generator should still find Kreatinin from the description.
    assert res.sut_code == "L104780"


def test_resolved_code_is_reviewed_only_when_frozen() -> None:
    """reviewed=True only for frozen-table hits. Generator/LLM matches are
    reviewed=False until promoted — the guard against unreviewed mappings
    feeding a motor."""
    frozen_res = resolve_code("C8446001", "x", CategoryHint(kind="LAB"))
    assert frozen_res.reviewed is True

    gen_res = resolve_code("FAKE99999", "Kreatinin", CategoryHint(kind="LAB"))
    assert gen_res.reviewed is False


def test_resolve_codes_bulk_preserves_order() -> None:
    """Bulk resolver must return one Resolution per input row, in order."""
    rows = [
        {"hospital_code": "C8256501", "description": "Kreatinin", "category": "LAB"},
        {"hospital_code": "FAKE1", "description": "Potasyum", "category": "LAB"},
    ]
    results = [r for r in [  # resolve_codes_bulk
        __import__(
            "src.bilun.domain.coding.code_resolver",
            fromlist=["resolve_codes_bulk"],
        ).resolve_codes_bulk(rows)
    ] for _ in [0]][0]
    assert len(results) == 2
    assert results[0].hospital_code == "C8256501"
    assert results[1].hospital_code == "FAKE1"
