# Plan: Remove check-up pricing end-to-end

**Tarih:** 2026-07-28  
**Durum:** Implemented 2026-07-28  
**Branch (öneri):** `chore/remove-checkup-pricing` from `origin/main`  
**İstek:** UI + backend + `sut_checkup_pricing.json` tamamen kaldırılsın

---

## Goal

Check-up pricing ürün yüzeyini ve artifact’ını silmek: frontend chip/panel, `GET /api/checkup-pricing`, schema/loader/catalog API’leri, ve `data/gazette/sut_checkup_pricing.json`. Done = check-up diye bir şey kalmaz; **ama** `get_katsayi()` hâlâ çalışan motorlar için kırılmaz (katsayı başka kaynağa taşınır).

---

## Why

- Check-up paketi SGK tarafından karşılanmıyor; JSON sadece SUT referans sepeti.
- Exact hastane fiyatını bilmiyor; ana claim/optimize değerine katkı düşük.
- UI gömülü (SUT Tools → “Kontrol muayenesi” chip); keşfedilebilirlik ve ROI zayıf.
- Dosya gazette root’ta el yapımı sidecar; pipeline artifact’ı değil.

---

## Critical dependency (silmeden önce)

`sut_checkup_pricing.json` sadece UI için değil. İçinden okunan:

| Fonksiyon | Kullanıldığı yer | Check-up silinince |
|---|---|---|
| `get_katsayi()` | `anestezi_puani.py`, `refakatci.py` (+ catalog `__main__`) | **Kırılır** — taşınmalı |
| `get_copayment_info()` | yalnız `get_checkup_pricing` endpoint | silinebilir |
| `get_checkup_procedure_prices()` | endpoint + catalog debug print | silinebilir |
| `_load_checkup_json` / lab&proc index | loader + tests | silinebilir |

Zaten var: `data/gazette/sut_katsayi_history.json` (doğrulanmış katsayı 0.593 + tarihçe).

**Hard rule:** JSON’u silmeden önce `get_katsayi()` → `sut_katsayi_history.json` (güncel `coefficients` satırı) okuyacak şekilde taşınır. Aksi halde anestezi/refakatçi puan→TL yanlış/boş kalır.

`get_copayment_info` check-up dışında kullanılmıyor; katılım payı asıl kaynaklar başka yerde (EK-2C-1 vb.). Bu fonksiyondaki `katilim_payi` bloğu check-up ile birlikte gider — ayrı migrate gerekmez.

---

## Out of Scope

- Synthetic cohort adı `"checkup"` (hasta senaryo etiketi) — fiyat özelliği değil, dokunma
- `diagnosis_coding_quality` içindeki `"checkup"` keyword seti — ICD/metin sinyali, dokunma
- `gap_closing` kuralı `non_listed_control_checkups_no_pay` — SUT kuralı, dokunma
- Genel lab pricing (`LabPricesSection` / `get_all_lab_prices`) — ayrı özellik
- `schemas.py` god-file split (yalnızca `CheckupPricingResponse` silinir)
- Frontend redesign / tools chip yeniden düzeni (sadece checkup chip kalkar)

---

## Phases / Subtasks

### Phase 0 — Katsayı migrate (blocker)

- [x] **0.1** `get_katsayi()` → `sut_katsayi_history.json`
- [x] **0.2** `KATSAYI_HISTORY_PATH` + `DEFAULT_KATSAYI`; `CHECKUP_JSON_PATH` silindi
- [x] **0.3** Unit tests in `test_loaders.py`
- [x] **0.4** history note güncellendi

### Phase 1 — Backend remove

- [x] checkup loader / catalog helpers / route / schema / docs

### Phase 2 — Frontend remove

- [x] section, chip, client, i18n, `_sections-en.json`

### Phase 3 — Data remove

- [x] `sut_checkup_pricing.json` silindi; product grep temiz

### Phase 4 — Verify

- [x] loaders + anestezi/refakatçi related tests; katsayi smoke


---

## Riskler

| Risk | Mitigasyon |
|---|---|
| `get_katsayi` kırılır | Phase 0 zorunlu; test |
| Cache / OpenAPI client stale | schema + route silindiğinde FE client da silinir |
| “checkup” string’leri yanlışlıkla silinir | Out of scope listesine uy; grep’te cohort/ICD ayıkla |
| Copay UI bir yerde bu JSON’a bağlı sandık | Grep doğruladı: yalnız checkup endpoint |

---

## Definition of Done

1. UI’da Kontrol muayenesi chip’i yok.
2. `GET /api/checkup-pricing` yok; `CheckupPricingResponse` yok.
3. `sut_checkup_pricing.json` yok.
4. `get_katsayi()` `sut_katsayi_history.json` üzerinden çalışıyor; anestezi/refakatçi bozulmamış.
5. İlgili testler yeşil.

---

## Onay kapısı

**Kilitli + uygulandı (2026-07-28):** Phase 0–4 tamam.
