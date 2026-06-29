#!/usr/bin/env python3
"""Gap-closing wave R6 — referral/admission, identity, YUPASS-MEDULA, surcharge, report format.

30 in-force deontic clauses encoded from
`tasks/encode_waves/REM_others_referral.csv` covering:

* §1.5  / 1.5.1 / 1.5.2  —  referral & patient admission (müracaat / sevk)
* §1.6                    —  identity verification & biometric authentication
* §1.7  / 1.7.1 / 1.7.2   —  YUPASS / MEDULA provizyon (foreign SSAs, system fault)
* §1.9  / 1.9.1-1.9.4     —  ilave ücret (surcharge) rules
* §1.10                   —  health-report formats, MEDULA e-approval

Rule shape follows the established `drug_indication_prose.json` pattern: a
``gate_b_sources`` list (one clause id per rule here), flat condition keys and a
nested ``action`` block (message_tr + enforcement).  NO_PAY / PROHIBITED
modalities encode as ``pay: False``; PERMISSION / COVERAGE as
``condition: {"coverage_note": True}``; MANDATORY / REGULATORY_ACTION as a bare
enforcement action.  ``message_tr`` is taken from the in-force Turkish text.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §1.10  —  health-report formats / MEDULA e-approval
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C000460 — health report formats subject to MoH rules & MEDULA e-approval
    {
        "rule_id": "1.10.report_format_medula_eapproval",
        "sut_section": "1.10",
        "gate_b_sources": ["C000460"],
        "action": {
            "enforcement": "sağlık rapor formatları ile tasdik/mühür ve diğer uygulamalarda Sağlık Bakanlığı mevzuatı ve MEDULA düzenlemelerine uyulması; MEDULA kullanan sunucular raporları elektronik düzenler, başhekimlikçe elektronik onaylanır",
            "message_tr": "Sağlık rapor formatları ile bu raporların tasdik, mühür ve diğer uygulamalarında Sağlık Bakanlığı mevzuatı ve MEDULA sistemindeki düzenlemelere uyulacaktır. MEDULA hastane sistemini kullanan sağlık hizmeti sunucuları raporları elektronik ortamda düzenleyecek ve bu raporlar başhekimlik tarafından elektronik ortamda onaylanacaktır. Sağlık kurulu raporlarına ait istisnai düzenlemeler SUT'ta ayrıca belirtilmiştir (§1.10).",
        },
    },

    # -----------------------------------------------------------------
    # §1.5 / 1.5.1 / 1.5.2  —  referral & patient admission
    # -----------------------------------------------------------------

    # C000094 — contracted outpatient/inpatient providers: payment only if admission per these rules
    {
        "rule_id": "1.5.referral_admission_procedure_required",
        "sut_section": "1.5",
        "gate_b_sources": ["C000094"],
        "action": {
            "enforcement": "ayakta/yatarak tanı ve tedavi hizmeti sunan sözleşmeli sunuculara bedel ödenebilmesi için müracaat işlemlerinin aşağıdaki usul ve esaslara uygun yapılması gerekir",
            "message_tr": "Ayakta veya yatarak tanı ve tedavi hizmeti sunan sözleşmeli sağlık hizmeti sunucularına, sunmuş oldukları sağlık hizmeti bedellerinin ödenebilmesi için müracaat işlemlerinin aşağıda belirtilen usul ve esaslar doğrultusunda gerçekleştirilmiş olması gerekmektedir (§1.5).",
        },
    },

    # C000097 — GSS persons 60/c-1, 60/c-3 & 12th-14th paras: eligibility via MEDULA, non-compliant admissions not paid
    {
        "rule_id": "1.5.medula_eligibility_noncompliant_admission_nopay",
        "sut_section": "1.5.1",
        "gate_b_sources": ["C000097"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: GSS kapsamındaki kişilerin müracaatında MEDULA üzerinden müstahaklık sorgulanır; aşağıdaki usul ve esaslara uygun olmayan müracaatlara ilişkin bedeller Kurumca karşılanmaz",
            "message_tr": "5510 sayılı Kanunun 60 ıncı maddesinin birinci fıkrasının (c) bendinin (1) ve (3) numaralı alt bentleri ile aynı maddenin onikinci, onüçüncü ve ondördüncü fıkraları gereği genel sağlık sigortası kapsamına alınan kişilerin, ayakta veya yatarak teşhis ve tedavi hizmeti veren sağlık hizmeti sunucularına müracaatlarında MEDULA sistemi üzerinden müstahaklık sorgulaması yapılır. Sorgulama sonucu Kurum bilgisi 60/c-1 veya 60/c-3 dönen kişiler ile 60 ıncı maddenin onikinci, onüçüncü ve ondördüncü fıkralarında tanımlanan kişilerin müracaat kabul ve sevk işlemleri aşağıdaki şekilde yürütülecektir. Aşağıda belirtilen usul ve esaslara uygun olmayan müracaatlara ilişkin sağlık hizmeti bedelleri Kurumca karşılanmaz (§1.5.1).",
        },
    },

    # C000099 — non-contracted private providers: no pay except emergencies accepted by audit unit
    {
        "rule_id": "1.5.noncontracted_private_provider_emergency_only_nopay",
        "sut_section": "1.5.1",
        "gate_b_sources": ["C000099"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: acil haller dışında sözleşmesiz özel sağlık hizmeti sunucularından alınan hizmet bedelleri ödenmez; acilde alınan hizmetin bedeli için Kurum inceleme biriminin durumu kabul etmesi gerekir",
            "message_tr": "Acil haller dışında sözleşmesiz özel sağlık hizmeti sunucularından alınan sağlık hizmeti bedelleri Kurumca ödenmez. Sözleşmesiz özel sağlık hizmeti sunucularından acil hallerde alınan sağlık hizmetlerinin bedellerinin ödenebilmesi için bu durumun Kurum inceleme birimlerince kabul edilmesi gerekmektedir (§1.5.1).",
        },
    },

    # C000105 — first-step referrals within same settlement to MoH 2nd/3rd step
    {
        "rule_id": "1.5.firststep_referral_within_settlement",
        "sut_section": "1.5.1.A-2",
        "gate_b_sources": ["C000105"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "permission: birinci basamak sunucularınca sevkler aynı yerleşim yeri içindeki Sağlık Bakanlığı ikinci veya üçüncü basamak sunucusuna yapılabilir",
            "message_tr": "Birinci basamak sağlık hizmeti sunucularınca; sevkler aynı yerleşim yeri içindeki Sağlık Bakanlığı ikinci veya üçüncü basamak sağlık hizmeti sunucusuna yapılabilir (§1.5.1.A-2).",
        },
    },

    # C000111 — chronic haemodialysis referral to non-MoH official providers; 3-month validity
    {
        "rule_id": "1.5.hemodialysis_referral_3mo_validity_a",
        "sut_section": "1.5.1.A-2",
        "gate_b_sources": ["C000111"],
        "report_duration_months": 3,
        "action": {
            "enforcement": "Sağlık Bakanlığı dışındaki resmi sunuculara kronik hemodiyaliz sevkleri; hemodiyaliz merkezi bulunan Bakanlık sunucusunca, yoksa müracaat edilen sunucunca yapılır; sevkler 3 ay geçerli, sürede yenilenmeli",
            "message_tr": "Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına kronik hemodiyaliz tedavisi programı için yapılacak sevkler, aynı yerleşim yerinde varsa bünyesinde hemodiyaliz merkezi bulunan Sağlık Bakanlığı sağlık hizmeti sunucularınca yoksa müracaat edilen sağlık hizmeti sunucusunca yapılacaktır. Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına yapılan hemodiyaliz amaçlı sevkler 3 ay süre ile geçerli olup sürenin bitiminde sevk belgesinin yenilenmesi gerekmektedir (§1.5.1.A-2).",
        },
    },

    # C000116 — chronic haemodialysis referral (duplicate paragraph variant)
    {
        "rule_id": "1.5.hemodialysis_referral_3mo_validity_b",
        "sut_section": "1.5.1.A-2",
        "gate_b_sources": ["C000116"],
        "report_duration_months": 3,
        "action": {
            "enforcement": "Sağlık Bakanlığı dışındaki resmi sunuculara kronik hemodiyaliz sevkleri; hemodiyaliz merkezi bulunan Bakanlık sunucusunca, yoksa müracaat edilen sunucunca yapılır; sevkler 3 ay geçerli, sürede yenilenmeli",
            "message_tr": "Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına kronik hemodiyaliz tedavisi programı için yapılacak sevkler, aynı yerleşim yerinde varsa bünyesinde hemodiyaliz merkezi bulunan Sağlık Bakanlığı sağlık hizmeti sunucularınca yoksa müracaat edilen sağlık hizmeti sunucusunca yapılacaktır. Sağlık Bakanlığı dışındaki resmi sağlık hizmeti sunucularına yapılan hemodiyaliz amaçlı sevkler 3 ay süre ile geçerli olup sürenin bitiminde sevk belgesinin yenilenmesi gerekmektedir (§1.5.1.A-2).",
        },
    },

    # C000133 — intra-hospital referral (same admission): re-enter referral declaration in system
    {
        "rule_id": "1.5.intrahospital_referral_same_admission",
        "sut_section": "1.5.1.B-1",
        "gate_b_sources": ["C000133"],
        "action": {
            "enforcement": "aynı sunucuda kabul edilen hastanın diğer branşa yönlendirilmesi (konsültasyon hariç) branş hekimince aynı sevk belgesi üzerinde belirtilmesi şartıyla yapılır; Kurum bilgi işlem sistemine hastane içi sevk beyanı girilir",
            "message_tr": "Müracaatları kabul edilen hastaların aynı sağlık hizmeti sunucusunda diğer branşlarda da muayene veya tedavisinin gerekli görülmesi durumunda (konsültasyon istemi hariç); branş hekimince aynı sevk belgesi üzerinde gönderilecek branşın belirtilmesi şartıyla ilgili branşa yapılan müracaatlarda Kurum bilgi işlem sistemine yeniden sevk beyanı (hastane içi sevk) girilecektir (§1.5.1.B-1).",
        },
    },

    # C000135 — program-based therapy (FTR/hemodiyaliz/radyoterapi/kemoterapi) follow-up admissions
    {
        "rule_id": "1.5.program_therapy_followup_admissions",
        "sut_section": "1.5.1.B-1",
        "gate_b_sources": ["C000135"],
        "report_duration_months": 3,
        "action": {
            "enforcement": "fizik tedavi/rehabilitasyon, hemodiyaliz, radyoterapi ve kemoterapi gibi program dahilinde tedavi gören hastaların tedavi süresi içindeki müteakip müracaatları ilk sevk belgesine istinaden yapılır; hemodiyaliz sevkleri 3 ay geçerli",
            "message_tr": "Müracaatları kabul edilen hastalardan fizik tedavi ve rehabilitasyon tedavisi, hemodiyaliz tedavisi, radyoterapi ve kemoterapi gibi belli bir program dahilinde tedavi gören hastaların tedavi süresi içindeki, ilk sevk belgesine istinaden yapılan müteakip müracaatları kabul edilir. Hemodiyaliz amaçlı sevkler 3 ay süre ile geçerli olup sürenin bitiminde sevk belgesinin yenilenmesi gerekmektedir (§1.5.1.B-1).",
        },
    },

    # C000145 — patient admission operations: comply with the listed arrangements (C-1 header)
    {
        "rule_id": "1.5.patient_admission_arrangements_c1",
        "sut_section": "1.5.1.C-1",
        "gate_b_sources": ["C000145"],
        "action": {
            "enforcement": "hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır",
            "message_tr": "Hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır (§1.5.1.C-1).",
        },
    },

    # C000161 — patient admission operations: comply with the listed arrangements (Ç-1 header)
    {
        "rule_id": "1.5.patient_admission_arrangements_c1c",
        "sut_section": "1.5.1.Ç-1",
        "gate_b_sources": ["C000161"],
        "action": {
            "enforcement": "hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır",
            "message_tr": "Hasta kabul işlemleri yürütümünde aşağıdaki düzenlemelere uyulacaktır (§1.5.1.Ç-1).",
        },
    },

    # C000166 — emergency admissions: audit unit must accept the emergency situation
    {
        "rule_id": "1.5.emergency_admission_audit_acceptance",
        "sut_section": "1.5.1.Ç-1",
        "gate_b_sources": ["C000166"],
        "action": {
            "enforcement": "acil haller nedeniyle yapılan müracaatlar; müracaatın acil hal nedeniyle yapıldığının Kurum inceleme birimlerince kabul edilmesi gerekir",
            "message_tr": "Acil haller nedeniyle yapılan müracaatlarda, hasta müracaatının söz konusu durum nedeniyle yapıldığının Kurum inceleme birimlerince kabul edilmesi gerekmektedir (§1.5.1.Ç-1).",
        },
    },

    # C000178 — non-contracted providers (no GSS exception): no pay except emergencies
    {
        "rule_id": "1.5.noncontracted_provider_nopay_except_emergency",
        "sut_section": "1.5.2",
        "gate_b_sources": ["C000178"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: SUT 2.2(5) istisnaları hariç, acil haller dışında Kurum ile sözleşmesi olmayan sunuculardan alınan hizmet bedelleri Kurumca karşılanmaz",
            "message_tr": "Kişilerin, SUT'un 2.2(5) fıkrasında belirtilen istisnalar hariç olmak üzere acil haller dışında Kurum ile sözleşmesi olmayan sağlık hizmeti sunucularından aldıkları sağlık hizmeti bedelleri Kurumca karşılanmaz (§1.5.2).",
        },
    },

    # C000179 — contracted providers must accept GSS beneficiaries without discrimination
    {
        "rule_id": "1.5.contracted_provider_nondiscriminatory_admission",
        "sut_section": "1.5.2",
        "gate_b_sources": ["C000179"],
        "action": {
            "enforcement": "Kurum ile sözleşmeli sunucular, Kurum sağlık yardımlarından yararlandırılan kişilerin müracaatlarını ayrım yapmaksızın kabul etmek zorundadır",
            "message_tr": "Kurum ile sözleşmeli sağlık hizmeti sunucuları, Kurum sağlık yardımlarından yararlandırılan kişilerin müracaatlarını ayrım yapmaksızın kabul etmek zorundadır (§1.5.2).",
        },
    },

    # -----------------------------------------------------------------
    # §1.6  —  identity verification & biometric authentication
    # -----------------------------------------------------------------

    # C000181 — identity verification & biometric authentication mandatory; mispaid amount recovered
    {
        "rule_id": "1.6.identity_biometric_verification_mandatory",
        "sut_section": "1.6",
        "gate_b_sources": ["C000181"],
        "action": {
            "enforcement": "müracaatta (acilde acil hal bitince) nüfus cüzdanı/sürücü belgesi/evlenme cüzdanı/pasaport/Kurum sağlık kartından biri ile kimlik tespiti ve biyometrik kimlik doğrulaması zorunlu; usulsüzlük nedeniyle başkasına hizmet sunulup Kurum zarara uğratılırsa ödenen tutar geri alınır",
            "message_tr": "Sağlık hizmeti sunucularınca, kişilerin müracaatı aşamasında, acil hallerde ise acil halin sona ermesinden sonra, nüfus cüzdanı, sürücü belgesi, evlenme cüzdanı, pasaport veya verilmiş ise Kurum sağlık kartı belgelerinden biri ile kimlik tespiti ve biyometrik yöntemlerle kimlik doğrulaması yapılması zorunludur. Kimlik tespiti, biyometrik kayıt işlemi veya biyometrik kimlik doğrulama işlemini usulüne uygun yapmayan ve bu nedenle bir başka kişiye sağlık hizmeti sunulması nedeniyle Kurumun zarara uğramasına sebebiyet veren sağlık hizmeti sunucularından ödenen tutar geri alınır (§1.6).",
        },
    },

    # C000183 — prohibited: obtaining service for another or illicit benefit; double damages recovered
    {
        "rule_id": "1.6.impersonation_illicit_benefit_prohibited",
        "sut_section": "1.6",
        "gate_b_sources": ["C000183"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: kapsamdaki kişilerin kendi adına bir başkasının sağlık hizmeti almasını veya Kurumdan haksız menfaat temin etmesini sağlaması yasaktır; zararın iki katı kanunî faiziyle müştereken ve müteselsilen tahsil edilir, 5237 sayılı TCK doğrultusunda suç duyurusu yapılır",
            "message_tr": "Kapsamdaki kişilerin kendi adına bir başkasının sağlık hizmeti almasını veya Kurumdan haksız bir menfaat temin etmesini sağlaması yasaktır. Bu fiilleri işleyenlerden Kurumun uğradığı zararın iki katı kanunî faiziyle birlikte müştereken ve müteselsilen tahsil edilir ve ilgililer hakkında 5237 sayılı Türk Ceza Kanunu hükümleri doğrultusunda suç duyurusunda bulunulur (§1.6).",
        },
    },

    # -----------------------------------------------------------------
    # §1.7 / 1.7.1 / 1.7.2  —  YUPASS / MEDULA provizyon
    # -----------------------------------------------------------------

    # C000218 — foreign SSA scope: only YUPASS "açıklamalar" illnesses covered
    {
        "rule_id": "1.7.yupass_foreign_ssa_scope_only_listed",
        "sut_section": "1.7.1",
        "gate_b_sources": ["C000218"],
        "action": {
            "enforcement": "yabancı ülke sosyal güvenlik sözleşmesi kapsamında iş kazası/meslek hastalığı ve tedavi için gönderilen sigortalılara YUPASS 'açıklamalar' bölümünde belirtilen hastalıklar dışındaki tedavi masrafları Kurumca karşılanmaz",
            "message_tr": "Yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında iş kazası ve meslek hastalığı sigortaları ve tedavi edilmek üzere ülkemize gönderilme kapsamında sağlık yardımlarından yararlanacak sigortalılara YUPASS provizyon sisteminde 'açıklamalar' bölümünde belirtilen hastalıklar dışındaki tedavi masrafları Kurumca karşılanmayacaktır (§1.7.1).",
        },
    },

    # C000219 — foreign SSA persons: orthosis/prosthesis/medical device needs prior Kurum approval
    {
        "rule_id": "1.7.yupass_foreign_ssa_device_prior_approval",
        "sut_section": "1.7.1",
        "gate_b_sources": ["C000219"],
        "action": {
            "enforcement": "geçici olarak Türkiye'de bulunan sözleşme kapsamı kişilere acil haller dışında ortez, protez, tıbbi araç-gereç ve kişiye mahsus tıbbi cihaz için YUPASS 'açıklamalar' uyarısı doğrultusunda önceden Kurum ilgili biriminden onay alınacaktır",
            "message_tr": "Yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında geçici olarak Türkiye'de bulundukları sürede Kurum sağlık yardımlarından yararlandırılan kişilere acil haller dışında sağlanacak ortez, protez, tıbbi araç ve gereç ile kişi kullanımına mahsus tıbbi cihaz için YUPASS provizyon sisteminde 'açıklamalar' bölümünde belirtilen uyarı doğrultusunda önceden Kurumun ilgili biriminden onay alınacaktır (§1.7.1).",
        },
    },

    # C000221 — MEDULA fault: no patient-tracking number → service still covered if attested
    {
        "rule_id": "1.7.medula_fault_coverage_without_tracking_number",
        "sut_section": "1.7.2",
        "gate_b_sources": ["C000221"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "MEDULA arızası nedeniyle hasta takip numarası alınamadığı sürede, Kurum Hizmet Sunumu Genel Müdürlüğü yetkililerince imzalanan tutanakla tevsik kaydıyla, hakkını yazılı beyan/belgeleyen kişilerin sağlık hizmetleri Kurumca karşılanır; sonradan müstahak olmadığı çıkarsa fatura sunucuya ödenip yasal işlem yürütülür",
            "message_tr": "Kurum Hizmet Sunumu Genel Müdürlüğü yetkililerince imzalanacak bir tutanak ile tevsik edilmesi kaydıyla MEDULA sisteminden kaynaklanan arıza nedeniyle hasta takip numarasının alınamadığı süre zarfında Kurum sağlık yardımlarından yararlanma hakkının olduğunu yazılı olarak beyan etmek veya belgelemek suretiyle müracaat eden kişilerin sağlık hizmetleri Kurumca karşılanır. Daha sonra yapılan sorgulama sonucu bu kişilerin müstahak olmadığının tespit edilmesi halinde, tedaviye ait fatura bedeli ilgili sağlık hizmeti sunucusuna ödenerek gerekli yasal işlemler Kurumca yürütülür (§1.7.2).",
        },
    },

    # -----------------------------------------------------------------
    # §1.9 / 1.9.1-1.9.4  —  ilave ücret (surcharge)
    # -----------------------------------------------------------------

    # C000394 — contracted foundation universities / 2nd-3rd step private providers: capped extra fee allowed
    {
        "rule_id": "1.9.foundation_private_provider_capped_surcharge",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000394"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "permission: Kurumla sözleşmeli vakıf üniversiteleri ile ikinci ve üçüncü basamak özel sağlık hizmeti sunucularınca Kurumca belirlenen oranı geçmemek kaydıyla kişilerden ilave ücret alınabilir",
            "message_tr": "Kurumla sözleşmeli; vakıf üniversiteleri, ikinci ve üçüncü basamak özel sağlık hizmeti sunucuları tarafından; Kurumca belirlenen oranı geçmemek kaydıyla kişilerden ilave ücret alınabilir (§1.9.1).",
        },
    },

    # C000395 — higher-ed providers: faculty off-hours surcharge capped; protocol providers: none
    {
        "rule_id": "1.9.highered_faculty_surcharge_cap",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000395"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: yükseköğretim kurumuna ait sunucularda (vakıf üniversiteleri hariç) öğretim üyelerince mesai dışı verilen hizmet için bir defada asgari ücretin iki katını geçmemek üzere poliklinikte en fazla iki katı, diğer hizmetlerde en fazla bir katı ilave ücret alınabilir; Bakanlık-üniversite birlikte kullanım protokollü sunucularda öğretim üyelerince ilave ücret alınamaz",
            "message_tr": "Yükseköğretim kurumlarına ait sağlık hizmeti sunucularında (vakıf üniversiteleri hariç) öğretim üyeleri tarafından mesai saatleri dışında bizzat verilen sağlık hizmetleri için bir defada asgari ücretin iki katını geçmemek üzere, Kurumca belirlenmiş sağlık hizmetleri bedelinin poliklinik muayenelerinde en fazla iki katı, diğer hizmetlerde en fazla bir katı kadar ilave ücret alınabilir. Sağlık Bakanlığı ve bağlı kuruluşlarına ait sağlık tesisleri ve üniversitelere ait ilgili birimlerin birlikte kullanımına ilişkin protokolü bulunan sağlık hizmeti sunucularında öğretim üyeleri tarafından ilave ücret alınamaz (§1.9.1).",
        },
    },

    # C000396 — surcharge prohibited on EK-2/B, EK-2/C, EK-2/Ç items & EK-2/A-inclusive procedures
    {
        "rule_id": "1.9.surcharge_prohibited_ek2_medical_material_drug",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000396"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: SUT eki EK-2/B, EK-2/C, EK-2/Ç listelerindeki işlemlerin bedellerine ilave olarak Kuruma ayrıca faturalandırılabilen tıbbi malzeme, ilaçlar ve kan bileşenleri ile EK-2/A listesindeki tutarlara dahil işlemler için ayrıca ilave ücret alınamaz",
            "message_tr": "(a) ve (b) bentlerinde belirtilen sağlık hizmeti sunucularınca SUT ve eklerinde yer alan sağlık hizmetleri işlem bedellerinin tamamı üzerinden Kuruma fatura edilebilen tutarlar esas alınarak kişilerden ilave ücret alınabilir. Ancak SUT eki EK-2/B, EK-2/C, EK-2/Ç listelerinde yer alan işlemlerin bedellerine ilave olarak Kuruma ayrıca faturalandırılabilen tıbbi malzeme, ilaçlar ve kan bileşenleri ile SUT eki EK-2/A Listesindeki tutarlara dahil olan işlemler için ayrıca ilave ücret alınamaz (§1.9.1).",
        },
    },

    # C000399 — surcharges cannot be claimed from the Kurum
    {
        "rule_id": "1.9.surcharge_not_claimable_from_kurum",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000399"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: ilave ücretler genel sağlık sigortalılarınca veya bakmakla yükümlü olunan kişilerce ve/veya sağlık hizmeti sunucularınca Kurumdan talep edilemez",
            "message_tr": "İlave ücretler, genel sağlık sigortalılarınca veya bakmakla yükümlü olunan kişilerce ve/veya sağlık hizmeti sunucularınca Kurumdan talep edilemez (§1.9.1).",
        },
    },

    # C000405 — emergency: no surcharge within 24h / direct emergency procedures / 24h observation
    {
        "rule_id": "1.9.emergency_24h_no_surcharge_disclosure_form",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000405"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: hastanın acil serviste 24 saat içinde stabilizasyonu esastır; acil servisten kabul edilip doğrudan uygulanan acil girişimsel işlemler ile 24 saat içinde acil gözlem ünitelerindeki tüm hizmetler için ilave ücret alınamaz; ilave ücret için 'Acil Halin Sona Ermesine İlişkin Bilgilendirme Formu' (EK-1/D) ile imza karşılığı yazılı bilgi verilmesi zorunludur",
            "message_tr": "Hastanın acil servislerde 24 saat içinde stabilizasyonu esastır. Hastanın acil servise başvurusundan itibaren 24 saat içinde stabilize edilerek ilgili kliniğe yatışı ya da başka bir sağlık hizmeti sunucusunun yataklı kliniğine sevk edilmesiyle acil hal sona erer. Acil servislerden kabul edilerek doğrudan uygulanan acil girişimsel işlemler ile 24 saat içinde acil gözlem ünitelerinde uygulanan tüm sağlık hizmetleri için ilave ücret alınamaz. Hastadan ilave ücret alınabilmesi için hastaya/hasta yakınına acil halin sona erdiğine ve müteakip işlemlerin ilave ücrete tabi olduğuna ilişkin 'Acil Halin Sona Ermesine İlişkin Bilgilendirme Formu' (EK-1/D) kullanılarak, yazılı bilginin imza karşılığı verilmesi zorunludur (§1.9.1).",
        },
    },

    # C000410 — inpatient >100 TL: must give EK-1/B services & surcharge document at discharge
    {
        "rule_id": "1.9.inpatient_ek1b_document_at_discharge",
        "sut_section": "1.9.1",
        "gate_b_sources": ["C000410"],
        "action": {
            "enforcement": "sözleşmeli vakıf üniversiteleri ile ikinci ve üçüncü basamak özel sunucular, aynı başvuru numarası altındaki yatarak tedavide Kurumca karşılanan bedeller toplamı 100 TL'yi aşarsa 'Hastaya Sunulmuş Olan Hizmetleri ve İlave Ücreti Gösterir Belge (EK-1/B)'yi en geç taburculuk tarihinde hastaya vermek zorundadır; aynı süre içinde elektronik olarak da verilebilir",
            "message_tr": "Kurumla sözleşmeli vakıf üniversiteleri, ikinci ve üçüncü basamak özel sağlık hizmeti sunucuları, aynı başvuru numarası altında yatarak tedavilerde yapılan Kurumca karşılanan sağlık hizmeti bedellerinin toplamının 100 (yüz) TL'yi aşması halinde, bu hizmetleri ve varsa ilave ücret tutarını gösterir, SUT eki 'Hastaya Sunulmuş Olan Hizmetleri ve İlave Ücreti Gösterir Belge (EK-1/B)'yi en geç hastanın taburcu olduğu tarihte hastaya vermek zorundadır. Söz konusu bilgiler aynı süreler içerisinde elektronik ortamda da verilebilir (§1.9.1).",
        },
    },

    # C000418 — no surcharge from the listed persons
    {
        "rule_id": "1.9.no_surcharge_listed_persons",
        "sut_section": "1.9.2",
        "gate_b_sources": ["C000418"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: aşağıda belirtilen kişilerden hiçbir ilave ücret alınamaz",
            "message_tr": "Aşağıda belirtilen kişilerden hiçbir ilave ücret alınamaz (§1.9.2).",
        },
    },

    # C000426 — no surcharge on the listed services (with university-faculty exceptions)
    {
        "rule_id": "1.9.no_surcharge_listed_services",
        "sut_section": "1.9.3",
        "gate_b_sources": ["C000426"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: aşağıda belirtilen sağlık hizmetleri için hiçbir ilave ücret alınamaz; ancak yükseköğretim kurumuna ait sunucularda (vakıf üniversiteleri hariç) öğretim üyesince verilen (18 yaşını doldurmamış çocuklar hariç) EK-2/B ve EK-2/C işitsel implant işlemleri ile 2.1.1 kapsamındaki hizmetler ve kardiyovasküler cerrahi işlemler için ilave ücret alınabilir",
            "message_tr": "Aşağıda belirtilen sağlık hizmetleri için hiçbir ilave ücret alınamaz. Ancak; yükseköğretim kurumlarına ait sağlık hizmeti sunucularında (vakıf üniversiteleri hariç) öğretim üyesi tarafından verilen 18 yaşını doldurmamış çocuklar hariç olmak üzere; SUT eki EK-2/B ve EK-2/C Listesindeki işitsel implant işlemleri için ilave ücret alınabilir. Ayrıca yükseköğretim kurumlarına ait sağlık hizmeti sunucularında öğretim üyesi tarafından verilen SUT'un 2.1.1 numaralı maddesi kapsamındaki sağlık hizmetleri ve kardiyovasküler cerrahi işlemler için de ilave ücret alınabilir (§1.9.3).",
        },
    },

    # C000427 — emergency services (except green-area examination) subject to no-surcharge list
    {
        "rule_id": "1.9.emergency_services_no_surcharge_except_green_area",
        "sut_section": "1.9.3",
        "gate_b_sources": ["C000427"],
        "action": {
            "enforcement": "acil servislerde verilen ve EK-2/B'de 520.021 kodlu 'Yeşil alan muayenesi' adı altında fatura edilen hizmetler hariç, acil haller nedeniyle sunulan sağlık hizmetleri ilave ücret alınmayan hizmetlerdendir",
            "message_tr": "Acil servislerde verilen ve SUT eki EK-2/B Listesinde yer alan 520.021 kod numaralı 'Yeşil alan muayenesi' adı altında Kuruma fatura edilebilen sağlık hizmetleri hariç olmak üzere, acil haller nedeniyle sunulan sağlık hizmetleri (§1.9.3).",
        },
    },

    # C000437 — cardiovascular surgery procedures (except exceptional services) on no-surcharge list
    {
        "rule_id": "1.9.cardiovascular_surgery_no_surcharge",
        "sut_section": "1.9.3",
        "gate_b_sources": ["C000437"],
        "action": {
            "enforcement": "kardiyovasküler cerrahi branşında yapılan cerrahi işlemler (istisnai sağlık hizmetlerinde belirtilenler hariç) ilave ücret alınmayan hizmetlerdendir",
            "message_tr": "Kardiyovasküler cerrahi branşında yapılan cerrahi işlemler (istisnai sağlık hizmetlerinde belirtilen işlemler hariç) ilave ücret alınmayan hizmetlerdendir (§1.9.3).",
        },
    },

    # C000455 — hoteling-service surcharge caps; no surcharge on exceptional-service hospitality
    {
        "rule_id": "1.9.hospitality_service_surcharge_caps",
        "sut_section": "1.9.4",
        "gate_b_sources": ["C000455"],
        "pay": False,
        "action": {
            "enforcement": "prohibited sınır: sözleşmeli sunucular, asgari banyo/TV/telefon bulunan 2 yataklı odalardaki otelcilik hizmeti için 510.010 'Standart yatak tarifesi'nin 1,5 katını, tek yataklı odalarda 3 katını geçmemek üzere ilave ücret alabilir; günübirlik otelcilikte 'Gündüz yatak tarifesi'nin en fazla 3 katı; istisnai sağlık hizmetlerinde (EK-1/C) otelcilik için ayrıca ilave ücret uygulanmaz",
            "message_tr": "Sözleşmeli sağlık hizmeti sunucuları, asgari banyo, TV ve telefon bulunan; 2 yataklı odalarda sundukları otelcilik hizmetleri için SUT eki EK-2/B Listesinde 510.010 kod ile yer alan 'Standart yatak tarifesi' işlem bedelinin 1,5 katını, tek yataklı odalarda ise 3 katını geçmemek üzere kişilerden ilave ücret alabilir. Günübirlik tedavi kapsamındaki işlemler sırasında verilen otelcilik hizmeti için ise en fazla SUT eki EK-2/B Listesinde yer alan 'Gündüz yatak tarifesi' işlem bedelinin 3 katına kadar ilave ücret alınabilir. SUT eki EK-1/C Listesinde yer alan istisnai sağlık hizmetlerinde otelcilik hizmetleri için ayrıca ilave ücret uygulanmaz (§1.9.4).",
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
