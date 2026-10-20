# Plan: SUT açık maddelerinin salt-okunur sınıflandırma döngüsü (gece koşusu)

**Durum:** Taslak; akşam provası yapıldı (§10.1); **gece koşusu 1 başladı (2026-10-20 09:35), kalibrasyon KIRMIZI, kuyruk Safa'nın kararını bekliyor (§10.2)**
**Üst plan:** `plans/billing/algorithmic-gap-closure-plan.md` (kuzey yıldızı metriği: `has_algorithmic_gap`)
**Bu plan kural YAZMAZ ve repoda hiçbir dosyayı değiştirmez.** Yalnız okur, sınıflandırır, sabah için bir paket üretir.

---

## 0. Özet (düz dille)

- **Soru:** Kalan 394 "açık" maddenin gerçekte ne olduğunu bilmiyoruz: claim alanlarıyla kural yazılabilir mi, claim'de olmayan bir alan mı istiyor, yoksa zaten kod motorunda mı, ya da kural olmayan bir metin mi? Bu bilinmeden "encode'u bitir" demek, kapsamı bilmeden gece boyu kural yazdırmak olur.
- **Ne yapılır:** Bir döngü 394 maddeyi parti parti okur. Her madde için iki bağımsız ajan sınıf, gerekçe (maddeden birebir alıntıyla) ve kanıt üretir. Makine kapıları uydurma alıntıyı ve olmayan kanıtı reddeder. Hiçbir izlenen dosya değişmez.
- **Sabah:** ~15 dakikada okunacak bir paket: ilk satırda koşunun sağlığı (YEŞİL / SARI / KIRMIZI), sayılar, senin karar vereceğin satırlar ve spot kontrol örnekleri.
- **Sonraki adım ayrı bir plan:** paketi gördükten sonra kural yazan pilot döngü (tek kova, küçük partiler, yazan ajan ≠ doğrulayan ajan). Bu plan onu kapsamaz.

