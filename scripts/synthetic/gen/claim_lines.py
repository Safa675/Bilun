"""Per-claim line builders and ClaimEpisodeContext."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ProcedureClaimLine

from catalog import _drug_unit_price, _money
from gen.drug_fields import _empty_drug_indication_fields
from gen.materials_flags import _default_prose_material_flags, _default_specialty_prose_flags, _sample_prose_material_flags
from gen.reconcile import _reconcile_ek2c1_procedure_lines

# Paired-organ imaging/surgery prefixes that require sag_sol (laterality).
# Mirrors laterality_validation.py prefixes — codes matching these need a
# "1" (sol/left) or "2" (sağ/right) side designation.
_PAIRED_ORGAN_PREFIXES: tuple[str, ...] = (
    "80101", "80102", "80103", "80104", "80105", "80106", "80119", "80120", "80121",  # MR
    "80319", "80320", "80321",  # CT
    "516",  # cataract / eye surgery
)


def _maybe_sag_sol(procedure_code: str) -> str:
    """Emit sag_sol ('1'=left, '2'=right) for paired-organ codes.

    ~70% get a valid side, ~30% left empty (violation candidate for the
    laterality detectors). Non-paired codes always return ''.
    """
    code = str(procedure_code or "").strip()
    if not any(code.startswith(p) for p in _PAIRED_ORGAN_PREFIXES):
        return ""
    return random.choice(["1", "2"]) if random.random() < 0.7 else ""

@dataclass
class ClaimEpisodeContext:
    pid: str
    eid: str
    visit_type: str
    claim_id: str
    start_date: str
    scenario_tag: str

    facility_tier: str
    is_university: bool
    provider: str
    admission: str | None
    discharge: str | None
    claim_end: str

    package_candidate: bool
    package_code_for_claim: str | None

    all_codes: list[str]
    template: dict[str, Any]

    ek2g_no_surcharge: set[str]
    ek2c1_copay_rates: dict[str, float]
    ek3_all: list[tuple[str, pd.DataFrame]]
    active_drugs: pd.DataFrame

    rng: np.random.Generator

    procedure_rows: list[dict] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    drug_claims: list[dict] = field(default_factory=list)
    expected: list[dict] = field(default_factory=list)
    lab_billing_budget: dict = field(default_factory=dict)

    proc_specs: list[dict] = field(default_factory=list)
    servis_adi: str = "genel"

    from src.bilun.domain.claims.models import ProcedureClaimLine
def _procedure_row_as_claim_line(row: dict) -> ProcedureClaimLine:
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=str(row["islem_satiri_id"]),
        claim_id=str(row["fatura_id"]),
        patient_id=str(row["hasta_id"]),
        episode_id=str(row["basvuru_id"]),
        procedure_date=date.fromisoformat(str(row["islem_tarihi"])[:10]),
        procedure_code=str(row["islem_kodu"]),
        procedure_name=str(row.get("islem_adi") or ""),
        procedure_category=str(row.get("islem_kategorisi") or "islem"),
        quantity=int(row.get("adet") or 1),
        unit_price_try=Decimal(str(row.get("birim_fiyat_try") or 0)),
        billed_amount_try=Decimal(str(row.get("fatura_tutari_try") or 0)),
        expected_payable_try=Decimal(str(row.get("beklenen_odenebilir_tutar_try") or 0)),
        is_package_included=bool(row.get("pakete_dahil_mi")),
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _apply_session_point_billed_factors(
    rows: list[dict],
    *,
    locked_procedure_codes: set[str] | None = None,
) -> tuple[float, float]:
    """Scale secondary same-day billed lines per SUT §2.2.2; returns billed/payable deltas."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
    from src.bilun.domain.prose_rules.session_pricing import compute_session_point_factors
    from src.bilun.domain.prose_rules.session_specialty import detect_cross_specialty_session

    locked = {
        normalize_procedure_code(code)
        for code in (locked_procedure_codes or set())
    }

    old_billed = sum(float(row.get("fatura_tutari_try") or 0) for row in rows)
    old_payable = sum(float(row.get("beklenen_odenebilir_tutar_try") or 0) for row in rows)

    billable = [
        row
        for row in rows
        if not row.get("pakete_dahil_mi")
        and float(row.get("fatura_tutari_try") or 0) > 0
        and normalize_procedure_code(str(row.get("islem_kodu") or "")) not in locked
    ]
    if len(billable) < 2:
        return 0.0, 0.0

    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in billable:
        by_date[str(row.get("islem_tarihi") or "")].append(row)

    for session_rows in by_date.values():
        if len(session_rows) < 2:
            continue

        codes = [str(row["islem_kodu"]) for row in session_rows]
        stub_lines = [_procedure_row_as_claim_line(row) for row in session_rows]
        cross_specialty = detect_cross_specialty_session(stub_lines, None)
        session = compute_session_point_factors(
            codes,
            same_incision=True,
            cross_specialty=cross_specialty,
        )
        if session.rule_id == "single_procedure":
            continue

        factors = {
            normalize_procedure_code(factor.procedure_code): factor
            for factor in session.factors
        }
        primary_factor = 1.0
        for row in session_rows:
            factor = factors.get(normalize_procedure_code(str(row["islem_kodu"])))
            if factor is not None and factor.is_primary:
                primary_factor = factor.point_factor
                break

        for row in session_rows:
            factor = factors.get(normalize_procedure_code(str(row["islem_kodu"])))
            if (
                factor is None
                or factor.is_primary
                or factor.point_factor >= primary_factor
            ):
                continue

            billed = float(row["fatura_tutari_try"])
            payable = float(row["beklenen_odenebilir_tutar_try"])
            adjusted_billed = _money(billed * factor.point_factor)
            ratio = adjusted_billed / billed if billed > 0 else 1.0
            row["fatura_tutari_try"] = adjusted_billed
            row["beklenen_odenebilir_tutar_try"] = _money(payable * ratio)

    new_billed = sum(float(row.get("fatura_tutari_try") or 0) for row in rows)
    new_payable = sum(float(row.get("beklenen_odenebilir_tutar_try") or 0) for row in rows)
    return _money(new_billed - old_billed), _money(new_payable - old_payable)


