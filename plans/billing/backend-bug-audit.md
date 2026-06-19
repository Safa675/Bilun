# Plan: Backend Bug Audit Raporu

**Tarih:** 2026-06-19
**Kapsam:** `src/bilun/` backend (6 alan, ~33.407 LOC): `api/`, `domain/`, `db/`, `cache/`, `chatbot/`, `shared/`
**Yöntem:** 3 paralel Explore subagent (api + domain + db/cache/chatbot), tüm bulgular `Grep`/`Read` ile kanıtlandı. Chatbot PII bulgusu ve shared-connection bulgusu main agent tarafından ek doğrulamadan geçti.
**Tür:** Tespit raporu — fix'ler ayrı task'lerde (AGENTS.md §7). Bu rapor sadece envanter + öncelik.

---

## Özet

| Alan | Dosya | LOC | CRITICAL | HIGH | MEDIUM | LOW |
|---|---|---|---|---|---|---|
| api/ | 14 | 4023 | 1 | 5 | 6 | 4 |
| domain/ | 142 | 21471 | 3 | 7 | 5 | 0 |
| db/ + cache/ + chatbot/ | 32 | 7330 | 4 | 7 | 6 | 3 |
| **Toplam (de-dup)** | **188** | **32824** | **7** | **17** | **15** | **7** |

**En kritik 3 bulgu:**
1. **[B-C1]** Chatbot hasta verisini (PII: patient_id, tanı, fatura tutarları) OpenRouter'a KVKK consent gate'i olmadan gönderiyor — healthcare veri sızıntısı.
2. **[B-C2]** API process-ömrü boyunca tek read-write DuckDB connection'ı tutuyor → cache rebuild'i lock'luyor → stale SUT verisi servis ediliyor (PID 399842 senaryosunun kök nedeni).
3. **[B-C3]** DRG `ek2c_group` her zaman yanlış key'den okuyor (`entry["ek2c_group"]` ama veri `"group"` altında) → tüm DRG episode'ları yanlış kategorize ediliyor.

---

## CRITICAL (7)

### [B-C1] Chatbot hasta verisini OpenRouter'a consent/redaction gate olmadan gönderiyor (KVKK)
- **Dosya:** `src/bilun/chatbot/context.py:870-884`, `src/bilun/chatbot/llm.py:64-66`
- **Kod:**
  ```python
  if patient_id:
      context["patient_context"] = build_patient_context(data)      # patient_id + tanılar + DRG
      context["billing_context"] = build_billing_context(data, ...)  # tüm TRY tutarları, claim_id'ler
      if user_role == "dev":
          context["billing_report_json"] = raw_report               # tam ham billing report
  # llm.py: runtime_context system prompt'a append edilip OpenRouter'a POST
  ```
