"""L4.4 wave-2b — §3.3 specialty materials mid-batch (51 clauses → 51 rules).

Covers in-force deontic clauses across sub-sections 3.3.3, 3.3.6, 3.3.32,
3.3.2, 3.3.10, 3.3.27, 3.3.1, 3.3.9, 3.3.11. These are predominantly
COVERAGE / MANDATORY / PERMISSION clauses encoding health-board-report,
prescriber, renewal-period and report-content requirements, mapped to
MUST_BILL / REGULATORY_ACTION / MUST_NOT_BILL / NO_PAY deontics.

Each rule carries exactly one clause_id in ``gate_b_sources`` so every one of
the 51 source clauses is linked to a rule encoding.
"""

from __future__ import annotations

from typing import Any

WAVE2B_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C002839", "C002850", "C002853", "C002855",
        "C003115", "C003123", "C003127", "C003140", "C003141",
        "C003143", "C003144", "C003145",
        "C002873", "C002874", "C002875", "C002881", "C002882",
        "C003255", "C003256", "C003260", "C003261",
        "C002887", "C002891", "C002892", "C002900",
        "C002902", "C002913", "C002915", "C002928",
        "C002920", "C002921", "C002924",
        "C003283", "C003296", "C003298", "C003299", "C003300", "C003301", "C003303",
        "C003011", "C003012", "C003020", "C003025", "C003026",
        "C003032",
        "C003051", "C003058", "C003059",
        "C003099", "C003101", "C003103",
    }
)


def _all_gate_b_sources() -> list[str]:
    seen: list[str] = []
    for rule in WAVE2B_BATCH_RULES:
        for cid in rule.get("gate_b_sources", []):
            if cid not in seen:
                seen.append(cid)
    return seen