# ── Per-claim line builders ──────────────────────────────────────────
def _append_procedure_lines_for_claim(
    ctx: ClaimEpisodeContext,
) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0
    row_start = len(ctx.procedure_rows)

    for line_idx, ps in enumerate(ctx.proc_specs, start=1):
        is_package_proc = (ps["category"] == "paket")
        qty = int(ps.get("quantity_override", 1))
        unit_price = ps["price"]
        billed_override = "billed_override" in ps
        billed = _money(ps["billed_override"]) if billed_override else _money(unit_price * qty)

        included_in_package = ps.get("included_in_package", False)

        if included_in_package:
            sgk_base = 0.0
        elif is_package_proc:
            sgk_base = billed
        else:
            sgk_base = billed

        surcharge_applicable = (
            not ps.get("disable_surcharge")
            and ps["code"] not in ctx.ek2g_no_surcharge
        )
        if included_in_package:
            surcharge_applicable = False
        surcharge_rate = None
        if surcharge_applicable and not is_package_proc:
            if ctx.is_university:
                surcharge_rate = round(ctx.rng.uniform(0.90, 1.00), 2) if ctx.rng.random() < 0.8 else None
            else:
                surcharge_rate = round(float(ctx.rng.choice([0.20, 0.30, 0.50, 0.75, 1.00])), 2)

        from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

        norm_code = normalize_procedure_code(ps["code"])
        copay_applicable = norm_code in ctx.ek2c1_copay_rates
        copay_rate = ctx.ek2c1_copay_rates.get(norm_code) if copay_applicable else None
        if (
            not copay_applicable
            and ctx.visit_type in ("poliklinik", "gunubirlik")
            and not is_package_proc
        ):
            copay_applicable = True
            copay_rate = float(ctx.rng.choice([0.20, 0.40, 0.50]))
        if included_in_package:
            copay_applicable = False
            copay_rate = None

        if "payable_override" in ps:
            # Keep explicit demo overrides deterministic and mark rates unavailable.
            copay_applicable = False
            copay_rate = None
            surcharge_rate = None

        if billed_override:
            denominator = 1.0 + float(surcharge_rate or 0.0)
            sgk_base = _money(billed / denominator) if denominator > 0 else billed

        expected_payable = sgk_base
        patient_copay = 0.0
        if copay_rate and copay_applicable:
            expected_payable = _money(sgk_base * (1 - copay_rate))
            patient_copay = _money(sgk_base * copay_rate)
        surcharge_amount = (
            _money(sgk_base * float(surcharge_rate))
            if surcharge_applicable and surcharge_rate
            else 0.0
        )
        if not included_in_package and not billed_override:
            billed = _money(expected_payable + patient_copay + surcharge_amount)
        if expected_payable > billed:
            expected_payable = billed
        if "payable_override" in ps:
            expected_payable = _money(ps["payable_override"])

        denial_reason = ""
        if included_in_package:
            denial_reason = "Paket ici islem ayrica odenmez"

        line_id = f"ISL-{ctx.claim_id}-{line_idx:03d}"
        ctx.procedure_rows.append({
            "islem_satiri_id": line_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "islem_tarihi": ctx.start_date,
            "islem_kodu": ps["code"],
            "islem_adi": ps["name"],
            "islem_kategorisi": ps["category"],
            "adet": qty,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": billed,
            "beklenen_odenebilir_tutar_try": expected_payable,
            "pakete_dahil_mi": included_in_package,
            "paket_kodu": (
                ps.get("candidate_package_code") or ctx.package_code_for_claim
            )
            if (included_in_package or is_package_proc or ps.get("candidate_package_code"))
            else None,
            "ilave_ucret_uygulanabilir_mi": surcharge_applicable,
            "ilave_ucret_orani": surcharge_rate,
            "katilim_payi_orani_uygulanabilir_mi": copay_applicable,
            "katilim_payi_orani": copay_rate,
            "beklenen_red_nedeni": denial_reason,
            "beklenen_kural_izi": f"EK-2B:{ps['code']}" if not is_package_proc else f"EK-2C:{ps['code']}",
            "sag_sol": _maybe_sag_sol(ps["code"]),
            "procedure_specialty_code": ctx.servis_adi,
        })

        if ps["category"] == "laboratuvar":
            ctx.lab_billing_budget[(ctx.eid, ps["code"])] = {
                "islem_satiri_id": line_id,
                "kalan_adet": qty,
                "test_adi": ps["name"],
            }

        if included_in_package:
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{line_id}",
                "senaryo_etiketi": ctx.scenario_tag,
                "hasta_id": ctx.pid,
                "fatura_id": ctx.claim_id,
                "satir_id": line_id,
                "satir_tipi": "islem",
                "kural_ailesi": "drg_paket_ayristirma",
                "beklenen_durum": "pakete_dahil_red",
                "beklenen_odenebilir_tutar_try": expected_payable,
                "beklenen_tasarruf_try": _money(billed - expected_payable),
                "beklenen_red_nedeni": "Paket ici islem ayrica odenmez",
                "beklenen_kural_izi": f"EK-2B:{ps['code']}",
                "test_notu": "Satir duzeyi sentetik beklenen cikti",
            })

        total_billed += billed
        total_payable += expected_payable

    claim_rows = ctx.procedure_rows[row_start:]
    locked_codes = {
        str(ps["code"]) for ps in ctx.proc_specs if "billed_override" in ps
    }
    delta_billed, delta_payable = _apply_session_point_billed_factors(
        claim_rows,
        locked_procedure_codes=locked_codes,
    )
    _reconcile_ek2c1_procedure_lines(claim_rows, ctx.ek2c1_copay_rates)
    total_billed = _money(total_billed + delta_billed)
    total_payable = _money(total_payable + delta_payable)

    return total_billed, total_payable


