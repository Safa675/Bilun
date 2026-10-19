# Plan: SUT açık maddelerinin salt-okunur sınıflandırma döngüsü (gece koşusu)

**Durum:** Taslak, onay bekliyor — 2026-10-19
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
| Kuyruktaki `primary_rule_id` ailesi / partiler (≤12 madde) | 26 aile / 48 parti |
| Kuyruğun toplam metni | 141.707 karakter (~40 bin token; ortalama 360, en uzun 3.823) |

Not: açık maddelerin hepsi yürürlükte; başlık ve değişiklik maddesi yok. Metnin kendisi ucuzdur; maliyet, ajanın kanıt aramasından (kod, ek listeleri) gelir ve akşam provasında ölçülür.

---

## 1. "Bitti"nin tanımı (başarı koşulu) — hepsi makineyle kontrol edilir

Koşu üç düzeyden biriyle biter; düzey `manifest.json`'a ve `00-ozet.md`'nin ilk satırına yazılır.

| Koşul | Ölçüt |
|---|---|
| **S1 Tamlık** | 394 maddenin her biri için tam bir son kayıt; her kayıtta iki geçerli oy (A, B). |
| **S2 Kalibrasyon** | Altın kümede (45 madde, bkz. §4) her iki oyun **üst-sınıf** doğruluğu ≥ %80. |
| **S3 Uyuşma** | Tüm kuyrukta iki oyun üst-sınıf uyuşması ≥ %70 (tam sınıf uyuşması ayrıca raporlanır). |
| **S4 Yan etkisizlik** | Okuma klonu salt-okunur ve `git status --porcelain` boş; `data/gazette/sut_clause_coverage.parquet` sha256'sı koşu başı = koşu sonu; ana checkout'a ve çalışma ağaçlarına hiç dokunulmadı. |
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
- **Parti:** aynı `primary_rule_id` içinde, `section_id` sırasıyla ≤12 madde → 48 parti. `parti_id = sha256(sıralı clause_id listesi)[:10]`.
- **Sıra:** önce para etkileyen modalite içeren partiler (101 madde), sonra COVERAGE / REGULATORY_ACTION / PERMISSION, en sonda modalitesizler. Gece yarıda kesilirse en değerli kısım bitmiştir.
- **Ajana verilen alanlar:** `clause_id`, `section_id`, `section_path`, `clause_type`, `text_tr` (tam), `deontic_modality`, `annex_refs`, `procedure_codes`, `primary_rule_id`, `matched_rule_ids`.
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

**Rubrik dosyası** (kararlar + 8 çözülmüş örnek) koşu başında dondurulur ve sha256'sı `manifest.json`'a yazılır.

---

## 4. Döngü (parti başına) ve altın küme

**Bir kez, ilk partiden önce — kalibrasyon (G6):** sabit tohumla (`20261019`) 45 madde: 15 encode edilmiş (`has_rule_encoding` ve `implemented`; ailelere yayılmış) → beklenen **E1**; 15 `emr_blocked` → beklenen **E2**; 15 `non_algorithmic` (başlık / değişiklik hariç) → beklenen **{K1, T1, N1}**. Sınıflandırıcıya kuyrukla aynı alanlar verilir, etiketler verilmez. Üst-sınıf doğruluğu ≥ %80 değilse koşu durur (KIRMIZI).
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
| **G5 Yan etki** | Okuma klonunda `git status --porcelain` boş; parquet sha256 değişmedi; ana checkout `HEAD` ve `git status` aynı | **Anında dur (KIRMIZI)** |
| **G6 Kalibrasyon** | §4: altın küme ≥ %80 | Dur (KIRMIZI) |
| **G7 Uyuşma alarmı** | İlk 5 partide iki oyun üst-sınıf uyuşması < %60 ya da bir partide tek sınıf > %70 iken altın küme dağılımı bunu desteklemiyor | Dur (rubrik sorunu) |

**Kapıların kendisi sınanır:** doğrulayıcı betikler mutant kayıtlarla test edilir; uydurma alıntı, olmayan dosya, doğru dosya ama yanlış satır, boş kanıt, geçersiz sınıf, yasak yol içeren kayıt, tek oy eksik kayıt — hepsi reddedilmelidir (kapı yalnızca mutant testleri kadar dürüsttür).

