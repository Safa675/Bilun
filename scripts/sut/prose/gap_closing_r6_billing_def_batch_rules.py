#!/usr/bin/env python3
"""Gap-closing wave R6 — billing documents (§5.x), definitions (§6.x), copay (§1.8).

42 in-force deontic clauses encoded from
`tasks/encode_waves/REM_others_billing_def.csv` covering:

* §1.8 / 1.8.1 / 1.8.2 / 1.8.3  —  ayakta tedavi muayene katılım payı (copay)
* §5.1                          —  bilgilerin MEDULA sistemine girilmesi zorunluluğu
* §5.2 / 5.2.1-5.2.6             —  fatura/e-fatura düzenleme, dönem sonlandırma,
                                    reçete/kan ürünü/hemofili faturalama, sevk belgesi,
                                    engelli sağlık kurulu raporu ibrazı, YUPASS onayı
* §5.3.1 / 5.3.1.B/C/Ç          —  incelemeye esas belgeler, hizmet detay belgesi
* §5.3.2                        —  tıbbi malzeme faturası (arka yüz onay, ibraz, protokol)
* §6.1                          —  birim puanlar KDV hariç
* §6.3.1                        —  25.02.2011 öncesi trafik kazası bedelleri
* §6.3.2                        —  aynı işlevli malzeme garanti süresi / fiyatsız malzeme

Rule shape follows the established `gap_closing_r6_referral_batch_rules.py`
pattern: a ``gate_b_sources`` list (one clause id per rule here), flat
condition keys and a nested ``action`` block (message_tr + enforcement).
``message_tr`` is taken from the in-force Turkish text.
NO_PAY / PROHIBITED modalities encode as ``pay: False``; PERMISSION / COVERAGE
as ``condition: {"coverage_note": True}``; COPAY_REQUIRED as
``condition: {"copay_required": True}``; MANDATORY / REGULATORY_ACTION /
MUST_BILL as a bare enforcement action.
"""

from __future__ import annotations