def _append_material_prose_demo_line(
    ctx: ClaimEpisodeContext,
    spec: dict[str, Any],
) -> tuple[float, float]:
    """Inject a single pinned material line for Sprint 2 prose/KDV demos."""
    proc_line_id = f"ISL-{ctx.claim_id}-001"
    if ctx.procedure_rows:
        for row in ctx.procedure_rows:
            if row.get("fatura_id") == ctx.claim_id:
                proc_line_id = str(row.get("islem_satiri_id") or proc_line_id)
                break

    mat_billed = _money(float(spec.get("unit_price") or 0))
    m_line_id = f"MLZ-{ctx.claim_id}-DEMO-001"
    prose_flags = _default_prose_material_flags()
    prose_flags.update(spec.get("prose_flags") or {})
    specialty_flags = _default_specialty_prose_flags()
    specialty_flags.update(spec.get("specialty_flags") or {})

    ctx.materials.append({
        "malzeme_satiri_id": m_line_id,
        "fatura_id": ctx.claim_id,
        "islem_satiri_id": proc_line_id,
        "hasta_id": ctx.pid,
        "malzeme_tarihi": ctx.start_date,
        "malzeme_kodu": str(spec.get("material_code") or ""),
        "malzeme_adi": str(spec.get("material_name") or ""),
        "malzeme_tipi": str(spec.get("material_type") or "genel"),
        "uzmanlik_kategorisi": str(spec.get("specialty_category") or "genel"),
        "adet": 1,
        "birim_fiyat_try": mat_billed,
        "fatura_tutari_try": mat_billed,
        "beklenen_odenebilir_tutar_try": mat_billed,
        "pakete_dahil_mi": False,
        "on_onay_gerekli_mi": False,
        "beklenen_red_nedeni": "",
        "beklenen_kural_izi": f"MAT-PROSE-DEMO:{spec.get('material_code', '')}",
        **prose_flags,
        **specialty_flags,
    })
    return mat_billed, mat_billed


