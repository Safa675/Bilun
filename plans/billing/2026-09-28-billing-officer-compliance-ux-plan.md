# Fatura uyumluluğu ekranı — faturalama görevlisi için UX planı

> Durum: Uygulama başlamadı; ürün planı incelemeye hazır.
> Başlangıç: `origin/main` / `b5098a33`, dal `feat/billing-officer-compliance-ux`.

## Amaç

Hasta Fatura Uyumluluğu görünümünde bir faturalama görevlisinin ilk bakışta
**mevcut eyleme dönük uyumluluk bulgusunu** (kendi kesinlik etiketiyle),
**Wave A insan incelemesi gözlemini** ve **yalnızca bilgi/koşullu izin kaydını**
ayırabilmesini; her kayıt için ilgili fatura,
belirsizlik ve sonraki adımı görebilmesini sağlamak. Wave A kural kararları,
API/cache sözleşmeleri, canonical kimlikler ve finansal hesaplar değişmeyecek.

## Mevcut durum ve tasarım nedeni

- Hasta sayfası birleşik uyumluluk bulgularından sonra ayrı bir yapısal kontrol
  cümlesi, Wave A kapsamı, inceleme gözlemleri ve bilgi/izin tablosu gösteriyor
  (`frontend/src/components/patient/views/ComplianceViewSection.tsx`).
- “15 değerlendirme / 2 bulgu” `claim_compliance` verisinden geliyor; “25 grup /
  656 / 426 / 599” Wave A kural değerlendirmelerinin grup toplamı. Bunlar aynı
  payda ve aynı bulgu sayısı değil (`frontend/src/lib/complianceCoverage.ts`,
  `frontend/src/components/patient/WaveAEvidenceSection.tsx`).
- Wave A tablosu ham kural ve neden kodlarını ana metin olarak gösteriyor;
  mevcut hastanın kimliğini her satırda tekrarlıyor ve kaynaksız satırda
  “Kaynak doğrulanmadı” metnini iki kez basabiliyor
  (`frontend/src/components/patient/WaveAEvidenceSection.tsx`).
- Hasta kanıtları sınırlı önizleme ve “daha fazla göster” ile; kohort kanıtları
  20 satırlık sayfalarla geliyor. Yalnızca yüklenen satırlardan yapılan bir
  gruplama bütün veri için kesin sayı veremez
  (`frontend/src/components/patient/WaveAEvidenceSection.tsx`,
  `frontend/src/components/patient/CohortWaveAEvidenceSection.tsx`).

## Ürün düzeni

1. **Önce eyleme dönük bulgular.** Var olan birleşik bulgu tablosu, kesin
   ihlal/risk etiketleri ve KPI'lar üstte kalır. Yapısal özet “15 kural
   değerlendirmesi · 2 yapısal bulgu” gibi,
   yalnızca bu alt kümenin sayısını anlattığını belirten Türkçe/İngilizce
   metinle açıklanır. “Ek bulgu” sözcüğü toplam KPI'ya ilave anlamı
   vermemeli. Değerlendirme sayısı olumlu uyumluluk sonucu gibi sunulmaz.
2. **Ayrı inceleme listesi.** Wave A `reviews` kayıtları “İnsan incelemesi
   gerekli — henüz ihlal olarak sayılmadı” başlığı altında gösterilir. İlk
   seviyede kuralın anlaşılır konusu, insanın doğrulaması gereken şey,
   belirsizlik/kaynak durumu ve **yalnızca yüklenmiş kayıtlar** içindeki fatura
   sayısı bulunur. Bölümün toplam kayıt sayısı yalnızca API'nin `total_rows`
   alanından alınır; görünen konu/fatura sayısıyla karıştırılmaz. Teknik kural
   kimliği, ham gerekçe kodu ve locator ayrıntıda kalır. Desteklenmeyen
   kesinlik veya faturalama talimatı üretilmez.
