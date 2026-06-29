"""L r6 — §3.1/§3.2/§3.3 leftover materials batch (21 clauses → 21 rules).

Each clause_id from tasks/encode_waves/REM_others_materials.csv lands in exactly
one rule's gate_b_sources.

Deontic modality mapping (from CSV → SUT rule deontic):
  NO_PAY            → NO_PAY
  COVERAGE          → MUST_BILL / REGULATORY_ACTION
  MANDATORY         → REGULATORY_ACTION
  PERMISSION        → REGULATORY_ACTION
  PROHIBITED        → MUST_NOT_BILL
"""

from __future__ import annotations

from typing import Any

R6_LEFTOVER_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        # §3.1.1 general material payment rules
        "C002684", "C002689", "C002691", "C002692", "C002694", "C002695",
        "C002696", "C002697", "C002698",
        # §3.1.2 miat / protez-ortez renewal
        "C002720", "C002727", "C002728", "C002729", "C002744",
        # §3.1.3 list-external / demirbaş / reusable
        "C002789", "C002794", "C002795", "C002796",
        # §3.2.1.A/B/C not-in-list invoicing
        "C002824", "C002828", "C002831",
    }
)

BATCH_RULES: list[dict[str, Any]] = [
    # ───────────────────────── §3.1.1 — general material payment rules ─────────────────────────
    {
        "rule_id": "3.1.1.titubb_uts_registration_required",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002684"],
        "condition": {"material_titubb_uts_registration_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "TİTUBB/ÜTS kayıt/bildirimi tamamlanmamış tıbbi malzeme "
                "bedelleri Kurumca karşılanmaz (§3.1.1(2))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.ek3b_listed_material_excluded",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002689"],
        "condition": {"material_listed_in_ek3b_excluded": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "EK-3/B Listesinde yer alan tıbbi malzemeler istisnalar hariç "
                "Kurumca karşılanmaz (§3.1.1(7))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.material_for_nonpayable_procedure",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002691"],
        "condition": {"material_belonging_to_nonpayable_procedure": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Bedeli Kurumca karşılanmayan işleme ait tıbbi malzeme bedelleri "
                "Kurumca karşılanmaz (§3.1.1(9))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.ek3_price_kdv_handling",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002692"],
        "condition": {"ek3_price_kdv_exception_misapplied": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "EK-3 listelerindeki tıbbi malzeme fiyatları KDV hariçtir; tanımlı "
                "istisna/muafiyetler dışında KDV ilave edilerek ödenir (§3.1.1(10))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.abroad_sunucu_kesintiler_karsilanmaz",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002694"],
        "condition": {"abroad_sunucu_isletme_hazine_kesinti_claimed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yurt dışındaki Kurumla sözleşmeli sunucularda kullanılan "
                "malzemelere ait işletme gideri, hazine ve SHÇEK kesintileri "
                "Kurumca karşılanmaz (§3.1.1(12))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.material_sut_kodu_faturalama_kurali",
        "sut_section": "3.1.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002695"],
        "condition": {"material_additional_billing_requires_sut_provision": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "EK-3 SUT kodlarının işlem bedeline ilave faturalanabilmesi için "
                "SUT/eklerinde ilave faturalanabileceğinin belirtilmiş olması "
                "gerekir (§3.1.1(13))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.medula_tanimli_olmayan_malzeme_karsilanmaz",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002696"],
        "condition": {"material_not_defined_in_medula_on_procedure_date": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İşlem tarihinde MEDULA'da SUT kodu bazında tanımlı olmayan tıbbi "
                "malzeme bedelleri Kurumca karşılanmaz (§3.1.1(14))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.hatali_barkod_sut_eslesmesi_odeme",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002697"],
        "condition": {"barcode_sut_mismatch_or_noncompliant_invoicing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Barkod-SUT kodu eşleştirmesi hatalı veya malzeme kural/kriterlere "
                "uygunsuz fatura edildiyse bedel ödenmez, ödendiyse yersiz ödeme "
                "olarak tahsil edilir (§3.1.1(15))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.sunucu_kisiti_isleme_yansir",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002698"],
        "condition": {"material_sunucu_restriction_violated_on_procedure": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Malzemedeki sağlık hizmeti sunucusu kısıtı, malzemenin "
                "faturalandırıldığı işlem bedelinin ödemesinde de aranır; "
                "uymayan işlemlerin bedelleri ödenmez (§3.1.1(16))."
            ),
        },
    },

    # ───────────────────────── §3.1.2 — miat / protez-ortez renewal ─────────────────────────
    {
        "rule_id": "3.1.2.kayip_calinti_miat_dolana_kadar_yenilenmez",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002720"],
        "condition": {"material_lost_or_stolen_before_miat_expiry": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kurumca karşılanan tıbbi malzeme kaybolduğunda/çalındığında miat "
                "süresi doluncaya kadar yenisinin bedeli Kurumca karşılanmaz "
                "(§3.1.2(7))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.b.miatli_arizali_malzeme_yenileme",
        "sut_section": "3.1.2",
        "deontic": "MUST_NOT_BILL",
        "gate_b_sources": ["C002727"],
        "condition": {"miatli_material_early_renewal_misrouted_responsible": True},
        "action": {
            "material_outcome": "must_not_bill_separately",
            "severity": "warning",
            "message_tr": (
                "Miat dolmadan kasıt/kusur dışı arızalanan EK-3/C-2 ve C-3 "
                "malzeme — garanti içinde satıcı firma, garanti dışında Kurum "
                "tarafından süresinden önce yenilenir; faturalama yetkili tarafa "
                "yöneltilmelidir (§3.1.2(b))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.c.protez_ortez_early_renewal_75pct_coverage",
        "sut_section": "3.1.2",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002728"],
        "condition": {"protez_ortez_early_renewal_repair_cost_over_75pct": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/C-2 protez/ortezde bakım-onarım mümkün değilse ve ilgili "
                "parçaların onarım bedeli protez/ortez bedelinin %75'ini "
                "aşıyorsa, resmi sunucu sağlık raporuyla süresinden önce yenileme "
                "Kurumca karşılanır (§3.1.2(c))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.c_protez_ortez_ara_urun_renewal_coverage",
        "sut_section": "3.1.2",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002729"],
        "condition": {"protez_ortez_intermediate_part_renewal_documented": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/C-2 protez/ortezin miat süresi içinde ara ürünlerinden biri "
                "yenilenip protez/ortez kullanılabiliyorsa, bakım-onarım gereken "
                "parçaların bedelleri Kurumca karşılanır (§3.1.2(ç))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.e.garanti_sonu_kullanilamaz_yenileme_coverage",
        "sut_section": "3.1.2",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002744"],
        "condition": {
            "ek3c2_c5_material_unusable_after_warranty_health_board": True
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/C-2 ve C-5 malzemenin garanti süresi sonunda "
                "kullanılamaz olduğu FTR + ortopedi/travmatoloji sağlık kurulu "
                "raporuyla belgelendirilirse, miat süresi dikkate alınmadan "
                "yenileme Kurumca karşılanır (§3.1.2(e))."
            ),
        },
    },

    # ───────────────────────── §3.1.3 — list-external / demirbaş / reusable ─────────────────────────
    {
        "rule_id": "3.1.3.not_in_list_material_karsilanmaz",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002789"],
        "condition": {"material_not_in_sut_lists_without_contract": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "SUT eki listelerde yer almayan ve Kurumla sözleşmeli olmayan tıbbi "
                "malzeme bedelleri Kurumca karşılanmaz (§3.1.3(2))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.serbest_kodsuz_medula_giris_karsilanmaz",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002794"],
        "condition": {"material_entered_as_serbest_kodsuz_in_medula": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Malzemeler serbest kodsuz olarak MEDULA-Hastane'ye girilemez; "
                "girilirse hiçbir koşulda bedelleri Kurumca karşılanmaz "
                "(§3.1.3(7))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.demirbas_ve_reusable_sarf_karsilanmaz",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002795"],
        "condition": {"demirbas_or_reusable_accessory_spare_part_claimed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Demirbaş malzemeler ile bunların tamir/bakım-onarım, yedek parça, "
                "aksesuar ve tekrar kullanılabilir sarf bedelleri Kurumca "
                "karşılanmaz (§3.1.3(8))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.sunucu_temin_reusable_malzeme_karsilanmaz",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002796"],
        "condition": {"reusable_material_supplied_by_sunucu_claimed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Sağlık hizmeti sunucusu tarafından temin edilen tekrar kullanılabilir "
                "tıbbi malzeme bedelleri Kurumca karşılanmaz (§3.1.3(9))."
            ),
        },
    },

    # ───────────────────────── §3.2.1.A/B/C — not-in-list invoicing ─────────────────────────
    {
        "rule_id": "3.2.1.A.not_in_list_invoice_karsilanmaz",
        "sut_section": "3.2.1.A",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002824"],
        "condition": {"material_not_in_sut_lists_invoiced_for_payment": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "SUT eki listelerde yer almayan tıbbi malzemenin fatura edilmesi "
                "halinde bedelleri Kurumca karşılanmaz (§3.2.1.A(2))."
            ),
        },
    },
    {
        "rule_id": "3.2.1.B.not_in_list_invoice_karsilanmaz",
        "sut_section": "3.2.1.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002828"],
        "condition": {"material_not_in_sut_lists_invoiced_for_payment": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "SUT ve eki listelerde yer almayan tıbbi malzemenin fatura edilmesi "
                "halinde bedelleri Kurumca karşılanmaz (§3.2.1.B(2))."
            ),
        },
    },
    {
        "rule_id": "3.2.1.C.not_in_list_invoice_karsilanmaz",
        "sut_section": "3.2.1.C",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002831"],
        "condition": {"material_not_in_sut_lists_invoiced_for_payment": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "SUT ve eki listelerde yer almayan tıbbi malzemenin fatura edilmesi "
                "halinde bedelleri Kurumca karşılanmaz (§3.2.1.C(2))."
            ),
        },
    },
]