def _append_material_lines_for_claim(ctx: ClaimEpisodeContext) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0

    material_catalogs = ctx.template.get("material_catalogs", [])
    if not material_catalogs or ctx.visit_type not in ("yatis", "gunubirlik") or not ctx.ek3_all:
        return total_billed, total_payable

    n_materials = ctx.rng.integers(1, 5)
    for mat_idx in range(n_materials):
        cat_name = ctx.rng.choice(material_catalogs)
        cat_df = next((df for name, df in ctx.ek3_all if cat_name in name), None)
        if cat_df is None or cat_df.empty:
            continue
        valid = cat_df[
            cat_df["price_try"].notna() &
            (cat_df["price_try"] > 0) &
            cat_df["sut_code"].notna()
        ]
        if valid.empty:
            continue
        row = valid.sample(1, random_state=ctx.rng.bit_generator).iloc[0]

        bundled = ctx.package_code_for_claim is not None and ctx.rng.random() < 0.55
        mat_billed = _money(float(row.get("price_try", 0) or 0))
        mat_payable = 0.0 if bundled else mat_billed
        pre_auth = ctx.rng.random() < 0.5

        m_line_id = f"MLZ-{ctx.claim_id}-{(mat_idx + 1):03d}"
        prose_flags = _sample_prose_material_flags(bundled=bundled)
        ctx.materials.append({
            "malzeme_satiri_id": m_line_id,
            "fatura_id": ctx.claim_id,
            "islem_satiri_id": f"ISL-{ctx.claim_id}-{(mat_idx % max(1, len(ctx.proc_specs))) + 1:03d}",
            "hasta_id": ctx.pid,
            "malzeme_tarihi": ctx.start_date,
            "malzeme_kodu": str(row.get("sut_code", "")),
            "malzeme_adi": str(row.get("material_name", "")),
            "malzeme_tipi": str(row.get("category", "genel")),
            "uzmanlik_kategorisi": str(row.get("category", "genel")),
            "adet": 1,
            "birim_fiyat_try": mat_billed,
            "fatura_tutari_try": mat_billed,
            "beklenen_odenebilir_tutar_try": mat_payable,
            "pakete_dahil_mi": bundled,
            "on_onay_gerekli_mi": pre_auth,
            "beklenen_red_nedeni": "Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
            "beklenen_kural_izi": f"EK-3:{row.get('sut_code', '')}",
            **prose_flags,
        })
        if bundled or pre_auth:
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{m_line_id}",
                "senaryo_etiketi": ctx.scenario_tag,
                "hasta_id": ctx.pid,
                "fatura_id": ctx.claim_id,
                "satir_id": m_line_id,
                "satir_tipi": "malzeme",
                "kural_ailesi": "faturalama_stratejisi",
                "beklenen_durum": "pakete_dahil_red" if bundled else "on_onay_gerekli_odenebilir",
                "beklenen_odenebilir_tutar_try": mat_payable,
                "beklenen_tasarruf_try": _money(mat_billed - mat_payable),
                "beklenen_red_nedeni": "Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
                "beklenen_kural_izi": f"EK-3:{row.get('sut_code', '')}",
                "test_notu": "Satir duzeyi sentetik beklenen cikti",
            })
        total_billed += mat_billed
        total_payable += mat_payable

    return total_billed, total_payable


