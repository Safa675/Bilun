# Task: MDS epoetin alfa/beta klinik taslağı

## Goal

§4.2.9.A-2'nin doğrulanmış Ekim kaynağından dar, tipli ve incelenebilir bir aday değerlendirme hazırlamak; yeni MDS kaynak/tarih admission veya ödeme uygunluğu etkinleştirmemek.

## Context and ownership

- Depo: `Safa675/Bilun`; doğrulanmış taban `3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e`.
- İzole checkout: `task-3/mds-clinical`; dal: `codex/mds-epoetin-clinical-draft`.
- Ana checkout'taki mevcut kirli dosyalar korunur. Erişkin GH işi ayrı çalışma alanında devam eder.
- Aktif PR #158 deployment sahibi yalnız deployment scripts/tests kapsamını taşır; bu taslak ona kaynak veya hedef değişikliği aktarmayacak.

| Owner | Kesin yazım kapsamı |
| --- | --- |
| Source proof | `data/gazette/clinical_sources/mds_candidate_2026_10.json`, bu plan |
| Backend | `src/bilun/domain/claims/mds_evidence.py`, `src/bilun/domain/prose_rules/_drug_indication/clinical_mds.py`, `tests/unit/domain/claims/test_mds_evidence_transport.py`, `tests/unit/domain/prose_rules/test_mds_clinical_draft.py` |
| API scout | `src/bilun/api/mds_clinical_draft.py`, `tests/unit/api/test_mds_clinical_draft_api.py` |
| Frontend | `frontend/src/lib/api/mdsClinicalDraft.ts`, `frontend/src/components/tabs/sut/sections/MdsClinicalDraft.tsx`, `frontend/src/components/tabs/sut/sections/mdsClinicalDraft.test.tsx` |
| Coordinator | Bu plan, commit/PR/CI koordinasyonu ve açıkça atanmış `data/gazette/sut_coverage_evidence.json` dependency hash kapanışı |

`claims/models.py`, adapter/parsing/shared models/validation, `clinical.py`, mevcut frontend clinical fields/evidence/SUT messages, mevcut kaynak repairs/catalog ve coverage dosyaları ortak kapsamdır. Bu dört owner bu dosyalara yazmaz. Erişkin GH ile ortak entegrasyon, açık dosya sahipliği ve ayrı inceleme gerektirir.

PR #159 CI sonrası parent, koordinatörü kanonik coverage JSON için tek yazar olarak atadı. Dar düzeltme yalnız `clinical_mds.py` dependency hash satırını ekler; semantic counts, dört coverage parquet, kaynak admission ve runtime dispatch değişmez. Parent talebiyle `tasks/todo.md` PR farkından çıkarılır; görev planı bu deliverable'da kalır. Deployment Git-pack hatası önce salt okunur fixture/taban karşılaştırmasıyla incelenir; production deployment kodu kapsam dışıdır.

## Subtasks

- [x] Exact base, depo bağlamı ve Ekim DOCX byte pinini doğrula.
- [x] §4.2.9.A genel ESA ve §4.2.9.A-2 özel MDS metnini XML run strike durumundan bağımsız oku.
- [x] Yedi paragrafın yürürlükteki metni, paraId'si ve tam normalize hash'ini korpusla eşleştir.
- [x] Aday kaynak kanıtını izole JSON'a kaydet; çizili darbepoetin parçalarını ve tarih sınırlarını koru.
- [x] Dar tipli evidence ve aday evaluatorü benzersiz backend dosyalarında tamamla.
- [x] Standalone API payload helperları ve bağlantısız frontend formunu tamamla.
- [x] Başlangıç/devam/durdurma sınırları, substance ayrımı, eksik/geçersiz evidence ve MDS/CKD ayrımını yeni focused testlerle doğrula.
- [x] İlk exact HEAD üzerinde bağımsız kaynak/klinik yorum ve kod incelemesi yap (`eb519dba`, P1/P2 bulgu yok).
- [x] Dar Draft PR #159 oluştur.
- [x] Coverage dependency hash kapanışını currentness regresyonuyla doğrula (**1 PASS**); semantic JSON değerleri ve beş corpus/coverage parquet SHA'sı değişmedi.
- [ ] Fixture Git-pack CI hatasının taban/HEAD karşılaştırmasını tamamla; deployment dosyalarına yazmadan yeni hosted koşuda doğrula.
- [ ] Yeni son exact HEAD'i bağımsız incelet; hosted full CI sonucunu PR üzerinde kaydet.

