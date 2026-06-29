"""L4.4 wave-2c — §3.3 specialty materials tail sub-sections (29 clauses → 29 rules).

Covers the remaining in-force deontic clauses scattered across the smaller
§3.3.X sub-sections (3.3.5, 3.3.7.A, 3.3.7.B, 3.3.8, 3.3.12, 3.3.13, 3.3.14,
3.3.15, 3.3.16, 3.3.17, 3.3.18, 3.3.19, 3.3.20, 3.3.21, 3.3.22, 3.3.23,
3.3.24, 3.3.25, 3.3.28, 3.3.29, 3.3.30, 3.3.34). These are predominantly
COVERAGE clauses encoding health-board-report, prescriber, facility,
3rd-step-provider, age-band and per-procedure-quantity requirements, mapped
to MUST_BILL / REGULATORY_ACTION deontics.

Each rule carries exactly one clause_id in ``gate_b_sources`` so every one of
the 29 source clauses is linked to a rule encoding.
"""

from __future__ import annotations

from typing import Any

WAVE2C_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        # 3.3.5
        "C002986", "C002989",
        # 3.3.7.A / 3.3.7.B
        "C003065", "C003071",
        # 3.3.8
        "C003075", "C003093",
        # 3.3.12
        "C003148", "C003149",
        # 3.3.13
        "C003151",
        # 3.3.14
        "C003154", "C003158",
        # 3.3.15
        "C003163", "C003168",
        # 3.3.16
        "C003170",
        # 3.3.17
        "C003180",
        # 3.3.18
        "C003185",
        # 3.3.19
        "C003187",
        # 3.3.20
        "C003189",
        # 3.3.21
        "C003191",
        # 3.3.22
        "C003193",
        # 3.3.23
        "C003195",
        # 3.3.24
        "C003197",
        # 3.3.25
        "C003199",
        # 3.3.28
        "C003268",
        # 3.3.29
        "C003270",
        # 3.3.30
        "C003272", "C003273",
        # 3.3.34
        "C003391", "C003393",
    }
)


def _all_gate_b_sources() -> list[str]:
    seen: list[str] = []
    for rule in WAVE2C_BATCH_RULES:
        for cid in rule.get("gate_b_sources", []):
            if cid not in seen:
                seen.append(cid)
    return seen


