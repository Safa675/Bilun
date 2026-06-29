#!/usr/bin/env python3
"""Wave REM_4_2_eye_mid_b — §4.2.9 (renal/mineral-bone), §4.2.24
(respiratory: triple-combo/nebul/rinit), §4.2.49 (SMA: nusinersen/risdiplam).

34 in-force deontic clauses encoded from
`tasks/encode_waves/REM_4_2_eye_mid_b.csv` (second half of the §4.2
eye/anti-VEGF/neuro/mid wave).

Rule shape follows the established `drug_indication_rheum_biologics_batch_rules`
pattern: flat condition keys (drug_names, icd10_codes/ranges, report_required,
report_duration_months, report_specialties, prescriber_specialties, pay) plus a
nested `action` block (message_tr + enforcement) for NO_PAY/PROHIBITED
exclusions.  Bare coverage statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.24.B  —  respiratory: COPD triple-combo maintenance / nebul forms
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C006180 — KOAH idame üçlü kombinasyon: ≥3 ay İKS+LABA veya LABA+LAMA yetersiz + atak/dispne
    {
        "rule_id": "4.2.24.B.resp.copd_triple_combo_maintenance",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006180"],
        "drug_names": ["mono laba", "mono lama", "mono iks", "laba/lama/iks kombinasyonu"],
        "icd10_codes": ["J44.0", "J44.1", "J44.9"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "erişkin orta-ağır KOAH idame: ≥3 ay İKS+LABA veya LABA+LAMA yetersiz + sık atak (yılda ≥2 atak veya ≥1 yatarak) + dispne (mMRC≥2 veya CAT≥10); durum raporda belirtilmeli",
            "message_tr": "Mono LABA/LAMA/İKS veya sabit doz LABA/LAMA/İKS kombinasyonlarıyla yapılacak üçlü kombinasyon tedavilerinde; en az 3 ay süreyle İKS ve LABA veya LABA ve LAMA ile tedavi edildiği halde yeterli yanıt alınamayan, sık atak geçiren (yılda 2 ve üzeri atak veya 1 ve üzeri yatarak tedavi) ve dispnesi olan (mMRC 2 ve üzeri veya CAT skoru 10 ve üzeri) orta-ağır KOAH'lı erişkin hastaların idame tedavisinde kullanılmaları ve bu durumların uzman hekim raporunda belirtilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006182 — nebül solunum ilaçları: ilk kutu raporsuz, devam uzman raporuyla; kombine nebül yok
    {
        "rule_id": "4.2.24.B.resp.nebul_respiratory_drugs_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006182"],
        "drug_names": ["nebül formu solunum sistemi ilaçları"],
        "icd10_codes": ["J44.0", "J44.1", "J44.9", "J45"],
        "report_required": True,
        "report_specialties": [
            "göğüs hastalıkları", "immünoloji", "immünoloji ve alerji",
            "alerji", "çocuk sağlığı ve hastalıkları",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nebül formları (arformoterol hariç) Bakanlık onaylı endikasyonda tüm hekimlerce raporsuz en fazla 1 kutu; devamı göğüs/immünoloji(-alerji)/alerji/çocuk uzman raporuyla diğer hekimlerce; aynı gruptan iki nebül kombine kullanılamaz",
            "message_tr": "Nebül formundaki solunum sistemi ilaçları (arformoterol hariç) Sağlık Bakanlığınca onaylı endikasyonlarında kullanılması koşulu ile tüm hekimlerce raporsuz olarak en fazla bir kutu reçete edilmesi halinde, göğüs hastalıkları, immünoloji, immünoloji ve alerji, alerji veya çocuk sağlığı ve hastalıkları uzman hekimlerin biri tarafından düzenlenen uzman hekim raporu mevcut ise tedavinin devamı için diğer hekimlerce de reçete edilmesi halinde bedelleri Kurumca karşılanır; aynı grupta yer alan etkin maddeleri içeren iki ayrı nebül formundaki ilaçlar kombine olarak kullanılamaz (§4.2.24.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.24.C  —  respiratory: allergic rhinitis fixed-dose combos
    # -----------------------------------------------------------------

    # C006188 — alerjik rinit: azelastin+flutikazon sabit doz kombinasyonu ≥12 yaş
    {
        "rule_id": "4.2.24.C.resp.rhinitis_azelastine_fluticasone_combo",
        "sut_section": "4.2.24.C",
        "gate_b_sources": ["C006188"],
        "drug_names": ["azelastin hidroklorür", "flutikazon propiyonat"],
        "icd10_codes": ["J30.1", "J30.2", "J30.3"],
        "prescriber_specialties": [
            "alerji ve immünoloji", "kulak burun boğaz", "iç hastalıkları",
            "çocuk sağlığı ve hastalıkları", "göğüs hastalıkları",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "mevsimsel/pereniyal alerjik rinitte intranazal antihistaminik veya glukokortikoid monoterapisi yetersizse; azelastin+flutikazon sabit doz kombinasyonu ≥12 yaşta belirlenen uzmanlarca reçete",
            "message_tr": "Mevsimsel ve pereniyal alerjik rinit semptomlarının giderilmesinde intranazal antihistaminik veya glukokortikoid monoterapilerinin yeterli olmadığı durumlarda; azelastin hidroklorür ve flutikazon propiyonat etken maddelerini içeren sabit doz kombine preparatları 12 yaş ve üzeri hastalarda alerji ve immünoloji, kulak burun boğaz, iç hastalıkları, çocuk sağlığı ve hastalıkları, göğüs hastalıkları uzman hekimlerince reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.24.C).",
        },
    },

    # C006190 — alerjik rinit: mono intranazal kortikosteroid + mono intranazal antihistaminik birlikte
    {
        "rule_id": "4.2.24.C.resp.rhinitis_intranazal_steroid_antihistamine_couse",
        "sut_section": "4.2.24.C",
        "gate_b_sources": ["C006190"],
        "drug_names": ["mono intranazal kortikosteroid", "mono intranazal antihistaminik"],
        "icd10_codes": ["J30.1", "J30.2", "J30.3"],
        "prescriber_specialties": [
            "alerji ve immünoloji", "kulak burun boğaz", "iç hastalıkları",
            "çocuk sağlığı ve hastalıkları", "göğüs hastalıkları",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "mevsimsel/pereniyal alerjik rinitte monoterapi yetersizse; mono intranazal kortikosteroid ve mono intranazal antihistaminik belirlenen uzmanlarca birlikte reçete",
            "message_tr": "Mevsimsel ve pereniyal alerjik rinit semptomlarının giderilmesinde intranazal antihistaminik veya glukokortikoid monoterapilerinin yeterli olmadığı durumlarda; mono intranazal kortikosteroid ve mono intranazal antihistaminik ilaçların birlikte kullanımı alerji ve immünoloji, kulak burun boğaz, iç hastalıkları, çocuk sağlığı ve hastalıkları, göğüs hastalıkları uzman hekimlerince birlikte reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.24.C).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.49  —  SMA: SMN2 copy-number eligibility (nusinersen/risdiplam)
    # -----------------------------------------------------------------

    # C007010 — SMN2 kopya 2 ve 3 olan bebeklerde ilaç bedeli ödenir
    {
        "rule_id": "4.2.49.neuro.sma_smn2_copy2_3_infant_coverage",
        "sut_section": "4.2.49",
        "gate_b_sources": ["C007010"],
        "drug_names": ["nusinersen", "nusinersen sodium", "risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "SMN2 kopya sayısı 2 ve 3 olan bebeklerde ilaç bedeli Kurumca karşılanır",
            "message_tr": "SMN2 kopya sayısı 2 ve 3 olan bebeklerde ilaç bedeli Kurumca karşılanır (§4.2.49).",
        },
    },

    # C007011 — SMN2 kopya 4: klinik takip, semptomatik olana ödenir
    {
        "rule_id": "4.2.49.neuro.sma_smn2_copy4_symptomatic_coverage",
        "sut_section": "4.2.49",
        "gate_b_sources": ["C007011"],
        "drug_names": ["nusinersen", "nusinersen sodium", "risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "SMN2 kopya sayısı 4 olduğunda klinik takiple tedavi kararı; takipte semptomatik olan hastalara ilaç bedeli ödenir",
            "message_tr": "SMN2 kopya sayısı 4 olduğunda klinik takiple tedavi kararı verilir, takip sırasında semptomatik olan hastalarda ilacın bedeli Kurumca karşılanır (§4.2.49).",
        },
    },

    # C007013 — nusinersen: BOS drenaj şantı/kateteri olmamalı (mandatory)
    {
        "rule_id": "4.2.49.neuro.nusinersen_no_csf_shunt_catheter",
        "sut_section": "4.2.49",
        "gate_b_sources": ["C007013"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: nusinersen tedavisi için hastalarda BOS drenajı için yerleştirilmiş bir şant veya BOS kateteri bulunmamalıdır",
            "message_tr": "Nusinersen tedavisi için hastalarda BOS drenajı için yerleştirilmiş bir şant veya BOS kateteri bulunmaması gerekmektedir (§4.2.49).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.49.A  —  SMA (nusinersen sodium) eligibility + monitoring criteria
    # -----------------------------------------------------------------

    # C007018 — nusinersen sodium: tüm kriterler sağlanırsa ödenir (header)
    {
        "rule_id": "4.2.49.A.neuro.nusinersen_all_criteria_coverage_a",
        "sut_section": "4.2.49.A",
        "gate_b_sources": ["C007018"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nusinersen sodium: aşağıdaki kriterlerin tamamı sağlanırsa bedeli ödenir",
            "message_tr": "Hastalarda aşağıda yer alan kriterlerin tamamının sağlanması halinde bedeli Kurumca karşılanır (§4.2.49.A).",
        },
    },

    # C007021 — nusinersen sodium: BOS drenaj şantı/kateteri olmamalı (mandatory)
    {
        "rule_id": "4.2.49.A.neuro.nusinersen_no_csf_shunt_catheter_a",
        "sut_section": "4.2.49.A",
        "gate_b_sources": ["C007021"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: BOS drenajı için yerleştirilmiş bir şant veya BOS kateteri bulunmamalıdır",
            "message_tr": "BOS drenajı için yerleştirilmiş bir şant veya BOS kateteri bulunmaması gerekmektedir (§4.2.49.A).",
        },
    },

    # C007024 — nusinersen sodium: tedavi süresince multidisipliner izlem + değerlendirme raporda (mandatory)
    {
        "rule_id": "4.2.49.A.neuro.nusinersen_multidisciplinary_monitoring_a",
        "sut_section": "4.2.49.A",
        "gate_b_sources": ["C007024"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi; yaşa/hastalığa özel standart değerlendirmeler yapılarak raporda belirtilmelidir",
            "message_tr": "Tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi, yaşa uygun ve hastalığa özel tanımlanmış ölçütlerle standart değerlendirmelerin yapılması ve sağlık kurulu raporunda belirtilmesi gereklidir (§4.2.49.A).",
        },
    },

    # C007026 — nusinersen sodium: tüm kriterler sağlanırsa ödenir (header, dup variant)
    {
        "rule_id": "4.2.49.A.neuro.nusinersen_all_criteria_coverage_b",
        "sut_section": "4.2.49.A",
        "gate_b_sources": ["C007026"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nusinersen sodium: aşağıdaki kriterlerin tamamı sağlanırsa bedeli ödenir",
            "message_tr": "Hastalarda aşağıda yer alan kriterlerin tamamının sağlanması halinde bedeli Kurumca karşılanır (§4.2.49.A).",
        },
    },

    # C007029 — nusinersen sodium: multidisipliner izlem + değerlendirme raporda (mandatory, dup variant)
    {
        "rule_id": "4.2.49.A.neuro.nusinersen_multidisciplinary_monitoring_b",
        "sut_section": "4.2.49.A",
        "gate_b_sources": ["C007029"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi; yaşa/hastalığa özel standart değerlendirmeler yapılarak raporda belirtilmelidir",
            "message_tr": "Tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi, yaşa uygun ve hastalığa özel tanımlanmış ölçütlerle standart değerlendirmelerin yapılması ve sağlık kurulu raporunda belirtilmesi gereklidir (§4.2.49.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.49.B  —  SMA (risdiplam) eligibility + monitoring criteria
    # -----------------------------------------------------------------

    # C007032 — risdiplam: tüm kriterler sağlanırsa ödenir (header)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_all_criteria_coverage",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007032"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "risdiplam: aşağıdaki kriterlerin tamamı sağlanırsa bedeli ödenir",
            "message_tr": "Hastalarda aşağıda yer alan kriterlerin tamamının sağlanması halinde bedeli Kurumca karşılanır (§4.2.49.B).",
        },
    },

    # C007035 — risdiplam: implante BOS drenaj şantı/kateteri olmamalı (mandatory)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_no_implanted_csf_shunt",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007035"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: BOS drenajı için implante edilmiş bir şant veya implante edilmiş bir BOS kateteri bulunmamalıdır",
            "message_tr": "BOS drenajı için implante edilmiş bir şant veya implante edilmiş bir BOS kateteri bulunmaması gerekmektedir (§4.2.49.B).",
        },
    },

    # C007038 — risdiplam: lomber ponksiyona engel olmadığı raporda (mandatory)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_no_lumbar_puncture_contraindication",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007038"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: lomber ponksiyon uygulanmasına engel bir durum olmadığı sağlık kurulu raporunda belirtilmiş olmalıdır",
            "message_tr": "Lomber ponksiyon uygulanmasına engel bir durum olmadığının sağlık kurulu raporunda belirtilmiş olması gerekmektedir (§4.2.49.B).",
        },
    },

    # C007040 — risdiplam: multidisipliner izlem + değerlendirme raporda (mandatory)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_multidisciplinary_monitoring_a",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007040"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi; yaşa/hastalığa özel standart değerlendirmeler yapılarak raporda belirtilmelidir",
            "message_tr": "Tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi, yaşa ve hastalığa özel tanımlanmış ölçütlerle standart değerlendirmelerin yapılması ve sağlık kurulu raporunda belirtilmesi gereklidir (§4.2.49.B).",
        },
    },

    # C007042 — risdiplam: tüm kriterler sağlanırsa ödenir (header, dup variant)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_all_criteria_coverage_b",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007042"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "risdiplam: aşağıdaki kriterlerin tamamı sağlanırsa bedeli ödenir",
            "message_tr": "Hastalarda aşağıda yer alan kriterlerin tamamının sağlanması halinde bedeli Kurumca karşılanır (§4.2.49.B).",
        },
    },

    # C007045 — risdiplam: multidisipliner izlem + değerlendirme raporda (mandatory, dup variant)
    {
        "rule_id": "4.2.49.B.neuro.risdiplam_multidisciplinary_monitoring_b",
        "sut_section": "4.2.49.B",
        "gate_b_sources": ["C007045"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "action": {
            "enforcement": "mandatory: tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi; yaşa/hastalığa özel standart değerlendirmeler yapılarak raporda belirtilmelidir",
            "message_tr": "Tedavi süresince motor, bilişsel, beslenme, solunum, fizik tedavi rehabilitasyon ve ortopedik açıdan izlenmesi, yaşa ve hastalığa özel tanımlanmış ölçütlerle standart değerlendirmelerin yapılması ve sağlık kurulu raporunda belirtilmesi gereklidir (§4.2.49.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.49.C  —  SMA treatment setting / report durations / switching
    # -----------------------------------------------------------------

    # C007047 — nusinersen: üçüncü basamak, çocuk nöroloji/nöroloji; ilk 4 uygulama 3 ay, sonra 4 ay rapor
    {
        "rule_id": "4.2.49.C.neuro.nusinersen_tertiary_setting_report_durations",
        "sut_section": "4.2.49.C",
        "gate_b_sources": ["C007047"],
        "drug_names": ["nusinersen", "nusinersen sodium"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_duration_months": 4,
        "report_specialties": ["çocuk nöroloji", "nöroloji", "ortopedi ve travmatoloji", "beyin ve sinir cerrahisi"],
        "prescriber_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nusinersen: Ulusal Yenidoğan SMA Tarama/SMA Tip-1 çocuk nöroloji raporu; Tip-2/3 en az biri çocuk nöroloji/nöroloji olmak üzere ortopedi veya beyin-sinir cerrahisi; üçüncü basamak, ilk 4 uygulama 3 ay, sonraki 4 ay; her uygulama için çocuk nöroloji/nöroloji reçetesi; koşullar raporda",
            "message_tr": "Nusinersen tedavisi; Ulusal Yenidoğan SMA Tarama Programından gelen hastalar ile SMA Tip-1 hastalarında çocuk nöroloji uzman hekiminin yer aldığı sağlık kurulu raporuna istinaden, SMA Tip-2 ve SMA Tip-3 hastalarında en az birisi çocuk nöroloji/nöroloji uzmanı olmak üzere ortopedi ve travmatoloji veya beyin ve sinir cerrahisi uzman hekiminin yer aldığı sağlık kurulu raporuna istinaden reçetelenir. İlk 4 uygulama için 3 ay süreli, sonraki uygulamalar için 4 ay süreli Kurumca belirlenen üçüncü basamak resmi sağlık hizmeti sunucularında düzenlenen sağlık kurulu raporuna istinaden üçüncü basamakta çocuk nöroloji veya nöroloji uzman hekimi tarafından her bir uygulama için ayrı ayrı reçete edilmesi halinde bedeli Kurumca karşılanır; ilaç kullanımı koşulları raporda belirtilmelidir (§4.2.49.C).",
        },
    },

    # C007048 — risdiplam: üçüncü basamak, çocuk nöroloji/nöroloji; Tip-1 ≤3 ay, Tip-2/3 ≤6 ay; ≤2 aylık doz
    {
        "rule_id": "4.2.49.C.neuro.risdiplam_tertiary_setting_report_durations",
        "sut_section": "4.2.49.C",
        "gate_b_sources": ["C007048"],
        "drug_names": ["risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "prescriber_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "risdiplam: üçüncü basamakta çocuk nöroloji/nöroloji raporu; SMA Tip-1/tarama en fazla 3 ay, Tip-2/3 en fazla 6 ay; reçetede hasta kilosu; koşullar raporda; reçeteler en fazla 2 aylık dozda",
            "message_tr": "Risdiplam tedavisi çocuk nöroloji/nöroloji uzman hekiminin yer aldığı; Ulusal Yenidoğan SMA Tarama Programından gelen hastalar ile SMA Tip-1 hastalarında en fazla 3 ay süreli, SMA Tip-2 ve SMA Tip-3 hastalarında en fazla 6 ay süreli Kurumca belirlenen üçüncü basamak resmi sağlık hizmeti sunucularında düzenlenen sağlık kurulu raporuna istinaden üçüncü basamakta çocuk nöroloji veya nöroloji uzman hekimi tarafından reçete edilmesi halinde bedeli Kurumca karşılanır; reçetelerde hastanın kilosu belirtilmelidir, ilaç kullanımı koşulları raporda belirtilmelidir, reçeteler en fazla 2 aylık dozda olmalıdır (§4.2.49.C).",
        },
    },

    # C007049 — nusinersen sodium + risdiplam: belirli üçüncü basamak multidisipliner merkezde kullanım
    {
        "rule_id": "4.2.49.C.neuro.sma_designated_multidisciplinary_center_coverage",
        "sut_section": "4.2.49.C",
        "gate_b_sources": ["C007049"],
        "drug_names": ["nusinersen", "nusinersen sodium", "risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "report_required": True,
        "report_specialties": ["çocuk nöroloji", "nöroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nusinersen sodium ve risdiplam: tescilli yenidoğan/çocuk yoğun bakım + çocuk nörolojisi uzmanı + beslenme-diyetetik ve fizik tedavi-rehabilitasyon multidisipliner sunulabilen Kurumca belirlenen üçüncü basamakta kullanılırsa ödenir",
            "message_tr": "Nusinersen sodium ve risdiplam etkin maddeli ilaçların; tescili yapılmış yenidoğan ve çocuk yoğun bakım servisi bulunan, bünyesinde çocuk nörolojisi uzmanının da yer aldığı, beslenme ve diyetetik ile fizik tedavi ve rehabilitasyon hizmetlerinin multidisipliner bir yaklaşımla sunulabileceği Kurumca belirlenen üçüncü basamak resmi sağlık hizmeti sunucularında kullanılması halinde bedeli Kurumca karşılanır (§4.2.49.C).",
        },
    },

    # C007051 — SMN2 modifiye tedaviler arasında 1 yıldan kısa geçiş: no-pay (istisnalarıyla)
    {
        "rule_id": "4.2.49.C.neuro.sma_modifying_switch_under_1yr_nopay",
        "sut_section": "4.2.49.C",
        "gate_b_sources": ["C007051"],
        "drug_names": ["nusinersen", "nusinersen sodium", "risdiplam"],
        "icd10_codes": ["G12.0", "G12.1"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: SMN2 modifiye eden tedaviler (nusinersen, risdiplam) arasında 1 yıldan kısa süre ile geçiş; ancak fonksiyonel değerlendirmede bozulma veya belirgin hayatı tehdit eden yan etki olursa yeni raporla ilaç değişimi yapılabilir",
            "message_tr": "SMN2 modifiye eden tedaviler (nusinersen, risdiplam) arasında 1 yıldan kısa süre ile geçiş yapılması halinde bedeli Kurumca karşılanmaz; ancak fonksiyonel değerlendirmelerde bozulma olması veya belirgin hayatı tehdit eden yan etki ortaya çıkması durumunda yeni düzenlenecek sağlık kurulu raporunda belirtilmesi halinde ilaç değişimi yapılabilir (§4.2.49.C).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.A  —  renal: erythropoiesis-stimulating agents / roxadustat
    # -----------------------------------------------------------------

    # C004125 — ESA/darbepoietin ve roksadustat endikasyon dışı: no-pay
    {
        "rule_id": "4.2.9.A.renal.esa_roxadustat_offlabel_nopay",
        "sut_section": "4.2.9.A",
        "gate_b_sources": ["C004125"],
        "drug_names": ["eritropoietin", "darbepoietin", "roksadustat"],
        "icd10_codes": ["D63.1", "N18"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: eritropoietin/darbepoietin kronik böbrek yetmezliği ilişkili anemi ve myelodisplastik sendrom dışındaki endikasyonlarda; roksadustat kronik böbrek yetmezliği ilişkili anemi dışındaki endikasyonlarda karşılanmaz",
            "message_tr": "Eritropoietin ve darbepoietin preparatları kronik böbrek yetmezliği ile ilişkili anemi ve myelodisplastik sendrom dışındaki endikasyonlarda, roksadustat preparatları ise kronik böbrek yetmezliği ile ilişkili anemi dışındaki endikasyonlarda Kurumca karşılanmaz (§4.2.9.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.B  —  renal: phosphate binders (sevelamer/lantanum/aluminium)
    # -----------------------------------------------------------------

    # C004141 — fosfor düşürücü: başlamak için ≥3 ay diğer fosfor düşürücü kullanılmış olmalı (mandatory)
    {
        "rule_id": "4.2.9.B.renal.phosphate_binder_prior_3mo_use_mandatory",
        "sut_section": "4.2.9.B",
        "gate_b_sources": ["C004141"],
        "drug_names": ["sevelamer", "lantanyum karbonat", "alüminyum klorür hidroksit", "fosfor düşürücü ilaçlar"],
        "icd10_codes": ["N18", "E83.3"],
        "report_required": True,
        "report_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "action": {
            "enforcement": "mandatory: tedaviye başlamak için diğer fosfor düşürücü ilaçların en az 3 ay süreyle kullanılmış olması ve bu hususun raporda belirtilmiş olması gerekir",
            "message_tr": "Tedaviye başlamak için diğer fosfor düşürücü ilaçların en az 3 ay süreyle kullanılmış olması ve bu hususun raporda belirtilmiş olması gerekir (§4.2.9.B).",
        },
    },

    # C004147 — sevelamer/lantanum/alüminyum: diyaliz hastasına nefroloji/iç/çocuk veya diyaliz sertifikalı hekim
    {
        "rule_id": "4.2.9.B.renal.phosphate_binders_dialysis_report_coverage",
        "sut_section": "4.2.9.B",
        "gate_b_sources": ["C004147"],
        "drug_names": ["sevelamer", "lantanyum karbonat", "alüminyum klorür hidroksit"],
        "icd10_codes": ["N18", "Z99.2"],
        "report_required": True,
        "report_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "prescriber_specialties": [
            "nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları",
            "diyaliz sertifikalı tüm hekimler",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "hemodiyaliz/periton diyalizi hastasına nefroloji (veya diyaliz sertifikalı iç/çocuk)/iç/çocuk uzmanının raporuyla sevelamer/lantanum/alüminyum klorür hidroksit; bu hekimlerce veya diyaliz sertifikalı tüm hekimlerce reçete",
            "message_tr": "Hemodiyaliz veya periton diyaliz tedavisi altındaki hastalara nefroloji, iç hastalıkları veya çocuk sağlığı ve hastalıkları uzman hekimlerinden birinin düzenlediği ve yukarıdaki durumlardan sevelamer, lantanyum karbonat veya alüminyum klorür hidroksit kullanımını gerektiren durumun belirtildiği uzman hekim raporuna dayanılarak bu hekimlerce veya diyaliz sertifikalı tüm hekimler tarafından reçete edildiğinde bedeli ödenir (§4.2.9.B).",
        },
    },

    # C004151 — sevelamer ve lantanum karbonat kombine kullanılamaz (prohibited)
    {
        "rule_id": "4.2.9.B.renal.sevelamer_lanthanum_combination_prohibited",
        "sut_section": "4.2.9.B",
        "gate_b_sources": ["C004151"],
        "drug_names": ["sevelamer", "lantanyum karbonat"],
        "icd10_codes": ["N18", "E83.3"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: sevelamer ve lantanyum karbonat kombine olarak kullanılamaz",
            "message_tr": "Sevelamer ve lantanyum karbonat kombine olarak kullanılamaz (§4.2.9.B).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.C  —  renal: paricalcitol parenteral/oral
    # -----------------------------------------------------------------

    # C004166 — parikalsitol parenteral: sadece hemodiyaliz, ≤6 ay rapor, ≤1 aylık doz
    {
        "rule_id": "4.2.9.C.renal.paricalcitol_parenteral_hemodialysis_coverage",
        "sut_section": "4.2.9.C",
        "gate_b_sources": ["C004166"],
        "drug_names": ["parikalsitol"],
        "icd10_codes": ["N18", "Z99.2"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "diyaliz sertifikalı uzman hekimi"],
        "prescriber_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "diyaliz sertifikalı uzman hekimi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "parikalsitol parenteral formları yalnızca hemodiyaliz hastalarına nefroloji/iç/çocuk veya diyaliz sertifikalı uzmanın ≤6 ay raporuyla bu hekimlerce en fazla 1 aylık dozda reçete",
            "message_tr": "Parikalsitolün parenteral formlarının yalnızca hemodiyaliz hastalarına yukarıda belirtilen koşullarda nefroloji, iç hastalıkları veya çocuk sağlığı ve hastalıkları uzman hekimleri veya diyaliz sertifikalı uzman hekimi tarafından düzenlenen en fazla 6 ay süreli sağlık raporuna istinaden yine bu hekimler tarafından en fazla 1 aylık dozda reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.9.C).",
        },
    },

    # C004167 — parikalsitol oral: sadece periton diyalizi, nefroloji ≤6 ay rapor, ≤1 aylık doz
    {
        "rule_id": "4.2.9.C.renal.paricalcitol_oral_peritoneal_dialysis_coverage",
        "sut_section": "4.2.9.C",
        "gate_b_sources": ["C004167"],
        "drug_names": ["parikalsitol"],
        "icd10_codes": ["N18", "Z99.2"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["nefroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "parikalsitol oral formları yalnızca periton diyalizi hastalarına nefroloji uzmanının ≤6 ay raporuyla nefroloji uzmanınca en fazla 1 aylık dozda reçete",
            "message_tr": "Parikalsitolün oral formlarının yukarıda belirtilen koşullarda periton diyalizi hastalarına nefroloji uzman hekimi tarafından düzenlenen en fazla 6 ay süreli sağlık raporuna istinaden nefroloji uzman hekimi tarafından en fazla 1 aylık dozda reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.9.C).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.E  —  renal: etelcalcetide (calcimimetic)
    # -----------------------------------------------------------------

    # C004197 — etelkalsetid: sadece hemodiyaliz, ≤6 ay rapor, ≤1 aylık doz
    {
        "rule_id": "4.2.9.E.renal.etelcalcetide_hemodialysis_report_coverage",
        "sut_section": "4.2.9.E",
        "gate_b_sources": ["C004197"],
        "drug_names": ["etelkalsetid"],
        "icd10_codes": ["N18", "Z99.2"],
        "report_required": True,
        "report_duration_months": 6,
        "report_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "diyaliz sertifikalı uzman hekimi"],
        "prescriber_specialties": ["nefroloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "diyaliz sertifikalı uzman hekimi"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "etelkalsetid yalnızca hemodiyaliz hastalarına nefroloji/iç/çocuk veya diyaliz sertifikalı uzmanın ≤6 ay raporuyla bu hekimlerce en fazla 1 aylık dozda reçete",
            "message_tr": "Etelkalsetid yalnızca hemodiyaliz hastalarına yukarıda belirtilen koşullarda nefroloji, iç hastalıkları veya çocuk sağlığı ve hastalıkları uzman hekimleri veya diyaliz sertifikalı uzman hekimi tarafından düzenlenen en fazla 6 ay süreli sağlık raporuna istinaden yine bu hekimler tarafından en fazla 1 aylık dozda reçete edilmesi halinde Kurumca bedelleri karşılanır (§4.2.9.E).",
        },
    },

    # C004199 — etelkalsetid: yalnızca hemodiyalizli KBH yetişkinde sekonder hiperparatiroidizm
    {
        "rule_id": "4.2.9.E.renal.etelcalcetide_adult_hdi_secondary_hpt_coverage",
        "sut_section": "4.2.9.E",
        "gate_b_sources": ["C004199"],
        "drug_names": ["etelkalsetid"],
        "icd10_codes": ["N18", "Z99.2"],
        "report_required": True,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["nefroloji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "etelkalsetid yalnızca hemodiyaliz tedavisi alan kronik böbrek hastalığı olan yetişkin hastalardaki sekonder hiperparatiroidizm tedavisinde kullanılırsa ödenir",
            "message_tr": "Etelkalsetid etken maddeli ilacın yalnızca; hemodiyaliz tedavisi alan kronik böbrek hastalığı olan yetişkin hastalardaki sekonder hiperparatiroidizmin tedavisinde kullanılması halinde Kurumca bedelleri karşılanır (§4.2.9.E).",
        },
    },

    # C004201 — cinacalcet ve etelkalsetid birlikte: no-pay
    {
        "rule_id": "4.2.9.E.renal.cinacalcet_etelcalcetide_combination_nopay",
        "sut_section": "4.2.9.E",
        "gate_b_sources": ["C004201"],
        "drug_names": ["cinacalcet", "etelkalsetid"],
        "icd10_codes": ["N18"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: cinacalcet ve etelkalsetid etken maddeli ilaçların birlikte kullanımı",
            "message_tr": "Cinacalcet ve etelkalsetid etken maddeli ilaçların birlikte kullanılması halinde Kurumca bedelleri karşılanmaz (§4.2.9.E).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.F  —  renal: potassium binder (sodyum/kalsiyum polistiren sülfonat)
    # -----------------------------------------------------------------

    # C004204 — hiperkalemi: RAAS/MRA + diyaliz dışı Evre4/5 KBH + ≥1 ağır atak + K≥6,0; nefroloji 3 ay rapor
    {
        "rule_id": "4.2.9.F.renal.hyperkalemia_k_binder_report_coverage",
        "sut_section": "4.2.9.F",
        "gate_b_sources": ["C004204"],
        "drug_names": ["sodyum polistiren sülfonat", "kalsiyum polistiren sülfonat"],
        "icd10_codes": ["N18", "E87.5"],
        "report_required": True,
        "report_duration_months": 3,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["nefroloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "RAAS inhibitörü veya MRA kullanan diyaliz almayan Evre 4/5 KBH + son 1 ay sodyum/kalsiyum polistiren sülfonat kullanımına rağmen ≥1 şiddetli hiperkalemi atağı + sK+≥6,0 mmol/L; nefroloji uzmanı 3 ay raporu; nefroloji veya iç hastalıkları reçetesi",
            "message_tr": "RAAS inhibitörünü veya MRA kullanmakta olan diyaliz almayan Evre 4 KBH veya Evre 5 KBH hastası olup ve son 1 ay içerisinde sodyum/kalsiyum polistiren sülfonat etkin maddeli ilaçları kullanmasına rağmen en az bir şiddetli hiperkalemi atağı geçiren ve serum potasyum seviyesi 6,0 mmol/L ya da üzerinde olan hastalarda; bu durumların belirtildiği en az bir nefroloji uzman hekimi tarafından düzenlenen 3 ay süreli sağlık kurulu raporuna istinaden nefroloji veya iç hastalıkları uzman hekimleri tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.9.F).",
        },
    },

    # C004205 — hiperkalemi: yılda en fazla 2 atak için toplam en fazla 6 kutu ödenir
    {
        "rule_id": "4.2.9.F.renal.hyperkalemia_max_2_attacks_6_boxes_coverage",
        "sut_section": "4.2.9.F",
        "gate_b_sources": ["C004205"],
        "drug_names": ["sodyum polistiren sülfonat", "kalsiyum polistiren sülfonat"],
        "icd10_codes": ["N18", "E87.5"],
        "report_required": True,
        "report_specialties": ["nefroloji"],
        "prescriber_specialties": ["nefroloji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "bir yılda en fazla iki hiperkalemi atağı için toplam en fazla 6 kutu bedeli ödenir; ilaç kullanımı her atak için yukarıdaki koşulların yeniden oluşması halinde mümkündür",
            "message_tr": "Bir yılda en fazla iki hiperkalemi atağı için toplam en fazla 6 kutu bedeli ödenir; ilacın kullanımı her atak için yukarıda belirtilen koşulların yeniden oluşması halinde mümkündür (§4.2.9.F).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.9.Ç  —  renal: cinacalcet/etelcalcetide combination prohibition
    # -----------------------------------------------------------------

    # C004179 — cinacalcet ve etelkalsetid birlikte: no-pay (variant paragraph)
    {
        "rule_id": "4.2.9.C.renal.cinacalcet_etelcalcetide_combination_nopay_variant",
        "sut_section": "4.2.9.Ç",
        "gate_b_sources": ["C004179"],
        "drug_names": ["cinacalcet", "etelkalsetid"],
        "icd10_codes": ["N18"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: cinacalcet ve etelkalsetid etken maddeli ilaçların birlikte kullanımı",
            "message_tr": "Cinacalcet ve etelkalsetid etken maddeli ilaçların birlikte kullanılması halinde Kurumca bedelleri karşılanmaz (§4.2.9.Ç).",
        },
    },
]


def all_gate_b_sources() -> list[str]:
    """Union of every gate_b_sources clause id in the batch (sorted)."""
    ids: set[str] = set()
    for rule in BATCH_RULES:
        ids.update(str(c) for c in (rule.get("gate_b_sources") or []))
    return sorted(ids)


if __name__ == "__main__":
    sources = all_gate_b_sources()
    print(f"BATCH_RULES: {len(BATCH_RULES)} rules, "
          f"{len(sources)} distinct gate_b_sources")