WAVE2B_BATCH_RULES: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- 3.3.1
    {
        "rule_id": "3.3.1.(1).wound_care_saglik_kurulu_must_bill",
        "sut_section": "3.3.1",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002839"],
        "condition": {"material_name_any": ["yara bakim", "yara bakım"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Yara bakım ürünleri — sağlık kurulu raporuna istinaden "
                "Kurumca karşılanır (§3.3.1(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.listede_yer_almasi_zorunlu_regulatory",
        "sut_section": "3.3.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002850"],
        "condition": {"material_name_any": ["yara bakim", "yara bakım"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Yara bakım ürününün Kurum listesinde/ekinde yer alması "
                "zorunludur (§3.3.1)."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(6).ayakta_yara_recete_branş_regulatory",
        "sut_section": "3.3.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002853"],
        "condition": {"material_name_any": ["yara bakim", "yara bakım"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Ayakta tedavi yara bakım ürünleri — sağlık kurulu raporuna "
                "dayanılarak genel cerrahi / ortopedi ve travmatoloji / plastik "
                "cerrahi / geriatri / enfeksiyon / deri uzman hekimlerinden "
                "biri tarafından reçete edilmelidir (§3.3.1(6))."
            ),
        },
    },
    {
        "rule_id": "3.3.1.(8).hydrocolloid_kopuk_fiber_must_bill",
        "sut_section": "3.3.1",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002855"],
        "condition": {
            "material_name_any": [
                "hydrocolloid",
                "hidrokolloid",
                "kopuk",
                "köpük",
                "fiber",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ayakta tedavide tedavi edici etkisini sadece hydrocolloid, "
                "köpük ve fiber içermesinden gösteren yara bakım ürünleri — "
                "Kurumca karşılanır (§3.3.1(8))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.10
    {
        "rule_id": "3.3.10.a.sakropelvik_konsey_must_bill",
        "sut_section": "3.3.10",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003115"],
        "condition": {"material_name_any": ["sakropelvik", "sakro-pelvik"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Eğitim kliniği olan 3. basamak resmi sunucularda genel "
                "cerrahi, gastroenteroloji, nöroloji ve psikiyatri "
                "kliniklerince 4 branşlı sağlık kurulu raporuna istinaden "
                "bedeli Kurumca karşılanır (§3.3.10 a)."
            ),
        },
    },
    {
        "rule_id": "3.3.10.c.anal_tetkik_rapor_eki_regulatory",
        "sut_section": "3.3.10",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003123"],
        "condition": {"material_name_any": ["sakropelvik", "sakro-pelvik"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Anal manometre, anal EMG, endoanal ultrason vb. tetkik "
                "sonuçlarının sağlık kurulu rapor ekinde yer alması "
                "gerekmektedir (§3.3.10 ç)."
            ),
        },
    },
    {
        "rule_id": "3.3.10.a.idyopatik_asiri_aktif_mesane_konsey_must_bill",
        "sut_section": "3.3.10",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003127"],
        "condition": {
            "material_name_any": ["asiri aktif mesane", "aşırı aktif mesane"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Eğitim kliniği olan 3. basamak resmi sunucularda üroloji, "
                "nöroloji ve psikiyatri kliniklerince 3 branşlı sağlık kurulu "
                "raporuna istinaden bedeli Kurumca karşılanır (§3.3.10 a)."
            ),
        },
    },
    {
        "rule_id": "3.3.10.(2).refraktor_aktif_mesane_regulatory",
        "sut_section": "3.3.10",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003140"],
        "condition": {
            "material_name_any": ["asiri aktif mesane", "aşırı aktif mesane"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Refraktör idyopatik aşırı aktif mesane — antimuskarinik ve "
                "intradetrüsör botulinum toksin tedavisine cevap vermeyen ve "
                "en az 2 yıldır izlemde olan hastalarda uygulanabilir "
                "(§3.3.10(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.10.(3).agrilı_mesane_sendromu_regulatory",
        "sut_section": "3.3.10",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003141"],
        "condition": {
            "material_name_any": [
                "agrilı mesane",
                "ağrılı mesane",
                "interstisyel sistit",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ağrılı mesane sendromu (interstisyel sistit) — tanıdan en az "
                "2 yıl geçmiş ve tüm oral/intravezikal tedavilere cevap "
                "vermeyen hastalara uygulanabilir (§3.3.10(3))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.11
    {
        "rule_id": "3.3.11.(1).greft_membran_sunucu_temin_regulatory",
        "sut_section": "3.3.11",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003143"],
        "condition": {
            "material_name_any": ["greft", "membran", "membran vb."]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Lokal anestezi altında cerrahi tedavilerde kullanılan greft, "
                "membran vb. iyileştirici malzemeler — sağlık hizmeti sunucusu "
                "tarafından temin edilmek zorundadır; hasta aldırılırsa fatura "
                "hastaya ödenip sunucudan mahsup edilir (§3.3.11(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.11.(2).greft_membran_sut_3_2_1_must_bill",
        "sut_section": "3.3.11",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003144"],
        "condition": {
            "material_name_any": ["greft", "membran", "membran vb."]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Bu kapsamdaki tıbbi malzeme bedelleri SUT 3.2.1.A ve 3.2.1.B "
                "doğrultusunda Kurumca karşılanır (§3.3.11(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.11.(3).dis_hekimi_saglik_kurulu_must_bill",
        "sut_section": "3.3.11",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003145"],
        "condition": {"material_name_any": ["greft", "membran"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Greft ve membran bedelleri — en az 1 periodontoloji/ağız diş "
                "çene cerrahisi uzmanı yer alan 3 diş hekimi imzalı sağlık "
                "kurulu raporuna ve ekli radyograflara istinaden Kurumca "
                "karşılanır (§3.3.11(3))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.2
    {
        "rule_id": "3.3.2.(1).kan_sekeri_olcum_cubugu_must_bill",
        "sut_section": "3.3.2",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002873"],
        "condition": {
            "material_name_any": [
                "kan sekeri olcum cubugu",
                "kan şekeri ölçüm çubuğu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Diyabet/hipoglisemi/gestasyonel diyabet veya oral "
                "antidiyabetik kullanan hastaların kan şekeri ölçüm çubuğu "
                "bedelleri — belirlenen esaslar doğrultusunda Kurumca "
                "karşılanır (§3.3.2(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.2.a.diyabet_uzman_raporu_regulatory",
        "sut_section": "3.3.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002874"],
        "condition": {
            "material_name_any": [
                "kan sekeri olcum cubugu",
                "kan şekeri ölçüm çubuğu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Diyabetli hastalar için aile hekimi / endokrinoloji ve "
                "metabolizma / iç hastalıkları / çocuk sağlığı uzman "
                "hekimlerinden biri tarafından uzman hekim raporu düzenlenmesi "
                "gerekmektedir (§3.3.2 a)."
            ),
        },
    },
    {
        "rule_id": "3.3.2.b.kan_sekeri_cihaz_yenileme_no_pay",
        "sut_section": "3.3.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002875"],
        "condition": {"glucose_meter_early_renewal": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kan şekeri ölçüm cihazı yenilenme süresi 2 yıldır; bu süreden "
                "önce temin edilen cihaz bedeli Kurumca ödenmez (§3.3.2 b)."
            ),
        },
    },
    {
        "rule_id": "3.3.2.kan_sekeri_cubugu_recete_must_bill",
        "sut_section": "3.3.2",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002881"],
        "condition": {
            "material_name_any": [
                "kan sekeri olcum cubugu",
                "kan şekeri ölçüm çubuğu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kan şekeri ölçüm çubukları — reçete edilmesi halinde bedeli "
                "Kurumca karşılanır (§3.3.2)."
            ),
        },
    },
    {
        "rule_id": "3.3.2.c.fatura_ekleri_regulatory",
        "sut_section": "3.3.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002882"],
        "condition": {
            "material_name_any": [
                "kan sekeri olcum cubugu",
                "kan şekeri ölçüm çubuğu",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Kan şekeri ölçüm çubuğu faturalarına sağlık raporu fotokopisi "
                "(e-rapor hariç) ile reçete asılları (e-reçete hariç) "
                "eklenecektir (§3.3.2 ç)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.27
    {
        "rule_id": "3.3.27.(1).kanama_durdurma_ek3a_must_bill",
        "sut_section": "3.3.27",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003255"],
        "condition": {"material_name_any": ["kanama durdurma"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "EK-3/A listesindeki kanama durdurmada kullanılan tıbbi "
                "malzemeler — geri ödeme kriterlerine uygun olmak şartıyla "
                "Kurumca karşılanır (§3.3.27(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.27.(2).emilemeyen_kanama_acil_yat_must_bill",
        "sut_section": "3.3.27",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003256"],
        "condition": {"material_name_any": ["kanama durdurma"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Emilemeyen kanama durdurma malzemeleri — acil servis/yatarak "
                "tedavide epikrizde endikasyon belirtilmesi şartıyla en fazla "
                "2 adet Kurumca karşılanır (§3.3.27(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.27.c.travma_acik_kanamali_damar_regulatory",
        "sut_section": "3.3.27",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003260"],
        "condition": {"material_name_any": ["kanama durdurma"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Girişimsel/iatrojenik işlemler hariç; boyun, aksiller ve "
                "inguinal bölgenin direkt bası ile durdurulamayan travmaya "
                "bağlı açık kanamalı damar yaralanmaları — endikasyon "
                "kriterlerindendir (§3.3.27 ç)."
            ),
        },
    },
    {
        "rule_id": "3.3.27.(3).emilebilen_kanama_yat_must_bill",
        "sut_section": "3.3.27",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003261"],
        "condition": {"material_name_any": ["kanama durdurma"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Emilebilen kanama durdurma malzemeleri — yatarak tedavide "
                "epikrizde endikasyon ve kullanılan malzeme sayısının "
                "belirtilmesi şartıyla Kurumca karşılanır (§3.3.27(3))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.3 / A
    {
        "rule_id": "3.3.3.(1).gozluk_cam_cerceve_ek3d_must_bill",
        "sut_section": "3.3.3",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002887"],
        "condition": {
            "material_name_any": ["gözlük", "gozluk", "görmeye yardimci"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Gözlük cam/çerçeve ve nitelikli görmeye yardımcı malzeme "
                "bedelleri — göz sağlığı uzman hekimi sağlık kurulu raporuna "
                "istinaden EK-3/D fiyatlarını aşmamak üzere Kurumca karşılanır "
                "(§3.3.3(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.A.(2).optisyenlik_muessesesi_temin_regulatory",
        "sut_section": "3.3.3.A",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002891"],
        "condition": {
            "material_name_any": ["gözlük", "gozluk", "görmeye yardimci"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Gözlük cam ve çerçeveleri — 5193 sayılı Kanuna uygun, Kurumla "
                "sözleşmeli optisyenlik müesseselerinden temin edilebilir "
                "(§3.3.3.A(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.A.(3).cam_cerceve_fatura_must_bill",
        "sut_section": "3.3.3.A",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002892"],
        "condition": {
            "material_name_any": ["gözlük", "gozluk", "cam bedeli"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Cam bedelleri — çerçeve bedeli ile birlikte sözleşmeli "
                "optisyenlik müesseseleri tarafından Kuruma fatura edilebilir "
                "(§3.3.3.A(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.A.(7).uzak_yakin_cok_odakli_must_bill",
        "sut_section": "3.3.3.A",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002900"],
        "condition": {
            "material_name_any": ["gözlük", "gozluk", "çok odaklı", "cok odakli"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Aynı reçetede uzak ve yakın iki gözlük reçete edilirse, hasta "
                "tercihiyle yeni reçete olmadan çok odaklı gözlük bedeli "
                "Kurumca karşılanır; 18 yaş ve altında hekim reçetesi "
                "zorunludur (§3.3.3.A(7))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.3 / B-C-D
    {
        "rule_id": "3.3.3.B.(1).teleskopik_gorme_3_basamak_must_bill",
        "sut_section": "3.3.3.B",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002902"],
        "condition": {
            "material_name_any": ["teleskopik", "teleskop"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Teleskopik görmeye yardımcı malzeme — iyi gören gözde "
                "düzeltmiş uzak görme keskinliği 3/10 ve altı hastalarda 3. "
                "basamak sağlık kurulu raporuna istinaden bedeli Kurumca "
                "karşılanır (§3.3.3.B(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.contact_lens_ek3d_must_bill",
        "sut_section": "3.3.3.C",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002913"],
        "condition": {
            "material_name_any": ["kontakt lens", "contact lens"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kontakt lens — 3. basamak göz sağlığı uzmanı içeren sağlık "
                "kurulu raporunda çap/derinlik/diyoptri/nitelik belirtilmesi "
                "ve sözleşmeli optisyenlikten temin şartıyla EK-3/D bedeli "
                "üzerinden Kurumca karşılanır (§3.3.3.C)."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.(3).konjenital_katarakt_cocuk_must_bill",
        "sut_section": "3.3.3.C",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002915"],
        "condition": {
            "material_name_any": ["kontakt lens", "contact lens"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Konjenital katarakt nedeniyle opere olmuş 6 yaşından küçük "
                "çocuklarda kontakt lens — 6 ayda bir yenilenmesi halinde "
                "sağlık kurulu raporuna istinaden Kurumca karşılanır "
                "(§3.3.3.C(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.D.(1).kalici_cift_gorme_prizma_must_bill",
        "sut_section": "3.3.3.D",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C002928"],
        "condition": {
            "material_name_any": ["prizma", "prizmatik", "çift görme"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Kalıcı çift görme (6 ay ve üzeri) paralitik/restriktrif "
                "şaşılıkta — 3 göz sağlığı uzmanı içeren sağlık kurulu "
                "raporuyla bedeli Kurumca karşılanır (§3.3.3.D(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.3 / Ç
    {
        "rule_id": "3.3.3.C.(1).e_recete_imza_regulatory",
        "sut_section": "3.3.3.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002920"],
        "condition": {
            "material_name_any": ["e-recete", "e-reçete", "elektronik imza"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "E-reçeteler Kurumca belirlenen yöntem ve standartlarla "
                "(elektronik imza, şifre) imzalanma şarttır (§3.3.3.Ç(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.(2).medula_sgk_sifresi_regulatory",
        "sut_section": "3.3.3.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002921"],
        "condition": {
            "material_name_any": ["e-recete", "e-reçete", "manuel reçete"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Reçeteler MEDULA sisteminde SGK Hekim Şifresi ile "
                "düzenlenecektir; istisnalar hariç manuel reçete bedelleri "
                "karşılanmayacaktır (§3.3.3.Ç(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.3.C.b.resmi_sunucu_e_recete_regulatory",
        "sut_section": "3.3.3.Ç",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002924"],
        "condition": {
            "material_name_any": ["e-recete", "e-reçete"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Resmi sunuculardan (kamu tabiplik, belediye poliklinik, 1. "
                "basamak, mediko-sosyal) düzenlenen reçeteler; MEDULA-Hastane "
                "altyapısı kurulduğunda e-reçeteye geçiş zorunludur "
                "(§3.3.3.Ç b)."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.32
    {
        "rule_id": "3.3.32.(1).dijital_isitme_cihazi_must_bill",
        "sut_section": "3.3.32",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003283"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Dijital programlanabilir işitme cihazları (kulak arkası / "
                "kulak içi / kanal içi) — Kurumca bedeli karşılanır "
                "(§3.3.32(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.32.(4).saf_ses_odyometri_icerik_regulatory",
        "sut_section": "3.3.32",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003296"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Saf ses odyometrisi 500-1000-2000-4000 Hz hava ve kemik yolu "
                "eşikleri ile konuşmayı ayırt etme skorunu içermelidir; 8 yaş "
                "üstünde test yapılamıyorsa gerekçesi belirtilmelidir "
                "(§3.3.32(4))."
            ),
        },
    },
    {
        "rule_id": "3.3.32.a.cocuk_kbb_3_basamak_rapor_regulatory",
        "sut_section": "3.3.32",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003298"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "0-18 yaş çocuklarda işitme cihazı için en az 1 KBB uzmanı yer "
                "alan 3. basamak resmi sunucu sağlık kurulu raporu düzenlenmesi "
                "gerekmektedir (§3.3.32 a)."
            ),
        },
    },
    {
        "rule_id": "3.3.32.b.yetiskin_kbb_rapor_regulatory",
        "sut_section": "3.3.32",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003299"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "18 yaş üzeri hastalarda işitme cihazı için en az 1 KBB uzmanı "
                "yer alan resmi sunucu sağlık kurulu raporu düzenlenmesi "
                "gerekmektedir (§3.3.32 b)."
            ),
        },
    },
    {
        "rule_id": "3.3.32.c.kalici_isitme_kaybi_kriter_regulatory",
        "sut_section": "3.3.32",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003300"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Sağlık kurulu raporlarında kalıcı işitme kaybı olduğu ve "
                "odyolojik kriterlerin sağlandığının belirtilmesi gerekmektedir "
                "(§3.3.32 c)."
            ),
        },
    },
    {
        "rule_id": "3.3.32.c.odyolojik_esik_kriter_regulatory",
        "sut_section": "3.3.32",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003301"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "500-1000-2000-4000 Hz hava yolu saf ses ortalaması 26 dB ve "
                "üzeri (ABR'de 30 dB ve üzeri) olmalıdır (§3.3.32 ç)."
            ),
        },
    },
    {
        "rule_id": "3.3.32.(7).cocuk_isitme_tutar_artis_must_bill",
        "sut_section": "3.3.32",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003303"],
        "condition": {
            "material_name_any": ["işitme cihazı", "isitme cihazi"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "18 yaş altı çocuklar için belirlenen işitme cihazı tutarı; "
                "0-4 yaş %80, 5-12 yaş %60, 13-18 yaş %50 oranında artırılarak "
                "Kurumca karşılanır (§3.3.32(7))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.6.A-1
    {
        "rule_id": "3.3.6.A-1.(2).nimv_uyku_merkezi_rapor_regulatory",
        "sut_section": "3.3.6.A-1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003011"],
        "condition": {"material_name_any": ["nimv", "nİmv", "cpap", "bpap"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "NİMV cihazı sağlık kurulu raporları — uyku merkezi bulunan "
                "sunucu sağlık kurullarınca; rapor, titrasyon uyku testini "
                "yapan sunucu tarafından düzenlenmelidir (§3.3.6.A-1(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.(3).nimv_uc_uzman_recete_regulatory",
        "sut_section": "3.3.6.A-1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003012"],
        "condition": {"material_name_any": ["nimv", "nİmv", "cpap", "bpap"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "NİMV sağlık kurulu raporunda göğüs hastalıkları/psikiyatri/"
                "nöroloji uzmanlarından 3 hekim (çocuk hastada çocuk göğüs/"
                "çocuk nöroloji en az biri) yer alıp reçete etmesi zorunludur "
                "(§3.3.6.A-1(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.nimv_rapor_bilgi_icerik_regulatory",
        "sut_section": "3.3.6.A-1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003020"],
        "condition": {"material_name_any": ["nimv", "nİmv", "cpap", "bpap"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "NİMV sağlık kurulu raporunda zorunlu bilgilerin (cihaz "
                "parametreleri, tanı, kullanım süresi vb.) yer alması "
                "gerekmektedir (§3.3.6.A-1)."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.(7).nimv_kronik_oksijen_must_bill",
        "sut_section": "3.3.6.A-1",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003025"],
        "condition": {
            "material_name_any": ["oksijen konsantratör", "oksijen cihaz"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "NİMV kullanımında oksijen saturasyonu %88 üzerine "
                "çıkarılamadığı raporda belirtilirse, kronik oksijen tedavisi "
                "cihaz bedelleri Kurumca karşılanır (§3.3.6.A-1(7))."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.(8).nimv_dusuk_kullanim_sevk_regulatory",
        "sut_section": "3.3.6.A-1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003026"],
        "condition": {"material_name_any": ["nimv", "nİmv", "cpap", "bpap"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "NİMV cihazının yıllık minimum 1.200 saatin altında "
                "kullanıldığının saptanması halinde kullanım saati içeren sevk "
                "evrakıyla hastanın sevk edilip tedavi devamlılığına ilişkin "
                "sağlık kurulu raporu düzenlenmesi gerekmektedir "
                "(§3.3.6.A-1(8))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.6.A-2
    {
        "rule_id": "3.3.6.A-2.(1).bpap_kronik_solunum_regulatory",
        "sut_section": "3.3.6.A-2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003032"],
        "condition": {"material_name_any": ["bpap-s", "bpap s/t", "bpap avaps"]},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Kronik solunum yetmezliğinde yalnızca BPAP-S, BPAP S/T ve BPAP "
                "S/T AVAPS bedelleri Kurumca karşılanır; raporda göğüs "
                "hastalıkları/nöroloji/anestezi-reanimasyon/yoğun bakım/çocuk "
                "göğüs hekimlerinden en az biri yer alıp reçete etmelidir "
                "(§3.3.6.A-2(1))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.6.B
    {
        "rule_id": "3.3.6.B.evde_uzun_sureli_oksijen_must_bill",
        "sut_section": "3.3.6.B",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003051"],
        "condition": {
            "material_name_any": ["oksijen konsantratör", "uzun sureli oksijen"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Evde uzun süreli oksijen tedavisi cihazı bedelleri — Kurumca "
                "karşılanır (§3.3.6.B)."
            ),
        },
    },
    {
        "rule_id": "3.3.6.B.(6).tasinabilir_oksijen_efor_must_bill",
        "sut_section": "3.3.6.B",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003058"],
        "condition": {
            "material_name_any": ["taşınabilir oksijen", "tasinabilir oksijen"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Taşınabilir oksijen komponentli cihaz — istirahatte PaO2 > 55 / "
                "SaO2 > %88 iken eforla desatüre olan mobilize/aktif/öğrenci "
                "hastalarda istirahat ve efor kan gazları raporda belgelendirilirse "
                "bedeli Kurumca karşılanır (§3.3.6.B(6))."
            ),
        },
    },
    {
        "rule_id": "3.3.6.B.(7).oksijen_konsantrator_tup_must_bill",
        "sut_section": "3.3.6.B",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003059"],
        "condition": {
            "material_name_any": ["oksijen tüpü", "oksijen tupu"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Oksijen konsantratörü verilen kişilere, raporda belirtilmek "
                "koşuluyla oksijen tüpü önerilmesi halinde bedeli Kurumca "
                "karşılanır (§3.3.6.B(7))."
            ),
        },
    },
    # ---------------------------------------------------------------- 3.3.9
    {
        "rule_id": "3.3.9.(1).medikal_çorap_saglik_kurulu_must_bill",
        "sut_section": "3.3.9",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003099"],
        "condition": {
            "material_name_any": ["medikal corap", "medikal çorap", "kompresyon"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Medikal çorap — genel cerrahi/dermatoloji/plastik cerrahi/kalp "
                "damar cerrahi/fizik tedavi uzmanlarından birinin yer aldığı "
                "sağlık kurulu raporuna istinaden tüm hekimlerce reçete "
                "edilirse tüm evrelerde bedeli Kurumca karşılanır (§3.3.9(1))."
            ),
        },
    },
    {
        "rule_id": "3.3.9.(3).standart_beden_medikal_corap_must_bill",
        "sut_section": "3.3.9",
        "deontic": "MUST_BILL",
        "gate_b_sources": ["C003101"],
        "condition": {
            "material_name_any": ["medikal corap", "medikal çorap", "kompresyon"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Medikal çorap — standart bedenler üzerinden bedeli Kurumca "
                "karşılanır (§3.3.9(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.9.(5).medikal_corap_yilda_iki_kez_regulatory",
        "sut_section": "3.3.9",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C003103"],
        "condition": {
            "material_name_any": ["medikal corap", "medikal çorap", "kompresyon"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Medikal çorap — ilgili hekimce uygun görülmesi halinde 6 ay "
                "arayla yılda en fazla 2 kez reçete edilebilir (§3.3.9(5))."
            ),
        },
    },
]
