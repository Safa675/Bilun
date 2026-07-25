"""Build SUT prose → domain coverage matrix."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from .classify import classify_clauses
from .clause_identity import (
    AmbiguousClauseCiteError,
    UnknownClauseCiteError,
    encoded_clause_ids_from_rules,
    resolve_gate_b_ref_to_clause_ids,
)
from .manifest_index import encoded_like_clause_ids, load_drug_bucket_clause_ids
from .rule_registry import RULE_BY_ID, RULE_REGISTRY, CoverageStatus

_IN_FORCE_ONLY = True
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUT_CLAUSES_PARQUET = _REPO_ROOT / "data/gazette/sut_clauses.parquet"
# Module-level cache: unset sentinel vs None (missing file) vs DataFrame.
_SUT_CLAUSES_FRAME_UNSET: object = object()
_sut_clauses_frame_cache: pl.DataFrame | None | object = _SUT_CLAUSES_FRAME_UNSET

_DRUG_INDICATION_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
)
_ANTI_VEGF_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.33_anti_vegf_4.2.33_manifest.json"
)
_DRUG_4213_4216_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4213_4216_manifest.json"
)
_DRUG_4217_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4217_manifest.json"
)
_DRUG_4219_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "data/gazette/prose_manifests/L4.2_drug_indication_4219_manifest.json"
)
_MANIFEST_DIR = Path(__file__).resolve().parents[3] / "data/gazette/prose_manifests"
_DRUG_INDICATION_RULES_JSON = (
    Path(__file__).resolve().parents[3] / "data/gazette/prose_rules/drug_indication_prose.json"
)
_PAYMENT_METHOD_22_MANIFEST = "L2.2_payment_method_encoded_manifest.json"
_SESSION_PRICING_22_MANIFEST = "L2.2_session_pricing_2_2_2_B_encoded_manifest.json"
_DEFINITIONS_2_6_MANIFEST = "L2.6_definitions_manifest.json"
_TREATMENT_PRICING_2_4_MANIFEST = "L2.4_treatment_pricing_wave2_manifest.json"
_WAVE2_MANIFESTS: dict[str, str] = {
    # §2.6 definitions/scope clauses encode runtime-billing gates.
    "definitions": _DEFINITIONS_2_6_MANIFEST,
    # §2.4 treatment-package pricing (incl. §2.4.4) wave encodes.
    "pricing_ek2b": _TREATMENT_PRICING_2_4_MANIFEST,
    "gazette_repricing": "L2.2_gazette_repricing_encoded_manifest.json",
    "procedure_pairing": "L2.2_procedure_pairing_encoded_manifest.json",
    "material_pairing": "L3.1_material_pairing_encoded_manifest.json",
    "payment_method_package": _PAYMENT_METHOD_22_MANIFEST,
    "payment_method_itemized": _PAYMENT_METHOD_22_MANIFEST,
    "payment_method_tier_override": _PAYMENT_METHOD_22_MANIFEST,
    "drg_unbundling": _SESSION_PRICING_22_MANIFEST,
    "copay_rate_general": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_ek1a": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_visit_type": "L1.8_copay_exemption_encoded_manifest.json",
    "copay_exemption_ek4d": "L1.8_copay_exemption_encoded_manifest.json",
}
_PROSE_MANIFESTS: dict[str, str] = {
    "material_bundling_prose": "L1.4_material_bundling_encoded_manifest.json",
    "specialty_materials_prose": "L4.4_specialty_prose_encoded_manifest.json",
    "dental_2_4_1": "dental_2_4_1_manifest.json",
    "gap_closing_misc": "gap_closing_misc_manifest.json",
    "fatura_inceleme_prose": "fatura_inceleme_prose_manifest.json",
}

def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def _has_actionable_signal(row: pd.Series) -> bool:
    """True when the clause plausibly needs a billing rule mapping (not pure reference)."""
    deontic_modality = _optional_str(row.get("deontic_modality"))
    annex_refs = _json_list(str(row.get("annex_refs", "[]")))
    clause_type = str(row.get("clause_type") or "")
    has_normative_or_annex = bool(deontic_modality or annex_refs)
    # Structural / navigational rows (chapter titles, section headings, RG lines,
    # short prose labels like "Genel Hükümler") are reference unless they carry
    # deontic or annex signals — fixes C000002 false missing/gap.
    if clause_type in {"chapter", "section_heading", "amendment", "prose"}:
        return has_normative_or_annex
    # numbered_item falls through here (not in either set). Its result is
    # `has_normative_or_annex` — identical to the prose branch above — so the
    # reclassification from prose is behavior-preserving for coverage gating.
    return bool(has_normative_or_annex or clause_type in {"fikra", "bent"})


def _load_encoded_clause_ids(manifest_name: str) -> frozenset[str]:
    path = _MANIFEST_DIR / manifest_name
    if not path.is_file():
        return frozenset()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _manifest_clause_ids_from_payload(payload)


def _manifest_clause_ids_from_payload(payload: dict[str, Any]) -> frozenset[str]:
    return encoded_like_clause_ids(payload)


def _load_drug_indication_emr_blocked_clause_ids() -> frozenset[str]:
    """Clause IDs genuinely EMR-blocked across all §4.2 drug manifests."""
    return load_drug_bucket_clause_ids(status="emr_blocked", manifest_dir=_MANIFEST_DIR)


def _load_drug_indication_tier_c_deferred_clause_ids() -> frozenset[str]:
    """Tier-C deferred clause IDs — honest deferral removes algorithmic gap."""
    return load_drug_bucket_clause_ids(status="tier_c_deferred", manifest_dir=_MANIFEST_DIR)


def _is_structural_gap_excluded(row: pd.Series) -> bool:
    """Structural/nav rows without normative signal are not encode debt."""
    clause_type = str(row.get("clause_type") or "")
    deontic_modality = _optional_str(row.get("deontic_modality"))
    if clause_type in {"chapter", "section_heading", "amendment"} and not deontic_modality:
        return True
    is_heading = row.get("is_heading")
    if is_heading is True and not deontic_modality:
        return True
    return False


# Canonical actionable statuses: a clause whose motor is implemented/partial
# but which has no JSON rule encoding it. ``has_algorithmic_gap`` (computed in
# ``_enrich_with_coverage``) is the runtime projection of this predicate plus
# the structural/EMR/Tier-C exclusions. Consumer sites that re-derive the raw
# "unencoded in an actionable motor" mask should mirror these status values:
#   - scripts/sut/build_sut_coverage.py:75  (gap AND unencoded, drug-motor subset)
#   - scripts/sut/close_algorithmic_gaps.py:100  (drug motor, gap, unencoded)
#   - scripts/sut/extract_tier_c_drug_rules.py:123  (drug motor, unencoded only)
#   - src/bilun/domain/prose_rules/drug_indication.py:346  (gap AND unencoded)
# Keep this set in sync with the ``has_algorithmic_gap`` definition at line ~381.
_ACTIONABLE_COVERAGE_STATUSES: frozenset[str] = frozenset({"implemented", "partial"})


# Phase 4.2/4.3 — explicit, auditable, reversible reclassification set.
# Clauses here are body text (bent/fikra/prose) that was auto-classified to a
# billing motor via section-prefix fallback but is NOT a billing decision:
# either reference/definitional text (visit-fee tables, section enumeration)
# or supporting text (indication lists, report-content specs) whose decisional
# parent is already encoded. Each clause_id was individually audited against
# its text_tr + the motor's declared scope; reclassifying hides nothing — the
# decisional rules for these sections are already in the prose JSONs. See
# plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 4.2/4.3.
#
# §1.8.1 visit-fee table (12) + §1.8 enumeration (6) — reference/definitional,
# no deontic, no annex; routed to copay_rate_general by the ("1.8", ...) prefix
# fallback at classify.py:150 but contain no rate/fee logic.
_RECLASSIFY_AS_NON_ALGORITHMIC: frozenset[str] = frozenset({
    # §1.8.1 visit-fee table — fixed TL amounts by facility tier (reference data,
    # not a billing rule; the amounts live in EK-2/C-1, not in copay_general).
    "C000258", "C000288", "C000289", "C000290", "C000291", "C000292",
    "C000293", "C000296", "C000297", "C000298", "C000305", "C000307",
    # §1.8 top-level enumeration — "ayakta tedavide ilaçlar", "vücut dışı protez",
    # "yardımcı üreme", collection-channel prose, income-threshold fikra.
    "C000228", "C000229", "C000230", "C000231", "C000232", "C000236",
    # §3.3 specialty_materials supporting text (Phase 4.3) — 261 clauses that
    # are the indication-list / report-content-spec / MIAT-renewal text
    # SURROUNDING the already-encoded 202 specialty_materials_prose decision
    # rules. All carry deontic_modality=None, annex_refs=[]; zero contain
    # negative-coverage language ("karşılanmaz") or EK-3 references. The
    # decisional parents (e.g. "bedelleri Kurumca karşılanır") ARE encoded;
    # these are the bullet-list indications + report fields those decisions
    # reference. Reclassifying closes the gap honestly without duplicating the
    # decisional rules. See plans/refactor/rule-encoding-gap-closure-roadmap.md
    # Phase 4.3.
    "C002840", "C002841", "C002842", "C002843", "C002844", "C002845",
    "C002846", "C002847", "C002848", "C002849", "C002851", "C002852",
    "C002854", "C002859", "C002876", "C002877", "C002878", "C002879",
    "C002880", "C002885", "C002896", "C002903", "C002906", "C002909",
    "C002910", "C002911", "C002912", "C002914", "C002916", "C002922",
    "C002923", "C002925", "C002929", "C002935", "C002940", "C002941",
    "C002942", "C002943", "C002944", "C002945", "C002949", "C002955",
    "C002959", "C002974", "C002975", "C002977", "C002978", "C002979",
    "C002980", "C002981", "C002982", "C002983", "C002984", "C002991",
    "C002992", "C002993", "C002994", "C002995", "C002996", "C003002",
    "C003003", "C003004", "C003005", "C003006", "C003007", "C003013",
    "C003014", "C003015", "C003016", "C003017", "C003018", "C003019",
    "C003021", "C003024", "C003029", "C003033", "C003034", "C003038",
    "C003039", "C003042", "C003043", "C003047", "C003048", "C003049",
    "C003050", "C003052", "C003053", "C003054", "C003055", "C003062",
    "C003063", "C003064", "C003067", "C003068", "C003069", "C003070",
    "C003076", "C003077", "C003078", "C003079", "C003080", "C003081",
    "C003082", "C003083", "C003084", "C003085", "C003086", "C003087",
    "C003088", "C003089", "C003090", "C003091", "C003092", "C003094",
    "C003095", "C003096", "C003097", "C003100", "C003102", "C003104",
    "C003105", "C003106", "C003107", "C003108", "C003109", "C003110",
    "C003112", "C003116", "C003117", "C003118", "C003119", "C003120",
    "C003121", "C003122", "C003126", "C003128", "C003129", "C003130",
    "C003131", "C003132", "C003133", "C003134", "C003135", "C003136",
    "C003137", "C003138", "C003139", "C003153", "C003155", "C003156",
    "C003157", "C003164", "C003165", "C003166", "C003167", "C003172",
    "C003173", "C003174", "C003175", "C003176", "C003177", "C003178",
    "C003179", "C003182", "C003183", "C003184", "C003203", "C003204",
    "C003205", "C003206", "C003208", "C003209", "C003210", "C003211",
    "C003212", "C003213", "C003214", "C003215", "C003217", "C003218",
    "C003219", "C003221", "C003222", "C003223", "C003224", "C003225",
    "C003226", "C003228", "C003229", "C003230", "C003232", "C003233",
    "C003235", "C003236", "C003237", "C003238", "C003239", "C003241",
    "C003242", "C003244", "C003246", "C003247", "C003249", "C003250",
    "C003252", "C003253", "C003257", "C003258", "C003259", "C003262",
    "C003263", "C003264", "C003265", "C003266", "C003284", "C003285",
    "C003286", "C003287", "C003288", "C003290", "C003291", "C003292",
    "C003293", "C003294", "C003295", "C003297", "C003333", "C003335",
    "C003336", "C003337", "C003338", "C003341", "C003342", "C003343",
    "C003351", "C003352", "C003353", "C003356", "C003357", "C003358",
    "C003359", "C003360", "C003361", "C003367", "C003368", "C003370",
    "C003371", "C003372", "C003373", "C003374", "C003375", "C003376",
    "C003380", "C003381", "C003382", "C003387", "C003388", "C003389",
    "C003390", "C003392", "C003395",
    # Phase 7 — residual gap resolution (283 clauses). 3 buckets:
    # (a) payment_method 203: §2.4 clinical content (cardiac risk, IVF, dialysis,
    #   physio, palliative) + §2.2 reference tables (DRG duration, package enum)
    #   mis-routed via classify.py:159 fallback; §2.2 code motor (42 rules) complete.
    # (b) bundling 28: EK-3 annex-list citations (C002767-C002788) + C002815/C008293.
    # (c) smaller motors 52: drg_coding 16 (§2.2.1.B service-category lists) +
    #   drug 17 (price lines + Mülga + cross-ref) + surcharge/copay/drg_unbundling/preauth.
    "C000226", "C000343", "C000377", "C000390", "C000428", "C000429",
    "C000430", "C000431", "C000432", "C000434", "C000449", "C000453",
    "C000520", "C000528", "C000529", "C000534", "C000541", "C000570",
    "C000587", "C000588", "C000589", "C000591", "C000593", "C000595",
    "C000596", "C000597", "C000598", "C000599", "C000600", "C000601",
    "C000602", "C000605", "C000625", "C000656", "C000667", "C000673",
    "C000674", "C000675", "C000676", "C000682", "C000683", "C000684",
    "C000685", "C000688", "C000689", "C000690", "C000691", "C000692",
    "C000693", "C000743", "C000798", "C000806", "C000817", "C000820",
    "C000831", "C000836", "C000837", "C000844", "C000845", "C000846",
    "C000848", "C000862", "C000863", "C000871", "C000872", "C000873",
    "C000879", "C000885", "C000886", "C000887", "C000888", "C000889",
    "C000890", "C000891", "C000892", "C000893", "C000894", "C000895",
    "C000898", "C000918", "C000919", "C000920", "C000921", "C000922",
    "C000923", "C000932", "C000933", "C000935", "C000936", "C000937",
    "C000948", "C000949", "C000951", "C000952", "C000960", "C000961",
    "C000965", "C000967", "C000969", "C000981", "C000985", "C000989",
    "C000990", "C000992", "C001008", "C001021", "C001024", "C001057",
    "C001062", "C001069", "C001103", "C001111", "C001121", "C001133",
    "C001134", "C001137", "C001138", "C001139", "C001140", "C001141",
    "C001142", "C001143", "C001144", "C001145", "C001146", "C001147",
    "C001148", "C001149", "C001150", "C001151", "C001152", "C001153",
    "C001154", "C001155", "C001156", "C001157", "C001158", "C001159",
    "C001160", "C001161", "C001162", "C001163", "C001164", "C001165",
    "C001166", "C001167", "C001168", "C001169", "C001170", "C001171",
    "C001172", "C001173", "C001174", "C001175", "C001176", "C001177",
    "C001178", "C001179", "C001180", "C001181", "C001182", "C001183",
    "C001184", "C001185", "C001186", "C001187", "C001188", "C001189",
    "C001190", "C001191", "C001192", "C001193", "C001194", "C001195",
    "C001196", "C001197", "C001198", "C001199", "C001200", "C001201",
    "C001202", "C001209", "C001214", "C001220", "C001240", "C001245",
    "C001256", "C001257", "C001258", "C001259", "C001263", "C001265",
    "C001267", "C001268", "C001269", "C001270", "C001271", "C001272",
    "C001273", "C001277", "C001278", "C001279", "C001280", "C001281",
    "C001282", "C001283", "C001292", "C001303", "C001311", "C001312",
    "C001314", "C001318", "C001319", "C001321", "C001323", "C001324",
    "C001325", "C001339", "C001341", "C001342", "C001343", "C001344",
    "C001354", "C001355", "C001356", "C001357", "C001358", "C001359",
    "C001363", "C001369", "C001373", "C001374", "C001388", "C001391",
    "C002701", "C002702", "C002703", "C002704", "C002705", "C002713",
    "C002767", "C002768", "C002769", "C002770", "C002771", "C002772",
    "C002773", "C002774", "C002775", "C002776", "C002777", "C002778",
    "C002779", "C002780", "C002781", "C002782", "C002783", "C002784",
    "C002785", "C002786", "C002787", "C002788", "C002798", "C002815",
    "C004623", "C005026", "C005232", "C005313", "C005467", "C005633",
    "C005994", "C005995", "C005996", "C005997", "C006008", "C006009",
    "C006010", "C006014", "C006087", "C006106", "C006122", "C007824",
    "C008293",
})


def _load_sut_clauses_frame() -> pl.DataFrame | None:
    """Load ``sut_clauses.parquet`` once (Polars). None if missing / unreadable."""
    global _sut_clauses_frame_cache
    if _sut_clauses_frame_cache is not _SUT_CLAUSES_FRAME_UNSET:
        return _sut_clauses_frame_cache  # type: ignore[return-value]
    if not _SUT_CLAUSES_PARQUET.is_file():
        _sut_clauses_frame_cache = None
        return None
    try:
        _sut_clauses_frame_cache = pl.read_parquet(_SUT_CLAUSES_PARQUET)
    except Exception:  # pragma: no cover - defensive I/O
        _sut_clauses_frame_cache = None
    return _sut_clauses_frame_cache  # type: ignore[return-value]


def _reset_sut_clauses_frame_cache() -> None:
    """Test helper — clear the module-level parquet cache."""
    global _sut_clauses_frame_cache
    _sut_clauses_frame_cache = _SUT_CLAUSES_FRAME_UNSET


def _resolve_rule_json_gate_b_sources(
    payload: dict[str, Any],
    clauses_frame: pl.DataFrame | None,
) -> set[str]:
    """Collect clause_ids from rules' ``gate_b_sources`` (dual-read).

    When ``clauses_frame`` is None, keep opaque strings (legacy C*-only path).
    When provided, resolve coordinate cites via ``clause_identity``. On
    ``AmbiguousClauseCiteError`` or ``UnknownClauseCiteError`` for a cite,
    skip that ref (do not insert the coordinate string). ``C*`` / ``F*`` ids
    always pass through.
    """
    rules = list(payload.get("rules") or [])
    if clauses_frame is None:
        return encoded_clause_ids_from_rules(rules, None)

    out: set[str] = set()
    for rule in rules:
        for raw in rule.get("gate_b_sources") or []:
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            try:
                out.update(resolve_gate_b_ref_to_clause_ids(text, clauses_frame))
            except AmbiguousClauseCiteError:
                # Mixed/legacy data: ambiguous coordinate would not match
                # clause_id column — skip rather than crash coverage build.
                continue
            except UnknownClauseCiteError:
                # Unknown / invalid coordinate cites — skip. C* never raises.
                continue
    return out


def _load_gate_b_sources_from_rules_json(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    return frozenset(_resolve_rule_json_gate_b_sources(payload, _load_sut_clauses_frame()))


def _load_drug_indication_encoded_clause_ids() -> frozenset[str]:
    """Encoded clause IDs for the merged drug_indication corpus.

    Phase 6 simplification: derive the encoded set directly from rule JSON
    gate_b_sources (the single source of truth), supplemented by manifests
    for sections whose rules haven't been fully encoded yet.
    """
    # Primary: derive from rules JSON gate_b_sources (canonical source of truth)
    encoded: frozenset[str] = _load_gate_b_sources_from_rules_json(_DRUG_INDICATION_RULES_JSON)

    # Supplement: anti-VEGF corpus (separate JSON)
    anti_vegf_rules = _DRUG_INDICATION_RULES_JSON.parent / "anti_vegf_prose.json"
    encoded |= _load_gate_b_sources_from_rules_json(anti_vegf_rules)

    # Supplement: R6 deontic-wave manifests (sections whose rules aren't in the
    # main JSON yet — these are still manifest-tracked only)
    for name in (
        "L4.2_drug_indication_4_2_14_wave2_manifest.json",
        "L4.2_drug_indication_rheum_biologics_manifest.json",
        "L4.2_drug_indication_small_mid_manifest.json",
        "L4.2_drug_indication_metabolic_mid_manifest.json",
        "L4_drug_ek4a_r6_manifest.json",
        "L4.2_drug_indication_eye_mid_b_r6_manifest.json",
        "L4.2_drug_indication_eye_mid_a_r6_manifest.json",
        "L4.2_drug_indication_tail_a_r6_manifest.json",
        "L4.2_drug_indication_tail_b_r6_manifest.json",
    ):
        path = _MANIFEST_DIR / name
        if path.is_file():
            encoded |= _manifest_clause_ids_from_payload(
                json.loads(path.read_text(encoding="utf-8"))
            )
    return encoded


def _load_wave2_encoded_clause_ids(rule_id: str) -> frozenset[str]:
    manifest_name = _WAVE2_MANIFESTS.get(rule_id)
    if not manifest_name:
        return frozenset()
    return _load_encoded_clause_ids(manifest_name)


# --- Section-scoped encode overrides ---------------------------------------
# These clauses are encoded in dedicated manifests, but the classifier
# sometimes routes them to a different primary motor than the one the manifest
# is keyed to. The overrides ensure has_rule_encoding reflects the encode
# regardless of the classification motor.

# Single-manifest-per-section overrides, table-driven. §2.2 also hits the
# r6_misc override below; §4.2/§4.1/§4.3-4.7 and the r6 wave keep bespoke logic.
_SECTION_MANIFEST_OVERRIDES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("2.2", (_PAYMENT_METHOD_22_MANIFEST, _SESSION_PRICING_22_MANIFEST)),
    ("2.4", (_TREATMENT_PRICING_2_4_MANIFEST, "L2.4_treatment_pricing_r6_rest_manifest.json")),
    ("2.6", (_DEFINITIONS_2_6_MANIFEST,)),
    ("3.3", ("L4.4_specialty_prose_encoded_manifest.json",)),
)


def _section_manifest_encode_override(clause_id: str, section_id: str) -> bool:
    """Clause is encoded if it's in any manifest listed for its section prefix."""
    for prefix, manifests in _SECTION_MANIFEST_OVERRIDES:
        if section_id.startswith(prefix):
            for manifest_name in manifests:
                if clause_id in _load_encoded_clause_ids(manifest_name):
                    return True
    return False