WAVE2C_BATCH_RULES: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- 3.3.5
    {
        "rule_id": "3.3.5.(1).enjektor_adet_ml_must_bill",
        "sut_section": "3.3.5",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002986"],
        "condition": {"material_name_any": ["enjektör", "enjektor"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ayaktan tedavide reçeteye yazılan enjektabl ilaç adedine ve "
                "ml'sine uygun enjektör bedeli — Kurumca belirlenen bedel "
                "üzerinden ödenir (§3.3.5(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.5.(2).insulin_kalem_igne_ucu_must_bill",
        "sut_section": "3.3.5",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002989"],
        "condition": {
            "material_name_any": [
                "insülin kalem iğne ucu",
                "insulin kalem igne ucu",
                "kalem iğne ucu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "İnsülin kalem iğne uçları — insülin kartuşları veya eksenatid "
                "etkin maddesi içeren ilaçlarla birlikte ya da tek başına "
                "reçete edildiğinde bedeli Kurumca karşılanır (§3.3.5(2))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.7.A
    {
        "rule_id": "3.3.7.A.c.cocuk_standing_table_tetrapleji_must_bill",
        "sut_section": "3.3.7.A",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003065"],
        "condition": {
            "material_name_any": ["standing table", "standing masasi", "standing masası"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Çocuk standing table — herhangi bir nedene bağlı tetrapleji/"
                "parapleji veya ayakta durmanın tedaviye katkı sağlayacağının "
                "belirtildiği 2-18 yaş hastalara bu hekimlerce reçete edilmesi "
                "halinde Kurumca bedeli karşılanır (§3.3.7.A c)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.7.B
    {
        "rule_id": "3.3.7.B.c.erin_stand_up_wheelchair_must_bill",
        "sut_section": "3.3.7.B",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003071"],
        "condition": {
            "material_name_any": ["stand up wheelchair", "stand-up wheelchair"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Erişkin stand up wheelchair — yerleşmiş parapleji klinik "
                "tablosunun belirtildiği ve bu hekimlerce reçete edildiği, "
                "aktif çalışan ve/veya öğrenci hastalarda Kurumca bedeli "
                "karşılanır (§3.3.7.B ç)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.8
    {
        "rule_id": "3.3.8.(1).ortopedi_travmatoloji_3_basamak_must_bill",
        "sut_section": "3.3.8",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003075"],
        "condition": {
            "material_name_any": ["ortopedi ve travmatoloji", "ortopedi implant"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ortopedi ve travmatoloji branşı ameliyatlarında kullanılan "
                "tıbbi malzemeler — eğitim verme yetkisi olan 3. basamak resmi "
                "sunucularda uygulanması halinde bedeli Kurumca karşılanır "
                "(§3.3.8(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.8.(2).ortopedi_danisma_kurulu_onay_must_bill",
        "sut_section": "3.3.8",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003093"],
        "condition": {
            "material_name_any": ["ortopedi ve travmatoloji", "ortopedi implant"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Belirtilen tıbbi malzemeler — eğitim verme yetkisi olan 3. "
                "basamak resmi sunucularda uygulanması ve Sağlık Bakanlığı "
                "Ortopedi Bilimsel Danışma Kurulundan her hasta için onay "
                "alınması şartıyla bedeli Kurumca karşılanır (§3.3.8(2))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.12
    {
        "rule_id": "3.3.12.(1).kulak_kepecesi_protezi_must_bill",
        "sut_section": "3.3.12",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003148"],
        "condition": {
            "material_name_any": ["kulak kepçesi protezi", "kulak kepecesi protezi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kulak kepçesi protezi — 3. basamak resmi sunucularda sağlık "
                "kurulu raporuna istinaden kulak burun boğaz veya plastik "
                "rekonstrüktif ve estetik cerrahi hekimlerince uygulanması "
                "halinde bedeli Kurumca karşılanır (§3.3.12(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.12.(2).kulak_kepecesi_protezi_yenileme_must_bill",
        "sut_section": "3.3.12",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003149"],
        "condition": {
            "material_name_any": ["kulak kepçesi protezi", "kulak kepecesi protezi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kulak kepçesi protezi — ilgili dal uzmanlarınca düzenlenen "
                "sağlık kurulu raporuna istinaden kulak burun boğaz veya "
                "plastik rekonstrüktif ve estetik cerrahi hekimlerince gerekli "
                "durumlarda yenilenmesi halinde bedeli Kurumca karşılanır "
                "(§3.3.12(2))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.13
    {
        "rule_id": "3.3.13.(1).kikirdak_hucre_kulturu_danisma_onay_must_bill",
        "sut_section": "3.3.13",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003151"],
        "condition": {
            "material_name_any": [
                "kıkırdak hücre kültürü",
                "kikirdak hucre kulturu",
                "otolog kondrosit",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Kıkırdak hücre kültürleri — EK-2/B 612731/612975 ve EK-2/C "
                "P612731/P612975 kodlarıyla birlikte, eğitim verme yetkisi olan "
                "3. basamak resmi sunucularda ve Ortopedi Bilimsel Danışma "
                "Kurulundan her hasta için onay alınması şartıyla bedelleri "
                "Kurumca karşılanır (§3.3.13(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.14
    {
        "rule_id": "3.3.14.(2).cift_yuzlu_mesh_defekt_goruntu_must_bill",
        "sut_section": "3.3.14",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003154"],
        "condition": {
            "material_name_any": ["çift yüzlü yama", "cift yuzlu yama", "mesh"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Çift yüzlü yamalar (meshler) — özellikli vakalarda ameliyat "
                "öncesi karın duvarı defektinin görüntüsünün epikrize eklenmesi, "
                "mesh ve defekt boyutlarının ilişkilendirilmesi ve genel cerrahi/"
                "göğüs cerrahisi/plastik rekonstrüktif cerrahi sağlık kurulu "
                "raporuyla 3. basamakta bedeli Kurumca karşılanır (§3.3.14(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.14.c.hiatus_diyafragma_herni_must_bill",
        "sut_section": "3.3.14",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003158"],
        "condition": {
            "material_name_any": ["çift yüzlü yama", "cift yuzlu yama", "mesh"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Çift yüzlü yama (mesh) — hiatus ve diyafragma hernilerinin açık "
                "ve laparoskopik onarımlarında kullanılması durumunda bedeli "
                "Kurumca karşılanır (§3.3.14 c)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.15
    {
        "rule_id": "3.3.15.(1).trakeobronsial_stent_gogus_kurulu_must_bill",
        "sut_section": "3.3.15",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003163"],
        "condition": {
            "material_name_any": ["trakeobronşiyal stent", "trakeobronsial stent"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Trakeobronşiyal stentler — 3. basamak resmi sunucularda göğüs "
                "hastalıkları ve/veya göğüs cerrahisi uzmanlarınca düzenlenen "
                "sağlık kurulu raporuna istinaden bedeli Kurumca karşılanır "
                "(§3.3.15(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.15.trakeobronsial_stent_endikasyon_must_bill",
        "sut_section": "3.3.15",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003168"],
        "condition": {
            "material_name_any": ["trakeobronşiyal stent", "trakeobronsial stent"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Trakeobronşiyal stentler — malign/benign darlıklarda ve trakea "
                "özofageal fistüllerde kullanılmaları halinde bedelleri Kurumca "
                "karşılanır (§3.3.15)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.16
    {
        "rule_id": "3.3.16.(1).total_yuz_maskesi_noninvaziv_must_bill",
        "sut_section": "3.3.16",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003170"],
        "condition": {
            "material_name_any": ["total yüz maskesi", "total yuz maskesi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Total yüz maskesi — noninvaziv mekanik ventilasyon ihtiyacı "
                "olan, yüz deformiteli/travmalı/yanıklı ya da oronazal maskeye "
                "uyum sağlayamayan hastalarda kullanılması durumunda bedeli "
                "Kurumca karşılanır (§3.3.16(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.17
    {
        "rule_id": "3.3.17.f.transbronsiyal_igne_aspirasyonu_must_bill",
        "sut_section": "3.3.17",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003180"],
        "condition": {
            "material_name_any": [
                "transbronsiyal iğne aspirasyonu",
                "transbronsiyal igne aspirasyonu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Transbronşiyal iğne aspirasyonu iğnesi — bronkojenik karsinom "
                "evrelemesi, peribronşial/submukozal lezyonlar, periferik "
                "nodüller/kitleler, sarkoidoz/tüberküloz ve mediastinal kitle "
                "tanısında kullanılması durumunda bedeli Kurumca karşılanır "
                "(§3.3.17)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.18
    {
        "rule_id": "3.3.18.b.brons_dilatasyon_balonu_must_bill",
        "sut_section": "3.3.18",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003185"],
        "condition": {
            "material_name_any": ["bronş dilatasyon balonu", "brons dilatasyon balonu"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Bronş dilatasyon balonları — trakeobronşiyal malign/benign "
                "darlıkların dilatasyonu ve hayatı tehdit eden hemoptizilerde "
                "kanayan tarafın ana bronşunu oblitere etmek durumlarında "
                "kullanılması halinde bedeli Kurumca karşılanır (§3.3.18)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.19
    {
        "rule_id": "3.3.19.(1).damar_kapama_ultrasonik_prob_must_bill",
        "sut_section": "3.3.19",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003187"],
        "condition": {
            "material_name_any": [
                "damar kapama probu",
                "ultrasonik cerrahi prob",
                "doku füzyonu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Damar kapama ve kesme probu ile ultrasonik cerrahi problar — 3. "
                "basamak resmi sunucularda kullanılması halinde bedelleri Kurumca "
                "karşılanır (§3.3.19(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.20
    {
        "rule_id": "3.3.20.(1).burun_protezi_total_defekt_must_bill",
        "sut_section": "3.3.20",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003189"],
        "condition": {"material_name_any": ["burun protezi", "epitez"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Burun protezi — total burun defektlerinin rekonstrüksiyonu veya "
                "epitezin yenilenmesine gerek duyulan hallerde 3. basamak resmi "
                "sunucularda sağlık kurulu raporuna istinaden bedeli Kurumca "
                "karşılanır (§3.3.20(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.21
    {
        "rule_id": "3.3.21.(1).dura_yapistirici_bos_fistulu_must_bill",
        "sut_section": "3.3.21",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003191"],
        "condition": {"material_name_any": ["dura yapıştırıcı", "dura yapistirici"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Dura yapıştırıcı — BOS fistülü olan vakalarda bedeli Kurumca "
                "karşılanır (§3.3.21(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.22
    {
        "rule_id": "3.3.22.(1).sentetik_meniskus_implant_must_bill",
        "sut_section": "3.3.22",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003193"],
        "condition": {
            "material_name_any": [
                "sentetik menisküs implant",
                "sentetik meniskus implant",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Sentetik menisküs implantları — 3. basamak resmi sunucularda "
                "uygulanması şartıyla, 45 yaş altında subtotal menisektomi "
                "sonrası en az 1 yıl geçmesine rağmen konvansiyonel tedavi ile "
                "ağrısı azalmayan vakalarda bedelleri Kurumca karşılanır "
                "(§3.3.22(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.23
    {
        "rule_id": "3.3.23.(1).meniskus_tamiri_urun_must_bill",
        "sut_section": "3.3.23",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003195"],
        "condition": {
            "material_name_any": [
                "menisküs tamiri",
                "meniskus tamiri",
                "nitinol",
                "tek barlı",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Menisküs tamiri ürünleri — 55 yaş altında, eğitim verme yetkisi "
                "3. basamak sunucularda 3 ortopedi uzmanı sağlık kurulu raporuyla "
                "(Nitinol/Tek Barlı en fazla 1, Çift Barlı en fazla 2 adet) "
                "onarılabilir kıkırdak lezyonu veya dejeneratif olmayan Zon-1/2 "
                "menisküs yırtığı olan vakalarda bedelleri Kurumca karşılanır "
                "(§3.3.23(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.24
    {
        "rule_id": "3.3.24.(1).sinus_tarsi_vidasi_cocuk_must_bill",
        "sut_section": "3.3.24",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003197"],
        "condition": {
            "material_name_any": ["sinüs tarsi vidası", "sinus tarsi vidasi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Sinüs tarsi vidası — esnek, ağrılı 8-14 yaş vaka grubunda "
                "eğitim verme yetkisi bulunan 3. basamak resmi sunucularda "
                "kullanılması halinde bedelleri Kurumca karşılanır (§3.3.24(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.25
    {
        "rule_id": "3.3.25.(1).omuz_balon_spacer_rotator_must_bill",
        "sut_section": "3.3.25",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003199"],
        "condition": {
            "material_name_any": ["omuz balon spacer", "absorbe olabilir omuz"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Absorbe olabilir omuz balon spacer — 3. basamak resmi "
                "sunucularda, tamir edilemeyen tam kat rotator cuff yırtıklarında "
                "sağlık kurulu raporuyla belgelendirilmesi ve başka tıbbi "
                "malzeme kullanılmaması kaydıyla işlem başına en fazla 1 adet "
                "kullanılması halinde bedeli Kurumca karşılanır (§3.3.25(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.28
    {
        "rule_id": "3.3.28.(1).hucresiz_kikirdak_matriks_danisma_must_bill",
        "sut_section": "3.3.28",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003268"],
        "condition": {
            "material_name_any": [
                "hücresiz kıkırdak matriks",
                "hucresiz kikirdak matriks",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Hücresiz kıkırdak matriksleri — EK-2/B 612732/612976 ve EK-2/C "
                "P612732/P612976 kodlarıyla birlikte, eğitim verme yetkisi olan "
                "3. basamak resmi sunucularda işlem başına en fazla 1 adet "
                "kullanılması halinde bedeli Kurumca karşılanır (§3.3.28(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.29
    {
        "rule_id": "3.3.29.(1).hucresiz_meniskus_implant_must_bill",
        "sut_section": "3.3.29",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003270"],
        "condition": {
            "material_name_any": [
                "hücresiz menisküs implant",
                "hucresiz meniskus implant",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Hücresiz menisküs implantları — eğitim verme yetkisi olan 3. "
                "basamak resmi sunucularda işlem başına en fazla 1 adet "
                "kullanıldığında bedeli Kurumca karşılanır (§3.3.29(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.30
    {
        "rule_id": "3.3.30.(1).bag_tendon_guclendirici_sutursuz_must_bill",
        "sut_section": "3.3.30",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003272"],
        "condition": {
            "material_name_any": [
                "kendinden sütursüz transosseöz",
                "kendinden sutursuz transosseoz",
                "transosseöz sistem",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kendinden sütursüz transosseöz sistemi — işlem başına en fazla "
                "1 adet kullanıldığında bedeli Kurumca karşılanır (§3.3.30(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.30.(2).transosseoz_sutur_tasiyici_must_bill",
        "sut_section": "3.3.30",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003273"],
        "condition": {
            "material_name_any": [
                "transosseöz sistem sütür taşıyıcı",
                "transosseoz sistem sutur tasiyici",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Transosseöz sistem sütür taşıyıcı — işlem başına en fazla 1 adet "
                "kullanıldığında bedeli Kurumca karşılanır (§3.3.30(2))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.34
    {
        "rule_id": "3.3.34.(2).hasta_alt_bezi_nakden_aylik_must_bill",
        "sut_section": "3.3.34",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003391"],
        "condition": {
            "material_name_any": [
                "hasta alt bezi",
                "külotlu hasta alt bezi",
                "cocuk hasta alt bezi",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Hasta alt bezi/külotlu hasta alt bezi — primer inkontinans "
                "tanısı belirtilmesi ve günde 4 adedi geçmemek kaydıyla 18 yaş "
                "üstü için A10049, 3-18 yaş için A10118 kodlu malzeme fiyatı "
                "üzerinden 1 aylık tutar nakden ödenir (§3.3.34(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.34.(3).inkontinans_hidrofilik_sonda_must_bill",
        "sut_section": "3.3.34",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003393"],
        "condition": {
            "material_name_any": [
                "hidrofilik kendinden kayganlaştırıcılı sonda",
                "hidrofilik sonda",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "İdrar/gaita inkontinansı nedeniyle hasta alt bezi ödemesi alan "
                "hastalarda; SUT hükümlerine göre düzenlenen sağlık raporu ve "
                "reçeteye istinaden hidrofilik kendinden kayganlaştırıcılı sonda "
                "bedeli Kurumca karşılanır (§3.3.34(3))."
            ),
        },
    },
]