def _append_drug_lines_for_claim(ctx: ClaimEpisodeContext) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0

    n_drugs = ctx.rng.integers(1, 5)
    if n_drugs <= 0 or ctx.active_drugs.empty:
        return total_billed, total_payable

    drug_sample = ctx.active_drugs.sample(n_drugs, random_state=ctx.rng.bit_generator)
    for drug_idx, (_, drug_row) in enumerate(drug_sample.iterrows(), start=1):
        unit_price = _drug_unit_price(drug_row, ctx.rng)
        qty = int(ctx.rng.integers(1, 4))
        billed = _money(unit_price * qty)
        tier_raw = drug_row.get("discount_tier_1")
        try:
            discount_tier = float(tier_raw) if tier_raw is not None else 0.28
        except (ValueError, TypeError):
            discount_tier = 0.28
        payable = _money(billed * (1 - discount_tier))
        copay_rate = discount_tier if discount_tier > 0 else None

        d_line_id = f"ILC-{ctx.claim_id}-{drug_idx:03d}"
        prescription_id = f"REC-{ctx.claim_id}-{drug_idx:03d}"
        ctx.drug_claims.append({
            "ilac_satiri_id": d_line_id,
            "recete_id": prescription_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "ilac_fatura_tarihi": ctx.start_date,
            "ilac_adi": str(drug_row.get("drug_name", "")),
            "ilac_kodu": str(drug_row.get("kamu_no", "")),
            "barkod": str(drug_row.get("barcode", "")),
            "esdeger_grup": str(drug_row.get("equivalence_group", "")),
            "adet": qty,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": billed,
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_indirim_kademesi": discount_tier,
            "katilim_payi_orani": copay_rate,
            "ilave_ucret_orani": None,
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"EK-4A:{drug_row.get('kamu_no', '')}",
            **_empty_drug_indication_fields(),
        })
        ctx.expected.append({
            "beklenen_cikti_id": f"BEK-{d_line_id}",
            "senaryo_etiketi": ctx.scenario_tag,
            "hasta_id": ctx.pid,
            "fatura_id": ctx.claim_id,
            "satir_id": d_line_id,
            "satir_tipi": "ilac",
            "kural_ailesi": "ilac_indirimi",
            "beklenen_durum": "ilac_indirimi_uygulandi",
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_tasarruf_try": _money(billed - payable),
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"EK-4A:{drug_row.get('kamu_no', '')}",
            "test_notu": "Satir duzeyi sentetik beklenen cikti",
        })
        total_billed += billed
        total_payable += payable

    return total_billed, total_payable