## Source proof

Kaynak: SGK'nin [02/10/2026 işlenmiş güncel 2013 SUT duyurusu](https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06). Duyuru web aracında erişilebilir ve Ekim ZIP adını içerir. Web ZIP okuyucusu paketi açamadığı için yeni bir uzak byte capture iddiası yoktur. Yerel DOCX ve mevcut resmi raw-byte receipt hash'i aynı:

`227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573` (1.200.635 byte).

Korpus pin: `40b2b7ebdb44c2483867d5413f7af3d97bb55c92d43d3a4be2737d80135425ec`.

Paragraf index'i, `document.xml` içindeki bütün `w:p` elemanlarının sıfırdan başlayan sırasıdır; tablolardaki paragraflar da sayılır. Doğrudan body-paragraf index'i bu kimlik değildir.

| Paragraf | XML paraId | Kaynak ref | Rol |
| --- | --- | --- | --- |
| 4477 | `28D52EBF` | `4.2.9.A.(1)#d8313b78` | ESA endikasyon sınırı; genel MDS bağlamı |
| 4478 | `156F17DA` | `4.2.9.A.(2)#8b36884a` | Tetkik belge tarihi ve sonucu |
| 4479 | `61F2BE17` | `4.2.9.A.(3)#a9d0cf5b` | Genel endikasyon muadili hükmü |
| 4480 | `38736587` | `4.2.9.A.(4)#ed1d5fdf` | Raporda doz/süre; bir aylık supply sınırı |
| 4487 | `40D6098F` | `4.2.9.A-2#678e9289` | MDS başlığı |
| 4488 | `6E398DFC` | `4.2.9.A-2.(1)#6369cafd` | Yalnız 2013 değişiklik annotation'ı yürürlükte; eski gövde çizili |
| 4489 | `3108F0FD` | `4.2.9.A-2#17efb08b` | Yürürlükteki özel MDS gövdesi |

4489'un tam normalize hash'i: `17efb08ba397a16ad5177e6c27ba7c34c565a4a436de28ff83a3ebf07f23207f`. Silinen iki contiguous run grubu JSON'da birebir korunur: `), darbepoetin için maksimum doz haftada 150 µg’ı` ve `ve darbepoetin`. İlk grubun kapanış parantezi de çizili olduğu için yürürlükteki metinde dengesiz parantez kalır; hash için metin düzeltilmez.

## Candidate interpretation