BATCH_RULES: list[dict] = [

    # -----------------------------------------------------------------
    # §1.8 / 1.8.1 / 1.8.2 / 1.8.3  —  ayakta tedavi muayene katılım payı
    # -----------------------------------------------------------------

    # C000227 — aile hekimleri hariç ayakta tedavide hekim/diş hekimi muayene katılım payı
    {
        "rule_id": "1.8.outpatient_exam_copay_excluding_family_physicians",
        "sut_section": "1.8",
        "gate_b_sources": ["C000227"],
        "action": {
            "enforcement": "Sağlık Bakanlığı tarafından sözleşme imzalanmış, görevlendirilmiş veya yetkilendirilmiş aile hekimleri hariç olmak üzere ayakta tedavide hekim ve diş hekimi muayenesi için katılım payı alınır",
            "message_tr": "Sağlık Bakanlığı tarafından sözleşme imzalanmış, görevlendirilmiş veya yetkilendirilmiş aile hekimleri hariç olmak üzere ayakta tedavide hekim ve diş hekimi muayenesi katılım payı alınır (§1.8).",
        },
    },

    # C000237 — 5510/60(c)(1)(2)(3) kapsamı kişilerin katılım payları SYDV'ce geri ödenir
    {
        "rule_id": "1.8.social_solidarity_copay_refund",
        "sut_section": "1.8",
        "gate_b_sources": ["C000237"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "5510 sayılı Kanunun 60 ıncı maddesinin birinci fıkrasının (c) bendinin (1), (2) ve (3) numaralı alt bentleri gereği genel sağlık sigortalısı sayılanlar ile bakmakla yükümlü olduğu kişilerin ödedikleri katılım payları talepleri halinde 3294 sayılı Kanun hükümlerine göre sosyal yardımlaşma ve dayanışma vakıflarınca geri ödenir",
            "message_tr": "5510 sayılı Kanunun 60 ıncı maddesinin birinci fıkrasının (c) bendinin (1), (2) ve (3) numaralı alt bentleri gereği genel sağlık sigortalısı sayılanlar ile bunların bakmakla yükümlü olduğu kişilerin ödemiş oldukları katılım payları talepleri halinde, 3294 sayılı Sosyal Yardımlaşma ve Dayanışmayı Teşvik Kanunu hükümlerine göre sosyal yardımlaşma ve dayanışma vakıflarınca kendilerine geri ödenir (§1.8).",
        },
    },

    # C000308 — katılım payları kişinin reçete ile eczaneye ilk müracaatında tahsil edilir
    {
        "rule_id": "1.8.1.copay_collected_first_pharmacy_visit",
        "sut_section": "1.8.1",
        "gate_b_sources": ["C000308"],
        "action": {
            "enforcement": "muayene katılım payları ile yatan hasta reçeteleri ve askerlik hizmeti süresince düzenlenen reçeteler hariç olmak üzere, kişilerin reçete ile eczaneye ilk müracaatında eczanelerce kişilerden tahsil edilir",
            "message_tr": "Sağlık hizmeti sunucularında yapılan muayene sonucunda oluşan ve eczanelerce kişilerden tahsil edileceği belirtilen ayakta tedavide hekim ve diş hekimi muayenesi katılım payları; SUT 4.1.2'de tanımlanan yatan hasta reçeteleri ile 5510 sayılı Kanunun 60 ıncı maddesinin on ikinci fıkrası kapsamında askerlik hizmeti süresince düzenlenen reçeteleri hariç olmak üzere, kişilerin reçete ile eczaneye ilk müracaatında kişilerden tahsil edilir (§1.8.1).",
        },
    },

    # C000312 — 10 gün içinde aynı uzmanlıkta farklı sunucuya başvuruda +5 TL
    {
        "rule_id": "1.8.1.repeated_same_specialty_within_10d_plus_5tl",
        "sut_section": "1.8.1",
        "gate_b_sources": ["C000312"],
        "action": {
            "enforcement": "birinci basamak muayeneleri, Kurumca belirlenen kronik hastalıklar, elektronik sevk formu ile sevk edilen hastalar ve acil haller hariç; 10 gün içerisinde aynı uzmanlık dalında farklı sunucuya yapılan başvurularda katılım payı 5 TL artırılarak tahsil edilir",
            "message_tr": "Bu maddede yer alan genel hükümler saklı kalmak kaydıyla; birinci basamak sağlık kuruluşları muayeneleri, Kurumca belirlenen kronik hastalıklar, elektronik sevk formu ile sevk edilen hastalar ve acil haller hariç olmak üzere 10 gün içerisinde aynı uzmanlık dalında farklı sağlık hizmeti sunucusuna yapılan başvurularda ayakta tedavide hekim ve diş hekimi muayenesi katılım payı tutarları 5 TL artırılarak tahsil edilir (§1.8.1).",
        },
    },

    # C000324 — katılım payı alınır (1.8.2)
    {
        "rule_id": "1.8.2.copay_required",
        "sut_section": "1.8.2",
        "gate_b_sources": ["C000324"],
        "condition": {"copay_required": True},
        "action": {
            "enforcement": "katılım payı alınır",
            "message_tr": "Bu kapsamdaki işlemlerde katılım payı alınır (§1.8.2).",
        },
    },

    # C000337 — katılım payı alınır (1.8.3)
    {
        "rule_id": "1.8.3.copay_required",
        "sut_section": "1.8.3",
        "gate_b_sources": ["C000337"],
        "condition": {"copay_required": True},
        "action": {
            "enforcement": "katılım payı alınır",
            "message_tr": "Bu kapsamdaki işlemlerde katılım payı alınır (§1.8.3).",
        },
    },

    # -----------------------------------------------------------------
    # §5.1  —  bilgilerin MEDULA sistemine girilmesi zorunluluğu
    # -----------------------------------------------------------------

    # C008040 — bilgilerin (istisnalar hariç) MEDULA sistemine girilmesi zorunlu
    {
        "rule_id": "5.1.medula_data_entry_mandatory",
        "sut_section": "5.1",
        "gate_b_sources": ["C008040"],
        "action": {
            "enforcement": "protokollü/sözleşmeli ve sözleşmesiz sunuculara, sundukları sağlık hizmetlerine ilişkin bedellerin ödenebilmesi için Kurum mevzuatı gereği istenilen bilgilerin belirlenen istisnalar hariç MEDULA sistemine girilmesi zorunludur",
            "message_tr": "Kurumla protokollü/sözleşmeli, sözleşmesiz sağlık hizmeti sunucularına, sundukları sağlık hizmetlerine ilişkin bedellerin ödenebilmesi için Kurum mevzuatı gereği istenilen bilgilerin belirlenen istisnalar hariç olmak üzere MEDULA sistemine girilmesi zorunludur (§5.1).",
        },
    },

    # C008042 — ulusal kayıt formları + geri ödemeye esas bilgi/belgelerin MEDULA'ya girilmesi zorunlu
    {
        "rule_id": "5.1.national_registry_forms_medula_mandatory",
        "sut_section": "5.1",
        "gate_b_sources": ["C008042"],
        "action": {
            "enforcement": "sözleşmeli sunucular, Kurumca belirlenen hizmetlere ait ulusal kayıt formlarını ve geri ödemeye esas diğer bilgi/belgelerini MEDULA sistemine girmek zorundadır; uyulacak kurallar Kurumca duyurulur",
            "message_tr": "Kurumla protokollü/sözleşmeli sağlık hizmeti sunucularının, sundukları sağlık hizmetlerine ilişkin bedellerin ödenebilmesi için, Kurumca belirlenecek sağlık hizmetlerine ait oluşturulan ulusal kayıt formlarını ve MEDULA sistemine girilmesi gerekli görülen geri ödemeye esas teşkil edecek diğer bilgi/belgelerini MEDULA sistemine girmesi zorunludur (§5.1).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2  —  fatura / e-fatura düzenleme
    # -----------------------------------------------------------------

    # C008046 — MEDULA provizyonlu hizmetler için tek fatura/e-fatura
    {
        "rule_id": "5.2.single_invoice_for_medula_provisioned_services",
        "sut_section": "5.2",
        "gate_b_sources": ["C008046"],
        "action": {
            "enforcement": "MEDULA sisteminden provizyon alarak MEDULA sistemine kaydettikleri hizmetler için (SUT'ta belirtilen istisnalar hariç) tek fatura/e-fatura düzenlenir",
            "message_tr": "MEDULA sisteminden provizyon alarak MEDULA sistemine kaydettikleri hizmetler için (SUT'ta belirtilen istisnalar hariç) tek fatura/e-fatura düzenlenir (§5.2).",
        },
    },

    # C008050 — MEDULA arızası nedeniyle provizyonsuz süre zarfında müstehak olmayanlara ait işlemler ayrı faturalandırılır
    {
        "rule_id": "5.2.medula_fault_ineligible_separate_invoice",
        "sut_section": "5.2",
        "gate_b_sources": ["C008050"],
        "action": {
            "enforcement": "Hizmet Sunumu Genel Müdürlüğü yetkililerince imzalanacak bir tutanak ile tevsik edilmek kaydıyla, MEDULA sisteminden kaynaklanan arıza nedeniyle provizyon alınamayan süre zarfında Kurumca karşılandığını beyan eden kişilerden, sonradan müstehak olmadığı tespit edilenlere ait tüm işlemler ayrı faturalandırılır",
            "message_tr": "Hizmet Sunumu Genel Müdürlüğü yetkililerince imzalanacak bir tutanak ile tevsik edilmesi kaydıyla MEDULA sisteminden kaynaklanan arıza nedeniyle provizyon numarasının alınamadığı süre zarfında sağlık hizmeti bedellerinin Kurumca karşılandığını yazılı olarak beyan etmek veya belgelemek suretiyle müracaat eden kişilerden daha sonra yapılan sorgulama sonucu müstehak olmadığı tespit edilenlere ait tüm işlemler ayrı faturalandırılır (§5.2).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.1  —  MEDULA hastane: tek fatura & dönem sonlandırma
    # -----------------------------------------------------------------

    # C008058 — her ay tek fatura; döneminde faturalandırılamayan hizmet 1 ay içinde dönem sonlandırmasına dahil;
    #           3./SGKB 2. basamakta patoloji/genetik/tüberküloz/diş protezi 4 ay; trafik kazası süresi dikkate alınmaz
    {
        "rule_id": "5.2.1.monthly_single_invoice_period_closing_windows",
        "sut_section": "5.2.1",
        "gate_b_sources": ["C008058"],
        "action": {
            "enforcement": "her ayın ilk ve son günü arasında verilen hizmetlere tek fatura; döneminde faturalandırılamayan hizmet işlem bitişini takip eden en geç 1 ay içindeki dönem sonlandırmasına dahil edilir; 3. basamak ve Sağlık Bakanlığı 2. basamak sunucularında patoloji/genetik/tüberküloz/diş protezi 4 ay içinde; trafik kazalarında dönem sonlandırma süresi dikkate alınmaz",
            "message_tr": "MEDULA hastane sistemini kullanan sağlık hizmeti sunucuları, sağlık hizmeti bedelleri Kurumca karşılanan kişiler için her ayın ilk ve son günü arasında verdikleri sağlık hizmetlerine ilişkin tek fatura düzenler. Herhangi bir nedenle döneminde faturalandırılamayan sağlık hizmeti, işlemin bittiği tarih itibarıyla faturalandırılması gereken dönemi takip eden en geç 1 ay içerisindeki dönem sonlandırılmasına dâhil edilir. Ancak üçüncü basamak sunucuları ile Sağlık Bakanlığına bağlı ikinci basamak sunucularında döneminde faturalandırılamayan patoloji, genetik, tüberküloz tetkikleri ve diş protezleri en geç 4 ay içerisindeki dönem sonlandırılmasına dahil edilir. Trafik kazası nedeniyle verilen sağlık hizmetleri için dönem sonlandırma süresi dikkate alınmaz (§5.2.1).",
        },
    },

    # C008061 — (b) bendi: nakiller/fotoferez/HBO/tüp bebek/plazmaferez/allogreft/diş protezleri/palyatif/yabancı vatandaş
    {
        "rule_id": "5.2.1.separate_invoicing_transplant_etc_categories",
        "sut_section": "5.2.1",
        "gate_b_sources": ["C008061"],
        "action": {
            "enforcement": "(a) bendinde sayılan haller hariç; kemik iliği ve kök hücre nakilleri, ekstrakorporeal fotoferez, hiperbarik oksijen, tüp bebek, plazmaferez, allogreft kullanılan tedaviler, ağız/diş tedavi protezleri (damak yarığı protezi, preoperatif aparey, velum uzantılı konuşma apareyi, optüratörler, çene defektleri, yüz protezleri), palyatif bakım ve yabancı ülke vatandaşlarına sunulan sağlık hizmetleri ayrı faturalandırılır",
            "message_tr": "(a) bendinde sayılan haller hariç olmak üzere 1.7 maddesinin ikinci fıkrasının (b) bendinde sayılan hallerdeki işlemler, kemik iliği, kök hücre nakilleri, ekstrakcorporeal fotoferez tedavisi, hiperbarik oksijen tedavileri, tüp bebek tedavileri, plazmaferez tedavileri, allogreftlerin kullanıldığı tedaviler, ağız ve diş tedavileri ile ilgili damak yarığı protezi, yenidoğanda preoperatif aparey, velum uzantılı konuşma apareyi, geçici optüratörler, basit ve komplike çene defektlerinin protetik tedavileri, yüz protezleri, palyatif bakım tedavisine ait işlemler, genel sağlık sigortalısı veya bakmakla yükümlü olduğu kişisi sayılan yabancı ülke vatandaşlarına sunulan sağlık hizmetleri ayrı faturalandırılır (§5.2.1).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.2  —  eczane reçete / kan ürünü-hemofili faturalama
    # -----------------------------------------------------------------

    # C008067 — aylık reçeteler ay sonuna provizyon dönem sonlandırmasıyla faturalandırılır
    {
        "rule_id": "5.2.2.monthly_prescription_period_closing_invoice",
        "sut_section": "5.2.2",
        "gate_b_sources": ["C008067"],
        "action": {
            "enforcement": "her ayın ilk ve son günü arasındaki döneme ait reçeteler, o aya ait son günün tarihini taşıyacak şekilde provizyon sistemi üzerinden dönem sonlandırması yapılarak faturalandırılır",
            "message_tr": "Her ayın ilk ve son günü arasındaki döneme ait reçeteler, o aya ait son günün tarihini taşıyacak şekilde provizyon sistemi üzerinden dönem sonlandırması yapılarak faturalandırılır (§5.2.2).",
        },
    },

    # C008068 — kan ürünü/hemofili reçeteleri ayda iki kere, her dönemden sonra 3 iş günü içinde faturalandırılır
    {
        "rule_id": "5.2.2.blood_hemophilia_prescriptions_twice_monthly",
        "sut_section": "5.2.2",
        "gate_b_sources": ["C008068"],
        "action": {
            "enforcement": "kan ürünü ve hemofili reçeteleri; her ayın 1'i ile 15'i arasındaki reçeteler takip eden 3 iş günü içinde, 16'sı ile ayın son günü arasındaki reçeteler takip eden 3 iş günü içinde olmak üzere ayda iki kere faturalandırılır",
            "message_tr": "Kan ürünü ve hemofili reçeteleri ise; her ayın 1'i ila 15'i arasında karşılanan reçeteler takip eden 3 iş günü içinde, her ayın 16'sı ila ayın son günü arasında karşılanan reçeteler ise takip edilen 3 iş günü içinde olmak üzere ayda iki kere faturalandırılır (§5.2.2).",
        },
    },

    # C008078 — ayrı ayrı faturalandırılır
    {
        "rule_id": "5.2.2.separate_invoicing",
        "sut_section": "5.2.2",
        "gate_b_sources": ["C008078"],
        "action": {
            "enforcement": "ilgili işlemler ayrı ayrı faturalandırılır",
            "message_tr": "İlgili işlemler ayrı ayrı faturalandırılır (§5.2.2).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.3  —  tek fatura & sevk belgesi
    # -----------------------------------------------------------------

    # C008082 — diğer kişiler için her ayın ilk ve son günü arasında tek fatura
    {
        "rule_id": "5.2.3.single_invoice_for_other_persons",
        "sut_section": "5.2.3",
        "gate_b_sources": ["C008082"],
        "action": {
            "enforcement": "(a) bendinde sayılan haller hariç, sağlık hizmeti bedelleri Kurumca karşılanan diğer kişiler için her ayın ilk ve son günü arasında verilen sağlık hizmetlerine ilişkin tek fatura düzenlenir",
            "message_tr": "(a) bendinde sayılan haller hariç olmak üzere sağlık hizmeti bedelleri Kurumca karşılanan diğer kişiler için, her ayın ilk ve son günü arasında verdikleri sağlık hizmetlerine ilişkin tek fatura düzenlenir (§5.2.3).",
        },
    },

    # C008083 — 60/c-1, 60/c-3 ve 12-14. fıkra kişilere sevk belgesi eklenir (e-sevk hariç)
    {
        "rule_id": "5.2.3.referral_document_for_60c_persons",
        "sut_section": "5.2.3",
        "gate_b_sources": ["C008083"],
        "action": {
            "enforcement": "müstehaklığı 60/c-1 veya 60/c-3 dönen kişiler ile 5510 md.60 on ikinci, on üçüncü, on dördüncü fıkralarında tanımlanan kişilere, götürü bedel protokolü yapan sunucular dışında (acil haller dışında) reçete düzenlenirse sevk belgesi eklenir (e-sevk hariç)",
            "message_tr": "Provizyon sisteminden yapılan sorgu neticesinde müstehaklıkları 60/c-1 veya 60/c-3 dönen kişiler ile 5510 sayılı Kanunun 60 ıncı maddesinin on ikinci, on üçüncü ve on dördüncü fıkralarında tanımlanan kişilere, Kurumla götürü bedel protokolü yapan sağlık hizmeti sunucuları dışında sunucularınca reçete düzenlenmesi halinde (acil haller dışında) sevk belgesi eklenir (e-sevk hariç) (§5.2.3).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.4  —  YUPASS onayı, sevk belgesi, engelli raporu
    # -----------------------------------------------------------------

    # C008090 — YUPASS/yabancı ülke protez-ortez-tıbbi cihaz için Kurum onayı
    {
        "rule_id": "5.2.4.yupass_prosthesis_orthosis_authorization",
        "sut_section": "5.2.4",
        "gate_b_sources": ["C008090"],
        "action": {
            "enforcement": "YUPASS numarası ile hasta takip/provizyon alınan kişiler de dahil, yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında sağlık hizmeti bedelleri Kurumca karşılanan kişilere sağlanacak protez-ortez, tıbbi araç-gereç ve kişiye mahsus tıbbi cihazların temini için Kurumun ilgili biriminden onay alınır",
            "message_tr": "YUPASS numarası ile hasta takip numarası/provizyon alınan kişiler de dahil olmak üzere yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında sağlık hizmeti bedelleri Kurumca karşılanan kişilere sağlanacak protez ve ortez, tıbbi araç ve gereç ile kişi kullanımına mahsus tıbbi cihazlarının temini için Kurumun ilgili biriminden onay alınır (§5.2.4).",
        },
    },

    # C008091 — 60/c-1,3 ve 12-14 fıkra kişilere sevk belgesi (e-sevk hariç)
    {
        "rule_id": "5.2.4.referral_document_for_60c_persons",
        "sut_section": "5.2.4",
        "gate_b_sources": ["C008091"],
        "action": {
            "enforcement": "müstehaklığı 60/c-1 veya 60/c-3 dönen kişiler ile 5510 md.60 on ikinci, on üçüncü, on dördüncü fıkralarında tanımlanan kişilere götürü bedel protokolü yapan sunucular dışında (acil haller dışında) reçete düzenlenirse sevk belgesi eklenir (e-sevk hariç)",
            "message_tr": "Provizyon sisteminden yapılan sorgu neticesinde müstehaklıkları 60/c-1 veya 60/c-3 dönen kişiler ile 5510 sayılı Kanunun 60 ıncı maddesinin on ikinci, on üçüncü ve on dördüncü fıkralarında tanımlanan kişilere, Kurumla götürü bedel protokolü yapan sağlık hizmeti sunucuları dışunda sunucularınca reçete düzenlenmesi halinde (acil haller dışında) sevk belgesi eklenir (e-sevk hariç) (§5.2.4).",
        },
    },

    # C008092 — engelli sağlık kurulu raporu aslı/onaylı fotokopisi reçete ekinde ibraz zorunlu
    {
        "rule_id": "5.2.4.disability_board_report_attachment_required",
        "sut_section": "5.2.4",
        "gate_b_sources": ["C008092"],
        "action": {
            "enforcement": "engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur",
            "message_tr": "Engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur (§5.2.4).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.5  —  YUPASS onayı, sevk belgesi, engelli raporu
    # -----------------------------------------------------------------

    # C008096 — YUPASS/yabancı ülke protez-ortez-tıbbi cihaz için Kurum onayı
    {
        "rule_id": "5.2.5.yupass_prosthesis_orthosis_authorization",
        "sut_section": "5.2.5",
        "gate_b_sources": ["C008096"],
        "action": {
            "enforcement": "YUPASS numarası ile hasta takip/provizyon alınan kişiler de dahil, yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında Kurumca karşılanan kişilere sağlanacak protez-ortez, tıbbi araç-gereç ve kişiye mahsus tıbbi cihazların temini için Kurumun ilgili biriminden onay alınır",
            "message_tr": "YUPASS numarası ile hasta takip numarası/provizyon alınan kişiler de dahil olmak üzere yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında sağlık hizmeti bedelleri Kurumca karşılanan kişilere sağlanacak protez ve ortez, tıbbi araç ve gereç ile kişi kullanımına mahsus tıbbi cihazlarının temini için Kurumun ilgili biriminden onay alınır (§5.2.5).",
        },
    },

    # C008097 — 60/c-1,3 ve 12-14 fıkra kişilere sevk belgesi (e-sevk hariç)
    {
        "rule_id": "5.2.5.referral_document_for_60c_persons",
        "sut_section": "5.2.5",
        "gate_b_sources": ["C008097"],
        "action": {
            "enforcement": "müstehaklığı 60/c-1 veya 60/c-3 dönen kişiler ile 5510 md.60 on ikinci, on üçüncü, on dördüncü fıkralarında tanımlanan kişilere götürü bedel protokolü yapan sunucular dışında (acil haller dışında) reçete düzenlenirse sevk belgesi eklenir (e-sevk hariç)",
            "message_tr": "Provizyon sisteminden yapılan sorgu neticesinde müstehaklıkları 60/c-1 veya 60/c-3 dönen kişiler ile 5510 sayılı Kanunun 60 ıncı maddesinin on ikinci, on üçüncü ve on dördüncü fıkralarında tanımlanan kişilere, Kurumla götürü bedel protokolü yapan sağlık hizmeti sunucuları dışında sunucularınca reçete düzenlenmesi halinde (acil haller dışında) sevk belgesi eklenir (e-sevk hariç) (§5.2.5).",
        },
    },

    # C008098 — engelli sağlık kurulu raporu aslı/onaylı fotokopisi reçete ekinde ibraz zorunlu
    {
        "rule_id": "5.2.5.disability_board_report_attachment_required",
        "sut_section": "5.2.5",
        "gate_b_sources": ["C008098"],
        "action": {
            "enforcement": "engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur",
            "message_tr": "Engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur (§5.2.5).",
        },
    },

    # -----------------------------------------------------------------
    # §5.2.6  —  YUPASS onayı, sevk belgesi, engelli raporu
    # -----------------------------------------------------------------

    # C008102 — YUPASS/yabancı ülke protez-ortez-tıbbi cihaz için Kurum onayı
    {
        "rule_id": "5.2.6.yupass_prosthesis_orthosis_authorization",
        "sut_section": "5.2.6",
        "gate_b_sources": ["C008102"],
        "action": {
            "enforcement": "YUPASS numarası ile hasta takip/provizyon alınan kişiler de dahil, yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında Kurumca karşılanan kişilere sağlanacak protez-ortez, tıbbi araç-gereç ve kişiye mahsus tıbbi cihazların temini için Kurumun ilgili biriminden onay alınır",
            "message_tr": "YUPASS numarası ile hasta takip numarası/provizyon alınan kişiler de dahil olmak üzere yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında sağlık hizmeti bedelleri Kurumca karşılanan kişilere sağlanacak protez ve ortez, tıbbi araç ve gereç ile kişi kullanımına mahsus tıbbi cihazlarının temini için Kurumun ilgili biriminden onay alınır (§5.2.6).",
        },
    },

    # C008103 — 60/c-1,3 ve 12-14 fıkra kişilere sevk belgesi (e-sevk hariç)
    {
        "rule_id": "5.2.6.referral_document_for_60c_persons",
        "sut_section": "5.2.6",
        "gate_b_sources": ["C008103"],
        "action": {
            "enforcement": "müstehaklığı 60/c-1 veya 60/c-3 dönen kişiler ile 5510 md.60 on ikinci, on üçüncü, on dördüncü fıkralarında tanımlanan kişilere götürü bedel protokolü yapan sunucular dışında (acil haller dışında) reçete düzenlenirse sevk belgesi eklenir (e-sevk hariç)",
            "message_tr": "Provizyon sisteminden yapılan sorgu neticesinde müstehaklıkları 60/c-1 veya 60/c-3 dönen kişiler ile 5510 sayılı Kanunun 60 ıncı maddesinin on ikinci, on üçüncü ve on dördüncü fıkralarında tanımlanan kişilere, Kurumla götürü bedel protokolü yapan sağlık hizmeti sunucuları dışında sunucularınca reçete düzenlenmesi halinde (acil haller dışında) sevk belgesi eklenir (e-sevk hariç) (§5.2.6).",
        },
    },

    # C008104 — engelli sağlık kurulu raporu aslı/onaylı fotokopisi reçete ekinde ibraz zorunlu
    {
        "rule_id": "5.2.6.disability_board_report_attachment_required",
        "sut_section": "5.2.6",
        "gate_b_sources": ["C008104"],
        "action": {
            "enforcement": "engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur",
            "message_tr": "Engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin reçete ekinde ibrazı zorunludur (§5.2.6).",
        },
    },

    # -----------------------------------------------------------------
    # §5.3.1 / 5.3.1.B / 5.3.1.C / 5.3.1.Ç  —  incelemeye esas belgeler
    # -----------------------------------------------------------------

    # C008121 — incelemeye esas belgeler örneklemeye düşenler Kuruma gönderilir, diğerleri muhafaza edilir
    {
        "rule_id": "5.3.1.examination_documents_submission_sampling",
        "sut_section": "5.3.1",
        "gate_b_sources": ["C008121"],
        "action": {
            "enforcement": "incelemeye esas belgelerden örneklemeye düşenler incelenmek ve ödeme yapılmak üzere Kuruma gönderilir; örnekleme dışı kalanlar ihtiyaç duyulması halinde ibraz edilmek üzere sunucuda muhafaza edilir; belgeler elektronik olarak Kurum bilgi işlem sistemine intikal ettirilir",
            "message_tr": "Aşağıda sayılan incelemeye esas belgeler, incelenmek ve ödeme yapılmak üzere Kuruma gönderilir. Ancak örnekleme yöntemi ile incelenen işlemlere ait belgelerden örneklemeye düşmüş olanlar Kuruma gönderilir, örnekleme dışında kalan işlemlere ait olanlar ise ihtiyaç duyulması halinde Kuruma ibraz edilmek üzere sağlık hizmeti sunucularında muhafaza edilir. İncelemeye esas belgeler elektronik olarak düzenlenerek ve/veya elektronik ortama aktarılarak Kurum bilgi işlem sistemine intikal ettirilir (§5.3.1).",
        },
    },

    # C008148 — T.C. Kimlik Numarası, hasta ad-soyad (6284 sayılı Kanun kapsamı koruyucu tedbir kişileri hariç)
    {
        "rule_id": "5.3.1.B.patient_identity_fields_with_6284_exception",
        "sut_section": "5.3.1.B",
        "gate_b_sources": ["C008148"],
        "action": {
            "enforcement": "hizmet detay belgesinde T.C. Kimlik Numarası ve hasta ad-soyad yer alır; 6284 sayılı Kanun hükümlerine göre hakkında koruyucu tedbir kararı verilen kişiler hariç",
            "message_tr": "T.C. Kimlik Numarası, hasta adı soyadı, (8/3/2012 tarihli ve 6284 sayılı Ailenin Korunması ve Kadına Karşı Şiddetin Önlenmesine Dair Kanun hükümlerine göre hakkında koruyucu tedbir kararı verilen kişiler hariç) bilgileri hizmet detay belgesinde yer alır (§5.3.1.B).",
        },
    },

    # C008152 — hizmet detay belgesi MEDULA'ya elektronik kaydedilir; epikriz yatarak/cerrahide ayrıntılı
    {
        "rule_id": "5.3.1.C.service_detail_document_medula_epicrisis",
        "sut_section": "5.3.1.C",
        "gate_b_sources": ["C008152"],
        "action": {
            "enforcement": "MEDULA sistemini kullanan sunucular tedaviye ait hizmet detay belgesini MEDULA'ya elektronik kaydeder; belge Kuruma teslim edilmez ancak talep halinde başhekimlikçe onaylanarak teslim edilir; epikriz bölümü yatarak ve cerrahi işlemlerde ayrıntılı düzenlenmek zorundadır",
            "message_tr": "MEDULA sistemini kullanan sağlık hizmeti sunucuları, tedaviye ait hizmet detay belgesini MEDULA sistemine elektronik olarak kaydeder. Hizmet detay belgesi Kurumun ilgili birimine teslim edilmez. Ancak Kurum tarafından fatura incelemesi dışında başka bir nedenle talep edilmesi halinde, hizmet detay belgesinin dökümü başhekimlikçe onaylanarak teslim edilir. Hizmet detay belgesindeki epikriz bölümü, yatarak tedavilerde ve cerrahi işlemlerin yapıldığı tüm sağlık hizmetlerinde elektronik ortamda ayrıntılı olarak düzenlenmek zorundadır (§5.3.1.C).",
        },
    },

    # C008172 — sevkle başvuran hastalar için tedavi sevk belgesi (e-sevk hariç)
    {
        "rule_id": "5.3.1.Cc.referral_document_for_referred_patients",
        "sut_section": "5.3.1.Ç",
        "gate_b_sources": ["C008172"],
        "action": {
            "enforcement": "sevkle başvuran hastalar için tedavi sevk belgesi (e-sevk hariç) bulundurulur",
            "message_tr": "Sevkle başvuran hastalar için tedavi sevk belgesi (e-sevk hariç) incelemeye esas belgeler arasında yer alır (§5.3.1.Ç).",
        },
    },

    # C008183 — ortodontik tedavi gereksinimi olan hastalar için sağlık kurulu raporu (e-rapor hariç)
    {
        "rule_id": "5.3.1.Cc.orthodontic_board_report_required",
        "sut_section": "5.3.1.Ç",
        "gate_b_sources": ["C008183"],
        "action": {
            "enforcement": "ortodontik tedavi gereksinimi olan hastalar için düzenlenecek sağlık kurulu raporu (e-rapor hariç) bulundurulur",
            "message_tr": "Ortodontik tedavi gereksinimi olan hastalar için düzenlenecek sağlık kurulu raporu (e-rapor hariç) incelemeye esas belgeler arasında yer alır (§5.3.1.Ç).",
        },
    },

    # -----------------------------------------------------------------
    # §5.3.2  —  tıbbi malzeme faturası
    # -----------------------------------------------------------------

    # C008213 — ibrazı zorunludur (5.3.2 header)
    {
        "rule_id": "5.3.2.document_submission_required",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008213"],
        "action": {
            "enforcement": "ilgili belgenin ibrazı zorunludur",
            "message_tr": "İlgili belgenin ibrazı zorunludur (§5.3.2).",
        },
    },

    # C008214 — fatura arka yüzünde teslim alan kişi ad/soyad, T.C., telefon, ıslak imza + "Teslim aldım"
    {
        "rule_id": "5.3.2.invoice_back_delivery_signature",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008214"],
        "action": {
            "enforcement": "fatura arka yüzünde; tıbbi cihazı/sarf malzemeyi teslim alan kişinin ad-soyad, T.C. Kimlik Numarası, telefon numarası ve ıslak imzası yer almalı; teslim aldığına dair 'Teslim aldım' ibaresi ve teslim alınan miktar belirtilmelidir (Kurumca iade alınan cihazlar hariç)",
            "message_tr": "Fatura arka yüzünde; tıbbi cihazı/sarf malzemeyi teslim alan kişinin adı ve soyadı, T.C. Kimlik Numarası, telefon numarası, ıslak imzası yer almalı ve faturadaki tıbbi malzeme/malzemeleri teslim aldığına dair 'Teslim aldım' ibaresi ve teslim alınan tıbbi malzeme miktarı belirtilmelidir (Kurumca iade alınan tıbbi cihazlar hariç) (§5.3.2).",
        },
    },

    # C008215 — YUPASS/yabancı ülke protez-ortez-tıbbi cihaz için Kurum onayı
    {
        "rule_id": "5.3.2.yupass_prosthesis_orthosis_authorization",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008215"],
        "action": {
            "enforcement": "YUPASS numarası ile hasta takip/provizyon alınan kişiler de dahil, yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında Kurumca karşılanan kişilere sağlanacak protez-ortez, tıbbi araç-gereç ve kişiye mahsus tıbbi cihazların temini için Kurumun ilgili biriminden onay alınır",
            "message_tr": "YUPASS numarası ile hasta takip numarası/provizyon alınan kişiler de dahil olmak üzere yabancı ülkelerle yapılan sosyal güvenlik sözleşmesi kapsamında sağlık hizmeti bedelleri Kurumca karşılanan kişilere sağlanacak protez ve ortez, tıbbi araç ve gereç ile kişi kullanımına mahsus tıbbi cihazlarının temini için Kurumun ilgili biriminden onay alınır (§5.3.2).",
        },
    },

    # C008221 — ibrazı zorunludur (5.3.2)
    {
        "rule_id": "5.3.2.document_submission_required_b",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008221"],
        "action": {
            "enforcement": "ilgili belgenin ibrazı zorunludur",
            "message_tr": "İlgili belgenin ibrazı zorunludur (§5.3.2).",
        },
    },

    # C008223 — fatura arkasında branş uzmanı uygulama/onay (ısmarlama protez-ortez için)
    {
        "rule_id": "5.3.2.specialist_fitting_approval_on_invoice",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008223"],
        "action": {
            "enforcement": "fatura arkasında reçetenin düzenlendiği branşın uzman hekimlerinden biri tarafından reçetedeki malzemenin (ısmarlama eksternal protez ve ortezler için) hasta üzerinde uygulandığının görüldüğü ve uygunluğunun belirtilerek onaylanması gerekir (tıbbi uygunluk gerektirmeyen malzemeler ve işitme cihazları hariç)",
            "message_tr": "Fatura arkasında reçetenin düzenlendiği branşın uzman hekimlerinden biri tarafından reçetede yazan malzemenin (ısmarlama eksternal protez ve ortezler için) hasta üzerinde uygulandığının görüldüğü ve uygunluğunun belirtilerek onaylanması gerekir (tıbbi uygunluk gerektirmeyen tıbbi malzemeler ve işitme cihazları hariç) (§5.3.2).",
        },
    },

    # C008224 — SUT eki malzemelerden duyurulanların aylık nakdi ödeme (diğer fıkra koşulları aranmaz)
    {
        "rule_id": "5.3.2.announced_materials_monthly_cash_payment",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008224"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "ayakta tedavide kullanımı sağlık raporu ile uygun görülen ve Kurumca duyurulan SUT eki malzemelerden olanların ödemesi; sağlık raporu ve bir defaya mahsus bu rapora göre düzenlenen reçeteye istinaden, reçete tarihi esas alınarak aylık nakdi ödeme şeklinde yapılabilir; bu durumda diğer fıkra koşulları aranmaz",
            "message_tr": "Sağlık hizmeti bedelleri Kurumca karşılanan kişilerin ayakta tedavileri sırasında kullanmaları sağlık raporu ile uygun görülen SUT eki listelerde yer alan malzemelerden Kurumca duyurulacak olanların ödemesi; SUT hükümleri ve ilgili mevzuat doğrultusunda düzenlenecek sağlık raporu ve bir defaya mahsus olmak üzere sağlık raporuna göre düzenlenen reçeteye istinaden reçete tarihi esas alınmak kaydıyla aylık nakdi ödeme şeklinde yapılabilir. Bu fıkra kapsamında yapılacak ödemelerde bu maddenin diğer fıkralarında yer alan hususlar aranmaz (§5.3.2).",
        },
    },

    # C008225 — Sağlık Bakanlığı protokolü kapsamında iadeli tıbbi cihaz + hizmet bedeli ödenir
    {
        "rule_id": "5.3.2.moh_protocol_returnable_device_payment",
        "sut_section": "5.3.2",
        "gate_b_sources": ["C008225"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "Sağlık Bakanlığı ile yapılan protokol kapsamında Sağlık Bakanlığı tarafından iadeli tıbbi cihazlar ile verilen sağlık hizmetleri karşılığında hizmet ve/veya cihaz bedeli ödenir",
            "message_tr": "Sağlık Bakanlığı ile yapılan protokol kapsamında Sağlık Bakanlığı tarafından iadeli tıbbi cihazlar ile verilen sağlık hizmetleri karşılığında hizmet ve/veya cihaz bedeli ödenir (§5.3.2).",
        },
    },

    # -----------------------------------------------------------------
    # §6.1  —  birim puanlar KDV hariç
    # -----------------------------------------------------------------

    # C008231 — birim puanlar/fiyatlar KDV hariç; KDV ilgili mevzuatı çerçevesinde ayrıca ödenir
    {
        "rule_id": "6.1.unit_points_excluding_vat",
        "sut_section": "6.1",
        "gate_b_sources": ["C008231"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "SUT ve eki listelerde yer alan birim puanlar/fiyatlar katma değer vergisi hariç tespit edilmiştir; katma değer vergisi ilgili mevzuatı çerçevesinde ayrıca ödenir",
            "message_tr": "SUT ve eki listelerde yer alan birim puanlar/fiyatlar katma değer vergisi hariç olarak tespit edilmiştir. Katma değer vergisi, ilgili mevzuatı çerçevesinde ayrıca ödenecektir (§6.1).",
        },
    },

    # -----------------------------------------------------------------
    # §6.3.1  —  25.02.2011 öncesi trafik kazası bedelleri
    # -----------------------------------------------------------------

    # C008236 — 6111 yürürlük (25.02.2011) öncesi trafik kazası bedelleri SUT kısıtlamaları dikkate alınmaksızın
    {
        "rule_id": "6.3.1.pre_2011_traffic_accident_no_sut_restrictions",
        "sut_section": "6.3.1",
        "gate_b_sources": ["C008236"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "6111 sayılı Kanunun yürürlüğe girdiği 25.02.2011 tarihinden önce trafik kazaları nedeniyle sağlanan sağlık hizmeti bedelleri, SUT ve eklerindeki kısıtlamalar dikkate alınmaksızın Kurumca bu hizmetler için ödenen tutarlar üzerinden karşılanır",
            "message_tr": "6111 sayılı Kanunun yürürlüğe girdiği 25.02.2011 tarihinden önce trafik kazaları nedeniyle sağlanan sağlık hizmeti bedelleri, SUT ve eklerinde yer alan kısıtlamalar dikkate alınmaksızın Kurumca bu sağlık hizmetleri için ödenen tutarlar üzerinden karşılanır (§6.3.1).",
        },
    },

    # -----------------------------------------------------------------
    # §6.3.2  —  aynı işlevli malzeme garanti süresi / fiyatsız malzeme
    # -----------------------------------------------------------------

    # C008243 — 28.07.2012 sonrası raporla temin istenen aynı işlevli malzeme, öncekinin garantisi dolana kadar karşılanmaz
    {
        "rule_id": "6.3.2.same_function_device_within_warranty_no_pay",
        "sut_section": "6.3.2",
        "gate_b_sources": ["C008243"],
        "pay": False,
        "action": {
            "enforcement": "no-pay condition: 28.07.2012 tarihinden sonra düzenlenen sağlık kurulu raporuna istinaden temin edilmek istenen tıbbi malzeme bedeli, aynı işlevi gören başka bir malzemenin daha önceden temin edilmiş olması halinde, önceki malzemenin garanti süresi dolana kadar Kurumca karşılanmaz",
            "message_tr": "28.07.2012 tarihinden sonra düzenlenen sağlık kurulu raporuna istinaden temin edilmek istenen tıbbi malzeme bedeli, aynı işlevi gören başka bir tıbbi malzemenin daha önceden temin edilmiş olması halinde, temin edilmiş olan malzemenin garanti süresi dolana kadar Kurumca karşılanmaz (§6.3.2).",
        },
    },

    # C008250 — fiyatsız tıbbi malzeme olarak fatura edilirse SUT hükümleri doğrultusunda bedeli karşılanır
    {
        "rule_id": "6.3.2.unpriced_device_payment_per_sut",
        "sut_section": "6.3.2",
        "gate_b_sources": ["C008250"],
        "condition": {"coverage_note": True},
        "action": {
            "enforcement": "fiyatsız tıbbi malzemeler şeklinde fatura edilmesi halinde, SUT eki listelerde fiyatı belirli olmayan tıbbi malzemelerin ödenmesine ilişkin SUT hükümleri doğrultusunda bedelleri Kurumca karşılanır",
            "message_tr": "Yeni düzenlemeye göre fiyatsız tıbbi malzemeler şeklinde fatura edilmesi halinde ise SUT eki listelerde fiyatı belirli olmayan tıbbi malzemelerin ödenmesine ilişkin SUT hükümleri doğrultusunda bedelleri Kurumca karşılanacaktır (§6.3.2).",
        },
    },
]
