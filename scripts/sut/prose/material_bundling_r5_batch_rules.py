"""R5 Epic B — §3.1.2–3.1.3 batch rules + manifest-header-only clause IDs."""

from __future__ import annotations

from typing import Any

# Amendment-header rows encoded via gate_b_sources on substantive rules (not standalone).
R5_AMENDMENT_HEADER_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C002731",
        "C002738",
        "C002763",
    }
)

# §3.2.1 subsection headings — manifest trace only (no standalone JSON rules).
R5_MANIFEST_HEADER_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C002822",
        "C002826",
        "C002829",
    }
)

R5_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.2.(1).ek3c_list_field_definitions",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002706"],
        "condition": {"ek3c_list_field_definition_scope": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/C listelerinde SUT kodu, alan tanımı ve fiyat "
                "tanımları geçerlidir — liste eşleşmesi doğrulanmalı (§3.1.2(1))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(4)a.ismarlama_licensed_center_supply",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002710"],
        "condition": {"ismarlama_licensed_center_supply_required": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Ismarlama protez/ortez veya işitme cihazı — Sağlık Bakanlığı "
                "ruhsatlı merkezden temin şartı (§3.1.2(4)(a))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(5).ek3c_optional_appropriateness_consumables",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002714", "C002716", "C002717", "C002718", "C002731"],
        "condition": {"ek3c_optional_appropriateness_consumable": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Hasta alt bezi, sonda veya aspirasyon kateteri için tıbbi "
                "uygunluk zorunlu değil — ihtiyaç halinde aranabilir (§3.1.2(5))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(14).disabled_veteran_ortez_protez_billing",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002736", "C002737", "C002738"],
        "condition": {"disabled_veteran_ortez_protez_billing_review": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "3713 sayılı Kanun kapsamı malul/vazife malulü ortez-protez — "
                "liste fiyatı aşımı ve kapsam doğrulanmalı (§3.1.2(14))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(15).terror_victim_ortez_protez_documentation",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002747"],
        "condition": {"terror_victim_ortez_protez_documentation_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "3713/21 olay mağduru ortez-protez — mülki amirlik belgesi "
                "fatura ekinde olmalı (§3.1.2(15))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(18).prescription_correction_authority",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002750"],
        "condition": {"material_prescription_correction_invalid": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Reçete/rapor düzeltmesi yetkili hekim tarafından yapılmalı "
                "(§3.1.2(18))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.1.(3).device_return_deadline_missed",
        "sut_section": "3.1.2.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002756"],
        "condition": {"device_return_application_deadline_missed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İade kapsamı cihaz işlemi reçete tarihinden itibaren 10 işgünü "
                "içinde başlatılmalı (§3.1.2.1(3))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.effective_date_transition_scope",
        "sut_section": "3.1.3",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C008292"],
        "condition": {"material_effective_date_transition_scope": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "§3.1.3 geçiş hükmü — yürürlük tarihi ve fiyat geçişi "
                "doğrulanmalı (RG geçiş metni)."
            ),
        },
    },
]

R5_RULE_PATCHES: dict[str, dict[str, Any]] = {
    "3.1.2.report_prescription_invalid": {
        "gate_b_sources_append": ["C002763"],
    },
}