- **Neden bug:** Türk SGK healthcare reimbursement sistemi. patient_id, tanılar, fatura tutarları KVKK korumasında. Bu veriler `https://openrouter.ai/api/v1/chat/completions`'a system message olarak gönderiliyor — consent flag yok, alan-bazlı redaction yok, DPA gate yok. `_get_api_key` (llm.py:41) sadece anahtar varlığını kontrol ediyor, kullanıcının veriyi dış LLM'a aktarmaya yetkili olduğunu değil. Herhangi bir role için (dev değil dahil) hasta seçiliyken koşulsuz gönderiliyor.
- **Main agent doğrulaması:** ✅ Yapıldı — `build_bilun_runtime_context` (context.py:807-907) baştan sona okundu, hiçbir authorization/consent check yok.
- **Fix yönü:** Açık consent flag + rol kontrolü ekle (hasta verisi dış LLM'a gitmeden önce); OpenRouter DPA + data residency belgele. Mevcut duruma kadar: hasta-bağlam-chat'ı config-driven disable et.
- **Güven:** verified

### [B-C2] API tek read-write DuckDB connection'ı process ömrü boyunca tutuyor (stale data + lock)
- **Dosya:** `src/bilun/shared/runtime.py:53-63`, `src/bilun/db/connection.py:33-39`, `src/bilun/api/routes/alerts.py:242`
- **Kod:**
  ```python
  # runtime.py — process-singleton read-write connection
  def get_cache_con(self):
      if self.cache_con is not None:
          return self.cache_con
      self.cache_con = connect_cache_db(self.canonical_cache_db_path)  # read-write!
  # connection.py
  def connect(db_path): return duckdb.connect(str(db_path))   # read_only değil
  ```
- **Neden bug:** DuckDB dosya başına tek read-write connection izin verir. uvicorn worker (PID 399842) açılışta read-write bağlanıp hiç bırakmıyor. `get_cache_reader()` aynı connection'ın `.cursor()`'u — izole değil. Sonuç: (a) `build_cache.py --activate` ayrı process write lock alamıyor → rebuild başarısız/aktivasyon olmuyor, (b) API eski build'i servis etmeye devam ediyor (01.17), (c) her read endpoint'i `INSERT OR IGNORE INTO build_pointer_scopes` yazıyor (builds.py:282) → concurrent request'ler aynı connection'da yazışıyor. **Bu, "SUT replace sonrası cache rebuild" sorusunun kök nedenidir.**
- **Fix yönü:** API cache connection'ı `read_only=True` aç; ayrı reader process veya per-thread connection.
- **Güven:** verified (3 audit bağımsız doğruladı)

### [B-C3] DRG `ek2c_group` her zaman yanlış dict key'inden okuyor → tüm DRG episode'ları yanlış kategorize
- **Dosya:** `src/bilun/domain/analytics/drg.py:254-256`
- **Kod:**
  ```python
  entry = get_ek2c_entry(package_code, as_of_date=admission_date.isoformat())
  if entry and entry.get("ek2c_group"):     # ← hep None
      ek2c_group = entry["ek2c_group"]
  # fallback: _ICD10_CHAPTER_TO_EK2C_GROUP.get(chapter, "C")
  ```
- **Neden bug:** `get_ek2c_entry` (`catalog_membership.py:118-127`) alanı `"group"` key'i altında saklıyor, `"ek2c_group"` değil. `entry.get("ek2c_group")` hep None → if hiç çalışmıyor → her DRG episode chapter-heuristic ile etiketleniyor. API payload'a (`drg_payload.py:83`) ve group-bazlı agregasyona yayılıyor. Bu backend'in en kolay CRITICAL fix'i (tek satır: `entry.get("group")`).
- **Fix yönü:** `entry.get("group")`.
- **Güven:** verified

### [B-C4] Bundling/exclusion substring match'i iki yönlü → yanlış malzeme flag'leme (para + tıbbi karar)
- **Dosya:** `src/bilun/domain/rules/bundling_rules.py:108-110`, `src/bilun/domain/materials/exclusions.py:111,162`
- **Kod:** `if needle in mat_name or mat_name in needle: return entry`
- **Neden bug:** Match `needle in entry OR entry in needle`. Kısa EK-3B-1 entry ismi alakasız malzemeleri substring olarak yakalıyor: "tel" → "metal stent", "kitel"; "cam" → "camaflaj". Bu malzemeleri reimbursable/non-reimbursable ve bundled/separately-billable arasında çeviriyor — hem yanlış para (claim line düşürülüyor veya risk_amount yanlış), hem yanlış tıbbi billing kararı.
- **Fix yönü:** Token-bound match (kelime sınırı) veya sadece `entry in needle` (uzun malzeme isminde entry tam geçiyorsa), tersi değil.
- **Güven:** verified

### [B-C5] Eksik `procedure_date` alakasız prosedürleri tek session'da birleştiriyor
- **Dosya:** `src/bilun/domain/prose_rules/claim_utils.py:96-102` + `src/bilun/domain/claims/parsing/primitives.py:91-95`
- **Kod:**
  ```python
  grouped[line.procedure_date].append(line)   # date.min (0001-01-01) key
  # primitives.py: null date → date.min
  ```
- **Neden bug:** `procedure_date` null ise `date.min`'e parse ediliyor, atlanmıyor. Tüm tarihsiz prosedür satırları tek `0001-01-01` key'inde gruplanıyor → tek session muamelesi. Bu `compute_session_point_factors`'a (§2.2.2.B %25/30/50 tenzil) besleniyor → alakasız prosedürler arası yanlış tenzil → tüm claim yanlış fiyatlanıyor. Ayrıca `0001-01-01` her as-of filter'ından geçer.
- **Fix yönü:** `date.min`'e eşit satırları session gruplamadan çıkar veya her birini ayrı session say.
- **Güven:** verified

### [B-C6] Read path lazy WRITE yapıyor (alerts tablosu rebuild) → concurrent read corrupt + lock deadlock
- **Dosya:** `src/bilun/api/routes/alerts.py:242`, `src/bilun/db/patient_alerts.py:435-464`
- **Kod:**
  ```python
  reader = _get_cache_reader()   # shared read-write connection'ın cursor'u
  ensure_patient_alert_tables(reader, active_build)   # DELETE + INSERT!
  ```
- **Neden bug:** Read endpoint'i lazy backfill için shared reader üzerinde `transactional(con)` ile DELETE+INSERT çalıştırıyor. DuckDB transaction'ları connection-scoped; commit'lenmemiş DELETE her concurrent cursor'a görünür ve block'lar. 500-satırlık batch backfill sırasında tablo saniyelerce half-populated kalıyor; concurrent `read_patient_alert_rows_page` inconsistent row count görüyor → `ServiceUnavailableError`. `_patient_alert_backfill_lock` process-içi thread lock, ayrı build process'e karşı korumaz.
- **Fix yönü:** Legacy backfill'i request path'inden çıkar (build her zaman `patient_alert_rows` doldursun); runtime backfill kaçınılmazsa ayrı kısa-ömürlü write connection.
- **Güven:** verified

### [B-C7] Stale data tespit mekanizması yok — API source_hash karşılaştırmıyor
- **Dosya:** `src/bilun/db/builds.py:279-288` (read), `src/bilun/cache/builder.py:205` (build writes source_hash)
- **Neden bug:** Build `source_hash`/`config_hash` (parquet mtime+size) yazıyor ama read path hiçbir zaman current parquet hash'ini recompute edip karşılaştırmıyor. 04.08 parquet'leri diske yazılınca `source_hash_from_files` değişiyor ama `get_active_build_id` yine 01.17 build_id döndürüyor. `/health`'te stale flag yok, uyarı log'u yok. `request_cache.STATE_STALE` tanımlı ama canonical build için hiç yazılmıyor. B-C2 ile birlikte: sistem stale servis ediyor ve bunu bilmiyor.
- **Fix yönü:** API startup + periyodik olarak `source_hash_from_files` recompute et, `build_meta.source_hash` ile karşılaştır, mismatch'i degraded health flag olarak surface et.
- **Güven:** verified

---

## HIGH (17) — özet liste (tam detay alt-audit'lerde)

### Para / billing doğruluğu
- **[B-H1]** `procedure_addon_uplift` recoverable TRY'yi addon'ın kendi list fiyatı değil trigger'ın billed amount'undan hesaplıyor → SGK uplift headline yanlış. `procedure_addon_uplift.py:218`
- **[B-H2]** as-of catalog fallback cutoff'tan önce hiç tarih yoksa EN ESKİ fiyatı döndürüyor (olması gereken: None/empty). `loaders/gazette.py:45-48`, `catalog_membership.py:60-64`. `pricing/temporal.py` ile tutarsız (o None döndürüyor).
- **[B-H3]** Cohort `cohort_mean_rate`/`rate_distribution` EK-2C-1'de olmayan kodlarla kirleniyor (catalog_validated=True default). `aggregator.py:141-147` + `catalog_join.py:72-75`
- **[B-H4]** `rate_distribution` key formatı iki path'te farklı (`Decimal.normalize()` → "4E+1%" vs float → "40.0%") → distribution'lar merge edilemiyor. `exactness.py:216` vs `aggregator.py:144`
- **[B-H5]** `total_copay_savings_try` field adı "total" ama sadece visit savings — drug savings düşüyor. `billing_actions.py:68` fallback'te sıfır gelince yanlış total. `claim_copay.py:231`

### None / tip güvenliği
- **[B-H6]** `claim_materials` latest-line selection `material_date=None` olursa `None >= None` → TypeError, patient material pre-check tamamen abort. `claim_materials.py:83`
- **[B-H7]** Session primary line seçimi duplicate normalized code'da factor-map key collision yüzünden yanlış line seçebiliyor → tüm session yanlış fiyatlanıyor. `session_pricing.py:378-385`

### Stale data / tebliğ migration
- **[B-H8]** Checkup katsayi + docstring stale (01.17 = 0.593, RG-17/1/2026). 04.08 replace sonrası güncellenmedi. `catalog.py:282-285`

### Cache build lifecycle
- **[B-H9]** Expensive backfill 100% failure durumunda bile build'i COMPLETE+activate ediyor → half-built build active servis ediliyor. `build_expensive.py:54-136`, `builder.py:360-432`
- **[B-H10]** `run_active_sut_expensive_backfill` aktif build'in expensive tablosunu önce siliyor sonra batch yazıyor; Ctrl-C/crash'te half-populated kalıyor, restore yok. `build_expensive.py:70-76,164-230`

### Chatbot
- **[B-H11]** Token budget hiç enforced değil — runtime context (dev mode'da tam billing report) model context window'u sessizce aşıyor; `_validate_messages_for_llm` runtime_context append'inden ÖNCE çalıştığı için bypass. `llm.py:64-66,259-280`
- **[B-H12]** Streaming'de backpressure yok — `asyncio.Queue(maxsize)` yok, verbose model + yavaş client = sınırsız memory growth. `llm.py:131-201`, `chat.py:470`
- **[B-H13]** `_call_llm` HTTP error'larını (401/402/413/429) generic "Unable to reach LLM"'e collapse ediyor; streaming raw upstream error body'yi kullanıcıya sızdırıyor. `llm.py:101-128,158-167`
- **[B-H14]** Decimal money `float()`'a serialize ediliyor (representation error, cohort aggregate'lerde drift). `cache/sut_context.py:302-318`, `cache/payloads.py:43-46`, `api/routes/patients.py:51-57`

### API contract
- **[B-H15]** `get_bill_optimization` claim_dataset None olunca guard'ı atlıyor, fabricated bill-scoped payload dönüyor (gerçekte patient-scoped). `optimization.py:265-286`
- **[B-H16]** `/health` DuckDB error path'inde connection leak (con.close() sadece success path'ında). `api/__init__.py:103-115`, `startup.py:31-34,94-96`
- **[B-H17]** Provenance her zaman cohort summary'den okunuyor, patient/bill satırından değil → stale/mismatched durumda yanlış data_source reklam ediliyor. `provenance.py:28-38`

