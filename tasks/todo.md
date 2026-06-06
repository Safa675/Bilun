## Task: Copay UI — exemption gap rephrase (Option A)

### Goal
Use **Exemption gap** / **Muafiyet farkı** for copay TRY; dual-benefit footnote; MEDULA chip; hospital recoverable separate from exemption gap in billing summary.

### Subtasks
- [x] Backend: `gap_kind`, `savings_beneficiary=patient_and_sgk`
- [x] Frontend en/tr: exemption gap KPIs, footnote, MEDULA chip, billing summary dual totals
- [x] Optimizer: Exemption gap (corrective)
- [x] Chatbot + tests updated

### Review
- `grand_total_recoverable` excludes exemption gap; billing summary shows both columns when exempt.

### Out of Scope
- MEDULA HIS export; EK-1A visit-scope narrowing
