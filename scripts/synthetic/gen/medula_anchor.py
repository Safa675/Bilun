"""MEDULA rejection anchor line injection."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd

from catalog import _money
from gen.claim_lines import ClaimEpisodeContext
from gen.drug_fields import _empty_drug_indication_fields
from gen.materials_flags import _default_prose_material_flags, _default_specialty_prose_flags
from gen.procedures import _lookup_ek2b_price

def _inject_medula_anchor_line(
    ctx: ClaimEpisodeContext,
    anchor: dict[str, Any],
    ek2b_procs: dict[str, pd.DataFrame],
) -> dict[str, str]:
    """Inject the offending line(s) for a MEDULA rejection demo and return the
    rejection-row pointer fields.

    Returns a dict with keys: ``related_line_type``, ``related_line_id``,
    ``ilgili_islem_kodu`` (procedure code, when the anchor is a procedure),
    ``ilgili_islem_satiri_id`` (procedure line id, when the anchor is a
    procedure), ``anchor_billed``, ``anchor_payable`` (the offending line's
    contribution to fold into the claim totals). For material/drug anchors the
    legacy procedure-code fields are left blank and the new discriminator fields
    carry the real line id. The offending line is appended ON TOP of the claim's
    realistic base bill.
    """
    anchor_type = str(anchor.get("type") or "claim")
    result: dict[str, str] = {
        "related_line_type": "",
        "related_line_id": "",
        "ilgili_islem_kodu": "",
        "ilgili_islem_satiri_id": "",
        "anchor_billed": "0.0",
        "anchor_payable": "0.0",
    }

    if anchor_type == "claim":
        result["related_line_type"] = "claim"
        return result

    if anchor_type in ("procedure", "procedure_duplicate"):
        code = str(anchor["code"])
        name, price = _lookup_ek2b_price(code, ek2b_procs)
        category = str(anchor.get("category") or "islem")
        qty = 1
        billed = _money(price * qty)
        # Two copies for the duplicate scenario; one otherwise.
        copies = 2 if anchor_type == "procedure_duplicate" else 1
        last_line_id = ""
        for copy_idx in range(1, copies + 1):
            # New procedure line id, continuing the existing numbering for the claim.
            existing = [r for r in ctx.procedure_rows if r.get("fatura_id") == ctx.claim_id]
            line_idx = len(existing) + 1
            line_id = f"ISL-{ctx.claim_id}-{line_idx:03d}"
            date_offset = int(anchor.get("date_offset_days") or 0)
            proc_date = ctx.start_date
            if date_offset:
                proc_date = (
                    dt.date.fromisoformat(ctx.start_date) + dt.timedelta(days=date_offset)
                ).isoformat()
            ctx.procedure_rows.append({
                "islem_satiri_id": line_id,
                "fatura_id": ctx.claim_id,
                "hasta_id": ctx.pid,
                "basvuru_id": ctx.eid,
                "islem_tarihi": proc_date,
                "islem_kodu": code,
                "islem_adi": name,
                "islem_kategorisi": category,
                "adet": qty,
                "birim_fiyat_try": price,
                "fatura_tutari_try": billed,
                "beklenen_odenebilir_tutar_try": billed,
                "pakete_dahil_mi": False,
                "paket_kodu": None,
                "ilave_ucret_uygulanabilir_mi": False,
                "ilave_ucret_orani": None,
                "katilim_payi_orani_uygulanabilir_mi": False,
                "katilim_payi_orani": None,
                "beklenen_red_nedeni": "",
                "beklenen_kural_izi": f"EK-2B:{code}",
            })
            last_line_id = line_id
        # Point at the (second/duplicate) procedure line.
        result["related_line_type"] = "procedure"
        result["related_line_id"] = last_line_id
        result["ilgili_islem_kodu"] = code
        result["ilgili_islem_satiri_id"] = last_line_id
        result["anchor_billed"] = str(_money(billed * copies))
        result["anchor_payable"] = str(_money(billed * copies))
        return result

    if anchor_type == "procedure_bundled":
        # A procedure that is bundled into a package but was billed separately
        # (the offending line). No standalone package header is emitted: adding
        # one would turn the claim into a packaged bill and conflict with the
        # DRG-mandatory side-procedure check. The component carries the package
        # code reference, which is what the rejection concerns.
        package_code = str(anchor["package_code"])
        component_code = str(anchor["component_code"])
        comp_name, comp_price = _lookup_ek2b_price(component_code, ek2b_procs)
        existing = [r for r in ctx.procedure_rows if r.get("fatura_id") == ctx.claim_id]
        comp_idx = len(existing) + 1
        comp_line_id = f"ISL-{ctx.claim_id}-{comp_idx:03d}"
        # Bundled component billed separately (the offending line).
        ctx.procedure_rows.append({
            "islem_satiri_id": comp_line_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "islem_tarihi": ctx.start_date,
            "islem_kodu": component_code,
            "islem_adi": comp_name,
            "islem_kategorisi": "islem",
            "adet": 1,
            "birim_fiyat_try": comp_price,
            "fatura_tutari_try": comp_price,
            "beklenen_odenebilir_tutar_try": 0.0,
            "pakete_dahil_mi": True,
            "paket_kodu": package_code,
            "ilave_ucret_uygulanabilir_mi": False,
            "ilave_ucret_orani": None,
            "katilim_payi_orani_uygulanabilir_mi": False,
            "katilim_payi_orani": None,
            "beklenen_red_nedeni": "Paket ici islem ayrica odenmez",
            "beklenen_kural_izi": f"EK-2B:{component_code}",
        })
        # Bundled procedures carry a line-level expected output (mirrors
        # _append_procedure_lines_for_claim's pakete_dahil_red branch).
        ctx.expected.append({
            "beklenen_cikti_id": f"BEK-{comp_line_id}",
            "senaryo_etiketi": ctx.scenario_tag,
            "hasta_id": ctx.pid,
            "fatura_id": ctx.claim_id,
            "satir_id": comp_line_id,
            "satir_tipi": "islem",
            "kural_ailesi": "drg_paket_ayristirma",
            "beklenen_durum": "pakete_dahil_red",
            "beklenen_odenebilir_tutar_try": 0.0,
            "beklenen_tasarruf_try": _money(comp_price),
            "beklenen_red_nedeni": "Paket ici islem ayrica odenmez",
            "beklenen_kural_izi": f"EK-2B:{component_code}",
            "test_notu": "MEDULA anchor: bundled procedure separately billed",
        })
        result["related_line_type"] = "procedure"
        result["related_line_id"] = comp_line_id
        result["ilgili_islem_kodu"] = component_code
        result["ilgili_islem_satiri_id"] = comp_line_id
        result["anchor_billed"] = str(_money(comp_price))
        result["anchor_payable"] = "0.0"
        return result

    if anchor_type == "material":
        # A real material whose ÜTS barcode registration is missing.
        proc_line_id = ""
        for row in ctx.procedure_rows:
            if row.get("fatura_id") == ctx.claim_id:
                proc_line_id = str(row.get("islem_satiri_id") or "")
                break
        unit_price = _money(float(anchor.get("unit_price") or 0))
        existing_mats = [r for r in ctx.materials if r.get("fatura_id") == ctx.claim_id]
        m_line_id = f"MLZ-{ctx.claim_id}-{len(existing_mats) + 1:03d}"
        prose_flags = _default_prose_material_flags()
        prose_flags.update(anchor.get("prose_flags") or {})
        # Specialty (L4.4) prose flags must be present with explicit False
        # values; omitting them leaves NaN and coerces the column to float,
        # which breaks the validator's string-based truthy check across ALL rows.
        specialty_flags = _default_specialty_prose_flags()
        specialty_flags.update(anchor.get("specialty_flags") or {})
        ctx.materials.append({
            "malzeme_satiri_id": m_line_id,
            "fatura_id": ctx.claim_id,
            "islem_satiri_id": proc_line_id,
            "hasta_id": ctx.pid,
            "malzeme_tarihi": ctx.start_date,
            "malzeme_kodu": str(anchor.get("material_code") or ""),
            "malzeme_adi": str(anchor.get("material_name") or ""),
            "malzeme_tipi": str(anchor.get("material_type") or "genel"),
            "uzmanlik_kategorisi": str(anchor.get("specialty_category") or "genel"),
            "adet": 1,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": unit_price,
            "beklenen_odenebilir_tutar_try": unit_price,
            "pakete_dahil_mi": False,
            "on_onay_gerekli_mi": False,
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"MEDULA-ANCHOR:{anchor.get('material_code', '')}",
            **prose_flags,
            **specialty_flags,
        })
        result["related_line_type"] = "material"
        result["related_line_id"] = m_line_id
        result["anchor_billed"] = str(unit_price)
        result["anchor_payable"] = str(unit_price)
        return result

    if anchor_type == "drug":
        # An oncology drug billed without the mandatory indication report.
        unit_price = 12500.0
        qty = 1
        billed = _money(unit_price * qty)
        payable = _money(billed * 0.72)
        existing_drugs = [r for r in ctx.drug_claims if r.get("fatura_id") == ctx.claim_id]
        drug_idx = len(existing_drugs) + 1
        d_line_id = f"ILC-{ctx.claim_id}-{drug_idx:03d}"
        prescription_id = f"REC-{ctx.claim_id}-{drug_idx:03d}"
        drug_row: dict[str, Any] = {
            "ilac_satiri_id": d_line_id,
            "recete_id": prescription_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "ilac_fatura_tarihi": ctx.start_date,
            "ilac_adi": str(anchor.get("ilac_adi") or ""),
            "ilac_kodu": str(anchor.get("ilac_kodu") or ""),
            "barkod": str(anchor.get("barkod") or ""),
            "esdeger_grup": str(anchor.get("esdeger_grup") or ""),
            "adet": qty,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": billed,
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_indirim_kademesi": 0.28,
            "katilim_payi_orani": 0.28,
            "ilave_ucret_orani": None,
            "beklenen_red_nedeni": "İlaç endikasyon raporu eksik",
            "beklenen_kural_izi": f"MEDULA-ANCHOR:drug:{anchor.get('ilac_kodu', '')}",
            **_empty_drug_indication_fields(),
        }
        drug_row["uzmanlik_kurulu_raporu_var"] = bool(anchor.get("uzmanlik_kurulu_raporu_var", False))
        ctx.drug_claims.append(drug_row)
        # Drug lines carry a line-level expected output (validator requires one
        # for every drug_claim_line; mirrors _append_drug_lines_for_claim).
        ctx.expected.append({
            "beklenen_cikti_id": f"BEK-{d_line_id}",
            "senaryo_etiketi": ctx.scenario_tag,
            "hasta_id": ctx.pid,
            "fatura_id": ctx.claim_id,
            "satir_id": d_line_id,
            "satir_tipi": "ilac",
            "kural_ailesi": "drug_indication",
            "beklenen_durum": "endikasyon_raporu_eksik",
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_tasarruf_try": _money(billed - payable),
            "beklenen_red_nedeni": "İlaç endikasyon raporu eksik",
            "beklenen_kural_izi": f"MEDULA-ANCHOR:drug:{anchor.get('ilac_kodu', '')}",
            "test_notu": "MEDULA anchor: oncology drug without indication report",
        })
        result["related_line_type"] = "drug"
        result["related_line_id"] = d_line_id
        result["anchor_billed"] = str(billed)
        result["anchor_payable"] = str(payable)
        return result

    # Unknown anchor type — claim-level fallback.
    result["related_line_type"] = "claim"
    return result
