"""Wave-1 *tail* batch of §2.6 definition/scope rules.

A prior batch (``definitions_2_6_wave1_batch_rules.py``) encoded 47 §2.6
deontic clauses.  This file closes the remaining 9 in-force clauses that
that batch missed (C001497, C001541, C001567, C001572, C001579, C001591,
C001600, C001603, C001604).  They are NO_PAY / MUST_NOT_BILL rules covering
dialysis travel when a courtesy service is provided, escort travel when a
vehicle is allocated, same-day daily allowance, inpatient/outpatient escort
billing, non-listed control-call costs, unlicensed thermal-spa costs,
funeral transport without referral, and intra-settlement / un-referred
travel exclusions.

Style follows the gap_closing family: free-form ``condition`` / ``action``
dicts, no strict schema.  Turkish is preserved verbatim in ``message_tr``.
``merge_definitions_2_6`` appends these after ``WAVE1_BATCH_RULES`` and
dedups by ``rule_id``.
"""

from __future__ import annotations

WAVE1_TAIL_BATCH_RULES: list[dict] = [
    # ─────────────────────────── 2.6.1.A — dialysis travel scope ──────────────
    {
        "rule_id": "2.6.1.A.(5).dialysis_service_courtesy_no_travel",
        "sut_section": "2.6.1.A",
        "gate_b_sources": ["C001497"],
        "condition": {
            "expense_not_covered": "diyaliz_sunucusunun_servis_hizmeti_vermesi_halinde_yol_gideri",
            "applies_to": "Servis hizmetinden faydalanan diyaliz hastaları",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Diyaliz merkezinin/sağlık hizmeti sunucusunun servis hizmeti verdiğinin "
            "tespit edilmesi halinde, servis hizmetinden faydalananlara bu mesafeler için ayrıca "
            "yol gideri ödenmez.",
        },
    },
    # ─────────────────────────── 2.6.1.B-3 — vehicle-allocated escort travel ──
    {
        "rule_id": "2.6.1.B-3.(3).vehicle_allocated_escort_no_travel",
        "sut_section": "2.6.1.B-3",
        "gate_b_sources": ["C001541"],
        "condition": {
            "expense_not_covered": "vasita_tahsis_edilen_refakatci_yol_gideri",
            "applies_to": "Bir vasıta tahsis edilerek gönderilen GSS'li ve bakmakla yükümlü olunan kişiler",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Genel sağlık sigortalısı ve bakmakla yükümlü olduğu kişiler, kendilerine bir "
            "vasıta tahsis edilmesi suretiyle başka bir yere gönderilmiş iseler, eşlik eden refakatçiye "
            "ayrıca yol gideri ödenmez.",
        },
    },
    # ─────────────────────────── 2.6.2 — same-day daily allowance ─────────────
    {
        "rule_id": "2.6.2.(3).same_day_application_no_daily_allowance",
        "sut_section": "2.6.2",
        "gate_b_sources": ["C001567"],
        "condition": {
            "expense_not_covered": "muracaat_ve_tedavi_bitisi_ayni_gun_ise_gundelik",
            "applies_to": "Sevk edilen sağlık hizmeti sunucusuna müracaat — aynı gün biten tedavi",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Sevk edilen sağlık hizmeti sunucusuna müracaat tarihi ile tedavinin sona erdiği "
            "tarihin aynı gün olması halinde gündelik ödenmez.",
        },
    },
    # ─────────────────────────── 2.6.3 — companion billing (MUST_NOT_BILL) ────
    {
        "rule_id": "2.6.3.(2).companion_ek2b_point_no_separate_daily",
        "sut_section": "2.6.3",
        "gate_b_sources": ["C001572"],
        "condition": {
            "expense_not_billed": "ayrica_gundelik_veya_outpatient_refakat_kodu",
            "applies_to": "Yatarak tedavide refakatçi yatak/yemek gideri ve günübirlik tedaviler",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Yatarak tedavi sırasında refakatçinin yatak ve yemek giderleri, sunucuca Kuruma "
            "fatura edilmesi halinde SUT eki EK-2/B “refakat” puanı esas alınarak karşılanır; ayrıca bu "
            "günler için ilgililere gündelik ödenmez. Günübirlik tedavilerde SUT eki EK-2/B “refakat” "
            "kodu faturalandırılamaz.",
        },
    },
    # ─────────────────────────── 2.6.4 — non-listed control-call costs ────────
    {
        "rule_id": "2.6.4.(c).non_listed_control_call_not_covered",
        "sut_section": "2.6.4",
        "gate_b_sources": ["C001579"],
        "condition": {
            "expense_not_covered": "ilk_fikrada_sayilmayan_tedavi_hastalik_kontrol_cagrisi_giderleri",
            "applies_to": "Birinci fıkra kapsamı dışındaki tedavi/hastalık kontrol çağrıları",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Birinci fıkrada sayılan tedaviler/hastalıklar dışında kalan tedavilerin/"
            "hastalıkların kontrol amaçlı çağrılarına ilişkin giderler Kurumca karşılanmaz.",
        },
    },
    # ─────────────────────────── 2.6.6 — unlicensed thermal-spa costs ─────────
    {
        "rule_id": "2.6.6.(3).unlicensed_thermal_spa_not_covered",
        "sut_section": "2.6.6",
        "gate_b_sources": ["C001591"],
        "condition": {
            "expense_not_covered": "isletme_izni_verilmeyen_kaplica_giderleri",
            "applies_to": "Sağlık Bakanlığınca işletme izni verilmeyen kaplıcalar",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Sağlık Bakanlığınca işletme izni verilmeyen kaplıcalarda tedavi görenlere ve "
            "refakatçilerine ait giderler Kurumca karşılanmaz.",
        },
    },
    # ─────────────────────────── 2.6.8 — funeral transport without referral ───
    {
        "rule_id": "2.6.8.(2).funeral_transport_without_referral_not_covered",
        "sut_section": "2.6.8",
        "gate_b_sources": ["C001600"],
        "condition": {
            "expense_not_covered": "sevk_edilmeksizin_muracaat_edilen_sunucuda_vefat",
            "applies_to": "Sevk edilmeksizin müracaat edilen sunucuda vefat eden kişilerin cenaze nakli",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Sevk edilmeksizin müracaat edilen sağlık hizmeti sunucusunda vefat eden kişilerin "
            "cenaze nakline ilişkin giderler Kurumca karşılanmaz.",
        },
    },
    # ─────────────────────────── 2.6.9 — intra-settlement transport ───────────
    {
        "rule_id": "2.6.9.(1).intra_settlement_transport_no_travel_daily",
        "sut_section": "2.6.9",
        "gate_b_sources": ["C001603"],
        "condition": {
            "expense_not_covered": "yerlesim_yeri_icindeki_nakiller",
            "applies_to": "Genel sağlık sigortalısı, bakmakla yükümlü olunan kişiler ve refakatçiler",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Genel sağlık sigortalısı ve bakmakla yükümlü olduğu kişiler ile refakatçilere "
            "mücavir alan yerleşim yeri içindeki nakiller için yol ve gündelik gideri ödenmez.",
        },
    },
    # ─────────────────────────── 2.6.9 — unreferred cross-settlement ──────────
    {
        "rule_id": "2.6.9.(2).unreferred_cross_settlement_no_travel_daily",
        "sut_section": "2.6.9",
        "gate_b_sources": ["C001604"],
        "condition": {
            "expense_not_covered": "sevk_yapilmaksizin_dis_yerlesim_yerinden_hizmet_alinmasi",
            "applies_to": "Belediye/büyükşehir belediye mücavir alanı yerleşim yeri dışı sevk edilmeksizin hizmet",
        },
        "action": {
            "enforcement": "reject",
            "message_tr": "Sevk yapılmaksızın belediye/büyükşehir belediye mücavir alanı yerleşim yeri "
            "dışındaki bir sağlık hizmeti sunucusundan sağlık hizmeti alınması hâlinde yol gideri ve "
            "gündelik ödenmez.",
        },
    },
]