def _section_drug_indication_wave_encoding(clause_id: str, section_id: str) -> bool:
    """§4.2 drug-indication wave encodes (oncology/rheum/small-mid/metabolic).

    Catches clauses the classifier routes to exclusion_ek3b2/material_exclusion
    instead of drug_indication_prose. Also covers §4.1/4.3-4.7 drug provisions
    (drug_ek4a motor) encoded in the r6 wave.
    """
    if section_id.startswith("4.2"):
        return clause_id in _load_drug_indication_encoded_clause_ids()
    if section_id.startswith(("4.1", "4.3", "4.4", "4.5", "4.6", "4.7")):
        return clause_id in _load_encoded_clause_ids("L4_drug_ek4a_r6_manifest.json")
    return False


def _section_r6_misc_encoding(clause_id: str, section_id: str) -> bool:
    """R6 wave encodes across §1.5-1.10 (referral/surcharge), §2.2/2.3/2.5
    (payment/pricing), §5.x/§6.x (billing docs / misc), §3.x leftover materials.

    These clauses classify under non-algorithmic or fallback motors, so the
    dedicated r6 manifests must be checked via section-scoped overrides.
    """
    if section_id.startswith(("1.5", "1.6", "1.7", "1.9", "1.10")):
        return clause_id in _load_encoded_clause_ids("L_r6_referral_encoded_manifest.json")
    if section_id.startswith(("5.", "6.", "1.8", "1.1", "1.11")):
        return clause_id in _load_encoded_clause_ids("L_r6_billing_def_encoded_manifest.json")
    if section_id.startswith(("2.2", "2.3", "2.5")):
        return clause_id in _load_encoded_clause_ids("L2_payment_pricing_r6_manifest.json")
    if section_id.startswith(("3.1", "3.2")):
        return clause_id in _load_encoded_clause_ids("L_r6_specialty_leftover_manifest.json")
    return False

