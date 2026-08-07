# TIER-2 Stale Refs — Phase 4 Örnekleme Sonucu ve Politika Kararı

**Tarih:** 2026-08-06
**Plan:** `plans/update/2026-08-06-stale-clause-triage-plan.md` — Phase 4
**Yöntem:** 687 T2 ref'inden rule-set büyüklüğüyle orantılı, sabit seed'li (42) stratified örneklem; 37 vaka; 12 rule-set'in tamamı kapsandı. Her vaka: clause metni + aynı koordinattaki kardeş clause'lar + parquet-geneli taşınma araması (3 paralel analiz).

## Ana bulgu: TIER-2 bayrakları doğru — gürültü oranı 0/37

37 örneğin **37/37'i GENUINELY-DEAD** (her `is_in_force=False` doğru), **0 NOISE**, 0 UNCERTAIN. Ölü clause'lar tek tip: konsolide 2013 SUT docx'inde tutulan **eski amendment-katmanı satırları** (Mülga/Değişik marker'lı veya in-force ikiziyle aynı koordinatta). Rule of three ile %95 güven üst sınırı ≈ %9.5 — gerçek gürültü oranı düşük kalmaya mahkûm, çünkü örneklemde tek bir hatalı bayrak bile çıkmadı.

**Politika sonucu 1:** T2 için toplu yeniden sınıflandırma veya extractor düzeltmesi **gerekmiyor**. Reporter doğru ölçüyor.

## İkinci bulgu: içerik çoğunlukla taşınmış — sorun kural değil, pointer

| Taşınma | Adet | Anlam |
|---|---|---|
| YES | 28 | Ölü clause'un içeriği başka in-force clause'da aynen mevcut (çoğu aynı koordinatta in-force ikiz) |
| PARTIAL | 5 | İçeriğin bir kısmı taşınmış |
| NO | 3 | İçerik tamamen kaldırılmış (idx 0, 6, 13) |

**Politika sonucu 2:** T2 burn-down'ın ana aksiyonu **pointer hijyeni** — `gate_b_sources`'ları in-force ikizlere yeniden bağlamak. Bu büyük ölçüde otomatikleştirilebilir (aynı koordinatta in-force kardeş varsa re-point).

## Üçüncü bulgu: gerçek kırık nadir (~%5) — 5 vaka insan kararı ister

| rule_id | Sorun | Aksiyon |
|---|---|---|
| `3.3.1.(10).wound_debridman_no_pay` | §3.3.1 RG-12/12/2024 ile yeniden yazıldı; larva/ultrasonik debridman dışlaması artık hiçbir in-force clause'da yok | Sil veya yeni §3.3.1'e göre re-encode (hukuki karar) |
| `4.2.33.E.siklosporin_kuru_goz` | Kural mülga "3 göz uzmanı sağlık kurulu raporu"nu enforce ediyor; güncel hukuk tek uzman raporu istiyor (C006575) | Re-encode |
| `3.1.2.(2).not_in_ek3c` | İçerik C002707'de aynen yaşıyor; pointer ölü clause'a | Re-point |
| `3.1.4.diagnosis_package_material_unbundled` | İçerik C002801'de yaşıyor; pointer ölü clause'a | Re-point |
| `3.1.3.(8).fixed_asset_repair_spare_part_no_pay` | İçerik C002795'te yaşıyor; pointer ölü clause'a | Re-point |

## Ek bulgular (ayrı iş kalemleri)

1. **Yanlış koordinat eşleşmesi** (idx 3, 4, 6, 8): gate_b çözümleyici, koordinatı eskiden işgal eden clause'u seçmiş — re-point ile temizlenir.
2. **Ölü duplike referanslar** (idx 11/12): bir kural aynı paragrafın iki ölü duplikesini (C004724, C004795) birden cite ediyor; canlı versiyon C004912 — dedup fırsatı.
3. **Data-freshness açığı** (idx 36): `copay_general_1_8` kuralı RG-01/07/2026-33297 tutarlarını (50/90/100 TL) kullanıyor ama parquet'teki en yeni in-force değerler 26/60 TL — clause store henüz o tebliği içermiyor. Ayrı SUT-update işi.
4. `gap_closing_treatment_2` idx 23: kuralın denial_tr'si clause'daki "böbrek nakli"ni "kök hücre nakli" diye etiketliyor — kozmetik hata.

## Politika özeti (Phase 4 kararı)

1. **T2 bayraklarına dokunma** — extractor doğru çalışıyor (0/37 gürültü).
2. **Burn-down stratejisi:** (a) aynı koordinatta in-force ikiz olan T2 ref'leri için otomatik re-point batch'i; (b) DEPENDS vakaları (yukarıdaki 5) için insan kararlı küçük PR; (c) reporter gate yapılmaz.
3. **T2 reporter'ı gate yapılmaz** — pointer hijyeni tamamlanana kadar uyarı olarak kalır.
4. Örneklem raw verisi: `/tmp/opencode/phase4_dossier.json` + `phase4_review_{1,2,3}.md` (geçici); bu belge kalıcı karar kaydıdır.

---

## Uygulama (2026-08-07)

Onaylı liste uygulandı; T2 687→674:

- **4 re-point:** not_in_ek3c→C002707, diagnosis_package→C002801, fixed_asset→C002795, hcv_geno1_4→C004912 (ölü duplikeler temiz)
- **Siklosporin re-encode:** tek uzman + C006575; `struck_clause_no_replacement` kaldırıldı
- **2 silme:** wound_debridman (dışlama hukuktan kalktı); gap_closing transplant duplikesi (doğru encode treatment_pricing'da zaten vardı: `abo_incompatible_kidney_transplant_no_pay` — "kozmetik etiket" sanılan hata aslında yanlış kategorili duplikeydi, silmek elegant fix)
- **Yapılmadı (ayrı iş):** copay data-freshness (yeni SUT paketi gerekir)
