"""§2.4.4 treatment package pricing & coverage rules — wave-2c batch (part 3).

Gate-B encoded rules for SUT §2.4.4 (Bazı tetkik ve tedavi yöntemlerinin usul
ve esasları), part 3. This batch covers the §2.4.4 clauses NOT yet encoded in
batch 1 (T1), wave-2a (W2A) or wave-2b (W2B): palyatif bakım (K) all-in
provision, lomber epidural diskoplasti (L), EK-2/D-4 nöromonitörizasyon (M),
epidermolizis bülloza (N) wound-care board report, obezite cerrahisi (O),
prostat kanseri Lu-177 PSMA tedavisi (P), ekstrakorporeal fotoferez (Ç)
report/coverage/cycle rules, intraoperatif nöronavigasyon (Ö), risk puanlaması
(Ğ), IVF merkez kayıtları (İ), IVF (İ-1), PGT kök hücre verici kardeş (İ-2) ve
PGT kalıtsal hastalıklar (İ-3).

Modalities covered here: COVERAGE, MUST_BILL, MANDATORY, NO_PAY,
MUST_NOT_BILL, REGULATORY_ACTION, PERMISSION.

Merge target: data/gazette/prose_rules/treatment_pricing_2_4.json
"""

from __future__ import annotations

from typing import Any