---

## MEDIUM (15) — özet liste

Para/serialization (Decimal→float _money helper 7 yerde: `claim_strategy.py:38`, `session_pricing.py:243`, `gazette_repricing.py:30`, `material_uplift.py:34`, `drg_package_adequacy.py:27`, `procedure_addon_uplift.py:27`, `claim_audit_exposure.py:9`); bank rounding SUT citation yok. Diğerleri: rate-limit IP-only bypass (chat.py:42-51), `time.time()` wall-clock (chat.py:31-51), SSE `[DONE]` quoted (chat.py:54-58), pagination silent clamp (billing.py:253-262), operator-precedence fragility (drg_package_adequacy.py:159), ek1a partial exemption default-True footgun (copay_exemptions.py:65), hemogram over-count riski (claim_lab.py:35-37), `transactional` rollback silent-swallow (_internal.py:109-121), cleanup_build_lifecycle autocommit (builds.py:328-406), naive datetime cleanup (request_cache.py:60-67).

## LOW (7)

Hardcoded effective_date (validation.py:94,107), material substring search UX (pricing.py:94-98), materials specialty 500-cap pagination yok (billing.py:282-287), PIPELINE_MODE module-global foot-gun (patients.py:47 vb.), temp filename TOCTOU (patient_alerts.py:361), metadata .max() mixed types (metadata.py:16-29), zero-token INFO log tutarsız (llm.py:189-194).

