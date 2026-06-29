#!/usr/bin/env python3
"""Wave B1 / r6 — drug ek4a / overseas-drug / other-drug-provision (§4.1, §4.3-4.7).

59 in-force deontic clauses encoded from
`tasks/encode_waves/REM_4_1_4_3_7.csv` (clauses spanning §4.1, §4.3,
§4.4, §4.5, §4.6 and §4.7).

Rule shape follows the established `drug_indication_rheum_biologics_batch_rules`
pattern: flat condition keys (drug_names, report_required / report_duration_months
/ report_specialties, prescriber_specialties, pay, condition.coverage_note)
plus a nested ``action`` block (enforcement + message_tr) for NO_PAY /
coverage / no-copay / permission / prohibited statements.  Each rule maps
exactly one gate_b_sources clause_id.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.1 — drug use conditions / MEDULA recording (ek4a)
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C003401 — NO_PAY: prior-agent condition drugs require MEDULA recording
    {
        "rule_id": "4.1.prior_agent_condition_medula_recording_nopay",
        "sut_section": "4.1",
        "gate_b_sources": ["C003401"],
        "condition": {"prior_agent_use_condition": True},
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: another active substance usage is required as a condition, the relevant SUT provision usage must be recorded in MEDULA; if not recorded the cost is not covered (except patients who started before effective date); overseas/referral use requires GSS approval + supply document",
            "message_tr": "Başka bir etkin madde/maddelerin kullanılmış olması şartı belirtilen ilaçların ilgili SUT hükmü kapsamında kullanıldığına dair MEDULA kaydının yer alması gerekir; MEDULA sisteminde yer almaması halinde Kurumca bedeli karşılanmaz (yürürlük öncesi başlayanlar hariç). Sevkli yurtdışı tedavi/ikili güvenlik sözleşmesi gibi istisnai durumlarda GSS Genel Müdürlüğü onayı ve temin/kullanım belgesi şarttır (§4.1).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.1 — diagnoses on prescriptions (ek4a)
    # -------------------------------------------------------------------

    # C003406 — MANDATORY: diagnosis info on prescriptions; no abbreviations
    {
        "rule_id": "4.1.1.prescription_diagnosis_mandatory",
        "sut_section": "4.1.1",
        "gate_b_sources": ["C003406"],
        "condition": {"diagnosis_required": True},
        "action": {
            "enforcement": "mandatory: prescriptions must carry diagnosis; no abbreviations except those in SUT 'Teşhis Kısaltmaları Listesi' (EK-4/Ç); supportive/anti-side-effect drugs need no separate diagnosis",
            "message_tr": "Reçetelerde teşhis bilgisinin yer alması zorunludur; SUT eki 'Teşhis Kısaltmaları Listesi' (EK-4/Ç) kısaltmaları hariç teşhislerde kısaltma yapılmaz; yan etki önlemek/tedaviyi desteklemek amacıyla reçete edilen ilaçlar için ayrıca teşhis aranmaz (§4.1.1).",
        },
    },

    # C003412 — COVERAGE: family-medicine contracted/authorized physicians may prescribe family-medicine specialist drugs
    {
        "rule_id": "4.1.1.family_medicine_contracted_prescribe_coverage",
        "sut_section": "4.1.1",
        "gate_b_sources": ["C003412"],
        "prescriber_specialties": [
            "aile hekimliği sözleşmeli/yetkilendirilmiş hekim",
            "aile hekimliği uzman hekim",
        ],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "coverage: MoH family-medicine contracted/authorized physicians may prescribe all drugs a family-medicine specialist can; specific SUT sections (4.2.13.1, 4.2.13.2, 4.2.15.B/C/Ç/D-1/D-2/E/F, 4.2.20, 4.2.38) prescribed per health report by these physicians or family-medicine specialists are paid",
            "message_tr": "Sağlık Bakanlığınca aile hekimliği sözleşmesi yapılan/yetkilendirilen hekimler, aile hekimliği uzman hekiminin yazabildiği tüm ilaçları reçete edebilir; belirtilen SUT maddelerindeki ilaçlar sağlık raporuna istinaden bu hekimlerce veya aile hekimliği uzmanlarınca reçete edilirse bedelleri Kurumca ödenir (§4.1.1).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.2 — inpatient drug procurement / manual prescriptions (ek4a)
    # -------------------------------------------------------------------

    # C003428 — MANDATORY: inpatient drugs must be procured by contracted institutions (overseas excepted)
    {
        "rule_id": "4.1.2.inpatient_drug_procurement_mandatory",
        "sut_section": "4.1.2",
        "gate_b_sources": ["C003428"],
        "condition": {"inpatient_care": True, "procurement_by_contracted_institution": True},
        "action": {
            "enforcement": "mandatory: inpatient (admitted + day-care) drugs must be procured by contracted/protocol health institutions (overseas drugs not authorized for hospital use excepted)",
            "message_tr": "Yatarak tedavilerde kullanılacak ilaçların Kurumla sözleşmeli/protokollü sağlık kurum ve kuruluşlarınca temini zorunludur (Sağlık Bakanlığınca hastanede kullanılmasına izin verilen yurtdışı ilaçlar hariç) (§4.1.2).",
        },
    },

    # C003429 — MANDATORY: manual prescriptions for un-procured inpatient drugs need 'Yatan/Günübirlik Hasta' + chief-physician approval
    {
        "rule_id": "4.1.2.manual_prescription_inpatient_chief_approval_mandatory",
        "sut_section": "4.1.2",
        "gate_b_sources": ["C003429"],
        "condition": {"manual_prescription": True, "inpatient_care": True},
        "action": {
            "enforcement": "mandatory: manual prescriptions for inpatient drugs not procurable by contracted institutions must carry 'Yatan/Günübirlik Hasta' phrase + chief-physician approval; overseas-drug prescriptions do not require these",
            "message_tr": "Kurumla sözleşmeli/protokollü kuruluşlarca temin edilemeyen inpatient ilaçlar için düzenlenen manuel reçetelerde 'Yatan/Günübirlik Hasta' ibaresi ve başhekimlik onayı zorunludur; yurtdışı ilaç reçetelerinde bu ibare ve onay zorunlu değildir (§4.1.2).",
        },
    },

    # C003430 — COVERAGE: contracted-pharmacy supply of un-procured drugs, 5-day dose rules
    {
        "rule_id": "4.1.2.contracted_pharmacy_supply_coverage",
        "sut_section": "4.1.2",
        "gate_b_sources": ["C003430"],
        "condition": {"coverage_note": True, "max_days_per_dispense": 5},
        "action": {
            "enforcement": "coverage: drugs not procured by contracted institutions but supplied by contracted pharmacies are paid up to a 5-day dose (TB patients up to 1-month documented; chemotherapy course drugs up to 1-course amount), deducted from the institution; EK-4/H chemo drugs require chief-physician proof of non-procurement for refund w/ pharmacist margin removed; overseas / interim-payment drugs excepted",
            "message_tr": "Temin edilemeyip sözleşmeli eczanelerce karşılanan reçete ilaç bedelleri 5 günlük dozu aşmamak kaydıyla (uzun süre yatan tüberküloz hastalarına 1 aylık, kür protokolü ilaçlarda 1 küre yetecek miktarda) ödenir, ilgili kurumdan mahsup edilir; EK-4/H kemoterapi ilaçları başhekimlik onayıyla temin edilemedi belgelendirilirse eczacı kârı düşülerek iade edilir (yurtdışı/ara ödemeli ilaçlar hariç) (§4.1.2).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.3 — health report format / validity (ek4a)
    # -------------------------------------------------------------------

    # C003435 — MANDATORY: health report formats follow MoH + MEDULA rules
    {
        "rule_id": "4.1.3.health_report_format_moh_medula_mandatory",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003435"],
        "report_required": True,
        "action": {
            "enforcement": "mandatory: health report formats, attestations, stamps and other practices must comply with MoH legislation and MEDULA system rules",
            "message_tr": "Sağlık raporu formatları ile bu raporların tasdik, mühür ve diğer uygulamalarında Sağlık Bakanlığı mevzuatı ve MEDULA sistemindeki düzenlemelere uyulacaktır (§4.1.3).",
        },
    },

    # C003436 — REGULATORY_ACTION: reports per §1.10; specialist/board reports; electronic + chief-physician approval in MEDULA
    {
        "rule_id": "4.1.3.health_report_1_10_specialist_electronic",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003436"],
        "report_required": True,
        "action": {
            "enforcement": "regulatory: reports issued per SUT §1.10; per §1.10.1 by specialist physician, SUT §1.10.2 health-board reports also valid; MEDULA-using providers issue reports electronically and chief-physician approves electronically",
            "message_tr": "Sağlık raporlarının düzenlenmesinde SUT 1.10 maddesi dikkate alınır; bu raporlar SUT'taki istisnalar saklı kalmak kaydıyla 1.10.1 doğrultusunda uzman hekimce düzenlenir, 1.10.2'ye göre düzenlenen sağlık kurulu raporları da geçerlidir; MEDULA kullanan sunucular raporları elektronik düzenler ve başhekimlikçe elektronik onaylanır (§4.1.3).",
        },
    },

    # C003437 — REGULATORY_ACTION: active-substance name suffices; dose on prescription; report dose is upper limit
    {
        "rule_id": "4.1.3.report_active_substance_dose_rule",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003437"],
        "report_required": True,
        "action": {
            "enforcement": "regulatory: except drugs with special rules, report need not state dose — active substance name suffices; for such drugs dose/daily dose written on prescription; if dose is detailed in the report that dose cannot be exceeded",
            "message_tr": "Özel düzenlemesi olan ilaçlar hariç raporda doz belirtilmesi şart olmayıp etken madde adının yazılması yeterlidir; bu ilaçların etken madde miktarı ve günlük dozu reçeteyle düzenlenir; raporda doz ayrıntılı belirtilmişse bu doz aşılamaz (§4.1.3).",
        },
    },

    # C003438 — EXEMPTION: copay-exemption reports must carry diagnosis + ICD-10 code; no abbreviations
    {
        "rule_id": "4.1.3.copay_exemption_report_icd10_diagnosis",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003438"],
        "report_required": True,
        "condition": {"copay_exemption_report": True},
        "action": {
            "enforcement": "exemption: copay-exemption health reports must carry diagnosis and ICD-10 code; no abbreviations except those in EK-4/Ç; no abbreviations in active-substance name",
            "message_tr": "Hasta katılım payı muafiyeti için düzenlenen sağlık raporlarında teşhis ve ICD-10 kodu yer alır; SUT eki EK-4/Ç Listesi kısaltmaları hariç teşhislerde ve etken madde isminde kısaltma yapılmaz (§4.1.3).",
        },
    },

    # C003439 — REGULATORY_ACTION: reports valid up to 2 years except special rules
    {
        "rule_id": "4.1.3.report_max_2_year_validity",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003439"],
        "report_required": True,
        "report_duration_months": 24,
        "action": {
            "enforcement": "regulatory: health reports valid up to 2 years except drugs with special SUT provisions",
            "message_tr": "Sağlık raporları, SUT'ta yer alan özel düzenlemeler hariç en fazla iki yıl süreyle geçerlidir (§4.1.3).",
        },
    },

    # C003443 — REGULATORY_ACTION: report remains valid until expiry if SUT changes; non-conforming reports re-done per §4.1.3(6)
    {
        "rule_id": "4.1.3.report_validity_on_sut_change",
        "sut_section": "4.1.3",
        "gate_b_sources": ["C003443"],
        "report_required": True,
        "action": {
            "enforcement": "regulatory: on SUT change reports remain valid until expiry if they comply with new provisions; non-compliant reports become valid only if re-conformed under SUT §4.1.3(6) (except reports the Institution declares valid until expiry)",
            "message_tr": "Sağlık raporları SUT değişikliği olması halinde yeni hükümlere uygun olması kaydıyla süresi sonuna kadar geçerlidir; değişiklik sonrası SUT hükümlerine uygun olmayan raporlar 4.1.3(6) kapsamında yeni hükümlere uygun hale getirilebilirse geçerlidir (Kurumca süresi sonuna kadar geçerli duyurulanlar hariç) (§4.1.3).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.4 — drugs without report / off-label use / dispense amounts (ek4a)
    # -------------------------------------------------------------------

    # C003447 — COVERAGE: parenteral forms + magistrals without report — up to 10-day tx cost
    {
        "rule_id": "4.1.4.parenteral_magistral_no_report_10day_coverage",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003447"],
        "condition": {"coverage_note": True, "max_days_per_dispense": 10},
        "action": {
            "enforcement": "coverage: parenteral forms + magistrals written without health report paid up to 10-day treatment cost; daily dose mandatory on prescription; magistrals paid only when prescribed by relevant specialist physician, treatment duration + purpose stated; magistral pricing uses MEDULA tariff, Institution-set ceiling",
            "message_tr": "Sağlık raporu olmaksızın ilaçların parenteral formları ile majistrallerin reçeteye yazılması halinde en fazla 10 günlük tedavi bedeli ödenir; reçetede günlük doz belirtilir; majistraller sadece ilgili uzman hekimlerce reçete edilirse ödenir, tedavi süresi/amacı reçetede belirtilir; majistral fiyatlandırması MEDULA tarife/fiyat/miktar esas alınır, Kurumca belirlenen tutarı geçemez (§4.1.4).",
        },
    },

    # C003468 — NO_PAY: drug used outside licensed indication but SUT special rule — off-label use OK w/ MoH approval; but in indication with no SUT condition = no pay
    {
        "rule_id": "4.1.4.offlabel_no_sut_condition_nopay",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003468"],
        "condition": {"off_label_use": True},
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: use outside licensed indication but with a SUT special-provision condition requires MoH patient-based off-label approval; however if the drug IS in its licensed indication but the indication has NO SUT condition, cost is NOT covered",
            "message_tr": "Bir ilacın ülkemizde onaylanmış endikasyonunda tanımlı olmayıp SUT'ta özel düzenleme koşulu dışında kullanımı Sağlık Bakanlığınca hasta bazında endikasyon dışı kullanım onayıyla mümkündür; ancak ilacın ödeme kapsamına alındığı tarihte ülkemizde onaylı endikasyonunda tanımlı olmasına rağmen SUT'ta koşulu olmayan endikasyonlarda kullanılması halinde bedeli Kurumca karşılanmaz (§4.1.4).",
        },
    },

    # C003472 — COVERAGE: EK-4/A drug gains new licensed indication — covered with MoH off-label approval pending reimbursement review
    {
        "rule_id": "4.1.4.ek4a_new_indication_offlabel_coverage",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003472"],
        "condition": {"coverage_note": True, "off_label_use": True},
        "action": {
            "enforcement": "coverage: EK-4/A drug with SUT provision gains a new licensed indication after the provision's effective date — from refund-management application date until review finalization, with MoH patient-based off-label approval, the new KÜB indication is covered",
            "message_tr": "EK-4/A'da yer alan ve SUT'ta düzenlemesi olan ilaçlarda, yürürlük tarihinden sonra Sağlık Bakanlığınca yeni ruhsatlı endikasyon eklendiğinde, başvuru tarihinden sonuçlandırılmasına kadar geçen sürede Bakanlıkça şahıs bazında endikasyon dışı kullanım onayı olması halinde bedeli Kurumca karşılanır (§4.1.4).",
        },
    },

    # C003473 — NO_PAY: indication defined in licensed KUB but not reimbursed = no pay
    {
        "rule_id": "4.1.4.non_reimbursed_indication_kub_nopay",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003473"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: use of a drug in an indication defined in the licensed KUB but not taken into reimbursement scope by the Commissions is not covered",
            "message_tr": "Bir ilacın ülkemizde onaylanmış Kısa Ürün Bilgisinde tanımlı olup ilgili Komisyonlarca geri ödeme kapsamına alınmayan endikasyonlarda kullanılması halinde ilacın bedeli Kurumca karşılanmaz (§4.1.4).",
        },
    },

    # C003481 — COVERAGE: first-time drugs paid per dose up to 1 month; 4-week pack counts as 1 month
    {
        "rule_id": "4.1.4.first_prescription_1month_dose_coverage",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003481"],
        "condition": {"coverage_note": True, "max_days_per_dispense": 30},
        "action": {
            "enforcement": "coverage: first-time drugs, even if reported, are paid by usage dose in periods not exceeding 1 month; pack size reaching 4-week dose counts as 1-month dose; subsequent prescriptions follow general/special SUT provisions; different pharmaceutical doses on continuation count as first treatment",
            "message_tr": "İlk defa reçete edilecek ilaçlar raporlu olsa dahi kullanım dozuna göre bir ayı geçmeyecek sürelerde ödenir; 4 haftalık doza yetecek miktardaki ambalaj 1 aylık doz sayılır; sonraki reçetelerde SUT genel/özel düzenlemeleri esas alınır; devam reçetelerindeki farklı farmasötik dozlar da ilk tedavi sayılır (§4.1.4).",
        },
    },

    # C003482 — COVERAGE: course-protocol drugs paid one course amount per use
    {
        "rule_id": "4.1.4.course_protocol_one_course_coverage",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003482"],
        "condition": {"coverage_note": True, "course_protocol": True},
        "action": {
            "enforcement": "coverage: course-protocol drugs paid one-course amount per each use",
            "message_tr": "Kür protokolü uygulanan ilaçlarda her kullanımda 1 küre yetecek miktarda ilacın bedeli ödenir (§4.1.4).",
        },
    },

    # C003483 — COVERAGE: topical antifungals (same form+active) — up to 6 months, ≤2 boxes per Rx; excess needs derm/OBGYN
    {
        "rule_id": "4.1.4.topical_antifungal_6month_2box_coverage",
        "sut_section": "4.1.4",
        "gate_b_sources": ["C003483"],
        "drug_names": ["topikal antifungal"],
        "prescriber_specialties": ["dermatoloji", "kadın hastalıkları ve doğum"],
        "condition": {"coverage_note": True, "max_boxes_per_dispense": 2, "max_supply_months": 6},
        "action": {
            "enforcement": "coverage: topical antifungals (same form + active substance) up to 6-month total amount, max 2 boxes per prescription; above the box count or >6-month tx requires prescription by dermatology or (in OBGYN indication) OBGYN specialist, OR a 6-month specialist report enabling any physician to prescribe",
            "message_tr": "Aynı farmasötik form ve etkin maddeye sahip topikal antifungallerden toplamda 6 aylık dozda ve bir reçetede en fazla 2 kutu yazılabilir; üst sınırı aşan kullanımda veya 6 aydan uzun sürmesi gereken hallerde dermatoloji veya endikasyona göre kadın hastalıkları ve doğum uzmanınca reçete edilmesi, ya da bu uzmanların 6 ay süreli raporuna istinaden tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.1.4).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.5 — e-prescription rules (ek4a)
    # -------------------------------------------------------------------

    # C003485 — MANDATORY: e-prescriptions must be signed per Institution method/standards (e-signature/password)
    {
        "rule_id": "4.1.5.eprescription_signing_method_mandatory",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003485"],
        "condition": {"e_prescription": True},
        "action": {
            "enforcement": "mandatory: e-prescriptions must be signed by the Institution-determined methods/standards (electronic signature, password)",
            "message_tr": "E-reçete uygulamasında e-reçetelerin Kurumun belirlediği yöntem ve standartlarla (elektronik imza, şifre) imzalanması şarttır (§4.1.5).",
        },
    },

    # C003486 — REGULATORY_ACTION: prescriptions issued with SGK physician password; manual/manual-entry prescriptions not paid except exceptions
    {
        "rule_id": "4.1.5.sgk_password_manual_nopay",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003486"],
        "pay": False,
        "condition": {"manual_prescription": True},
        "action": {
            "enforcement": "regulatory/no-pay: institution prescriptions issued with SGK physician password; manual prescriptions and pharmacy manual-entry prescriptions are NOT covered except Institution-determined exceptions; after Institution arrangements, prescriptions signed with electronic signature from a set date",
            "message_tr": "Sağlık kuruluşlarınca düzenlenecek reçeteler SGK Hekim Şifresi ile düzenlenir; Kurumca belirlenen istisnalar hariç manuel reçetelerin bedelleri karşılanmaz; eczanelerce manuel giriş yapılan reçetelerin bedelleri karşılanmaz; gerekli düzenleme sonrası reçeteler belirlenen tarihten itibaren elektronik imzayla imzalanır (§4.1.5).",
        },
    },

    # C003493 — MANDATORY: family-physician 'gezici sağlık hizmeti' prescriptions (must carry phrase + physician approval)
    {
        "rule_id": "4.1.5.family_physician_mobile_health_service_mandatory",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003493"],
        "prescriber_specialties": ["aile hekimi"],
        "condition": {"mobile_health_service_prescription": True},
        "action": {
            "enforcement": "mandatory: family-physician 'gezici (mobile) health service' prescriptions — must carry the phrase indicating they are issued under mobile health service and be physician-approved",
            "message_tr": "Aile hekimlerince 'gezici sağlık hizmeti' kapsamında düzenlenen reçeteler (reçetenin gezici sağlık hizmeti kapsamında düzenlendiğini belirten ibarenin bulunması ve hekimce onaylanması zorunludur) (§4.1.5).",
        },
    },

    # C003495 — MANDATORY: prescriptions from various official/private settings (institution/occupational physicians, municipality polyclinics, care homes, etc.) — e-prescription once MEDULA infra ready
    {
        "rule_id": "4.1.5.official_private_setting_prescriptions_mandatory",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003495"],
        "condition": {"e_prescription": True},
        "action": {
            "enforcement": "mandatory: prescriptions issued in various official/private settings (institution physicians, occupational physicians, municipality polyclinics, care homes, non-family-medicine primary-care public providers, university medico-social units, TSK first-line providers) — once they start using MEDULA hospital system or build infrastructure they must move to e-prescription",
            "message_tr": "Resmi ve özel sağlık kuruluşlarından; kamu idareleri bünyesindeki kurum hekimliklerinde, işyeri hekimliklerinde, belediyelere ait polikliniklerde, huzur evlerinde, aile hekimliği dışındaki birinci basamak resmi sunucularda, üniversitelerin mediko-sosyal birimlerinde, TSK'nın birinci basamak sunucularında düzenlenen reçeteler (MEDULA hastane sistemini kullanmaya başlamaları veya teknik altyapı oluşturmaları halinde e-reçeteye geçmeleri zorunludur) (§4.1.5).",
        },
    },

    # C003500 — COVERAGE: red/purple/orange/green prescriptions paid as e-prescription; matbu paid only on MEDULA-system-outage notice
    {
        "rule_id": "4.1.5.colored_prescription_eprescription_coverage",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003500"],
        "condition": {"coverage_note": True, "e_prescription": True},
        "action": {
            "enforcement": "coverage: red/purple/orange/green prescriptions paid when issued as e-prescription; matbu (printed) colored prescriptions paid only based on the Institution's official-website notice that MEDULA-system causes prevented e-prescription issuance in the stated periods",
            "message_tr": "Kırmızı, mor, turuncu ve yeşil reçetelerin elektronik reçete olarak düzenlenmesi halinde bedelleri Kurumca karşılanır; bu renkli matbu reçetelerin bedelleri, MEDULA kaynaklı nedenlerle (belirtilen sürelerde) e-reçete düzenlenemediğine dair Kurumun resmi internet sitesindeki duyurusuna istinaden karşılanır (§4.1.5).",
        },
    },

    # C003505 — MANDATORY: overseas-duty personnel must state official document date/number on e-prescription
    {
        "rule_id": "4.1.5.overseas_duty_official_document_mandatory",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003505"],
        "condition": {"overseas_duty_personnel": True, "e_prescription": True},
        "action": {
            "enforcement": "mandatory: personnel sent on continuous overseas duty must state the date and number of the overseas-duty official document on the e-prescription",
            "message_tr": "Sürekli görevle yurt dışına gönderilenlerin yurt dışı görevine dair resmi belgenin tarih ve sayısının e-reçetede belirtilmesi zorunludur (§4.1.5).",
        },
    },

    # C003524 — NO_PAY: work-accident / occupational disease / forensic / traffic-accident cases — e-prescription only; manual = no pay
    {
        "rule_id": "4.1.5.work_accident_forensic_eprescription_only_nopay",
        "sut_section": "4.1.5",
        "gate_b_sources": ["C003524"],
        "pay": False,
        "condition": {"manual_prescription": True, "work_accident_or_forensic_case": True},
        "action": {
            "enforcement": "no-pay condition: work accident, occupational disease, forensic case and traffic-accident cases — prescriptions ONLY as e-prescription; manual (non-e) prescriptions are NOT covered",
            "message_tr": "İş kazası, meslek hastalığı, adli vaka ve trafik kazası durumlarında reçeteler sadece e-reçete olarak düzenlenir; e-reçete haricinde manuel reçetelerin bedelleri Kurumca karşılanmaz (§4.1.5).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.6 — EK-4/D chronic-disease drug supply (ek4a)
    # -------------------------------------------------------------------

    # C003526 — COVERAGE: EK-4/D chronic-disease drugs paid up to 3-month dose per report; specialists up to 1-year Rx, ≤3-month pharmacy supply
    {
        "rule_id": "4.1.6.ek4d_chronic_3month_dose_coverage",
        "sut_section": "4.1.6",
        "gate_b_sources": ["C003526"],
        "report_required": True,
        "report_duration_months": 12,
        "condition": {"coverage_note": True, "max_days_per_dispense": 90, "ek4d_list": True},
        "action": {
            "enforcement": "coverage: EK-4/D disease drugs paid up to 3-month treatment dose per health report; specialists of the branches that may report per SUT may prescribe up to 1-year dose, with pharmacy supply of up to 3-month amounts during the Rx period; EXCLUDES colored-receipt drugs, off-label-approval drugs, overseas-procured drugs, §4.2.1/4.2.10/4.2.14 drugs and Institution-designated drugs",
            "message_tr": "EK-4/D Listesindeki hastalıklarda kullanılacak ilaçlar sağlık raporuna dayanılarak en fazla 3 aylık tedavi dozunda reçete edilirse ödenir; ilgili uzmanlık dallarınca en fazla 1 yıllık dozda reçete ve bu reçeteye istinaden en fazla üçer aylık dozda sözleşmeli eczanelerden temini halinde Kurumca ödenir; renkli reçeteli, endikasyon dışı onaylı, yurt dışından temin edilen ve 4.2.1/4.2.10/4.2.14 ilaçları ile Kurumca belirlenecek ilaçlar hariçtir (§4.1.6).",
        },
    },

    # C003527 — NO_COPAY: EK-4/D substances with matching-diagnosis report — drugs exempt from copay
    {
        "rule_id": "4.1.6.ek4d_copay_exempt",
        "sut_section": "4.1.6",
        "gate_b_sources": ["C003527"],
        "report_required": True,
        "condition": {"copay_exempt": True, "ek4d_list": True},
        "action": {
            "enforcement": "no-copay: for EK-4/D listed active substances, when a health report is issued matching the diagnoses under the relevant heading, drugs prescribed on that report are exempt from patient copay",
            "message_tr": "EK-4/D Listesindeki etken maddeler için ilgili başlıktaki tanılara uygun sağlık raporu düzenlenmesi halinde bu rapora istinaden reçete edilen ilaçlar katılım payından muaf tutulur (§4.1.6).",
        },
    },

    # C003529 — COVERAGE: overseas-duty personnel + dependents — EK-4/D drugs up to 1-year dose per Rx + report + overseas-duty document
    {
        "rule_id": "4.1.6.ek4d_overseas_duty_1year_coverage",
        "sut_section": "4.1.6",
        "gate_b_sources": ["C003529"],
        "report_required": True,
        "condition": {"coverage_note": True, "max_days_per_dispense": 365, "ek4d_list": True, "overseas_duty_personnel": True},
        "action": {
            "enforcement": "coverage: overseas-duty personnel + co-resident spouse/dependents — EK-4/D drugs paid up to 1-year treatment dose per patient-named prescription + health report + overseas-duty official document; if SUT report duration <1 year, drugs given for report duration",
            "message_tr": "Sürekli görevle yurt dışına gönderilenler ile yurt dışında birlikte yaşadıkları eş ve bakmakla yükümlü olduğu kişilere, EK-4/D hastalıklarında kullanılacak ilaçların hasta adına düzenlenmiş reçete, sağlık raporu ve yurt dışı görevine dair resmi belge ibrazına dayanılarak en fazla bir yıllık tedavi dozunda reçete edilmesi halinde bedelleri ödenir (SUT'ta süresi 1 yıldan az olan raporlarda rapor süresi kadar ilaç verilir) (§4.1.6).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.7 — EK-4/G drugs: hospital-only procurement (ek4a)
    # -------------------------------------------------------------------

    # C003533 — NO_PAY: EK-4/G drugs follow §4.1.2; outpatient prescription = no pay
    {
        "rule_id": "4.1.7.ek4g_outpatient_prescription_nopay",
        "sut_section": "4.1.7",
        "gate_b_sources": ["C003533"],
        "pay": False,
        "condition": {"outpatient_care": True, "ek4g_list": True},
        "action": {
            "enforcement": "no-pay condition: EK-4/G drugs follow SUT §4.1.2 principles; with SUT special provisions reserved, when prescribed in outpatient treatment the cost is NOT covered",
            "message_tr": "EK-4/G Listesindeki ilaçların reçete edilmesinde SUT 4.1.2 esaslarına uyulur; özel hükümler saklı kalmak kaydıyla ayakta tedavilerde reçete edilmesi halinde bu ilaçların bedeli ödenmez (§4.1.7).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.8 — EK-4/F outpatient report drugs (ek4a)
    # -------------------------------------------------------------------

    # C003535 — COVERAGE: EK-4/F outpatient-report drugs — any physician may prescribe per report; up to 3-month dose
    {
        "rule_id": "4.1.8.ek4f_outpatient_report_3month_coverage",
        "sut_section": "4.1.8",
        "gate_b_sources": ["C003535"],
        "report_required": True,
        "condition": {"coverage_note": True, "max_days_per_dispense": 90, "ek4f_list": True},
        "action": {
            "enforcement": "coverage: EK-4/F 'outpatient-report drugs' — when outpatient use is needed, per SUT special provisions, any physician may prescribe on the health report; paid up to 3-month treatment dose",
            "message_tr": "EK-4/F 'Ayakta Tedavide Sağlık Raporu ile Verilebilecek İlaçlar Listesi' ilaçlarının ayakta tedavide kullanımı gerektiği durumlarda, düzenlenen sağlık raporuna dayanılarak tüm hekimlerce reçete edilebilir; en fazla 3 aylık tedavi dozunda reçete edilmesi halinde bedelleri ödenir (§4.1.8).",
        },
    },

    # C003537 — NO_COPAY: EK-4/F drugs — copay taken unless also in EK-4/D
    {
        "rule_id": "4.1.8.ek4f_copay_unless_ek4d",
        "sut_section": "4.1.8",
        "gate_b_sources": ["C003537"],
        "condition": {"ek4f_list": True, "copay_exempt": False},
        "action": {
            "enforcement": "no-copay rule: EK-4/F drugs that are NOT in EK-4/D incur patient copay; those that are also within EK-4/D scope do not incur copay",
            "message_tr": "EK-4/F Listesinde yer alıp EK-4/D Listesinde yer almayan ilaçlardan hasta katılım payı alınır, EK-4/D kapsamında olanlardan ise katılım payı alınmaz (§4.1.8).",
        },
    },

    # -------------------------------------------------------------------
    # §4.1.9 — EK-4/A payable drug list (ek4a)
    # -------------------------------------------------------------------

    # C003540 — NO_PAY: drugs not in EK-4/A (no trade name/barcode) = never paid; overseas drugs excepted
    {
        "rule_id": "4.1.9.non_ek4a_drug_nopay",
        "sut_section": "4.1.9",
        "gate_b_sources": ["C003540"],
        "pay": False,
        "condition": {"not_in_ek4a_list": True},
        "action": {
            "enforcement": "no-pay condition: Institution-paid drugs are listed in EK-4/A 'Bedeli Ödenecek İlaçlar Listesi'; drugs without trade name and barcode/QR in this list are NEVER paid under any condition; overseas-procured drugs have special provisions reserved",
            "message_tr": "Kurumca bedeli ödenecek ilaçlar EK-4/A 'Bedeli Ödenecek İlaçlar Listesi'nde belirtilmiştir; ticari isimleri ve barkod/karekod numaraları bu listede yer almayan ilaçların bedelleri hiçbir koşulda Kurumca ödenmez; yurt dışından temin edilen ilaçlar için özel düzenlemeler saklıdır (§4.1.9).",
        },
    },

    # -------------------------------------------------------------------
    # §4.3 — overseas drug procurement (overseas-drug)
    # -------------------------------------------------------------------

    # C007288 — PERMISSION: overseas procurement of drugs not available domestically, MoH approval + TEB protocol
    {
        "rule_id": "4.3.overseas_procurement_permission",
        "sut_section": "4.3",
        "gate_b_sources": ["C007288"],
        "condition": {"overseas_drug": True},
        "action": {
            "enforcement": "permission: drugs needed for Institution beneficiaries and not procurable domestically may be procured from overseas when MoH confirms domestic unavailability + mandatory use and grants supply permission; a protocol between TEB and the Institution is in force; MoH may authorize other parties via legislation",
            "message_tr": "Kurum sağlık yardımlarından yararlandırılan kişiler için gerekli görülen ve yurt içinden sağlanması mümkün olmayan ilaçların, yurt içinde bulunmadığı ve kullanılmasının zorunlu olduğu Sağlık Bakanlığınca onaylanarak teminine izin verildiği takdirde yurt dışından temini mümkündür; bu amaçla TEB ile Kurum arasında protokol yürürlüktedir; Bakanlıkça yetkilendirilen diğer taraflarla da protokol yapılabilir (§4.3).",
        },
    },

    # C007290 — NO_PAY: overseas drugs not in EK-4/C = no pay; listing needs tertiary health-board report + tertiary Rx
    {
        "rule_id": "4.3.non_ek4c_overseas_drug_nopay",
        "sut_section": "4.3",
        "gate_b_sources": ["C007290"],
        "pay": False,
        "condition": {"overseas_drug": True, "not_in_ek4c_list": True},
        "action": {
            "enforcement": "no-pay condition: overseas-procured payable drugs are listed in EK-4/C 'Yurt Dışı İlaç Fiyat Listesi'; drugs not in the list are NOT covered (list published on Institution website); for EK-4/C inclusion applications (equivalent-drug registrations excepted) a tertiary public-provider health-board report + tertiary public-provider prescription must be submitted to the Institution",
            "message_tr": "Yurt dışından temini halinde bedeli ödenecek ilaçlar EK-4/C 'Yurt Dışı İlaç Fiyat Listesi'nde belirtilmiştir; listede yer almayan ilaçların bedelleri Kurumca ödenmez; EK-4/C'ye alınma başvurularının (eşdeğer ilaç kaydı hariç) değerlendirilebilmesi için üçüncü basamak resmi sunucuda düzenlenmiş sağlık kurulu raporu ve reçetesinin Kuruma ibrazı gerekir (§4.3).",
        },
    },

    # C007291 — COVERAGE: EK-4/C drugs self-procured (domestic/overseas) — paid via bank to beneficiary; ceiling = Institution cost
    {
        "rule_id": "4.3.ek4c_self_procured_bank_payment_coverage",
        "sut_section": "4.3",
        "gate_b_sources": ["C007291"],
        "condition": {"coverage_note": True, "overseas_drug": True},
        "action": {
            "enforcement": "coverage: EK-4/C drugs procured by beneficiary's own means (domestic/overseas) — drug cost paid via bank to the beneficiary under Institution legislation; amount cannot exceed the Institution's cost-of-supply for the same drug (incl. different-financial-model drugs); for different-financial-model overseas drugs, paid at cost-of-supply if protocol-supplier unavailability within protocol period is documented",
            "message_tr": "EK-4/C'deki ilaçların kişinin kendi imkânlarıyla (yurt içinden/dışından) temini halinde ilaç bedelleri Kurumca belirlenen mevzuat kapsamında hak sahibi adına banka aracılığıyla ödenir; ödenecek bedel aynı ilacın Kuruma mal oluş bedelini geçemez; farklı finansal model kapsamındaki yurtdışı ilaçlarının kişilerce temini halinde protokol tedarikçiden belirlenen sürede temin edilemediği belgelendirilirse Kuruma mal oluş bedeli üzerinden ödenir (§4.3).",
        },
    },

    # C007292 — NO_COPAY: EK-4/C drugs that are in EK-4/D scope — no patient copay
    {
        "rule_id": "4.3.ek4c_ek4d_copay_exempt",
        "sut_section": "4.3",
        "gate_b_sources": ["C007292"],
        "condition": {"copay_exempt": True, "overseas_drug": True, "ek4d_list": True},
        "action": {
            "enforcement": "no-copay: among overseas drugs, those that fall within EK-4/D scope do not incur patient copay",
            "message_tr": "Bu ilaçlardan EK-4/D Listesi kapsamında olanlardan hasta katılım payı alınmaz (§4.3).",
        },
    },

    # C007293 — COVERAGE: overseas drugs per specialist report — up to 90-day Rx by specialists
    {
        "rule_id": "4.3.overseas_drug_specialist_report_90day_coverage",
        "sut_section": "4.3",
        "gate_b_sources": ["C007293"],
        "report_required": True,
        "report_specialties": ["uzman hekim"],
        "prescriber_specialties": ["uzman hekim"],
        "condition": {"coverage_note": True, "overseas_drug": True, "max_days_per_dispense": 90},
        "action": {
            "enforcement": "coverage: overseas-treatment drugs per specialist-physician report (with SUT special provisions reserved) — specialists may prescribe up to 90-day dose; report must state active substance, daily dose, application plan and duration",
            "message_tr": "Tedavi için yurt dışından getirtilecek ilaçların, uzman hekim raporuna dayanılarak uzman hekimlerce en fazla 90 günlük doza kadar reçete edilmesi halinde bedelleri ödenir; raporda etken madde, günlük doz, uygulama planı ve süresi belirtilir (§4.3).",
        },
    },

    # C007297 — NO_COPAY: drugs procured overseas with MoH permission that gain domestic license/distribution — per-prescription ≤1-month, EK-4/D = no copay
    {
        "rule_id": "4.3.overseas_licensed_distributed_copay_exempt",
        "sut_section": "4.3",
        "gate_b_sources": ["C007297"],
        "report_required": True,
        "report_specialties": ["uzman hekim"],
        "prescriber_specialties": ["uzman hekim"],
        "condition": {"overseas_drug": True, "copay_exempt": True, "ek4d_list": True, "max_days_per_dispense": 30},
        "action": {
            "enforcement": "no-copay/coverage: drugs procured overseas with MoH permission that later gain domestic license + distribution document — from EK-4/A entry-request date (distribution doc date basis), within max review period, per specialist report + MoH use approval, specialists may prescribe up to 1-month amounts during the approval period; MoH retail price with §4.4.1 discounts (incl. special) then tiered pharmacy discount, paid per beneficiary invoices; per-box cap = EK-4/C price after §4.4.1 base discount; EK-4/D-scope drugs incur no patient copay; §4.5.2(1) 4-business-day period does not apply; report + Rx must be after MoH use-approval date",
            "message_tr": "Bakanlık izniyle yurt dışından temin edilen ilacın ülkemizde ruhsat alıp dağıtım belgesi alması halinde, dağıtım belgesi tarihi esas alınarak EK-4/A giriş talebinden sonuçlandırılacağı maksimum süre içinde, uzman hekim raporu ve Bakanlık kullanım onayına dayanılarak onayda belirtilen süre boyunca uzman hekimlerce en fazla birer aylık miktarlarda reçete edilmesi koşuluyla, Bakanlık perakende satış fiyatı üzerinden §4.4.1 indirimleri (özel iskontolar dahil) uygulanıp kademeli eczane iskontosu uygulanarak sözleşmeli eczane faturalarına dayanılarak ödeme yapılır; her kutu için EK-4/C kayıtlı fiyatın §4.4.1 baz iskonto sonrası tutarından fazla ödenemez; EK-4/D kapsamında olanlardan katılım payı alınmaz; §4.5.2(1) 4 iş günlük süre aranmaz; rapor ve reçetenin onay tarihi sonrası düzenlenmesi esastır (§4.3).",
        },
    },

    # -------------------------------------------------------------------
    # §4.4.1 — public-institution drug discounts (drug_discount_prose)
    # -------------------------------------------------------------------

    # C007725 — REGULATORY_ACTION: discount determination uses MoH reference/equivalent/price-protected rules; Institution evaluates status changes
    {
        "rule_id": "4.4.1.discount_reference_basis_regulatory",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C007725"],
        "action": {
            "enforcement": "regulatory: in the public-institution discounts and additional-discount provisions, reference/equivalent/price-protected status is determined per MoH legislation; discount applications for status changes are evaluated by the Institution",
            "message_tr": "Kamu kurum iskontoları ve ilave iskonto uygulamalarında ilaçların referans, eşdeğer, fiyat korumalı gibi durumlarının belirlenmesinde Sağlık Bakanlığı düzenlemeleri esas alınır; durum değişikliklerine ilişkin iskonto uygulamaları Kurumca değerlendirilir (§4.4.1).",
        },
    },

    # C007745 — NO_COPAY/exemption: new molecules / therapy-innovation products in EK-4/A exempt from additional discounts for 1 year
    {
        "rule_id": "4.4.1.new_molecule_1year_additional_discount_exempt",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C007745"],
        "condition": {"new_molecule_ek4a_entry": True, "additional_discount_exempt_months": 12},
        "action": {
            "enforcement": "exemption: new molecules / therapy-innovation products not previously in EK-4/A, upon admission, are exempt from additional discounts for 1 year from entry date; for §4.3(8)-paid drugs this period starts from EK-4/A entry-request date; the 1-year exemption per molecule ends when the period for the first-entering pharmaceutical form across all forms ends",
            "message_tr": "Piyasaya verilecek, EK-4/A'da bulunmayan yeni moleküller ile tedaviye yenilik getirecek ürünlerin EK-4/A'ya kabulü halinde, listeye girdiği tarihten itibaren 1 yıl ilave iskontolardan muaf tutulur; §4.3 sekizinci fıkra kapsamında ödenen ilaçlar için bu süre EK-4/A giriş talep tarihinden başlar; molekülün ilave iskontodan muafiyet süresi tüm farmasötik formlar için listeye ilk giren formun süresi bitiminde sona erer (§4.4.1).",
        },
    },

    # C007747 — PROHIBITED: contracted providers may not charge patients the gap between purchase price and Institution max price
    {
        "rule_id": "4.4.1.provider_cannot_charge_price_gap_prohibited",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C007747"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: outpatient/inpatient contracted providers invoice their own-pharmacy-supplied drugs at the equivalent-drug max unit price per the above rules, applying public discount + 3.5% pharmacist discount; if a gap exists between purchase price and equivalent-drug max paid price, the difference may NOT be charged to the person; 'depocu fiyatlı ilaçlar' (no free-pharmacy sale) are billed at depot price with EK-4/A discounts (incl. special), no pharmacist discount",
            "message_tr": "Ayakta/yatarak tedavi sunan sözleşmeli sunucular, kendi eczanelerinden temin ettikleri ilaçları da Kurum eşdeğer ilaç azami birim bedeli esas alınarak kamu kurum iskontosu ve %3,5 eczacı indirimi uygulanarak fatura eder; satın alma bedeli ile eşdeğer ilacın Kurumca ödenen azami fiyatı arasındaki fark kişilerden talep edilemez; serbest eczane satışı olmayan 'depocu fiyatlı ilaçlar'a depocu satış fiyatı üzerinden EK-4/A indirimleri (özel iskontolar dahil) uygulanır, ek olarak eczacı indirimi uygulanmaz (§4.4.1).",
        },
    },

    # C008258 — REGULATORY_ACTION: discount determination uses MoH rules (duplicate provision variant)
    {
        "rule_id": "4.4.1.discount_reference_basis_regulatory_dup",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C008258"],
        "action": {
            "enforcement": "regulatory (duplicate provision): public-institution discounts and additional discounts — reference/equivalent/price-protected status per MoH legislation; status-change discounts evaluated by the Institution",
            "message_tr": "Kamu kurum iskontoları ve ilave iskonto uygulamalarında ilaçların referans, eşdeğer, fiyat korumalı durumlarının belirlenmesinde Sağlık Bakanlığı düzenlemeleri esas alınır; durum değişikliklerine ilişkin iskonto uygulamaları Kurumca değerlendirilir (§4.4.1).",
        },
    },

    # C008278 — NO_COPAY/exemption: new-molecule 1-year additional-discount exemption (duplicate provision variant)
    {
        "rule_id": "4.4.1.new_molecule_1year_additional_discount_exempt_dup",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C008278"],
        "condition": {"new_molecule_ek4a_entry": True, "additional_discount_exempt_months": 12},
        "action": {
            "enforcement": "exemption (duplicate provision): new molecules / therapy-innovation products admitted to EK-4/A exempt from additional discounts for 1 year; §4.3(8)-paid drugs start from EK-4/A entry-request date; exemption ends when the first-entering form's period ends",
            "message_tr": "Yeni moleküller ile tedaviye yenilik getirecek ürünlerin EK-4/A'ya kabulü halinde listeye girdiği tarihten itibaren 1 yıl ilave iskontolardan muaf tutulur; §4.3 sekizinci fıkra kapsamındaki ilaçlar için EK-4/A giriş talep tarihinden başlar; muafiyet süresi ilk giren formun süresi bitiminde sona erer (§4.4.1).",
        },
    },

    # C008280 — PROHIBITED: providers cannot charge the price gap (duplicate provision variant)
    {
        "rule_id": "4.4.1.provider_cannot_charge_price_gap_prohibited_dup",
        "sut_section": "4.4.1",
        "gate_b_sources": ["C008280"],
        "pay": False,
        "action": {
            "enforcement": "prohibited (duplicate provision): contracted providers invoice own-pharmacy drugs at equivalent-drug max unit price with public discount + 3.5% pharmacist discount; the gap between purchase and max-paid price may NOT be charged to the person; 'depocu fiyatlı ilaçlar' use depot price + EK-4/A discounts, no pharmacist discount",
            "message_tr": "Sözleşmeli sunucular kendi eczanelerinden temin ettikleri ilaçları eşdeğer ilaç azami birim bedeli üzerinden kamu kurum iskontosu ve %3,5 eczacı indirimiyle fatura eder; satın alma bedeli ile azami ödenen fiyat arasındaki fark kişilerden talep edilemez; 'depocu fiyatlı ilaçlar'a depocu satış fiyatı üzerinden EK-4/A indirimleri uygulanır, eczacı indirimi uygulanmaz (§4.4.1).",
        },
    },

    # -------------------------------------------------------------------
    # §4.4.2 — internal reference pricing (ek4a / drug_discount_prose)
    # -------------------------------------------------------------------

    # C007788 — PROHIBITED: internal reference pricing — equivalence-group substitution; some Institution groups NOT substitutable
    {
        "rule_id": "4.4.2.internal_reference_pricing_substitution_prohibited",
        "sut_section": "4.4.2",
        "gate_b_sources": ["C007788"],
        "action": {
            "enforcement": "prohibited/rule: internal reference pricing — equivalent-group application groups same-active-same-dose same-dosage-form drugs; these ARE substitutable in pharmacy; the Institution may also form non-substitutable groups (per rational-use commissions w/ MoH) for drugs whose access would not be hindered",
            "message_tr": "İç referans fiyatlandırması kapsamında eşdeğer grup uygulaması, aynı etkin maddeyi aynı dozda içeren benzer dozaj formundaki ilaçları aynı eşdeğer grupta değerlendirir, bu gruptaki ilaçlar eczanede ikame edilebilir; Kurum akılcı ilaç kullanımı çerçevesinde Bakanlığın da yer aldığı komisyonlarla erişimde zorluk oluşturmayacak ilaçlar için gruplar oluşturabilir, bu gruptakiler eczanede ikame edilemez (§4.4.2).",
        },
    },

    # C007789 — REGULATORY_ACTION: internal-reference-pricing payments use cheapest-group + 6% buffer
    {
        "rule_id": "4.4.2.internal_reference_pricing_6pct_buffer_regulatory",
        "sut_section": "4.4.2",
        "gate_b_sources": ["C007789"],
        "action": {
            "enforcement": "regulatory: in payments for internal-reference-pricing drugs, considering the drug having ≥1% market share, up to 6% above the group's cheapest drug price is taken into account",
            "message_tr": "İç referans fiyatlandırması uygulaması kapsamındaki ilaç ödemelerinde, ilacın %1 pazar payına sahip olması hususu gözetilerek grubun en ucuz ilaç bedelinin %6 fazlasına kadarı dikkate alınır (§4.4.2).",
        },
    },

    # C007790 — NO_PAY: internal-reference-pricing group — amount above max unit price (cheapest+6%) per box NOT paid
    {
        "rule_id": "4.4.2.internal_reference_pricing_excess_nopay",
        "sut_section": "4.4.2",
        "gate_b_sources": ["C007790"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: in internal-reference-pricing groups, discounted unit prices (after §4.4.1 public discount) compared to find cheapest; +6% added to find max payable unit price; per-box price derived per pack form is compared with the drug's public price — the portion of public price exceeding the max-unit-derived box price is NOT paid",
            "message_tr": "Bu kapsamdaki gruplarda §4.4.1 kamu kurum iskontosuyla hesaplanan kamu fiyatı üzerinden gruptaki ilaçların ortak en küçük birimi başına 'indirimli birim bedelleri' karşılaştırılarak en ucuz birim bedel bulunur; buna %6 ilave edilerek ödenebilecek azami birim bedel bulunur, ambalaj formuna göre kutu bedeli hesaplanıp kamu fiyatıyla karşılaştırılır; kamu fiyatının azami birim bedelden hesaplanan kutu fiyatını aşan kısmı ödenmez (§4.4.2).",
        },
    },

    # -------------------------------------------------------------------
    # §4.5.1 — contracted-pharmacy drug supply (ek4a / copay_rate)
    # -------------------------------------------------------------------

    # C007794 — COVERAGE: drugs from contracted pharmacies paid
    {
        "rule_id": "4.5.1.contracted_pharmacy_supply_coverage",
        "sut_section": "4.5.1",
        "gate_b_sources": ["C007794"],
        "condition": {"coverage_note": True, "contracted_pharmacy": True},
        "action": {
            "enforcement": "coverage: prescribed drugs procured from Institution-contracted pharmacies are paid",
            "message_tr": "Reçete edilen ilaçların Kurumla sözleşme yapan eczanelerden temini halinde bedelleri ödenir (§4.5.1).",
        },
    },

    # C007795 — NO_PAY: drugs from non-contracted pharmacies not covered except emergencies (with documentation)
    {
        "rule_id": "4.5.1.non_contracted_pharmacy_nopay_except_emergency",
        "sut_section": "4.5.1",
        "gate_b_sources": ["C007795"],
        "pay": False,
        "condition": {"non_contracted_pharmacy": True, "emergency_case": False},
        "action": {
            "enforcement": "no-pay condition: drugs procured from non-Institution-contracted pharmacies are NOT covered except in emergencies; emergency procurement from non-contracted pharmacies is covered if the Institution accepts the emergency, with public discount + highest pharmacist discount + patient copay deducted and the remainder paid to the person; full price coupons (with drug name) must be pasted on the prescription + a pharmacy invoice for the dispensed drugs/amount must be submitted; KKTC pre-contract prescriptions follow the same discount/calculation",
            "message_tr": "Acil haller dışında Kurum ile sözleşmesi olmayan eczanelerden temin edilen ilaçların bedelleri Kurumca karşılanmaz; sözleşmesiz eczaneden acil hal nedeniyle temin edilen ilaç bedelleri acil halin Kurumca kabulü şartıyla karşılanır; kamu iskontosu, en yüksek eczacı iskontosu ve katılım payı düşüldükten sonra kalan kısım ilgiliye ödenir; ödeme için ilaç fiyat kupürlerinin tamamı ismiyle reçeteye yapıştırılması ve eczane faturasının ibrazı zorunludur; KKTC'de eczane sözleşmesine kadar sözleşmeli sunucu reçeteleri aynı şekilde ödenir (§4.5.1).",
        },
    },

    # C007796 — REGULATORY_ACTION: Institution drug payment uses retail price on dispensing date
    {
        "rule_id": "4.5.1.payment_dispensing_date_retail_price_regulatory",
        "sut_section": "4.5.1",
        "gate_b_sources": ["C007796"],
        "action": {
            "enforcement": "regulatory: in Institution drug payment, the retail sale prices on the drug dispensing date are the basis",
            "message_tr": "Kurum ilaç ödemesinde, ilacın veriliş tarihindeki perakende satış fiyatları esas alınır (§4.5.1).",
        },
    },

    # -------------------------------------------------------------------
    # §4.5.2 — refill timing (ek4a)
    # -------------------------------------------------------------------

    # C007799 — PERMISSION: reported-prescription refills (EK-4/D or not, except course/plan drugs) may be given 15 days before drug end date
    {
        "rule_id": "4.5.2.refill_15days_before_end_permission",
        "sut_section": "4.5.2",
        "gate_b_sources": ["C007799"],
        "report_required": True,
        "condition": {"refill_early_days": 15, "course_protocol": False},
        "action": {
            "enforcement": "permission: on health-report-based prescriptions, EK-4/D or non-EK-4/D drugs (excluding course-protocol and treatment-plan drugs) may be dispensed 15 days before the drug's end date",
            "message_tr": "Sağlık raporuna dayanılarak yazılan reçetelerde, EK-4/D'de bulunan veya bulunmayan (kür ve tedavi planı olan ilaçlar hariç) ilaçlar, ilaç bitim tarihinden 15 gün öncesinde verilebilir (§4.5.2).",
        },
    },

    # -------------------------------------------------------------------
    # §4.5.3 — outpatient/inpatient drug payment (ek4a / copay_rate)
    # -------------------------------------------------------------------

    # C007801 — COVERAGE: inpatient-treatment drug costs covered by the Institution per SUT
    {
        "rule_id": "4.5.3.inpatient_drug_cost_coverage",
        "sut_section": "4.5.3",
        "gate_b_sources": ["C007801"],
        "condition": {"coverage_note": True, "inpatient_care": True},
        "action": {
            "enforcement": "coverage: drug costs arising from inpatient treatment in health institutions are covered by the Institution, provided SUT provisions are followed",
            "message_tr": "Sağlık kurum ve kuruluşlarında yatarak sağlanan tedaviler sonucu doğan ilaç bedelleri SUT hükümlerine uyulmak kaydıyla Kurum tarafından karşılanır (§4.5.3).",
        },
    },

    # C007802 — COVERAGE: outpatient drug amounts — after institution discount + pharmacy discount + patient copay, remainder paid
    {
        "rule_id": "4.5.3.outpatient_drug_net_payment_coverage",
        "sut_section": "4.5.3",
        "gate_b_sources": ["C007802"],
        "condition": {"coverage_note": True, "outpatient_care": True},
        "action": {
            "enforcement": "coverage: from outpatient-treatment drug amounts, after deducting the drug institution discount + pharmacy discount + patient copay, the remainder is paid by the Institution",
            "message_tr": "Ayakta yapılan tedavilerde kullanılan ilaç bedellerinden, ilaç kurum indirimi, eczane indirimi ve hasta katılım payı düşüldükten sonra kalan tutarlar Kurum tarafından ödenecektir (§4.5.3).",
        },
    },

    # -------------------------------------------------------------------
    # §4.6 — blood / blood-component supply (ek4a / drg_unbundling)
    # -------------------------------------------------------------------

    # C007807 — COVERAGE: 2nd/3rd-line institutions procure blood/components from licensed/Kızılay units; cost reimbursed + deducted
    {
        "rule_id": "4.6.blood_component_procurement_coverage",
        "sut_section": "4.6",
        "gate_b_sources": ["C007807"],
        "drug_names": ["kan ve kan bileşenleri"],
        "condition": {"coverage_note": True, "blood_component": True},
        "action": {
            "enforcement": "coverage: 2nd/3rd-line institutions procure blood/components (RBC suspension, whole blood, platelets, plasma, etc.) from MoH-licensed blood-service units and Kızılay blood units where present; institutions must NOT have patients procure blood; if an institution that must procure fails to and the patient procures it, the invoice is paid to the patient and deducted from the institution",
            "message_tr": "İkinci ve üçüncü basamak kuruluşlarınca hastalar için gerekli görülen kan ve kan bileşenleri, Bakanlıkça ruhsatlandırılmış kan hizmet birimleri ile Kızılay kan birimi bulunan yerlerde bu birimlerden temin edilir; kuruluşlarca hastalara kan temin ettirilmez; temini zorunlu olduğu halde temin edilmeyerek hastaya aldırılan kan/komponent fatura bedeli hastaya ödenir ve ilgili kuruluştan mahsup edilir (§4.6).",
        },
    },

    # C007808 — COVERAGE: EK-2/B-procedure blood/components — paid per EK-2/B points with ISBT-128 barcode in epicrisis
    {
        "rule_id": "4.6.ek2b_blood_component_isbt_barcode_coverage",
        "sut_section": "4.6",
        "gate_b_sources": ["C007808"],
        "drug_names": ["kan ve kan bileşenleri"],
        "condition": {"coverage_note": True, "blood_component": True, "ek2b_list": True},
        "action": {
            "enforcement": "coverage: blood/components used for EK-2/B-billed procedures and procured by institutions — paid by the Institution per EK-2/B point values, provided the epicrisis states the component name, count and ISBT-128 blood-barcode numbers",
            "message_tr": "EK-2/B üzerinden faturalandırılan tedaviler için kullanılması gerekli görülen ve sağlık kurumlarınca temin edilen kan ve kan bileşenlerinin bedelleri, epikrizde kan bileşeninin adı, sayısı ve ISBT 128 kan barkod numaralarının belirtilmesi kaydıyla EK-2/B puanları esas alınarak Kurumca kuruma ödenir (§4.6).",
        },
    },

    # C007809 — MUST_BILL / NO_PAY: EK-2/C-procedure blood/components are bundled in DRG points — cannot be billed; specific % payable exceptions
    {
        "rule_id": "4.6.ek2c_blood_component_drg_unbundling_must_bill",
        "sut_section": "4.6",
        "gate_b_sources": ["C007809"],
        "drug_names": ["kan ve kan bileşenleri"],
        "pay": False,
        "condition": {"blood_component": True, "ek2c_list": True, "drg_bundled": True},
        "action": {
            "enforcement": "must-bill/no-pay: blood/components used within EK-2/C procedures are included in diagnosis-based procedure points and CANNOT be billed; exceptions — 705371/705430/705440 components billable at 36%, 705372/705373 at 24%, 705441 at 20%, 705442/705443 at 28%; all blood components must be recorded in MEDULA with ISBT-128 barcodes",
            "message_tr": "EK-2/C kapsamındaki işlemler için kullanılan kan ve kan bileşenleri tanıya dayalı işlem puanlarına dâhil olduğundan Kuruma fatura edilemez; 705371/705430/705440 kodlu bileşenler için %36'sı, 705372 ve 705373 için %24'ü, 705441 için %20'si, 705442 ve 705443 için %28'i ayrıca faturalandırılır; tüm kan bileşenlerinin ISBT 128 barkod numaralarıyla MEDULA'ya kaydedilmesi zorunludur (§4.6).",
        },
    },

    # -------------------------------------------------------------------
    # §4.7 — hemophilia prescriptions (ek4a)
    # -------------------------------------------------------------------

    # C007816 — COVERAGE: hemophilia prescriptions by hematology/internal-medicine/pediatrics specialist = covered
    {
        "rule_id": "4.7.hemophilia_specialist_prescription_coverage",
        "sut_section": "4.7",
        "gate_b_sources": ["C007816"],
        "prescriber_specialties": ["hematoloji", "iç hastalıkları", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True, "hemophilia": True},
        "action": {
            "enforcement": "coverage: hemophilia prescriptions are covered when issued by a hematology, internal-medicine or pediatrics specialist physician in accordance with the relevant legislation",
            "message_tr": "Hemofili reçetelerinin hematoloji, iç hastalıkları veya çocuk sağlığı ve hastalıkları uzman hekimlerinden biri tarafından ilgili mevzuata uygun olarak düzenlenmesi halinde bedelleri Kurumca karşılanır (§4.7).",
        },
    },

    # C007821 — MANDATORY: cardless hemophilia patients — drugs written once on 'Kan Ürünleri Reçetesi' per health-board report; must obtain follow-up card
    {
        "rule_id": "4.7.hemophilia_cardless_once_blood_product_prescription_mandatory",
        "sut_section": "4.7",
        "gate_b_sources": ["C007821"],
        "report_required": True,
        "report_specialties": ["sağlık kurulu"],
        "prescriber_specialties": ["uzman hekim"],
        "condition": {"hemophilia": True, "hemophilia_followup_card": False},
        "action": {
            "enforcement": "mandatory: hemophilia patients who became ill before obtaining the follow-up card may have their drugs written ONCE by the relevant specialist physician on the 'Kan Ürünleri Reçetesi' based on a health-board report; since there is no second cardless treatment opportunity, after treatment patients must promptly apply to Provincial Health Directorates with the health-board report to obtain the hemophilia follow-up card",
            "message_tr": "Hemofili takip karnesini alamadan herhangi bir nedenle hastalanmış olanların ilaçları, ilgili uzman hekimlerce bir kereye mahsus olmak üzere sağlık kurulu raporuna istinaden 'Kan Ürünleri Reçetesi'ne yazılabilir; karnesiz ikinci defa tedavi görme imkânı olmadığından tedaviden sonra hastaların sağlık kurulu raporuyla birlikte vakit geçirmeden hemofili takip karnesi alabilmek için İl Sağlık Müdürlüklerine müracaat etmeleri gerekir (§4.7).",
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
