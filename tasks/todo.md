## Task: Fix Documentation After Fact-Check

### Goal
Update all 12 docs in `docs/` to reflect current codebase structure and correct all factual errors found.

### Subtasks
- [ ] Phase 1: Global path rewrite (src/sut/ → src/bilun/domain/, src/api/ → src/bilun/api/, etc.)
- [ ] Phase 2: sut.md — fix 60 exports, API prefix, row counts, unverifiable claims, path refs
- [ ] Phase 3: gazette.md — fix row counts (117,285 → 115,568, EK-3 4,407 → 3,265)
- [ ] Phase 4: algorithms_reference.md — fix HEMOGRAM_TESTS count, lab lookup description
- [ ] Phase 5: Decision docs — remove nonexistent plan refs, fix filenames, fix env var names
- [ ] Phase 6: External docs — fix broken wiki links in olive-ai-post-mortem.md
- [ ] Phase 7: Verify — grep for old paths, spot-check

### Out of Scope
- Creating missing plan files or wiki pages
- Adding unverifiable analysis code to repo
- Fixing empty EK-3 curated parquets

### Review
Full fact-check report in `plans/docs-fact-check-fix.md`.