_STATUS_RANK: dict[str, int] = {
    "implemented": 0,
    "partial": 1,
    "needs_claim_lines": 2,
    "missing": 3,
    "non_algorithmic": 4,
}


def _json_list(raw: str) -> list[str]:
    if not raw or raw == "[]":
        return []
    return json.loads(raw)


def _enrich_with_coverage(classified: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    encoded_clause_ids = _load_drug_indication_encoded_clause_ids()
    emr_blocked_ids = _load_drug_indication_emr_blocked_clause_ids()
    tier_c_deferred_ids = _load_drug_indication_tier_c_deferred_clause_ids()

    for _, row in classified.iterrows():
        primary_rule_id = row.get("primary_rule_id")
        matched_rule_ids = _json_list(str(row.get("matched_rule_ids", "[]")))

        if primary_rule_id and primary_rule_id in RULE_BY_ID:
            primary = RULE_BY_ID[primary_rule_id]
            primary_status: CoverageStatus = primary.coverage_status
            primary_category = primary.rule_category
            primary_modules = list(primary.domain_modules)
            coverage_notes = primary.description
        elif matched_rule_ids:
            primary_status = "missing"
            primary_category = "unmapped"
            primary_modules = []
            coverage_notes = "Matched registry entry not found"
        else:
            primary_status = "missing"
            primary_category = "unclassified"
            primary_modules = []
            coverage_notes = "No rule category matched"

        all_statuses: list[str] = []
        all_modules: set[str] = set()
        all_categories: set[str] = set()

        for rule_id in matched_rule_ids:
            entry = RULE_BY_ID.get(rule_id)
            if not entry:
                continue
            all_statuses.append(entry.coverage_status)
            all_categories.add(entry.rule_category)
            all_modules.update(entry.domain_modules)

        if all_statuses:
            worst_status = max(all_statuses, key=lambda s: _STATUS_RANK.get(s, 99))
        else:
            worst_status = primary_status

        has_actionable_signal = _has_actionable_signal(row)

        if primary_category == "unclassified" and not has_actionable_signal:
            primary_status = "non_algorithmic"
            worst_status = "non_algorithmic"
            coverage_notes = "Administrative or definitional text without billing rule signals"
        elif primary_category == "unclassified" and has_actionable_signal:
            primary_status = "missing"
            worst_status = "missing"
            coverage_notes = "Actionable SUT rule text with no mapped domain implementation"

        # Phase 1.1 — honest reclassification of structural clauses.
        # A clause auto-classified to an implemented/partial motor via section
        # prefix but with NO normative content (chapter/section_heading/
        # amendment without deontic_modality, or is_heading=True without
        # deontic_modality) is administrative text, not encode debt. Without
        # this, 821 structural clauses (468 amendment markers like
        # "(Değişik: RG-...)" + 353 section headings) masquerade as gaps in
        # the dashboard because their motor is partial/implemented but they
        # have no JSON rule encoding them — which is correct, because there is
        # nothing to encode. Reclassify them out of the actionable population
        # so the gap count reflects real encode debt. See
        # plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 1.1.
        if (
            primary_status in {"implemented", "partial", "missing", "needs_claim_lines"}
            and _is_structural_gap_excluded(row)
        ):
            primary_status = "non_algorithmic"
            worst_status = "non_algorithmic"
            coverage_notes = (
                "Structural/navigational clause (heading/amendment marker) "
                "without normative content — not encode debt"
            )

        clause_id = str(row.get("clause_id") or "")

        # Phase 4.2/4.3 — explicit reclassification of audited non-decisional
        # body text (visit-fee tables, section enumeration, supporting-text
        # indication lists). See _RECLASSIFY_AS_NON_ALGORITHMIC above.
        if (
            primary_status in {"implemented", "partial", "missing", "needs_claim_lines"}
            and clause_id in _RECLASSIFY_AS_NON_ALGORITHMIC
        ):
            primary_status = "non_algorithmic"
            worst_status = "non_algorithmic"
            coverage_notes = (
                "Reference/definitional or supporting text — not a billing "
                "decision (audited per Phase 4.2/4.3)"
            )

        # Compute has_rule_encoding FIRST — has_algorithmic_gap depends on it.
        if primary_rule_id == "drug_indication_prose":
            has_rule_encoding = clause_id in encoded_clause_ids
        elif primary_rule_id in _WAVE2_MANIFESTS:
            has_rule_encoding = clause_id in _load_wave2_encoded_clause_ids(primary_rule_id)
        elif primary_rule_id in _PROSE_MANIFESTS:
            manifest_name = _PROSE_MANIFESTS[primary_rule_id]
            has_rule_encoding = clause_id in _load_encoded_clause_ids(manifest_name)
        else:
            has_rule_encoding = False

        section_id = str(row.get("section_id") or "")
        if not has_rule_encoding:
            # Section-specific overrides: reflect encodes whose manifest motor
            # differs from the classifier's primary_rule_id.
            for _override in (
                _section_manifest_encode_override,
                _section_drug_indication_wave_encoding,
                _section_r6_misc_encoding,
            ):
                if _override(clause_id, section_id):
                    has_rule_encoding = True
                    break

        # A clause has an algorithmic gap when its motor is not fully
        # implemented/encoded — either the motor itself is partial/missing,
        # OR the motor is "implemented" but this specific clause has no JSON
        # rule encoding it (has_rule_encoding=False). The latter catches the
        # 2.100+ clauses auto-classified to an "implemented" motor via section
        # prefix but never individually encoded in any rule JSON.
        has_algorithmic_gap = (
            primary_status in {"partial", "missing", "needs_claim_lines"}
            or (primary_status == "implemented" and not has_rule_encoding)
        ) and primary_status != "non_algorithmic"
        if _is_structural_gap_excluded(row):
            has_algorithmic_gap = False
        elif clause_id in emr_blocked_ids or clause_id in tier_c_deferred_ids:
            has_algorithmic_gap = False

        rows.append(
            {
                **row.to_dict(),
                "primary_rule_category": primary_category,
                "coverage_status": primary_status,
                "worst_coverage_status": worst_status,
                "domain_modules": json.dumps(sorted(all_modules or primary_modules), ensure_ascii=False),
                "matched_rule_categories": json.dumps(sorted(all_categories), ensure_ascii=False),
                "coverage_notes": coverage_notes,
                "has_algorithmic_gap": has_algorithmic_gap,
                "has_rule_encoding": has_rule_encoding,
                "emr_blocked": clause_id in emr_blocked_ids,
            }
        )

    return pd.DataFrame(rows)


def build_coverage_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()

    agg_spec: dict[str, Any] = {
        "clause_count": ("clause_id", "count"),
        "sections": ("section_id", lambda s: sorted({x for x in s.dropna().unique()})),
        "sample_text": ("in_force_text", "first")
        if "in_force_text" in coverage.columns
        else ("text_tr", "first"),
        "gap_clause_count": ("has_algorithmic_gap", "sum"),
    }
    if "has_rule_encoding" in coverage.columns:
        agg_spec["encoded_clause_count"] = ("has_rule_encoding", "sum")

    grouped = (
        coverage.groupby(["primary_rule_id", "primary_rule_category", "coverage_status"], dropna=False)
        .agg(**agg_spec)
        .reset_index()
    )

    if "encoded_clause_count" in grouped.columns:
        grouped["encoded_clause_count"] = grouped["encoded_clause_count"].astype(int)
        grouped["unencoded_gap_clause_count"] = (
            grouped["gap_clause_count"] - grouped["encoded_clause_count"]
        ).clip(lower=0).astype(int)
    grouped["gap_clause_count"] = grouped["gap_clause_count"].astype(int)

    grouped["sample_sections"] = grouped["sections"].apply(lambda xs: json.dumps(xs[:8], ensure_ascii=False))
    grouped["domain_modules"] = grouped["primary_rule_id"].apply(
        lambda rule_id: json.dumps(
            list(RULE_BY_ID[rule_id].domain_modules) if rule_id in RULE_BY_ID else [],
            ensure_ascii=False,
        )
    )
    grouped["description"] = grouped["primary_rule_id"].apply(
        lambda rule_id: RULE_BY_ID[rule_id].description if rule_id in RULE_BY_ID else ""
    )
    grouped = grouped.drop(columns=["sections"])
    grouped = grouped.sort_values(["coverage_status", "clause_count"], ascending=[True, False])
    return grouped


def build_section_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    if coverage.empty:
        return pd.DataFrame()

    def _worst_status(statuses: pd.Series) -> str:
        values = [s for s in statuses.dropna().unique()]
        if not values:
            return "missing"
        return max(values, key=lambda s: _STATUS_RANK.get(str(s), 99))

    grouped = (
        coverage[coverage["section_id"].notna()]
        .groupby(["section_id", "section_title"], dropna=False)
        .agg(
            clause_count=("clause_id", "count"),
            worst_coverage_status=("worst_coverage_status", _worst_status),
            gap_clause_count=("has_algorithmic_gap", "sum"),
            primary_categories=("primary_rule_category", lambda s: sorted(set(s.dropna()))),
        )
        .reset_index()
    )
    grouped["primary_categories"] = grouped["primary_categories"].apply(
        lambda xs: json.dumps(xs, ensure_ascii=False)
    )
    grouped = grouped.sort_values(["worst_coverage_status", "gap_clause_count"], ascending=[True, False])
    return grouped


def build_registry_coverage_summary(coverage: pd.DataFrame) -> pd.DataFrame:
    """One row per registry rule showing whether any clause mapped to it."""
    classified_ids = set()
    for raw in coverage.get("matched_rule_ids", pd.Series(dtype=str)):
        classified_ids.update(_json_list(str(raw)))

    rows: list[dict[str, Any]] = []
    for entry in RULE_REGISTRY:
        matched = coverage["matched_rule_ids"].str.contains(entry.rule_id, regex=False, na=False)
        rows.append(
            {
                "rule_id": entry.rule_id,
                "rule_category": entry.rule_category,
                "registry_coverage_status": entry.coverage_status,
                "domain_modules": json.dumps(list(entry.domain_modules), ensure_ascii=False),
                "description": entry.description,
                "matched_clause_count": int(matched.sum()),
                "has_clause_mapping": entry.rule_id in classified_ids,
            }
        )

    frame = pd.DataFrame(rows)
    return frame.sort_values(["registry_coverage_status", "matched_clause_count"], ascending=[True, False])


def build_sut_coverage(clauses: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if _IN_FORCE_ONLY and "is_in_force" in clauses.columns:
        clauses = clauses[clauses["is_in_force"]].copy()
    classified = classify_clauses(clauses)
    coverage = _enrich_with_coverage(classified)
    rule_summary = build_coverage_summary(coverage)
    section_summary = build_section_summary(coverage)
    registry_summary = build_registry_coverage_summary(coverage)
    return coverage, rule_summary, section_summary, registry_summary


def write_sut_coverage(
    clauses_path: Path,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clauses = pd.read_parquet(clauses_path)
    coverage, rule_summary, section_summary, registry_summary = build_sut_coverage(clauses)

    output_dir.mkdir(parents=True, exist_ok=True)
    coverage.to_parquet(output_dir / "sut_clause_coverage.parquet", index=False)
    rule_summary.to_parquet(output_dir / "sut_coverage_by_rule.parquet", index=False)
    section_summary.to_parquet(output_dir / "sut_coverage_by_section.parquet", index=False)
    registry_summary.to_parquet(output_dir / "sut_registry_coverage.parquet", index=False)

    return coverage, rule_summary, section_summary, registry_summary