---

## Doğrulanan "bug değil" bulgular (audit'lerin yaptığı olumsuz kanıtlar)
- **SQL injection:** Yok — tüm DuckDB query'leri parametrize `?` placeholder. f-string SQL sadece `placeholders` (`?` string) + whitelist'lenmiş kolon adları içinden, user input yok. (`patient_meta.py`, `patient_alerts.py`, `patients.py:108-115`)
- **Division by zero money path:** Korunuyor (`claim_context.py:55`, `drug_discounts.py:72`, `temporal.py:51` hepsi `==0` guard'lı).
- **Rule application order:** Doğru — exclusions bundling'den sonra, prose annex list'lerden sonra; risk vs savings ayrı accumulate. (`rule_engine.py`)
- **Decimal aggregation:** `claims/totals.py` `Decimal("0.00")` ile doğru başlatıyor.
- **Mutable default Pydantic v2:** `MaterialItem: list = []` güvenli (Pydantic v2 deep-copy'ler).

---

## Önerilen fix önceliği (sıralı)

1. **[B-C1]** Chatbot PII gate — healthcare veri sızıntısı, regulatuar risk. (Acil)
2. **[B-C2] + [B-C7]** Shared read-write connection → read_only + staleness tespiti. Bu aynı zamanda "cache rebuild" blocker'ı çözüyor. (Acil)
3. **[B-C3]** DRG `entry["group"]` — tek satır, tüm DRG grouping fix. (Kolay + yüksek etki)
4. **[B-C4]** Substring bundling match tightening — yanlış para + tıbbi karar.
5. **[B-C5] + [B-H2]** date.min session collapse + oldest-price fallback — birlikte session pricing ve as-of selection corrupt.
6. **[B-C6]** Alerts read-path write — concurrent read corrupt.
7. **[B-H9] + [B-H10]** Cache build lifecycle — half-built build active servis edilmesi.
8. **[B-H1, H6, H7, H14]** Money doğruluğu cluster (addon fiyatı, None date, session primary, Decimal→float).
9. Geri kalan HIGH/MEDIUM — dalga dalga ayrı task'lerde.

## Out of scope (bu audit'te yok)
- Frontend, scripts, tests (ayrı audit'ler yapıldı)
- Feature request'ler, stil/dead-code (ayrı concern)
- Full patch yazımı — bu rapor tespit; fix'ler ayrı task (AGENTS.md §7)

## Riskler
- Bazı HIGH bulgular (H7 session primary, H5 copay fallback) "suspicious" — duplicate-code veya falsy-zero senaryosu gerektiriyor, üretim datasında realize olmayabilir. Fix'lemeye başlamadan önce her birini gerçek cohort fixture'ında reproduce etmek gerekir.
- Chatbot token-budget ve streaming bulguları model seçimine bağlı (şu anki OpenRouter modelinin context window'u büyükse H11/H12 realize olmayabilir).
