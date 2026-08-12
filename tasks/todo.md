## Task: K2 — Kan ürünleri tier'ları — CONFIG katmanı (kanban t_f9ed6c00)

### Goal
4 kan ürünü tier'ı (0.36/0.24/0.20/0.28) × 8 kod (705371, 705430, 705440, 705372,
705373, 705441, 705442, 705443) yapısal olarak `data/gazette/prose_rules/
session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
içine işlensin; compile + check + ruff yeşil; motorun genelleştirilmiş
`blood_component_billable_fraction()`'ının okuyacağı `fractions` haritası net.

### Yol seçimi: Path B (JSON'a elle ekle) — gerekçe
- `_payload_preserving_key_order` (scripts/sut/compile_rules.py:109-124),
  `_write_rule_set_for_target` (167-173) ile compile, committed JSON'daki
  üretilmeyen top-level anahtarları (special_codes dahil) korur.
- Tarihsel kanıt: special_codes 8406b8f'den beri var, 2 regenerasyon (13ca112,
  757cae1) sonrası da duruyor.
- Path A (YAML) shared `_compile_fresh`'i değiştirmeyi + var olmayan bir YAML
  special_codes konvansiyonu icat etmeyi gerektirir — tüm fresh target'ları
  riske atar, over-engineering.
- Ampirik test: compile sonrası JSON'da fractions DURUYOR olmalı.

### Subtasks
- [x] `session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
      içine `fractions` dict'i ekle (8 kod → fraction; 0.36/0.24/0.20/0.28);
      `codes[]` + `billable_point_fraction` backward-compat için koru; note güncelle.
- [x] Lock kontrolü (`fuser /tmp/bilun_compile_rules_check.lock`); ghost varsa öldür.
- [x] `.venv/bin/python scripts/sut/compile_rules.py` (write) — background ~8-9 dk.
- [x] Compile sonrası doğrula: JSON'da special_codes + fractions DURUYOR;
      `git diff --stat` sadece hedeflenen dosya (format gürültüsü yok).
- [x] `.venv/bin/python scripts/sut/compile_rules.py --check` (byte-identical).
- [x] `.venv/bin/ruff check scripts/`.
- [x] İlgili testler: test_session_pricing_json_driven.py, test_prose_rules.py
      (blood fraction), test_blood_uplift.py — regresyon yok.
- [x] `git status --short` kontrolü (lessons.md kuralı), commit wt/p71-k2'ye (push YOK).
- [x] kanban raporu (yol A/B + şema + compile/check çıktısı + diff stat) + block review-required.

### Out of Scope
- Motor kodunun genelleştirilmesi (src/bilun/domain/prose_rules/session_pricing.py)
  — Reimbursement task'ı; ben sadece config/veri katmanını işliyorum.
- ISBT 128 barkod format doğrulaması — motor tarafı.
- treatment_pricing_2_4.json / drug_indication_prose.json düzenlemesi
  (corroborating prose, session_pricing motoru okumuyor).
- Push / PR açma (branch'e commit, push yok).
