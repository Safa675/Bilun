## Task: Prose corpus human review — HTML audit export (decided)

### Goal
Regenerable **HTML-only** sidecars from `prose_corpus/*.csv` for Gate B human audit.
Not production; not a replacement for machine CSV. Reviewers open one file in a browser.

### Decision (2026-06-26)
**HTML wins.** XLSX was useful for the A/B prototype; for ongoing human audit HTML is
clearly better: readable long Turkish excerpts, custom layout, client-side sort/filter,
no Excel dependency. Neither format ships in the product.

### Subtasks
- [x] Prototype `scripts/sut/export_prose_review_bundle.py` (card layout + legend)
- [x] Safa decision: **HTML primary**
- [ ] **HTML v2** — table view + JS sort/filter on all columns; optional card/detail toggle
- [ ] Wire HTML export into corpus scripts (`export_material_bundling_clauses.py`, `anti_vegf_4233_export.py`, …) — run after CSV write
- [ ] Drop or gate XLSX behind `--xlsx` (default off) once HTML v2 is enough
- [ ] `DATA_DICTIONARY.md` + legend synced with `in_force_text` / `encode_priority` columns post strike-strip

### HTML v2 ideas (exactly how we want rules shown)
| Feature | Why |
|---------|-----|
| Sortable table (all columns) | Rank by `encode_priority`, `section_id`, `char_count` |
| Column filters | e.g. only `p1_encode`, hide `skip_annex_duplicate` |
| View modes | Table (scan) + card (read full `excerpt` / `in_force_text`) |
| Badges | `encode_priority`, `deontic_modality`, `duplicate_of` color-coded |
| Strike context | Badge if clause is legacy-only (`is_in_force=false` in parquet join) — post in-force pipeline |
| Deep links | `#C002684` anchor per row (already in prototype) |
| Sign-off (optional) | `localStorage` reviewer notes — export back to CSV is v3 if needed |

No server, no auth: single self-contained `.html` file (inline CSS + vanilla JS).

### Out of scope
- Rule Database UI / production Gate B workflow
- Replacing CSV for CI/diff
- Hosted review server

### Regenerate (current prototype)
```bash
python scripts/sut/export_prose_review_bundle.py --html-only   # after v2 flag
python scripts/sut/export_prose_review_bundle.py \
  --csv data/gazette/prose_corpus/L4.33_anti_vegf_corpus.csv \
  --title "L4.33 Anti-VEGF §4.2.33"
```

Outputs today: `data/gazette/prose_corpus/review/*.review.html` (L1.4 now 24 rows after in-force filter).

### Review
Prototype 2026-06-26. Decision: HTML for human audit; XLSX optional/deprecated.