3. **Güvenli gruplama.** Hasta inceleme kayıtları yalnızca aynı kural,
   gerekçe, kaynak durumu, kaynak referansı, kaynak motoru, satır türü ve kayıt
   türü eşleştiğinde tek
   açılabilir konu altında toplanır. Her fatura/satır ve `evidence_id` ayrı
   çocuk kayıt olarak korunur. Başlıkta “gösterilen kayıtlarda” kapsamı yazılır;
   ek sayfa geldikçe grup genişler. Gizli sayfalardaki kayıtlar toplam sayıya
   katılmaz. Seçili `?finding=` kaydı önizleme dışında ise mevcut tekil
   getirme yolu korunur, ilgili grup açılır ve o kayıt görünür hale gelir.
4. **Bilgi ve koşullu izin ayrı.** `advisories` ayrı ve varsayılan olarak
   kapalı, fakat sayısı/varlığı görünür bir bölümde kalır. “İzin” yalnızca
   koşullar teyit edilirse uygulanabilir diye açıklanır; bu kayıtlar ihlal,
   tahsilat veya risk toplamına girmez. Seçili derin bağlantı bu bölümü açar.
5. **Kapsam ayrıntısı aşağıda.** Wave A özeti önce “Değerlendirme kısmi” veya
   “Kapsam bilgisi” gibi dürüst, kısa bir durum verir. 25 grup ve üç durumun
   kesin sayıları açılabilir “Kapsam ve veri eksikleri” ayrıntısında kalır.
   `missing_inputs` ve `unavailable` hiçbir zaman “uygun/sorunsuz” diye
   çevrilmez; neden mevcut veriden çıkarılamıyorsa uydurulmaz.
6. **Kaynak ve metin temizliği.** Kaynak locator'ı ile mevzuatın bu faturaya
   uygulanmasının doğrulanmış olmasını ayrı anlatan Türkçe/İngilizce metin
   kullanılır. Kaynak yoksa durum bir kez gösterilir. Bilinen ham gerekçe
   kodları insan tarafından anlaşılır, temkinli açıklamalara çevrilir;
   bilinmeyen kodlar dürüst bir açıklama ve teknik ayrıntı ile gösterilir.
   API insan dostu kural başlığı veya sonraki adım alanı sağlamadığı için
   görünen kural/gerekçe aileleri için gözden geçirilmiş iki dilli bir sunum
   kataloğu hazırlanır; kod adından hukuki sonuç türetilmez.
7. **Kohort sınırı.** Paylaşılan satır metinleri ve yinelenen kaynak düzeltmesi
   kohortta da geçerli olur. Kohortta sayfalar arası gruplama bu PR'a girmez;
   bunun için sunucu destekli toplu sayımlar gerekir. Kohort filtreleri,
   sayfalama ve hasta bağlantıları korunur.

Örnek hasta görünümü (sayılar yalnızca ekrandaki örnek kapsamındadır):

```text
Fatura uyumluluğu
Eyleme dönük bulgular                         [mevcut tablo ve kesinlik etiketleri]
Yapısal kontroller: 15 değerlendirme · 2 bulgu [bu alt kümenin özeti]

İnsan incelemesi gerekli · henüz ihlal değil  [20 kayıt]
  ▸ Ek ücret kapsamı · gösterilen 3 fatura
    Bu hizmetlerde mevzuatın uygulanmasını teyit edin.
    Kaynak konumu var; faturaya uygulanabilirliği doğrulanmadı.
    [Aç: her fatura ve satırın ayrı kanıtı]

Bilgi ve koşullu izinler                     [ayrı, açılabilir]
Kapsam ve veri eksikleri                      [25 grubun durum ayrıntısı]
```

## Uygulama sırası

- [ ] Hasta 0043 ve ayrı bir boş/kısmi hasta örneğiyle mevcut sayılar, kayıt
      kimlikleri, bağlantılar ve finansal/KPI değerleri için başlangıç verisini
      sabitle; görünen ham gerekçe/kural ailelerini envanterle.
- [ ] Wave A satırları için yalnızca frontend sunum modeli kur: güvenli grup
      anahtarı, yüklenmiş kayıt kapsamı, açıklama ve belirsizlik metni. Kanıt
      kayıtlarını silme veya canonical kimliklerine dokunma.
