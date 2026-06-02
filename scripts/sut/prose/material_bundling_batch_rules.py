"""Curated Gate B batch rules — maps p1_encode themes to prose JSON rows."""

from __future__ import annotations

from typing import Any

# Appended after existing Sprint E rules (keyword block first in JSON for precedence).
GATE_B_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(2).titubb_uts_incomplete",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [
            "C001618",
            "C001619",
            "C002684",
            "C001636",
            "C002696",
        ],
        "condition": {"titubb_uts_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "TİTUBB/ÜTS kayıt-bildirim tamamlanmamış — Kurumca karşılanmaz (§3.1.1(2)).",
        },
    },
    {
        "rule_id": "3.1.1.(17).barcode_sut_mismatch",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001637", "C002697"],
        "condition": {
            "material_name_any": [
                "barkod-sut uyumsuz",
                "barkod sut uyumsuz",
                "sut kodu eşleşme hatalı",
                "sut kodu eslesme hatali",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Barkod–SUT kodu eşleştirme hatası — malzeme ödenmez (§3.1.1(17)).",
        },
    },
    {
        "rule_id": "3.1.1.(9).non_reimbursed_procedure_material",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002691"],
        "condition": {
            "material_name_any": [
                "karşılanmayan işlem malzemesi",
                "karsilanmayan islem malzemesi",
                "ödenmeyen işleme ait malzeme",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Bedeli karşılanmayan işleme ait malzeme — Kurumca karşılanmaz (§3.1.1(9)).",
        },
    },
    {
        "rule_id": "3.1.2.(2).not_in_ek3",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": [
            "C001834",
            "C001837",
            "C001840",
            "C001845",
            "C001849",
            "C002824",
            "C002828",
            "C002831",
        ],
        "condition": {"material_not_in_ek3": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Malzeme kodu EK-3 uzmanlık listelerinde yok — Kurumca karşılanmaz (§3.2.1 / §3.1.2).",
        },
    },
    {
        "rule_id": "3.1.2.(7).lost_stolen_miat",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001664", "C002707", "C002720"],
        "condition": {
            "material_name_any": [
                "kaybolması",
                "kaybolmasi",
                "çalınması",
                "calinmasi",
                "çalıntı",
                "calinti",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": "Kayıp/çalıntı sonrası MIAT dolana kadar yeni malzeme ödenmez (§3.1.2(7)).",
        },
    },
    {
        "rule_id": "3.1.2.c.onarim_not_covered",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002724"],
        "condition": {
            "material_name_any": [
                "kullanım kurallarına uyulmaması",
                "kullanim kurallarina uyulmamasi",
                "onarım masraf",
                "onarim masraf",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": "Kullanım kuralı ihlali onarım masrafı — Kurumca karşılanmaz (§3.1.2(c)).",
        },
    },
    {
        "rule_id": "3.1.2.ç.garanti_renewal_denied",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002742"],
        "condition": {
            "material_name_any": [
                "garanti süresi içindeki yenilenme",
                "garanti suresi icindeki yenilenme",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": "Garanti süresi içi yenileme talebi — Kurumca karşılanmaz (§3.1.2(ç)).",
        },
    },
    {
        "rule_id": "3.1.2.d.duplicate_function_garanty",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002743"],
        "condition": {
            "material_name_any": [
                "aynı işlevi gören",
                "ayni islevi goren",
                "birden fazla ürün çeşidi",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": "Aynı işlevli alternatif ürün — garanti süresi dolana kadar diğerleri ödenmez (§3.1.2(d)).",
        },
    },
    {
        "rule_id": "3.1.2.(17).device_consumable_excluded",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002749"],
        "condition": {
            "material_name_any": [
                "karşılanmayan tıbbi cihaz",
                "karsilanmayan tibbi cihaz",
                "cihaza ait sarf",
                "cihaz sarf",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Karşılanmayan cihaza ait sarf/bakım — Kurumca karşılanmaz (§3.1.2(17)).",
        },
    },
    {
        "rule_id": "3.1.3.(2).branch_unlisted_material",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001762", "C002789"],
        "condition": {
            "material_name_any": [
                "listelerde yer almayan branş",
                "listelerde yer almayan brans",
                "branş listesinde yok",
            ]
        },
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": "Branş EK-3 listesinde olmayan malzeme — Kurumca karşılanmaz (§3.1.3(2)).",
        },
    },
]

# Superseded by material_bundling_deferred_batch_rules.GATE_B_STILL_DEFERRED_CLAUSE_IDS
GATE_B_DEFERRED_CLAUSE_IDS: frozenset[str] = frozenset()