WAVE2C_BATCH_RULES: list[dict[str, Any]] = [
    # ── §2.4.4.K — Palyatif bakım (7) MUST_NOT_BILL — tüm işlemler dahil ───────
    # C001349 already encoded (K.(7).palliative_bundled_no_separate_bill).

    # ── §2.4.4.L — Lomber epidural diskoplasti / adezyolizis / nöroplasti ──────
    # (1) MUST_BILL — P551120/P615895/P615991 sadece EK-2/C üzerinden; 3. basamak
    {
        "rule_id": "2.4.4.L.(1).diskoplasty_ek2c_3rd_step_only",
        "sut_section": "2.4.4.L",
        "condition": {
            "procedure_code_any": ["P551120", "P615895", "P615991"],
            "billing_basis": "other",
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "P551120, P615895 ve P615991 kodlu işlemler sadece SUT EK-2/C "
                "Listesinde belirtilen puanlar üzerinden faturalandırılır; "
                "bedelleri algoloji, beyin cerrahisi ve ortopedi ve travmatoloji "
                "branş hekimlerince üçüncü basamak sunucularında yapılması halinde "
                "Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001352"],
        "encode_batch": "W2C",
    },
    # (2) MANDATORY — 3 uzman hekimli sağlık kurulu raporu zorunlu
    {
        "rule_id": "2.4.4.L.(2).diskoplasty_3_specialty_board_report_required",
        "sut_section": "2.4.4.L",
        "condition": {
            "procedure_code_any": ["P551120", "P615895", "P615991"],
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "transsakral girişimle kamera eşliğinde lomber epidural "
                "diskoplasti/adezyolizis/nöroplasti amaçlı işlemlerin "
                "yapılabilmesi için algoloji, nöroloji, fiziksel tıp ve "
                "rehabilitasyon, ortopedi ve travmatoloji ile beyin cerrahisi "
                "branşlarından herhangi üç uzman hekim tarafından oluşturulan "
                "sağlık kurulu raporu düzenlenmesi gerekir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001353"],
        "encode_batch": "W2C",
    },
    # (3) COVERAGE — uygun şartlarda bedeli Kurumca karşılanır
    {
        "rule_id": "2.4.4.L.(3).diskoplasty_covered_when_conditions_met",
        "sut_section": "2.4.4.L",
        "condition": {
            "procedure_code_any": ["P551120", "P615895", "P615991"],
            "conditions_met": True,
        },
        "action": {
            "billable": True,
            "enforcement": "coverage",
            "message_tr": "uygun şartlarda yapılan işlemin bedeli Kurumca karşılanır",
        },
        "gate_b_sources": ["C001360"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.M — EK-2/D-4 nöromonitörizasyon ────────────────────────────────
    # (1) COVERAGE — EK-2/D-4 + P703365 nöromonitörizasyon; 2.2.2.B(3) uygulanmaz
    {
        "rule_id": "2.4.4.M.(1).neuromonitoring_ek2d4_p703365_bypass_2_2_2b3",
        "sut_section": "2.4.4.M",
        "condition": {
            "annex_list": "EK-2/D-4",
            "procedure_code_any": ["P703365"],
            "apply_2_2_2_b3_rules": True,
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "EK-2/D-4 Listesinde yer alan işlemlerin P703365 'Intraoperatif "
                "nöromonitörizasyon' ile birlikte uygulanması şartıyla 2.2.2.B(3) "
                "kuralları uygulanmaksızın faturalandırılması halinde Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/D-4",
        },
        "gate_b_sources": ["C001362"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.N — Epidermolizis bülloza (EB) yara bakım ──────────────────────
    # C001366 already encoded (N.(1).eb_wound_care_3rd_step_public).

    # ── §2.4.4.O — Obezite cerrahisi sağlık kurulu ────────────────────────────
    # (a) MANDATORY — BMI > 40 için 4 branşlı sağlık kurulu raporu
    {
        "rule_id": "2.4.4.O.(a).bariatric_bmi40_4_specialty_board_report",
        "sut_section": "2.4.4.O",
        "condition": {
            "procedure_category": "bariatric_surgery",
            "bmi": {"min": 40.0001},
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "BMI > 40 kg/m2 olan kişilerde; genel cerrahi, endokrinoloji "
                "(yoksa dahiliye), akıl ve ruh sağlığı hastalıkları ile anestezi "
                "ve reanimasyon uzman hekimlerinin yer aldığı ve tıbbi endikasyonun "
                "belirtildiği sağlık kurulu raporu düzenlenmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001370"],
        "encode_batch": "W2C",
    },
    # (b) MANDATORY — BMI 35-40 + eşlik eden hastalık; ilgili branş dahil
    {
        "rule_id": "2.4.4.O.(b).bariatric_bmi35_40_comorbidity_board_report",
        "sut_section": "2.4.4.O",
        "condition": {
            "procedure_category": "bariatric_surgery",
            "bmi": {"min": 35.0, "max": 40.0},
            "has_comorbidity": True,
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "BMI 35-40 kg/m2 ve eşlik eden hastalığı bulunan kişilerde; "
                "genel cerrahi, endokrinoloji (yoksa dahiliye), akıl ve ruh "
                "sağlığı, anestezi ve reanimasyon uzmanları ile eşlik eden "
                "hastalığın branş uzmanının da yer aldığı ve tıbbi endikasyonun "
                "belirtildiği sağlık kurulu raporu düzenlenmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001371"],
        "encode_batch": "W2C",
    },
    # (c) MANDATORY — BMI 35-40 + eşlik eden hastalık için 6 ay kilo verememe notu
    {
        "rule_id": "2.4.4.O.(c).bariatric_bmi35_40_6mo_unsuccessful_weight_loss",
        "sut_section": "2.4.4.O",
        "condition": {
            "procedure_category": "bariatric_surgery",
            "bmi": {"min": 35.0, "max": 40.0},
            "has_comorbidity": True,
            "documented_6mo_lifestyle_medical_failure": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "BMI 35-40 ve eşlik eden hastalığı bulunan kişilere düzenlenecek "
                "sağlık kurulu raporunda; uzman kontrolünde en az 6 ay yaşam tarzı "
                "değişikliği ve/veya medikal tedavi ile kilo verilemediğinin "
                "belirtilmesi gerekmektedir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001372"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.P — Lu-177 PSMA prostat kanseri tedavisi ───────────────────────
    # (2) MANDATORY — raporda progrese kastrasyona dirençli metastatik tanı
    {
        "rule_id": "2.4.4.P.(2).psma_castration_resistant_metastatic_diagnosis",
        "sut_section": "2.4.4.P",
        "condition": {
            "procedure_category": "lu177_psma_therapy",
            "diagnosis_is": "progressive_castration_resistant_metastatic_prostate_ca",
            "diagnosis_on_board_report": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "sağlık kurulu raporunda progrese, kastrasyona dirençli metastatik "
                "prostat kanseri tanısının bulunması gerekir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001389"],
        "encode_batch": "W2C",
    },
    # (3) MANDATORY — testesteron < 50 ng/dl; PSA kriter değil
    {
        "rule_id": "2.4.4.P.(3).psma_testosterone_under_50_psa_not_criteria",
        "sut_section": "2.4.4.P",
        "condition": {
            "procedure_category": "lu177_psma_therapy",
            "testosterone_ng_dl": {"min": 50},
        },
        "action": {
            "billable": False,
            "enforcement": "pre_treatment_lab_gate",
            "message_tr": (
                "tedavi öncesinde kan testesteron düzeyinin 50 ng/dl altında olması "
                "gerekir; tedaviye başlanması için PSA değeri kriter değildir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001390"],
        "encode_batch": "W2C",
    },
    # (5) MANDATORY — öncesinde Ga-68 PSMA PET; ≥3 odakta karaciğer üstü tutulum
    {
        "rule_id": "2.4.4.P.(5).psma_ga68_pet_min3_foci_above_liver",
        "sut_section": "2.4.4.P",
        "condition": {
            "procedure_category": "lu177_psma_therapy",
            "prior_ga68_psma_pet": False,
        },
        "action": {
            "billable": False,
            "enforcement": "pre_treatment_imaging_gate",
            "message_tr": (
                "Lu-177 işaretli PSMA bileşikleri ile tedavisi öncesinde Ga-68 PSMA "
                "PET görüntülemenin mutlaka yapılmış olması ve en az 3 odakta "
                "karaciğerden daha yüksek düzeyde patolojik tutulumun bulunması gerekir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001392"],
        "encode_batch": "W2C",
    },
    # (6) PERMISSION — en az 6 hafta ara; en fazla 8 (3 imzalı raporla 12) doz
    {
        "rule_id": "2.4.4.P.(6).psma_min6week_gap_8_or_12_doses_with_report",
        "sut_section": "2.4.4.P",
        "condition": {
            "procedure_category": "lu177_psma_therapy",
            "weeks_between_cycles": {"max": 5},
        },
        "action": {
            "billable": False,
            "enforcement": "frequency_and_cycle_cap",
            "message_tr": (
                "tedavi en az 6 hafta ara ile uygulanır; nükleer tıp uzmanı "
                "tarafından gerekçeli raporla en fazla 8 doz; klinik fayda gören "
                "hastalarda nükleer tıp + tıbbi onkoloji uzmanlı üç imzalı "
                "gerekçeli sağlık kurulu raporu ile 12 doza kadar uygulanabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001393"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.Ç — Ekstrakorporeal fotoferez (ECP) ────────────────────────────
    # C000927 already encoded (Ç.(5).photopheresis_ek2b_pricing).
    # (1) MANDATORY — ECP için 3. basamak (veya ruhsatlı 2. basamak) sağlık kurulu
    {
        "rule_id": "2.4.4.C-c.(1).photopheresis_3rd_step_board_report",
        "sut_section": "2.4.4.Ç",
        "condition": {
            "procedure_category": "extracorporeal_photopheresis",
            "facility_not_in": [
                "contracted_3rd_step",
                "licensed_2nd_step_transplant_apheresis",
            ],
        },
        "action": {
            "billable": False,
            "enforcement": "facility_and_documentation_gate",
            "message_tr": (
                "ekstrakorporeal fotoferez tedavi bedellerinin ödenebilmesi için "
                "üçüncü basamak sunucularınca sağlık kurulu raporu düzenlenmesi "
                "gerekir; kemik iliği/organ nakil ve terapötik aferez ruhsatlı "
                "ikinci basamaklar yalnızca GVHD veya solid organ naklinde doku "
                "reddini önleme için rapor düzenleyebilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000917"],
        "encode_batch": "W2C",
    },
    # (2) COVERAGE — uygun endikasyonla uygulanırsa bedeli Kurumca karşılanır
    {
        "rule_id": "2.4.4.C-c.(2).photopheresis_covered_for_indication",
        "sut_section": "2.4.4.Ç",
        "condition": {
            "procedure_category": "extracorporeal_photopheresis",
            "indication_accepted": True,
        },
        "action": {
            "billable": True,
            "enforcement": "coverage",
            "message_tr": "uygun endikasyon nedeniyle uygulanması halinde bedelleri Kurumca karşılanır",
        },
        "gate_b_sources": ["C000924"],
        "encode_batch": "W2C",
    },
    # (3) COVERAGE — 6 ayda bir rapor, en fazla 26 döngü; komisyon onayıyla süre uzatımı
    {
        "rule_id": "2.4.4.C-c.(3).photopheresis_6mo_report_max26_cycles",
        "sut_section": "2.4.4.Ç",
        "condition": {
            "procedure_category": "extracorporeal_photopheresis",
            "cycles_within_6mo_report": {"min": 27},
        },
        "action": {
            "billable": False,
            "enforcement": "report_and_cycle_cap",
            "message_tr": (
                "sağlık kurulu raporunda tedavi programı ve süresi belirtilir; "
                "ECP 6 ayda bir düzenlenen (en az bir hematoloji uzmanı dâhil üç "
                "imzalı) sağlık kurulu raporu ile en fazla 26 döngü için ödenir; "
                "komisyon onayıyla tedavi kesin sonuç alınıncaya kadar uzatılabilir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000925"],
        "encode_batch": "W2C",
    },
    # (4) MANDATORY — CTCL/GVHD/sklerozis/nakil dışı endikasyonlarda komisyon görüşü
    {
        "rule_id": "2.4.4.C-c.(4).photopheresis_other_indications_commission_approval",
        "sut_section": "2.4.4.Ç",
        "condition": {
            "procedure_category": "extracorporeal_photopheresis",
            "indication_not_in": [
                "ctcl", "gvhd", "systemic_sclerosis", "solid_organ_rejection_prophylaxis",
            ],
            "apheresis_photopheresis_commission_approval": False,
        },
        "action": {
            "billable": False,
            "enforcement": "commission_approval_gate",
            "message_tr": (
                "kutanöz T hücreli lenfoma, GVHD, sistemik sklerozis ve solid organ "
                "nakillerinde doku reddinin önlenmesi endikasyonlarında ilk 26 döngü "
                "için sağlık kurulu raporu alınır; diğer kullanım alanlarında sağlık "
                "kurulu raporuna ek olarak Aferez-Fotoferez Danışma Komisyonu'nun "
                "uygun görüşü alınması zorunludur"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C000926"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.Ö — İntraoperatif nöronavigasyon ───────────────────────────────
    # (1) COVERAGE — P614981 nöronavigasyon EK-2/C; 2.2.2.B(3) uygulanmaz; EK-2/D-5
    {
        "rule_id": "2.4.4.O-u.(1).neuronavigation_ek2c_d5_bypass_2_2_2b3",
        "sut_section": "2.4.4.Ö",
        "condition": {
            "procedure_code_any": ["P614981"],
            "apply_2_2_2_b3_rules": True,
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "intraoperatif nöronavigasyon işlem bedeli P614981 üzerinden ve "
                "2.2.2.B(3) kuralları uygulanmaksızın faturalandırılır; EK-2/D-5 "
                "Listesindeki işlemlerle birlikte uygulanıp beyin ve sinir cerrahisi "
                "ile kulak burun boğaz uzmanlarınca yapılması halinde Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001377"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.Ğ — Risk puanlaması ────────────────────────────────────────────
    # (1) COVERAGE — risk puanına göre EK üzerinden karşılanır
    {
        "rule_id": "2.4.4.G-u.(1).risk_scored_coverage_via_annex",
        "sut_section": "2.4.4.Ğ",
        "condition": {
            "procedure_category": "risk_scored_payment",
            "risk_score_documented": True,
        },
        "action": {
            "billable": True,
            "enforcement": "coverage",
            "message_tr": "risk puanına göre ilgili işlem üzerinden karşılanır",
        },
        "gate_b_sources": ["C001135"],
        "encode_batch": "W2C",
    },
    # (2) MANDATORY — risk puanlamasına esas bilgi ve belgeleri hasta dosyasında saklama
    {
        "rule_id": "2.4.4.G-u.(2).risk_score_records_kept_in_patient_file",
        "sut_section": "2.4.4.Ğ",
        "condition": {
            "procedure_category": "risk_scored_payment",
            "risk_score_basis_documents_in_file": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "sözleşmeli/protokollü sağlık hizmeti sunucuları, risk puanlamasına "
                "esas teşkil eden bilgi ve belgeleri hasta dosyasında saklamak zorundadır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001136"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.İ — IVF merkez kayıtları ───────────────────────────────────────
    # (1) MANDATORY — IVF işlemlerinin kaydı tutulması ve denetimde ibrazı
    {
        "rule_id": "2.4.4.I-d.(1).ivf_records_kept_and_presented_on_audit",
        "sut_section": "2.4.4.İ",
        "condition": {
            "procedure_category": "ivf_art",
            "procedure_records_maintained": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "sözleşmeli/protokollü üremeye yardımcı tedavi merkezlerinde IVF "
                "kapsamında yapılan her türlü tıbbi işlemin kaydının tutulması ve "
                "tutulan kayıtların denetim esnasında ibrazı zorunludur; kayıtların "
                "doğru tutulması ve muhafazasında merkez sorumlusu ile ruhsat sahibi "
                "kişiler müşterek ve müteselsilen yükümlüdür"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001302"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.İ-1 — IVF (tüp bebek) temel kurallar ───────────────────────────
    # C001261, C001296, C001297, C001298 already encoded (İ-1 IVF batch 1).
    # (1) COVERAGE — evli + mevcut evlilikte çocuğu olmayan sigortalıya en fazla 3 siklus
    {
        "rule_id": "2.4.4.I-1.(1).ivf_married_no_child_max_3_cycles",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "patient_married": True,
            "has_child_in_current_marriage": False,
            "ivf_cycles_lifetime": {"min": 4},
        },
        "action": {
            "billable": False,
            "enforcement": "cycle_cap",
            "message_tr": (
                "evli olup mevcut evliliğinde çocuğu olmayan genel sağlık "
                "sigortalısına en fazla üç deneme (siklus) ile sınırlı olmak üzere "
                "uygulanan IVF tedavilerine ilişkin giderler, şartların birlikte "
                "gerçekleşmesi halinde Kurumca karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001255"],
        "encode_batch": "W2C",
    },
    # (d) REGULATORY_ACTION — son 3 yıl diğer yöntemlerden sonuç alınamadığı belgesi
    {
        "rule_id": "2.4.4.I-1.(1d).ivf_3yr_other_methods_unsuccessful_documented",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "diagnosis_not_in": ["primary_ovarian_failure", "male_azoospermia"],
            "other_methods_unsuccessful_within_3y_documented": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "kadının primer ovaryan yetmezliği ve erkeğin azoospermisi hâlleri "
                "hariç, son üç yıl içinde diğer tedavi yöntemlerinden sonuç "
                "alınamamış olduğunun sözleşmeli/protokollü sunucu sağlık "
                "kurullarınca belgelenmesi gerekir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001260"],
        "encode_batch": "W2C",
    },
    # (3) REGULATORY_ACTION — devredilen kurumların ödediği tüp bebekler adede dahil
    {
        "rule_id": "2.4.4.I-1.(3).ivf_prior_cycles_counted",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "prior_ivf_paid_by_transferred_agency": True,
            "prior_cycles_counted_in_total": False,
        },
        "action": {
            "billable": False,
            "enforcement": "cycle_accounting",
            "message_tr": (
                "Kuruma devredilen sosyal güvenlik kurumlarınca daha önce ödenen "
                "tüp bebek tedavileri, işlem adetlerinin hesaplanmalarında dikkate alınır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001262"],
        "encode_batch": "W2C",
    },
    # (4) MANDATORY — raporda gerekli şartların belirtilmiş olması
    {
        "rule_id": "2.4.4.I-1.(4).ivf_report_conditions_specified",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "ivf_report_conditions_specified": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": "sağlık kurulu raporunda IVF için gerekli şartların belirtilmiş olması gereklidir",
            "severity": "error",
        },
        "gate_b_sources": ["C001284"],
        "encode_batch": "W2C",
    },
    # (5) MANDATORY — rapor tarihinden 6 ay içinde uygulama yoksa yeniden rapor
    {
        "rule_id": "2.4.4.I-1.(5).ivf_apply_within_6mo_or_new_report",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "months_from_report_to_application": {"min": 7},
        },
        "action": {
            "billable": False,
            "enforcement": "report_validity",
            "message_tr": (
                "sağlık kurulu raporunun düzenlendiği tarihten itibaren 6 ay içinde "
                "IVF uygulamasının yapılmaması halinde yeniden sağlık kurulu raporu "
                "düzenlenmesi gereklidir; bu sürede temin edilen ilaçlar maksimum doz "
                "hesabında dikkate alınır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001293"],
        "encode_batch": "W2C",
    },
    # (6) MANDATORY — her IVF tedavisi için ayrı sağlık kurulu raporu
    {
        "rule_id": "2.4.4.I-1.(6).ivf_separate_board_report_per_treatment",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "health_board_report_present": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": "her bir IVF tedavisi (ve ikinci tedavi) için sağlık kurulu raporu düzenlenmesi gereklidir",
            "severity": "error",
        },
        "gate_b_sources": ["C001294"],
        "encode_batch": "W2C",
    },
    # (3) MUST_BILL — uygulanamayan IVF'te yapılan işlemler EK-2/B %10 indirimle
    {
        "rule_id": "2.4.4.I-1.(3c).ivf_not_performed_10pct_discount_ek2b",
        "sut_section": "2.4.4.İ-1",
        "condition": {
            "procedure_category": "ivf_art",
            "ivf_not_performed": True,
            "billing_basis": "other",
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "hastaya IVF uygulamasının yapılamaması durumunda; o süreye kadar "
                "yapılan işlemler EK-2/B Listesi üzerinden %10 indirim yapılarak "
                "faturalandırılır; bu işlemler deneme sayısına dâhil edilmez; "
                "kullanılan ilaçlar maksimum doz hesabında dikkate alınır"
            ),
            "annex_basis": "EK-2/B",
        },
        "gate_b_sources": ["C001299"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.İ-2 — PGT ile kök hücre verici kardeş (savior sibling) ─────────
    # (1) NO_PAY — hasta çocuk için PGT+savior sibling şartları dışında Kurumca ödenmez
    {
        "rule_id": "2.4.4.I-2.(1).pgt_savior_sibling_conditions_otherwise_no_pay",
        "sut_section": "2.4.4.İ-2",
        "condition": {
            "procedure_category": "preimplantation_genetic_diagnosis",
            "savior_sibling_conditions_met": False,
        },
        "action": {
            "billable": False,
            "enforcement": "exclusion",
            "message_tr": (
                "hasta çocuğun tedavisi amaçlı PGT ile uygun kök hücre verici "
                "kardeş doğmasına yönelik IVF, kemik iliği transplantasyon merkezi "
                "bulunan Bakanlığa bağlı 3. basamak/tıp fakülteli üniversite "
                "sağlık kurullarınca düzenlenen genetik uzmanlı raporla yapılması "
                "şartıyla Kurumca karşılanır; bu durum ve İ-3 dışında PGT ve birlikte "
                "yapılan IVF bedelleri Kurumca karşılanmaz"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001310"],
        "encode_batch": "W2C",
    },

    # ── §2.4.4.İ-3 — PGT ile IVF (kalıtsal hastalıklar, EK-2/K) ───────────────
    # (1) COVERAGE — EK-2/K kalıtsal hastalığı/taşıyıcılığı olan çifte en fazla 3 siklus
    {
        "rule_id": "2.4.4.I-3.(1).pgt_hereditary_ek2k_max_3_cycles",
        "sut_section": "2.4.4.İ-3",
        "condition": {
            "procedure_category": "preimplantation_genetic_diagnosis",
            "diagnosis_in": ["ek2k_hereditary_disease"],
            "patient_married": True,
            "has_healthy_child_in_current_marriage": False,
            "pgt_ivf_cycles_lifetime": {"min": 4},
        },
        "action": {
            "billable": False,
            "enforcement": "cycle_cap",
            "message_tr": (
                "EK-2/K'de yer alan kalıtsal bir hastalığı olan veya taşıyıcı olduğu "
                "belgelenen, mevcut evliliğinde sağlam çocuğu olmayan evli çiftin "
                "PGT ile IVF tedavisine ilişkin giderleri, şartların birlikte "
                "gerçekleşmesi halinde en fazla üç deneme (siklus) ile sınırlı "
                "olarak Kurumca karşılanır"
            ),
            "annex_basis": "EK-2/K",
            "severity": "error",
        },
        "gate_b_sources": ["C001317"],
        "encode_batch": "W2C",
    },
    # (4) COVERAGE — EK-2/K tanılarında PGT+IVF Kurumca karşılanır; genetik danışmanlık+rapor
    {
        "rule_id": "2.4.4.I-3.(4).pgt_hereditary_ek2k_genetic_report_required",
        "sut_section": "2.4.4.İ-3",
        "condition": {
            "procedure_category": "preimplantation_genetic_diagnosis",
            "diagnosis_in": ["ek2k_hereditary_disease"],
            "medical_geneticist_signed_genetic_report": False,
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_required",
            "message_tr": (
                "sağlam çocuk doğmasına yönelik PGT ile IVF tedavi bedelleri EK-2/K "
                "tanılarında Kurumca karşılanır; bu tanılara ait evli çiftin tıbbi "
                "genetik uzman imzalı genetik danışmanlık notu ile klinik yorumun "
                "yapıldığı genetik tanı raporu bulunmalıdır"
            ),
            "annex_basis": "EK-2/K",
            "severity": "error",
        },
        "gate_b_sources": ["C001320"],
        "encode_batch": "W2C",
    },
    # (6) MANDATORY — embriyolar en fazla 8 adet numaralandırılır; raporlar Kuruma gönderilir
    {
        "rule_id": "2.4.4.I-3.(6).pgt_embryo_max8_numbered_report_to_institution",
        "sut_section": "2.4.4.İ-3",
        "condition": {
            "procedure_category": "preimplantation_genetic_diagnosis",
            "embryos_numbered_count": {"min": 9},
        },
        "action": {
            "billable": False,
            "enforcement": "documentation_and_cap",
            "message_tr": (
                "üremeye yardımcı tedavi merkezi tarafından elde edilen IVF'ye uygun "
                "embriyoların en fazla sekiz adet olmak üzere numaralandırılması "
                "gerekir; embriyoların 'sağlıklı/taşıyıcı/hasta' olarak belirtildiği "
                "analiz sonuçlarını içeren raporların Kuruma incelemeye esas belge "
                "olarak gönderilmesi gereklidir"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001322"],
        "encode_batch": "W2C",
    },
    # (10) COVERAGE — transfer edilmeyen sağlıklı embriyo freezing, deneme hakkı varsa
    {
        "rule_id": "2.4.4.I-3.(10).pgt_healthy_embryo_freezing_if_cycles_remaining",
        "sut_section": "2.4.4.İ-3",
        "condition": {
            "procedure_category": "preimplantation_genetic_diagnosis",
            "embryo_freezing_of_untransferred_healthy": True,
            "ivf_cycle_entitlement_remaining": False,
        },
        "action": {
            "billable": False,
            "enforcement": "coverage_condition",
            "message_tr": (
                "PGT ile elde edilen ve transfer edilmeyen sağlıklı embriyo veya "
                "embriyoların freezing işlemi, IVF deneme hakkının bulunması "
                "durumunda Kurumca karşılanır"
            ),
            "severity": "error",
        },
        "gate_b_sources": ["C001326"],
        "encode_batch": "W2C",
    },
    # (11) MUST_BILL — freezing embriyo transferi EK-2/C üzerinden; denemeye dâhil
    {
        "rule_id": "2.4.4.I-3.(11).pgt_frozen_embryo_transfer_ek2c",
        "sut_section": "2.4.4.İ-3",
        "condition": {
            "procedure_category": "ivf_art",
            "is_frozen_embryo_transfer": True,
            "billing_basis": "other",
        },
        "action": {
            "billable": True,
            "enforcement": "pricing_basis",
            "message_tr": (
                "IVF tedavisinin freezing işlemi uygulanan embriyonun transferi ile "
                "yapılması durumunda işlemler EK-2/C'deki 'Freezing işlemi uygulanan "
                "embriyonun transferi' işlemi üzerinden faturalandırılır; bu işlem "
                "deneme sayısına dâhil edilecektir"
            ),
            "annex_basis": "EK-2/C",
        },
        "gate_b_sources": ["C001327"],
        "encode_batch": "W2C",
    },
]