- [ ] Hasta inceleme görünümünü açılabilir konu + tekil fatura/satır listesi
      olarak kur; seçili kayıt otomatik açılsın ve mevcut derin bağlantı çalışsın.
- [ ] Bilgi/izin ve kapsam bölümlerini anlaşılır, erişilebilir açıklamalarla
      yeniden düzenle; yapısal özetin ayrı sayım olduğunu açıklaştır.
- [ ] Türkçe ve İngilizce metinleri birlikte güncelle; ham kodları birincil
      metinden çıkar, doğrulanmamış kaynağı tek kez göster; kohort ortak
      bileşenindeki görünümü kontrol et.
- [ ] Dar ekran, geniş ekran, klavye ve ekran okuyucu etiketlerini gözden
      geçir; boş, kısmi, kaynaksız, bilinmeyen gerekçe ve yükleme hatası
      durumlarını doğrula.
- [ ] Anlamlı birim/bileşen testleri ve en az bir tarayıcı etkileşim kontrolü
      ekle; ardından TypeScript, tüm Vitest testleri ve üretim build'ini çalıştır.
- [ ] Son diff, ekran görüntüleri ve önce/sonra örneğiyle yalnızca bu UX
      değişikliğini içeren incelemeye hazır PR aç.

## Kabul ölçütleri

- Görünür ilk bakışta eyleme dönük bulgular ile inceleme/bilgi kayıtları ayrı; hiçbir
  review/advisory satırı kesin ihlal veya finansal kazanç gibi görünmüyor.
- Birden çok faturadaki aynı inceleme konusu okunabilir tek başlıkta; her
  kanıtın tekil fatura/satır bağlantısı, `evidence_id` ve derin bağlantısı
  kaybolmuyor. Farklı gerekçe/kaynak kayıtları birleşmiyor.
- Görünen grup sayısı yalnızca yüklenen satırları kapsıyor; yeni sayfa gelince
  doğru güncelleniyor. Kohort sayfa toplamı bütün kohort gibi sunulmuyor.
- Yapısal kontroller ile Wave A kapsamı farklı sayımlar olarak açıklanıyor;
  eksik/değerlendirilemeyen durumları temiz sonuca dönüştürülmüyor.
- Ana görünümde ham enum kodları yok; kaynak doğrulanmadı metni tekrarlanmıyor;
  bilinmeyen durumlarda kesin hüküm kurulmadan teknik bilgiye erişilebiliyor.
- Hasta/kohort bulgu ve para toplamları, API payload'ları, kural sonuçları ve
  mevcut finansal ayrım değişmiyor. Masaüstü/mobil ve klavye kullanımı çalışıyor.

## Doğrulama

Odaklı testler aynı kuralın üç faturada görünmesini, farklı gerekçelerin ayrı
kalmasını, seçili tekil kaydın açılmasını, `load more` davranışını, advisory
ayrımını ve kısmi kapsamın dürüst metnini sınayacak. Tarayıcı kontrolü
sentetik hasta `SENTETIK-HASTA-0043` üzerinde masaüstü ve dar ekran
görünümünü, klavye aç/kapat davranışını ve deep link hedefini doğrulayacak.
Son kapı: `npx tsc --noEmit`, `npx vitest run`, `npm run build`.

## Kapsam dışı

Kural motoru, kaynak otoritesinin yeniden sınıflandırılması, backend/API veya
cache şeması, yeni ingestion, tahsilat/risk hesapları, kohortta sunucu tarafı
gruplama, canlı deploy ve bu UX PR'ında mevzuatın hukuki teyidi.

## Plan incelemesi

Hasta/kohort bileşenleri, veri tipleri ve mevcut testler iki bağımsız
salt-okunur incelemede karşılaştırıldı. İnceleme özellikle `15/2` ve Wave A
sayımlarının farklı kaynaklardan geldiğini, hasta önizlemesi/kohort
sayfalamasının genel gruplama sayısına izin vermediğini, API'de insan dostu
başlık/sonraki adım bulunmadığını ve `evidence_id` derin bağlantılarının
korunması gerektiğini doğruladı. Ürün planı incelemeye hazır; kod uygulanmadı.