| Kuyruk (bugün ölçüldü: `data/gazette/sut_clause_coverage.parquet`) | Sayı |
|---|---|
| Toplam madde | 4.781 |
| Kural olarak encode edilmiş (`has_rule_encoding`) | 1.903 |
| **Açık (`has_algorithmic_gap`) = bu planın kuyruğu** | **394** (5 Temmuz: 1.896 · Eylül ilk haftası, bellek kaydı: 484) |
| · kuzey yıldızı: açık **ve** encode edilmemiş | 344 (338 `implemented`, 6 `partial`) |
| · açık ama encode edilmiş (`partial`) | 50 |
| · modalitesiz (`deontic_modality` boş) | 195 (168'inde prosedür kodu ve ek atfı da yok: tanım gibi metin) |
| · para etkileyen modalite (NO_PAY 41, MUST_BILL 19, MANDATORY 18, PROHIBITED 9, NO_COPAY 7, MUST_NOT_BILL 7) | 101 |
| · COVERAGE / REGULATORY_ACTION / PERMISSION / diğer | 74 / 15 / 7 / 2 |
| EMR yüzünden bilerek açık sayılmayan (`emr_blocked`) | 143 (kuyruğun dışında) |
| Kuyruktaki `primary_rule_id` ailesi / partiler (≤12 madde; 6'dan küçük aile kalıntıları birleşir) | 26 aile / 37 parti (yalnız para etkileyen 101 madde: 10 parti) |
| Kuyruğun toplam metni | 141.707 karakter (~40 bin token; ortalama 360, en uzun 3.823) |

Not: açık maddelerin hepsi yürürlükte; başlık ve değişiklik maddesi yok. Metnin kendisi ucuzdur; maliyet, ajanın kanıt aramasından (kod, ek listeleri) gelir ve akşam provasında ölçülür.

---

## 1. "Bitti"nin tanımı (başarı koşulu) — hepsi makineyle kontrol edilir

Koşu üç düzeyden biriyle biter; düzey `manifest.json`'a ve `00-ozet.md`'nin ilk satırına yazılır.

| Koşul | Ölçüt |
|---|---|
| **S1 Tamlık** | 394 maddenin her biri için tam bir son kayıt; her kayıtta iki geçerli oy (A, B). |
| **S2 Kalibrasyon** | **Güçlü** altın etiketlerde (E2 ve N, 30 madde, bkz. §4) her iki oyun **üst-sınıf** doğruluğu ≥ %80. E1 etiketleri (projenin zaten encode ettiği maddeler) kapı değil, mevcut encode'ların denetimi olarak raporlanır. |
| **S3 Uyuşma** | Tüm kuyrukta iki oyun üst-sınıf uyuşması ≥ %70 (tam sınıf uyuşması ayrıca raporlanır). |
| **S4 Yan etkisizlik** | Okuma klonunun dosya ağacı imzası ve `data/gazette/sut_clause_coverage.parquet` sha256'sı koşu başı = koşu sonu (klonda `.git` yok: `git archive` çıktısı); `votes/` içinde yalnız beklenen oy dosyaları; araç-çağrı denetimi temiz (klon / girdi / kendi oy dosyası dışına yazma ya da okuma yok). Ana checkout'un `HEAD` ve `git status`'u **karşılaştırılmaz**: başka oturumlar orada meşru iş yapar; erişimi fiziksel önlem (klon) ve denetim engeller. |
| **S5 Kanıt kalitesi** | Her kayıt G1–G4'ten geçti (şema, birebir alıntı, doğrulanmış `dosya:satır`, yasak yol yok). |
| **S6 Paket tutarlılığı** | `01-siniflandirma.csv` satır sayısı = tamamlanan madde sayısı; sınıf toplamları `00-ozet.md` ile çapraz eşit. |

- **YEŞİL:** S1–S6 hepsi tuttu.
- **SARI:** S2–S6 tuttu, S1 eksik (en çok 4 parti `failed` ya da kota nedeniyle durdu). Paket üretilir, kalan partiler ve devam komutu başa yazılır.
- **KIRMIZI:** S2 ya da S3 ya da S4 tutmadı. Paket "sınıflandırma güvenilir değil" der ve nedeni gösterir (örn. rubrik şu sınıflarda ayrışıyor); kural yazan döngüye geçilmez.

Başarısızlık da sonuçtur: KIRMIZI bir paket, rubriği düzeltmek için en ucuz kanıttır.

**Döngünün iddia etmediği şey:** encode edilmiş kuralların doğru olduğunu. Bu plan yalnız açık maddelerin ne olduğunu söyler.

---

## 2. Kuyruk

- **Kaynak:** `data/gazette/sut_clause_coverage.parquet`, `has_algorithmic_gap == True` (tanım: `scripts/sut/prose/coverage.py:476-511`; EMR-blocked ve Tier-C çıkarımı yalnız ilaç kovası için: satır 104-106, 387-388, 497-498).
- **Parti:** aynı `primary_rule_id` içinde, `section_id` sırasıyla ≤12 madde. Bir ailenin 6'dan az maddelik kalıntısı diğer ailelerin kalıntılarıyla `mixed` partide birleşir (ajanın rubriği ve kodu okuma maliyeti 1–3 maddeye yayılmasın) → 37 parti. `parti_id = sha256(sıralı clause_id listesi)[:10]`.
- **Sıra:** önce para etkileyen modalite içeren partiler (101 madde), sonra COVERAGE / REGULATORY_ACTION / PERMISSION, en sonda modalitesizler. Gece yarıda kesilirse en değerli kısım bitmiştir.
- **Ajana verilen alanlar:** `clause_id`, `section_id`, `section_path`, `clause_type`, `text_tr` (tam), `deontic_modality`, `annex_refs`, `procedure_codes`, `primary_rule_id`, `matched_rule_ids`, `domain_modules` (kapsam modelinin maddeyi hangi kod / veri dosyalarında karşılandığını düşündüğü; etiket sızdırmaz).
- **Verilmeyen alanlar (etiket sızıntısı olmasın):** `coverage_status`, `has_rule_encoding`, `emr_blocked`, `coverage_notes`.
- **Durum dosyası** `state.json`: parti → `pending | running | done | failed(n)`, girdi hash'iyle. Yeniden başlatma biten partiyi atlar; girdi hash'i değişen partiyi yeniden işler (kademeli, kaldığı yerden devam eden döngü).

---

## 3. Sınıflar (rubrik) — her madde tam bir sınıf alır

Karar sırası (ajan bu soruları sırayla yanıtlar):

1. Madde denetlenebilir bir koşul ya da sonuç içeriyor mu? Hayır → **N1**.
2. Madde bir tutar, oran, eşik ya da katsayı mı (kural değil veri)? Evet → **T1**; motorda var mı bakılır.
3. Madde zaten bir Python motorunda uygulanıyor mu (kanıt: `dosya:satır`)? Evet → **K1**.
4. Koşul yalnız claim alanları ve katalog verisiyle değerlendirilebilir mi (alan envanterine göre)? Evet → **E1**; hayır → **E2** ve eksik alanın adı.
5. Karar verilemedi → **H**.

| Kod | Sınıf | Sonraki adım |
|---|---|---|
| **E1** | `encode_edilebilir` — mevcut claim alanlarından ve kataloglardan değerlendirilebilir | Kural yazma adayı (pilot kovası) |
| **E2** | `claim_dışı_girdi` — claim'de olmayan alan ister (lab değeri, yaş / doğum tarihi, ECOG, rapor içeriği, saat…) | Eksik alan adlandırılır; hangi alan kaç maddeyi açar tablosu |
| **K1** | `kod_motoru_karşılıyor` — madde zaten motorda, madde-seviyesi iz yok | İz bağla ya da dürüstçe `non_algorithmic` işaretle |
| **T1** | `sabit_veya_tablo` — tutar / oran / eşik; veri tablosuna ait | Veri tablosuna bağlanma kontrolü |
| **N1** | `kural_değil` — tanım, yönlendirme, usul, açıklama | `non_algorithmic` gerekçesi |
| **H** | `insan_kararı` — ajan karar veremedi ya da oylar ayrıştı | Sabah paketi `02` |

**Üst-sınıflar** (S2 ve S3 bunlarla ölçülür): {E1} · {E2} · {K1, T1, N1} · {H}.

**Her kayıtta:** `clause_id`, `class`, `confidence` (yüksek / orta / düşük), `rationale` (≤2 cümle, **maddeden en az bir tırnaklı birebir alıntı zorunlu**), `evidence[]` (K1/T1/E1 için `dosya:satır` ya da annex / kod; boş olamaz), `carrier` (maddeyi taşıyan ya da taşıyacak mevcut aile / motor), `required_inputs[]` (E2 için ≥1), `money_moving` (bool: modalite NO_PAY, MUST_BILL, MANDATORY, PROHIBITED, MUST_NOT_BILL, NO_COPAY), `proposed_action`, `risk_note`.

**Alan envanteri (E1 / E2 ayrımının dayanağı):** `src/bilun/domain/claims/models.py` dataclass'larından mekanik üretilir (`ClaimHeader`, `ClaimDiagnosis`, `ProcedureClaimLine`, `PerformedProcedureLine`, `MaterialClaimLine`, `DrugClaimLine`, `PatientCopayProfile`, `ClaimTotals`, `MedulaRejectionEvent`) + `PatientClaimContext` geçmişi + kataloglar (`data/gazette/curated`, EK-2/B, EK-2/C, EK-3 listeleri). Envanterde olmayan alan ⇒ E2.

**Rubrik dosyası** (kararlar + 7 çözülmüş örnek; her örnek kendi kapılarından geçer) koşu başında dondurulur ve sha256'sı `manifest.json`'a yazılır.

---

## 4. Döngü (parti başına) ve altın küme

**Bir kez, ilk partiden önce — kalibrasyon (G6):** sabit tohumla (`20261019`) 45 madde: 15 `emr_blocked` ve metinde ölçüm / skor / laboratuvar sözcüğü geçen → beklenen **E2** (güçlü etiket); 15 `non_algorithmic` (başlık / değişiklik hariç) → beklenen **{K1, T1, N1}** (güçlü etiket); 15 encode edilmiş ve para etkileyen modaliteli → **zayıf etiket**. Sınıflandırıcıya kuyrukla aynı alanlar verilir, etiketler verilmez. **Kapı yalnız 30 güçlü etiketle ölçülür**: üst-sınıf doğruluğu ≥ %80 değilse koşu durur (KIRMIZI).
*Neden E1 etiketi kapı değil (provada görüldü):* "encode edilmiş" ile "claim verisinden değerlendirilebilir" aynı şey değil. Encode edilmiş bir madde kod motorunda uygulanıyor olabilir (doğru sınıf K1, E1 değil) ya da projenin bir bayrakla encode ettiği ama claim'in gerçekte taşımadığı bir girdiye dayanıyor olabilir (iki oy da E2 der). İkisi de sınıflandırıcının hatası değil; ikincisi encode'ların kendisi için bilgi taşır, o yüzden pakette ayrı bir denetim tablosu olarak raporlanır.
*Sınırı:* altın etiketler projenin önceki kararlarıdır, mutlak gerçek değil; kalibrasyon "rubriği bizim eski yargılarımızla tutarlı anlıyor mu"yu ölçer.

**Parti başına:**
1. Parti kuyruktan alınır (`running`).
2. **İki bağımsız oy (A, B):** aynı rubrik ve aynı girdi, madde sırası farklı (B'de ters), birbirinin çıktısını görmez. B için farklı bir model ya da farklı bir ifade biçimi kullanılır (aynı modelin aynı yanılgıyı iki kez yapmasına karşı).
3. Her oya mekanik kapılar G1–G5 uygulanır. Geçmeyen oy **bir kez** hata mesajıyla yeniden istenir; ikinci kez geçmezse parti `failed`.
4. **Mekanik uzlaştırma** (ajan değil, betik): üst-sınıflar eşitse kayıt "uyuşmalı", güven = iki güvenin küçüğü; değilse **H**'ye düşer ve iki gerekçe de saklanır.
5. Çıktı `out/<parti_id>.jsonl`; durum `done`; `progress.log`'a tek satır (zaman, parti, durum, süre, deneme sayısı).
6. G7 (uyuşma alarmı) ve G5 (yan etki) her partiden sonra kontrol edilir.

---

## 5. Kapılar

| Kapı | Kontrol | Başarısızlıkta |
|---|---|---|
| **G0 Başlangıç** | Taban = `origin/main` commit'i kaydedilir; parquet sha256 kaydedilir; boş bellek ≥ 6 GB (eşikler varsayılan, §8'deki provada ayarlanır); başka ağır iş yok (`docker ps`, `pgrep pytest\|vitest`); rubrik ve alan envanteri sha256 kaydedilir | Başlama |
| **G1 Şema** | Zorunlu alanlar var; sınıf ve güven listede; K1/T1/E1 için `evidence` boş değil; E2 için `required_inputs` ≥1; CLI'nin `--json-schema` çıktısıyla aynı şema | Oy reddedilir |
| **G2 Alıntı** | `rationale` içindeki her tırnaklı alıntı clause metninde **birebir** geçer (Türkçe büyük / küçük harf katlamasıyla: İ→i, I→ı; boşluk normalize) | Oy reddedilir |
| **G3 Kanıt** | `dosya:satır` kanıtında dosya var ve satır, anılan tanımlayıcıyı (fonksiyon / sabit adı) içeriyor; annex / kod kanıtı katalogda var | Oy reddedilir |
| **G4 Yasak yol** | Çıktıda `ilay_validation`, `golden/ilay`, `raw data` geçmez. Ayrıca fiziksel önlem: işçiler bu klasörlerin **bulunmadığı** bir okuma klonunda çalışır | Oy reddedilir; ihlal şüphesinde dur |
| **G5 Yan etki** | Okuma klonunun ağaç imzası ve parquet sha256'sı değişmedi; `votes/` içinde beklenmeyen dosya yok; araç-çağrı denetimi (yazma, klon dışı okuma, diğer oyun) temiz | **Anında dur (KIRMIZI)** |
| **G6 Kalibrasyon** | §4: güçlü altın etiketler (E2, N; 30 madde) ≥ %80 | Dur (KIRMIZI) |
| **G7 Uyuşma alarmı** | (a) İlk 5 partide iki oyun üst-sınıf uyuşması < %60 → **dur** (rubrik sorunu). (b) ≥6 maddelik bir partide tek üst-sınıf > %70 → **uyarı, durdurmaz**: homojen bir aile (on iki NO_PAY istisnası) dürüstçe tek sınıfa düşebilir; orkestratör partiden iki satır okur, kararı `progress.log`'a yazar, rubrik yanlış görünüyorsa durur | (a) Dur; (b) uyarı |

**Kapıların kendisi sınanır:** doğrulayıcı betikler mutant kayıtlarla test edilir; uydurma alıntı, olmayan dosya, doğru dosya ama yanlış satır, boş kanıt, geçersiz sınıf, yasak yol içeren kayıt, tek oy eksik kayıt — hepsi reddedilmelidir (kapı yalnızca mutant testleri kadar dürüsttür).

**Okuma klonu:** `git archive <origin/main commit>` ile `~/.cache/bilun-gap-classification/<run-id>/repo/` (disk; `/tmp` tmpfs'tir, yeniden başlatmada silinir) içine açılır, yasak klasörler silinir, `chmod -R a-w` yapılır, işçiler `PYTHONDONTWRITEBYTECODE=1` ile çalışır. Çıktılar yalnız sürücünün verdiği `out/` klasörüne yazılır.

---

## 6. Durma koşulları

| Koşul | Eylem |
|---|---|
| Tüm partiler `done` (tüm kuyruk 37, `--scope money` 10) ve S1–S6 tuttu | Paketi yaz, YEŞİL, dur |
| G6 başarısız / G7a (uyuşma < %60) tetiklendi / G5 ihlali | Hemen dur, KIRMIZI paket (nedenle) |
| ≥3 parti `failed` | Dur, SARI paket (kalan partiler ve devam komutu başta) |
| İlk kota ya da API-limit hatası | Yeniden **deneme yok**; durum dosyası kayıtlı; paket o ana kadarkiyle yazılır, devam komutu başta (dün ajanlar limit sonrası kendiliğinden dönmedi) |
| Süre kutusu: 6 saat | Dur, SARI paket |
| Bellek < 3 GB iki ölçümde (10 dk arayla) ya da yük > 12, 20 dakika sürekli | Dur (dün üç ağır iş uygulamayı OOM'a soktu) |

Parti başına en fazla 2 deneme. Sınırsız bekleme ve yeniden deneme fırtınası yok.

---

## 7. Sabah paketi

Konum: `~/.cache/bilun-gap-classification/<run-id>/packet/`; bir kopya bu oturumun notlar klasörüne. Repoya **hiçbir şey commit edilmez**; ne yapılacağına paketi gördükten sonra sen karar verirsin.

| Dosya | İçerik |
|---|---|
| `00-ozet.md` | Türkçe, düz dille. İlk satır: YEŞİL / SARI / KIRMIZI + neden. Sınıf dağılımı tablosu, uyuşma ve kalibrasyon sayıları, başarısız / karantina partileri, süre ve (varsa) kullanım, "repoda hiçbir şey değişmedi" kanıtı (sha256'lar), senin vereceğin ≤5 karar |
| `01-siniflandirma.csv` | Her madde bir satır: madde, bölüm, modalite, sınıf, güven, iki oyun sınıfı ve gerekçesi, `risk_note`, kanıt, eksik girdi, `carrier`, `money_moving`, önerilen adım |
| `02-insan-karari.md` | H satırları: iki oy yan yana, alıntılarla |
| `03-ornekler.md` | Her sınıftan 3 satır, tam metin + gerekçe + kanıt (spot kontrol: ~20 satır, 20 dakikadan az) |
| `05-risk-notlari.md` | İşçilerin risk notları; kod / kural dosyasına atıf yapanlar önce. Mevcut bir encode'un maddeyle çeliştiği ipuçları burada çıkar (provada ilk ipuçları buradan geldi, §10.1). **Doğrulanmamış iddialardır, hüküm değil** |
| `04-sonraki-adim.md` | Pilot encode kovası önerisi (E1 satırları aile aile); K1 / T1 / N1 için dürüst yeniden sınıflama **yama taslağı** (uygulanmaz); E2 için "hangi eksik alan kaç maddeyi açar" tablosu |
| `manifest.json` | taban commit, parquet / kuyruk / rubrik / envanter sha256'ları, model ve CLI sürümü, kapı sonuçları, parti durumları |

**Senin işin (≈15–20 dk):** `00` oku (5 dk) → `03`'ten en az 10 satır kontrol et (10 dk) → `02`'yi karara bağla ya da "bırak" → `05`'in "kod / kural dosyasına atıf yapanlar" bölümüne göz at (birkaç dk; ipuçlarını ayrı işe çevirmek sonra). Sonuç sana yetmiyorsa koşu aynı kuyruğa ikinci tur olarak uzatılır.

**Bilinen açık, sınıflandırma sonrası karar isteyecek:** `emr_blocked` / Tier-C çıkarım mekanizması yalnız ilaç kovasında var (`scripts/sut/prose/coverage.py:104-106, 497-498`). E2 çıkan ilaç dışı maddeler gap sayısını bu yolla düşüremez; ya mekanizma genişletilir ya da yeniden sınıflanır. `04`'te bu madde sayısıyla birlikte sorulur.

---

## 8. Kaynak ve makine kuralları

- Aynı anda en fazla **2** ajan süreci (oy A ve oy B) ve **0** ağır iş: pytest, vitest, docker, CI kapısı yok. Hafif Python (polars okuma) serbest. Başka bir oturum ağır iş koşarken başlama (G0).
- Her partiden sonra durum dosyası yazılır (checkpoint). Kota penceresi dolarsa devam komutu paketin başındadır.
- Maliyet ölçüldü (§10.1): para etkileyen madde başına oy başına ~104 sn ve ~38 bin token, tanım / liste maddesi ~33 sn ve ~14 bin token. Tüm kuyruk × 2 oy süre kutusunu (6 saat) aşar; ilk gece kapsamı bu yüzden daraltıldı (D7).
- **Çalıştırma yöntemi (D2 — provada çözüldü):** başsız CLI yolu **kapalı**: pakette gelen CLI (`~/.config/Claude/claude-code/2.1.299/*/claude`) bu makinede giriş yapmamış (`claude auth status`: `loggedIn: false`; her `-p` çağrısı "Not logged in" döner). Bunu ancak Safa tek seferlik `claude setup-token` / `/login` ile çözebilir; ben kimlik bilgisiyle uğraşmam. Bu yüzden oyları **oturum içi alt ajanlar** üretir (Agent aracı, `general-purpose`; oy A `sonnet`, oy B `opus`); kuyruk, kapılar, uzlaştırma ve paket Python araçlarıdır (`~/.cache/bilun-gap-classification/driver/`, 81 birim / mutant testi, `RUNBOOK.md`). Orkestratör bir Claude Code oturumudur: parti başına `prompt` → iki ajan (arka planda, aynı anda en çok iki) → `finish` (G1–G4 + araç-çağrı denetimi + uzlaştırma + durma koşulları). Orkestratör oturum kotaya ya da OOM'a takılırsa döngü durur; durum dosyasından kaldığı yerden sürer. Gece boyu çalışması için uygulamanın açık, makinenin uyanık kalması gerekir (`request_keep_awake`).

---

## 9. Riskler

| Risk | Önlem |
|---|---|
| Ajan gerekçeyi uydurur | G2 (birebir alıntı) + G3 (doğrulanmış kanıt), ikinci bağımsız oy |
| Rubrik partiler arasında kayar | Dondurulmuş rubrik + sha256; her partide aynı 8 örnek; G7 alarmı |
| Sınıflandırıcı tembelleşir (hepsini N1 der) | Kalibrasyon (G6, koşunun ilk adımı) + parti sınıf dağılımı uyarısı (G7b; durdurmaz, orkestratör örnek okur) |
| İki oy aynı yanlışı yapar | B için farklı model / ifade; sabah 10+ satır spot kontrol; altın küme |
| Yasak klasörler okunur | Fiziksel yokluk (okuma klonu) + G4 çıktı taraması |
| OOM / kota | Seri çalışma, ≤2 süreç, checkpoint, ilk limit hatasında dur |
| Sınıflandırma "kural doğru" izlenimi verir | Pakette ve bu planda açık: yalnız açık maddelerin ne olduğunu söyler |
| Veri mahremiyeti | Girdi kamu mevzuat metni + sentetik veri; hasta verisi yok |

---

## 10. Yapılacaklar ve akşam provası

Betikler ilk koşu yargılanana kadar repo dışında: `~/.cache/bilun-gap-classification/driver/` (paket `gapclass`, `RUNBOOK.md`, 81 birim / mutant testi).

- [x] Okuma klonu üretici (`git archive`, yasak klasörlerin yokluğu, salt-okunur) + yokluk testi
- [x] Kuyruk üretici (394 → 37 parti, sha256'lar, `--scope money` = yalnız para etkileyen 101 madde → 10 parti) + durum dosyası
- [x] Alan envanteri üretici (`models.py` → `claim_fields.md`)
- [x] Rubrik + 7 çözülmüş örnek (örnekler kendi kapılarından geçer; sha256 manifestte)
- [x] Altın küme üretici (45 madde, tohum 20261019; kapı yalnız 30 güçlü etiketle)
- [x] Doğrulayıcı G1–G4 + **mutant kayıtlarla birim testleri** (testler yazarken G4'te gerçek bir hatayı yakaladı: kapı alan *adlarını* tarıyordu, değerleri değil)
- [x] Araç-çağrı denetimi (işçinin gerçek çağrıları; bağımsızlık: diğer oyun dosyasını okumak ihlal)
- [x] Uzlaştırıcı + paket üretici + prova raporu
- [x] Orkestrasyon protokolü (`RUNBOOK.md`; `finish` komutu: ingest + denetim + uzlaştırma + durma koşulları)
- [x] **Akşam provası** (2026-10-20 00:00–01:00): sonuçlar §10.1
- [x] Prova sonrası iki değişiklik (aşağıda, §10.1 sonunda): küçük aile kalıntılarını birleştirme, G7b uyarısı
- [~] Gece koşusu 1 (Safa'nın onayıyla 2026-10-20 09:35): 3 kalibrasyon partisi bitti, **G6 tutmadı**, kuyruk başlamadı; karar bekliyor (§10.2)

### 10.1 Prova sonuçları (gerçek ajanlar, gerçek maddeler)

Koşular: `rehearsal-20261019` ve `rehearsal2-20261020`; taban `origin/main` `1a5352b9`. Üç parti türü, 2 oy (A `sonnet`, B `opus`) her biri: para etkileyen 8 maddelik parti (iki bağımsız koşu), 9 maddelik kalibrasyon alt kümesi, modalitesiz 12 maddelik tanım / liste partisi.

**Çalışıyor mu?** Evet, uçtan uca. Kuyruk → iki bağımsız oy → G1–G4 → araç-çağrı denetimi → uzlaştırma → rapor. Sekiz oy dosyasının sekizi de **ilk denemede** kapılardan geçti (0 sorun). Araç-çağrı denetiminde gerçek ihlal yok: işçiler yalnız `Read` / `Grep` / `Glob` ve salt-okunur `grep` / `ls` kullandı, dışa çıkmadı, yalnız kendi oy dosyalarını yazdı. Denetimde ilk sürümümün 4 yanlış alarmı vardı (hepsi benim denetleyicimin hatası, düzeltildi ve testle sabitlendi): işçinin kendi komut dosyasını okuması; `--exclude-dir="raw data"` gibi yasak klasörü *dışlama* argümanları; `2>/dev/null`; tırnak içindeki `>` ve `.git`. Denetim şimdi ayrıca diğer oyun dosyasını / koşunun durum dosyalarını okumayı ihlal sayar.

**Kalite.** Gerekçeler gerçek maddeden birebir alıntı taşıyor ve kanıt gerçek kod konumlarına işaret ediyor (örn. `models.py:170 treating_physician_different_from_board_signatory`, `gap_closing.py:16 overseas_treatment_days`, `ek4d_exempt.py:166 match_ek4d_copay_exempt_drug`). Aynı 8 maddelik parti iki bağımsız koşuda: son sınıf 6 / 8 aynı, her model kendi içinde 7 / 8 aynı; farklılaşan ikisi gerçekten sınırda maddeler. Uyuşma: para etkileyen parti %88 (1 madde insan kararına), tanım / liste partisi %100 (12 / 12), kalibrasyon alt kümesi %89 (1 madde insana). Sınırı: iki oyun **aynı yanlışta uyuşması** mümkün (örnek C000825: ilk koşuda B bir claim alanı buldu ve E1 dedi, ikincide ikisi E2 dedi); bu yüzden pakette uyuşan satırlardan da spot kontrol var.

**Kalibrasyon (9 madde alt kümesi, güçlü etiketler E2 + N = 6 madde):** oy A %83, oy B %100, uzlaşmış %83 (kaçırılan: C008330, "Engelli sağlık kurulu raporu bulunması halinde aslının veya onaylı fotokopisinin": A E2 dedi, B N1; gerçekten ikisi de savunulabilir, insan kararına düştü). **Zayıf etiketler (projenin zaten encode ettiği 3 madde):** 3'ünden yalnız 1'i iki oyla da "kuralı var" (K1) bulundu; ikisi için **iki oy da E2 dedi** (C000382 "Kurumca iade alınan tıbbi malzemelerden katılım payı alınmaz": claim'de iade bayrağı yok; C000760 diş implantı kurul koşulu: kurul bileşimi, radyografi eki, implant adedi claim alanı değil). Bu, ilk tasarımdaki "encode edilmiş = E1" varsayımının yanlış olduğunu gösterdi (§4'te düzeltildi) ve ayrıca mevcut encode'lar için bilgi taşıyor: bazıları claim'in gerçekte taşımadığı girdilere dayanıyor olabilir. 9 madde istatistik değil; tam 30 maddelik kalibrasyon gece koşusunun ilk adımı.

**Maliyet (ölçüldü).**

| Parti türü | Madde başına, oy başına süre | Madde başına, oy başına token |
|---|---:|---:|
| Para etkileyen (8 madde, 4 oy-koşusu) | 104 sn | 37,7 bin |
| Kalibrasyon (9 madde, karışık) | 97 sn | 29,7 bin |
| Modalitesiz tanım / liste (12 madde) | 33 sn | 14,4 bin |

Bir oy 8–9 maddelik partide 12–16 dk, 12 maddelik tanım partisinde ~6,5 dk sürdü; 250–355 bin token, 26–100 araç çağrısı. Kapsam modelinin `domain_modules` alanını işçiye vermek maliyeti **düşürmedi** (aynı parti: 323 bin → 355 bin token, 13,6 → 16,2 dk; opus 264 bin → 262 bin), alan yine de girdi olarak kaldı (zararsız, ilk bakılacak dosyaları gösteriyor).

Tahmin (kaba; parti içeriğine bağlı): tüm kuyruk × 2 oy **11–29 milyon token** (orta ~20 milyon) ve tek parti sırasıyla, iki oy paralel, **3,6–10,9 saat** duvar saati; altın küme buna ek. Yalnız 101 para etkileyen madde × 2 oy: ~7,6 milyon token, ~2,9 saat. Kalibrasyon (30 güçlü madde × 2 oy): ~1,8 milyon token, ~0,8 saat. **Bu, tasarlandığı biçimiyle tüm kuyruğun tek geceye sığmadığı, ama para etkileyen kısmın + kalibrasyonun (~9 milyon token, ~3,7 saat) sığabileceği anlamına geliyor.** Kota penceresine nasıl denk geleceği bilinmiyor: ilk limit hatasında durur, devam komutu yazılır.

**Kapılar ve durma koşulları üzerinde bulgu:** G0 gerçekten çalıştı (laptop CI çalıştırıcısının `bilun-ci-*` konteyneri PR #326'nın kontrollerini koşarken koşuyu başlatmadı; konteyner bitince başladı).

**Önerilen ilk gece (D7):** `prepare --scope money` (101 madde, 10 parti) + 30 güçlü altın maddelik kalibrasyon (3 parti); ardından paket. Paketi gördükten sonra: ya kalan 293 maddeyi tek oyla (A) koşmak, ya ikinci oyu yalnız A'nın düşük güvenli / E1 / K1 dediği satırlara uygulamak (maliyeti kabaca yarıya indirir), ya da tamamını ikinci gece. Karar paketten sonra.

**İlk denetim ipuçları (hüküm değil; işçilerin `risk_note` alanından, paketteki `05-risk-notlari.md`'nin ilk içeriği; ikisini de kodu / YAML'ı okuyarak yüzeyde kontrol ettim, sınır: hukuki yorumu SUT metniyle ben hükme bağlamadım).** (1) C000825 (SUT 2.4.1.B-3.(1): rapor imzacısı hekimin kendisinin / yakınının / ortaklarının tedavisi ödenmez): iki oy E2 dedi ve mevcut kuralın (`data/gazette/prose_rule_sources/dental_2_4_1/2.4.1.B-3.yaml`, `2.4.1.B-3.(1).treating_physician_continuity`) maddeyle uyuşmadığını yazdı. YAML'ı ben de okudum: koşul `treating_physician_different_from_board_signatory: true` + `patient_in_first_degree_relative_of_physician: true`, kuralın kendi ret metni ise "raporu düzenleyen hekim veya yakını tedavi yapıyorsa" diyor; yani koşuldaki "farklı hekim" bayrağı ret metniyle ve maddeyle ters, yakınlık bayrağı da tedavi edenin değil hastanın yakınlığı. (2) C000482 / C000492 (SUT 2.1.2 günübirlik tanımı): işçiler `infer_care_setting`'in günübirliği ayakta okuduğunu ve `claim_is_day_case`'in yalnız `claim_type` dizgesine baktığını, 24 saat ve işlem listesinin kodda denetlenmediğini yazdı. Kodu okudum: ilk iki gözlem doğru (`claim_utils.py:85-86`, `:73-74`), ama kodun kendi docstring'i bunu biliyor ve `detect_care_setting_ambiguity` günübirlik için çift yorum üretiyor; yani bilinen bir tasarım, hata kanıtı değil. Açık kalan yalnız "24 saat ve liste denetlenmiyor, etikete güveniliyor" (işçilerin `yatak_puani.py:450` atfı bu kodda `claim_is_day_case` kullanımına denk gelmiyor: kullanım satırları 195, 368, 416; `risk_note` içindeki satır atıfları G3'ten geçmez, yalnız `evidence` geçer). Düzeltmeler bu planın kapsamı dışında (`src/` ve manifest hash'leri); pilot encode planında (§13) ilk denetim girdisi olur.

**Prova sonrası yapılan iki değişiklik (araçlar testli; gerçek ajanlarla henüz koşulmadı, ilk kez gece koşusunda çalışacaklar); bir de paket eksiği kapandı.**
1. *Küçük aile kalıntıları birleşir.* Provadan önce para etkileyen kapsam 20 partiydi, bir kısmı 1–3 maddelikti; her parti iki ajanın rubriği ve kodu baştan okuma maliyetini öder. 6'dan az maddelik kalıntılar `mixed` partide toplanır: tüm kuyruk 48 → 37, para etkileyen kapsam 20 → 10 parti. Son parti hâlâ tek maddelik bir artık (kabul edildi; tahminen ~4 dk ek süre, ölçülmedi).
2. *G7'nin ikinci yarısı uyarı olarak eklendi.* Planın ilk sürümü "bir partide tek sınıf > %70" alarmını vaat ediyordu, araçta yoktu (yalnız uyuşma < %60 durduruyordu). Şimdi ≥6 maddelik bir partide tek üst-sınıf > %70 ise `finish` çıktısında ve `progress.log`'da `skew` görünür; **durdurmaz** (homojen bir ailede meşru olabilir), orkestratör iki satır okuyup kararı yazar.
3. *`risk_note` pakete eklendi.* İşçilerin yazdığı risk notu (en yakın başka sınıf, mevcut kodun maddeyle çelişmesi) pakette hiç görünmüyordu; ipuçlarını ham çıktıya bakarken buldum. Şimdi CSV'de sütun ve `05-risk-notlari.md` ayrı dosya (prova koşusunda 29 satırın 17'sinde not var, 6'sı kod / kural dosyasına atıf yapıyor).

### 10.2 Gece koşusu 1 (`night1-20261020`, 2026-10-20 09:35–10:37): kalibrasyon KIRMIZI, kuyruk başlamadı

Taban `origin/main` `1a5352b9`, kapsam `money` (101 madde, 10 parti), G0 geçti. Önce üç güçlü kalibrasyon partisi (30 madde, her biri iki oyla) koştu: 6 oy dosyasının 6'sı ilk denemede G1–G4'ten geçti; iki oy arasında üst-sınıf uyuşması 27 / 30 (%90, 3 madde insana düştü). Maliyet: **1,82 milyon token, 61 dk** (A `sonnet` 1,01 M token ve 56 dk, B `opus` 0,81 M token ve 40 dk oy süresi; madde başına oy başına A 33,5 bin token / 112 sn, B 27 bin token / 80 sn: §10.1 tahminiyle uyumlu).

| Kalibrasyon (G6, 30 güçlü etiket) | Oy A | Oy B | Uzlaşmış |
|---|---:|---:|---:|
| Orijinal etiketler | %70 | %63 | %63 |

Eşik %80: **tutmadı**; §6 gereği kuyruk başlatılmadı (0 / 10 parti), KIRMIZI paket üretildi (`06-kalibrasyon-hatalari.md` 11 maddeyi metin ve iki gerekçeyle gösterir). E2 etiketlilerde (15) iki oy da 13'ünde doğru; **N etiketlilerde (15) A 8, B 6 doğru**.

**Neden (11 ıskalanan maddeyi okudum):**
1. *N havuzum yapısal olarak hatalıydı (4 madde: C005249, C008330, C001529, C005380).* Proje `emr_blocked` mekanizmasını yalnız ilaçta kullanıyor; ilaç dışı, claim'de olmayan girdi isteyen maddeleri `non_algorithmic` diye işaretliyor (laboratuvar eşiği, belge ibrazı, sevk formu, klinik ilerleme). Benim rubriğimde bunlar **E2**; iki oy da E2 dedi ve alan envanterinde nötrofil / trombosit, engelli raporu, sevk belgesi alanı gerçekten yok. "non_algorithmic = N" eşleştirmesi benim varsayımımdı (§4'ün "kodlanmış = E1" hatasının eşi) ve yanlış.
2. *Eski E2 etiketi bayat ya da gürültülü (2 madde: C007401, C006886).* C007401'de (vosoritid sonlandırma) `annual_growth_velocity_cm` ve `epiphyses_closed` claim modelinde var (`models.py:290`, `:289`): iki oyun E1'i doğru. C006886 (diyaliz öncesi anemi) etiketi anahtar sözcükle ("evre") seçilmişti; ICD-10 yolu makul ama doğrulanmadı.
3. *Kural gibi görünen, `non_algorithmic` etiketli maddeler (3: C000990 APD hastasında ek hemodiyaliz kamu merkezinde, C001241 yoğun bakımda ayrıca faturalanan ATC'li ilaçlar, C003495 rapor en fazla iki yıl).* İki oy da E1 dedi. Doğruysa etiket yanlış ve bunlar encode adayı (asıl değerli bulgu türü); yanlışsa iki oy aynı yöne sapıyor. Ayırt edemiyorum.
4. *B, çıplak liste maddelerinde fazla iddialı (2: C000202, C000609).* A N1 dedi (doğru), B E2 / E1; iki oy tasarımı bunları insana düşürdü (beklenen davranış).

**Düzeltilmiş etiketlerle yeniden hesap (yalnız ben, oyları gördükten sonra; bu yüzden kapı olarak kullanmadım):**

| Düzeltme | n | Oy A | Oy B | Uzlaşmış |
|---|---:|---:|---:|---:|
| Muhafazakâr: yalnız doğrulananlar (C005249, C008330, C001529 → E2; C007401 → E1) | 29 | %83 | %76 | %76 |
| + C006886 → E1 | 28 | %86 | %79 | %79 |
| + C005380 → E2 | 28 | %86 | %82 | %79 |
| + üç "kural gibi" madde dışarıda | 25 | %96 | %92 | %88 |

Okuma: sınıflandırıcı etiketlerden iyi görünüyor ama aralık %76–96 ve belirleyen birkaç yargı çağrısı; bu etiket kümesi %80'lik bir kapıyı karara bağlayacak kadar temiz değil. Doğru kalibrasyon, Safa'nın gözü kapalı etiketlediği ~20 madde olurdu. Yan bulgu: ilaç dışı E2 maddeleri için proje bugün `non_algorithmic` kullanıyor; bu, §7'deki "bilinen açık"ın (ilaç dışı `emr_blocked` yok) ölçülmüş hâli.

**Araç bulguları.** (a) Oy A'nın denetimi 5 yanlış alarm verdi (denetimin beşinci yanlış alarm türü): işçi `... | grep -vi "golden/ilay"` ile yasak adları *süzdü*, klasörler zaten dışa aktarımda yok (yol varlığı kontrol edildi). Denetim, ters grep'in kalıp işlenenlerini dışlama sayacak şekilde düzeltildi (7 olumlu, 6 olumsuz örnek; mutasyon testi testin dişli olduğunu gösterdi), aynı oylar yeniden denetlendi, kayıt `progress.log` ve `manifest.json` `driver_changes` içinde. (b) `S4` / G5 metni, aracın gerçekte kontrol ettiğiyle hizalandı (ana checkout karşılaştırılmaz). (c) Bu koşuda ilk kez bir `bilun-ci-*` konteyneri koşu *sırasında* başladı (09:39'da başladı, 09:54'te yoktu; 8 pytest işçisi, ~10 GB): boş bellek 18,6 → 8,8 GB'a indi, eşik (3 GB) altına düşmedi, koşu etkilenmedi; G0 yalnız başlangıçta bakıyor.

**Karar (Safa):** (1) G6'yı bu koşuda *bilgi amaçlı* sayıp 101 maddelik kuyruğu başlatmak (~7 milyon token, ~3,5 saat; paket G6'nın tutmadığını ve düzeltilmiş hesabı açıkça yazar, spot kontrol uyuşan satırları da kapsar; önerim), (2) N havuzunu yeniden kurup kalibrasyonu tekrar koşmak (+1,8 milyon token, +1 saat; yeni havuz yine proje etiketlerinden olacağı için temizliği garanti değil), (3) burada durup gözü kapalı etiketleme yapmak.

## 11. Kapsam dışı

Kural yazmak; `src/`, `tests/`, `data/gazette/` içinde (izlenen) herhangi bir dosyayı değiştirmek; kapsam parquet'ini yeniden üretmek (`scripts/sut/build_sut_coverage.py`); atıf sağlığı düzeltmesi (ayrı iş; Eylül ölçümünde 3.248 atıfın 699'u yürürlükte olmayan, 159'u yürürlükten kalkmış maddeye gidiyordu, güncelini ölçmedim); frontend; push / PR / merge; `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` ve adı "raw data" olan klasörler (hiç açılmaz); gerçek hasta verisi.

---

## 12. Açık kararlar (varsayılanlarla)

| # | Karar | Varsayılan |
|---|---|---|
| D1 | Çıktı yeri | Repo dışı (`~/.cache/bilun-gap-classification/`); paket onaydan sonra `plans/` ya da `reports/` altına commit edilir |
| D2 | Çalıştırma yöntemi | **Çözüldü:** oturum içi alt ajanlar (başsız CLI giriş yapmamış, §8) |
| D3 | İki oy | Evet, 394 madde küçük; oy B farklı model / ifade |
| D4 | Süre kutusu / kota | 6 saat; ilk limit hatasında dur |
| D5 | Başlama | Safa'nın onayından sonra; prova yapıldı |
| D6 | İlaç dışı E2 maddeleri | Sınıflandırma sonrası karar (§7 son paragraf) |
| D7 | İlk gece kapsamı | Yalnız para etkileyen 101 madde (`--scope money`) + 30 maddelik güçlü kalibrasyon; ~9 milyon token, ~3,7 saat |
| D8 | Gece koşusu koşulları | Uygulama açık, makine uyanık (`request_keep_awake`), o sırada başka ağır iş yok |
| D9 | Modeller | Oy A `sonnet`, oy B `opus` (provada ikisi de denendi); ikinci oyu yalnız seçili satırlara uygulamak paket sonrası karar |
| D10 | Başsız sürücü | İstersen bir kez `claude setup-token` / `/login` yap: gece boyu oturumdan bağımsız, limit sonrası kendiliğinden devam eden bir sürücü mümkün olur. Ben kimlik bilgisiyle uğraşmam; şart değil |

---

## 13. Sonraki plan (bu plan bitince, ayrı)

Pilot encode döngüsü: tek kova (adaylar `exclusion_ek3b2` 16 NO_PAY maddesi gibi mekanik kovalar — içine henüz bakılmadı), parti ≤10, yazan ajan ≠ doğrulayan ajan, her kural için madde metninden türetilmiş ≥1 pozitif + ≥1 negatif fatura, kapılar: açık sayısı tam parti kadar düşer, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, atıf sağlığı kötüleşmez, 16 vitrin raporu değişmez (bilerek değiştirmiyorsa), pytest; iki kez kırmızı parti karantina; çıktı tek dal, otomatik merge / push yok.