- Başlangıç koşulları birlikte gereklidir: Hb **<11 gr/dl**, blast **<%5**, serum EPO **<500 mu/ml**. Eşitlik başlangıç koşulunu karşılamaz. Başlangıç fazı ve tarihli/birimli kanıt olmadan başlangıç kontrolü unknown kalır.
- Hb **>12 gr/dl** durumunda durdurma kontrolü vardır; **Hb=12** için kaynak durdurma emri vermez. Hedef Hb 12 ifadesinden ek stop veya restart protokolü türetilmez.
- Özel gövde yalnız **eritropoietin alfa-beta** için haftalık maksimum **900 IU/kg** sınırını korur. Tam sınır değer eşitliği uygundur. Aday exact alfa/beta ingredient kimliği ister; marka, generic ESA adı veya `beta` substring'i yeterli değildir.
- Genel A.(3) alfa/beta/zeta, PEG epoetin beta, darbepoetin ve roksadustatı endikasyon muadili olarak isimlendirir. Bu cümle alfa/beta dozunu veya MDS numeric/report koşullarını diğer maddelere aktarmaya tek başına yetmez. PEG epoetin beta plain epoetin beta değildir.
- Hematoloji uzman hekim raporu gerekir; reçete hematoloji **veya** iç hastalıkları uzmanından olabilir. Genel A.(4) raporda kullanım **dozu ve süresini** ister. Bir defada en fazla **bir aylık** ilaç verilir; 30 günlük eşdeğerlik varsayılmaz.
- Genel A.(2), gerekli tetkik sonuç belgesinin **tarih ve sonucunun reçete veya raporda** bulunmasını ister. Numeric lab değeri ve tarihi bu belge konumunu kanıtlamaz; explicit belge konumu kanıtı ayrıca gerekir. MDS gövdesi hemogram sonuç belgesinin **tarih ve sonucunun reçetede** olmasını ister. Genel A.(2)'deki reçete/rapor alternatifi bu daha dar gerekliliğin yerine geçmez. MDS hemogramı için azami test yaşı veya CKD cadence'i kaynakta yoktur.
- EPO birimi metinde `mu/ml` yazılır; başka birime sessiz conversion yapılmaz. Birim, sayı, tarih veya faz eksik/geçersizse unknown/review korunur.
- Kaynak MDS hastalığını isimlendirir; ICD-10 aralığı vermez. D47 umbrella kodu veya CKD-only kanıt MDS uygunluğu yerine kullanılmaz.
- Darbepoetin/Aranesp özel parçaları 17/05/2024 annotation'ı ile çizili, genel MDS/ESA bağlamı ise aktiftir. Bu gerilim **REVIEW**'da kalır; mutlak ödeme yasağı veya alfa/beta eligibility aktarımı yapılmaz.

## Admission and integration gates

Bu kanıt `candidate_only=true`, `clinical_eligibility_complete=false`, `mechanical_family_admission=false`, boş `admitted_service_date_windows` ve `ai_generated_pending_review` taşır. Ekim observation günü hukuki başlangıç değildir. 2013'teki çizili gövde annotation'ı ve 2024 deletion annotation'ı historical source gaps'i doldurmaz.

Mevcut `clinical_versions.json` ve 5 Ekim receipt yalnız on iki isimli aileyi içerir; MDS bunlardan biri değildir. Renal binding'ler §4.2.9.B/Ç/D kapsamındadır. Followup ailesinin mevcut kaynak admission'ı da bağımsız MDS numeric admission değildir. Yeni MDS ailesi için exact source bindings, bağımsız yorum ve açık service-date admission gerekir. On iki aile için continuity yenilemesi bunu otomatik onaylamaz.

Standalone API yardımcıları registered endpoint değildir. Yeni component ve payload helperları mevcut `/api/validate-claim`, shared request schema, adapter, evaluator dispatch veya mevcut klinik form ile bağlanmaz. Bu taslak paylaşılan entegrasyon için somut inceleme çıktısı verir; üretimde kullanıcıya klinik pay-clear üretmez.

## Validation and review

Kaynak incelemesinde yedi XML operative text'i korpusla ve normalize hash/ref'lerle birebir eşleşti. İlgili paragraflarda tracked deletion veya double strike bulunmadı; DOCX styles içinde inherited strike tanımı yoktur.

JSON/DOCX kaynak proof kontrolü, depo modülü import etmeden ve dosya yazmadan yeniden üretilebilir:

```bash
python -B - <<'PY'
import hashlib, json, re, unicodedata, xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
p = json.loads(Path('data/gazette/clinical_sources/mds_candidate_2026_10.json').read_text())
doc = Path(p['source_docx']['path']).read_bytes()
assert len(doc) == p['source_docx']['bytes']
assert hashlib.sha256(doc).hexdigest() == p['source_docx']['sha256']
assert hashlib.sha256(Path(p['source_corpus']['path']).read_bytes()).hexdigest() == p['source_corpus']['sha256']
w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
pid = '{http://schemas.microsoft.com/office/word/2010/wordml}paraId'
from io import BytesIO
ps = list(ET.fromstring(ZipFile(BytesIO(doc)).read('word/document.xml')).iter(w + 'p'))
for row in p['paragraphs']:
    para = ps[row['paragraph_index']]
    assert para.get(pid) == row['xml_para_id']
    groups = []
    for run in para.iter(w + 'r'):
        text = ''.join(t.text or '' for t in run.iter(w + 't'))
        struck = any(z is not None and (z.get(w + 'val') or '').lower() in ('', 'true', '1', 'on') for z in (run.find(w + 'rPr/' + w + 'strike'), run.find(w + 'rPr/' + w + 'dstrike')))
        if text and groups and groups[-1][0] == struck:
            groups[-1][1] += text
        elif text:
            groups.append([struck, text])
    operative = ''.join(text for struck, text in groups if not struck).strip()
    assert operative == row['operative_text']
    assert [text for struck, text in groups if struck] == row['struck_fragments']
    normalized = re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', operative)).strip()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    assert digest == row['operative_text_sha256']
    assert row['source_ref'].endswith('#' + digest[:8])
assert p['candidate_only'] and not p['mechanical_family_admission']
assert not p['clinical_eligibility_complete'] and not p['admitted_service_date_windows']
print('MDS source proof PASS:', len(p['paragraphs']), 'paragraphs; no clinical admission')
PY
```

Uygulama dondurulduktan sonra owner focused sonuçları koordinatör tarafından doğrulandı:

| Kontrol | Kanıt kapsamı | Sonuç |
| --- | --- | --- |
| Backend | `test_mds_evidence_transport.py`, `test_mds_clinical_draft.py` | **290 PASS** |
| API | `test_mds_clinical_draft_api.py` | **63 PASS** |
| Frontend | Dört focused test dosyası; `mdsClinicalDraft.test.tsx` içinde 27 yeni test dahil | **118 PASS** |
| TypeScript | Frontend `tsc` | **exit 0** |
| Scoped Ruff | Yeni Python backend/API/test dosyaları | **exit 0** |

Bu sonuçlar ayrı owner koşularıdır; sayıları full-suite sonucu gibi toplanmaz. Kaynak proof commit'i `27ea41b9732072630fc28b8d0151a97042c44920` olup uygulama/test dosyaları sonraki bağımlı commit'lere hazırlanır; yukarıdaki sonuçlar henüz final commit HEAD için hosted CI veya bağımsız review sonucu değildir.

Mevcut kaynak/context ve klinik güvenlik regresyonları **63 PASS**; mevcut validator API kontratı **28 PASS**. İlk sandbox koşusu TestClient/AnyIO portal fixture aşamasında bekledi; traceback ile ortam sınırı ayrıştırılıp aynı 28 test izinli normal ortamda 1,98 saniyede geçti. Kesilmiş koşunun kısmi çıktısı sayılmadı; kod değişikliği gerekmedi. Exact final HEAD bağımsız kaynak/klinik yorum ve kod incelemesi, Draft PR ve hosted full CI **pending** kalır. Laptop full suite tekrar edilmeyecek; hosted full CI ayrı sonuç olarak raporlanacak. Clinical source/date admission ve merge/deploy bu taslağın tamamlanma ölçütü değildir.

## Out of Scope

VPS, deployment hedefi/script değişikliği, main yazımı, merge/deploy, dependency sürümü/global config, genel ESA mimarisi, ilaç fiyatı/listing/product equivalence, tam klinik eligibility ve pay-clear; ortak GH dosyalarına atanmamış yazım; mevcut repairs/catalog/coverage yenilemesi.
