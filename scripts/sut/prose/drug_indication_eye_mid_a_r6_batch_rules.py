#!/usr/bin/env python3
"""Wave REM_4_2_eye_mid_a — §4.2.12.A (immünglobulinler: HBIg/CMV/IVIG),
§4.2.12.B-1/B-2 (IVIG nörolojik/sok endikasyonları), §4.2.24.A (astım
LABA/İKS/üçlü/nebül) and §4.2.24.B (KOAH LABA/LAMA/İKS/üçlü) — first half
of the §4.2 eye/anti-VEGF/neuro/mid wave.

35 in-force deontic clauses encoded from
`tasks/encode_waves/REM_4_2_eye_mid_a.csv`.

Rule shape follows the established `drug_indication_rheum_biologics_batch_rules`
pattern: flat condition keys (drug_names, icd10_codes/ranges, report_required,
report_duration_months, report_specialties, prescriber_specialties, pay) plus a
nested `action` block (message_tr + enforcement) for NO_PAY/PROHIBITED
exclusions.  Bare coverage statements use ``condition: {"coverage_note": True}``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# §4.2.12.A  —  immünglobulinler (hepatit B / tetanoz / sitomegalovirüs)
# ---------------------------------------------------------------------------

BATCH_RULES: list[dict] = [

    # C004416 — Hepatit B + tetanoz immünglobulinleri: ayakta uzman raporu, 1 aylık doz
    {
        "rule_id": "4.2.12.A.immunglob.hbig_tetanus_ambulatory_coverage",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004416"],
        "drug_names": ["hepatit b immünglobulini", "tetanoz immünglobulini"],
        "icd10_codes": ["B16", "B18.0", "B18.1", "A33", "A35"],
        "report_required": True,
        "prescriber_specialties": ["uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ayakta tedavide yalnızca Sağlık Bakanlığının onay verdiği endikasyon ve dozlarda, uzman hekim raporuna dayanılarak uzman hekimlerce birer aylık dozda reçete edilirse ödenir",
            "message_tr": "Hepatit B ve tetanoz immünglobulinlerinin ayakta tedavide, sadece Sağlık Bakanlığının onay verdiği endikasyonlarda ve dozlarda olmak üzere uzman hekim raporuna dayanılarak uzman hekimler tarafından birer aylık dozda reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.12.A).",
        },
    },

    # C004417 — HBIg karaciğer nakli sonrası profilaksi: risk grubu raporda
    {
        "rule_id": "4.2.12.A.immunglob.hbig_liver_tx_prophylaxis_risk_group",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004417"],
        "drug_names": ["hepatit b immünglobulini", "hbig"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "HbsAg taşıyanlarda karaciğer transplantasyonu sonrası enfeksiyon profilaksisinde belirlenen risk grubu rapor/reçetede belirtilirse ödenir",
            "message_tr": "Hepatit B immünglobulini (HBIg)'nin, Hepatit B virüs yüzey antijeni (HbsAg) taşıyan hastalarda karaciğer transplantasyonu sonrası enfeksiyon profilaksisi endikasyonunda belirlenen risk grubuna göre aşağıdaki durumların rapor/reçetede belirtilmesi halinde bedelleri Kurumca karşılanır (§4.2.12.A).",
        },
    },

    # C004427 — anhepatik faz: yüksek risk 10.000 IU, düşük risk 5.000 IU HBIg
    {
        "rule_id": "4.2.12.A.immunglob.hbig_anhepatic_phase_dose_by_risk",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004427"],
        "drug_names": ["hepatit b immünglobulini", "hbig"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "karaciğer naklinin anhepatik fazında yüksek risk grubuna 10.000 IU, düşük risk grubuna 5.000 IU HBIg",
            "message_tr": "Karaciğer naklinin anhepatik fazında; yüksek risk grubu hastalarda 10.000 IU, düşük risk grubu hastalarda 5.000 IU HBIg kullanılması halinde bedelleri Kurumca karşılanır (§4.2.12.A).",
        },
    },

    # C004429 — post-nakil gün 0-7: günlük 2.000 IU HBIg; sonra AntiHBs>100 ise aylık idame
    {
        "rule_id": "4.2.12.A.immunglob.hbig_posttx_day0_7_daily_maintenance",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004429"],
        "drug_names": ["hepatit b immünglobulini", "hbig"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "action": {
            "enforcement": "nakil sonrası 7 gün boyunca her gün 2.000 IU HBIg; 7. gün HBsAg negatif ve/veya AntiHBs>100 IU/l ise aylık 2.000 IU HBIg idameye geçilir",
            "message_tr": "7 gün boyunca her gün 2.000 IU HBIg kullanılabilir. Nakilden 7 gün sonra HBsAg ve AntiHBs düzeylerine bakılır. HBsAg negatif olması durumunda ve/veya AntiHBs düzeyi>100 IU/l ise aylık 2.000 IU HBIg idame tedavisi uygulamasına geçilir (§4.2.12.A).",
        },
    },

    # C004430 — gün 7 HBsAg pozitif/AntiHBs<100: günlük 2.000 IU 7 gün daha, gün 14 bakılır
    {
        "rule_id": "4.2.12.A.immunglob.hbig_day7_hbsag_positive_continuation",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004430"],
        "drug_names": ["hepatit b immünglobulini", "hbig"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "action": {
            "enforcement": "nakilden 7 gün sonra HBsAg pozitif ve/veya AntiHBs<100 IU/l ise 7 gün boyunca her gün 2.000 IU HBIg; 14. günde AntiHBs bakılır, >100 IU/l ise aylık 2.000 IU idameye geçilir",
            "message_tr": "Nakilden 7 gün sonra HBsAg pozitif olması durumunda ve/veya AntiHBs düzeyi<100 IU/l 7 gün boyunca her gün 2.000 IU HBIg kullanılabilir. Nakilden 14 gün sonra AntiHBs düzeylerine yeniden bakılır. AntiHBs düzeyi>100 IU/l ise aylık 2.000 IU HBIg idame tedavisi uygulamasına geçilir (§4.2.12.A).",
        },
    },

    # C004431 — gün 14 AntiHBs<100: günlük 2.000 IU 7 gün daha; sonra bakılmaksızın aylık idame
    {
        "rule_id": "4.2.12.A.immunglob.hbig_day14_antihbs_low_continuation",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004431"],
        "drug_names": ["hepatit b immünglobulini", "hbig"],
        "icd10_codes": ["B18.0", "B18.1", "Z94.4"],
        "report_required": True,
        "action": {
            "enforcement": "nakilden 14 gün sonra AntiHBs<100 IU/l ise 7 gün boyunca her gün 2.000 IU HBIg; bu sürenin sonunda AntiHBs düzeyinden bağımsız olarak aylık 2.000 IU HBIg idameye geçilir",
            "message_tr": "Nakilden 14 gün sonra AntiHBs düzeyinin<100 IU/l olması halinde 7 gün boyunca her gün 2.000 IU HBIg kullanılabilir. Bu sürenin de sonunda AntiHBs düzeyinden bağımsız olarak aylık 2.000 IU HBIg idame tedavisi uygulamasına geçilir (§4.2.12.A).",
        },
    },

    # C004440 — CMV immünglobulini: kalp/akciğer nakli, donör+ alıcı-, sağlık kurulu raporu
    {
        "rule_id": "4.2.12.A.immunglob.cmv_ig_heart_lung_tx_coverage",
        "sut_section": "4.2.12.A",
        "gate_b_sources": ["C004440"],
        "drug_names": ["sitomegalavirüs immünglobulini", "sitomegalovirüs immünglobulini", "cmv immünglobulini"],
        "icd10_codes": ["B25", "Z94.1", "Z94.8"],
        "report_required": True,
        "report_specialties": ["kardiyovasküler cerrahi", "kardiyoloji", "enfeksiyon hastalıkları", "göğüs cerrahisi", "göğüs hastalıkları"],
        "prescriber_specialties": ["uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "yalnızca kalp ve/veya akciğer nakli alıcılarında donör CMV-IgG pozitif + alıcı negatif yüksek riskli immünsupresif hastalarda CMV profilaksisinde; kalm naklinde kardiyovasküler cerrahi/kardiyoloji/enfeksiyon, akciğer naklinde göğüs cerrahisi/göğüs hastalıkları/enfeksiyon sağlık kurulu raporuyla tabela/reçete uzman hekimlerce",
            "message_tr": "Sitomegalavirüs immunglobulini; yalnızca kalp ve/veya akciğer nakli alıcılarında, donör CMV-IgG pozitif, alıcı negatif olan yüksek riskli ve immünosupresif tedaviye maruz kalan hastalarda, sitomegalovirüs enfeksiyonunun klinik belirtilerinin profilaksisinde; bu durumların belirtildiği kalp naklinde kardiyovasküler cerrahi, kardiyoloji ve enfeksiyon hastalıkları, akciğer naklinde göğüs cerrahisi, göğüs hastalıkları ve enfeksiyon hastalıkları uzman hekimlerinden oluşan sağlık kurulu raporuna dayanılarak tabela/reçetelerin uzman hekimlerce düzenlenmesi halinde bedelleri Kurumca ödenir (§4.2.12.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.12.B-1  —  IVIG nörolojik/sok endikasyonları
    # -----------------------------------------------------------------

    # C004484 — Guillain-Barre: IVIG kritik fazda ilk tercih 2 g/kg (0,4 g/kg/gün x5), nöroloji 1 ay
    {
        "rule_id": "4.2.12.B-1.immunglob.ivig_guillain_barre_loading",
        "sut_section": "4.2.12.B-1",
        "gate_b_sources": ["C004484"],
        "drug_names": ["intravenöz immünglobulin", "ivig"],
        "icd10_codes": ["G61.0"],
        "report_required": True,
        "report_duration_months": 1,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "action": {
            "enforcement": "Guillain-Barre sendromunda IVIG kritik fazda ilk tercih olarak 2 g/kg (0,4 g/kg/gün ilk 5 gün); tekrarı halinde bir ay içinde 2 g/kg (0,4 g/kg/gün x5); 1 ay süreyle nöroloji uzmanınca",
            "message_tr": "Guillan-Barre sendromunda IVIG kritik fazda ilk tercih olarak 2 gr/kg dozunda (0,4 gr/kg/gün olarak ilk 5 günde, tekrarı gerekmesi halinde bir ay içinde 2 gr/kg dozunda (0,4 gr/kg/gün olarak 5 gün kullanılabilir.) 1 ay süre ile nöroloji uzman hekimi tarafından (§4.2.12.B-1).",
        },
    },

    # C004486 — Multifokal motor nöropati: ≤2 g/kg yükleme (2-5 gün); yanıt varsa 2-6 haftada 1-2 g/kg
    {
        "rule_id": "4.2.12.B-1.immunglob.ivig_multifocal_motor_neuropathy",
        "sut_section": "4.2.12.B-1",
        "gate_b_sources": ["C004486"],
        "drug_names": ["intravenöz immünglobulin", "ivig"],
        "icd10_codes": ["G60.8", "G61.8"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "action": {
            "enforcement": "multifokal motor nöropatide 2-5 günde bölünmüş dozlarda en fazla 2 g/kg yükleme dozu; yükleme tedavisine yanıt alınırsa 2-6 haftada bir 1-2 g/kg tek doz; 2 ay sonunda yanıt alınamazsa tedavi sonlandırılır; idame 1 yıl nöroloji uzmanınca",
            "message_tr": "Multifokal motor nöropati endikasyonunda, 2-5 günde bölünmüş dozlarda en fazla 2g/kg yükleme dozunda, yükleme tedavisine yanıt alınması durumunda 2-6 haftada bir 1-2 g/kg tek dozda verilir ve 2 ay sonunda yanıt alınamazsa tedavi sonlandırılır. Başlangıç tedavisine yanıt alınması halinde idame tedavide 1 yıl süre ile nöroloji uzman hekimi tarafından (§4.2.12.B-1).",
        },
    },

    # C004487 — CIDP: steroid yetersiz/kontrendike ise ≤2 g/kg yükleme (2-5 gün); idame 3 haftada 1 g/kg
    {
        "rule_id": "4.2.12.B-1.immunglob.ivig_cidp_steroid_failure",
        "sut_section": "4.2.12.B-1",
        "gate_b_sources": ["C004487"],
        "drug_names": ["intravenöz immünglobulin", "ivig"],
        "icd10_codes": ["G35"],
        "report_required": True,
        "report_specialties": ["nöroloji"],
        "prescriber_specialties": ["nöroloji"],
        "action": {
            "enforcement": "kronik inflamatuvar demiyelinizan polinöropatide steroid tedavisine (puls+idame ≥6 ay) yetersiz cevap veya steroid komplikasyonu/kontrendikasyonu varsa 2-5 ardışık günde en fazla 2 g/kg yükleme; yükleme dozuna yanıt alınamazsa 3 haftada bir 1 g/kg (1-2 günde); 2 ayda yanıt yoksa sonlandırılır; idame 1 yıl nöroloji uzmanınca",
            "message_tr": "Kronik inflamatuvar demiyelinizan polinöropati endikasyonunda steroid tedavisine (puls ve idame tedavisine en az 6 ay) yetersiz cevap veya steroid tedavisine kanıtlanmış komplikasyon ve/veya kontrendikasyon durumlarında 2-5 ardışık günde bölünmüş dozlarda en fazla 2 g/kg yükleme dozunda, yükleme dozuna yanıt alınamaması durumunda 3 haftada bir 1 g/kg total doz 1 veya 2 günde verilir ve 2 ay sonunda yanıt alınamazsa tedavi sonlandırılır. Başlangıç tedavisine yanıt alınması halinde 3 haftada bir (0,4-1 g/kg) total doz 1 veya 2 günde, idame tedavide 1 yıl süre ile nöroloji uzman hekimi tarafından (§4.2.12.B-1).",
        },
    },

    # C004489 — IVIG ilgili bentlerce sağlık kurulu raporuyla 1 aylık doz; akut GBS/myastenia acil tek rapor; Birdshot ödenmez
    {
        "rule_id": "4.2.12.B-1.immunglob.ivig_board_report_1mo_dose_acute_emergency",
        "sut_section": "4.2.12.B-1",
        "gate_b_sources": ["C004489"],
        "drug_names": ["intravenöz immünglobulin", "ivig"],
        "icd10_codes": ["G61.0", "G70.0"],
        "report_required": True,
        "prescriber_specialties": ["uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ilgili bentlerdeki uzman hekimlerin yer aldığı sağlık kurulu raporuyla ilgili uzmanlarca 1 aylık dozda reçete edilirse ödenir; akut Guillain-Barre ve bulber tutulumlu myastenia gravis tanılı acil durumlarda ilgili uzman hekim raporuyla kullanılabilir; Birdshot retinokoroidopati ödenmez",
            "message_tr": "Düzenlenen, yukarıdaki bentlerde belirtilen ilgili uzman hekimlerin yer aldığı sağlık kurulu raporuna istinaden, ilgili bentlerde belirtilen uzman hekimlerce 1 aylık dozda reçete edilmesi halinde bedelleri Kurumca karşılanır. Akut guillain barre sendromu ve bulber tutulumu olan myastenia gravis tanılı acil durumlarda ilgili uzman hekim raporu ile kullanılabilir. (Birdshot retinokoroidopati endikasyonu ödenmez.) (§4.2.12.B-1).",
        },
    },

    # C004491 — IgM ile zenginleştirilmiş IVIG: 3. basamak YBÜ septik şokta uzman hekim
    {
        "rule_id": "4.2.12.B-1.immunglob.igm_enriched_ivig_septic_shock",
        "sut_section": "4.2.12.B-1",
        "gate_b_sources": ["C004491"],
        "drug_names": ["immunoglobulin m ile zenginleştirilmiş intravenöz immünglobulin", "igm ile zenginleştirilmiş ivig"],
        "icd10_codes": ["R57.2", "A41"],
        "report_required": True,
        "prescriber_specialties": ["uzman hekim"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamak yoğun bakımda yatan ciddi bakteriyel enfeksiyon kaynaklı septik şokta uygun antibiyotik/sıvı/vazopressör tedaviye rağmen devam eden ciddi hipotansiyon (OAB≤65 mmHg, laktat≥2 mmol/L) tedavisinde uzman hekim tarafından kullanılırsa ödenir",
            "message_tr": "Immunoglobulin M (IgM) ile zenginleştirilmiş intravenöz immünglobulinler; üçüncü basamak yoğun bakım ünitesinde yatan ciddi bakteriyel enfeksiyon kaynaklı septik şokta olan hastaların; uygun antibiyotik, sıvı, vazopressör tedavilerine rağmen devam eden ciddi hipotansiyon (ortalama arter basıncı ≤ 65 mmHg, 2mmol/L ve üzeri laktat seviyesi) tedavisinde uzman hekim tarafından kullanılması halinde bedelleri Kurumca karşılanır (§4.2.12.B-1).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.12.B-2  —  IVIG other indications (board report / 1-month dose)
    # -----------------------------------------------------------------

    # C004497 — IVIG ilgili bentlerce sağlık kurulu raporuyla 1 aylık doz; Birdshot ödenmez
    {
        "rule_id": "4.2.12.B-2.immunglob.ivig_board_report_1mo_dose",
        "sut_section": "4.2.12.B-2",
        "gate_b_sources": ["C004497"],
        "drug_names": ["intravenöz immünglobulin", "ivig"],
        "report_required": True,
        "prescriber_specialties": ["uzman hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ilgili bentlerdeki uzman hekimlerin yer aldığı sağlık kurulu raporuyla ilgili uzmanlarca 1 aylık dozda reçete edilirse ödenir; Birdshot retinokoroidopati ödenmez",
            "message_tr": "Düzenlenen, yukarıdaki bentlerde belirtilen ilgili uzman hekimlerin yer aldığı sağlık kurulu raporuna istinaden, ilgili bentlerde belirtilen uzman hekimlerce 1 aylık dozda reçete edilmesi halinde bedelleri Kurumca karşılanır. (Birdshot retinokoroidopati endikasyonu ödenmez.) (§4.2.12.B-2).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.24.A  —  astım: LABA/İKS/üçlü sabit doz kombinasyon / nebül
    # -----------------------------------------------------------------

    # C006142 — 3. basamak sağlık kurulu (alerji/immünoloji-alerji) raporuyla göğüs/alerji reçetesi
    {
        "rule_id": "4.2.24.A.resp.tertiary_allergy_board_coverage",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006142"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J45"],
        "report_required": True,
        "report_specialties": ["alerji", "immünoloji ve alerji hastalıkları"],
        "prescriber_specialties": ["göğüs hastalıkları", "alerji", "immünoloji ve alerji hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "üçüncü basamakta en az bir alerji veya immünoloji ve alerji hastalıkları uzmanının yer aldığı sağlık kurulu raporuyla göğüs hastalıkları, alerji veya immünoloji ve alerji hastalıkları uzmanlarınca reçete edilirse ödenir",
            "message_tr": "Üçüncü basamak resmi sağlık hizmeti sunucularında, en az bir alerji veya immünoloji ve alerji hastalıkları uzman hekiminin yer aldığı sağlık kurulu raporuna dayanılarak göğüs hastalıkları, alerji veya immünoloji ve alerji hastalıkları uzman hekimleri tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006143 — 16. haftada tedaviye yanıt değerlendirilip devam uygunsa 3. basamak alerji raporuyla
    {
        "rule_id": "4.2.24.A.resp.week16_response_allergy_board_coverage",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006143"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J45"],
        "report_required": True,
        "report_specialties": ["alerji", "immünoloji ve alerji hastalıkları"],
        "prescriber_specialties": ["göğüs hastalıkları", "alerji", "immünoloji ve alerji hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ilk tedaviye yanıt üçüncü basamakta 16. haftada değerlendirilir ve tedaviye devam uygun görülürse bu durum belirtilen alerji/immünoloji-alerji uzmanlı sağlık kurulu raporuyla göğüs/alerji uzmanlarınca reçete edilirse ödenir",
            "message_tr": "İlk tedaviye yanıtın üçüncü basamak resmi sağlık hizmeti sunucularında 16 ncı haftada değerlendirilmesi ve tedaviye devamın uygun görülmesi halinde bu durumun belirtildiği en az bir alerji veya immünoloji ve alerji hastalıkları uzman hekiminin yer aldığı sağlık kurulu raporu ile göğüs hastalıkları, alerji veya immünoloji ve alerji hastalıkları uzman hekimleri tarafından reçete edilmesi halinde bedeli Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006145 — LABA ve İKS mono ürünler tek başına veya birlikte reçete edilirse ödenir
    {
        "rule_id": "4.2.24.A.resp.laba_iks_mono_or_combined_coverage",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006145"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "LABA ve İKS gruplarında mono olarak yer alan ürünler tek başına veya birlikte reçete edilirse ödenir",
            "message_tr": "Uzun etkili solunum yolu beta-agonistleri (LABA) ve inhale kortikosteroidler (İKS) gruplarında mono olarak yer alan ürünlerin tek başına veya birlikte reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006146 — aynı reçetede LABA içeren müstahzarlardan yalnızca birinin bedeli ödenir
    {
        "rule_id": "4.2.24.A.resp.laba_one_per_prescription_coverage",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006146"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba"],
        "icd10_codes": ["J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "aynı reçetede LABA mono veya sabit doz kombinasyonu içeren müstahzarlardan yalnızca bir müstahzarın bedeli ödenir",
            "message_tr": "Aynı reçetede bulunan uzun etkili solunum yolu beta-agonistini (LABA) mono veya sabit doz kombinasyonu şeklinde içeren müstahzarlardan yalnızca bir müstahzarın bedeli Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006147 — aynı reçetede İKS içeren müstahzarlardan yalnızca birinin bedeli ödenir
    {
        "rule_id": "4.2.24.A.resp.iks_one_per_prescription_coverage",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006147"],
        "drug_names": ["inhale kortikosteroid", "iks"],
        "icd10_codes": ["J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "aynı reçetede İKS mono veya sabit doz kombinasyonu içeren müstahzarlardan yalnızca bir müstahzarın bedeli ödenir",
            "message_tr": "Aynı reçetede bulunan inhale kortikosteroidi (İKS) mono veya sabit doz kombinasyonu şeklinde içeren müstahzarlardan yalnızca bir müstahzarın bedeli Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006148 — LABA ve İKS mono/sabit doz ürünler diğer şekillerde reçete edilirse: no-pay
    {
        "rule_id": "4.2.24.A.resp.laba_iks_otherwise_nopay",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006148"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J45"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: LABA ve İKS mono veya sabit doz kombinasyonu gruplarındaki ürünlerin diğer şekillerde reçete edilmesi",
            "message_tr": "Uzun etkili solunum yolu beta-agonistleri (LABA) ve inhale kortikosteroidlerin (İKS) mono veya sabit doz kombinasyonu gruplarında yer alan ürünlerin diğer şekillerde reçete edilmesi halinde bedelleri Kurumca karşılanmaz (§4.2.24.A).",
        },
    },

    # C006149 — SABA veya SABA+SAMA inhale formları 4.2.24.A hükümlerinden istisna
    {
        "rule_id": "4.2.24.A.resp.saba_sama_inhale_exemption",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006149"],
        "drug_names": ["kısa etkili solunum yolu beta-agonisti", "saba", "kısa etkili antikolinerjik", "sama", "saba+sama"],
        "icd10_codes": ["J45"],
        "action": {
            "enforcement": "exemption: SABA veya SABA+SAMA inhale formları ile nebülizatörle uygulanan İKS, 4.2.24.A hükümlerinden istisnadır",
            "message_tr": "Kısa etkili solunum yolu beta-agonistini (SABA) veya kısa etkili solunum yolu beta-agonistini (SABA) ve obstrüktif solunum yolu hastalıklarında kullanılan kısa etkili antikolinerjik maddeyi (SAMA) kombine olarak içeren ürünler (SABA+SAMA) ile nebülizatörle uygulanan inhale kortikosteroidler (İKS), inhale formları 4.2.24.A numaralı maddesinde yer alan hükümlerden istisnadır (§4.2.24.A).",
        },
    },

    # C006151 — beklometazon+formoterol+glikopironyum veya flutikazonfuroat+umeklidinyum+vilanterol: astım idame
    {
        "rule_id": "4.2.24.A.resp.triple_combo_asthma_maintenance_a",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006151"],
        "drug_names": [
            "beklometazon+formoterol+glikopironyum", "flutikazonfuroat+umeklidinyum+vilanterol",
        ],
        "icd10_codes": ["J45"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları", "göğüs cerrahisi", "alerji", "iç hastalıkları"],
        "prescriber_specialties": ["göğüs hastalıkları", "göğüs cerrahisi", "alerji", "iç hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "LABA+orta doz İKS ile yeterince kontrol edilemeyen ve önceki yıl ≥1 astım alevlenmesi olan erişkin idame tedavisinde belirlenen uzmanlarca reçete edilirse ödenir; bir uzman raporu varsa diğer hekimlerce de devamı reçete edilebilir",
            "message_tr": "Beklometazon+formoterol+glikopronyum veya flutikazonfuroat 100 mcg + umeklidinyum+ vilanterol etken maddelerini sabit dozda içeren ürünler; uzun etkili beta-2 agonist ve orta doz inhale kortikosteroid kombinasyonu ile yeterince kontrol edilemeyen ve önceki yıl bir veya daha fazla astım alevlenmesi yaşayan erişkin hastaların idame tedavisinde göğüs hastalıkları, göğüs cerrahisi, alerji, iç hastalıkları uzman hekimleri tarafından reçete edilir. Bu uzman hekimlerden biri tarafından düzenlenen uzman hekim raporu mevcut ise tedavinin devamı için diğer hekimlerce de reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006153 — flutikazonfuroat 200 mcg+umeklidinyum+vilanterol: yüksek doz İKS yetersiz astım idame
    {
        "rule_id": "4.2.24.A.resp.triple_combo_asthma_maintenance_b",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006153"],
        "drug_names": ["flutikazonfuroat+umeklidinyum+vilanterol"],
        "icd10_codes": ["J45"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları", "alerji"],
        "prescriber_specialties": ["göğüs hastalıkları", "alerji"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "flutikazonfuroat 100 mcg+umeklidinyum+vilanterol veya LABA+yüksek doz İKS ile yeterince kontrol edilemeyen ve önceki yıl ≥1 astım alevlenmesi olan erişkin idame tedavisinde göğüs hastalıkları veya alerji uzmanlarınca reçete edilirse ödenir; bir uzman raporu varsa diğer hekimlerce de devamı reçete edilebilir",
            "message_tr": "Flutikazonfuroat 200 mcg + umeklidinyum + vilanterol etken maddelerini sabit dozda içeren ürünler; flutikazonfuroat 100 mcg + umeklidinyum + vilanterol veya uzun etkili beta-2 agonist ve yüksek doz inhale kortikosteroid kombinasyonu ile yeterince kontrol edilemeyen ve önceki yıl bir veya daha fazla astım alevlenmesi yaşayan erişkin hastaların idame tedavisinde göğüs hastalıkları veya alerji uzman hekimleri tarafından reçete edilir. Bu uzman hekimlerden biri tarafından düzenlenen uzman hekim raporu mevcut ise tedavinin devamı için diğer hekimlerce de reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.A).",
        },
    },

    # C006155 — nebül solunum ilaçları: ilk kutu raporsuz tüm hekimlerce; devam uzman raporuyla
    {
        "rule_id": "4.2.24.A.resp.nebul_respiratory_first_box_report",
        "sut_section": "4.2.24.A",
        "gate_b_sources": ["C006155"],
        "drug_names": ["nebül formu solunum sistemi ilaçları"],
        "icd10_codes": ["J45"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları", "immünoloji", "immünoloji ve alerji", "alerji", "çocuk sağlığı ve hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "nebül solunum ilaçları Bakanlık onaylı endikasyonda tüm hekimlerce raporsuz en fazla 1 kutu; devamı göğüs/immünoloji(-alerji)/alerji/çocuk uzman raporuyla tüm hekimlerce reçete edilirse ödenir; aynı gruptan iki nebül kombine kullanılamaz",
            "message_tr": "Nebül formundaki solunum sistemi ilaçları Sağlık Bakanlığınca onaylı endikasyonlarında kullanılması koşulu ile tüm hekimlerce raporsuz olarak en fazla bir kutu reçete edilmesi halinde, göğüs hastalıkları, immünoloji, immünoloji ve alerji, alerji veya çocuk sağlığı ve hastalıkları tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır. Aynı grupta yer alan etkin maddeleri içeren iki ayrı nebül formundaki ilaçlar kombine olarak kullanılamaz (§4.2.24.A).",
        },
    },

    # -----------------------------------------------------------------
    # §4.2.24.B  —  KOAH: LABA/LAMA/İKS mono + sabit doz kombinasyonları
    # -----------------------------------------------------------------

    # C006160 — formeterol/salmeterol/arformoterol+İKS, indakaterol/glikopironyum, üçlü sabit doz kombinasyonlar
    {
        "rule_id": "4.2.24.B.resp.laba_lama_iks_combinations_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006160"],
        "drug_names": [
            "formeterol", "salmeterol", "arformoterol", "indakaterol", "glikopironyum",
            "tiotropium", "vilanterol+flutikazon", "vilanterol+umeklidinyum",
            "tiotropium+olodaterol", "beklometazon+formoterol+glikopronyum",
            "flutikazon furoat+umeklidinyum+vilanterol",
        ],
        "icd10_codes": ["J44", "J45"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları", "göğüs cerrahisi", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "kardiyoloji"],
        "prescriber_specialties": ["göğüs hastalıkları", "göğüs cerrahisi", "iç hastalıkları", "çocuk sağlığı ve hastalıkları", "kardiyoloji", "tüm hekimler"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "belirtilen etken maddeli ilaçlar göğüs hastalıkları/göğüs cerrahisi/iç hastalıkları/çocuk sağlığı/kardiyoloji uzmanlarınca veya bu uzmanlardan birinin raporuyla tüm hekimlerce reçete edilirse ödenir",
            "message_tr": "Formeterol, salmeterol, arformoterol ve bunların inhaler kortikosteroidlerle kombinasyonları, indakaterol, glikopironyum, indakaterol+glikopironyum, tiotropium, vilanterol+flutikazon, vilanterol+umeklidinyum, tiotropium+olodaterol, beklometazon+formoterol+glikopronyum veya flutikazon furoat+umeklidinyum+vilanterol etken maddeli ilaçlar; göğüs hastalıkları, göğüs cerrahisi, iç hastalıkları, çocuk sağlığı ve hastalıkları veya kardiyoloji uzman hekimleri tarafından veya bu uzman hekimlerden biri tarafından düzenlenen uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006162 — KOAH idame üçlü: ≥3 ay İKS+LABA veya LABA+LAMA yetersiz + atak/dispne
    {
        "rule_id": "4.2.24.B.resp.copd_iks_laba_lama_failure_maintenance",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006162"],
        "drug_names": ["flutikazon furoat+umeklidinyum+vilanterol", "laba", "lama", "iks"],
        "icd10_codes": ["J44.0", "J44.1", "J44.9"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "erişkin orta-ağır KOAH idame: ≥3 ay İKS+LABA veya LABA+LAMA yetersiz + sık atak (yılda ≥2 atak veya ≥1 yatarak) + dispne (mMRC≥2 veya CAT≥10); durum uzman raporunda belirtilmeli",
            "message_tr": "En az 3 ay süreyle inhale kortikosteroid (İKS) ve uzun etkili solunum yolu beta-agonistleri (LABA) ile tedavi edildiği halde yeterli yanıt alınamayan, sık atak geçiren (yılda 2 ve üzeri atak veya 1 ve üzeri yatarak tedavi) ve dispnesi olan (mMrc 2 ve üzeri veya CAT skoru 10 ve üzeri) orta-ağır Kronik Obstrüktif Akciğer Hastalığı (KOAH) olan erişkin hastaların idame tedavisinde kullanılmaları ve bu durumların uzman hekim raporunda belirtilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006163 — LAMA/LABA/İKS birbirleriyle veya kombine kullanılırsa: no-pay
    {
        "rule_id": "4.2.24.B.resp.laba_lama_iks_combination_nopay",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006163"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "uzun etkili antikolinerjik", "lama", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: ilaçların birbirleriyle veya LABA/LAMA/İKS ile kombine kullanımı",
            "message_tr": "Birbirleri ile veya uzun etkili solunum yolu beta-agonistleri (LABA), obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjikler (LAMA) ve inhale kortikosteroidler (İKS) ile kombine olarak kullanılmaları halinde bedelleri Kurumca karşılanmaz (§4.2.24.B).",
        },
    },

    # C006169 — teofilinle kombine kullanılamaz (prohibited)
    {
        "rule_id": "4.2.24.B.resp.theophylline_combination_prohibited",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006169"],
        "drug_names": ["teofilin", "uzun etkili solunum yolu beta-agonisti", "laba", "uzun etkili antikolinerjik", "lama", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "pay": False,
        "action": {
            "enforcement": "prohibited: teofilinle kombine olarak kullanılamaz",
            "message_tr": "Teofilinle kombine olarak kullanılamaz (§4.2.24.B).",
        },
    },

    # C006171 — LABA/LAMA/İKS mono ürünler tek başına veya birlikte + üçlü kombinasyon KOAH idame
    {
        "rule_id": "4.2.24.B.resp.laba_lama_iks_mono_and_triple_maintenance",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006171"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "uzun etkili antikolinerjik", "lama", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "report_required": True,
        "report_specialties": ["göğüs hastalıkları"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "LABA/LAMA/İKS mono ürünler tek başına veya birlikte reçete edilirse ödenir; (LABA+LAMA+İKS) mono veya sabit doz üçlü kombinasyonlar ≥3 ay İKS+LABA yetersiz + sık atak + dispneli orta-ağır KOAH erişkin idame tedavisinde kullanılır ve durum raporda belirtilirse ödenir",
            "message_tr": "Uzun etkili solunum yolu beta-agonistleri (LABA), obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjikler (LAMA) ve inhale kortikosteroidler (İKS) gruplarında mono olarak yer alan ürünlerin tek başına veya birlikte reçete edilmesi halinde bedelleri Kurumca karşılanır. (LABA+LAMA+İKS) şeklinde mono ürünlerle veya sabit doz kombinasyonlarla yapılacak üçlü kombinasyon tedavilerin; en az 3 ay süreyle inhale kortikosteroid (İKS) ve uzun etkili solunum yolu beta-agonistleri (LABA) ile tedavi edildiği halde yeterli yanıt alınamayan, sık atak geçiren (yılda 2 ve üzeri atak veya 1 ve üzeri yatarak tedavi) ve dispnesi olan (mMrc 2 ve üzeri veya CAT skoru 10 ve üzeri) orta-ağır kronik obstrüktif akciğer hastalığı (KOAH) olan erişkin hastaların idame tedavisinde kullanılmaları ve bu durumların uzman hekim raporunda belirtilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006172 — (LABA+İKS) ürünleri tek başına veya LAMA ile birlikte reçete edilirse ödenir
    {
        "rule_id": "4.2.24.B.resp.laba_iks_with_lama_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006172"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti+inhale kortikosteroid", "laba+iks", "uzun etkili antikolinerjik", "lama"],
        "icd10_codes": ["J44", "J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "(LABA+İKS) ürünleri tek başına veya LAMA içeren ürünlerle birlikte reçete edilirse ödenir",
            "message_tr": "Uzun etkili solunum yolu beta-agonistini (LABA) ve inhale kortikosteroidi (İKS) kombine olarak içeren ürünlerin (LABA+İKS) tek başına veya obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjik maddeyi içeren ürünler (LAMA) ile birlikte reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006173 — (LABA+LAMA) ürünleri tek başına veya İKS ile birlikte reçete edilirse ödenir
    {
        "rule_id": "4.2.24.B.resp.laba_lama_with_iks_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006173"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti+uzun etkili antikolinerjik", "laba+lama", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "(LABA+LAMA) ürünleri tek başına veya İKS içeren ürünlerle birlikte reçete edilirse ödenir",
            "message_tr": "Uzun etkili solunum yolu beta-agonistini (LABA) ve obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjik maddeyi (LAMA) kombine olarak içeren ürünlerin (LABA+LAMA) tek başına veya inhale kortikosteroid içeren ürünler (İKS) ile birlikte reçete edilmesi halinde bedelleri Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006174 — LABA/LAMA/İKS mono/sabit doz ürünler diğer şekillerde reçete edilirse: no-pay
    {
        "rule_id": "4.2.24.B.resp.laba_lama_iks_otherwise_nopay",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006174"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba", "uzun etkili antikolinerjik", "lama", "inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: LABA/LAMA/İKS mono veya sabit doz kombinasyonu grubundaki ürünlerin diğer şekillerde reçete edilmesi",
            "message_tr": "Uzun etkili solunum yolu beta-agonistleri (LABA), obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjikler (LAMA) ve inhale kortikosteroidlerin (İKS) mono veya sabit doz kombinasyonu gruplarında yer alan ürünlerin diğer şekillerde reçete edilmesi halinde bedelleri Kurumca karşılanmaz (§4.2.24.B).",
        },
    },

    # C006175 — aynı reçetede LABA içeren müstahzarlardan yalnızca birinin bedeli ödenir
    {
        "rule_id": "4.2.24.B.resp.laba_one_per_prescription_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006175"],
        "drug_names": ["uzun etkili solunum yolu beta-agonisti", "laba"],
        "icd10_codes": ["J44", "J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "aynı reçetede LABA mono veya sabit doz kombinasyonu içeren müstahzarlardan yalnızca bir müstahzarın bedeli ödenir",
            "message_tr": "Aynı reçetede bulunan uzun etkili solunum yolu beta-agonistini (LABA) mono veya sabit doz kombinasyonu şeklinde içeren müstahzarlardan yalnızca bir müstahzarın bedeli Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006176 — aynı reçetede LAMA içeren müstahzarlardan yalnızca birinin bedeli ödenir
    {
        "rule_id": "4.2.24.B.resp.lama_one_per_prescription_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006176"],
        "drug_names": ["uzun etkili antikolinerjik", "lama"],
        "icd10_codes": ["J44", "J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "aynı reçetede LAMA mono veya sabit doz kombinasyonu içeren müstahzarlardan yalnızca bir müstahzarın bedeli ödenir",
            "message_tr": "Aynı reçetede bulunan obstrüktif solunum yolu hastalıklarında kullanılan uzun etkili antikolinerjikleri (LAMA) mono veya sabit doz kombinasyonu şeklinde içeren müstahzarlardan yalnızca bir müstahzarın bedeli Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006177 — aynı reçetede İKS içeren müstahzarlardan yalnızca birinin bedeli ödenir
    {
        "rule_id": "4.2.24.B.resp.iks_one_per_prescription_coverage",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006177"],
        "drug_names": ["inhale kortikosteroid", "iks"],
        "icd10_codes": ["J44", "J45"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "aynı reçetede İKS mono veya sabit doz kombinasyonu içeren müstahzarlardan yalnızca bir müstahzarın bedeli ödenir",
            "message_tr": "Aynı reçetede bulunan inhale kortikosteroidi (İKS) mono veya sabit doz kombinasyonu şeklinde içeren müstahzarlardan yalnızca bir müstahzarın bedeli Kurumca karşılanır (§4.2.24.B).",
        },
    },

    # C006178 — SABA veya SABA+SAMA inhale formları 4.2.24.B hükümlerinden istisna
    {
        "rule_id": "4.2.24.B.resp.saba_sama_inhale_exemption",
        "sut_section": "4.2.24.B",
        "gate_b_sources": ["C006178"],
        "drug_names": ["kısa etkili solunum yolu beta-agonisti", "saba", "kısa etkili antikolinerjik", "sama", "saba+sama"],
        "icd10_codes": ["J44", "J45"],
        "action": {
            "enforcement": "exemption: SABA veya SABA+SAMA inhale formları ile nebülizatörle uygulanan İKS, 4.2.24.B hükümlerinden istisnadır",
            "message_tr": "Kısa etkili solunum yolu beta-agonistini (SABA) veya kısa etkili solunum yolu beta-agonistini (SABA) ve obstrüktif solunum yolu hastalıklarında kullanılan kısa etkili antikolinerjik maddeyi (SAMA) kombine olarak içeren ürünler (SABA+SAMA) ile nebülizatörle uygulanan inhale kortikosteroidler (İKS), inhale formları 4.2.24.B numaralı maddesinde yer alan hükümlerden istisnadır (§4.2.24.B).",
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