**Okuma klonu:** `git archive <origin/main commit>` ile `~/.cache/bilun-gap-classification/<run-id>/repo/` (disk; `/tmp` tmpfs'tir, yeniden başlatmada silinir) içine açılır, yasak klasörler silinir, `chmod -R a-w` yapılır, işçiler `PYTHONDONTWRITEBYTECODE=1` ile çalışır. Çıktılar yalnız sürücünün verdiği `out/` klasörüne yazılır.

---

## 6. Durma koşulları

| Koşul | Eylem |
|---|---|
| 48 parti `done` ve S1–S6 tuttu | Paketi yaz, YEŞİL, dur |
| G6 başarısız / G7 tetiklendi / G5 ihlali | Hemen dur, KIRMIZI paket (nedenle) |
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
| `01-siniflandirma.csv` | 394 satır: madde, bölüm, modalite, sınıf, güven, tek satır gerekçe, `carrier`, `money_moving`, önerilen adım |
| `02-insan-karari.md` | H satırları: iki oy yan yana, alıntılarla |
| `03-ornekler.md` | Her sınıftan 3 satır, tam metin + gerekçe + kanıt (spot kontrol: ~20 satır, 20 dakikadan az) |
| `04-sonraki-adim.md` | Pilot encode kovası önerisi (E1 satırları aile aile); K1 / T1 / N1 için dürüst yeniden sınıflama **yama taslağı** (uygulanmaz); E2 için "hangi eksik alan kaç maddeyi açar" tablosu |
| `manifest.json` | taban commit, parquet / kuyruk / rubrik / envanter sha256'ları, model ve CLI sürümü, kapı sonuçları, parti durumları |

**Senin işin (≈15–20 dk):** `00` oku (5 dk) → `03`'ten en az 10 satır kontrol et (10 dk) → `02`'yi karara bağla ya da "bırak". Sonuç sana yetmiyorsa koşu aynı kuyruğa ikinci tur olarak uzatılır.

**Bilinen açık, sınıflandırma sonrası karar isteyecek:** `emr_blocked` / Tier-C çıkarım mekanizması yalnız ilaç kovasında var (`scripts/sut/prose/coverage.py:104-106, 497-498`). E2 çıkan ilaç dışı maddeler gap sayısını bu yolla düşüremez; ya mekanizma genişletilir ya da yeniden sınıflanır. `04`'te bu madde sayısıyla birlikte sorulur.

---

## 8. Kaynak ve makine kuralları

- Aynı anda en fazla **2** ajan süreci (oy A ve oy B) ve **0** ağır iş: pytest, vitest, docker, CI kapısı yok. Hafif Python (polars okuma) serbest. Başka bir oturum ağır iş koşarken başlama (G0).
- Her partiden sonra durum dosyası yazılır (checkpoint). Kota penceresi dolarsa devam komutu paketin başındadır.
- Maliyet bilinmiyor: **akşam provası ölçer** (parti süresi × 48). Tahmin süre kutusunu (6 saat) aşarsa parti boyutu / oy sayısı kararı sana sorulur.
- Çalıştırma yöntemi (karar D2): önerilen, repo dışındaki bir sürücü betiği (`~/.cache/bilun-gap-classification/driver/`) ve oy başına **başsız** Claude Code oturumu. Pakette gelen CLI bu makinede `~/.config/Claude/claude-code/2.1.299/*/claude`; PATH'te değil, koşu başında yolu sabitlenir (uygulama gece güncellenirse bile). Sürüm 2.1.299'da şu bayraklar var: `-p`, `--output-format`, `--json-schema`, `--model`, `--allowedTools` / `--disallowedTools`, `--permission-mode`, `--add-dir`, `--no-session-persistence`, `--max-budget-usd`, `--append-system-prompt`. Bayrakların davranışı **prova ile doğrulanır**, şimdiye kadar yalnız varlıkları görüldü. Yedek yol: tek bir ince orkestratör oturumu + iki alt ajan / parti (orkestratör limitte ölürse döngü durur, devam komutuyla sürer).

---

## 9. Riskler

| Risk | Önlem |
|---|---|
| Ajan gerekçeyi uydurur | G2 (birebir alıntı) + G3 (doğrulanmış kanıt), ikinci bağımsız oy |
| Rubrik partiler arasında kayar | Dondurulmuş rubrik + sha256; her partide aynı 8 örnek; G7 alarmı |
| Sınıflandırıcı tembelleşir (hepsini N1 der) | Kalibrasyon (G6) + parti sınıf dağılımı alarmı |
| İki oy aynı yanlışı yapar | B için farklı model / ifade; sabah 10+ satır spot kontrol; altın küme |
| Yasak klasörler okunur | Fiziksel yokluk (okuma klonu) + G4 çıktı taraması |
| OOM / kota | Seri çalışma, ≤2 süreç, checkpoint, ilk limit hatasında dur |
| Sınıflandırma "kural doğru" izlenimi verir | Pakette ve bu planda açık: yalnız açık maddelerin ne olduğunu söyler |
| Veri mahremiyeti | Girdi kamu mevzuat metni + sentetik veri; hasta verisi yok |

---

## 10. Yapılacaklar (onaydan sonra; betikler ilk koşu yargılanana kadar repo dışında)

- [ ] Okuma klonu üretici (`git archive`, yasak klasörlerin yokluğu, salt-okunur) + yokluk testi
- [ ] Kuyruk üretici (394 → 48 parti, sha256'lar) + durum dosyası
- [ ] Alan envanteri üretici (`models.py` → `claim_fields.md`)
- [ ] Rubrik + 8 çözülmüş örnek (dondurulur, sha256)
- [ ] Altın küme üretici (45 madde, tohum 20261019)
- [ ] Doğrulayıcı G1–G5 + **mutant kayıtlarla birim testleri**
- [ ] Uzlaştırıcı + paket üretici (+ çapraz tutarlılık kontrolü S6)
- [ ] Sürücü (başsız CLI, 2 oy, durma koşulları, `progress.log`)
- [ ] **Akşam provası (≈30 dk):** 1 parti (en küçük para etkileyen) + altın kümenin 9 maddelik alt kümesi (3+3+3). Kabul: G1–G7 çalışıyor, iki geçerli oy üretiliyor, süre ve kullanım ölçülüyor. Çıktı: sana **tek örnek** (bir madde için iki oy + kapı sonuçları) ve tahmini toplam süre. Geçmezse gece koşusu yok.
- [ ] Gece koşusu → sabah paketi

---

## 11. Kapsam dışı

Kural yazmak; `src/`, `tests/`, `data/gazette/` içinde (izlenen) herhangi bir dosyayı değiştirmek; kapsam parquet'ini yeniden üretmek (`scripts/sut/build_sut_coverage.py`); atıf sağlığı düzeltmesi (ayrı iş; Eylül ölçümünde 3.248 atıfın 699'u yürürlükte olmayan, 159'u yürürlükten kalkmış maddeye gidiyordu, güncelini ölçmedim); frontend; push / PR / merge; `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` ve adı "raw data" olan klasörler (hiç açılmaz); gerçek hasta verisi.

---

## 12. Açık kararlar (varsayılanlarla)

| # | Karar | Varsayılan |
|---|---|---|
| D1 | Çıktı yeri | Repo dışı (`~/.cache/bilun-gap-classification/`); paket onaydan sonra `plans/` ya da `reports/` altına commit edilir |
| D2 | Çalıştırma yöntemi | Başsız CLI sürücüsü; provada yürümezse orkestratör oturum + alt ajan |
| D3 | İki oy | Evet, 394 madde küçük; oy B farklı model / ifade |
| D4 | Süre kutusu / kota | 6 saat; ilk limit hatasında dur |
| D5 | Başlama | Akşam provasından sonra, aynı gece |
| D6 | İlaç dışı E2 maddeleri | Sınıflandırma sonrası karar (§7 son paragraf) |

---

## 13. Sonraki plan (bu plan bitince, ayrı)

Pilot encode döngüsü: tek kova (adaylar `exclusion_ek3b2` 16 NO_PAY maddesi gibi mekanik kovalar — içine henüz bakılmadı), parti ≤10, yazan ajan ≠ doğrulayan ajan, her kural için madde metninden türetilmiş ≥1 pozitif + ≥1 negatif fatura, kapılar: açık sayısı tam parti kadar düşer, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, atıf sağlığı kötüleşmez, 16 vitrin raporu değişmez (bilerek değiştirmiyorsa), pytest; iki kez kırmızı parti karantina; çıktı tek dal, otomatik merge / push yok.
