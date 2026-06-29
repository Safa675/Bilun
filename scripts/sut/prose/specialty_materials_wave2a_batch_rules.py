"""L4.4 Wave 2a — §3.3.33 (auditory implants), §3.3.4 (greft sub-sections), §3.3.26
(orthopedic tumor/resection prosthesis) specialty batch (52 clauses → 52 rules).

Each clause_id from tasks/encode_waves/A3a_specialty_big.csv lands in exactly one
rule's gate_b_sources.
"""

from __future__ import annotations

from typing import Any

WAVE2A_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        # §3.3.26 orthopedic tumor/resection prosthesis (COVERAGE)
        "C003201", "C003202", "C003207", "C003216", "C003220", "C003227",
        "C003231", "C003234", "C003240", "C003243", "C003245", "C003248",
        "C003251",
        # §3.3.33 auditory implants
        "C003306", "C003332", "C003334", "C003339", "C003340", "C003344",
        "C003345", "C003347", "C003348", "C003349", "C003350", "C003355",
        "C003362", "C003364", "C003378", "C003379", "C003383", "C003385",
        "C003366", "C003369",
        # §3.3.4 greft sub-sections A/B/C/Ç
        "C002932", "C002933", "C002938", "C002946", "C002947", "C002948",
        "C002950", "C002951", "C002952", "C002954", "C002957", "C002960",
        "C002961", "C002965", "C002968", "C002969", "C002972", "C002973",
        "C002976",
    }
)

WAVE2A_BATCH_RULES: list[dict[str, Any]] = [
    # ───────────────────────── §3.3.26 — orthopedic tumor/resection prosthesis ─────────────────────────
    {
        "rule_id": "3.3.26.(1).orthopedic_tumor_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003201"],
        "condition": {"orthopedic_tumor_prosthesis_third_step_facility": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/F-3 tümör/rezeksiyon alan grubu protezleri — geri ödeme "
                "kriterlerine uygun ve eğitim yetkili 3. basamak/vakıf protokollü "
                "özel hastanede kullanımı halinde Kurumca karşılanır (§3.3.26(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.a.saddle_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003202"],
        "condition": {"saddle_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Saddle protez — tanımlı kriterlerden en az biri varsa bedeli "
                "Kurumca karşılanır (§3.3.26(a))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.b.proximal_femur_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003207"],
        "condition": {"proximal_femur_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Proksimal femur rezeksiyon protezi — kriterlerden en az biri "
                "mevcutsa Kurumca karşılanır (§3.3.26(b))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.c.total_femur_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003216"],
        "condition": {"total_femur_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Total femur rezeksiyon protezi — kriterlerden en az biri varsa "
                "Kurumca karşılanır (§3.3.26(c))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.c.distal_femur_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003220"],
        "condition": {"distal_femur_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Distal femur rezeksiyon protezi — kriterlerden en az biri varsa "
                "Kurumca karşılanır (§3.3.26(ç))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.d.proximal_tibia_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003227"],
        "condition": {"proximal_tibia_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Proksimal tibia rezeksiyon protezi — kriterlerden en az biri "
                "varsa Kurumca karşılanır (§3.3.26(d))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.e.distal_tibia_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003231"],
        "condition": {"distal_tibia_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Distal tibia rezeksiyon protezi — kriterlerden en az biri varsa "
                "Kurumca karşılanır (§3.3.26(e))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.f.skapula_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003234"],
        "condition": {"skapula_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Skapula protezi — kriterlerden en az biri varsa Kurumca "
                "karşılanır (§3.3.26(f))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.g.proximal_humerus_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003240"],
        "condition": {"proximal_humerus_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Proksimal humerus rezeksiyon protezi — kriterlerden en az biri "
                "varsa Kurumca karşılanır (§3.3.26(g))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.g.intercalar_segment_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003243"],
        "condition": {"intercalar_segment_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "İnterkalar rezeksiyon/segment protezi — kriterlerden en az biri "
                "varsa Kurumca karşılanır (§3.3.26(ğ))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.h.total_humerus_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003245"],
        "condition": {"total_humerus_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Total humerus protezi — kriterlerden en az biri varsa Kurumca "
                "karşılanır (§3.3.26(h))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.i.elbow_resection_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003248"],
        "condition": {"elbow_resection_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Dirsek rezeksiyon protezi — kriterlerden en az biri varsa "
                "Kurumca karşılanır (§3.3.26(ı))."
            ),
        },
    },
    {
        "rule_id": "3.3.26.i.expandable_prosthesis_coverage",
        "sut_section": "3.3.26",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003251"],
        "condition": {"expandable_prosthesis_criteria_met": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Uzayabilen protez — kriterlerden en az biri varsa Kurumca "
                "karşılanır (§3.3.26(i))."
            ),
        },
    },

    # ───────────────────────── §3.3.33 — auditory implants ─────────────────────────
    {
        "rule_id": "3.3.33.A.(1).auditory_implant_third_step_facility",
        "sut_section": "3.3.33.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003306"],
        "condition": {"auditory_implant_non_third_step_facility": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "İşitsel implantlar yalnızca 3. basamak resmi sunucu veya vakıf "
                "protokollü özel hastanede uygulandığında Kurumca karşılanır "
                "(§3.3.33.A(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.cochlear_implant_coverage_general",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003332"],
        "condition": {"cochlear_implant_commission_or_bilateral_criteria": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Koklear implant — İşitsel İmplantlar Komisyonu onayı veya "
                "bilateral ileri-çok ileri sensörinöral işitme kaybı + işitme "
                "cihazından yarar görmeme sağlık kurulu raporu ile Kurumca "
                "karşılanır (§3.3.33.B)."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(2).cochlear_implant_alternative_criteria",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003334"],
        "condition": {"cochlear_implant_alternative_criteria_health_board": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Koklear implant — alternatif kriterlerden en az biri sağlık "
                "kurulu raporuyla belgelenirse Kurumca karşılanır (§3.3.33.B(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(5).cochlear_implant_meningitis",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003339"],
        "condition": {"cochlear_implant_meningitis_post_hearing_loss": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Menenjit sonrası işitme kaybında koklear implant — 3 aylık "
                "binaural cihaz deneme şartı aranmaz, sağlık kurulu raporuyla "
                "Kurumca karşılanır (§3.3.33.B(5))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(6).cochlear_implant_auditory_neuropathy",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003340"],
        "condition": {"cochlear_implant_auditory_neuropathy_no_benefit": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "İşitsel nöropati olgusunda en az 6 ay rehabilitasyondan yarar "
                "görmeme odyolojik + sağlık kurulu raporuyla koklear implant "
                "Kurumca karşılanır (§3.3.33.B(6))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.c.bilateral_blindness_over_48m",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003344"],
        "condition": {"cochlear_implant_bilateral_blindness_over_48_months": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "48 ay üzeri ileri sensörinöral işitme kaybına eşlik eden "
                "bilateral körlük — koklear implant kriteri (§3.3.33.B(c))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(8).cochlear_implant_internal_part_revision",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003345"],
        "condition": {"cochlear_implant_internal_part_revision_no_term": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Enfeksiyon/kolesteatom/tümör ile iç parça işlevsizliğinde süre "
                "aranmaksızın yalnızca cerrahi iç parça bedeli Kurumca "
                "karşılanır (§3.3.33.B(8))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(10).cochlear_implant_audiologic_protocol",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003347"],
        "condition": {"cochlear_implant_audiologic_protocol_required": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Koklear implant odyolojik değerlendirme (odyometri, timpanometri, "
                "stapes refleks, OAE, ABR) uygulanmalıdır (§3.3.33.B(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(10)a.cochlear_implant_threshold_over_2y",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003348"],
        "condition": {"cochlear_implant_threshold_adult_child_criteria": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "2 yaş üzeri çocuk/erişkinlerde bilateral 500-4000 Hz ortalaması "
                ">80 dB (veya asimetrik 70/90 dB) ve konuşmayı ayırt etme <%30 "
                "koklear implant kriteri (§3.3.33.B(10)(a))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(10)b.cochlear_implant_threshold_under_2y",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003349"],
        "condition": {"cochlear_implant_threshold_infant_criteria": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "2 yaş ve altı çocuklarda bilateral >90 dB HL sensörinöral işitme "
                "kaybı koklear implant kriteri (§3.3.33.B(10)(b))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.B.(11).cochlear_implant_minimum_kit_content",
        "sut_section": "3.3.33.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003350"],
        "condition": {"cochlear_implant_minimum_kit_content_check": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Koklear implant asgari çanta içeriği (işlemci, transmitter, pil, "
                "kablo, mıknatıs vb.) kontrol edilmelidir (§3.3.33.B(11))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.C.(1).bone_anchored_hearing_aid_coverage",
        "sut_section": "3.3.33.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003355"],
        "condition": {"bone_anchored_hearing_aid_over_5y_criteria": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "5 yaş üzeri bilateral işitme kaybı + konvansiyonel cihazdan yarar "
                "görmeme (3 KBB uzmanı + odyolog sağlık kurulu) veya Komisyon "
                "onayıyla kemiğe monte işitme cihazı Kurumca karşılanır "
                "(§3.3.33.C(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.C.e.single_side_deaf_conductive_mixed",
        "sut_section": "3.3.33.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003362"],
        "condition": {"bone_anchored_hearing_aid_single_sided_deafness": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tek kulak total işitme kaybı + karşı kulak iletim/mikst tip "
                "kaybında kemiğe monte cihaz Kurumca karşılanır (§3.3.33.C(e))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.C.(4).headband_internal_part_coverage",
        "sut_section": "3.3.33.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003364"],
        "condition": {"bone_anchored_hearing_aid_headband_internal_part": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kafa bandı uygulanan hastada cerrahi planlanan tarihte aktarıcı "
                "sistem + iç parça bedeli Kurumca karşılanır (§3.3.33.C(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.D.(1).brainstem_implant_health_board",
        "sut_section": "3.3.33.D",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003378"],
        "condition": {"brainstem_implant_unilateral_health_board": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Beyin sapı implantı — 3 KBB uzmanı + odyolog/psikolog/dil-konuşma "
                "terapisti değerlendirmeli sağlık kurulu raporuyla tek taraflı "
                "uygulamada Kurumca karşılanır (§3.3.33.D(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.D.(2).brainstem_implant_bilateral_profound",
        "sut_section": "3.3.33.D",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003379"],
        "condition": {"brainstem_implant_bilateral_profound_loss": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Bilateral çok ileri derecede sensörinöral işitme kaybında beyin "
                "sapı implantı Kurumca karşılanır (§3.3.33.D(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.D.(3).brainstem_implant_kurum_odeme",
        "sut_section": "3.3.33.D",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003383"],
        "condition": {"brainstem_implant_criteria_kurum_odeme": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Beyin sapı implantı — tanımlı kriterleri sağlayanlarda bedeli "
                "Kurumca karşılanır (§3.3.33.D)."
            ),
        },
    },
    {
        "rule_id": "3.3.33.D.(5).brainstem_implant_commission_approval",
        "sut_section": "3.3.33.D",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003385"],
        "condition": {"brainstem_implant_commission_outside_criteria": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kriterleri taşımayan hastalarda İşitsel İmplantlar Komisyonu "
                "onayıyla beyin sapı implantı Kurumca karşılanır (§3.3.33.D(5))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.C.(1).middle_ear_implant_coverage",
        "sut_section": "3.3.33.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003366"],
        "condition": {"middle_ear_implant_bilateral_stable_threshold": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Orta kulak implantı — bilateral kayıp + cihazdan yarar görmeme "
                "(3 KBB + odyolog) ve son 2 yıl stabil eşik; Komisyon onayıyla "
                "Kurumca karşılanır (§3.3.33.Ç(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.33.Ç.(2).middle_ear_implant_no_retrocochlear",
        "sut_section": "3.3.33.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003369"],
        "condition": {"middle_ear_implant_no_retrocochlear_pathology_required": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Orta kulak implantı için retrokoklear patoloji olmadığı sağlık "
                "kurulu raporunda belirtilmelidir (§3.3.33.Ç(2))."
            ),
        },
    },

    # ───────────────────────── §3.3.4.A — greft / allogreft sub-section ─────────────────────────
    {
        "rule_id": "3.3.4.A.(1).allogreft_titubb_uts_registration",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002932"],
        "condition": {"allogreft_titubb_uts_registration_required": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "İnsan dokusu kaynaklı ürünlerin (allogreft) MEDULA girişinde "
                "TİTUBB/ÜTS kaydı “Allogreft Ürün Onay Ekranı”nda tamamlanmalı ve "
                "barkodlu gönderilmelidir (§3.3.4.A(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(2).allogreft_donor_id_mandatory",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002933"],
        "condition": {"allogreft_donor_id_mandatory": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Sunucu tarafından Donör ID MEDULA-Hastane ilgili alanına girilmesi "
                "zorunludur (§3.3.4.A(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(7).graft_small_dimension_combination_prohibited",
        "sut_section": "3.3.4.A",
        "deontic": "MUST_NOT_BILL",
        "gate_b_sources": ["C002938"],
        "condition": {"graft_small_dimension_combined_for_large_qty": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Küçük boyut/ölçüler bir arada kullanılarak listedeki büyük "
                "miktarlar elde edilemez (§3.3.4.A(7))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.e.corpectomy_cage_fill_coverage",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002946"],
        "condition": {"corpectomy_interbody_cage_fill_graft_coverage": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tümör/travma korpektomi boşluğuna titanyum/çelik interbody kafes "
                "içi doldurulduğunda (DBM hariç) bedeli Kurumca karşılanır "
                "(§3.3.4.A(e))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(10).synthetic_graft_30cc_cap",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002947"],
        "condition": {"synthetic_graft_per_case_30cc_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Sentetik greft kullanılan tüm uygulamalarda vaka başı 30 cc’yi "
                "geçmemek üzere Kurumca karşılanır (§3.3.4.A(10))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(11).allograft_xenograft_60cc_cap",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002948"],
        "condition": {"allograft_xenograft_per_case_60cc_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Allogreft/xenogreft kullanılan tüm uygulamalarda vaka başı 60 "
                "cc’yi geçmemek üzere Kurumca karşılanır (§3.3.4.A(11))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.a.posterior_spinal_allograft_xenograft_cap",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002950"],
        "condition": {"posterior_spinal_allograft_xenograft_per_level_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Posterior spinal stabilizasyonda allogreft/xenogreft C1-T10 her "
                "seviye 5 cc, T11-S1 her seviye 10 cc’yi geçmemek üzere Kurumca "
                "karşılanır (§3.3.4.A(a))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.b.posterior_spinal_synthetic_graft_cap",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002951"],
        "condition": {"posterior_spinal_synthetic_graft_per_level_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Posterior spinal stabilizasyonda sentetik greft C1-T10 her "
                "seviye 2,5 cc, T11-S1 her seviye 5 cc’yi geçmemek üzere Kurumca "
                "karşılanır (§3.3.4.A(b))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(13).bone_cyst_allograft_xenograft_120cc_cap",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002952"],
        "condition": {"bone_cyst_allograft_xenograft_120cc_ct_documented": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Büyük kemik kisti cerrahisinde allogreft/xenogreft — koronal/aksiyel "
                "BT raporuyla 120 cc’yi geçmemek üzere Kurumca karşılanır "
                "(§3.3.4.A(13))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(15).fascia_temporalis_ent_only",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002954"],
        "condition": {"fascia_temporalis_allograft_ent_only": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Fasiya Temporalis alan tanımındaki allogreftler yalnızca Kulak "
                "Burun Boğaz uzmanlık dalınca kullanıldığında Kurumca karşılanır "
                "(§3.3.4.A(15))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.A.(17).graft_op_note_epikriz_mandatory",
        "sut_section": "3.3.4.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002957"],
        "condition": {"graft_op_note_epikriz_mandatory": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Greft adı ve miktarını içeren ameliyat notu MEDULA-Hastane epikriz "
                "alanına girilmelidir (§3.3.4.A(17))."
            ),
        },
    },

    # ───────────────────────── §3.3.4.B — ligament/tendon reconstruction graft ─────────────────────────
    {
        "rule_id": "3.3.4.B.a.reconstruction_revision_one_unit_cap",
        "sut_section": "3.3.4.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002960"],
        "condition": {"reconstruction_revision_one_unit_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Rekonstrüksiyon revizyon ameliyatlarında en fazla 1 adet "
                "kullanıldığında Kurumca karşılanır (§3.3.4.B(a))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.B.b.multi_ligament_reconstruction_two_unit_cap",
        "sut_section": "3.3.4.B",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002961"],
        "condition": {"multi_ligament_reconstruction_two_unit_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Çoklu bağ rekonstrüksiyon ameliyatlarında en fazla 2 adet "
                "kullanıldığında Kurumca karşılanır (§3.3.4.B(b))."
            ),
        },
    },

    # ───────────────────────── §3.3.4.C — DBM / bone stimulant ─────────────────────────
    {
        "rule_id": "3.3.4.C.(2).dbm_cervical_fusion_1cc_cap",
        "sut_section": "3.3.4.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002965"],
        "condition": {"dbm_cervical_fusion_1cc_per_disc_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tek başına DBM için servikal füzyonda disk mesafesinde kafes içine "
                "1 cc’yi geçmemek üzere Kurumca karşılanır (§3.3.4.C(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.C.(5).open_physis_tumor_defect_health_board",
        "sut_section": "3.3.4.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002968"],
        "condition": {"open_physis_tumor_defect_health_board_volume_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Epifiz hattı açık hastanın tümoral defektinde — 3 ortopedi "
                "uzmanı sağlık kurulu raporuyla humerus/pelvis/femur/tibia 5 cc, "
                "fibula/radius/ulna 2 cc, diğer kemikler 1 cc’yi geçmemek üzere "
                "Kurumca karşılanır (§3.3.4.C(5))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.C.(6).spinal_fusion_revision_nonunion_5cc_cap",
        "sut_section": "3.3.4.C",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002969"],
        "condition": {"spinal_fusion_revision_nonunion_5cc_cap": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Enstrümante spinal füzyon üzerinden ≥1 yıl geçtiği halde "
                "füzyon elde edilemeyen revizyon vakalarında vaka başı 5 cc’yi "
                "geçmemek üzere Kurumca karşılanır (§3.3.4.C(6))."
            ),
        },
    },

    # ───────────────────────── §3.3.4.Ç — dura graft ─────────────────────────
    {
        "rule_id": "3.3.4.C.(1).dura_defect_uncovered_by_autograft",
        "sut_section": "3.3.4.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002972"],
        "condition": {"dura_defect_uncovered_by_autograft": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Otojen greftlerle kapatılamayan dura defekti olan vakalarda "
                "bedeli Kurumca karşılanır (§3.3.4.Ç(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.C.(2).dura_graft_coverage_general",
        "sut_section": "3.3.4.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002973"],
        "condition": {"dura_graft_indication_coverage": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Dura greftleri tanımlı endikasyonlarda kullanılması halinde "
                "Kurumca karşılanır (§3.3.4.Ç(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.4.C.c.intramedullary_intradural_spinal_coverage",
        "sut_section": "3.3.4.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002976"],
        "condition": {"dura_graft_intramedullary_intradural_spinal": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Dekompresyon/disk/kırık cerrahisi hariç intramedüller/intradural "
                "spinal cerrahide dura grefti Kurumca karşılanır (§3.3.4.Ç(c))."
            ),
        },
    },
]
