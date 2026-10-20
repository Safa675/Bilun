## Task: The bed motors stop expecting the days an ICU claim's own lines pay — EK-2/B 510090 and the EK-2/C ICU packages (2026-10-20)

### Goal
The standard-bed motor (and, through the one shared helper `bed_days_not_expected`, the newborn motor and the ICU reconciliation) shows no recoverable bed day on a day of an ICU claim that the claim's own ICU lines already pay: a day on which the claim bills EK-2/B 510090 or an EK-2/C ICU package (P552001-3, P552006-8, with or without the P), for as many days as the line's quantity says, and the days between the first and the last such day. Ward days of the same claim outside that stay are expected as before. The ICU motor's rows, every claim without an ICU code and the 16 showcase reports stay byte-identical; no bill's bed money or headline goes up; a false recoverable is worse than silence.

Follow-up of the block "Bed motors stop expecting a bed day the SUT says is already paid …" below (its found-not-fixed item 1 and Decision 9, which left the ICU claim's own days to "the ICU owner"); this block is that decision. Brief from the session that started this one (`local_228cd4dc-…`); the independent review's notes `…/side-session-notes/local_b23ae239-…/bed-exclusions-review-notes.md` (finding 1) were read as data and re-measured here.

**Step 0 (the brief's does not fit the tree).** It says `git log --oneline -5` must show 1e7563c9 / d1565117 / 1673a3c8 / 5e2de9d8 and otherwise to merge `claude/angry-banach-5b5bc0`. This worktree is cut from `origin/main` ba49216d, which holds that work as the squash #325 (and #326 after it): the log shows other subjects. By content (lesson of 2026-10-18): of the 10 files that branch changed (5e2de9d8..1e7563c9) seven are byte-identical in HEAD (`git diff claude/angry-banach-5b5bc0 HEAD -- <file>` empty: `yatak_puani.py`, `yatak_icu_overlap.py`, `test_bed_days_not_expected.py`, `test_bed_already_paid.py`, `test_yatak_icu_overlap.py`, `test_yatak_puani.py`), the other three differ only through later merged work (#322 in `yenidogan_yatak.py` and `test_yenidogan_yatak.py`, the tasks files), and the reverse-apply check of its diff on the two src files passes. Not merged (3 commits of duplicate content, conflicts for nothing).

### Evidence (read from the files, 2026-10-20)
`data/gazette/sut_clauses.parquet` (`in_force_text` where it differs from `text_tr`), `data/gazette/raw/annex=EK-2B/…` and `annex=EK-2C/…` (every partition, 2018-07-05 … 2026-07-07):
- C001234 §2.4.4.H.(2): "Yoğun bakım tedavileri SUT eki EK-2/C Listesinde yer alan puanlar üzerinden faturalandırılır." … "Yoğun bakım tedavisi sürmekte iken; EK-2/C Listesinde yer alan A, B, C grubu işlemin uygulanması durumunda işlemin yapıldığı gün, tanıya dayalı yoğun bakım puanı faturalandırılabilir." … "D ve E grubu işlemler yoğun bakım bedellerine dâhil olup ayrıca faturalandırılamaz." (The sentence "Yoğun bakım tedavisi uygulanmayan günlerde verilen sağlık hizmetleri, hizmet başına ödeme yöntemiyle faturalandırılabilir." is struck, "Mülga … Yürürlük: 01/05/2015": `in_force_text` drops it.)
- C001243 §2.4.4.H.(8): "Yoğun bakımda yatan hastanın, yattığı ilk gün ile vefat ettiği veya yoğun bakımdan çıkarıldığı gün ya da başka bir sağlık hizmeti sunucusunun yoğun bakım servisine sevk edildiği gün verilen sağlık hizmetleri, hizmet başına ödeme yöntemiyle faturalandırılır." C001242 (7): one ICU fee for a patient in several levels on one day. C001235 (3): no ICU fee for PACU.
- C000685 + C000686 + C000699 §2.2.2.B-1.(1).a: "Tanıya dayalı ödeme listesi işlem puanlarına yatarak tedaviler kapsamında takip alındıktan sonraki, özel hükümler saklı kalmak kaydıyla; a) Yatak bedeli, … gibi tanı ve tedavi kapsamında yapılan tüm işlemler dahil olup ayrıca faturalandırılamaz."
- EK-2/B 510090 "Yoğun bakım" (1252.27 puan = 742.60 TL on 2026-07-10): "Yemek, yatak, hasta vizit hizmetlerini kapsar. Bu kod ile birlikte monitörizasyon, hastanın mekanik ventilatöre bağlanması, ventilatör ile takip, nebülizatör, oksijen tedavisi ve derin trakeal aspirasyon ücreti ayrıca faturalandırılmaz." The same text in every partition since 2018-07-05 (the code set needs no date).
- EK-2/C P552001-3 and P552006-8 "Birinci / İkinci / Üçüncü basamak (Yenidoğan … ) yoğun bakım hastası": name and points only, no explanatory text and no işlem grubu (`get_ek2c_entry(c)["group"] == ""` for all six, the unprefixed spelling `552002` finds the same entry); 3,221.799 / 6,846.35 / 12,896.186 puan = 1,910.53 / 4,059.89 / 7,647.44 TL a day on 2026-07-10. 510010 is 222.36 TL, so one package day is 9 to 34 bed days.
- What the project already holds: `icu_puani.py` docstring — 510090 on the FIRST and LAST ICU day, P55200x on the intermediate days, ICU days = `(discharge - admission).days` (nights, not dates); `_infer_billed_icu_days` reads line quantities as days, never expects a package day that is not billed and never more than `max(raw_days, 1)` ICU days. `yatak_icu_overlap.py` — "the ICU span is the claim span and the LAST ICU day (510090) is the claim's discharge_date" (pinned by tests), the service→ICU first day "intentionally NOT in scope". `claim_has_icu_code` is the ICU motor's own gate; the newborn motor leaves any claim that passes it to the ICU motor. The ICU packages have no işlem grubu, so `claim_package_window` gives a P-prefixed one (category paket) a window of ONE day (`PACKAGE_WINDOW_DAYS.get("", 1)`) that bundles the claim's days from admission through its date (silence side); an unprefixed `552002` (category islem) opens none.
- The 8 showcase claims carry 117 procedure lines, none of them 510090 or P55200x (committed claim tables): no showcase story has an ICU day.

### Measured before (in-memory bills, HEAD ba49216d; `probe_icu.py` + `icu_lib.py` in `~/.cache/bilun-icudays-scratch/`, outputs `probe_before.txt|json`; d0 = 2026-07-10, "N dates" = N calendar dates; amounts TL; STD = standard-bed recoverable, ICU = the ICU motor's)
| # | Bill | STD today | ICU row |
|---|---|---|---|
| A1 (S5) | 3 dates, 510090 qty 3 on one line | **444.72** (2 of 3 days) | 0.00 |
| A2 | 3 dates, 510090 on each date | **444.72** | 0.00 |
| A5 | 3 dates, 510090 first + last, nothing between | **444.72** | 0.00 |
| A4 | 3 dates, 510090 + UNPREFIXED 552002 (islem) + 510090 | **444.72** | 0.00 |
| A3 | the SUT shape: 510090, P552002 (paket), 510090 | 0.00 (window + last day) | 0.00 |
| A6 | 3 dates, 510090 once on the first date | **444.72** | 742.60 |
| A17 | 3 dates, P552002 qty 3 on the first date | **222.36** | 0.00 |
| B1 (I1) | 2 dates, 510090 on both | **222.36** | 0.00 |
| D1 | 5 dates, 510090 + P552002 qty 3 + 510090 | **444.72** | (my amounts) |
| D4 | 5 dates, 510090 first + last | **889.44** | 0.00 |
| E1 | 7 dates: ward d0-d1, 510090 d2, P552002 d3-d4, 510090 d5, ward d6 | **222.36** | (my amounts) |
| E3 | 7 dates, 510090 on d2 and d5 only | **1,334.16** | 0.00 |
| E5 | 7 dates, 510090 qty 7 | **1,334.16** | 0.00 |
| J1 | 14 dates, 3-day ICU segment (d5-d7) in the middle | **1,334.16** | 0.00 |
| F2 / F3 / F6 | newborn ICU claims: 510090 qty 3 / NICU P552006 qty 3 / 5 dates SUT shape | **444.72 / 222.36 / 444.72** (no newborn row: the ICU gate) | – |
| I1 | 3 dates, 510090 qty 3 + 530000 on d0 | **222.36** | 0.00 |
| G1 | ICU claim d0-d2 (SUT shape), then ward claim d2-d4 | ICU claim 0.00, ward claim 444.72 | 0.00 |
| controls | K1 3 dates nothing 667.08 · K2 510010 qty 3 billed 0.00 · K3 530000 on d0 444.72 · K4 newborn 3 dates NB 1,322.94 · K5 ICU department, no ICU code 667.08 · K6 one date 44.45 | | |

### Candidate rules, measured on the same bills (STD recoverable; `probe_variants.py`; the ICU row does not move under ANY candidate, 0 of 54 bills)
| # | V0 today | V1 the review's one-liner (510090 into `BED_INCLUDING_CODES`) | V2 = V1 + the ICU packages | V3 = V2 + the days between the first and last ICU day (**chosen**) | V4 claim span (every day of an ICU-coded claim) |
|---|---|---|---|---|---|
| A1 / A2 / A7 / A13 / A19 / B1-B3 / D3 / E5 / F2 / F5 / I1 | 444.72 / 444.72 / 444.72 / 444.72 / 444.72 / 222.36 / 889.44 / 1,334.16 / 444.72 / 444.72 / 222.36 | 0.00 | 0.00 | 0.00 | 0.00 |
| A4 / A17 / D1 / D5 / F3 / F6 (a package line) | 444.72 / 222.36 / 444.72 / 889.44 / 222.36 / 444.72 | 222.36 / 222.36 / 444.72 / 667.08 / 222.36 / 444.72 | 0.00 | 0.00 | 0.00 |
| A5 / D4 (first and last, nothing between) | 444.72 / 889.44 | 222.36 / 667.08 | 222.36 / 667.08 | **0.00** | 0.00 |
| E3 (d2 and d5 only, ward around) | 1,334.16 | 889.44 | 889.44 | **444.72** (ward d0-d1) | 0.00 |
| E4 (qty 4 from d2, ward around) / J1 (ward around a 3-day segment) | 1,334.16 / 1,334.16 | 444.72 / 1,111.80 | 444.72 / 1,111.80 | 444.72 / 1,111.80 | **0.00 / 0.00** |
| A6 (one line on the first date only) | 444.72 | 222.36 | 222.36 | 222.36 | 0.00 |
| A11 (reversals only) / A18 (line dated before the stay) | 444.72 / 444.72 | 444.72 / 444.72 | 444.72 / 444.72 | 444.72 / 444.72 | 0.00 / 0.00 |
| controls K1-K6, G1, G2, X1 | unchanged | unchanged | unchanged | unchanged | unchanged |
V1 fixes the "qty n" shapes and misses every package line and every gap; V2 misses the gap between a billed first and last day (a package day the claim does not bill); V4 is simplest and silences the ward days of every ICU-coded claim (E3, E4, J1, A6: 2,223.60 TL of bed days the lines place outside the ICU stay), and contradicts `_infer_billed_icu_days`, which keeps a 14-date claim with a 3-day ICU segment at 3 ICU days.

### Decisions
1. **What an ICU line says.** A billed line of 510090 or of an EK-2/C ICU package (the six codes above; read with `normalize_procedure_code`, so `P552002`, `552.002`, `p510090`; the same set `claim_has_icu_code` accepts, pinned by a test) pays the bed of the days from its date for its quantity in days (at least 1; an unreadable quantity counts one; an undated line sits on the admission date, as for 530000), clipped to the stay; a line dated outside the stay covers only what its quantity runs into. Evidence: 510090 "Yemek, yatak, hasta vizit hizmetlerini kapsar" (the sentence this project already reads as "the bed is paid" for 530000, 510100, 510110, 510070, 510081 and for 510090 on the ICU last day); the ICU packages are EK-2/C points (§2.4.4.H.(2)) and EK-2/C points include "Yatak bedeli" (§2.2.2.B-1.(1).a). A credit line (a reversal) says nothing, a zero-priced line counts (the service is listed), a line of another claim says nothing — exactly the rules of the 530000 / 510100 / 510110 helper.
2. **The days between the first and the last covered day are inside the ICU stay.** §2.4.4.H.(8) puts the first and the exit day on hizmet başı (510090) and (2) the ICU treatment between on the EK-2/C package: a day between two ICU lines of one claim is a package day (whether or not the package is billed — a missing package is an ICU finding, not a bed day), not a ward day. Cost of the reading: a ward interval between two separate ICU stays of ONE claim is read as part of one stay (silence, not a false recoverable). Days with no ICU line on either side stay as they are.
3. **Ward days outside the ICU stay stay expected, as today.** Before the first ICU day (subject to the package window exactly as today: a P-prefixed ICU package bundles the days from admission through its date, which already hides ward days there: E1 d0-d1) and after the last (the claim's discharge day is still dropped by the reconciliation on every ICU-coded claim, the pinned claim-span rule; the other days after the stay stay expected).
4. **One helper, three consumers.** The cause goes into `bed_days_not_expected` (the one place both motors and the ICU reconciliation read), not into the reconciliation alone: the standard-bed motor's own output is right without a post-processing step, the days stay after the package window (never taken twice), and the reconciliation skips the days the helper already took out, so the claim's last day is never subtracted twice. `BED_INCLUDING_CODES` keeps its three codes (its pin test stays); the ICU codes get their own frozen set `ICU_BED_CODES` because they carry a second rule (Decision 2).
5. **Newborn motor.** No change: it leaves any claim that carries an ICU code to the ICU motor (`claim_has_icu_code`), so a newborn ICU claim never reaches the helper from there; its standard-bed row, the only bed number such a claim shows, gets the days out through the same helper (F2, F3, F5, F6). The newborn motor keeps reading the ICU last days of OTHER claims (`icu_last_days`) as before. A test pins that the newborn motor stays silent on every ICU-coded claim.
6. **ICU motor unchanged** (`icu_puani.py` is not edited; its rows are compared byte for byte on every probe and in the differential). Its day model counts nights and expects no package day it does not see billed; the two motors cannot be reconciled by counting, which is why the dates of the lines decide here.
7. **Row shape.** No new key, no `public_contracts.json` change. `bed_days`, `expected_yatak_try` and the money fall; one sentence per cause is appended to `detail`. `icu_overlap_days` / `icu_overlap_dates` keep their meaning "ICU last day taken out by the reconciliation": a claim whose own ICU line covers its last day shows the helper's sentence instead (the day was taken out before the reconciliation looked), and the ward claim after an ICU claim keeps its keys.
8. **What I leave, with the numbers (Found, not fixed below):** the claim-span discharge-day rule (hides a real ward day after the ICU stay: E1 / E3 / E4, 222.36 each), the service→ICU first day across two claims (X1: the ward claim still expects the ICU claim's first day, 222.36), the package window's bundling of the ward days before an ICU package, the audit side (a 510010 billed on an ICU-paid day), department-only ICU claims, the ICU motor's own model.

### Design
- `prose_rules/yatak_puani.py`: public `ICU_DAY_RATE_CODE`, `ICU_BED_CODES`; private `_stay_days_covered(line, admission, discharge)` (the one definition of "the days a line's quantity reaches", now also used by the 530000 / 510100 / 510110 loop, behaviour identical) and `_icu_stay_days(...)`; a fourth cause in `bed_days_not_expected` (dates after the package window, one sentence naming the codes, the stay and the days); docstrings of the module, of `bed_days_not_expected` and of `detect_yatak_puani_opportunities`.
- `prose_rules/yatak_icu_overlap.py`: docstring only (scope note: the claim's own ICU days are the helper's now; the cross-claim first day is still out of scope). No code change: `already_out` already skips what the helper returns.
- Not touched: `icu_puani.py`, `yenidogan_yatak.py` (a sibling branch edits its department words), `claim_*.py`, `billing_actions.py` and the frontend (another branch), contracts, `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`. None of the changed src files is pinned by `data/gazette/sut_coverage_evidence.json` (37 paths checked: no `yatak`, no `icu`).
- Predictions (written before the code; Results compares): STD 0.00 for A1-A5, A7, A8-A10, A12-A17, A19, B1-B3, D1-D5, E1, E2, E5, F1-F3, F5, F6, I1; A6 222.36; E3 444.72; E4 444.72; J1 1,111.80; A11, A18, F4, K1-K6 unchanged; G1 444.72, G3 667.08, X1 667.08 unchanged; ICU rows unchanged everywhere; nothing goes up.

### Subtasks
- [x] 0. Step 0 by content (above); `baseline_before.json` of the 16 showcase reports (sha256 `f09e8a1b…`, equal to the earlier blocks') and `probe_before.*` saved in `~/.cache/bilun-icudays-scratch/`.
- [x] 1. Read the clauses, the annex rows, the ICU motor's day model, both bed motors, the reconciliation and their tests myself (above); the review notes as data.
- [x] 2. Probe all three motors on the same in-memory bills for every billing shape and for four candidate rules (above), before deciding.
- [x] 3. This plan, before any code.
- [ ] 4. Tests first, red: the helper (code set pinned and equal to `claim_has_icu_code`; one line one day; quantity, clip, undated, outside the stay, reversal, zero-priced, other claim, spellings; every package code; the gap between first and last; ward days outside; the package window; one date; union with 530000; degenerate claims; reasons); the standard-bed motor (shapes A/B/D/E/F, netting of billed 510010); the ICU reconciliation (own last day covered or not, keys, ward claim after the ICU claim unchanged, no double subtraction); the pipeline in both scopes (headline = rows, ICU row equals its before value, newborn ICU claims, claims without an ICU code unchanged); the tests that pin the superseded two-stage rows of an ICU claim are rewritten with the reason.
- [ ] 5. Implement the helper cause; docstrings.
- [ ] 6. Probe after = predictions; 16 showcase reports `cmp`-identical; a randomized differential (HEAD export against the tree): claims without an ICU code hash-identical, nothing up, ICU rows identical, headline = rows, bill scope = patient scope.
- [ ] 7. Mutants of every changed branch (sha256 backups, restore with `cp` + `cmp`; a WIP commit first).
- [ ] 8. Gates one after the other: ruff `src/ scripts/`, targeted tests, full pytest (guarded launcher), `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, surfacing inventory `--check`.
- [ ] 9. Independent review (fresh agent, code only, alone), findings fixed or classified.
- [ ] 10. CI-image gate alone on a clone of the committed tip.
- [ ] 11. Results in this block, commits on the branch (no push, no PR), Turkish report.

### Out of Scope
Pushing and the PR (Safa's call); the audit side (a 510010 billed on a day an ICU line pays is over-billing; `detect_yatak_icu_overlap` names only the ICU last day); the service→ICU first day across two claims (X1); the claim-span discharge-day rule; the package window's bundling of ward days before an ICU package; the ICU motor's day model and its rows (nights, no package day it does not see billed, uncapped recoverable on reversed lines: A11 shows 3,713.00 against a 1,485.20 charge); department-only ICU claims without an ICU code (F4: 667.08, "a claim without an ICU code gives byte-identical rows"); the ward days of a newborn ICU claim priced at 510010 instead of 510070 / 510081; two separate ICU stays on one claim; frontend, cache rebuild, staging update; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json`; `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened).

---

## Task: A day-bed action row reads as the day bed in the Revenue view; the dead sentence mapping goes (2026-10-19)

### Goal
The action row of a stay under 24 hours that the standard-bed motor or the newborn bed motor prices at the day bed (510120, SUT §2.2.2.(3)) is titled "Day bed charge (510120)" / "Gündüz yatak ücreti (510120)" in the full action table (Revenue view) and in the compact next-actions panel, not "Standard bed-day charge" / "Standart yatak puanı" or "Newborn bed charge (510070 / 510081)" / "Yenidoğan yatak ücreti (510070 / 510081)". The frontend mapping of the removed advice sentence ("Same-day admission/discharge — consider 510120 (gündüz yatak) instead of 510010 for <24h stays.", key `api.billingProse.yatakSameDay`) and its two strings are gone. No engine number moves; the 16 showcase reports stay byte-identical.

Follow-up of the block "Stays under 24 hours at the day bed (510120) in both bed motors" further down in this file (its "Found, not fixed" items 4 and 5; the independent review's T1 and T3), asked by the session that started this one. Step 0: `DAY_BED_CODE` was not in this worktree (cut from `origin/main` a7a105da); the day-bed work is not on `origin/main` (`git log origin/main | grep -i 'day bed'` finds nothing) and the branch `claude/youthful-lichterman-28b767` (5e2de9d8) was 8 commits ahead and 0 behind, so `git merge --no-edit` was a fast-forward, no conflict.

### Facts measured (2026-10-19; `probe_rows.py` in the session scratchpad, rows as `_serialize_billing_report` writes them; one claim, 10 July 2026)
| Bill | surface | `kind` | `procedure_code` | row amount | title today (EN / TR) |
|---|---|---|---|---|---|
| adult, one date, nothing billed | `yatak_puani` | `yatak_puani_standard_bed` | – | 44.45 | Standard bed-day charge / Standart yatak puanı |
| adult, one date, 510120 billed 20.00 | same | same | – | 24.45 | same |
| newborn, one date, nothing billed | `yenidogan_yatak` | `yenidogan_yatak` | – | 44.45 | Newborn bed charge (510070 / 510081) / Yenidoğan yatak ücreti (510070 / 510081) |
| newborn, one date, 510070 billed 20.00 | same | same | – | 24.45 | same |
| control: adult, 2 dates | `yatak_puani` | `yatak_puani_standard_bed` | – | 444.72 | Standard bed-day charge |
| control: newborn, 2 dates | `yenidogan_yatak` | `yenidogan_yatak` | – | 881.96 | Newborn bed charge (510070 / 510081) |
- **Title path.** `recommendedActionTitle` (`frontend/src/lib/recommendedActions.ts`) builds "kind label: code — name" from `kind`, `procedure_code`, `procedure_name`; a row without a code is titled by its kind label alone (`KIND_LABEL_KEYS`, `messages/en|tr/billing.ts` lines 98 and 102). The full table (`RecommendedActionsPanel`, Revenue view and the audit view) and the compact panel both call it.
- **Where the row's kind comes from.** `collect_billing_actions` (`billing_actions.py`, the uplift loop) sets `kind = row["type"]` and the code from `procedure_code` / `trigger_procedure_code`, which neither bed motor's opportunity has; `bed_code`, `rule_id` and `same_day_stay` stay on the opportunity and never reach the action row. The action row therefore carries no structured field that says "day bed": `message_code` is empty, `sut_section_id` is "2.2.2" on both motors, only the English `detail` starts "Gündüz yatak (510120)".
- **Who reads a bed row's `kind`.** The title (`KIND_LABEL_KEYS`), the chat page context (`sutChatPageContext.ts:91`, passes the string), `engine_proof.ui_signals` (showcase rows only: none is a one-date stay). Nothing in the backend does (`cohort_compliance` reads compliance rows only); the surfacing audit reads the `surface=` keyword of the `_action_row` calls only; `public_contracts.json` lists `kind` and `type` as keys without values. Tests that pin `row["kind"] == opportunity["type"]` (`test_icu_and_newborn_rows.py:109,318`, `test_showcase_fault_rows.py:97,126`) use multi-day and other-motor rows.
- **The dead mapping.** `translateApiText` splits a detail only at " · ", never at sentences, and the engine joins a detail's sentences with a space, so `yatakSameDay` matched only when the sentence was the whole detail; the old detail was "Standart yatak (510010): … Same-day admission/discharge — consider …" (two sentences) and never matched. Referenced only by `apiMessages.ts:338-343`, `messages/en/api.ts:133-134`, `messages/tr/api.ts:134-135` (and prose in this file, plus a negative assertion in `test_yatak_puani.py:377`).
- **Does the UI translate row details?** Only the exact one-sentence shape of a multi-day standard-bed row ("Standart yatak (510010): N billable bed-day(s) (gross LOS G day(s) at R TRY/day) = X TRY (inclusive LOS, discharge day billed).", `api.billingProse.yatakStandard`). Every other detail (any with a second sentence, all newborn ones, the day-bed rows) is shown as the engine wrote it, before and after the day-bed change.

### Decisions
1. **Engine side, in the action-row builder.** A row of surface `yatak_puani` or `yenidogan_yatak` whose opportunity `bed_code` is the day bed (`DAY_BED_CODE`, 510120) gets its own action `kind`, `yatak_puani_day_bed`, the same for both motors (the surface chip still says which motor owns the day). `procedure_code` stays empty (setting 510120 would turn the title into "…: 510120" and highlight a bill line, a feature nobody asked for). The opportunity's `type`, every opportunity key and every number stay as they are, so the public contract, both reconciliations and the motors' tests do not change; the one visible difference is that this action row's `kind` differs from its opportunity's `type`.
2. **Labels.** `kinds.yatakPuaniDayBed`: "Day bed charge (510120)" / "Gündüz yatak ücreti (510120)" (the style of "Companion bed charge (510121)"), mapped in `KIND_LABEL_KEYS`. Rows of cached reports built before this change keep their old kind, and the frontend keeps the old labels for the old kinds (the cache rebuild is the staging update, already item 8 of that block).
3. **Why not the smallest-looking frontend-only fix** (choose the title from the row's `detail`, "starts with Gündüz yatak (510120)"): no structured field exists on the row, so it would be the one title in the app that depends on English engine prose; the repo moved away from that (the §2.2 messages are served by `message_code`, the regex parsers were removed in the Aşama 3 cutover), a reworded `detail` would silently bring the Kuvöz/Kot title back, and an engine test could not pin it (only a frontend test holding a copy of the engine's sentence). Two other options rejected: changing the opportunity's `type` (reverses the reviewed decision "type keeps its meaning" and rewrites the motors' same-day tests for a label) and `procedure_code` 510120 plus a frontend rule on kind + code (both layers change and the title gets a code suffix it does not need).
4. **Dead mapping.** Remove the `if` in `tryTranslateBillingProsePart` and `api.billingProse.yatakSameDay` from `messages/en/api.ts` and `messages/tr/api.ts`. No replacement translation: the UI does not translate the day-bed detail shape (above), and a Turkish day-bed detail would need the structured message contract, not another regex (listed as a follow-up).

### Design
- `billing_actions.py`: constant `DAY_BED_ACTION_KIND = "yatak_puani_day_bed"` and `_BED_SURFACES`; the uplift loop computes `kind` before `_action_row`; `DAY_BED_CODE` imported from `prose_rules.yatak_puani` (already imported by `claim_yatak_newborn_overlap.py` in the same package; `billing_actions.py` is not among the 37 hash-pinned src files).
- `frontend/src/lib/recommendedActions.ts`: `KIND_LABEL_KEYS` entry; `messages/en|tr/billing.ts`: `kinds.yatakPuaniDayBed`.
- `frontend/src/lib/apiMessages.ts`, `messages/en|tr/api.ts`: the dead mapping and its strings.
- Tests (red first): Python in `test_yatak_newborn_overlap.py` (`TestStayUnder24Hours` neighbours: adult and newborn one-date rows are `yatak_puani_day_bed`, partly billed too; two-date rows keep their kinds; the kind is decided per surface and `bed_code`, not by `same_day_stay` alone; money and detail of the row unchanged); vitest in `recommendedActions.test.ts` (kind label in both locales, titles of a day-bed row of each motor in both locales, no Kuvöz/Kot/510070 in them) and `SutBillingReportSections.test.tsx` (the full table and the compact panel render the day-bed title in EN and TR).

### Subtasks
- [x] 0. Step 0 (fast-forward merge of the day-bed branch), read of the day-bed block and the newest lessons; `before.json` (16 showcase reports, sha256 `f09e8a1b…`, equal to the day-bed block's) and `probe_before.json` saved in the session scratchpad.
- [x] 1. Trace the title path and the consumers; this plan (before any code).
- [x] 2. Tests first, red: the four one-date cases of `TestDayBedActionRow` failed (the two-date controls passed), and 6 vitest tests (kind label, title of both rows in both locales, full table and compact panel in EN and TR) failed with the humanized fallback "Yatak Puani Day Bed".
- [x] 3. `billing_actions.py`: `_opportunity_kind` and `_DAY_BED_ACTION_KIND`.
- [x] 4. Frontend: `KIND_LABEL_KEYS` entry, `kinds.yatakPuaniDayBed` in en and tr, the dead mapping and its two strings removed.
- [x] 5. 258 passed in the seven bed / action-row / surfacing-audit Python test files; vitest 112 files, 1,135 tests passed (6 of them new); `tsc --noEmit` exit 0; eslint on the 8 changed frontend files exit 0 (link to `~/.cache/ui-review-code2/frontend/node_modules` in, removed again).
- [x] 6. 12 mutants (6 on `_opportunity_kind` / the constant, 6 on the label map and the two texts), one at a time, restored with `cp` + `cmp`: 12 killed, 0 survived; the one equivalent mutant (decide by `same_day_stay` instead of `bed_code`) is not run, the two flags agree on every row that has money.
- [x] 7. Looked at in the real app (anonymous local demo mode, own ports, a pass-through proxy that swaps in the engine's rows of two in-memory one-date bills): see Results.
- [x] 8. Gates one after the other: showcase dump byte-identical, ruff on `src/ scripts/`, CI-image gate alone on a clone of the committed code tip `d56816c6`.
- [x] 9. Results in this block; commits on this branch (no push, no PR).
- [x] 10. Rebase onto `origin/main` 1a5352b9 (asked by the session that started this one), re-check by hand after #324 / #325, re-run the gates one group at a time (Results, "After the rebase").

### Results (2026-10-19, branch `claude/zealous-snyder-c1aabe`; nothing pushed)
Commits, oldest first, after the rebase below: `556e01da` the day-bed kind in the builder, the labels, the dead mapping removed, tests, this plan · `bf611907` the first results block and a lesson · the final commit (the rebase paragraph and the re-run numbers of this block). Before the rebase they were `d56816c6` and `0aa07f00` on top of the eight commits of `claude/youthful-lichterman-28b767`, whose content is now `origin/main`'s own (#323).

**The rule now.** `collect_billing_actions` gives the action row of an opportunity whose `bed_code` is 510120 the kind `yatak_puani_day_bed`, on both bed motors; every other row keeps its opportunity's `type` as its kind. The frontend maps the kind to "Day bed charge (510120)" / "Gündüz yatak ücreti (510120)". The opportunity (`type`, keys, amounts, detail), the headline and every two-date row are untouched; `procedure_code` stays empty on these rows. The mapping of the removed advice sentence and its two strings (`api.billingProse.yatakSameDay`, en and tr) are gone; no replacement translation (see 1 below).

**Before → after, in the app** (anonymous local demo mode: backend :8741, a pass-through proxy :8742 that puts the engine's rows of two in-memory one-date bills into the patient page, `next dev --webpack` :3741; all stopped again). The rows are what the engine wrote before and after (`probe_before.json` / `probe_after.json` in the session scratchpad): on the six probe bills only the `kind` of the four one-date rows differs; amounts, details, claim ids and headlines are equal.
| Row (one date, 44.45 TL) | Before, EN / TR | After, EN / TR |
|---|---|---|
| standard-bed motor | Standard bed-day charge / Standart yatak puanı | Day bed charge (510120) / Gündüz yatak ücreti (510120) |
| newborn bed motor | Newborn bed charge (510070 / 510081) / Yenidoğan yatak ücreti (510070 / 510081) | Day bed charge (510120) / Gündüz yatak ücreti (510120) |
Seen in both places that call `recommendedActionTitle`: the "Next actions" panel on the patient page and the itemized table of the Revenue tab, in EN and in TR (the surface chips are unchanged: "Bed-day (yatak puanı)" / "Newborn bed (yenidoğan yatağı)", "Yatak puanı" / "Yenidoğan yatağı"). Screenshots: `~/.config/Claude/side-session-notes/local_b23ae239-9cb9-4af3-a9a1-89305a566a00/day-bed-title-screenshots/`. Limits of that check: the proxy swaps `recommended_actions` after the backend's own projection, so the endpoint payload and the public projection of the new kind are tested in Python (`test_the_api_payload_and_its_public_projection_serve_the_day_bed_kind`); the dev server ran on the `node_modules` of `~/.cache/ui-review-code2` (Next 16.3.6, the repo pins 16.3.8).

**Gates (first run, on `d56816c6` before the rebase; the re-run is further down).** Showcase: `baseline.py` dumps of the 16 reports before and after are byte-identical (`cmp`; sha256 `f09e8a1b…`, equal to the day-bed block's). Frontend: vitest 112 files, 1,135 tests passed (6 of them new); `tsc --noEmit` exit 0; eslint on the 8 changed files exit 0. Python: 258 passed in the seven bed / action-row / surfacing-audit test files; ruff on `src/ scripts/` and the changed test file clean. Mutants: 12 (6 on `_opportunity_kind` and the constant, 6 on the label map and the two texts), 12 killed. CI-image gate, alone, on a clone of `d56816c6` (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0): ruff clean, **11,993 passed, 2 skipped, 0 failed** (136 s; the previous gate had 11,985, +8 are the new Python tests), `compile_rules.py --check` 119 artifacts byte-identical, manifest parity 0 issues, no tracked file changed by the run. Left behind in the worktree: nothing (`frontend/.next`, the `AGENTS.md` / `CLAUDE.md` that `next dev` generates, `tsconfig.tsbuildinfo` and the `node_modules` link are removed, `next-env.d.ts` restored; ports 3741, 8741, 8742 free).

**Found, not fixed (measured):**
1. *The note column is English in the Turkish UI.* `translateApiText` translates exact shapes only (the plain multi-day standard-bed sentence, `yatakStandard`); every row note with a second sentence, all newborn and ICU notes and the day-bed notes show the engine's English text, as they did before this change. A Turkish day-bed note needs the structured message route (`message_code`), not another regex.
2. *`api.billingProse.yatakStandardWithSurgery` is dead the same way* (`apiMessages.ts`, `messages/en|tr/api.ts`): it matches "… TRY/day, surgery day D bundled into EK-2/C package) = …", which the engine no longer writes (its window text is "N day(s) bundled into EK-2/C package window (surgery S, window through W)"). Not removed: not asked.
3. *Section cite.* The day-bed rows still cite `sut_section_id` "2.2.2" (the clause that prices the day bed is §2.2.2.(3)), and `clause_ref` is null (no caller sets it for uplift-loop rows), so the "SUT §2.2.2" button of the compact panel is disabled on these rows, as on the ICU and anaesthesia rows.
4. *Cache.* Cached reports keep the old kind until the cache is rebuilt (item 8 of the day-bed block further down); the frontend still labels the old kinds as before.

**Process note.** One search (`grep -rIn … .` from the worktree root, early in the session) also read the folders the brief forbade (`raw data`, the two `ilay` paths); it printed nothing from them, every later search named its directories, and the slip is recorded as a lesson in `tasks/lessons.md`.

**After the rebase onto `origin/main` 1a5352b9** (asked by the session that started this one, 2026-10-19, once Safa had approved the landing order: the day-bed work #323, the audit-exposure detector #324, the exclusions #325, then this change). `git rebase --onto origin/main 5e2de9d8 claude/zealous-snyder-c1aabe` replayed the two commits (`d56816c6` → `556e01da`, `0aa07f00` → `bf611907`). Only `tasks/todo.md` and `tasks/lessons.md` conflicted (every block and every lesson kept, this change's on top; the two "Fixed" marks in the day-bed block now name this block instead of "the block above"); `billing_actions.py`, `recommendedActions.ts` (and its test), `messages/en|tr/billing.ts` and `test_yatak_newborn_overlap.py` merged without a conflict. The branch is 2 commits ahead of `origin/main` and 0 behind; the diff against it is the same 12 files as before.

*Re-check by hand on the rebased tree* (`probe_recheck.py` in the session scratchpad; in-memory bills of 2026-07-10; STD = standard-bed motor, NB = newborn motor):
| Bill | opportunity | action row |
|---|---|---|
| K1 adult, 1 date, nothing billed | STD 510120, 1 day, 44.45 | `yatak_puani_day_bed`, 44.45 |
| K2 newborn, 1 date, nothing billed | NB 510120, 1 day, 44.45 (STD 0 days) | `yatak_puani_day_bed`, 44.45 |
| K3 adult, 510120 billed 20.00 | STD recoverable 24.45 | `yatak_puani_day_bed`, 24.45 |
| K4 newborn, 510070 billed 20.00 | NB recoverable 24.45 | `yatak_puani_day_bed`, 24.45 |
| E1 / E3 adult / newborn, 530000 billed (#325: the day bed is forbidden) | days 0, expected 0 | none |
| H1 / H2 / H3 hemodialysis 704230 / 704210 (adult, adult) and 704230 (newborn) | days 0 | none |
| H4 package P704230; S1 / S2 510100 / 510110 billed (they cover the day) | days 0 | none |
| T1 adult 2 dates; T2 newborn 2 dates; T3 adult 3 dates with 530000 on day 1 (controls) | 510010 / 510070 / 510010 rows | `yatak_puani_standard_bed` / `yenidogan_yatak` / `yatak_puani_standard_bed` (unchanged) |
Every priced one-date row has the new kind (its titles as measured above, in the app and in the vitest render tests, EN and TR); a day that #325 now excludes has no action row at all (zero money makes none), so nothing needs a title there, and the 0-day opportunities keep `bed_code` 510120 and #325's sentences, which only reach rows without an action row. #324's audit-exposure rows are surface `audit_exposure` with their own kind `yatak_newborn_overlap_double_billing` (its own labels sit next to this change's entry in `recommendedActions.ts` and `messages/en|tr/billing.ts`); they do not go through `_opportunity_kind`, which the uplift loop alone calls. The removed mapping is referenced nowhere (a search of `frontend/src src tests scripts` finds only the assertion `"consider 510120" not in opp["detail"]` in `test_yatak_puani.py`) and the engine writes no such sentence.

*Gates, re-run on the rebased tree, one group at a time:* ruff on `src/ scripts/` clean. The 15 bed / action-row / audit-exposure / surfacing-audit Python test files: 1,034 passed (the eight of `TestDayBedActionRow` among them). Full pytest locally (`-n 4`): 12,562 passed, 2 skipped, 0 failed (190 s). `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` 0 issues; `build_rule_surfacing_inventory.py --check` exit 0; no tracked file changed by them. Frontend (the cached `node_modules` linked in, removed again with `tsconfig.tsbuildinfo`): vitest 112 files, 1,137 tests passed; `tsc --noEmit` exit 0; eslint on the 8 changed files exit 0. The 16-report dump (`baseline.py`) of this branch, of an export of `origin/main` itself (`git archive origin/main` with the forbidden folders left out by pathspec, run inside the export) and of the pre-rebase baseline: three byte-identical files (sha256 `f09e8a1b…`). CI-image gate, alone, on a clone of `bf611907` (the rebased code tip; the final commit changes only `tasks/todo.md`): ruff clean, **12,562 passed, 2 skipped, 0 failed** (181 s; 569 more tests than before the rebase, those of #322–#325), `compile_rules.py --check` 119 byte-identical, manifest parity 0 issues, no tracked file changed by the run (208 s in all).

*Not verified:* the staging UI and the deployed cache (cached reports keep the old kind until rebuilt); the browser check was not repeated after the rebase: the frontend lines are the same (auto-merged), the vitest render tests of both panels in EN and TR pass on the rebased tree, and the engine rows above are the rows that check used.

### Out of Scope
Pushing and the PR (Safa's call); a Turkish translation of the day-bed (or any newborn) detail; the cache rebuild and the staging update; the ICU motor's own `same_day_stay`; every other item of the "Found, not fixed" list of that block; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; the files pinned by `data/gazette/sut_coverage_evidence.json` (checked: `billing_actions.py` and the frontend files are not among them); `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened).

---

## Task: Bed motors stop expecting a bed day the SUT says is already paid or may not be billed (2026-10-19)

### Goal
Neither bed motor (standard bed `yatak_puani`, newborn bed `yenidogan_yatak`) shows a recoverable bed day on a day whose bed the claim has already been paid through another EK-2/B code (530000 ER critical bed, 510100 sterile room, 510110 isolated radioactive-treatment room), and neither shows the day bed (510120) of a stay under 24 hours where the SUT forbids billing it (530000 on the claim; hemodialysis 704210 / 704230), and no bed at all on a day case that bills an EK-2/C procedure. A claim that bills none of these codes gives byte-identical rows and totals; the 16 showcase reports stay byte-identical; a false recoverable on a billed dialysis session or ER bed is worse than silence.

Follow-up of the day-bed block below: its independent review found (found-not-fixed item 1) that neither motor knows where the SUT includes or forbids the bed. Brief from the orchestrating session; shared notes `…/side-session-notes/local_843bfa6a-…/same-day-review-notes.md` (cases ER-1, ER-3, dialysis). Step 0: `claude/youthful-lichterman-28b767` (5e2de9d8, not pushed) was not in this worktree (cut from `origin/main` a7a105da: the `grep -c` printed 0 and `DAY_BED_CODE` was absent) and not squash-merged either (`git log origin/main | grep -i 'day bed'` empty, `origin/main` is still a7a105da); `git merge --no-edit` was a fast-forward to 5e2de9d8; the two greps then print 1 and the `DAY_BED_CODE` lines.

### Evidence (read from the files, 2026-10-19)
`data/gazette/sut_clauses.parquet` (in force) and `data/gazette/raw/annex=EK-2B/effective_date=2026-07-07/…parquet`:
- C000648 §2.2.2.(3), MUST_BILL: "24 saatten kısa süreli yatışlarda yatak bedeli, gündüz yatak bedeli üzerinden faturalandırılır."
- C000649 §2.2.2.(4), MUST_NOT_BILL: "Günübirlik tedavilerde SUT eki EK-2/C Listesinde yer alan işlemler için gündüz yatak bedeli faturalandırılamaz."
- C000650 §2.2.2.(5), NO_PAY: "Günübirlik tedavilerde, SUT eki EK-2/B Listesinde yer alan refakatçi bedeli ödenmez." (C001628 §2.6.3.(2) ends: "Günübirlik tedavilerde SUT eki EK-2/B Listesinde yer alan “refakat” kodu faturalandırılamaz.")
- C000492 §2.1.2.B.(1): a day case is a treatment done "yatış ve taburcu işlemi yapılmadan 24 saatlik zaman dilimi içinde"; C000496 §2.1.2.B.ç lists "Hemodiyaliz tedavileri" among them.
- C000969 §2.4.4.D-1.(11), MUST_NOT_BILL: "Hemodiyaliz tedavisi süresince, … seans sırasında gelişen komplikasyonların tedavisinde kullanılan ilaçlar ve gündüz yatak ücreti fiyata dâhil olup ayrıca faturalandırılmayacaktır." (D-1-1, home hemodialysis, has no such sentence.)
- EK-2/B 530000 "Acil serviste kritik hasta yatak ve takibi" (577.4538 puan): "Acil tıp uzman hekimi tarafından acil hal kapsamındaki hastalarda yapılması halinde günde 1 defa faturalandırılır. Yatak, yemek, hasta vizit hizmetlerini kapsar. 510120, 530003 ile birlikte faturalandırılmaz."
- EK-2/B 510100 "Steril oda" (1674.76 puan): "Yemek, yatak, hasta vizit hizmetlerini kapsar. İki haftayı geçmesi beklenen mutlak nötropenik hastalar için faturalandırılır." 510110 "İzole radyoaktif tedavi odası" (749.84 puan): "Yemek, yatak, hasta vizit hizmetlerini kapsar. İzole radyoaktif tedavi hizmeti Türkiye Atom Enerjisi Kurumu tarafından lisanslandırılmış odalarda sunulur." The same sentence the project already reads as "the bed is paid" for 510090 (`yatak_icu_overlap`) and for 510070 / 510081 (`claim_yatak_newborn_overlap`).
- EK-2/B 510120 "Gündüz yatak tarifesi" (74.96 puan): "Günübirlik tedaviler, 24 saatten kısa süren yatarak tedaviler, acil müşahade için faturalandırılır. Yemek hizmetleri dahildir." 704210 "Acil hemodiyaliz" / 704230 "Hemodiyaliz" (4342.4775 puan each): "SUT'un 2.4.4.D-1 maddesine bakınız." and "sadece yatarak tedavilerde" for 704210.
- The texts of 530000 (from the 2024-05-11 list), 510100, 510110, 704210 and 704230 are the same in every list version back to 2020-03-11 (read all `annex=EK-2B` partitions): the code sets need no date.
- EK-2/C lists P704210 / P704230 / P704233 with no işlem grubu (`get_ek2c_entry(...)["group"] == ""`): billed as a package they open a one-day window (already 0 days, probe H4), billed itemised (704210 / 704230, EK-2/B) they open none and are not mandated (`mandated_package_lines` needs a group A1–E): that is the gap.
- The synthetic data already treats these as beds: `scripts/synthetic/cohort/compose.py:32` `_BED_CODES` has 530000, and `code_sets.yaml` notes "not with 510120 or 530003".
- Claim types in the committed claim table: `yatis`, `acil` only. `claim_is_day_case` knows `gunubirlik` / `day_case`; `infer_care_setting` reads `gunubirlik` as outpatient (both motors skip it) but `day_case` and `gunubirlik yatis` as inpatient.

### Measured before (in-memory bills, tip 5e2de9d8; `probe_excl.py` / `probe_extra.py` in `~/.cache/bilun-bedexcl-scratch/`, outputs `probe_before.txt|json`; amounts TL; STD = standard-bed row, NB = newborn row; one date 2026-07-10 unless "3 days" = 07-10..07-12; headline = `sgk_uplift_try`)
| # | Bill | before |
|---|---|---|
| K1 / K2 | adult / newborn, one date, nothing billed (control) | STD 44.45 / NB 44.45 |
| E1 | adult one date, 530000 billed | STD **44.45** (the day bed beside 530000) |
| E3 | newborn one date, 530000 billed | NB **44.45** |
| E2 | adult one date, 530000 + 510120 billed | 0.00 (netted by the billed day bed; the pair is itself forbidden) |
| H1 / H2 / H3 | one date, 704230 / 704210 / newborn 704230 billed | STD **44.45** / **44.45** / NB **44.45** |
| H4 | one date, P704230 billed as a package | 0.00 (one-day window, already right) |
| H11 | 3 days, 704230 on day 2 | STD 667.08 (3 × 222.36: stays, see Decision 4) |
| M1 / M2 / M3 | 3 days, 530000 on day 1 / day 2 / qty 2 from day 1 | STD **667.08** each (3 days; 1, 1 or 2 are paid by 530000) |
| M4 | 3 days, 530000 day 1 + 510010 billed on days 2–3 (444.72) | STD rec **222.36** |
| N1 / N2 | newborn 3 days, 530000 day 1 / + 510070 billed days 2–3 | NB **1,322.94** / rec **440.98** |
| S1 / S2 / S3 | 3 days, 510100 × 3 / 510110 × 3 / 510100 day 1 billed | STD **667.08** each (the special room is billed daily) |
| Q2 | `day_case` one date, 702580 (HBO, EK-2/C, no group) billed itemised | STD **44.45** |
| controls | 3 days nothing billed STD 667.08; newborn 3 days NB 1,322.94; 530000 credit line only, 530003 only, 704231 / 704290 / 704233: unchanged | |

Not in the brief but measured on the way: a 3-day ICU-coded claim (510090 × 3 billed) shows a standard-bed row of 2 days = 444.72 beside an ICU row of 0.00 (S5) — the ICU motor's own day model (first and last day at 510090, packages between, ward days possible); not touched, listed below.

### Decisions
1. **What a line says.** Only lines of the claim itself, with a non-credit amount (≥ 0.00); a credit line (a reversal) states nothing about the stay's bed, exactly as the newborn motor reads a credit bed line. Codes are read with `normalize_procedure_code` (spaces, dots, hyphens, leading P). One helper, `bed_days_not_expected(claim, claim_procs, window)` in `yatak_puani.py`, returns the days of the stay (after any package window) on which no bed is expected, with one sentence per cause; both motors and the ICU reconciliation use it, so they cannot disagree.
2. **Bed-including codes (530000, 510100, 510110): the days they cover.** A line pays the bed of the days from its date for `quantity` days (at least 1), clipped to the stay and to the days after the package window; an undated line sits on the admission date (as `_package_window_end` places an undated package line); a line dated outside the stay covers nothing; two lines on one day cover it once. This is the project's rule for 510090 on the ICU transfer day and for 510070 / 510081, applied to the same EK-2/B sentence. Nothing says 510010 may not be billed beside them, so a billed 510010 on such a day is not called a violation here (audit matter); it is simply not expected.
3. **The day bed of a stay under 24 hours (one date) is not billable** when the claim bills (a) 530000 on any date — "510120, 530003 ile birlikte faturalandırılmaz" is a claim-level exclusion, so date and quantity do not matter; (b) hemodialysis 704210 or 704230 (C000969, the bed fee is in the price). The one day is taken out: days 0, expected 0, the row stays with its sentence (as for a package window), so a billed 510120 beside them leaves nothing to recover and is not a recoverable.
3a. **A day case that bills an EK-2/C-listed procedure has no bed on any date** (`claim_is_day_case`, C000649; revised after the independent review, planned as "one date only"). A day case is "yatış ve taburcu işlemi yapılmadan 24 saatlik zaman dilimi içinde" (C000492): it may cross midnight, so it may span two dates, and it has no ward bed; its only bed is the day bed, which C000649 forbids for EK-2/C procedures. Every day of such a claim after any package window is taken out, whatever its dates. A day case without an EK-2/C procedure is untouched.
4. **Multi-day stays.** Hemodialysis takes nothing out: C000969 speaks of the *day bed*, which a stay of two dates does not bill, and says nothing of 510010. Only Decision 2 (and 3a for a day case) applies. (Reading "gündüz yatak ücreti fiyata dâhil" as "the ward bed too" would be inventing a rule.)
5. **Hemodialysis codes.** 704210 and 704230 (and their P-package spelling). Not 704233 (home hemodialysis, §2.4.4.D-1-1: no bed to include), not 704231 (catheter placement), not 704290 (continuous hemodiafiltration, not "Hemodiyaliz tedavisi" of D-1.(11)).
6. **Interplay, never subtracted twice.** The package window takes its days first (the helper looks only at days after it); an ICU transfer day that a bed-including line also covers is subtracted once (the reconciliation in `yatak_icu_overlap.reconcile_yatak_bed_days` and the newborn motor skip the days the helper already took out). `bundled_days` / `surgery_day_bundled` keep meaning the package window only.
7. **Row shape.** No new key, no `public_contracts.json` change; `bed_days` / `days` and the money fall, one sentence per cause is appended to `detail`. A one-date row with days 0 keeps `same_day_stay` as before (the standard row: true; the newborn row: false, as with a package window).
8. **Companion-bed motor unchanged.** No text above excludes 510121 (its own EK-2/B line is the companion's bed: "Yemek ve yatak hizmetlerini kapsar"); the motor already suppresses every stay of one date and every EK-2/C package (C000650, C001628).
9. **Why not 510090 / the ICU claim's own days** (corrected after the review): not because it would move the ICU motor's rows (the review put 510090 into the set in its own clone: no ICU row moved on 68 bills, only standard-bed rows fell), but because six tests in `test_yatak_icu_overlap.py` pin today's ICU-claim rows and `yatak_icu_overlap.py` calls the ICU first day "intentionally not in scope": the ICU owner decides (found, not fixed 1, below).

### Design
- `prose_rules/yatak_puani.py`: public `BED_INCLUDING_CODES`, `HEMODIALYSIS_CODES`, frozen `BedNotExpected(dates, reasons)` and `bed_days_not_expected` (plus `_units`: an unreadable quantity counts one day); the detector subtracts `len(dates)` from the days after the package window and appends the reasons to `detail`.
- `prose_rules/yenidogan_yatak.py`: the same helper after the ICU transfer day (`dates − icu_overlap_dates`), before `standard_bed_days`; reasons appended to `detail`.
- `prose_rules/yatak_icu_overlap.py`: `reconcile_yatak_bed_days` skips ICU days the helper already took out.
- No change: `claim_yatak_*`, `claim_yatak_newborn_overlap` (the newborn days it removes already exclude the paid days), `refakatci.py`, `icu_puani.py`, frontend, contracts. None of the three files is pinned by `data/gazette/sut_coverage_evidence.json` (37 paths checked).
- Tests: see the subtasks; mutants of every changed branch; an independent review (code only) afterwards.

### Subtasks
- [x] 0. Step 0 (fast-forward merge above); `baseline_before.json` of the 16 reports (sha256 f09e8a1b…, the same as the day-bed block's) and `probe_before.*` saved in `~/.cache/bilun-bedexcl-scratch/`.
- [x] 1. Read the clauses and the annex rows myself (above); the other EK-2/B bed-like rows (510100, 510110, sleep-lab heading) and the ICU day model.
- [x] 2. Probe both motors on the same bills for every condition (table above) before deciding.
- [x] 3. Write this plan before any code.
- [x] 4. Tests first, red: standard-bed motor (each code and each cause; credit / zero / undated / outside-the-stay / spelled lines; quantity; package window; one-date + package; billed netting; multi-day dialysis unchanged; C000649 for `day_case` and not for `yatis` / `gunubirlik` / no EK-2/C line); newborn motor (same, plus Kot / Kuvöz split, `standard_bed_days`, stand-down, ICU transfer day); ICU reconciliation; pipeline (both motors on the same bills, headline = rows, no day in both rows, bill scope = patient scope, every claim without these lines unchanged).
- [x] 5. Implement helper, standard-bed motor, newborn motor, reconciliation.
- [x] 6. Probe after = targets; 16 showcase reports `cmp`-identical to `baseline_before.json`.
- [x] 7. Mutants of the changed branches (sha256 backups, restore with `cp` + `cmp`).
- [x] 8. Gates one after the other: ruff `src/ scripts/`, targeted tests, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, surfacing audit `--check`.
- [x] 9. Independent review (fresh agent, code only, alone), findings fixed or classified.
- [x] 10. CI-image gate alone on a clone of the committed tip.
- [x] 11. Results in this block, commits on the branch (no push, no PR), Turkish report.

### Results (2026-10-19, branch `claude/angry-banach-5b5bc0`; nothing pushed)
Commits, oldest first: fast-forward to `5e2de9d8` (the day-bed work, Step 0; not a commit of this branch) · `1673a3c8` plan, helper, both motors, reconciliation, tests · `d1565117` the independent review's changes (day case, unreadable quantity; also the lesson) · the results commit (the tip; it only adds this block).

**The rule now** (evidence and decisions above): a line of 530000, 510100 or 510110 pays the bed of the days from its date for its quantity, clipped to the stay and to the days after the package window (undated: the admission date; a reversal, a line of another claim and a line the quantity does not carry into the stay say nothing; a zero-priced line counts), and those days are no bed days to expect, in the standard-bed motor and in the newborn motor; a stay of one date expects no day bed when the claim bills 530000 (any date) or hemodialysis 704210 / 704230; a day case that bills an EK-2/C-listed procedure expects no bed on any date. One helper, `bed_days_not_expected`, serves both motors and the ICU reconciliation, so a day is never taken out twice (package window, ICU transfer day, ER day). No new row key, no contract change; one sentence per cause in `detail`. A claim that bills none of these lines gives byte-identical rows.

**Before → after** (in-memory bills, 2026-07-10, standard-bed row = STD, newborn row = NB, amounts TL recoverable; `probe_excl.py` / `probe_extra.py` in `~/.cache/bilun-bedexcl-scratch/`, outputs `probe_before|after2.txt|json`):
| Bill | before | after |
|---|---|---|
| E1 adult one date, 530000 billed | STD 44.45 | 0.00 |
| E3 newborn one date, 530000 billed | NB 44.45 | 0.00 |
| E7 / E8 / E9 530000 dated the day before / undated / spelled "530.000" | 44.45 | 0.00 |
| H1 / H2 / H3 one date, 704230 / 704210 / newborn 704230 | 44.45 | 0.00 |
| E2 / H8 one date, 530000 or 704230 with 510120 billed | 0.00 (expected 44.45) | 0.00 (expected 0.00) |
| E5 / H6 reversed line only; E10 530003 only; H5 704233; K8 704290; H4 P704230 package | 44.45 / 44.45 / 44.45 / 44.45 / 44.45 / 0.00 | unchanged |
| H11 3 days, 704230 on day 2 | 667.08 | 667.08 |
| M1 / M2 / M6 3 days, 530000 on day 1 / day 2 / undated | 667.08 | 444.72 |
| M3 530000 for two days | 667.08 | 222.36 |
| M8 530000 on every day | 667.08 | 0.00 |
| M4 530000 + 510010 billed on the other two days (444.72) | 222.36 | 0.00 |
| M5 / M7 reversed / dated before the admission | 667.08 | 667.08 |
| N1 newborn 3 days, 530000 on day 1 | NB 1,322.94 | 881.96 |
| N2 / N3 same, incubator / standard bed billed on the other days | 440.98 / STD 222.36 | 0.00 / 0.00 |
| S1 / S2 3 days, 510100 / 510110 billed every day | STD 667.08 | 0.00 |
| S3 510100 billed on day 1 only | 667.08 | 444.72 |
| Q2 `day_case` one date, hyperbaric oxygen (702580) | 44.45 | 0.00 |
| Q4 `day_case` two dates, 702580 | 444.72 | 0.00 |
| Q2 / Q8 the same bill on a `yatis` claim | 44.45 | 44.45 |
| W3 12 days, group-B package, 530000 on the one day after its window | 222.36 | 0.00 |
| I1 ICU transfer day that 530000 also covers (ward claim 3 days) | 444.72 | 444.72 (taken out once) |
| I2 530000 on a ward day, not the transfer day | 444.72 | 222.36 |
| X2 two one-date claims, one with dialysis | 88.90 | 44.45 |
Of 94 bills 48 changed and 46 did not (controls K1–K8, the package windows, X1, S5, …); on none did any bed money or the headline go up; the bed rows over all 94 bills sum to 23,068.57 before and 12,866.63 after.

**Showcase:** `baseline.py` dumps of the 16 reports are byte-identical before and after (sha256 `f09e8a1b…`, the same as the day-bed block) at both code commits.
**Gates (code tip `d1565117`; the results commit only adds this block):** local: ruff on `src/ scripts/` clean; the six bed test files 484 passed (246 before, 238 new); full pytest `-n 4` 12,222 passed / 2 skipped / 1 failed (the known local-only pandas 2.3.3 test `test_curated_catalog_idempotence`); `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` 0 issues; `build_rule_surfacing_inventory.py --check` exit 0. CI-image gate, alone, on a clone of the tip (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0): ruff clean, **12,223 passed, 2 skipped, 0 failed** (111 s), compile_rules 119 byte-identical, parity 0 issues, no tracked file changed by the run (131 s in all).
**My mutants:** 56 hand mutants of the changed branches (guards, package window, reversal / zero / other-claim filters, code reading, quantity floor and clip, off-by-one, code sets, the three one-date causes, the day-case span, both call sites and the ICU reconciliation): 56 killed, 0 survive. Two were first reported as survivors: a window argument the ICU reconciliation already filters by (deleted from the code, not listed) and an order-sensitive one (the subtraction before the standard-bed days), now killed by `test_standard_bed_units_beyond_the_days_left_take_only_the_free_days`. Red first: 84 failed and 1 import error before the code; the 14 tests added after the review fail on `1673a3c8` and pass now.
**Independent review** (fresh agent, own clones, code only; notes `bed-exclusions-review-notes.md` in the shared notes folder): differential base against tip, patient scope and single-bill slice: 1,500 random bills without any of the lines → 3,466 reports hash-identical; 4,500 bills with them → 10,767 reports, 4,908 changed, none broke an invariant (money never up, never negative, headline = rows, day ownership exact against an independent oracle for package window / ICU day / ER day, bill scope = patient scope); 44 reviewer mutants, 40 killed, 4 equivalent. SUT read: §2.2.2.(1)–(5), §2.1.2.B, §2.4.4.D-1.(11), F-2.(9), R.(5), H, §1.9.1.(6), §1.9.4 and every in-force clause with yatak / gündüz / günübirlik / yemek, and every EK-2/B row with "dahil" or "kapsar" in all versions 2020–2026. Verdict: no defect in the change's own logic; its findings 1–4 are misses already there, 5 and 6 were mine.
**What the review changed:** (1) its finding 3: a day case that bills an EK-2/C procedure has no bed on any date (Decision 3a; the plan had it for one date only); (2) its finding 5: a NaN or infinite quantity on a bed-including line raised and lost the whole report, it counts one day now; (3) its finding 6: the helper docstring says a line dated outside the stay covers the days its quantity runs into (a 530000 dated the day before the admission with quantity 3 covers two stay days, the safe side).
**Corrections to what I said earlier:** (a) the plan said the sleep-laboratory sentence is "in force from 2026-09-05": it is on the heading "Laboratuvarda Yapılan Uyku Araştırmaları" in every EK-2/B list since 2020-03-11, only the sub-heading wording was amended in 2026; (b) Decision 9 said that changing 510090 "would move the ICU rows": it moves no ICU row, see found-not-fixed 1; (c) Decision 4 (a day case of several dates keeps its beds) is reversed for a day case with an EK-2/C procedure.

**Found, not fixed (measured; inherited unless stated):**
1. *ICU days on the ICU claim itself (the most money).* EK-2/B 510090 "Yemek, yatak, hasta vizit hizmetlerini kapsar" and the EK-2/C ICU packages pay every ICU day, but only the ICU claim's last day is taken out of its standard-bed row: a 3-day claim billing 510090 × 3 shows 444.72 (two days) beside an ICU row of 0.00 (S5); a 2-day ICU claim (510090 on both days, the model's own billing) shows 222.36 for its first day (I1). The review's one-line experiment (510090 into `BED_INCLUDING_CODES`) moved no ICU row on 68 bills; the standard-bed rows fell to 0 and six tests in `test_yatak_icu_overlap.py` that pin today's rows fail. `yatak_icu_overlap.py` calls the ICU first day "intentionally not in scope": the ICU owner decides.
2. *Sleep-laboratory studies* (702820 …; the heading says "Yatak ücreti, EEG, EOG, EMG, EKG dahildir. Tüm gece laboratuvarda"): a two-date inpatient claim billing 702880 shows 444.72, one date 44.45; the text is on a heading row and names no code, and which of the two dates the night belongs to is not in it.
3. *`Günübirlik` with ü* is read as inpatient and not as a day case (`claim_is_day_case` / `infer_care_setting` compare "gunubirlik" in a case-folded, not ASCII-folded, claim type): a one-date claim of that type with an EK-2/C procedure still shows 44.45. Whether real data spells it that way is unknown.
4. *A day case of several dates without an EK-2/C procedure* still shows 2 × 510010 although its only bed is the day bed (one 44.45): untouched on purpose, no line of this change.
5. *Audit side:* a 510120 / 510010 line billed beside 530000, hemodialysis or a special room is over-billing; the rows now show expected 0.00 and the billed money, but no detector names it (like `yatak_icu_overlap` for the ICU day).
6. *Decisions that leave a number:* a reversed 530000 or dialysis line says nothing, so the day bed stays expected (44.45); other claims of the patient on the same date are not read (X1: an ER visit billed as a `poliklinik` claim takes no day of the ward claim); a quantity-1 line that carries several days' amount covers one day; a same-date `acil` claim with dates is read as inpatient (44.45, base = tip).
7. Cosmetic: when the ER day is also the ICU transfer day the newborn row names that date in both sentences and subtracts it once.
8. Still open from the day-bed block: a zero-amount newborn line beside 510120, spelled 510010, the row titles (the sibling branch `claude/zealous-snyder-c1aabe` gives 510120 rows their own kind), cache rebuild.

### Out of Scope
Pushing and the PR (Safa's call); the audit-exposure side (a 510120 / 510010 line billed beside 530000, dialysis or a special room is over-billing, a detector like `yatak_icu_overlap`); other claims of the same patient on the same date (the exclusions are read per claim, as "birlikte" and "fiyata dâhil" speak of one bill); 510090 and the ICU claim's ward days (S5: 444.72 standard-bed beside ICU 0.00); the sleep-laboratory heading ("Yatak ücreti, EEG, EOG, EMG, EKG dahildir. Tüm gece laboratuvarda", on a heading row in every EK-2/B list since 2020-03-11, attached to no code: the codes would be inferred from the layout); home hemodialysis, catheter placement and hemodiafiltration (above); the `Günübirlik` spelling with ü, which `claim_is_day_case` does not recognise; a quantity-1 line that carries several days' amount (read as one day, as in the newborn motor); the `care_setting_review` surface; cache rebuild and staging update; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json`; `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened).

---

## Task: Audit-exposure detector for a standard bed (510010) billed on a day a newborn bed (510070 Kuvöz / 510081 Kot) covers (2026-10-18)

### Goal
A 510010 line billed on a day that a Kuvöz (510070) or Kot (510081) line of the same patient also covers is flagged as double-billing risk: a detector in `analyze_claim` beside `detect_yatak_icu_overlap`, and `audit_exposure` action rows (Compliance view) whose `risk_amount_try` also enters `audit_exposure_try`. No number on the 16 showcase reports moves (dump before/after byte-identical).

Follow-up of the "Newborn bed motor" block below (decision 3; "found, not fixed" point 4). Safa answered the one question of the brief on 2026-10-18: *"Aynı gün hem standart yatak (510010) hem kuvöz/kot (510070/510081) faturalanmışsa bunu çift fatura riski olarak işaretleyelim mi?"* — **Evet**. Branch `claude/charming-austin-b8d3d5`, cut from `origin/main` 7ea9457a (squash #319). Not pushed.

Step 0: the brief expected the newborn bed work to be missing. It is in main: #319 is the squash of the newborn branch, `git diff HEAD claude/funny-tereshkova-662936` is empty and both trees are `eb2068ec`. The brief's check `git log | grep "review round 3"` finds nothing only because the squash dropped the commit titles. No merge was made (it would add 18 commits of history for zero content). Baseline: the 16 reports dumped before any change, `~/.cache/bilun-bedpair-scratch/before.json` (sha256 f09e8a1b…, identical to the previous session's final dump `after7.json`).

### Evidence (read from the files)
- `data/gazette/raw/annex=EK-2B/effective_date=2026-07-07/` (re-read this session): 510010 (374.97 puan), 510070 (743.65), 510081 (524.95) and 510090 (1252.27) start with the same sentence, "Yemek, yatak, hasta vizit hizmetlerini kapsar."; 510070 adds "510081 ile birlikte faturalandırılmaz. Günde bir adet faturalandırılır."; 510081 adds "510070 ile birlikte faturalandırılmaz. Anne yanında izlenen bebekler için faturalandırılmaz."
- No text says "510010 ile birlikte faturalandırılmaz" for 510070 or 510081. That 510010 cannot be billed on a day of a newborn bed is an **inference** from the identical "kapsar" text: the one `prose_rules/yatak_icu_overlap.py` applies to 510090 against 510010, and the newborn bed motor applies (decision 3 below). So the detail says *risk*, quotes EK-2B, the severity is `warning` (the ICU sibling is `error`) and the basis is `heuristic`, not `sourced` (the exclusion is not in the SUT text; review F4).
- Explicit in the text, not part of this task: 510070 and 510081 on one day ("birlikte faturalandırılmaz"). A separate, smaller detector; listed under Out of Scope.

### What the ICU sibling really does (read, not assumed — the brief assumed more)
- `detect_yatak_icu_overlap` is one of the 18 focused Wave A groups. The patient report reaches it through `FocusedLegacyMaterializer.all_rows()` → `project_focused_legacy_rows` → `financial_findings` (confirmed amount None; the surfacing matrix row says `hidden_runtime`, "the current API draft gate hides it"). It is **not** an `audit_exposure` row.
- `analyze_claim` is not called for a patient context by the report or by any route: `rule_engine.validate_claim` builds `patient_id=""` contexts and the El Kitabı block (steps 13+) is gated on a patient id. The matrix says of every direct `analyze_claim` call: "the flat analyze_claim result is not projected into BillingActionReport".
- The visible `audit_exposure` rows come only from `recommend_audit_exposure_from_claims` (unbundling findings: session factor, blood component, bundled line; payment-method money counts in the total and has no row).
- So wiring in `analyze_claim` alone would be invisible to the user. The detector is therefore (a) called in `analyze_claim` step 14.6b beside the ICU one, as the brief asks, as a **direct call, not a 19th focused group** (the focused inventory is hard-pinned at 18 groups / 32 ids by an import-time `RuntimeError` in `focused_rule_projection.py` and `focused_legacy_materializer.py` and by `tests/unit/scripts/test_rule_surfacing_inventory.py`; `sut/rule_registry.py` is hash-pinned by `sut_coverage_evidence.json`; `tests/unit/deploy/**` references the ICU group and is off limits), and (b) re-run by `recommend_audit_exposure_from_claims`, which makes the rows and adds their money to `audit_exposure_try`: one function, one number for both places.

### Decisions
1. **Predicate.** A newborn bed line is code 510070 / 510081 (`normalize_procedure_code`: `p` prefix, dots, spaces, hyphens), a standard-bed line is 510010; both need a positive billed amount. A line dated d with quantity n (at least 1) covers the days d … d+n−1: the repo's own bed lines are one line per day, quantity 1, and MEDULA `adet` is the day count. The newborn motor reads quantity as a day count too, but only as a *count* (`standard_bed_days` sums quantities and ignores dates); the detector also places the days from the line's date. The same model for both sides; nothing is guessed beyond it. A finding that rests on a quantity above 1 says so in its detail ("tarih + adet varsayımı"), because the two readings can disagree on aggregated lines (Found, not fixed, point 1). A 510010 line is flagged when its days meet the days of a newborn bed line of the **same patient**, on any claim of the patient's history, and is emitted only for the claims of the active context (the ICU detector's scope: `ctx.history` + `claim_ids_with_procs`). A reversed line (negative amount) covers no day and asks no money; a 0-TL line asks no second charge: both are ignored on both sides (the ICU detector skips non-positive 510010 lines too).
2. **One violation per flagged 510010 line**, with `overlap_days`, the overlap as date ranges, and the covering newborn lines (ids, claim ids, codes). Interval arithmetic, not day sets, so a huge quantity cannot blow up memory; a line's days are capped at 3,660 (ten years) so garbage data cannot overflow `date`. Lines without a date are skipped.
3. **Amount** = billed amount × overlapping days ÷ covered days, round half up: the money of exactly the doubled days. With one line per day that is the whole line, as in the ICU detector. In the report the combined exposure of one line, identified by its `(claim_id, line id)` pair, (unbundling risk + this) is capped at its billed amount, so a line that is also a package-included line is not counted twice.
4. **Rows:** surface `audit_exposure` (Compliance view, finding type compliance), kind `yatak_newborn_overlap_double_billing` (== the violation `type`), the same nine row keys as the other audit rows (so no `public_contracts.json` change), `sut_section` 2.2.2. `audit_exposure_try` = unbundling total + these rows; `compute_audit_exposure_from_claims` likewise. No uplift, no `sgk_uplift_try`.
5. **Which side is flagged:** the standard-bed line, as the brief says. Whether the newborn line is the extra one is not decided (the claim does not say which bed the baby lay in).
6. **Code style:** per-line dataclass objects, not a DataFrame (the neighbouring detectors take `list[ProcedureClaimLine]`), so AGENTS.md §9's Polars rule is not in play; interval math keeps it O(lines × newborn lines of one patient).

### Design
- New `src/bilun/domain/prose_rules/yatak_newborn_overlap.py`: `detect_yatak_newborn_overlap(procedure_lines, *, claim_ids_with_procs=None)`; violation keys as the ICU one plus `overlap_days`, `overlap_ranges`, `newborn_bed_codes`, `newborn_claim_id`, `newborn_line_ids`, `billed_amount_try`; `severity` warning, `savings_category` audit_exposure, `savings_basis` heuristic, `sut_section_id` 2.2.2.
- `billing/engine.py`: module-level import (so the surfacing audit sees the call) and the call in step 14.6b, history lines + the active claims.
- `billing/claim_audit_exposure.py`: rows and total from the detector, capped per line; comments in `types.py`, `patient_report.py`, `claim_yatak_newborn_overlap.py` (the "separate detector" sentence now names it).
- `scripts/audits/rule_surfacing/metadata.py` (`EXPECTED_ANALYZE_CALLS`, `EMISSION_OVERRIDES` of `recommend_audit_exposure_from_claims`), then `python scripts/audits/build_rule_surfacing_inventory.py --write`.
- Frontend (a delegated agent, `frontend/**` only): kind label EN/TR in `recommendedActions.ts` and `messages/{en,tr}/billing.ts`, vitest, tsc, eslint.
- Touchpoints of the seven that do **not** apply: `types.py` field (none), `public_contracts.json` (no new key), the `_finding_type` sets (`audit_exposure` is already compliance), showcase proof JSON (no showcase number moves). Each is checked, not assumed (contract projection test, action-row test, 16-report dump).
- Tests first, red: detector (exact pair, Kot, different days, quantity, 510010 beside 510090, reversed, zero, cross-claim, other patient, code spellings, huge quantity), `analyze_claim` wiring and gates, rows / total / action rows, patient vs bill scope, the per-line cap, no change on a bill without the pair.

### Subtasks
- [x] 0. Step 0 (newborn work is in main, no merge), baseline dump of the 16 reports, EK-2/B text re-read.
- [x] 1. Read AGENTS.md, lessons, the ICU detector and its wiring, the surfacing audit, the audit-exposure rows (what the ICU sibling really does is above).
- [x] 2. Safa's yes/no: Evet.
- [x] 3. This plan, before any code.
- [x] 4. Frontend agent launched with the fixed kind name and labels.
- [x] 5. Tests first (red).
- [x] 6. `yatak_newborn_overlap.py`; `engine.py` call; `claim_audit_exposure.py` rows and total; comments.
- [x] 7. Surfacing metadata and `build_rule_surfacing_inventory.py --write`.
- [x] 8. Targeted tests green; dump the 16 reports again and compare with `before.json` (byte-identical).
- [x] 9. Own mutation loop (backup copy + `cmp`, never `git checkout --`).
- [x] 10. WIP commit; independent review (fresh agent, own clone, random-bill harness with a brute-force oracle, hand mutants); triage.
- [x] 11. Gates one after the other: ruff on `src/ scripts/`, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, `build_rule_surfacing_inventory.py --check`, CI-image gate on a clone of the committed tip.
- [x] 12. Results here, lessons, one commit on the branch (no push), Turkish report to Safa.

### Results (2026-10-18/19, branch `claude/charming-austin-b8d3d5`, one commit on top of `origin/main` a7a105da; nothing pushed)
The work was cut at 22:11 by an OOM kill of the Claude app (reported by the orchestrating session: systemd-oomd while three sessions ran gates at once); it resumed from a WIP checkpoint (`ffc8e602`), merged `origin/main` (#320, #321; one conflict, `tasks/todo.md`, where every PR adds a block at the top: all blocks kept; AGENTS.md and `agents/` are gone with #321, as intended) and was then squashed into this one commit (tree identical to the last checkpoint `11fdb592` plus this block).

**What it does now.** A 510010 line with a positive amount whose days (date, quantity − 1 days after it) meet the days of a positive 510070 / 510081 line of the same patient (any claim of the patient's history) is flagged once: `detect_yatak_newborn_overlap` (new, `prose_rules/yatak_newborn_overlap.py`) is called in `analyze_claim` step 14.6b (patient history, active claims only, gated like the ICU detector) and re-run by `recommend_audit_exposure_from_claims`, which makes one `audit_exposure` row per flagged line (kind `yatak_newborn_overlap_double_billing`, Compliance view, the same nine row keys as the other audit rows) and adds its money to `audit_exposure_try`. The money is the line's billed amount × shared days ÷ its days (round half up); the combined exposure of one `(claim_id, line id)` is capped at what it billed. Severity `warning`, basis `heuristic` (the exclusion is an inference from EK-2/B's identical text, not a sentence of the SUT). Reversed and 0-TL lines are ignored; 510010 beside 510090 is the ICU detector's business.

**Before → after** (in-memory bills, Z38.0 stay of 3 days from 2026-07-10; `audit_exposure_try` of the report; before, the report had no source for this finding):
| Bill | before → after |
|---|---|
| Kuvöz 440.98 and 510010 222.36 on 07-10 | 0.00 → 222.36, one row |
| same with Kot 311.30 instead of Kuvöz | 0.00 → 222.36, one row |
| Kuvöz on 07-10, 510010 on 07-11 | 0.00 → 0.00 |
| 510010 beside 510090 (ICU claim, same day) | 0.00 → 0.00 (the ICU detector's business) |
| 510010 reversed (−222.36) or 0.00 beside Kuvöz | 0.00 → 0.00 |
| 510010 × 3 (667.08) over a Kuvöz on its middle day | 0.00 → 222.36 (one of three days) |
| a 510010 line that already carries 60.00 of unbundling risk, beside Kuvöz | 60.00 → 222.36 (60.00 + 162.36: the line billed 222.36) |
| claim A bills Kuvöz, claim B of the same patient bills 510010 the same day | 0.00 → 222.36, the row on B only (patient report and B's bill report) |

**Showcase:** the 16 reports (8 stories, copay exempt and not) are byte-identical before and after, also after the merge of `origin/main` (sha256 `f09e8a1b…`; `baseline.py` dumps in `~/.cache/bilun-bedpair-scratch/`); no showcase claim carries a newborn bed line. `public_contracts.json`, the `_finding_type` sets and the showcase proof JSON did not change (checked by tests: the row keys equal the contract's nine on the live, cache and API shapes).

**Tests:** 109 new (`test_yatak_newborn_double_billing.py`, `test_audit_exposure_bed_rows.py`); frontend vitest 112 files / 1,131 tests (+2), `tsc --noEmit` and eslint on the five touched files exit 0 (run alone, after the OOM; the link to `node_modules` is removed). **Mutants:** 73 hand mutants of the detector, the engine call and the rows (boundaries, day model, rounding, scope, ordering, cap, wording), 72 killed; the survivor `D4` (`quantity or 1` against `or 0`) is equivalent because the outer `max(…, 1)` gives 1 either way. The loop ran from a checkpoint commit with byte-identical copies of the originals and sha256 checks; nothing was restored with `git checkout --`.

**Gates** (code tip `11fdb592`; the final commit has the same tree plus this block): local: ruff on `src/ scripts/` clean; full pytest, run alone, 12,024 passed / 2 skipped / 1 failed (the known local-only pandas 2.3.3 test `test_pandas_string_storage_variation_does_not_change_decoded_semantics`, absent in the image; no tracked file changed by the run); `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` 0 issues; `build_rule_surfacing_inventory.py --check` exit 0. **CI-image gate**, alone, on a clone of `11fdb592` (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0): ruff clean, **12,025 passed, 2 skipped, 0 failed** (125 s of pytest, 145 s in all), compile_rules 119 byte-identical, parity 0 issues, no tracked file changed by the run. Frontend, alone: vitest 112 files / 1,131 tests, `tsc --noEmit` and eslint on the five touched files exit 0.

**Independent review** (fresh agent, own clones of the reviewed commit and of `a7a105da`, code only): 12,500 random cases (16,153 patients, 182,490 lines: several claims and patients, odd code spellings, quantities 0 … 6 and huge, positive / zero / negative / tiny amounts, dates clustered plus calendar edges, ICU claims and packages mixed in) against a brute-force day-set oracle: 0 differences on 25,647 flagged lines (to the cent, with ranges, codes, claims and line ids); 0 pipeline invariant violations except F3; the 3,064 bills without the pair are byte-identical to base in the cache and API shapes; 77 hand mutants, 62 killed, 15 survived (4 equivalent or out of contract, 11 test gaps: all now killed by adopted tests). Findings and what became of them: **F1** (medium, a modelling risk) aggregated lines dated on the same day, Kuvöz × 2 and 510010 × 3 both on the admission date, overlap by date although both bed motors read a clean 2 + 3 split — kept as the brief's day model, the detail now says "tarih + adet varsayımı" whenever a line with several days is involved, the docstring no longer claims the motor counts quantity the same way, and a test pins it (open question, below); **F2** a +x line and its −x reversal beside a Kuvöz still give a row for the positive line — the convention of the other audit buckets (a +500 and −500 `bundled_line_flag` still counts 500), pinned as a known limit, a decision for Safa; **F3** the per-line cap was keyed on the line id alone — now `(claim_id, line id)`, with a test (the loader rejects duplicate ids, so only hand-built contexts could reach it); **F4** English label without the same-day condition ("…on a newborn bed day" now), `savings_basis` `sourced` → `heuristic`, "bu günler için" for several days; **F5** the reviewer's nine tests adopted (cap boundary 3,659 / 3,661, calendar-end clamp, merge order, float against Decimal cents, names of non-overlapping newborn lines, dateless 510010, total / capped row / billed spelling) plus one for the "(2 gün)" text; **F6** plan text (14.6b, 2.2.2, the cap is why the report can show less than the violation). Not checked by the review: real MEDULA data, the frontend at run time (I ran vitest, tsc and eslint myself), cache rebuild and staging.

**Corrections to what I said earlier:** (1) the brief called the ICU sibling "wired into `analyze_claim` and shown as audit_exposure rows"; it is neither (see "What the ICU sibling really does"), so the visible rows are new here and the ICU pair stays a hidden Wave A review; (2) my first version labelled the basis `sourced` and its docstring said the newborn motor counts quantity "the same way"; (3) the first plan text said step 14.6 and section 2.2.

**Found, not fixed (decisions or separate tasks):**
1. *Aggregated bed lines (review F1).* The bed motors read a quantity as a day count and ignore dates; this detector also places the days from the line's date. The synthetic data has one line per day, so the two agree there; whether MEDULA dates an aggregated line on its first day, on the admission date or on the discharge date is not known. Needs real data before real claims reach the product (fast lane is synthetic only).
2. *Reversal pairs (review F2).* A positive line and its reversal are not netted, here and in the other audit buckets.
3. *A full bed day billed on a one-date stay.* The unmerged short-stay branch (`claude/youthful-lichterman-28b767`) prices stays under 24 hours at the day bed 510120 in both bed motors (SUT §2.2.2.(3)) and names, as a possible extension, an audit-exposure check for a 510010 / 510070 line billed on such a stay. This detector reads line dates, never the stay, so it behaves sensibly there (a full 510010 and a Kuvöz on the one date are still flagged once, a 510120 line is never read; three tests pin it) and does not do that check. Follow-up card: *over-billing check for a 510010 / Kuvöz / Kot line billed on a stay inside one calendar date* — needs the claim's admission and discharge dates (this detector has only lines) and that branch to have landed. Whoever lands second resolves the top blocks of `tasks/todo.md` and `tasks/lessons.md` and the module docstring of `claim_yatak_newborn_overlap.py`, keeping both intents.
4. *510070 together with 510081 on one day* is an explicit SUT exclusion ("birlikte faturalandırılmaz") that no detector reads; a small separate detector.
5. *The ICU pair is hidden, this one is visible.* `detect_yatak_icu_overlap` reaches the report only as a Wave A financial review with no confirmed amount; making it an audit row too would need its whole-line amount allocated to days, the Q9 corrections of the Wave A map.
6. *Package windows, short stays and who is a newborn* are not modelled for this pair (the newborn motor's own open decisions stand).
7. *Cache:* cached reports need a rebuild before the new rows and the money in `audit_exposure_try` show (staging update is Safa's call).

### Out of Scope
Pushing and the PR (Safa's call); cache rebuild and staging update (cached reports need a rebuild before the rows show); the ICU detector's own open points (zero-charge ICU evidence, whole-line amount); a detector for 510070 and 510081 on one day (explicit in the SUT text, separate); the newborn detection (department tokens), short-stay bed, package-window handling for this pair; making the ICU pair visible as a row; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json` (checked: none of the files above is among the 37 pinned `src/` files); `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened; the EK-2/B text was read from the derived `annex=EK-2B` parquet partition).

## Task: Stays under 24 hours at the day bed (510120) in both bed motors — SUT §2.2.2.(3) (2026-10-18)

### Goal
A stay whose admission date equals its discharge date (so under 24 hours) is priced at the day bed 510120 (44.45 TL on the 2026-07-07 list) by the standard-bed motor and by the newborn bed motor, not as a full 510010 (222.36) or Kuvöz (440.98) day; a stay billed correctly as 510120 leaves nothing to recover and counts as the billed bed; no day is counted by both motors; the 16 showcase reports stay byte-identical.

Safa decided first (asked in the app, answered "Evet" on 2026-10-18): "24 saatten kısa yatışlarda iki yatak motoru da gündüz yatak (510120, ~44,45 TL) fiyatlasın mı?" Follow-up of the "Newborn bed motor" block below (found-not-fixed item 3, review finding F5). Step 0: the worktree is cut from `origin/main` (7ea9457a), which already holds that work as the squash-merge #319; `git diff claude/funny-tereshkova-662936 HEAD` is empty (the branch tip and `main` have the same tree), so the branch was not merged (the check "a commit named `review round 3`" fails only because squash-merge drops the subjects).

### Evidence (read from the files, 2026-10-18)
- SUT §2.2.2.(3) (clause C000648): "24 saatten kısa süreli yatışlarda yatak bedeli, gündüz yatak bedeli üzerinden faturalandırılır." It names no patient group: a newborn is no exception (Kuvöz and Kot are not billable for such a stay; the bed fee is the day bed).
- EK-2/B 510120 "Gündüz yatak tarifesi" (74.96 puan = 44.45 TL on the 2026-07-07 list): "Günübirlik tedaviler, 24 saatten kısa süren yatarak tedaviler, acil müşahade için faturalandırılır. Yemek hizmetleri dahildir."
- `lookup_procedure_code("510120", visit_date=…)` has a price on every list since 2013 (6.60 → 44.45) and is exactly one fifth of 510010 on each (33.00 / 222.36 on the same dates): the catalog needs no fallback.
- The claim has dates, no times: a stay inside one calendar date is certainly under 24 hours; an overnight stay under 24 hours (two dates) cannot be seen. Stated limit, not fixed.

### Measured before (in-memory bills, one date 2026-07-10; `probe_same_day.py` in the session scratchpad; amounts in TL, newborn = Z38.0 "yenidoğan", adult = I10 "kardiyoloji")
| Bill | newborn row (expected / recoverable) | standard-bed row (days, expected / recoverable) | headline |
|---|---|---|---|
| N1 nothing billed | 440.98 / 440.98 | 0 days (newborn owns it) | 440.98 |
| N2 510120 billed in full (44.45) | 440.98 / **440.98** (review F5: the day bed is not seen) | 0 | 440.98 |
| N3 510120 billed 20.00 | 440.98 / 440.98 | 0 | 440.98 |
| N4 510010 billed 222.36 | none (stands down) | 1 day, 222.36 / 0 | 0.00 |
| N5 510070 billed 440.98 | 440.98 / 0 | 0 | 0.00 |
| N6 510070 billed 20.00 | 440.98 / 420.98 | 0 | 420.98 |
| N7 510081 billed 311.30 | 311.30 / 0 | 0 | 0.00 |
| N8 510120 + 510070 billed | 440.98 / 0 | 0 | 0.00 |
| N9 group-B package on the day | 0 days | 0 | 0.00 |
| N10 ICU claim (510090 line) | none | 0 | 742.60 (ICU motor) |
| N11 same-day ward claim on an ICU claim's last day | 0 days | 0 | (the ICU claim's own rows) |
| N12 ICU-named department, no ICU code, nothing billed | none | 1 day, 222.36 / 222.36 | 222.36 |
| N13 department "Pediatri" (J18.9), nothing billed | 440.98 / 440.98 | 0 | 440.98 |
| A1 adult, nothing billed | – | 1 day, 222.36 / 222.36 | 222.36 |
| A2 adult, 510120 billed in full | – | 222.36 / **222.36** | 222.36 |
| A3 adult, 510120 billed 20.00 | – | 222.36 / 222.36 | 222.36 |
| A4 adult, 510010 billed 222.36 | – | 222.36 / 0 | 0.00 |
| A5 adult, package on the day | – | 0 | 0.00 |
| A7 adult, 510070 billed 440.98 | – | 222.36 / 222.36 (inherited: no newborn line is read on a non-newborn claim) | 222.36 |
Controls (not same-day, must not move): N14 newborn 2 days nothing billed 881.96 (headline 956.06); A8 adult 2 days 444.72 (headline 518.82).

### Decisions
1. **Rate and code.** A single-date stay is priced at the 510120 price of the admission date; the row's `bed_code` is "510120" and `daily_rate_try` / `puan` are the day bed's. `rule_id` of the standard-bed row stays `yatak_puani_510010` (it names the §2.2.2 bed-day rule, and the surfacing-audit map lists it); the newborn row's `rule_id` is derived from `bed_code` as before (`yenidogan_yatak_510120`). `type`, row keys and `same_day_stay` keep their meaning, so the public contract does not change. A single-date stay is priced at the day bed also when its one day is already taken out (package window, ICU last day, standard-bed day): days 0, expected 0.
2. **Standard-bed motor.** Nets 510010 lines as before and, on a single-date stay only, 510120 lines too (a 510120 line on a multi-day stay pays no standard-bed day, so it is not counted there: unchanged). The credit-line cap and the mandated-window rule (`counts_against_expected_days`) apply to both codes. A billed 510010 on a single-date stay (222.36 against 44.45 due) leaves 0 to recover as before; the over-billing is an audit matter, not this task.
3. **Newborn motor.** On a single-date stay the one owned day is priced at the day bed, with no Kuvöz/Kot split; the counted lines stay 510070 / 510081 (a billed incubator or cot beside the day-bed price leaves 0, capped at the charge). A claim that bills 510120 and no newborn bed line has stated its bed: the motor stands down exactly as for a billed 510010, the standard-bed motor owns the day and nets the 510120 line (this settles the open point: the billed day bed counts as the billed bed, and its line is netted by one motor only). A 510120 line beside a newborn bed line is ignored by this motor (the newborn bed line covers the day first, as with a 510010 line). The rooming-in gate and the ICU gates are unchanged.
4. **The two reconciliations.** `reconcile_yatak_icu_overlap` and `reconcile_yatak_newborn_overlap` recompute `(bed_days − overlap) × daily_rate_try`; the row now carries the day-bed rate, so their money is right without a change. `reconcile_yatak_newborn_overlap` only names the newborn row's own bed code in its sentence when that code is the day bed ("510070 / 510081" would be wrong there).
5. **Details.** Standard-bed single-date row: "Gündüz yatak (510120): … = 44.45 TRY …" and one sentence, "Same-day admission/discharge (under 24 hours): SUT §2.2.2.(3) bills the bed at the day bed (510120, Gündüz yatak tarifesi), not as a full 510010 day." replacing "consider 510120 … instead of 510010". Newborn single-date row: the same label and a sentence naming Kuvöz and Kot as not billable; its Kuvöz-mutual-exclusion, Kot and "Kuvöz is assumed" sentences are not said for the day bed. Details of multi-day rows stay byte-identical.
6. **Why not stand the newborn motor down on every single-date stay** (rejected): the day bed is the SUT's price for any such stay, so the newborn bed type is moot; but the row Safa asked to have priced would vanish, a billed Kuvöz line on a single-date stay would then net nothing in the standard-bed motor (a false 44.45), and the ownership architecture (newborn motor owns its days, the standard bed loses them) would change. Changing the rate and the stated-bed rule keeps it.

### Design
- `prose_rules/yatak_puani.py`: public constant `DAY_BED_CODE`; `_daily_rate` takes the bed code (default 510010; same signature for existing callers); on `same_day` rate, `bed_code`, netted codes, detail label and sentence change; the `same_day_stay` key stays.
- `prose_rules/yenidogan_yatak.py`: `single_date` branch (day-bed rate, `bed_code`, `puan`, no Kuvöz/Kot split, sentences), stand-down on a billed 510120 for a single-date stay; `_daily_rate(bed_code, visit_date)` unchanged (tests monkeypatch it).
- `billing/claim_yatak_newborn_overlap.py`: the sentence names the newborn row's bed code when it is the day bed.
- No new row key, no `public_contracts.json` change, no frontend change (the frontend's exact-sentence translation of the old advice sentence, `api.billingProse.yatakSameDay`, is then never matched: it was matched only when it was the whole detail, which it never was; listed as a follow-up).
- Tests: see the subtasks. Mutants of the changed branches (mine, then an independent review).

### Subtasks
- [x] 0. Step 0 (no merge needed, see Goal); `before.json` of the 16 reports and `probe_before.json` / `probe_before.txt` saved in the session scratchpad.
- [x] 1. Ask Safa the yes/no first; change nothing until he answered ("Evet").
- [x] 2. Read AGENTS.md, the two newest lessons, both motors, both reconciliations, the tests, the consumers (contract, frontend, engine proof, surfacing audit map, pins: none of the files to change is pinned).
- [x] 3. Write this plan (before any code).
- [x] 4. Tests first, red (48 failed / 165 passed before the code): standard-bed motor on a single date (nothing billed → 44.45; 510120 in full → 0; 510120 in part; 510010 or 510070 billed → 0; 510120 on a 2-day stay is not counted; package window; credit line; a day-bed price on the date of the stay; `same_day_stay` and the sentence); newborn motor (nothing billed → 44.45 with `bed_code` 510120; 510070 / 510081 billed → 0; 510070 in part; 510120 billed → stands down; 510120 beside a newborn line; package, ICU transfer day; Kuvöz/Kot sentences absent; a 2-day stay unchanged); pipeline in `test_yatak_newborn_overlap.py` (N1–N13 and A1–A8 of the table, headline = rows, the day counted once, ICU motor untouched); the existing `test_same_day_stay_flags_gunduz` and the same-day newborn tests updated to the new rule.
- [x] 5. `yatak_puani.py`.
- [x] 6. `yenidogan_yatak.py`.
- [x] 7. `claim_yatak_newborn_overlap.py`.
- [x] 8. Consumers: public contract (no new key), surfacing audit `--check` exit 0, engine-proof and API tests (1,178 passed), no frontend file changed.
- [x] 9. Dump the 16 reports again: byte-identical to `before.json` (sha256 f09e8a1b…); probe table after equals the targets.
- [x] 10. Independent review (fresh agent, code only, own clones; two runs, the first cut by an OOM kill): findings below, fixed or classified.
- [x] 11. Gates one after the other (never in parallel: three at once got the app OOM-killed): ruff, targeted tests, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, CI-image gate alone on a clone of the code tip.
- [x] 12. Commits on the branch (no push; a merge of `origin/main` makes it more than one commit); results in this block; Turkish report.

### Results (2026-10-18/19, branch `claude/youthful-lichterman-28b767`; nothing pushed)
Commits, oldest first: `6adbf7f4` day bed in both motors, plan, tests · `80510069` docs checkpoint · `5fb59032` merge of `origin/main` a7a105da (one conflict, `tasks/todo.md`, where every PR adds a block at the top: all blocks kept, this one first; #320 and #321 touched no bed file; AGENTS.md and `agents/` are gone with #321, as intended) · `4eefa039` the yatak catalog stub prices 510120 (a stub with 510010 only made the motor skip a one-date stay: `test_reconcile_same_day_icu_stay`) · `9347ced2` a day-bed line beside a reversed newborn line takes the day, the block labels name the day bed · `3f300f50` the spelling reading narrowed to 510120 (see below) · `b4e1b87e` pins for the review's survivors · the results commit (the tip).

**The rule now** (evidence and decisions above): a stay whose admission date equals its discharge date is priced at the 510120 price of that date by the standard-bed motor and by the newborn motor (`bed_code` 510120, `daily_rate_try` / `puan` the day bed's, no Kuvöz/Kot choice); a billed 510120 line nets it in the standard-bed motor (on such a stay only, spelled like the newborn stand-down reads it); the newborn motor stands down for a claim that bills 510120 or 510010 and no newborn bed line, counts only 510070/510081 lines, and lets a 510120 line cover the day beside a reversed (credit) newborn line exactly as a 510010 line does; both reconciliations recompute at the rate the row carries (only one sentence changed); a missing 510120 price skips the stay instead of falling back to a full-day price. Stays of two dates or more are untouched.

**Before → after** (in-memory bills, one date 2026-07-10, headline `sgk_uplift_try`; `probe_same_day.py` in the session scratchpad; the table above lists the rows):
| Bill | before | after |
|---|---|---|
| N1 newborn, nothing billed | 440.98 | 44.45 |
| N2 same, 510120 billed in full (44.45) | **440.98** | 0.00 |
| N3 same, 510120 billed 20.00 | 440.98 | 24.45 |
| N4 same, 510010 billed 222.36 | 0.00 | 0.00 |
| N5 / N7 same, 510070 440.98 / 510081 311.30 billed | 0.00 | 0.00 |
| N6 same, 510070 billed 20.00 | 420.98 | 24.45 |
| N8 510120 + 510070 both billed | 0.00 | 0.00 |
| N9 package on the day / N10 ICU claim / N11 ICU last day of another claim | 0.00 / 742.60 / (ICU rows) | unchanged |
| N12 ICU-named department, nothing billed (standard bed) | 222.36 | 44.45 |
| N13 department "Pediatri", nothing billed | 440.98 | 44.45 |
| A1 adult, nothing billed | 222.36 | 44.45 |
| A2 adult, 510120 billed in full | **222.36** | 0.00 |
| A3 adult, 510120 billed 20.00 | 222.36 | 24.45 |
| A4 adult, 510010 billed 222.36 | 0.00 | 0.00 |
| A7 adult, 510070 billed 440.98 (inherited: no newborn line is read on an adult claim) | 222.36 | 44.45 |
Controls, not moved: N14 newborn 2 days 956.06, A8 adult 2 days 518.82.

**Showcase:** `baseline.py` dumps of the 16 reports are byte-identical before and after (sha256 `f09e8a1b…`) at every commit, also after the merge of `origin/main` (a dump of an export of a7a105da is the same file); no showcase claim is a one-date inpatient claim.
**Gates (code tip `b4e1b87e`, the results commit only adds this block):** local: ruff on `src/ scripts/` clean; full pytest 11,984 passed / 2 skipped / 1 failed (the known local-only pandas 2.3.3 test `test_curated_catalog_idempotence`, absent in the image); `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` 0 issues; `build_rule_surfacing_inventory.py --check` exit 0. CI-image gate, alone, on a clone (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0): ruff clean, **11,985 passed, 2 skipped, 0 failed** (149 s), compile_rules 119 byte-identical, parity 0 issues, no tracked file changed by the run.
**Independent review** (fresh agent, own clones, code only; notes `same-day-review-notes.md` in the shared notes folder): on 3f300f50, 3,000 random one-date bills (3,352 one-date claims, each in patient and in bill scope, boundary dates with date-dependent prices, odd claim types, two ICU claims ending the same day) hold 0 violations of nine invariants (no day above the day-bed price, 0 ≤ recoverable ≤ expected, rows = headline = block components, no day in both rows, a stay billed exactly as 510120 leaves 0 on both motors in every context, nothing billed gives one 44.45, patient scope = sum of bill scopes, no claim above one day bed) and 0 disagreements with its first-principles oracle; against base 1,939 claims equal, 1,413 lower, 0 higher; 46 hand scenarios in two scopes equal the hand numbers; 2,700 random bills of two or more dates (6,147 reports) are byte-identical to base; 62 hand mutants, 55 killed by the three core test files (56 with six more), the survivors that change money or a visible sentence were pinned in `b4e1b87e`, two are equivalent. SUT audit (I re-read the clauses and the in-force EK-2/B rows in `sut_clauses.parquet` and `annex=EK-2B` myself): C000648 reads exactly as quoted and names no patient group; C000492 (2.1.2.B.(1)) defines the day case as treatment "yatış ve taburcu işlemi yapılmadan 24 saatlik zaman dilimi içinde", so a same-date admission and discharge is a real under-24-hour stay; C000649 (2.2.2.(4)): no day bed for EK-2/C procedures of a day case; C000969 (2.4.4.D-1.(11)): the day bed is in the hemodialysis price; EK-2/B 530000: "510120, 530003 ile birlikte faturalandırılmaz".
**What the review changed:** (1) hypotheses H1 (an incubator billed, reversed and re-billed as 510120 still showed 44.45) and H2 (spelled 510120 not netted) were reproduced and fixed in `9347ced2`; (2) my first fix also read spelled 510010 lines in the standard-bed motor, and the review measured 88 of 2,733 multi-date reports moving (downward, correct, but a change of stays of two dates and an inherited gap): narrowed in `3f300f50` to the new 510120 line, 510010 is matched as exactly as before and a characterisation test pins that.
**Corrections to what I said earlier:** (a) the plan said "no frontend change" without checking the row titles: they are the kind labels and now name Kuvöz/Kot for a day-bed row (found 4 below); (b) the commit message of `9347ced2` says both motors read bed codes alike: after `3f300f50` that holds for 510120 only.
**Found, not fixed (measured; inherited unless stated):**
1. *A bed is expected where the SUT includes or forbids it.* A one-date `yatis` claim that bills 530000 (EK-2/B: "510120, 530003 ile birlikte faturalandırılmaz") or hemodialysis 704210 / 704230 (C000969, §2.4.4.D-1.(11): the day bed is in the dialysis price) shows a 44.45 day bed (222.36 before); day-case EK-2/C procedures take no day bed (C000649). Neither motor models these exclusions.
2. *A billed 510120 beside a zero-amount or partial newborn bed line is netted by neither row* (the newborn line covers the day first): Kuvöz 0.00 + 510120 44.45 shows 44.45 (440.98 before), Kuvöz 10.00 + 510120 shows 34.45; the same pattern exists with 510010 (decision 3, the "placeholder bill" corner).
3. *A spelled 510010 (" 510.010 ", "510-010") is read by the newborn stand-down and not netted by the standard-bed motor*: a one-date claim billed 222.36 as " 510.010 " shows 44.45 (222.36 before); on stays of two dates the same gap moved 62 of 1,200 random bills when the review normalised it. Pinned by a characterisation test; closing it is a decision.
4. *Row titles (user-visible, low).* The action rows of both motors keep `kind` `yenidogan_yatak` / `yatak_puani_standard_bed`, and `recommendedActionTitle` titles a row without a code by that kind: "Newborn bed charge (510070 / 510081)" and "Standard bed-day charge" (`frontend/src/messages/*/billing.ts:98,102`) also on a row whose detail starts "Gündüz yatak (510120)". **Fixed** in the block "A day-bed action row reads as the day bed in the Revenue view" at the top of this file (own kind `yatak_puani_day_bed`).
5. *Dead frontend mapping* of the removed advice sentence (`apiMessages.ts:338-343`, `messages/en|tr/api.ts`); it only ever matched when the sentence was the whole detail, which it never was. **Fixed** in the block "A day-bed action row reads as the day bed in the Revenue view" at the top of this file (mapping and strings removed).
6. The ICU motor's own `same_day_stay` (a stay under 24 hours in the ICU is priced 510090 by the ICU motor: the clause says "yatak bedeli" without exception); a same-date `acil` claim with dates is read as inpatient by `infer_care_setting` and gets a day-bed row; an overnight stay under 24 hours (two dates) cannot be seen, the claim has no times.
7. The standard-bed row keeps `rule_id` `yatak_puani_510010` on a 510120 row (the surfacing-audit map lists it; `bed_code` carries the code); a standard-bed row with 0 billable days still says it bills the bed at the day bed (only in the API detail, no action row at 0 money).
8. *Cache:* cached reports need a rebuild before a one-date row shows the day bed (staging update is Safa's call).

### Out of Scope
Pushing and the PR (Safa's call); the ICU motor's own `same_day_stay` flag (`icu_puani.py`, its own convention, not a bed motor) and the companion-bed motor (suppresses same-day claims already); overnight stays under 24 hours (no times in the claim data); an audit-exposure detector for a 510010 / 510070 line billed on a stay under 24 hours (over-billing against §2.2.2.(3): nothing to recover, a detector like the ICU one); the frontend's dead sentence mapping; the code spelling difference between the motors ("510.010" with a dot stands the newborn motor down but is not netted by the standard-bed motor: inherited, not touched); the open decisions of the block below (who counts as a newborn, the Kuvöz default); cache rebuild and staging update; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json` (checked: none of the files to change is among the 37); `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened).

## Task: Newborn detection — only a Z38 / P00–P96 diagnosis or a newborn-named department marks a newborn stay (2026-10-18)

### Goal
`yenidogan_yatak` reads a claim as a newborn stay only from its diagnosis (Z38.x, P00–P96) or from a department whose name says newborn (yenidoğan, neonatal, neonatoloji, newborn), in any Turkish spelling; "çocuk" and "pediatri" wards are no newborn signal; the 16 showcase reports do not move by one byte.

Follow-up `newborn-detection` of the "Newborn bed motor" block below (decision 7a; Results "Found, not fixed" 1). Branch `claude/clever-hamilton-d5a51b`. **Safa's decision, 2026-10-18, in this session: yes** to "Yenidoğan algılamasını daraltalım mı? Tanı (Z38, P00–P96) ve yenidoğana özel bölüm adları (yenidoğan, neonatal, neonatoloji) kalsın; 'çocuk' ve 'pediatri' bölüm adları yenidoğan sayılmasın."

Step 0: the newborn-bed work is already in this tree, so no merge was run. `origin/main` 7ea9457a (#319) is the squash merge of branch `claude/funny-tereshkova-662936` (8cfe7ca2, which contains the puan-motor branch): all 36 files that branch changed are identical in HEAD (`git diff HEAD <branch> -- <those files>` is empty) and `tests/unit/domain/billing/test_yatak_newborn_overlap.py` exists. The "review round 3" subject is missing from `git log` only because the squash dropped the individual subjects; merging the branch would add 18 commits of identical content.

### Measured before (the real pipeline, `compute_patient_billing_report`, in-memory 3-day stay, nothing billed; probe `probe_detect.py` in the session scratchpad)
Headline `sgk_uplift_try` = the two bed blocks + the unrelated companion-bed rows (148.20). Showcase dump: byte-identical to the newborn session's final dump `after7.json` (sha256 f09e8a1bf1b41a16…).
| Department · primary ICD-10 | newborn motor | standard-bed motor | headline |
|---|---|---|---|
| Çocuk Sağlığı ve Hastalıkları · Cocuk Sagligi ve Hastaliklari · ÇOCUK SAĞLIĞI VE HASTALIKLARI · Pediatri · Çocuk Cerrahisi · J18.9 | **1,322.94** | 0.00 | 1,471.14 |
| PEDİATRİ (dotted capital İ) · J18.9 | 0.00 | 667.08 | 815.28 |
| Yenidoğan · Yenidoğan Servisi · Neonatal · Newborn · J18.9 | 1,322.94 | 0.00 | 1,471.14 |
| **YENİDOĞAN · YENIDOGAN · Yenidogan · yenıdoğan · Neonatoloji · NEONATOLOJİ** · J18.9 | 0.00 (not read) | 667.08 | 815.28 |
| a P / Z38 code with any department (Pediatri + Z38.0, Çocuk Sağlığı… + P07.3, Kardiyoloji + Z38.0 / P22.0) | 1,322.94 | 0.00 | 1,471.14 |
| controls: Kardiyoloji · J18.9, genel · I10 | 0.00 | 667.08 | 815.28 |

EK-2/B wording behind "0–28 days" (derived annex partitions, present in all 14 list versions, among them the in-force 2026-07-07 list): "Yenidoğan (0-28gün) olguların ameliyatlarında, epikrizde doğum tarihi belirtilmek kaydıyla, …".

### Consequence (to be stated plainly in the report)
A newborn whose claim carries neither a Z38 / P code nor a newborn-named department is no longer read: `ClaimHeader` has no age or birth date (the only age data in the repo is `PatientCopayProfile.birth_year`, `claims/models.py:26`: a year, too coarse for 28 days, and not part of this decision). A paediatric stay of any age stops being a Kuvöz stay; its bed days belong to the standard-bed motor like any other inpatient claim (so the two bed motors still count each day once). No showcase claim has a newborn signal (their departments: Genel Cerrahi, Ic Hastaliklari, Gogus Hastaliklari, Beyin ve Sinir Cerrahisi, Ortopedi ve Travmatoloji, Acil Tip), so no showcase number can move.

### Design
- `prose_rules/yenidogan_yatak.py` only: the folding that `_department_names_icu` does inline (NFKD, strip combining marks, `ı` → `i`, `[a-z]+` words) becomes `_department_words`, used by both functions (the ICU function keeps its behaviour). `_NEWBORN_DEPT_TOKENS` holds the folded newborn-specific names (`yenidogan`, `yenedogan`, `neonatal`, `neonatoloji`, `newborn`); `çocuk`, `cocuk`, `pediatri` are dropped. `_department_is_newborn` = any token inside any word, so "YENİDOĞAN", "Yenidogan", "yenıdoğan", "NEONATOLOJİ" read and "Yenidoğan Servisi" still does. `_is_newborn_icd10` is untouched. The module docstring ("Detection"), the detector docstring and the comment above the tokens say what is read, what is not and why (0–28 days in EK-2/B; no age on `ClaimHeader`).
- Nothing else reads the tokens (`grep`: only this file); `claim_yenidogan_yatak.py` already says "Z38/P00-P96 diagnosis or yenidoğan department". Not pinned by `data/gazette/sut_coverage_evidence.json` (0 mentions; its prose_rules paths are `adult_gh_draft.py` and `drug_indication.py`).
- Tests (red first): in `tests/unit/domain/prose_rules/test_yenidogan_yatak.py` every spelling in both directions (newborn names with no P code read; paediatric names with no P code do not; a P/Z38 code reads whatever the department says; adult control; the ICU spellings of the existing tests unchanged); in `tests/unit/domain/billing/test_yatak_newborn_overlap.py` the F1 test on paediatric departments keeps its assertions with an honest docstring, plus two report-level pins (a paediatric stay with no bed billed has no Kuvöz row and keeps its 3 standard-bed days; a newborn-named department with a non-newborn code has the Kuvöz row and the standard bed gives the days up). Mutants by hand, restored from a byte-identical backup.

### Subtasks
- [x] 0. Step 0 checked by content (36/36 files identical to the branch tip; no merge needed).
- [x] 1. Read AGENTS.md, lessons, the previous block, the motor, its tests and the dependents (only the motor file and `test_yatak_newborn_overlap.py:218`).
- [x] 2. Safa answered yes to the narrowing (quoted above).
- [x] 3. Write this plan (before any code).
- [x] 4. Dump `baseline.py` before (16 showcase reports), compare it with the newborn session's final dump `after7.json`; run `probe_detect.py` before and fill "Measured before".
- [x] 5. Tests first, red.
- [x] 6. `yenidogan_yatak.py`: `_department_words`, tokens, `_department_is_newborn`, `_department_names_icu` on the shared folding, docstrings.
- [x] 7. Tests green; mutants (re-add `çocuk`, re-add `pediatri`, drop the folding, drop `ı` → `i`, drop `neonatoloji`, drop `yenidogan`) each killed; file restored byte-identical.
- [x] 8. Dump `baseline.py` after and `cmp` with before (byte-identical); `probe_detect.py` after; fill the Results.
- [x] 9. Gates one after the other: ruff on `src/ scripts/`, targeted tests, full pytest (local), `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, `build_rule_surfacing_inventory.py --check`.
- [x] 10. Committed (`1181c504`, no push); CI-image gate on a clone of that tip; gate numbers in the Results; Turkish report to Safa.

### Results (2026-10-18, branch `claude/clever-hamilton-d5a51b`, on `origin/main` 7ea9457a; nothing pushed)
**What changed:** `src/bilun/domain/prose_rules/yenidogan_yatak.py` (the only source file) and two test files. `_department_words` is the folding `_department_names_icu` did inline, now shared (the ICU function reads the same); `_NEWBORN_DEPT_TOKENS` = `yenidogan`, `yenedogan`, `neonatal`, `neonatoloji`, `newborn`; `_department_is_newborn` = a token inside a folded word; `çocuk`, `cocuk`, `pediatri` are gone; the module docstring, the detector docstring and the two comments state the rule and its consequence. `_is_newborn_icd10` and everything after the detection are untouched.

**Before → after** (the real pipeline, 3-day stay, nothing billed; probe output in the session scratchpad; the 148.20 inside every headline is the unrelated companion-bed row):
| Department · primary ICD-10 | newborn motor | standard-bed motor | headline |
|---|---|---|---|
| Çocuk Sağlığı ve Hastalıkları · ÇOCUK SAĞLIĞI VE HASTALIKLARI · Cocuk Sagligi ve Hastaliklari · Pediatri · Çocuk Cerrahisi · J18.9 | 1,322.94 → **0.00** | 0.00 → 667.08 | 1,471.14 → **815.28** |
| YENİDOĞAN · YENIDOGAN · Yenidogan · yenıdoğan · Neonatoloji · NEONATOLOJİ · J18.9 | 0.00 → **1,322.94** | 667.08 → 0.00 | 815.28 → **1,471.14** |
| Yenidoğan · Yenidoğan Servisi · Neonatal · Newborn · J18.9; any department with a Z38 / P code; PEDİATRİ; Kardiyoloji; genel | unchanged | unchanged | unchanged |

**Consequence (decided by Safa):** a newborn whose claim has neither a Z38 / P00–P96 code nor a newborn-named department is no longer read; a paediatric stay of any age is a standard-bed stay like any other inpatient claim, and the two bed motors still count each day once. Unchanged by design: the match is inside a word ("Yenidoğanlar" reads), "yeni doğan" in two words, "bebek" and "perinatoloji" are not read (not in the decision).
**Showcase:** `baseline.py` dumped before and after the change is byte-identical (16 reports, 73,420 bytes, sha256 f09e8a1bf1b41a16…) and equal to the newborn session's final dump `after7.json`; no showcase claim carries a newborn signal.
**Tests:** 10 new test functions, 222 cases (the two files hold 366). `test_yenidogan_yatak.py`: every newborn spelling reads with no P code (dotted and plain capitals, ASCII, dotless `ı`, decomposed `ğ`, neonatal / neonatoloji / newborn, the kept `yenedogan`, a name inside a word, punctuation and digits as separators); every paediatric spelling does not (also the capitals and ASCII); a Z38 / P code reads whatever the department says (7 codes × 28 departments, a secondary diagnosis row, codes just outside the range do not); empty / None; a newborn name that names an ICU is still the ICU motor's. `test_yatak_newborn_overlap.py`: the F1 test on paediatric departments keeps its assertions with an honest docstring; a paediatric stay with no bed billed is the standard-bed motor's 3 days (667.08), no Kuvöz row; a newborn-named department with a non-newborn code is a Kuvöz stay (1,322.94) and the standard bed gives the days up. Red first: 41 failed / 322 passed on the unchanged engine, green after.
**Mutants** (by hand, restored from a byte-identical backup, checked with `cmp` and `git diff --stat`): 14 of 14 killed (re-add `cocuk`, re-add `pediatri`, keep combining marks, drop `ı` → `i`, drop each of `neonatoloji` / `yenidogan` / `newborn` / `neonatal` / `yenedogan`, whole-word equality, NFKD → NFC, ICU join with a space, department signal off, words not split).
**Gates (local, one after the other):** `ruff check src/ scripts/` clean; `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` exit 0, 0 issues; `build_rule_surfacing_inventory.py --check` exit 0; targeted bed-motor suites 546 passed + 1 xfailed; full pytest 12,131 passed, 2 skipped, 1 xfailed, **1 failed = the known local-only pandas 2.3.3 test** (`test_pandas_string_storage_variation_does_not_change_decoded_semantics`; CI pins pandas 3.0.6). No tracked file was changed by the runs. **CI-image gate** on a clone of the committed tip `1181c504` (the only heavy job on the machine; Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1): ruff on `src/ scripts/` clean; **12,132 passed, 2 skipped, 1 xfailed, 0 failed** in 195 s (the same 12,132 tests as the local run, where the pandas 2.3.3 one fails and here it passes); `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 23 manifests, 0 issues; no tracked file changed by the run; docker exit 0 after 255 s.
**Lesson written:** after a squash merge `git log | grep <subject>` cannot find a branch's commits; Step 0 of this brief would have merged 18 commits of identical content. The follow-up cards `short-stay-bed` and `bed-double-billing` start from the same Step 0.

### Out of Scope
The Kuvöz default for unbilled days; same-day stays; the audit detector for 510010 beside Kuvöz (the other two follow-up cards of the newborn block); detection by age or birth date (`ClaimHeader` has neither); further newborn spellings that are not in the decision ("yeni doğan" as two words, "bebek", "perinatoloji"); a change of `ClaimHeader`, of the synthetic data or of `data/synthetic/demo_vignettes.json`; cache rebuild and staging update; pushing and the PR; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`; `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened).

---

## Task: Remove AGENTS.md and the agents/ folder (2026-10-18)

### Goal
The root `AGENTS.md` and the `agents/` folder (the July 2026 employee-agent scaffold: three role prompts, three `run_checks.sh`, the `agents.memory` helpers) are gone from the repository, and nothing that CI runs depends on them.

Asked by Safa on 2026-10-18 ("delete the agents.md and agents folder from the repo"). Measured before deleting: 16 tracked files (`AGENTS.md` plus 15 under `agents/`, 920 lines in the folder); no Python, TOML, YAML, shell or workflow file outside `agents/` imports or calls it (`grep` for `agents.` imports, `agents/` paths, `-m agents`, and the packaging and CI entry points); `AGENTS.md` is named only in comments and one assertion message (`scripts/agent/stale_clause_refs.py:26,346`, `tests/unit/synthetic/test_cohort_clean.py:1184,1384`) and in the prompts of the deleted agents. Those comments cite its section 9 (the Polars-only rule); they are left as they are, because a comment edit changes a source hash that the coverage evidence may pin.

### Subtasks
- [x] 1. Measure what depends on the two (above).
- [x] 2. `git rm` the 16 files; add a status line to `plans/tooling/employee-agents-plan.md`.
- [ ] 3. CI-image gate on the committed tip (ruff, full pytest, `compile_rules.py --check`, manifest parity).
- [ ] 4. Push and PR (merge is Safa's call).

### What goes with them (for the record)
`AGENTS.md` carried the working rules of the agent sessions in this repo: plan in `tasks/todo.md` first, subagents, verification, the zombie-process check, CI green before a push, the PR-merge ending on `main`, anti-hallucination, and a closing list that tells an agent to read `docs/operations/RELEASE-LANES.md` and `docs/operations/AI-RUNBOOK.md` before release, CI or staging work and to leave the paused strict lane, Caddy, UFW, Tailscale and the live pair alone. `docs/operations/RELEASE-LANES.md` and `AI-RUNBOOK.md` stay; nothing points an agent to them any more.

### Out of Scope
The older plans that mention the folder (`plans/tooling/mem0-integration-design.md`), the comments that cite `AGENTS.md`, the OpenHands container setup outside the repo, `tasks/lessons.md`.

## Task: The copay key of the cohort table's top action counts the exemption gap on every path (2026-10-18)

### Goal
`_get_top_action_type` (live path) and `patient_recovery_summary_from_payload` (cached path) name the same top action for the `copay` key, and both weigh the figure the table's exemption-gap column shows.

Found by the independent review of the puan-motor work (follow-up of PR #319, where the strict xfail `TestKnownDivergence` pinned it), explained to Safa in plain words on 2026-10-18; Safa: "okay make the fix". Recommendation accepted: bind the live path to the exemption gate.

### Facts measured
- Live path: `waived if waived is not None else total_copay_savings + rx_copay_savings`, no `is_exempt` and no exactness gate. Cached path and the column: `exemption_gap_try` / `_exemption_gap_from_copay_payload`, 0 for a patient who is not exempt, nothing for a block that is not exact.
- `waiver_inpatient_drug` waives every drug of an inpatient claim: a patient who is not exempt has a waived total (5,870 TL on a 20,000 TL drug). Before: live `copay`, cache `none`, api `none` (printed by the xfail test with `--runxfail`).
- The existing exempt + exact tests (the full 16-key report, 71 TL) are untouched by the change.

### Subtasks
- [x] 1. `_get_top_action_type` weighs `exemption_gap_try(report) or 0.0` (`recovery_summary.py`).
- [x] 2. The xfail becomes `TestCopayKeyParity` (6 tests): not exempt, not exact, exempt and exact, the fallback sum, the next motor wins over a not-exempt waived total, a spy that the key reads the column's function.
- [x] 3. CI-image gate on the committed tip.
- [ ] 4. Push and PR (merge is Safa's call).

### Results
- **Behaviour:** a patient who is not exempt, or whose copay block is not exact, no longer names `copay` on the live path; exempt and exact patients are unchanged (waived total, else the procedure plus prescription gaps). No amount changes. The 16 showcase reports are unchanged (the full-report test and the showcase tests pass; none has an inpatient drug waiver on a patient who is not exempt).
- **Gates (tip cff4f469):** CI-image gate on a clone (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1, 270 s): `ruff check src/ scripts/` clean; **11,916 passed, 2 skipped, 0 failed** (the newborn-bed tip had 11,910 passed and 1 xfailed: +6 new tests, the xfail is gone); `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 0 issues; no tracked file changed by the run. Locally `-W error`: 62 passed in `test_top_action_type.py`.
- **Not done:** the file `test_top_action_type.py` was not format-clean before (ruff format wants changes in code this task did not touch); left as it was.

### Out of Scope
The newborn-bed follow-ups (who counts as a newborn, short stays, the 510010 detector), the staging deploy (Safa's call), the cache rebuild.

## Task: Newborn bed motor (`yenidogan_yatak`) — netting, double count with the standard bed, ICU gate, action rows (2026-10-18)

### Goal
The newborn bed motor counts only what the billed newborn bed lines leave of the stay, counts no day that the standard-bed motor also counts, leaves a newborn ICU stay to the ICU motor, and — with the amount right — has Revenue-view action rows that add up to `confirmed_yenidogan_yatak_try`; no existing number on the 16 showcase reports (8 stories, copay exempt and not) changes.

Follow-up 1 of "Finish the wiring of the four puan motors" (block below). Branch `claude/funny-tereshkova-662936`. Step 0: the puan-motor PR is not in `origin/main` yet (`bf917c98` is its base), so `claude/nervous-wilbur-9dfb50` (1ca15139) was merged in (fast-forward). Sanity check: a dump of the 16 reports on this tree is byte-identical to that session's final dump.

### Measured before (in-process, `~/.cache/bilun-newborn-scratch/probe_newborn.py`, in-memory bills, no showcase story)
| Bill | newborn block | standard bed | ICU block | headline `sgk_uplift_try` | rows |
|---|---|---|---|---|---|
| Z38.0, 3 days, nothing billed | 1,322.94 | 667.08 | – | 2,138.22 | 815.28 (bed 667.08 + companion 148.20) |
| same, 510070 billed in full | **1,322.94** | 667.08 | – | 2,138.22 | 815.28 |
| same, one line of 661.47 | **1,322.94** | 667.08 | – | 2,138.22 | 815.28 |
| same, 510081 (Kot) billed in full | **1,322.94** | 667.08 | – | 2,138.22 | 815.28 |
| newborn ICU, 4 days, P22.0, 510090 + P552006, nothing billed | **1,763.92** | 222.36 (1 day) | 3,395.73 | 5,382.01 | 3,618.09 |

The rows of the ICU bill miss exactly the newborn block (1,763.92). The review's figures (headline 4,882.01, rows 3,118.09, ICU 2,895.73) are the same bill with 500 TL billed on the ICU lines. The 8 showcase claims carry no newborn signal (no Z38 / P00–P96 code, no yenidoğan/çocuk/pediatri department: Genel Cerrahi, Ic Hastaliklari, Gogus Hastaliklari, Beyin ve Sinir Cerrahisi, Ortopedi ve Travmatoloji, Acil Tip), so nothing here can move a showcase number.

### Evidence: what the SUT says (read from the files, not from memory)
`data/gazette/raw/annex=EK-2B/…` (10 list versions 2020-03-11 → 2026-07-07; each code has ONE explanation text in all ten, whitespace-normalised full-cell comparison):
- **510010 Standart yatak tarifesi** (374.97 puan): "Yemek, yatak, hasta vizit hizmetlerini kapsar."
- **510070 Kuvöz** (743.65): "Yemek, yatak, hasta vizit hizmetlerini kapsar. 510081 ile birlikte faturalandırılmaz. Günde bir adet faturalandırılır."
- **510081 Kot (beşik)** (524.95): "Yemek, yatak, hasta vizit hizmetlerini kapsar. 510070 ile birlikte faturalandırılmaz. Anne yanında izlenen bebekler için faturalandırılmaz."
- **510090 Yoğun bakım** (1252.27): "Yemek, yatak, hasta vizit hizmetlerini kapsar. Bu kod ile birlikte monitörizasyon, hastanın mekanik ventilatöre bağlanması, ventilatör ile takip, nebülizatör, oksijen tedavisi ve derin trakeal aspirasyon ücreti ayrıca faturalandırılmaz."
- EK-2/C (2026-07-07): P552006 / P552007 / P552008 "Yenidoğan birinci / ikinci / üçüncü basamak yoğun bakım hastası", 3221.799 / 6846.35 / 12896.186 puan (the adult P552001–3 have the same puan); no explanation text.
- SUT §2.4.4.H.(7) (C001242): "Aynı sağlık hizmeti sunucusunda aynı gün birden fazla basamakta yoğun bakım tedavisi gören hasta için bir yoğun bakım bedeli faturalandırılabilir." §2.4.4.H.(8) (C001243): the first ICU day and the day of death / discharge from ICU / transfer are billed hizmet başına (510090); the days between are the EK-2/C package (P55200x, newborn P552006–8). §2.2.2.(3) (C000648): "24 saatten kısa süreli yatışlarda yatak bedeli, gündüz yatak bedeli üzerinden faturalandırılır."
- The SUT body (`sut_clauses.parquet`, in-force clauses, Turkish-folded search) has no clause that names Kuvöz, Kot, 510070 or 510081 and none on the newborn bed; the only newborn-bed text is the EK-2/B explanation column above.

What that does and does not establish:
1. **Says:** each of the four codes "kapsar" the same three services (yemek + yatak + vizit); 510070 is one per day and never with 510081; 510081 never with 510070 and never for a baby followed beside the mother; the ICU day is one fee per day and a newborn ICU stay is billed with 510090 + P552006–8.
2. **Does not say, in so many words:** "510070 is not billed with 510010", "a Kuvöz day is not billed beside an ICU day". That they cannot is an **inference** from the identical "kapsar" text: the bed codes are alternatives for one patient-day. The project already applies exactly this inference to 510090 against 510010 (`prose_rules/yatak_icu_overlap.py`, `claim_yatak_icu_overlap.py`: "yatak o gün zaten ödendiği için 510010 ayrı faturalanamaz"), and the motor's own docstring says Kuvöz "Bundles yemek + yatak + vizit (same bundle as standart yatak 510010)". So: same days must not be expected twice, and the newborn ICU is the ICU motor's (the docstring already says so).
3. **Nothing in the claim says which bed the baby lay in** (no incubator field; no age or birth date in `ClaimHeader`). The motor's default "Kuvöz for every identified newborn stay" is an assumption of the design, not SUT evidence; a billed bed line is the only evidence there is.

### Decisions
1. **Netting like the ICU motor** (`icu_puani.py:357-364`): `actual_billed_try` = Σ `billed_amount_try` of the claim's counted 510070 and 510081 lines (a line inside a mandated package window belongs to the package); `recoverable_uplift_try = min(expected_try, max(0, expected_try − actual_billed_try))` (the cap is decision 8); `expected_try` stays the full charge. `YenidoganYatakReview.confirmed_yenidogan_yatak_try` reads `recoverable_uplift_try`, else `expected_try` (the order of the ICU property; a hand-built row without the field keeps counting its `expected_try`, which the existing tests of the top action rely on). The motor still emits the opportunity when nothing is left (recoverable 0), as the ICU motor does: the standard-bed reconciliation below needs it.
2. **A billed bed line is the only evidence of the bed type; a billed Kot is never "upgraded" to Kuvöz (revised twice after the reviews).** Nothing in the claim says whether the baby lay in an incubator. Final rule, on the days this motor owns (any bed line states the type, a credit line — a reversal — too; only a non-credit line covers days, by its quantity, at least 1): (a) only Kot lines → every owned day at the Kot rate, wherever the billed days lie and whatever their quantity (pricing reads no quantity here); (b) Kuvöz and Kot lines → each billed Kot day (Σ quantity of the counted 510081 lines, at most the owned days) at the Kot rate, every other day at the Kuvöz default; (c) no bed line → Kuvöz, the full charge (the task requires it). Why not simpler: pricing a billed Kot by amount against the Kuvöz rate would show the Kuvöz–Kot difference (129.68 TL a day) as recoverable on a bill that follows the SUT. The first version ("Kot lines and no Kuvöz line → all days Kot") left exactly that difference on a stay billed Kuvöz and then Kot (review: 4 days, 2 Kuvöz + 2 Kot billed exactly, row 259.36); the second (per-day split for every Kot line) over-stated a cot-only stay whose single line carries several days at quantity 1 and priced the days after a billed cot at Kuvöz (review round 2: G1, G2); this one keeps the per-day split only where Kuvöz lines also exist. A path incubator → cot is a plausible one, not data: the repo has none. The ICU motor does the same with its tiers ("strictly from submitted lines; never default to 3rd-basamak"). A mixed stay's `bed_code` / `puan` name the Kuvöz default. Rooming-in claims stay Kuvöz-only. Quantity still decides in three places (the Kuvöz+Kot split, `standard_bed_days`, the netting of a mandated window): a line with quantity 1 that carries several days' amount is outside the claim data's per-day convention (the showcase bed lines are one line per day, quantity 1; MEDULA's `adet` is the day count) and reads as one day there.
3. **No day is counted by both bed motors.** The standard-bed expectation of a claim that has a newborn bed opportunity loses exactly the days that opportunity owns (`max(bed_days − newborn days, 0)`; with no billed 510010 beside the newborn bed that is every day of the stay), as a post-processing step after both blocks, the sibling of `reconcile_yatak_icu_overlap`. This also repairs the reverse bill (Kuvöz billed, 510010 not): the standard-bed motor must not call those days unbilled — except for a department-only ICU claim, where the newborn motor stands down and the standard bed still counts the days (decision 4b). **A claim that bills the standard bed (510010) and no newborn bed line has stated its bed (review F1):** the newborn motor stands down and the standard-bed motor keeps the stay and nets its own 510010 lines; before, a fully and correctly billed 510010 stay still got a full Kuvöz row (1,322.94 on a 3-day stay), and so did every correctly billed pediatric admission flagged by its department. A claim that bills both (incubator, then a standard bed) keeps the newborn motor for the days the billed 510010 lines do not cover: `standard_bed_days` (Σ quantity of the counted, non-credit 510010 lines, at most the stay) are the standard-bed motor's, which nets its own lines, and the reconciliation takes only the newborn-owned days out of its expectation (review round 2: Kuvöz ×2 + 510010 ×8 billed exactly left a 3,527.84 row; now 0 on both motors). The newborn bed lines cover their days first and the 510010 lines only the days left (review round 3: Kuvöz ×7 billed in full plus two 510010 lines on a 7-day stay used to make the standard bed claim 444.72; the excess is double billing, an audit matter). A credit line (negative amount) covers no day, for 510010 and for Kot alike, but it still states the bed type: a claim whose only bed line is a reversed 510010 stays with the standard-bed motor (review round 3: reading it as "no bed" turned a 10-day paediatric stay into a 4,409.80 Kuvöz row). Not built: an audit-exposure detector for 510010 actually billed beside Kuvöz on the same day (the ICU side has one); follow-up.
4. **The ICU gate:** the newborn bed motor stands down for a claim that carries an ICU indicator code (510090 / P55200x on its procedure lines — the ICU motor's own gate, so the two motors split the claims without a gap or an overlap) **or** whose department names an intensive care unit (Turkish-folded "yoğun bakım"). The department case is a stay in a unit the module docstring calls "NON-ICU newborn ward beds" only: with no ICU code on the bill the ICU motor stays silent and a Kuvöz is the wrong bed, so silence is the honest result ("pending is a valid state"). One existing test (`test_department_only_detection`) uses "Yenidoğan Yoğun Bakım" as its example of a department-only signal; its intent is the department signal, so its example becomes "Yenidoğan Servisi", and a new test pins the ICU department. The department spellings read: Turkish-folded "yoğun bakım" with spaces, hyphens and digits ignored ("Yoğunbakım", "Yoğun-Bakım", double space), and the whole words YB, YBÜ, YYBÜ, ÇYBÜ, NICU, PICU, ICU (also "YB1", "NICU2"). Not read: KYB, "Y.B.". Stated limits: (a) a claim with an NICU segment and a ward segment is, in the project's ICU model (the ICU span is the claim span), an ICU claim; its ward days are not priced as Kuvöz; (b) for a department-only ICU claim that bills no newborn bed the newborn motor stands down but the standard-bed and companion motors, which read no department, still count their days (review F6: 667.08 + 148.20 on a 3-day stay), so "silence" is the newborn motor's, not the report's; a unit named as an ICU that bills a newborn bed is netted like any other claim (review round 3: otherwise a "Çocuk YBÜ" stay billed Kuvöz in full showed a 1,334.16 standard-bed row), and one that bills 510010 stays with the standard-bed motor; (c) "Yoğun Bakım Dışı Yenidoğan Servisi" (a ward named by what it is not) also reads as ICU.
5. **Rows** (Revenue view, finding type `opportunity`): `yenidogan_yatak` joins the uplift loop of `collect_billing_actions`; amount = `recoverable_uplift_try`, else `expected_try`, over rows with `included_in_sgk_total`, what the component sums (fallback field `expected_try`); kind = the opportunity type, no `procedure_code` (as the bed and ICU rows); `sut_section_id` 2.2.2 (the motor's own). The detail is the engine's text plus, when newborn bed lines are billed, one sentence naming the billed amount ("this row is the unbilled remainder", as the ICU row), and when none is billed, one sentence that Kuvöz is assumed because the claim carries no bed line. The block leaves `_AGGREGATE_ONLY_BLOCKS` (now empty) and the surfacing audit's aggregate-only list. Check that `yenidogan_yatak` can no longer win the cohort table's Top action without a row behind it.
6. **The EK-2/C package window (a third overcount, found by probe, fixed in its own commit).** SUT §2.2.2.B-1(1),(3)-(4) (as `yatak_puani.py` encodes it): a package includes the bed from admission through its window (A1–A3 15, B 10, C 8, D 5, E 3 calendar days from the procedure date). Measured: a Z38.0 stay of 10 inclusive days with a group-B package line (P600040, procedure date day 2): the standard-bed motor bundles all 10 days (`bed_days` 0, 0 TL), the newborn motor still expects and counts 10 × 440.98 = **4,409.80 TL**. The brief names two defects; this is the same function being wrong about the same amount, so a row built on it would offer money the SUT includes in the package. The motor reuses `claim_package_window` / `counts_against_expected_days` from `yatak_puani.py` (days after the window; billed lines inside a mandated window do not count toward them), so the two bed motors agree on the days. Separate commit: it can be dropped without touching the three decisions above.
7. **Found, not fixed, reported with the measurements:** (a) detection by department: on a pneumonia claim (J18.9, no Z38 / P code) the departments "Yenidoğan", "Yenidoğan Servisi", "Çocuk Sağlığı ve Hastalıkları", "Cocuk Sagligi ve Hastaliklari", "Pediatri" and "Çocuk Cerrahisi" are each flagged as a newborn Kuvöz stay of 3 × 440.98; "YENİDOĞAN", "Yenidogan" and "Neonatoloji" are not (the folding is `casefold()` against tokens with `ğ`). Every pediatric inpatient stay is a "newborn" one today, and with rows it becomes visible; SUT's own newborn is 0–28 days (EK-2/B "Yenidoğan (0-28gün)") and the claim has no age field. (b) the Kuvöz default itself (point 3 of the evidence); (c) no audit-exposure detector for 510010 billed beside Kuvöz; (d) a same-day (admission = discharge, so under 24 h) stay is priced as one full Kuvöz day (440.98) although SUT §2.2.2.(3) and EK-2/B 510120 (74.96 puan = 44.45 TL) bill short stays as the day bed; the standard-bed motor has the same convention (222.36) and both only add a note; (e) the newborn department detection is not Turkish-upper-safe ("YENİDOĞAN", "PEDİATRİ", "NEONATOLOJİ" read as no signal) while the ICU department test is. Before real claims reach the product, (a) and (b) need a decision (fast lane = synthetic only).
8. **Recoverable never exceeds the expected charge (review F3).** A negative billed line (the parser accepts them) made `max(0, expected − actual)` exceed `expected` (440.98 expected, −100 billed → 540.98), and in the new reconciliation a −44.47 standard-bed line left 44.47 recoverable on a day that had been removed. The newborn motor and `reconcile_yatak_newborn_overlap` cap at `expected`; since the stand-down hands such claims to the standard-bed motor (review round 2, G4: −222.36 TL billed on a 10-day stay → 2,445.96 recoverable against 2,223.60 expected, 88 of 1,800 random bills) its detector and its ICU reconciliation (`reconcile_yatak_bed_days`) cap too. The ICU motor's own formula (`icu_puani.py:364`) has the same pattern and is not touched (inherited, not on this path).
9. **The ICU transfer day (review F4, a third commit).** When another claim of the patient is an ICU claim (510090 / P55200x) whose last day falls inside this claim's stay, the project's claim-span ICU model treats the ICU claim's `discharge_date` as a 510090 day (EK-2/B: it covers yemek + yatak + vizit), even when no 510090 line carries that date (review round 2, G6); the standard-bed motor drops it (`reconcile_yatak_icu_overlap`, from `ctx.history`), the newborn motor did not (B: 3 Kuvöz days 1,322.94 against 881.96). The motor takes the ICU last days of the patient's other claims, drops them from its days after the package window (as `reconcile_yatak_bed_days` does) and records `icu_overlap_days` / `icu_overlap_dates` like the standard-bed row.

### Design
- `prose_rules/yenidogan_yatak.py`: keywords `procedure_lines` and `icu_last_days`; per-claim ICU gate (code or department); the stand-down on a billed standard bed; bed-type evidence, Kot pricing and the owned days (package window, ICU transfer day, `standard_bed_days`); netting of the counted 510070 / 510081 lines with the cap; detail sentences; new row keys `actual_billed_try`, `bundled_days`, and only when non-zero `icu_overlap_days` / `icu_overlap_dates` / `standard_bed_days`. `claim_yenidogan_yatak.py` passes the lines and the ICU last days of `ctx.history`. `prose_rules/icu_puani.py`: `_claim_has_icu_code` becomes the public `claim_has_icu_code`; `prose_rules/yatak_icu_overlap.py`: `collect_icu_last_days` is public.
- `billing/types.py`: `confirmed_yenidogan_yatak_try`. New `billing/claim_yatak_newborn_overlap.py` (`reconcile_yatak_newborn_overlap(yatak_review, newborn_review)`), called in `patient_report.py` after both blocks; new row key `newborn_overlap_days` on the standard-bed row. `prose_rules/yatak_puani.py` and `yatak_icu_overlap.py`: the recoverable amount is capped at the expected charge.
- `billing/billing_actions.py`: the row loop (`_SGK_COUNTED_FALLBACK_FIELD`, `_OPPORTUNITY_SURFACES`, the netted detail shared with the ICU row).
- `api/public_contracts.json`: on `yenidogan_yatak` rows `actual_billed_try`, `bundled_days`, `icu_overlap_days`, `icu_overlap_dates`, `standard_bed_days`; on `yatak_puani` rows `newborn_overlap_days` (new row keys in the projection; no new report field).
- Surfacing audit: `recommend_yenidogan_yatak_from_claims` patient_visible (surface `yenidogan_yatak`, `RecommendedActionsPanel`), the new call in `EXPECTED_REPORT_CALLS` and the three metadata maps; `build_rule_surfacing_inventory.py --write`.
- Frontend (a delegated agent, `frontend/**` only): surface and kind labels EN/TR, compact-panel exactness source for the `yenidogan_yatak` block, vitest, `tsc`, eslint.
- Tests: see the subtasks. Mutants of every changed function (mine, then two independent rounds).
- No new report field, so no change in the engine proof JSON (no showcase story has a newborn stay).

### Subtasks
- [x] 0. Worktree has the puan-motor work (merged `claude/nervous-wilbur-9dfb50`, fast-forward); `before.json` of the 16 reports saved and equal to that session's `after.json`.
- [x] 1. Read AGENTS.md, lessons, both motors, their history, the SUT text; reproduce both defects on in-memory bills.
- [x] 2. Write this plan (before any code).
- [x] 3. Frontend agent launched in parallel (labels, panel, vitest, tsc, eslint) with the fixed names (surface and kind `yenidogan_yatak`).
- [x] 4. Tests first, red: netted amount (billed in full / partly / nothing / Kot in full / Kot partly / both / two claims / negative and zero amounts), the double count (both directions, adult control), the ICU gate (code, department, neither), rows == component for the newborn block over all field combinations, the top action has a row behind it (live and both payload shapes), the strict xfail turned into a normal test, the guard list empty, `test_department_only_detection` example.
- [x] 5. `yenidogan_yatak.py`, `claim_yenidogan_yatak.py`, `icu_puani.py` (public gate), `types.py`.
- [x] 6. `claim_yatak_newborn_overlap.py`, `patient_report.py`.
- [x] 7. `billing_actions.py` rows; `public_contracts.json`.
- [x] 7b. Separate commit: the package window in `yenidogan_yatak.py` (tests: the probe bill, partly bundled, mandated window, billed line inside the window, no window).
- [x] 8. Surfacing-audit metadata and `build_rule_surfacing_inventory.py --write`; its test counts.
- [x] 9. Dump the 16 reports again, diff against `before.json` (scalars, block components, action rows, summaries on three shapes): nothing may move.
- [x] 10. Probe the "found" points: department tokens and the package window measured (see decisions 6 and 7); numbers written down above.
- [x] 11a. Independent review (fresh agent, code only, own clones): 1,900 random bills, 87 hand mutants (71 killed), evidence audit. Findings F1–F9 triaged into decisions 2, 3, 4, 8, 9 above.
- [x] 11b. Fix commit: per-day Kot pricing (F2), cap at expected (F3), stand-down on a billed 510010 (F1), department spellings (F6), docstrings (F7), tests that kill the surviving mutants (Y08, Y26, R10, R11) and pin the contract keys (F8).
- [x] 11c. ICU transfer day commit (F4) with the P03 scenario (the order of the two reconciliations turned out to be equivalent for money: only the order of two detail sentences differs).
- [x] 11d. Second review round on the fix commits (3,700 random bills, 81 mutants, answers C1–C4): G1–G7 triaged, G1/G2/G3/G4/G5 fixed in two commits (standard-bed days beside a newborn bed; Kot rule v3, standard-bed cap, spellings), G6 reworded, G7 documented.
- [x] 12. Gates one after the other: ruff on `src/ scripts/`, targeted tests, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, CI-image gate on a clone of the committed tip.
- [x] 13. Commit on the branch; results in this block; Turkish report.

### Results (2026-10-18, branch `claude/funny-tereshkova-662936`, on top of `claude/nervous-wilbur-9dfb50` 1ca15139; nothing pushed)
Commits: `4be94e3a` plan · `51f0958b` netting, shared days, ICU gate, rows · `f3384112` frontend · `3dac377a` package window · `40e9ff9b` review round 1 fixes · `9122b922` ICU transfer day · `26b416d2` standard-bed days beside a newborn bed · `f5419825` review round 2 fixes · `d588b6df` review round 3 fixes · `c5a8675c` results · `bb69d474` pins for the confirmation round (the final tip).

**The amount now follows these rules** (evidence and decisions above): the motor prices only the days it owns — the stay less package-window days, less an ICU last day of the patient's other claims, less days billed on the standard bed beside a newborn bed line; Kuvöz for unbilled days, Kot where only a cot is billed (or for the billed Kot days of a Kuvöz+Kot stay); it nets the counted 510070/510081 lines and never recovers more than the charge; it stands down on an ICU stay (code or department) and on a claim that bills only the standard bed; the standard-bed motor expects no day the newborn motor owns. Rows: Revenue view, finding type `opportunity`, rows == `confirmed_yenidogan_yatak_try`; `_AGGREGATE_ONLY_BLOCKS` is empty; the surfacing audit has 1 aggregate-only finding (report totals) and 84 runtime rows.

**Before → after on in-memory bills** (`~/.cache/bilun-newborn-scratch/probe_table.py`; headline = `sgk_uplift_try`; the 148.20 / 222.30 left in several rows are the unrelated companion-bed rows):
| Bill | headline before → after | rows before → after |
|---|---|---|
| A Z38.0, 3 days, nothing billed | 2,138.22 → 1,471.14 | 815.28 → 1,471.14 |
| B same, 510070 billed in full | 2,138.22 → 148.20 | 815.28 → 148.20 |
| C same, 1 of 3 days billed | 2,138.22 → 1,030.16 | 815.28 → 1,030.16 |
| D same, Kot billed in full | 2,138.22 → 148.20 | 815.28 → 148.20 |
| E same, 510010 billed in full | 1,471.14 → 148.20 | 148.20 → 148.20 |
| F 4 days, 2 Kuvöz + 2 Kot billed exactly | 2,875.66 → 222.30 | 1,111.74 → 222.30 |
| G paediatric J18.9 "Pediatri", 510010 billed in full | 1,471.14 → 148.20 | 148.20 → 148.20 |
| I 10 days, group-B package from day 2 | 4,409.80 → 0.00 | 0.00 → 0.00 |
| J newborn ICU, 4 days, 510090 + P552006 | 5,382.01 → 3,618.09 | 3,618.09 → 3,618.09 (= headline) |
| K 1 day, 510070 line of −100 | 663.34 → 440.98 | 222.36 → 440.98 |
| L NICU claim 8–10 July + ward claim 10–12 July | 5,168.72 → 2,960.08 | 2,522.84 → 2,960.08 |
| M 10 days, Kuvöz ×2 + standard bed ×8, billed exactly | 5,521.42 → 666.90 | 1,111.62 → 666.90 |
| N 4 days, cot-only, one qty-1 line carrying 4 days | 2,875.66 → 222.30 | 1,111.74 → 222.30 |

**Showcase:** `baseline.py` (scalars, block components, action rows and the cohort summary on three payload shapes, 16 reports) is byte-identical to `before.json` at every commit and equal to the puan-motor session's final dump; no showcase claim carries a newborn signal.
**Gates (final tip bb69d474; the same code as d588b6df plus tests):** CI-image gate on a clone (Python 3.13.15, pandas 3.0.6, polars 2.0.0): ruff on `src/ scripts/` clean; **11,910 passed, 2 skipped, 1 xfailed, 0 failed** (the puan-motor gate had 11,717 passed / 2 xfailed; the remaining xfail is the `copay` one, the newborn strict xfail is a normal test now); `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 0 issues; no tracked file changed by the run. Local: ruff, `compile_rules --check`, parity clean; the one local-only failure is the known pandas 2.3.3 one (`test_curated_catalog_idempotence`), absent in the image. `build_rule_surfacing_inventory.py --check` exit 0. Frontend: vitest 112 files / 1,129 tests (+7), `tsc --noEmit` and eslint on the 7 changed files exit 0; the agent's mutants (maps, panel source, EN/TR strings, keys) all killed.
**Exactly billed stays:** over 8,100 random bills (round 3, quantity-faithful lines: a run is one line with quantity = days, or one line per day) no stay of any mix of 510070 / 510081 / 510010 shows money on either bed motor in any of four contexts (846 stays: plain, billed package, mandated package, ICU transfer day; 141 bill-scoped slices). Outside that convention (a line with quantity 1 that carries several days) it can: 33 of 98 cot-only stays in a mandated package window, 300 of 600 mixes with such Kot/510010 lines, 31 of 88 Kuvöz+Kot bills with such a Kot line. The standard-bed cap also moves non-newborn bills that carry a credit 510010 line (15 of 637 random bills; no showcase bill has one).
**Independent review** (fresh agent, own clones, never touched the worktree): round 1 on 3dac377a: 1,900 random full-pipeline bills (1,400 also on base), 479 bill-scoped reports, 87 hand mutants (71 killed), evidence audit; every invariant held (rows == headline == components, no day on both bed motors, top action backed by a row on live / cache / endpoint shapes, 637 bills without a newborn signal byte-identical to base) and it found F1–F9. Round 2 on 9122b922: 3,700 bills, 2,178 bill slices, 81 mutants of the new code (56 killed), 1,435 bills whose numbers differ explained by class; G1–G7. Round 3 on f5419825: 8,100 bills, 96 mutants (81 killed): invariants held; it found three regressions of my last two commits (H2 double-covered line-days, H3 a reversed 510010 line read as no bed, H4 an ICU-named unit that billed Kuvöz in full), fixed in `d588b6df` with their reproductions as tests. Round 4 on d588b6df (confirmation): the same 8,100 bills, 71 mutants (57 killed, the four meaningful survivors BU1 / N13 / N17 / N19 now pinned by tests): every invariant held, the H2 / H3 / H4 repros are fixed, the exactly-billed claim still holds (846 stays), and three corner cases on contradictory or placeholder bills remain (limit 6 below). All rounds' findings were fixed or classified (decisions 2, 3, 4, 8, 9; commits `40e9ff9b`, `26b416d2`, `f5419825`, `d588b6df`); the hole it found in my first stand-down (an incubator-then-standard-bed stay billed exactly still showed 3,527.84) is closed. Notes: `~/.cache/bilun-newborn-scratch/review-findings.md`.
**Corrections to what I said earlier:** (1) the task text and the message of `51f0958b` give the 3-day headline 2,138.22 as Kuvöz 1,322.94 + standard bed 667.08; it is those two plus the companion bed 148.20. (2) `9122b922` says the order of the two reconciliations is "killed by the same bill": it is not; the two orders are equivalent for money (only the order of two detail sentences differs). (3) `40e9ff9b` says "Both cap": the standard-bed detector was capped only in `f5419825`. (4) `9122b922` and an early docstring say 510090 pays the ICU last day's bed; in the claim-span ICU model that day is the ICU claim's `discharge_date`, which need not carry a 510090 line (the standard-bed motor drops the same day). (5) "incubator, then cot" is a plausible path, not data.
**Found, not fixed (measured; decisions or separate tasks):**
1. *Who is a newborn.* The department tokens read every paediatric ward stay as a newborn one ("Çocuk Sağlığı ve Hastalıkları", "Pediatri", "Çocuk Cerrahisi": a pneumonia claim of 3 days, nothing billed, gets a Kuvöz row of 1,322.94); "YENİDOĞAN" (dotted capital İ), "Yenidogan" and "Neonatoloji" read as no signal. SUT's newborn is 0–28 days (EK-2/B "Yenidoğan (0-28gün)") and the claim has no age or birth date. A paediatric stay that bills the standard bed, as real ones do, is now left alone (row G); one that bills no bed still gets the Kuvöz row (row H). Needs a decision before real claims reach the product.
2. *The Kuvöz default for unbilled days.* The task requires "nothing billed gives the full charge"; the reviewer's objection stands: nothing in a claim says an incubator was used. The detail says so ("Kuvöz (510070) is assumed — confirm the bed type in the stay record"). MEDULA's own notes (`docs/medula/medula_capabilities.md` §2.8) say each stay day carries a bed code, so a real bill would state the bed; the gap is the synthetic schema's.
3. *Same-day stays:* admission = discharge is priced as one full Kuvöz day (440.98) although SUT §2.2.2.(3) and EK-2/B 510120 (74.96 puan = 44.45 TL) bill stays under 24 hours as the day bed; the standard-bed motor has the same convention (222.36); both only add a note.
4. *No audit-exposure detector for 510010 billed beside Kuvöz/Kot on the same day* (the ICU side has one, `detect_yatak_icu_overlap`).
5. *Department-only ICU claims:* the newborn motor stands down but the standard-bed and companion motors read no department and still count their days (a "Yenidoğan Yoğun Bakım" claim, no ICU code, Kuvöz billed in full: standard-bed row 667.08, headline 815.28).
6. *Contradictory or placeholder bills (round 4, decided by the rules above):* (a) line-days beyond the stay with an unpaid newborn bed: Kuvöz ×9 at 0 TL plus 510010 ×5 billed in full on 10 days (14 line-days) — the newborn lines cover days first, so 4 days paid under 510010 are asked again as unbilled Kuvöz (headline 4,635.72, the previous design 2,871.80); (b) a reversed Kuvöz line beside paid 510010 days states a Kuvöz bed, so the stay is priced as Kuvöz (3,312.78, previously 2,001.06); (c) an ICU-named unit that bills one 0-TL Kuvöz placeholder loses its department silence (3,016.38, previously 1,704.66), because a stated newborn bed lifts the department gate. None occurs in the showcase data.
7. *Inherited, not touched:* the ICU motor's uncapped `max(0, expected − actual)` (`icu_puani.py:364`); the claim-span ICU model (a ward→ICU transfer's first ICU day is dropped by neither bed motor); a Kot line with quantity 1 carrying several days beside Kuvöz lines is still priced as one Kot day; a mixed stay's `bed_code` / `puan` name the Kuvöz default.
8. *Cache:* cached reports and legacy caches need a rebuild before the rows and the netted amounts show (staging update is Safa's call).

### Out of Scope
Pushing and the PR (Safa's call); the department tokens and the Kuvöz default (found, measured, reported, decision for Safa); an audit-exposure detector for 510010 billed beside Kuvöz; the `copay` key divergence and the other open follow-ups of the puan-motor block; cache rebuild and staging update; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json` (checked: the 37 pinned `src/` files are the drug-indication, adult-GH / MDS, constants, optimization/shared and SUT-registry modules; none of the files above is among them); `data/synthetic/sut/claims/ilay_validation/`, `data/gazette/prose_rules/golden/ilay/` and any folder named `raw data` (never opened; the EK-2/B text was read from the derived `data/gazette/raw/annex=…` parquet partitions).

---

## Task: Finish the wiring of the four puan motors — cohort-table top action and ICU action rows (2026-10-18)

### Goal
The cohort table's "Top action" names `anestezi_puani`, `refakatci`, `icu_puani` and `yenidogan_yatak` on the live and the cached-payload path, the ICU motor's counted money has action rows that add up to `confirmed_icu_try`, the newborn bed money stays aggregate-only until its amount is right, and no existing amount on the 16 showcase reports (8 stories, copay exempt and not) changes.

Follow-up 1 and 2 of the S3/S4/S8 task below. Branch `claude/nervous-wilbur-9dfb50`, on top of #317 (bf917c98), the squash merge of that task into `origin/main`. (History of step 0: the worktree was cut from `origin/main` 2804f468 and lacked `test_showcase_fault_rows.py`, so it was first fast-forwarded to that task's local branch `claude/infallible-saha-4d427f` e5f60645; when #317 landed, tree identical to e5f60645, the four commits of this task were replayed onto it, so the gate numbers below hold; the hashes and two commit messages changed.)

### Measured before (in-process, `patient_recovery_summary_*`, `~/.cache/bilun-puan-scratch/baseline.py` -> `before.json`)
`live` = `patient_recovery_summary_entry(report)`. `cache shape` = `patient_recovery_summary_from_payload(json_ready(report))`, which is exactly what `cache/builder.py` stores in `patient_billing_report_rows`. `api shape` = the same on `_serialize_billing_report(report)`.

| Story | Recoverable | live top action | cache shape | api shape |
|---|---|---|---|---|
| S1 | 4,122.06 | strategy | **none** | strategy |
| S2 | 667.08 | yatak_puani | **none** | **none** |
| S3 | 928.09 | **none** | none | none |
| S4 | 370.50 | **none** | none | none |
| S5, S6, S8 | 0 | none | none | none |
| S7 | 0 (capture gap) | capture_gap | capture_gap | capture_gap |

The same 16 rows with copay exempt. The ICU and newborn blocks have 0 opportunities on all 16 reports: no showcase story exercises them.

### Decisions (with the evidence)
1. **The cached-payload path of `top_action_type` is already wrong for 7 of its 12 keys; the four new keys must not copy that pattern.** `patient_recovery_summary_from_payload` reads `session_uplift.total_uplift_try`, `drg_uplift/blood_uplift/material_uplift/procedure_addon_uplift.confirmed_uplift_try`, `yatak_puani.confirmed_yatak_try` and `billing_strategy.uplift_savings_try`. These are `@property` values; `json_ready` (`cache/build_streaming.py`) keeps dataclass fields only, so a payload as the cache builder writes it has none of them (probe: all 7 absent) and the path returns `none` for S1 and S2. `_serialize_billing_report` restores 6 of them for a live dataclass but not `confirmed_yatak_try` (S2 `none` on the API shape too). A fresh cache is not affected (the cohort summary is built live, `cohort_summary.py:203`; the route recomputes from payloads only for a legacy cache whose `patient_summaries` are missing or lack `total_opportunity_try`, `optimization.py:332-339`), so the defect is silent. The audit-finding-#12 comment ("mirror ... so both paths produce identical top_action_type") has never held on the real cache shape. Decision: the payload path takes an amount the payload carries as it is (the endpoint shape: nothing that worked changes) and otherwise rebuilds the block from its rows (`opportunities` / `recommendations`, which every payload carries) and reads the same property as the live path. That makes the four new keys work and, with the same helper, repairs the 7 old keys; their live values do not change. A parity test over the 16 showcase reports on the real cache shape and on the endpoint shape proves it.
2. **Newborn bed money gets no rows: the amount is an engine defect.** `prose_rules/yenidogan_yatak.py:209-210` sets `recoverable_uplift_try = expected_try = days x 510070 rate` and never nets billed 510070/510081 lines; commit cea8a012 (#13, "recoverable_uplift_try was set to the full expected charge unconditionally, inflating the SGK-uplift headline for correctly-billed stays") fixed exactly this for `icu_puani` and `yatak_puani` and left the newborn motor out. Measured on an in-memory newborn bill (Z38.0, 3 days, 510070 at 440.98): expected 1,322.94; with 510070 billed in full (1,322.94) `recoverable_uplift_try` is still 1,322.94 and so is `confirmed_yenidogan_yatak_try`. Second defect on the same bill: `yatak_puani` also counts those 3 days (667.08), so the headline 2,138.22 = 667.08 + 1,322.94 although the module's own docstring says Kuvöz bundles the same yemek + yatak + vizit as 510010. Rows for this money would tell a billing officer to recover what was billed. No amount is changed in this task; the block stays on the named aggregate-only list and a strict `xfail` pins the correct behaviour.
3. **The ICU motor nets billed lines (`icu_puani.py:357-364`) and its rows are safe to surface.** `confirmed_icu_try` reads `recoverable_uplift_try`, else `total_try`, over rows with `included_in_sgk_total`.
4. **The ICU "tier" over-billing row does not reach the ICU block.** `detect_icu_tier_overbilling` (`icu_puani.py:450-569`, `included_in_sgk_total` False, `at_risk_try` 0.0) is called from `billing/engine.py:270-274` into the claim-audit violations; `recommend_icu_puani_from_claims` calls only `detect_icu_puani_opportunities`. Probe on an in-memory ICU bill with P552003 and no support line: block rows `['icu_puani_yogun_bakim']`, detector rows `['icu_tier_overbilling']`. The row collector skips rows with `included_in_sgk_total` False anyway; a test feeds the tier row's real shape into a block and a premise test pins that the detector's rows are not in the block.

### Design
- `recovery_summary.py`: both dicts get `icu_puani`, `yenidogan_yatak`, `refakatci` and `anestezi_puani` (the order of `BILLING_BLOCK_SPECS`) appended after `copay`, read from `confirmed_icu_try`, `confirmed_yenidogan_yatak_try`, `confirmed_refakat_try`, `confirmed_anestezi_try`. Appended last because `max` keeps the first of equal amounts: a tie then still goes to the key it went to before, so no existing patient's value can change except where a new motor has strictly the largest amount. The payload path takes a carried amount, else builds the block from its rows. The key order of the two dicts must be the same; a test records both dicts and compares the key lists. The comment's key count (13) was already stale (12 keys); it names 16 now.
- `billing_actions.py`: `icu_puani` joins the uplift loop and the SGK-counted set; `_sgk_counted_uplift` takes the fallback field of each block (`expected_try` for anaesthesia and companion, `total_try` for ICU), so each row equals the block's own component; finding type `opportunity`; `detail` is the opportunity's detail plus one sentence naming the billed ICU amount when there is one (the row's amount is the unbilled remainder; the detail states the full expected charge). No `procedure_code` (the row spans 510090 and P55200x lines), `sut_section_id` 2.4.4.H.
- Frontend: surface and kind labels for `icu_puani` / `icu_puani_yogun_bakim` (EN/TR), compact-panel exactness source, the four new values in `labels.sut.actionType` (EN/TR; today an unmapped value shows title-cased, e.g. "Anestezi Puani").
- Surfacing audit: `recommend_icu_puani_from_claims` becomes `patient_visible` (surface `icu_puani`, `RecommendedActionsPanel`); `aggregate_only` 3 -> 2 (report totals, newborn bed money); outputs regenerated.
- No new report field, so no `public_contracts.json` change; no showcase story gets a row, so no proof JSON change.

### Subtasks
- [x] 0. Worktree has the S3/S4/S8 work (#317 on `origin/main`; at the start only the local branch `claude/infallible-saha-4d427f`, fast-forwarded to).
- [x] 1. Read AGENTS.md, lessons, the code, the history of the two motors; measure the 16 reports (`before.json`); probe the newborn netting and the ICU tier row on in-memory bills.
- [x] 2. Write this plan (this block, before any code).
- [x] 3. `recovery_summary.py`: four keys on both paths; payload path from rows; tests (registry roles S3/S4, in-memory ICU and newborn, parity on the 16 showcase reports on the cache shape and the API shape, key order, tie).
- [x] 4. `billing_actions.py`: ICU rows; tests (rows = `confirmed_icu_try` over every field combination, netted amount, tier row shape, premise of the detector, newborn still no row + strict xfail of the netting); shrink `_AGGREGATE_ONLY_BLOCKS` to the newborn block.
- [x] 5. Frontend (labels, panel exactness, `actionType`, vitest, `tsc`, eslint).
- [x] 6. Surfacing-audit metadata, `build_rule_surfacing_inventory.py --write`, its test counts.
- [x] 7. Dump the 16 reports again, diff against `before.json`: only `top_action_type` of S3/S4 (live, both payload shapes) and of S1/S2 (cache shape, S2 api shape) and the new ICU rows may move.
- [x] 8. Gates one after the other: ruff on `src/ scripts/`, targeted tests, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, CI-image gate on a clone of the committed tip.
- [x] 9. Independent review of the diff (fresh agent, code only, 170 tool calls, 61 hand mutants); fix what holds up.
- [x] 10. Commit on the branch; results in this file; Turkish report.

### Results (2026-10-18, branch `claude/nervous-wilbur-9dfb50`, commits 70d0a003, 72666db6 and f98264a5 on top of `origin/main` bf917c98, the squash merge #317 of the S3/S4/S8 work)
- **Cohort table:** `top_action_type` names `anestezi_puani`, `refakatci`, `icu_puani` and `yenidogan_yatak` on the live and on the cached-payload path (appended last, `BILLING_BLOCK_SPECS` order, so a tie keeps going to the key it went to before). Live path on the 8 showcase bills: S3 `none` -> `anestezi_puani` (928.09 TL), S4 `none` -> `refakatci` (370.50 TL); S1 `strategy`, S2 `yatak_puani`, S7 `capture_gap` and the three `none` stories unchanged (no tie on the cohort). In the running app (fresh cache from the committed data, cohort table "En önemli işlem"): HASTA-0003 "Anestezi puanı", HASTA-0004 "Refakatçi ücreti", the rest as before.
- **Cached-payload path repaired on the way:** it was wrong for 7 of its 12 keys (decision 1). On a payload as the cache builder stores it S1 and S2 now read `strategy` and `yatak_puani` like the live path (before: `none`); on the endpoint shape S2 too. `_block_amount` takes an amount the payload carries and otherwise rebuilds the block from its rows, so nothing that worked changes.
- **ICU rows:** `icu_puani` / `icu_puani_yogun_bakim`, Revenue view, `sgk_uplift_try` = the unbilled remainder = `confirmed_icu_try` (rows add up to the component for every combination of `recoverable_uplift_try` / `total_try` / `included_in_sgk_total`, also for the anaesthesia and companion blocks). In-memory ICU stay (510090 x 2 + P552003 x 3, 700 TL billed): expected 16,780.08, row 16,080.08, headline = bed row 444.72 + ICU row 16,080.08. A stay billed in full makes no row. The tier over-billing review makes no row and is not in the block.
- **Newborn bed: no rows, engine defect found** (decision 2): billed 510070 days stay "recoverable", and the standard-bed motor counts the same days. Strict xfail `test_a_newborn_bed_billed_in_full_leaves_nothing_recoverable`; `_AGGREGATE_ONLY_BLOCKS` is `{"yenidogan_yatak"}` now. Consequence until the amount is fixed: a newborn patient's top action can name this motor next to an overstated amount (no showcase story has a newborn stay).
- **No existing number changed:** `~/.cache/bilun-puan-scratch/baseline.py` dumped every scalar, every block component, every action row and the summary (live, cache shape, endpoint shape) of the 16 reports before and after. Only `top_action_type` moves: live S3, S4; cache shape S1 to S4; endpoint shape S2 to S4 (both copay variants). `action_count`, every amount and every action row are identical.
- **Not touched, by design:** `public_contracts.json` (no report field added; the `icu_puani` section was already public), the engine proof JSON (no showcase story has an ICU stay), the cache (a rebuild is needed before a legacy cache shows new rows or top actions; Safa's call), `scripts/deploy/**`, `docs/operations/**`, `.github/**`, `pyproject.toml`, files pinned by `sut_coverage_evidence.json` (none of the edited ones is).
- **Tests added (+66 passed, +2 xfailed, +11 vitest):** `test_top_action_type.py` (57: registry roles, whole-summary parity on 16 reports x 2 payload shapes, same keys/order/amounts, ties, counted and uncounted money per motor, carried amount vs rows, a report whose 16 sources all hold a different amount, strict xfail of the copay divergence), `test_icu_and_newborn_rows.py` (11: netted row, nothing billed, billed in full, two claims, the review row, no invented detail, rows == component over 72 field combinations x 3 blocks, newborn control and strict xfail). Mutation checks: 10 mutants of `recovery_summary.py` and 10 of `billing_actions.py` killed by my own first round; the reviewer's 61 hand mutants left 15 meaningful survivors (nothing pinned the payload amounts of the old keys, the truthiness of `included_in_sgk_total`, a carried zero) and my re-run kills 14 of them after the additions (the 15th, the order of the ICU row in the list, is not worth pinning); the frontend agent's mutations (surface map, panel exactness source, EN/TR label maps, finding type) all killed.
- **Gates (tree of f98264a5; the docs commit after it changes no code):** CI-image gate on a clone (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1, 170 s): `ruff check src/ scripts/` clean; **11,717 passed, 2 skipped, 2 xfailed, 0 failed** (the S3/S4/S8 tip had 11,651; the gate on the ICU-rows commit 72666db6, before the review additions, gave 11,714 and 1 xfailed); `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 0 issues; no tracked file changed by the run. `build_rule_surfacing_inventory.py --check` exit 0. Frontend: vitest 112 files / 1,122 tests (+11), `tsc --noEmit` exit 0, eslint on the 10 changed files exit 0 (through a temporary link to `~/.cache/ui-review-code2/frontend/node_modules`, removed afterwards; re-run by me after the agent's run).
- **Live check:** backend (anonymous local mode, fresh cache build) on 8741 and `next dev` on 3741 from a scratch clone of the branch, so the worktree stayed clean; looked at as `http://localhost:3741/` (on `127.0.0.1` Next blocks `/_next/hmr` and the page never loads its data). Servers stopped by port, clone removed.
- **Independent review** (fresh agent, code only, read-only on the repo, ran 800 random full-pipeline bills base vs head, 60,000 random reports, an ICU boundary sweep, 61 hand mutants): no defect in the ICU rows or in the four new keys: rows == component for 150,000 random blocks and 300 pipeline bills, the review row never leaks, tie rule holds (every one of 13,794 changed top actions went to a new key strictly larger than all 12 old values), `sgk_uplift_try` unchanged in 800 of 800 bills, 16 showcase reports as in the commit message, `from_payload` 14 us per payload (not a cost). Findings and what was done: (1) **pre-existing parity break on the `copay` key**, reachable: the live path weighs `patient_copay_waived_total_try` with no `is_exempt` gate, the payload path `exemption_gap_try` (0 when not exempt); `waiver_inpatient_drug` (`copay_line_waivers.py:214`) waives every drug of an inpatient claim, so a patient who is NOT exempt can have waived 5,870 TL (20,000 TL drug, reproduced by me) and the live path names `copay` while the cached path and the table's exemption-gap column say 0. My plan's out-of-scope note described a different variant that the engine cannot produce. Pinned with a strict xfail; which side is right is a product decision (recommendation: gate the live path like the table's own column, which changes the live top action for such patients). (2) **`yenidogan_yatak` can win the Top action with no action row behind it** (a consequence of decision 2 and of the key the task asked for): 198 of 800 random bills (the reviewer's generator over-samples newborn claims: a mechanism check, not a rate), mostly stays that used to read `yatak_puani`; the headline already counts that money. Kept, reported. (3) a **second newborn defect**, reproduced by me: the newborn bed motor has no ICU gate although its docstring says newborn ICU is the ICU motor's: on a newborn ICU stay (dept yenidoğan yoğun bakım, P22.0, 510090 + P552006, 4 days) it adds 1,763.92 TL of Kuvöz on top of the ICU charge 2,895.73 and one standard-bed day 222.36: headline 4,882.01, rows explain 3,118.09. (4) the I5 invariant (rows == component) holds for non-negative cent amounts of an exact block; hand-built partial-exact blocks or negative amounts break it, the engine cannot produce them. (5) `_block_amount` is stricter than the old `float(x or 0)` on malformed fragments (an amount `""`, rows `[None]`): the real serializers cannot produce them, `optimization.py:338` has no try/except; left as it is. (6) six other top-action values still have no label (blood_uplift, material_uplift, procedure_addon_uplift, capture_gap, package_adequacy_review, medula_playbook; S7 reads "Capture Gap" in the Turkish table): follow-up. (7) three comments cite this plan block, which was uncommitted at review time: committed with this docs commit.
- **Found, not fixed (follow-ups):** (1) the newborn bed motor: net the billed 510070/510081 lines, add the ICU gate, decide against the SUT text whether Kuvöz and the standard bed 510010 can be billed on the same days, then give it rows (remove the strict xfail and the guard entry); (2) the `copay` divergence above (decision for Safa); (3) six unlabelled top-action values; (4) the open follow-ups of the S3/S4/S8 task that are not about the puan motors: the payment-method bucket amount, `COMPLIANCE_INDEX_SURFACES` without `audit_exposure`, `clause_ref` on the new rows; (5) cached reports and legacy caches need a cache rebuild before the rows and top actions show (staging update is Safa's call); (6) ICU/yatak row details show the expected charge, the ICU row now adds one sentence about the billed part, the yatak row does not.

### Out of Scope
The newborn amount (netting billed 510070/510081 lines, the ICU gate, the double count with the standard bed) and rows for it; the `copay` key of the two summary paths (live weighs `patient_copay_waived_total_try` without the `is_exempt` gate, the payload weighs `exemption_gap_try`: equal on all 16 reports, different for a patient who is not exempt but has a waived inpatient drug, see the review); the payment-method bucket amount; `COMPLIANCE_INDEX_SURFACES`; `clause_ref` on the new rows; labels for the six other top-action values; cache rebuild and staging update (Safa's call); anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; any file pinned by `data/gazette/sut_coverage_evidence.json` (none of the files above is).

---

## Task: Action rows for the three showcase faults that had none — S3, S4, S8 (2026-10-18)

### Goal
The S3 (anaesthesia points), S4 (companion bed) and S8 (second package at full rate) bills each get an action row that carries the fault's money, in the workspace view that fits the money, and no existing amount changes.

Started by the session that ran P7-lite (finding in its Results: "S3, S4 and S8 show their money in the KPIs but have no row that explains it"). Branch `claude/infallible-saha-4d427f`, cut from `origin/main` 3abe33a3 and merged with `claude/synthetic-v3-p7-lite-swap` e1aa315d (step 0: the registry and the 8-claim tables were missing on the base; the merge was a fast-forward).

### Measured before (in-process, `compute_patient_billing_report`, not-exempt copay, one bill each)
| Story | Money in the report | Where | Action rows today |
|---|---|---|---|
| S3 | `sgk_uplift_try` 928.09 | `anestezi_puani.confirmed_anestezi_try` (1 opportunity, `anestezi_puani_group`, code 615931) | 2, both `claim_checklist` |
| S4 | `sgk_uplift_try` 370.50 | `refakatci.confirmed_refakat_try` (1 opportunity, 5 days x 74.10) | 2, both `claim_checklist` |
| S8 | `audit_exposure_try` 3,584.80 (`sgk_uplift_try` 0) | `compute_audit_exposure_from_claims` = `ClaimUnbundlingFinding.session_violations` (P603840, billed 7,169.60, allowed 3,584.80 at 50%) | 3, all `claim_checklist` |

### Decision (judgment, with the evidence)
1. **S3 and S4 get rows, in the Revenue view** (`finding_type` `opportunity`, amount in `sgk_uplift_try`).
   - The omission is a wiring gap, not a design choice. `BILLING_BLOCK_SPECS` (`block_registry.py`) feeds both blocks into `sgk_uplift_try` (`uplift_field` `confirmed_anestezi_try` / `confirmed_refakat_try`) and `test_claim_integration.py` pins them as components of the headline; every other uplift block that feeds the headline (strategy, session, DRG, blood, yatak, material, add-on) has rows in `collect_billing_actions`. History: commit 2fc03061 (2026-07-12) listed `billing_actions.py` as a touchpoint only for `yatak_puani`; its wiring list for the other puan motors (types, block_registry, patient_report, cohort_summary) leaves it out.
   - The repo's own surfacing audit saw it and parked it: `scripts/audits/rule_surfacing/metadata.py:419-446` marks `recommend_icu_puani/yenidogan_yatak/refakatci/anestezi_puani` as `aggregate_only` with `hidden_reason` "Contributes to SGK/cohort totals but has no recommended-action row or patient section", and the audit plan (`plans/billing/2026-09-18-rule-engine-surfacing-audit-plan.md`, "Wave D") says "Decide explicitly whether aggregate-only outputs need row-level surfacing". This is that decision: yes for the two with a showcase story.
   - SUT: both amounts are payable on the clause the rule cites. §2.2.2.A.(1) bills hizmet başı by EK-2/B (the anaesthesia groups 550130-550260 are EK-2/B §4 rows); §2.6.3.(2) pays the companion's bed and food at the EK-2/B "refakat" points when the provider bills it, on the physician's medical need and a stay certificate (§2.2.2.A.(3) sends the itemized bill to the same paragraph). That certificate is a precondition, so the S4 row keeps the detector's verification note in its `detail`.
2. **S8 gets a row, in the Compliance view** (`finding_type` `compliance`, amount in `audit_risk_try`, never in `sgk_uplift_try`).
   - The money is over-billing exposure, not a payable uplift: `claim_audit_exposure.py` ("over-billing risk — not SGK uplift"), the chatbot money rules (`sgk_uplift_try ≠ audit_exposure_try`), the registry (`effect_kind` `deduction_risk`). The Compliance view already shows `audit_exposure_try` as its first KPI above a findings table that stays empty for S8.
   - The row schema and the UI were built for it: `_action_row` has had `audit_risk_try` since the first itemization commit (469959f9, 2026-06-19) and `recommendedActionAmountParts` renders it ("Audit risk"), but no producer ever set it.
   - SUT §2.2.2.B.(3): in the same session the highest package pays in full and the others at 25% (a, same incision) or 50% (b, separate incision) of their own points. S8's second package is billed at 100%. The report takes the lenient 50% reading (3,584.80); the registry record takes the 25% reading (5,377.20) = 3,584.80 + 1,792.40, the "strict" part that the row's `detail` already states. This is the documented divergence `KNOWN_REPORT_DIVERGENCES["S8"]` (issue #311 item 6). The row carries what the report counts; no number changes.
3. **Not by design, so not "stop".** No test, comment or doc says rows must not exist; the only record is the audit's `aggregate_only` parking above.

### Design
- `billing_actions.py`: `anestezi_puani` and `refakatci` join the uplift loop with the `yatak_puani` rule (rows with no positive SGK-counted uplift make no row: S2/S6 refakat rows of 0 TL and S1/S5/S8 package-window suppressions stay silent); their finding type is `opportunity`; the refakat note rides in `detail`. New surface `audit_exposure` (finding type `compliance`), one row per `risk_amount_try > 0` entry of the session, blood-component and bundled-line buckets of the unbundling finding.
- The payment-method bucket makes no audit row: the same `mandated_package_gap` already produces the `billing_strategy` `compliance_violation` row for it, and a second row would double-list one finding. Its money stays in `audit_exposure_try` as today.
- Row source: `recommend_audit_exposure_from_claims` (`claim_audit_exposure.py`), a new explicit step of `compute_patient_billing_report` (the surfacing audit models it as its own callable): one `analyze_claim_unbundling` pass gives the unchanged `audit_exposure_try` arithmetic and the rows, kept on `BillingActionReport.audit_exposure_rows` (the public response contract lists the field). The collector stays the single place that makes `recommended_actions`. A first version filled the rows inside `finalize_report_totals`; dropped, because a totals function would then originate findings.
- Frontend: labels for the three surfaces and the new kinds (EN/TR), exactness source for the compact panel. Cohort compliance index (`COMPLIANCE_INDEX_SURFACES`) is not touched.
- Derived pins that move by design: the engine proof JSON of S3, S4, S8 (one more `action` signal, `action_count` +1), the surfacing audit metadata and its committed outputs (`aggregate_only` 5 → 3: report totals, ICU and newborn bed money; the last two stay aggregate-only on purpose, no showcase story and a different amount rule); the public response contract (`public_contracts.json`, the new `audit_exposure_rows` section).

### Subtasks
- [x] 0. Worktree has the 8-patient data (merge of `claude/synthetic-v3-p7-lite-swap`, `cohort_registry.json` present, `claim_headers.parquet` 8 rows).
- [x] 1. Read AGENTS.md and lessons; measure the report of each story; read the code, history, audit, SUT clauses; write this plan.
- [x] 2. Backend: collector rows for `anestezi_puani`, `refakatci`; `audit_exposure_rows` on the report and the `audit_exposure` rows; the unchanged `audit_exposure_try` value.
- [x] 3. Tests on the registry roles: S3, S4 rows with the registry amount; S8 row = the report's `audit_exposure_try` and the documented divergence; sum of the rows = the report's components for S1 to S4; no row for 0-TL refakat/anaesthesia opportunities; a guard that every block with an `uplift_field` has a surface or is on the named aggregate-only list.
- [x] 4. Surfacing audit: metadata for the changed callables, regenerate `reports/rule-engine-surfacing/*`, test counts.
- [x] 5. Engine proof: refresh S3/S4/S8 proof JSON (+1 `action` signal, `action_count` +1), README note; `test_cohort_engine_proof.py` green.
- [x] 6. Frontend: surface/kind labels (EN/TR), compact-panel exactness source, vitest, `tsc`, eslint.
- [x] 7. Gates one after the other: ruff on `src/ scripts/`, targeted tests, full pytest, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`, CI-image gate on a clone of the committed tip.
- [x] 8. Independent review of the diff (fresh agent, code only); fix what holds up.
- [x] 9. Commit on the branch; results in this file; Turkish report.

### Results (2026-10-18, branch `claude/infallible-saha-4d427f`, commits a4de4127 and 1f364d2e, rebased onto `origin/main` 2804f468 after #316)
- **Why the three bills had no row:** S3 and S4 are a wiring gap. `BILLING_BLOCK_SPECS` feeds `anestezi_puani` and `refakatci` into `sgk_uplift_try`, but `collect_billing_actions` never read these two blocks (commit 2fc03061 listed `billing_actions.py` as a touchpoint for the bed-day motor only; the 2026-09 surfacing audit then recorded the four puan motors as `aggregate_only`). S8 is different: `audit_exposure_try` is a scalar, and the report kept none of the entries behind it, so there was nothing to turn into rows.
- **What now exists (each bill, one new row, nothing removed):**

| Story | Surface / kind | View | Amount in the row | Report total it explains |
|---|---|---|---|---|
| S3 | `anestezi_puani` / `anestezi_puani_group` (code 615931, SUT 2.2.2.A) | Revenue (`opportunity`) | `sgk_uplift_try` 928.09 = registry | `sgk_uplift_try` 928.09 |
| S4 | `refakatci` / `refakatci_companion_bed` (SUT 2.6.3; the 2.6.3.(2) stay-certificate note is in `detail`) | Revenue (`opportunity`) | `sgk_uplift_try` 370.50 = registry | `sgk_uplift_try` 370.50 |
| S8 | `audit_exposure` / `session_point_violation` (P603840, SUT 2.2.2.B.b) | Compliance (`compliance`) | `audit_risk_try` and `billed_try` 3,584.80 | `audit_exposure_try` 3,584.80 |

  S8 differs from the registry (5,377.20) by the documented divergence (`KNOWN_REPORT_DIVERGENCES["S8"]`, #311 item 6): the report counts the separate-incision 50% reading, the record the same-incision 25% reading. The two add up in the test: 3,584.80 + 1,792.40 (the strict part, stated in the row's `detail`) = 5,377.20.
- **No existing number changed:** `~/.cache/bilun-s348-scratch/baseline.py` dumped every scalar, every block component and every action row of the 16 reports (8 stories, copay exempt and not) before and after. The only differences are `action_count` of S3, S4 and S8, +1 each, and the three new rows. `compute_audit_exposure_from_claims` keeps its arithmetic (the ~40 exposure pins of `test_showcase_session_and_package_gaps.py` pass); the cohort summary still gives `total_sgk_uplift` 6,087.73 and `total_audit_exposure` 3,584.80.
- **Other files that move by design:** the proof JSON of S3, S4 and S8 (`prove.py S3 S4 S8`: one more `action` signal, `action_count` +1, nothing else); `public_contracts.json` (the public projection drops sections the contract does not list; `test_public_projection_preserves_cohort_business_results_and_cached_nulls` caught it); the surfacing audit metadata and its committed outputs (`aggregate_only_findings` 5 to 3: report totals, ICU and newborn bed money); `test_billing_actions.py` (S4 is no longer "quiet": its fault row is part of the surfaces).
- **Tests added (+45 Python, +11 vitest):** `test_showcase_fault_rows.py` (31: rows on the registry roles with the registry amounts; every component equals the sum of its rows on all 8 bills; 0-TL and suppressed companion opportunities of S1, S2, S5, S6, S8 make no row; self-made opportunities for the included/excluded rule and the `expected_try` fallback; a guard that every block with an `uplift_field` has rows or is on the named list `{icu_puani, yenidogan_yatak}`), `test_audit_exposure_rows.py` (14: each bucket, two entries of one bucket, the payment-method bucket makes no row and its premise on the S1 bill with one 20,000 TL drug line added in memory, total and rows from one pass, the review handed to `finalize_report_totals` is used, no procedure lines gives nothing). Mutation checks: with the parent commit's `billing_actions.py` 14 of the first 30 fail; the three mutants that the independent review found alive (no line id in the audit action id, no `expected_try` fallback, `finalize_report_totals` ignoring the review) are caught now. Frontend: label maps, amounts, view buckets, `RecommendedActionsPanel` full and compact with a different exactness per block (a mutation that drops the exactness mapping fails), the Compliance view with an S8-like row.
- **Gates (tree of 1f364d2e):** CI-image backend gate on a clone of this tree before the rebase onto #316 (it was commit a99afd18; the rebase changed no file, the base trees e1aa315d and `origin/main` 2804f468 are identical) (`bilun-laptop-ci:20261008-runtime-complete`, Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1, 164 s): `ruff check src/ scripts/` clean; **11,651 passed, 2 skipped, 0 failed** (the P7-lite tip had 11,606; the first commit a4de4127 alone gave 11,647); `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 0 issues; no tracked file changed by the run. The same numbers locally. Frontend: vitest 112 files / 1,111 tests, `tsc --noEmit` exit 0, eslint on the changed files exit 0. The main checkout's `node_modules` lacks `react-test-renderer` (15 test files cannot load there), so the frontend gates ran through a temporary link to the matching install in `~/.cache/ui-review-code2/frontend/node_modules`, removed afterwards. Not run locally: `npm run build` and `verify_public_assets.py` (CI runs them); `verify-workspace-views.mjs` and `capture-screens.mjs` (no Playwright browser on this laptop; they make no assertion about S3, S4 or S8).
- **Independent review (fresh agent, code only, 149 tool calls, ran differential checks on 303 claim contexts):** rows equal `confirmed_*_try` (160 field combinations, 2,000 random blocks); `audit_exposure_try` identical to the parent's value and repr on the 303 contexts and the 16 reports; the sum of the rows plus the payment-method bucket equals the total in all 303; the public section adds only `procedure_line_id` and `rule_id`, both already public. Findings and what was done: (1) `billed_try` on the audit row carries the risk, not the line's billed amount: kept on purpose, it is the money SGK would deduct (a materials row's billed amount is the line it would reject; the registry's `amount_try` of S5 and S8 is the deduction), and it orders the next-actions card; now said in a code comment. (2) The payment-method bucket leaves part of the KPI without an amount row: confirmed (8 of 303 contexts; on the S1 bill with one 20,000 TL drug line the KPI is 15,877.94 and no row states an amount); the `billing_strategy` `compliance_violation` row exists for every entry and carries no money, so no second row was added (it would list one finding twice); the premise is pinned by a test now, the amount on that row is a follow-up. (3) Consumers: `top_action_type` and the cohort compliance index do not know the new surfaces (follow-ups 2 and 4 below). (4) Three surviving mutants: tests added. (5) Audit metadata: emitted kinds now name the three row kinds, the call moved inside the `if procedure_lines` block like its siblings, the UI token is the Compliance view's findings table; `report_fields` stays empty because the rows ride on a local, which is cosmetic. (6) The new section repeats the rows of `recommended_actions` in every cached payload: accepted, it is the carrier from the assembly to the collector. (7) The status chip of an audit row reads "review risk" and has no `clause_ref`: unchanged.
- **Live check in the app:** backend (anonymous local mode, `BILUN_PUBLIC_BILLING_ENABLED=1`, fresh cache build from the committed data) on 8731 and the frontend dev server on 3731, looked at in the built-in browser. S3 Revenue tab: recoverable 928.09, 1 opportunity, the row "Anesthesia group charge: 615931". S4 Revenue tab (EN and TR): 370.50, 1 opportunity, "Companion bed charge (510121)" with the verification note. S8 Compliance tab: audit exposure 3,584.80, 1 at-risk finding, billed at risk 3,584.80, the row "Session factor exceeded: P603840" with the detail. Servers stopped; the files that `next dev` writes (`frontend/AGENTS.md`, `frontend/CLAUDE.md`, `next-env.d.ts`, `.next`) and the temporary links removed; `git status` clean.
- **Found, not fixed (follow-ups):** (1) ICU and newborn bed money still have no rows (named list, guarded by a test); same fix shape, but they have no showcase story and the newborn rule counts `expected_try` without netting billed lines, which needs its own check. (2) The cohort table's `top_action_type` (`recovery_summary.py`, both the live and the cached-payload path) has no key for the four puan motors, so S3 and S4 read `none` next to 928.09 and 370.50 recoverable (S1 `strategy`, S2 `yatak_puani`, S7 `capture_gap`). (3) The payment-method bucket of the exposure has no audit row and its `billing_strategy` `compliance_violation` row carries no amount, so on a bill like the S1 bill with an expensive drug line added the KPI (15,877.94) has no amount row; attaching the amount to the strategy row also changes that row's `billed_try` in the cohort compliance index, hence a decision of its own. (4) The cohort compliance index (`COMPLIANCE_INDEX_SURFACES`) does not list `audit_exposure`. (5) The new rows carry no `clause_ref`, so the "inspect clause" button is disabled on them (as on the bed-day row). (6) Cached reports do not contain the rows until the cache is rebuilt; the staging update is Safa's call.

### Out of Scope
ICU and newborn bed rows (same fix shape, own amount rules, no showcase story); the payment-method bucket rows; the cohort compliance dashboard for the new surface; `clause_ref` links on the new rows; the S8 divergence itself (#311 item 6); prescription dose fields and drug prices; anything under `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`, `data/synthetic/demo_vignettes.json`; the staging update and the cache rebuild (Safa's call).

## Task: Synthetic v3 P7-lite — the 8 showcase patients replace the legacy 50 in `data/synthetic/sut/` (2026-10-18)

### Goal
The app's synthetic demo data (`data/synthetic/sut/`) is the v3 showcase cohort (8 patients, 8 bills, 3 clean tables), written there by `python -m scripts.synthetic.cohort.build`; nothing in the repository still pins the legacy 50-patient set or can regenerate it; the engine and the UI run on the 8 patients; every pin of the inventory is migrated.

Started by Safa on 2026-10-18 ("A: take the 8 showcase patients into the app now, with the part of P6 that is needed"). Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (P6, P7); inventory `plans/data/2026-10-17-p6-p7-legacy-pins.md` (50 rows). Out of scope: the other 42 patients and the remaining pathways, E2 hardening, the lab realism items (#309), drug prices (Q4), the staging update (Safa's call), the engine defects #289-#307.

### Decisions (judgment)
- **Layout:** the builder's default output directory becomes `data/synthetic`; it writes `sut/claims`, `sut/clean` and `cohort_registry.json` under it. `data/synthetic/showcase/` disappears (`git mv`), its `README.md` becomes `data/synthetic/README.md`. The registry lives at `data/synthetic/cohort_registry.json`.
- **Tests and scripts read the registry,** through the new `tests/fixtures/synthetic_cohort.py` (roles `default_landing`, `showcase_S1` to `showcase_S8`, counts from the registry) and, for Node, by reading the JSON directly. No patient id, tag or amount is hard-coded. `pyproject.toml` does not change (its bytes are pinned by `data/gazette/sut_coverage_evidence.json`).
- **Legacy machinery goes with the data,** once a grep shows nothing live imports it: `scripts/synthetic/gen/`, `exporters.py`, `specs.py`, `generate_sut_synthetic_data_v2.py`, `validate_sut_synthetic_data.py`, `assert_tier_a_post_regen.py`, `build_acibadem_mapping_workbook.py`, `cohort_tiers.py`, `demo_config.py`, `vignettes.py`, `fault_injection.py`, the two xlsx workbooks, `demo_manifest.json`, `demo_cohort_tiers.json`, `DEMO_COHORT.md`, and the tests of those modules. `data/synthetic/demo_vignettes.json` stays byte-identical: the paused strict lane pins it (`scripts/deploy/generate_candidate_source_roster.py:28`).
- **A legacy-data test that protects engine logic** is rewritten on the registry roles or on a self-made fixture. A test that only pinned legacy ids or amounts is deleted, with a one-line reason in the Results. Engine behaviour on the 8 stories is already pinned by `test_cohort_engine_proof.py`.
- **Not touched:** `scripts/deploy/**`, `docs/operations/**` and `tests/*/deploy/**` (the paused strict lane triggers on those paths), and `src/` unless a test proves a change necessary (the coverage evidence pins source hashes).

### Subtasks
- [x] 1. Slice S, the swap: builder default and registry location, `git mv` of the data, deletion of the legacy data and machinery, cohort scripts, tests and docs re-pointed to the new location, `tests/fixtures/synthetic_cohort.py`, `data/synthetic/README.md`. Done when `build --check` passes at the new location, the loader's default directory loads the 8 patients, the cohort tests are green and nothing imports a deleted module. Done in 5fd1ba46 (78 files, +759 / -8,049): `build --check` exit 0, a fresh build changes nothing, the default loader gives 8 claims and 8 patient totals, 3,853 tests in `tests/unit/synthetic` and `tests/unit/scripts` pass.
- [x] 2. Slice T, the Python tests of the inventory (rows 1 to 19, 24 and 26): migrated or deleted as decided above. After Safa asked to speed it up, the work list was split over three parallel Claude agents with the same rules: T1 (a32958b2: rows 1 to 8), T2 (eb979ac0: rows 9, 11, 12, 14, 15, 18 and the silent-skip API file), T3 (32b7e3c9: rows 10, 13, 16, 17, 19). 21 files: 1 deleted, 20 rewritten, none left as it was (per-file table in the Results). Row 24 (`tests/unit/scripts/test_synthetic_material_prose_flags.py`, a check of the legacy generator's flags) went with the generator in slice S; the loader's reads of those flags are covered by `test_loader.py` (T2). Row 26 is `scenario_tag` labels in provenance dicts, not pins: those tests pass untouched.
- [x] 3. Slice F, the frontend scripts, the chatbot tool text, the docs and the plan status (rows 36 and 43 to 50). Done in 5d78c413; 7d26d7d2 corrects two assertions of `verify-workspace-views.mjs` after the live check.
- [x] 4. Gates: ruff, the full suite, `compile_rules.py --check`, manifest parity, the CI-image backend gate on a clone, vitest for the frontend. Done on the tip 32b7e3c9 (numbers in the Results).
- [x] 5. The UI: run the backend and the frontend on the new data and walk the default landing, the 8 patient workspaces and the cohort pages in the browser; list what is wrong (Safa reviews too). Done for S1 and S7 by hand; the engine's output for all 8 stories was listed in-process (see Results).
- [x] 6. PR #316, squash-merged by Safa 2026-10-18 10:14 UTC (2804f468).

### Results (2026-10-18, branch `claude/synthetic-v3-p7-lite-swap`)
- **What changed:** `data/synthetic/sut/` holds the v3 showcase cohort (8 patients `SENTETIK-HASTA-0001..0008`, one bill each; 9 claims tables and 3 clean tables) and `data/synthetic/cohort_registry.json` is the registry; `python -m scripts.synthetic.cohort.build` writes both and `--check` passes. The legacy 50-patient parquet files, the two xlsx workbooks, `demo_manifest.json`, `demo_cohort_tiers.json`, `DEMO_COHORT.md`, the legacy generator and validators (25 script files) and their 7 tests are gone, so nobody can regenerate the old set over the new one. `data/synthetic/demo_vignettes.json` is byte-identical (the paused strict lane pins it). Tests and scripts read the registry (`tests/fixtures/synthetic_cohort.py`, `frontend/scripts/lib/cohort-registry.mjs`); no patient id, tag or amount is hard-coded any more. Not touched: `scripts/deploy/**`, `docs/operations/**`, `tests/*/deploy/**`, `.github/**`, `pyproject.toml`; `src/` changed in two example strings of `chatbot/tools.py` and four READMEs only.
- **Test migration (T), per file:**

| Test file | Verdict | Reason |
|---|---|---|
| `domain/billing/test_sgk_uplift_synthetic_demos.py` | deleted | 79 pins on 32 legacy scenario tags; every block has a detector or wiring test elsewhere (`test_optional_override_surfacing`, the `*_wiring.py` tests, `prose_rules/test_medula_rejection` and `test_claim_readiness`, `test_pricing_boundaries`, `test_report_exactness`, `test_claim_drug_indication`, the engine proof on S7) |
| `domain/billing/test_billing_actions.py` | rewritten | S4, S5, S1 through the registry; two self-made tests for the `optional_override` and `material_uplift` rows (no story produces them); S4 re-billed as `poliklinik` in memory is the only coverage of the ORTAK-5 outpatient rule |
| `domain/test_billing_strategy_exactness.py` | rewritten | binds to S1 (package row, `mandatory_compliance`, `DRG_MANDATORY`) |
| `domain/billing/test_claim_materials_precheck.py` (old :445-474) | rewritten | duplicate-code regression on S5's flagged implant with a twin line in memory |
| `domain/billing/test_claim_strategy_sut.py` (old :511-548) | rewritten | byte-exact "billed correctly as package" on S5, amount from the bill's package line |
| `domain/billing/test_session_uplift_patient_0013.py` | rewritten | S1 plus a second must-package operation added in memory |
| `domain/billing/test_lab_optimizer_sentetik_0001_002.py` | rewritten | S1, cwd-independent paths (also run from /tmp) |
| `domain/billing/test_session_uplift_patient_0001.py`, `test_drg_uplift_wiring.py` (old :331-343) | rewritten | the "clean control" lied (0001 is S1, a faulty bill); now the clean twins of the stories (no session, DRG or headline uplift) plus a positive control: a 2nd operation at full list price gives nothing, at 10% gives list x (0.30 - 0.10) and the headline moves by exactly that |
| `cache/test_copay_outcome_kind.py` | rewritten | no exempt or EK-2C-1 patient in the cohort: exempt, rate-capped, compliant and exempt-plus-capped built in memory (`tests/fixtures/t2_catalog_lines.py`); exempt outranks rate-capped |
| `domain/claims/test_loader.py`, `test_config.py` | rewritten | floors of 80 claims etc. became the registry's exact counts and ids; S5's flagged line from the registry; in-memory tests for `copay_rate`, `surcharge_rate` and the older prose flags |
| `domain/claims/test_ingestion_dates.py` | rewritten | a tmp copy with one valid MEDULA event (the cohort has 0), so the date conversion is no longer vacuous; the 2099 case has a control load |
| `domain/test_optimization_claim_context.py` | rewritten | no EK-2G or EK-2C-1 line in the cohort: self-made lines with exact counts, plus a cohort wiring test |
| `domain/billing/test_bill_billing_report.py`, `api/test_bill_optimization_api.py` | rewritten | a three-bill patient built with polars on a tmp copy (S2 and S5 bills filed under S1); the silent skips fail loudly now |
| `api/test_medula_rejection_queue_api.py` | rewritten (9 to 19 tests) | the cohort has 0 MEDULA events: tmp copy with 5 hand-made events; expectations computed from the rows; the committed queue pinned against the registry count |
| `domain/optimization/test_cohort_claim_integration.py`, `test_copay_rate_exposure.py`, `domain/billing/test_claim_integration.py`, `domain/claims/test_ingestion_optional_fields.py` | rewritten | vacuous floors and ceilings (`> 0`, `<= 2`, `0 == 0`, "share <= 100") became equalities against registry counts, independent catalog computations and in-memory controls |

  The agents mutation-tested their rewrites (T1: 9 in-memory mutants of the source; T2: 12; T3: 78 text mutants, 76 caught, 2 equivalent). Three file names still carry legacy ids (`test_session_uplift_patient_0013.py`, `..._0001.py`, `test_lab_optimizer_sentetik_0001_002.py`); suggested names `test_session_uplift_must_package.py`, `test_session_uplift_clean_control.py`, `test_lab_optimizer_claim_lines.py` (follow-up).
- **Frontend (F):** `capture-screens.mjs`, `lib/recording-kit.mjs`, `lib/capture-routes.mjs`, `verify-workspace-views.mjs` take their patients and amounts from the registry; `capture-screens` has a preflight that stops when the backend's patients or bills differ from the registry; two chatbot tool example ids; four READMEs; the two plans. `record-workflows.mjs` cannot complete its three workflows on 8 patients (no clause on the landing patient's top action, no material pre-auth action, no MEDULA events); `RECORDING.md` says so. vitest 112 files / 1,100 tests, eslint on scripts and `tsc --noEmit` clean.
- **UI (by hand, backend 8001 and frontend 3000 on the new data, throwaway local test account):** the landing (S1, `SENTETIK-HASTA-0001`) shows 3 tabs with badges 2 / 0 / 4, the compliance badge equals the At-risk findings KPI (2), the row `F-SENTETIK-HASTA-0001-001` with 4,122.06 TRY, the revenue KPI "Recoverable SGK uplift 4,122.06 TRY" and 4 document boxes ("Files ready 0 / 4"); S7 shows its capture gap (R101450, 1,138.22 TRY) and the EK-1A exemption review, and its clause drawer opens on 1.8.5 and closes with Escape. The Playwright browser binary is not installed on this laptop, so `verify-workspace-views.mjs` and `capture-screens.mjs` were not run as scripts: their assertions were replayed by hand. Two assertions were wrong for the new data and are fixed (7d26d7d2): the landing bill's compliance view has no "Recommended actions - itemized" table, so "exactly one" became "at most one"; the clause-drawer check matched only the Turkish kicker.
- **Gates (branch tip 32b7e3c9, 2026-10-18):** CI-image backend gate (`bilun-laptop-ci:20261008-runtime-complete`, CI's pinned Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1, on a shallow clone of the tip): `ruff check src/ scripts/` clean; **11,606 passed, 2 skipped, 0 failed**; `compile_rules.py --check` 119 artifacts byte-identical; manifest parity 0 issues; no tracked file changed by the run. Frontend: vitest 112 files / 1,100 tests passed, `tsc --noEmit` exit 0 (after deleting the `.next` folder that a local dev run leaves behind, whose generated types fail the check), eslint on `frontend/scripts` clean. Not run locally: `npm run build` and `verify_public_assets.py` (`frontend/src` is unchanged by this branch; CI runs them). The files this branch added or changed are ruff-clean; `ruff check tests/unit` has 49 older errors in files this branch did not touch, and `src/bilun/chatbot/tools.py` was already unformatted on `origin/main` (CI lints only `src/ scripts/` and does not run `ruff format --check`).
- **What the engine returns per story (in-process, `compute_patient_billing_report` on each bill):** S1 6 action rows (package compliance + 4 documents), S2 2 (bed points + 1 document), S3 2 (documents only), S4 2 (documents only), S5 7 (2 material bundling, submission check, 4 documents), S6 3 (indication mismatch + 2 documents), S7 1 (performed not submitted), S8 3 (documents only). **S3, S4 and S8 show their money in the KPIs but have no row that explains it** (anaesthesia points, companion and session uplift are not turned into action rows). Every page shows the "Partial exact" banner (prescription dose fields are null, drugs cost 0 TL).
- **Found by the test migration, not fixed (`src/` is out of scope):** `aggregator._aggregate_drug_discount_validation` (`src/bilun/domain/optimization/aggregator.py:220`) ignores `patient_ids`, so a subset summary counts every drug line of the dataset; all 19 cohort drug lines are 0 TL, so drug-discount validation is not exercised (Q4); the cohort has no EK-2G or EK-2C-1 line, so surcharge and copay-rate exposure are 0 on it; the MEDULA queue is empty on the committed data (tested on a tmp copy with hand-made events); the docstrings of `src/bilun/domain/claims/schema.py:5,225` and a comment in `prose_rules/gap_closing.py:351` still name deleted scripts.

### Out of Scope
The other 42 patients and the remaining pathways, E2 hardening, the lab realism items (#309), drug prices (Q4), the staging update (Safa's call), the engine defects #289-#307, the paused strict lane.

## Task: Synthetic v3 P4 — the cohort generator, showcase patients first (2026-10-17)

### Goal
`python -m scripts.synthetic.cohort.build` turns the 8 showcase recipes (pathway + pins + fault) into the files the app loads: the 9 claims tables, the 3 clean tables and `cohort_registry.json`. Every line is priced from the catalogs on its own date, the bytes are deterministic, and the answer rows come from the injection records. The app's loader accepts the files, the engine finds each injected fault with the proven amount, and a clean bill shows nothing.

Started by Safa on 2026-10-17: "the legacy dataset is going to get trashed", so there is no coexistence design; the legacy 50-patient files are replaced in P7. Until then the builder writes to `data/synthetic/showcase/`. Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D3, D4, P4, P5). Working rule: Claude orchestrates and verifies, Antigravity with Gemini 4 Argon implements (`agy -p`, one run per slice, tests as the judge; briefs in the session scratchpad; see memory `reference-argon-agy-runner`). **Changed 2026-10-17 about 18:30:** Safa's Claude usage limits reset and he asked for the rest of P4 to be done with Claude instead of Argon. The running Argon job (C2b) was stopped; from here the slices run on Claude subagents with the same briefs and tests as the judge, and I verify and commit. Argon stays the fallback if the Claude limits run out again. The session scratchpads live on tmpfs (`/tmp`) and the reboot at 20:05 wiped them; the briefs of this phase are rebuilt from the saved transcripts in `~/.cache/bilun-p4-scratch/briefs/` (persistent). Throwaway review worktrees: `.claude/worktrees/p4-e1-review` and `p4-c2-review` (remove them with `git worktree remove --force` when the reviews are done).

### Facts and decisions (judgment where marked)
- The target files, from the legacy cohort: `data/synthetic/sut/claims/` (claim_headers, claim_diagnoses, procedure_claim_lines, material_claim_lines, drug_claim_lines, expected_rule_outputs, patient_copay_profiles, performed_procedure_lines, medula_rejection_events) and `data/synthetic/sut/clean/` (anadata_clean, lab_clean, recete_clean); the app reads the first set through `load_sut_claim_dataset` and the second through `src/bilun/cache/`. Even the legacy narrative columns (YAKINMA, OYKU, Muayene Notu, Tedavi Notu) are placeholder text.
- New package `scripts/synthetic/cohort/` (Polars; the legacy `scripts/synthetic/gen/` stays untouched until P7). Ids follow the legacy formats (patient `SENTETIK-HASTA-NNNN`, claim `F-<patient>-NNN`, episode `B-...`, lines `ISL-`, `MLZ-`, `ILC-<claim>-NNN`, diagnoses `TANI-<patient>-NNN-NNN`, performed `EMR-<claim>-N`, answer rows `BEK-<claim>-<fault_id>`).
- Every line has `expected_payable_try == billed_amount_try` (no answer in a payable); drugs stay at 0 TL until the price list (Q4); EK-2B/EK-2C prices as-of the line date; EK-3/F-1 list price; rounding as the proofs (`ROUND_HALF_UP`, issue #299 stays open).
- Narrative texts are short Turkish sentences built only from structured fields (diagnosis names, procedures, dates); no invented clinical history. Lab results come from `data/synthetic/reference/lab_reference.csv`, one set per billed lab line.
- The golden for pricing is the proofs' priced bills `reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json … S8.json` (rows and totals, clean and faulty).

### Subtasks
- [x] 1. Slice A, compose: pathway bill (after `apply_fault`) plus an encounter context becomes priced claim objects (the dataclasses of `src/bilun/domain/claims/models.py`); equal to the proofs' priced rows for all 8 stories, clean and faulty. Done (Argon, 23 min): all 16 bills equal the proofs' priced rows.
- [x] 2. Slice B, claims tables and registry: recipes for the 8 showcase encounters, the 9 tables written from the claim objects with explicit schemas, injection records with real amounts, answer rows, `cohort_registry.json`; the real loader accepts the files; two runs give identical bytes. Done in two Argon runs: B1 (58 min) tables, schemas, writer, digest, loader round trip; B2 (23 min) recipes, injection records, registry, `build` command, committed `data/synthetic/showcase/`. The 8 amounts (4122.06, 667.08, 928.09, 370.50, 6465.27, 0.00, 1138.22, 5377.20) equal the proofs; two builds are byte-identical; `--check` caught 6 of my 6 mutations; the loader returns objects equal to the composed claims.
- [x] 3. Slice C, clean tables: anadata, lab, recete from the claims and the lab reference; the cache builder accepts them. C1 done (one Argon run, 2 h 38 min): `data/synthetic/cohort/showcase_clinical.yaml` (vitals, judgment, #309), `clean.py`, `clinical.py`; `anadata_clean` 8 rows and `recete_clean` 19 rows with the legacy dtypes, narratives built only from structured fields, comorbidity flags derived from the claim's ICD codes; `lab_clean` empty and typed with the extra column `parametre`; the cache loaders and the full `load_sut_build_context` (8 patients, 8 billing reports) accept the folder; six mutations of the clean files and registry all caught by `--check`. C2 (lab results) done, committed as f445ea0a: Argon run 1 (16:26 to 17:35) was killed from outside after 69 minutes, run 2 (C2b, 18:14 to 18:31) was stopped by me when Safa moved the work to Claude, and a Claude subagent finished it in 54 minutes from the C2b brief. `labs.py`, `lab_clean` with 207 rows (patients 1:16, 2:59, 3:17, 4:52, 6:40, 7:23; patients 5 and 8 are package bills and have none), a `drug_routes` block in the clinical YAML for the 4 prescription rows whose TİTCK name states no route, `test_cohort_labs.py` (192 tests, 91 of them mutation tests), and the row loops over DataFrames vectorised (the 96-row CSV reader keeps one `zip` over typed columns to build its spec objects). My own check, not the agent's report: 462 tests in the ten cohort files, ruff clean, `build --check` exit 0, two fresh builds byte-identical, engine proof equal to the earlier proofs, claims tables untouched; 15 of 20 mutations of my own caught for the right reason. The 5 not caught are the gaps slice E3 must close: impossible lab values (negative glucose, potassium 40) and prescription route, dose-unit and product sanity (null route, "1 bottle", CLEXANE as oral). Two independent reviews of C2 (code mutants; clinical plausibility of the 207 + 19 rows) are running.
- [x] 4. Slice D, engine proof: the engine over the generated dataset finds each of the 8 faults with the proven amount, and the clean twins show nothing (P7-lite for the showcase set). Done in two Argon runs (D 21 min, D2 14 min). The engine over the committed files equals the earlier proofs for all 8 stories (user-facing signals, direct detector rows, report scalars, totals; line ids compared by table and position, claim ids inside texts masked). S8 is the one documented divergence: the report shows `audit_exposure_try` 3584.80 (lenient 50% reading) while the record and the direct detector carry 5377.20 (same-incision 25% reading), because no claim line carries the incision (#311 item 6; `session_uplift.py:96-112`). Five consistent mutations of the data (S5 flag, S6 diagnosis, S8 ratio, S2 bed days, S7 CT billed) were all caught.
- [x] 5. Slice E, plausibility tests (P5) for the generated bills, and the list of pins and docs that P6 and P7 must change. (Pin list done: `plans/data/2026-10-17-p6-p7-legacy-pins.md`, 50 rows; plausibility tests pending.) Split in three: E1 (15 check ids: patient, clinical fit, stay, performed lines, package, anaesthesia) is done and committed as 8fffdcda (67 mutation cases, 143 tests; I re-ran it: the faulty bills trip exactly S1 `package.mode`, S2 `stay.bed_coverage`, S3 `anaesthesia.operation_pairing`, S7 `bill.performed_billed`, and the 8 clean twins trip nothing); E2 (10 ids: materials, prices, money, labels) is committed as 0aea1e34 in E1's module; E3 (12 ids: lab value bounds, flag and unit, result sets against the bill, blood-gas and eGFR relations, prescription route, dose unit, required fields, vitals; the gaps my C2 mutations found) is committed as d7765943 in a module of its own, `plausibility_clean.py`, so that it does not depend on the claims checks or on the generator. Independent mutation reviews of E1, E2 and E3 found the tests weaker than they looked (70%, 72% and 84% of mutants caught); E1 and E3 were hardened (all observable survivors killed), E2's hardening is left for a follow-up PR. `plausibility_all.py` is the single entry point over both families. Every id gets a mutation test; the clean twins must trip nothing and the faulty bills must trip a pinned set.
- [x] 6. (Done; results below.) After every slice: I run the gates (ruff, pathway/fault/cohort tests, full suite under the shared lock, `compile_rules.py --check`, parity, the CI-image gate at the end) and an independent read-only review before the PR.
- [ ] 7. PR(s), CI green, Safa merges.

### Results (2026-10-18, branch `claude/synthetic-v3-p4-generator`)
- **What exists:** `python -m scripts.synthetic.cohort.build` writes the 9 claims tables, the 3 clean tables and `cohort_registry.json` of the 8 showcase patients into `data/synthetic/showcase/`. The engine over those files reproduces the earlier proofs for all 8 stories (S8: report 3,584.80 against record 5,377.20, issue #311 item 6). The legacy 50-patient files are untouched until P7.
- **Clean tables:** `anadata_clean` 8 rows, `recete_clean` 19, `lab_clean` 207 (patients 1:16, 2:59, 3:17, 4:52, 6:40, 7:23; 5 and 8 are package bills and have none). The lab values come from a deterministic SHA-256 draw over `lab_reference.csv` with per-patient states (judgment, clinician review #309).
- **Plausibility checks (P5, first version):** `plausibility.py` (25 claims ids), `plausibility_clean.py` (12 clean-table ids) and `plausibility_all.py` (one entry point, `check_all_plausibility`). The 8 clean twins trip nothing; the committed faulty bills trip exactly S1 `package.mode`, S2 `stay.bed_coverage`, S3 `anaesthesia.operation_pairing`, S5 `material.stray_flag` and S7 `bill.performed_billed` (S4, S6 and S8 are invisible to plausibility by design: only the engine sees them). 2,076 cohort tests.
- **How it was built:** Argon (`agy`) did slices A, B, D and C1. After Safa's Claude limits reset on 2026-10-17 about 18:30, the rest ran on Claude subagents from briefs (kept in `~/.cache/bilun-p4-scratch/briefs/`), and I checked and committed every slice myself (tests, ruff, `build --check`, engine proof, mutations of my own). Independent mutation reviews of E1, E2, E3 and of the C2 lab code, and a clinical review of the lab and prescription tables (`reports/synthetic-data/2026-10-17-c2-lab-clinical-review.md`), each found the tests weaker than they looked.
- **Found by the reviews and fixed:** E1: null and zero quantity passed, a 6-night stay billed as 510120 passed, the ICD sex gate covered 83 codes, word lists had false negatives; **`pl.format` panics in polars 2.0.0 (the CI lock) on a larger table**, in the module since its first commit. E3: row-order dependent copy numbers, phantom findings from join misses, silent skips, route-word false positives. C2: validator gaps (null unit, kohort/donem, midnight timestamp, decimals, null age, sex code) and an R1 tolerance 10^13 times the real residual; the row loops of `validate_clean_tables` broke AGENTS.md section 9. The first CI-image gate failed one test (raw Parquet bytes against the committed file, polars 2.0.0 writes another footer); it compares content now.
- **Gates (2026-10-18, branch tip 170e36ee = `origin/main` 7a70ddb8 merged in, the one conflict was in this file):** CI-image backend gate (`bilun-laptop-ci:20261008-runtime-complete`, CI's pinned Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1, on a shallow clone of the tip): ruff clean; **11,591 passed, 2 skipped, 0 failed**; `compile_rules.py --check` 119 byte-identical; manifest parity 0 issues; no tracked file changed by the run. The earlier gate on d7765943 had one failure (raw Parquet bytes against the committed file under polars 2.0.0); it compares content now. `main`'s own CI was green on the latest runs. The commit after the gate changes `tasks/todo.md` only.
- **Open, for follow-up PRs:** E2 hardening (the reviewer's 57-case proposal in `~/.cache/bilun-p4-scratch/r3/` kills 48 of its 58 survivors; the module is correct on everything tried); the lab and prescription realism items of the clinical review (CRP course between samples, D-dimer 710 against the story's 920, troponin pair, red-cell indices re-drawn per sample, too-tidy normals, levodopa timing and route in S6, no IV fluid in S4) wait for #309; `lab_result_id` is empty on all 48 billed lab lines (the checks pair lab sets with bills by patient, episode, day, code and order); EK-3/F-1 amendments dated 24/01/2026 are treated as in force from the list start 2025-12-13; drug prices stay 0 TL (Q4); the other pathways, the 42 non-showcase patients, P6 and P7.

### Out of Scope
The other pathways of the first 20 and their clinical review (#309), the 42 non-showcase patients and the sampling from the public-statistics anchors (another session, branch `claude/synthetic-v3-population-anchors`), drug prices (Q4), the test-pin migration and the swap of the legacy files (P6, P7), staging, engine defects #298–#307.

## Task: Synthetic v3 P3 — fault registry, injection log and answer key (2026-10-17)

### Goal
Every injected fault of the demo cohort is declared once in a registry (SUT clause, the engine rule that must fire, the mutation applied to the clean bill, the expected detection and TL effect), every injection is written to a log in the same generator run, and the answer rows the app reads come from that log instead of the generator's own sums.

Approved by Safa on 2026-10-17 ("yeah go on"). Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D4, P3). New working rule (Safa, 2026-10-17): Claude orchestrates only; implementation runs on Antigravity with Gemini 4 Argon (`agy -p`, Cloud-project ADC), one run per slice, in an isolated worktree with its own permission file; Claude plans, briefs, verifies and reports.

### State found before starting
- PR #308 (pathways S1–S8, `expand`, golden bills) is merged; `main` at 98861219.
- Issue #240 (the loader demanded exhaustive answer rows) is closed by PR #246 (75b82fa4): `validate_expected_outputs` now checks only the rows that are present. So the loader work the plan expected for P3 is probably done; the design confirms it from the code.
- Open input: Safa675/Bilun#311 (format limits; items 4 to 6 matter here: expanded rows carry no line reference, S1's fault needs an itemized sibling pathway, `ayniFarkliKesi` has no field).

### Subtasks
- [x] 1. Design (phase 1, Argon): `plans/data/2026-10-17-p3-fault-registry-design.md`. Run 1 (11 min) ended with an empty answer because the final write was refused (a path under `.claude/` is not auto-allowed; a refused call ends the run silently); its document was recovered from the conversation log and turned out to contain invented pathway ids, rule names, files and line anchors (10 missing files, 7 bad anchors, 46 unknown identifiers). Run 2 (26 min) corrected it from a ground-truth table with a mechanical gate (every path exists, anchors inside the file, every identifier found in the repository or declared under "Proposed new names").
- [x] 2. I checked the design against the code (columns of `ExpectedRuleOutput`, `validate_expected_outputs`, the non-empty rule in `synthetic_demo`, `_line_itemized_payable`, zero readers of `expected_outputs` in `src/`, nine detector functions at their lines, prices of both walkthroughs against `results/`, SUT clause texts). One error found (S8 cited C000674, the +25 points rule) and fixed. The three open questions were engineering choices and are decided: Option A each. Slice 3 amended: mutations are proven against golden *faulty* bills exported from `stories.py`, not by importing the proofs harness into a test.
- [x] 3. Implementation slices (phase 2), one Argon run each, brief and permission file per run, I commit after verifying:
  - [x] Slice 1: `expand(..., annotate=True)`, golden faulty bills (`tests/fixtures/pathways/golden_faulty/`), S1 itemized sibling pathway `data/synthetic/faults/siblings/` (13 min, 481 pathway tests).
  - [x] Slice 2: registry schema, loader, 26 check ids and `data/synthetic/faults/fault_registry.yaml` for the 8 faults (21 min, 533 tests).
  - [x] Slice 3: `apply_fault`, `FaultInjectionRecord`/`make_record`, `build_expected_rule_outputs`; every fault equals its faulty golden, the rows pass the real `parse_expected_output` and `validate_expected_outputs` (29 min, 564 tests).
  - [x] Slice 4: fixes from the independent review (20 min, 585 tests): see Results.
- [x] 4. Independent read-only review (Claude, 35 code and 20 data mutants, loader readers, fit with P4/P7): found 5 defects, 14/35 and 12/20 mutants caught; its 12 probe tests are now tests.
- [x] 5. Gates: ruff (CI scope), full suite under the shared lock, `compile_rules.py --check`, manifest parity, the CI-image gate (clone and venv deleted afterwards).
- [ ] 6. PR, CI green, review comments read, Safa merges.

### Results (2026-10-17, branch `claude/synthetic-v3-p3-design`)
- **Built:** the fault registry (8 faults, 6 operations, 28 check ids with mutation cases), `apply_fault` (a fault that changes nothing, a dangling link or a stay outside the window is an error; `fault_window` for P4), the injection record, the answer rows, the S1 sibling pathway and the golden faulty bills. No `src/` change; the loader needs none (PR #246).
- **Tests:** 9,493 passed, 2 skipped, 0 failed (9,260 before); 233 new tests. `compile_rules.py --check` OK, parity 0 issues.
- **How it was built (new working rule):** the implementation ran on Antigravity with Gemini 4 Argon (`agy -p`, Cloud-project ADC); Claude wrote the plan and the briefs, ran every gate and reviewed. Six Argon runs (two for the design), about 2 hours of Argon time and about 3.5 million tokens in all, roughly 20 TL of Cloud credit (an estimate from the earlier price per million tokens).
- **What went wrong and what it taught:** run 1 of the design ended with an empty answer because its last write was refused (a path under `.claude/` is not auto-allowed and a refused call ends the run silently); its document, recovered from the conversation log, contained invented pathway ids, rule names, files and line anchors (10 missing files, 7 bad anchors, 46 unknown identifiers). Run 2 corrected it from a ground-truth table with a mechanical checker as its exit gate, and I re-checked the claims that carry weight; one wrong SUT clause (C000674) remained and was fixed. Code runs were safer because the tests decide.
- **Review findings fixed:** the expected findings were only shape-checked (now pinned); `apply_fault` ignored a narrower window of the S1 sibling (a stay before 2026-04-16 produced band-C anaesthesia); a test comment and its totals did not match `results/`; the README promised `FaultApplyError` for failures that raise `ExpandError`; a dropped procedure left materials linked to nothing.
- **Open for later phases:** `FaultId` forces the `S<n>` form while `story` may be null (Tier-B faults, P4); `detectable` and `tier` belong to the cohort registry (P4); three readers depend on the v2 shape of `expected_rule_outputs` (P6).

### Out of Scope
The generator (P4), regenerating the cohort (P7), pathways beyond S1–S8, the engine defects #298–#307, staging.

## Task: Public-statistics anchors for the synthetic v3 cohort (2026-10-17)

### Goal
`data/synthetic/reference/population_anchors.yaml` holds the public statistics found on 2026-10-16 (stay length, utilisation, operations, ICU, diagnoses, age, sex, money), each with source, year, scope and confidence, and a test refuses any row that lacks them.

### Subtasks
- [x] 1. Merge the four research files (`anchors_moh_yearbook` 37, `anchors_moh` 33, `anchors_sgk` 29, `anchors_oecd` 20 rows, 119 in all) into one deduplicated `population_anchors.yaml`:
  - values, units, years, scopes, sources, caveats and confidence are copied unchanged, never retyped (a script does the merge);
  - `merged_from` lists every origin row, and each input row is used once;
  - the same fact in two files becomes one row; rows that disagree are kept side by side (`conflicts_with`); a derived row says what it derives from, and is marked superseded when a source publishes the number.
- [x] 2. `scripts/synthetic/reference/population_anchors.py`: loader and validator (`validate_population_anchors` returns error strings).
- [x] 3. `tests/unit/synthetic/test_reference_population_anchors.py`:
  - the committed file validates;
  - one mutation test per validator rule (a seeded defect must be reported);
  - arithmetic checks on the key rows (sector sums, derived average stay, operation groups, ICU types);
  - Türkiye's average stay is 4.2 days, never 4.7 (4.7 is Mexico's value in the OECD data).
- [x] 4. `data/synthetic/reference/population_anchors_notes.md`: what was found, what was not found, caveats, the merge log, and the downloaded files (name, URL, size, sha256, deleted after reading).
- [x] 5. Independent provenance check, written by someone other than the implementer: every output value equals an input value, and every input row is used once.
- [ ] 6. `ruff`, the new tests, `tests/unit/synthetic`, then the full suite under the shared lock; CI green before merge; PR review check.

### Out of Scope
- Engine code (`src/`), the generator, the pathways, and choosing target distributions (age mix, stay length of the cohort). They use this file later.
- New research or downloads.
- Real data. Everything here is published aggregate statistics.

### Who does what
Implementation: Antigravity running Gemini 4 Argon, as Safa asked on 2026-10-17. Verification, commit, push and PR: Claude.

### Results
- **Counts:** 119 input rows (`anchors_moh_yearbook.yaml`: 37, `anchors_moh.yaml`: 33, `anchors_sgk.yaml`: 29, `anchors_oecd.yaml`: 20) -> 117 output rows (73 `primary`, 40 `supporting`, 4 `superseded`), 2 merged rows, 4 superseded rows, 40 supporting rows (across 22 primaries), 20 distinct symmetric `conflicts_with` pairs, and 8 `derived: true` flags added (on top of the 9 already present in `anchors_moh_yearbook.yaml`).
- **Tests (`tests/unit/synthetic/test_reference_population_anchors.py`):** 25 passed in 0.41s (schema validation, mutation tests for all 7 rules including the 12-case parametrized Rule 2 sub-check test, 4 arithmetic checks, and the 4.7-day Mexico vs 4.2-day Türkiye check).
- **Lint (`/home/safa/miniforge3/bin/ruff check scripts/synthetic/reference tests/unit/synthetic`):** All checks passed!
- **Independent check (Claude, 2026-10-17):** a script written apart from the implementer (kept outside the repo) compares every output row with its origin row. Result on the committed file: OK, 0 problems. Each of the 119 input rows is used once, every copied field equals its origin, no reference is broken, 4.7 is never given to Türkiye, and 11 figures read in the yearbook text are present. The script was first tried on a faithful file (passes) and on four seeded defects (changed number, dropped row, Türkiye = 4.7, changed unit; all four fail).
- **Local gates (2026-10-17, on the final tree):** `ruff check src/ scripts/` clean; full suite `python -m pytest -q -n auto` under the shared lock: 9,285 passed, 2 skipped, 0 failed; `compile_rules.py --check` 119 artifacts byte-identical; `audit_manifest_parity.py --drug-only` 0 issues. CI on the PR and the PR review check are still to do (box 6).
- **Run notes:** Argon (`gemini-4-argon-high` through the `agy` CLI) ran twice. Both runs ended on a Vertex AI 429 quota error: the first before the notes file existed, the second after all the work was on disk. What is on disk was verified by the checks above, not taken from Argon's report.
- **Corrections made in review:** (1) the notes said "36 OECD/Eurostat procedure counts", a number typed into the generator script; the anchor holds 17 procedure types for 2019 and 2024, so the text now says that. (2) Caveat 5 claimed that average stay in days runs about one more than nights; no source read says so (the instruction that asked for it was an unverified assumption), so it now says the sources do not state how same-day stays or the discharge day are counted.
- **For the generator (P4):** `conflicts_with` mixes real disagreements (same fact, different values) with different counting bases (e.g. institutions active during 2024 vs on 31.12.2024). The merge log classifies each of the 20 pairs. The flag does not mean "pick one".


## Task: Synthetic v3 P2 — care pathways for the 8 showcase stories (2026-10-16)

### Goal
`data/synthetic/pathways/` holds one YAML pathway per showcase story (S1–S8). A loader and a test suite reject a wrong code, name, date window, diagnosis or field. Each pathway, instantiated with its story's pins, reproduces the reviewed clean bill line for line.

Approved by Safa on 2026-10-16 ("okey do it"). Plan: `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md` (D2, phase P2). Inputs: `plans/data/2026-10-15-showcase-stories-draft.md`, `reports/synthetic-data/2026-10-15-showcase-proofs/stories.py`, `reports/synthetic-data/2026-10-16-v3-drafts-review.md`.

### Format decisions (judgment; P3/P4 may extend the schema, so it carries `schema_version: 1`)
- One file per pathway, `data/synthetic/pathways/<id>.yaml`. Code in `scripts/synthetic/pathways/` (`schema.py`, `loader.py`, `expand.py`); tests in `tests/unit/synthetic/test_pathways_*.py`.
- The content is the reviewed clean story. It is generalized only where a range is natural: patient age and sex, nights of stay, drug course days, optional lines with a probability. No clinical item (procedure, lab, drug, material, diagnosis) is added that the story does not have.
- Every line and every range carries `basis` (`sut`, `ek2b_aciklama`, `medula_kilavuz`, `guideline`, `judgment`) and a short `source`. Lines waiting for a field answer carry `pending` (`#297 Q2`, ...).
- Not in a pathway: faults (P3 registry), prices (read from the catalogs on the line date), the synthetic-only `package_candidate` flag, drug prices (Q4).
- A `showcase` block holds the story's pins (patient, dates, choices). It may move into the fault registry in P3.
- Names sit next to codes for review and are tested against the catalog on the line date, as in `code_sets.yaml`.
- Golden clean bills: `tests/fixtures/pathways/golden/S1.json`…`S8.json`, exported from the clean variant of each story in `stories.py` by `reports/synthetic-data/2026-10-15-showcase-proofs/export_clean_lines.py` (line identities only, no prices). A different agent writes the golden and the pathway, so the golden cannot be fitted to the YAML.

### Subtasks
- [x] 1. Branch `claude/synthetic-v3-p2-pathways` from main f5d2973d and this plan block.
- [x] 2. Golden export: `export_clean_lines.py` with a `--check` mode, 8 JSON files, a well-formedness test (agent F; 89 tests; I re-checked the files and the counts).
- [x] 3. Schema, loader, deterministic expander, catalog-validity checks with a mutation test for each, pathways S1 and S2 (agent A).
- [x] 4. I reviewed the schema and S1/S2 and ran A's throwaway drafts of S3-S8: all six load and expand to their goldens, so the format fits.
- [x] 5. Pathways S3-S8, one agent each (all six passed the checks and the round trip on the first run).
- [x] 6. Two independent reviews: (a) fidelity to the stories, the review report and the SUT sources, 10 dimensions over all 8 pathways; (b) strength of the checks and tests: 105 hand mutations, 3,598 single-leaf mutants, 89 mutants of the toolkit code, fit with P3/P4/P5.
- [x] 7. Fix-up of the findings (agent X: toolkit, tests, README, S2, proofs harness; agent Y: source texts of S3-S8). I re-ran nine of the reviewers' mutations by hand against the fixed toolkit: all caught.
- [x] 8. Gates: ruff; the pathway tests; full suite under the shared lock; `compile_rules.py --check`; manifest parity (sequentially, not at the same time); the CI-image backend gate on a clone.
- [x] 9. Plan status (P2 first step) and this block's Results.
- [ ] 10. PR, CI green, review comments read and classified; Safa merges.

### Results (2026-10-17, branch `claude/synthetic-v3-p2-pathways`)
- **8 pathways** (S1-S8) in `data/synthetic/pathways/`. With its own pins each one expands to the golden clean bill of its story (codes, dates, quantities, specialties, links, flags). The goldens come from `stories.py` through `export_clean_lines.py`; a test runs its `--check`, so a pathway and its golden cannot be changed together.
- **Toolkit** `scripts/synthetic/pathways/`: a pydantic schema that forbids unknown fields, a loader, a pure 152-line expander and 55 check ids (catalog identity on every window day, SKRS leaf ICD codes, EK-4A barcodes, lab table, package mode and window, anaesthesia band, sessions, stay coverage, pins, hygiene), each with a mutation case.
- **Tests:** 352 pathway tests (1 skipped: S7 has no stay). Full suite: 9,260 passed, 2 skipped, 0 failed (8,908 before). `compile_rules.py --check` OK (119 artifacts), manifest parity 0 issues.
- **A real defect was found by the review and fixed.** EK-4A `valid_until` is exclusive (the catalog's own docstring and `ek4a_as_of.py:152` agree); the pathway checks, the proofs harness and `cat.py` read it as inclusive. S2's window ended 2026-08-29, one day after KLACID 500 MG IV left EK-4A; now 2026-08-28, and a narrowed window must give its reason (`Window.source`).
- **Guard strength.** Before the fixes the toolkit guarded the pinned bill well but little else: 53 of 105 hand mutations survived and 37 of 89 code mutants. Fixed or documented: golden sync (`--check` in a test), bed/companion scaling with the nights (`stay.coverage`), an optional indication diagnosis, a pinned course past discharge, ANON/price/ID text, `.yml` files. Re-run after the fixes: 108 code mutants, 0 survive. What is guarded by review only (required/optional toggles, widened ranges, probabilities, notes, source edits) is listed in the README under known limits.
- **Source texts:** where the pathways said "certain" and the review says "güçlü çıkarım" (discharge day on the bed line, R07.1 as principal) they now carry the label; one clause that did not fit (C000603) was removed.
- **For the clinician reviewer (Q3):** `reports/synthetic-data/2026-10-17-pathways-judgment-list.md` lists the 77 `judgment` items and the observations the pathway writers raised (S4's whole-box paracetamol and 5-day antibiotic course, S6's PK-Merz/levodopa overlap, ...). The stories were not changed.
- CI-image backend gate (`bilun-laptop-ci:20261008-runtime-complete`, clone of 5f9aae31, CI's pinned pandas 3.0.6 / polars 2.0.0): ruff clean, 9,260 passed, 2 skipped, 0 failed, `compile_rules.py --check` OK, parity 0 issues. The commit after it changes `tasks/todo.md` only.

### Definition of done
1. `data/synthetic/pathways/` has 8 pathways (S1–S8); each loads through the loader.
2. Every code, name, barcode and ICD-10 code is checked against its catalog across the declared service window; a seeded defect of each kind makes the matching check fail.
3. For every pathway, `expand(pathway, pins)` equals its golden clean bill (codes, dates, quantities, specialties, links, flags). The exporter's `--check` shows the committed goldens equal a fresh export of `stories.py`.
4. Every range and optional line has `basis` and `source`; the `judgment` ones are listed in the PR for the Q3 reviewer.
5. ruff clean; new tests, full suite, `compile_rules.py --check` and parity pass; CI green; review comments read.
6. No patient data, ANON_ identifiers, prices or ILAY content in the YAML or the goldens.

### Out of Scope
- Fault registry, injection log, the answer-key loader change (P3).
- The composer with sampling and pricing, the generator, regenerating the cohort (P4, P7).
- The other ~12 pathways of the first 20.
- ER takip bills for S1 (the story models the ward bill only).
- Clinician sign-off of the ranges (flagged `judgment`; Q3 reviewer).
- Drug prices (Q4), the engine defects #298–#307, the staging update.

## Task: Review the synthetic v3 drafts on Safa's behalf — stories, lab table, ICD/drug notes (2026-10-16)

### Goal
Answer the open review questions with evidence and correct the drafts, so the v3 generator (P3/P4) has an approved recipe. Safa then confirms only the answers that need field knowledge.

### Subtasks
- [x] 1. Answer the SUT/MEDULA questions with clause ids, docs/medula and public sources, each with a confidence label:
  - stories: Q1 bed days, Q3 S1 realism, Q4 session amounts, Q6 KDV, Q7 drug boxes, Q9 companion, Q10 rounding, Q11 ICU takip;
  - lab: Q1 LDL billing, Q2 "birlikte faturalandırılmaz".
  - Done: `reports/synthetic-data/2026-10-16-v3-drafts-review.md` (answer tables with evidence and confidence).
- [x] 2. Clinical plausibility review of S1–S8 and the lab panels and ranges:
  - stories: Q5 S8 incision, Q6 cemented stem + cement code, Q8 R-codes;
  - lab: Q1 LDL, Q3 analyzers.
  - Done: same report ("Story corrections", "Lab table corrections").
- [x] 3. Data validity on current `main` (257d1e89):
  - every story code against the catalogs on its date, ICD against SKRS, drugs against EK-4A and the crosswalk;
  - re-run the proofs;
  - ICD/drug Q1–Q6; lab Q4.
  - Done: same report; found the EK-3/F-1 cement gap (fixed below).
- [ ] 4. Consolidate:
  - [x] one review report with each answer, its evidence and confidence;
  - [x] apply the corrections to the drafts and `stories.py` (branch `claude/v3-drafts-review-corrections`, results below);
  - [ ] one docs PR (the main session opens it).
- [ ] 5. Safa confirms the short list of field-knowledge answers.

### Results (2026-10-16, branch `claude/v3-drafts-review-corrections`)
- Stories S1–S8 corrected as the review lists. Proofs on 257d1e89 (`src/` unchanged): every target fires (S1 4.122,06; S2 667,08; S3 928,09; S4 370,50; S5 6.465,27 at risk; S6 indication mismatch; S7 1.138,22; S8 5.377,20, report 3.584,80) and every clean bill is 0 TL. N7 is the only open noise item.
- EK-3/F-1 cements AP3180–AP3250: the orthopedic extractor skipped coded rows with a blank first cell (their "KALÇA/DİZ" site was repealed 30.04.2024, not the rows). Fixed, rebuilt in the CI image (337 → 345 rows, deterministic). A full rebuild differs from main only in this file.
- Engine defects from the review filed as #298–#307 (field-expert questions: #297, #295).
- Lab table corrections 1–6 applied; item 7 decided by Safa on 2026-10-16: the demo data follows the SUT's same-day exclusions. ICD table: `kind` and `is_leaf` added (regenerated from the committed table; the source workbooks were not on disk).
- Checks: full suite 8,908 passed, 1 skipped; `compile_rules.py --check` and manifest parity OK; the same CI backend gate in the reviewed image on a clone: ruff, 8,908 passed, compile and parity OK.

### Already answered
- Stories:
  - Q2: package window, decided 2026-10-16;
  - Q12: SKRS codes; replacements to apply;
  - Q13: noise; fixed by #259–#270 and #283/#288.
- Lab Q4: #270 and #271 merged.

## Task: Catalog dates (#226, #227), package-gap double count and capture-gap rounding, independent review of #283 (2026-10-16)

### Goal
- Bilun's EK-2B/EK-2C/EK-1A/EK-3O catalogs keep every row, from its own start date.
- A package-mandated bill shows the package gap once.
- Money totals keep their kuruş.
- An independent check confirms or refutes the 17 review findings on the merged session-rule code (#283).

### Subtasks
- [x] 1. PR A (#226 + #227), one branch because both change `scripts/sut/catalogs/price_history.py`:
  - Result: PR Safa675/Bilun#287 (3 commits; curated files rebuilt in the CI image, and a second rebuild gives the same bytes).
  - EK-2B: 69,546 → 70,932 rows (30 procedures back; 1,118 rows start after their list's date).
  - EK-2C: 24,063 → 24,164 rows; 140 rows start later.
  - EK-1A and EK-3O are dated.
  - Local suite and the in-image CI gate: 8,797 passed, 0 failed.
  - Showcase results and the 50-patient cohort are byte-identical.
  - Follow-ups:
    - EK-3O/EK-1A callers without a service date;
    - marker parsing in the other lists (EK-2Ç, EK-3x, EK-2G, EK-2C-1);
    - stale dental catalog.
  - [ ] EK-2B: strip the amendment marker from the code cell (as `extract_ek2c` does), and keep the amended row over the older one.
  - [ ] Every curated row gets `valid_from` = its own Yürürlük marker date when later than the file date (`ek4a_history.py` is the model). The readers use it: `gazette.py:138-146`, `catalog_membership.py:103-119`.
  - [ ] EK-1A and EK-3O get a date column.
  - [ ] Rebuild the curated files inside the reviewed CI image (runbook "Local SUT package ingest"). Run the CI gate in the image.
  - [ ] Tests:
    - a marker row is kept;
    - 609541 exists from 2026-10-10;
    - P609541 does not match before 2026-10-10;
    - a row marked 2026-09-05 does not apply on 2026-07-07;
    - the showcase bills are unchanged.
- [x] 2. PR B (defects 1 + 2), PR Safa675/Bilun#286, branch `claude/fix-package-gap-double-count-and-rounding`:
  - [x] On a claim where the package is mandated but the bill is itemized, components the package includes (SUT §2.2.2.B-1(1): bed, companion, anaesthesia, exams, labs) add no itemized uplift inside the package window; days after the window still do (§2.2.2.B-1(4)). Faulty S1: SGK uplift 4,085.87, not 4,234.07. S4's companion uplift (no package) stays 370.50.
    - Measured: faulty S1 4,234.07 → 4,085.87 (companion row 148.20 → 0); S2 bed 667.08, S3 anaesthesia 928.09, S4 companion 370.50 unchanged; clean bills 0 TL. A 12-day mandated stay still expects 4 bed days (889.44) and 3 companion nights (222.30) after the window.
    - The mandate comes from the codes, not `package_candidate`: an EK-2/B line flagged "must use package billing" at the claim's tier, no package line for its code, an EK-2/C price and group on the day.
    - Exams and labs have no itemized uplift detector. Their capture-gap rows (separate headline) are not windowed yet: open question.
    - Cohort: SGK uplift 88,920.95 → 61,310.65 TL on 11 of 50 patients (mandated EK-2/C surgery billed itemized). The #269 gate still reads `package_candidate`, so these claims show no package gap until it is fixed.
  - [x] `capture_gap_try` keeps two decimals: S7 shows 1,138.22, not 1,138. Also `package_adequacy_review_try` (cohort 12,717 → 12,717.97).
  - [x] This PR also carries this block and the wave 2 record below.
- [x] 3. Independent review of #283 on `main`. Three read-only reviewers:
  - SUT correctness;
  - each of the 17 findings fixed or not, with probes, plus the cohort effect;
  - tests, and whether any gate relies on synthetic-only fields such as `package_candidate`.

  Confirmed bugs get their own fix PR.
- [x] 4. Per PR: targeted tests, the full suite, compile check, parity and ruff, run in sequence; showcase proofs before and after; CI on `main` green before each push.
- [x] 3a. Review results (2026-10-16): 15 of the 17 findings are fixed and 2 are partial. Must-fix problems still on `main`:
  - IONM P703365 and neuronavigation P614981 get the session cut despite C001389/C001413;
  - a mixed session prices every package at 100 % (C000670 says 25 %);
  - the #269 gate depends on the generator-only `package_candidate`;
  - "billed as package" has two definitions (category vs `P` code);
  - the package gap is stacked on itemized uplifts (= defect 1, PR B);
  - the exposure map keyed by code loses the primary on repeated codes.
- [x] 5. PR C (#283 follow-up), built on PR B's branch, because both need the code-derived "package mandated" predicate:
  - Result: PR Safa675/Bilun#288. It contains #286's commits, and main is merged in (c883b0df, #287).
  - All 14 items are done, plus 2 more the agent's own review found (C000672 session switch; IONM/neuronavigation priced next to the package).
  - "2 b" is applied. S8's money is 3,584.80, the excess over the lenient separate-incision 50 %; the strict-reading part (1,792.40) is a 0-TL review.
  - Outpatient mandate follows EK-2/A-2: new curated `ek2a2_outpatient_additional_procedures.parquet`, 1,035 rows, built in the CI image. 22 codes qualify; day cases stay mandated (C003484).
  - Cohort SGK uplift: main 88,920.95 → #286 61,310.65 → PR C before the EK-2/A-2 rule 564,058.45 → final 88,015.34.
  - Full suite 8,890 passed, 0 failed. The CI-image gate is green.
  - fix the must-fix list above (except defect 1, which PR B owns);
  - plus the confirmed smaller items:
    - `is_bundled` decided by the §3.1.4/#284 classifier, not the input flag;
    - risk = billed − package, not all-or-nothing;
    - catalog price when the unit price is missing;
    - no session uplift on a must-package line;
    - only operation branches in the uplift's cross-specialty check;
    - the package side priced with the B(3) rules for several operations;
    - C000690 drugs and C000707 post-window lines not counted as replaced;
    - Turkish ı in branch keys;
    - a test pinning the EK-2B puan ranking.
  - Domain questions wait for Safa:
    - +25 points per session or per line (C000662);
    - money vs a 0-TL review row when the incision or branch is unknown;
    - §3 incisional and endoscopy scope.

### Decisions (Safa, 2026-10-16)
- #259: days before the operation on the same inpatient takip stay inside the package. SUT §2.2.2.B-1(1) (C000685): "takip alındıktan sonraki … yatak bedeli … dahil".
- **Unknown incision or branch (Safa: "2 b"):** when the bill cannot show the incision type or the branch, Bilun claims money only above the most lenient legal factor (separate incision; +25 across specialties). Between the strict and the lenient factor it shows a 0-TL "kontrol et" review row.
- **Outpatient package gap (follows the SUT text; was an open question):**
  - Rule: §2.2.2(1) (C000646) mandates packages for yatarak services only. For outpatients, §2.2.1.B-1(10)(a) (C000581/C000582) applies the package method only to EK-2/A-2 procedures that are also in EK-2/C.
  - Data: the current EK-2/A-2 list is in the repo. `data/gazette/raw/annex=EK-2A-2/effective_date=2021-06-01` comes from the 2026.10.02 package, 517 rows, 17 marker-dated amendments up to 2026-04-16. It is not curated and the engine does not read it.
  - Fix in PR C: curate EK-2/A-2 with marker dates; an outpatient line is package-mandated only when it is on EK-2/A-2 on its date.
- **+25 points per session or per line (C000662/C000674):** Safa asks Ahmet Almalı. Until then, keep today's behaviour (whole session).
- **Follow-up issues filed 2026-10-16 (Safa's yes):**
  - #289 newborn-bed "çocuk/pediatri" substring;
  - #290 capture gaps inside the package window;
  - #291 markers in 13 other lists;
  - #292 EK-3O/EK-1A callers without a date;
  - #293 stale dental history and its reader ignoring `valid_to`;
  - #294 remaining `package_candidate` reads and the crosswalk under `synthetic/`.
- Defect 3 (0-TL review rows on every bill) waits for Safa's choice of what the demo shows.

### Wave 2 record (restored; the original block was lost uncommitted on 2026-10-15)
- **Workflow `wf_f4b4dd73-12f`, materials (#262 → PR #284):** implement → 3 reviewers → fix-up (12 findings applied, 3 partly rejected with reasons) → independent verify. Every criterion passed at f480cb68, which is the merged commit.
- **Workflow, session rules (#261/#264/#269 → PR #283):** implement → 3 reviewers (17 findings, 7 must-fix). Fix-up and verify died on the usage limit.
- **#283 follow-up:** b06cfbf3 says it addressed all 17. Argon merged #283 and #284 on 2026-10-15. Item 3 above checks b06cfbf3 independently.

### Out of Scope
- Defect 3 (waits for Safa).
- Synthetic v3 P2–P7 (waits for Safa's review of stories, lab table and ICD/drug notes).
- The strict release lane.

## Task: Step 3 engine and lab fixes — #280, #281, #255, #256, #259 (2026-10-15)

### Goal
Resolve the 5 remaining engine and lab-price issues (#280, #281, #255, #256, #259) in atomic commits on a single branch so all showcase-bill and lab-pricing defects are closed and verified green in CI.

### Subtasks
- [x] 1. **#280 (`lab_capture_gap` & `prose_rules` `lookup_procedure_code` `match_type` audit):**
  - Require `lookup.get("match_type") == "exact"` in `lab_capture_gap._resolve_lab_list_price` (`src/bilun/domain/prose_rules/lab_capture_gap.py`).
  - Guard reachable `prose_rules` `lookup_procedure_code` call sites (`dental_ga_uplift.py`, `procedure_addon_uplift.py`, `procedure_capture_gap.py`, `session_pricing.py`) against `match_type == "prefix_search"`, and record the runtime audit of all 10 call sites.
  - Add regression tests in `tests/unit/domain/prose_rules/test_lab_capture_gap.py` proving `L1070`, `L100`, `L10702` emit no finding while `L107020` prices at 19.73 TL on 2026-10-15.
- [x] 2. **#281 (Remove caller-less `_load_gazette_visit_prices`, `get_visit_prices`, and `get_lab_price`):**
  - Remove `_load_gazette_visit_prices` from `src/bilun/domain/loaders/gazette.py` and its re-export in `src/bilun/domain/loaders/__init__.py`.
  - Remove `get_visit_prices` and `get_lab_price` from `src/bilun/domain/catalog.py`.
  - Update `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:52` to cite `yatak_puani.py:40`, `refakatci.py:38`, and `icu_puani.py:59,65`.
  - Verify `git grep -n -w` returns zero hits in code/tests for the 3 removed names.
- [x] 3. **#255 (`detect_icu_tier_overbilling` sourced evidence & informational-only review):**
  - Cite `SUT §2.4.4.H.(1), (2), (4)` (`C001233`, `C001234`, `C001236`) and remove the non-existent `"EK-2/C-A"` citation in `src/bilun/domain/prose_rules/icu_puani.py`.
  - Count only separately billable items on EK-2/C ICU package days as positive support evidence: EK-2/C `A/B/C`-group procedures (e.g., ECMO `605960`, `605969`–`605979`, or any line whose EK-2/C group is in `A1`/`A2`/`A3`/`B`/`C`) and `§2.4.4.H.(4)` items (`704210`, `704230`, `704290`, `704920`, plus their keywords).
  - Emit an informational review (`severity="info"`, `at_risk_try=0.0`, `savings_try=0.0`, `risk_amount=0.0`) when `P552003`/`P552008` has no separately billed support item on the episode; update `tests/unit/domain/prose_rules/test_icu_puani.py`.
- [x] 4. **#256 (Turkish capital & filler-word normalization in `_specialty_matches`):**
  - Update `_normalize_tr` and `_specialty_matches` in `src/bilun/domain/prose_rules/_drug_indication/matching.py` so Turkish capitals (`I`→`ı`→`i`, `İ`→`i`) and filler words (`"ve"`, punctuation/abbreviations like `"(KVC)"`) normalize cleanly without cross-matching unrelated specialties (e.g. `"Kalp ve Damar Cerrahisi (KVC)"` matches `"kalp damar cerrahisi"` and never `"kardiyoloji"`).
  - Remove the two strict `xfail` marks in `tests/unit/domain/prose_rules/test_specialty_scope_cases.py` and add unit tests for `"ACİL TIP"`, `"GÖZ HASTALIKLARI"`, and non-matching `"kardiyoloji"`.
  - Refresh `file_sha256["src/bilun/domain/prose_rules/_drug_indication/matching.py"]` in `data/gazette/sut_coverage_evidence.json`.
- [x] 5. **#259 (EK-2C package window for `yatak_puani.py` and `refakatci.py`):**
  - Resolve the EK-2/C group (`A1`/`A2`/`A3`/`A`: 15, `B`: 10, `C`: 8, `D`: 5, `E`: 3 days) as of the package procedure date via `get_ek2c_entry` (with fallback to `line.ek2c_group`, or 1 day when ungrouped).
  - Bundle pre-op days on the same inpatient takip (`§2.2.2.B-1(1)`) and the `1..W` package window days starting on the procedure date (`§2.2.2.B-1(3)`), expecting `510010` and `510121` only for days after `window_end` (`§2.2.2.B-1(4)`).
  - Update `tests/unit/domain/billing/test_elkitabi_tablo23.py` and add regression tests in `test_yatak_puani.py` and `test_refakatci.py` covering clean S1/S5/S8 (0 TL uplift) and stays exceeding the package window.
- [x] 6. **Verification & CI:**
  - Run `ruff check src/ scripts/`, full `pytest -q`, `compile_rules.py --check`, and `audit_manifest_parity.py --drug-only`.
  - Push branch, open PR, run CI via `laptop_runner.py`, check reviews, squash-merge to `main`, and verify `main` CI green.

### Review (2026-10-15)
- **#280:** Required `match_type == "exact"` in `lab_capture_gap._resolve_lab_list_price` and rejected `prefix_search` across the 5 reachable `prose_rules` call sites (`dental_ga_uplift.py`, `procedure_addon_uplift.py`, `procedure_capture_gap.py`, `session_pricing.py:124,436`). Added regression tests for `L1070`, `L100`, `L10702`, `L1018`, and `L107020`.
- **#281:** Removed caller-less `_load_gazette_visit_prices`, `get_visit_prices`, and `get_lab_price`, and updated the plan citation in `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md:52`.
- **#255:** Removed non-existent `"EK-2/C-A"` citation in `icu_puani.py`; scoped positive Tier 3 support evidence to separately billable EK-2/C `A/B/C`-group procedures and `§2.4.4.H.(4)` items (`704210`, `704230`, `704290`, `704920`, ECMO `605960`/`605969`–`605979`); emitted informational-only review (`severity="info"`, `at_risk_try=0.0`) when `P552003`/`P552008` lacks separately billed support items.
- **#256:** Fixed Turkish capital folding (`İ`→`i`, `I`→`ı`→`i`) and filler/abbreviation normalization in `_drug_indication/matching.py`, un-xfailed both tests in `test_specialty_scope_cases.py`, and refreshed `matching.py` SHA-256 in `sut_coverage_evidence.json`.
- **#259:** Applied SUT `§2.2.2.B-1(1), (3)-(4)` EK-2/C group package windows (`A1/A2/A3/A=15`, `B=10`, `C=8`, `D=5`, `E=3`) to `yatak_puani.py`, `refakatci.py`, and `yatak_icu_overlap.py`, and updated Tablo 23 + unit tests.

### Out of Scope
- Catalog parser / temporal issues `#226` and `#227`.
- Rewriting committed showcase `results/` snapshots.

## Task: Remove three dead lab-price code paths (follow-up to Safa675/Bilun#271, 2026-10-15)

### Goal
The `get_lab_price` fallback in `lab_capture_gap._resolve_lab_list_price`, the caller-less `_load_gazette_lab_prices` with its re-export, and the never-read `_SUT_CODE_TO_BILUN` are gone with no behaviour change; the `constants.py` hash pinned in `data/gazette/sut_coverage_evidence.json` is refreshed openly in its own commit; all CI gates pass.

### Verified before planning (on main `91fb756c`)
- Fallback: `_resolve_lab_list_price` (`src/bilun/domain/prose_rules/lab_capture_gap.py:30-43`) has one caller (`:105`) and only receives `str(test_name).strip().upper()` values that start with `L` and have at least 4 characters (`:75-79`). `get_lab_price` (`src/bilun/domain/catalog.py:192`) returns a price only for a key of `BILUN_TO_SUT_CODE`, and no key has that shape (checked at runtime), so for every code that caller can pass, on every catalog date, the fallback returns `None`. (It does return a price for a BILUN name such as `"CRP"`, which the caller never passes.) `get_lab_price("L106430")` is `None`; `get_lab_price("PT")` is 55.96 on main (39.49 on #271). The first branch prices all 1,948 L-codes of the EK-2B catalog in force on 2026-10-15 (the default date), and the synthetic lab feed sends L-codes (`SUB_CODE` → `test_name`, `src/bilun/cache/loaders.py:25`). This fallback is the only caller of `get_lab_price` in the repository.
- `_load_gazette_lab_prices` (`src/bilun/domain/loaders/gazette.py:449`): `git grep` finds only the definition and the import and `__all__` entry in `src/bilun/domain/loaders/__init__.py:14,36`; no dynamic access. Its last caller was removed in `7e2cdfdc` (2026-06-22). `get_all_lab_prices` keeps two callers (`src/bilun/api/routes/pricing.py:195`, `src/bilun/domain/catalog.py:476`).
- `_SUT_CODE_TO_BILUN` (`src/bilun/domain/constants.py:246-249`): only its definition; present since the initial extraction `1f146824` (2026-05-16) as `_SUT_CODE_TO_ILAY`, renamed in `a27c5298` (2026-05-23), never read. `constants.py` has no `__all__`, and nothing imports the loop names `_name`/`_code`.
- Hash closure: `coverage_dependency_hashes` (`src/bilun/domain/sut/coverage_evidence.py`) pins `constants.py` but not `lab_capture_gap.py` or the two loader files, so exactly one pinned hash changes.

### Subtasks
- [x] 1. Baseline on unchanged main: `scripts/sut/build_sut_coverage.py --output-dir <scratch>/before` gives an evidence JSON that parses equal to the committed one and four parquets frame-equal to the committed ones; `tests/unit/domain/prose_rules/test_lab_capture_gap.py`, `tests/unit/domain/prose_rules/test_clause_provenance.py` and `tests/unit/domain/sut/test_coverage_evidence.py` pass.
- [x] 2. Delete the `get_lab_price` fallback from `_resolve_lab_list_price` and drop `get_lab_price` from the import; update the detector's line range that `data/synthetic/reference/lab_reference_notes.md:91` cites (`lab_capture_gap.py:74-136`), the only line-anchored citation the removals shift.
- [x] 3. Delete `_load_gazette_lab_prices` from `src/bilun/domain/loaders/gazette.py` and its import and `__all__` entry from `src/bilun/domain/loaders/__init__.py`.
- [x] 4. Delete `_SUT_CODE_TO_BILUN` (comment and three lines) from `src/bilun/domain/constants.py`.
- [x] 5. Commit items 2-4 together as one behaviour-preserving removal; re-run the item 1 tests.
- [x] 6. Refresh the hash: run the builder into `<scratch>/after`; prove the evidence parses equal to the committed file except `file_sha256["src/bilun/domain/constants.py"]`, that the new value equals `sha256(constants.py)`, and that the four parquets are frame-equal to the committed ones; replace only that value; `git diff` shows one changed line; commit on its own.
- [x] 7. Verify one after the other, never in parallel: `ruff check src/ scripts/`; full `python -m pytest -q -n auto`; `python scripts/sut/compile_rules.py --check`; `python scripts/sut/audit_manifest_parity.py --drug-only`; `git status` shows only the intended files, checked again after pytest.
- [x] 8. Confirm main CI is green and whether `origin/main` moved (if #271 merged first: merge main, redo item 6 on the merged `constants.py`). Before the push, main CI was green on `91fb756c`, `origin/main` had not moved, and #271 was still open.
- [x] 9. Push the branch, open the PR, follow its CI.
- [x] 10. Ask Safa before merging.

### Out of Scope
- `_load_gazette_visit_prices` (`src/bilun/domain/loaders/gazette.py:472`) has no callers either (removed in the same `7e2cdfdc`), and `get_visit_prices` (`src/bilun/domain/catalog.py:235`) is only called by it. These are visit and bed prices, not lab prices, so they are reported, not removed.
- `get_lab_price` (`src/bilun/domain/catalog.py:192`) has no caller once the fallback is gone (#271 adds none). It sits in the catalog's public price-lookup section next to `get_all_lab_prices`, so it is reported, not removed.
- Found on main during review, not caused here: `_resolve_lab_list_price` ignores `match_type`. `lookup_procedure_code`'s prefix search (`src/bilun/domain/catalog.py:414-437`) returns its first candidate as `entry`, so a truncated or unknown code is priced as another test and labelled `ek2b_list_price`. `"L1070"` gives 1,810.89 TL (L107000, a lymphocyte crossmatch) and `"L1018"` gives 222.55 TL (L101800). This is flagged as a separate task.
- The lab map values (#271), and any behaviour change.

### Merge order
#271 changes the same evidence line and also adds its entry at the top of this file. Whichever PR merges second merges main, redoes item 6 on the merged `constants.py` and keeps both `tasks/todo.md` entries. Both PRs also edit `data/synthetic/reference/lab_reference_notes.md`, at lines 91 and 96-107, which merge cleanly. #271 moves `HEMOGRAM_TESTS` to `constants.py:235-251`, so the `constants.py:228-244` citation on line 88 of that file goes stale once #271 is in; this PR does not cause that.

### Review (2026-10-15)
- Commits: `10d67d68` (the three removals and the shifted citation in `lab_reference_notes.md`), `76316b99` (the hash refresh, one line), then this plan. After the review only the first commit's message was reworded. The trees are those of the verified `51e67ebd`/`032b071e`.
- Hash refresh: outside `file_sha256` the regenerated evidence parses equal to the committed file; of its 163 pinned hashes only `constants.py` changed (`e0c90e5f…` → `13f37977…`); the four coverage parquets are frame-equal. On unchanged main the regenerated evidence also parses equal. Its bytes differ only in where the `input_clauses` key sits, because the committed file lists it first instead of in the builder's sorted order, so the value was replaced in place.
- No file at HEAD pins the old SHA-256 or blob id of any of the five changed files. As a control, the same search on main finds the evidence file. `data/gazette/source_authority/corpus_consumer_review_pr128.json:25730` pins an older `loaders/gazette.py` (`725191e1…`, the state at `d0337600`). It is already stale on main, no code reads it, and the ILAY Phase 1 entry below keeps it on purpose.
- Local environment (miniforge: pandas 2.3.3, polars 1.41.2, pyarrow 24.0.0): ruff clean; pytest 8,406 passed, 1 failed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues over 23 manifests. The failure (`tests/unit/scripts/test_curated_catalog_idempotence.py::test_pandas_string_storage_variation_does_not_change_decoded_semantics`) also fails on unchanged main in this environment. pandas 2.3.3 turns `None` into `'None'` under `astype("str")`; CI locks pandas 3.0.6.
- CI image `bilun-laptop-ci:20261008-runtime-complete` with `requirements-ci.lock` (Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), on a shallow clone of `032b071e` (same tree as `76316b99`), running CI's backend steps in order: ruff clean; pytest 8,407 passed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues; no tracked file changed.
- `git status` after every step showed only `tasks/todo.md`.
- Independent read-only review: none of the three claims falsified. A differential run of main's and this branch's `_resolve_lab_list_price` over 23 catalog dates and 1,971 inputs made 45,333 calls with 0 differences; main's fallback was reached 359 times and never returned a price. I re-ran it with the same result. The review's corrections, all applied: "every input" became "every code the caller can pass"; the map's history starts at `1f146824`, not `a27c5298`; the 1,948 count is dated; and `get_lab_price` is left without callers. It also found the `match_type` problem listed under Out of Scope, which I reproduced. Commit `10d67d68` alone fails the coverage-evidence test until `76316b99` refreshes the hash. That split is the separate commit Safa asked for, and it is harmless under the squash merges this repo uses.

## Task: Fix wrong EK-2B codes in the BILUN lab test map and its old-code aliases

### Goal
Every name in `BILUN_TO_SUT_CODE` and every old code in `_OLD_TO_NEW_CODE` (`src/bilun/domain/constants.py`) resolves to the EK-2B code whose in-force catalog name is that test, so `/api/lab-prices` serves PT/INR `L106430` 39.49, aPTT `L101050` 35.53, Prokalsitonin `L106240` 167.91 and Protein `L106300` 7.20 TL (2026-07-07 edition), and a test fails when a mapped code is missing from the catalog in force or names another test.

### Subtasks
- [x] 1. Add `tests/unit/domain/catalog/test_lab_code_map.py` and see it fail on the current map:
  - every mapped code is a real entry of the EK-2B catalog in force (`load_sut_catalog()`, today, as `/api/lab-prices` serves it) and `get_all_lab_prices()` prices every name;
  - the test name appears as whole words in the catalog name after Turkish case folding (`turkish_lower`, `src/bilun/domain/utils.py:16`); names the catalog spells differently are listed explicitly (13 hemogram components -> Hemogram, GFR -> Kreatinin, ALP -> Alkalen fosfataz, HbA1c -> Hb A1c, PT/INR -> Protrombin zamanı, Albumin -> Albümin);
  - every entry is pinned to its reviewed exact catalog name (the containment check alone accepts e.g. T3 -> Revers T3, Kreatinin -> Albümin/Kreatinin);
  - every old code resolves through `lookup_procedure_code` to the entry, and reviewed name, of its test name's code;
  - the `/api/lab-prices` route function returns, for every row, the mapped code and that code's catalog price (no 0.00 rows).
- [x] 2. Fix `BILUN_TO_SUT_CODE`: PT and INR -> `L106430`, aPTT -> `L101050`, Prokalsitonin -> `L106240`, Protein -> `L106300`; Kalsiyum -> `L103860` (total, not ionized) and CRP -> `L101850` (quantitative, not latex), both confirmed by Safa on 2026-10-15.
- [x] 3. Replace the literal `_OLD_TO_NEW_CODE` values with an old-code -> test-name table and derive the codes from `BILUN_TO_SUT_CODE`, so an alias cannot point elsewhere than its test name (fixes 905320, 904290, 903170).
- [x] 4. Refresh the `src/bilun/domain/constants.py` hash pinned in `data/gazette/sut_coverage_evidence.json` (checked by `tests/unit/domain/sut/test_coverage_evidence.py::test_committed_coverage_artifacts_match_current_source_rules_and_api`): run `scripts/sut/build_sut_coverage.py --output-dir <scratch>`, prove the four coverage parquets equal the committed ones and the evidence JSON differs from HEAD only in that hash, then copy only the JSON.
- [x] 5. Verify: the new test passes; `ruff check src/ scripts/`; full `python -m pytest -q -n auto`; `python scripts/sut/compile_rules.py --check`; `python scripts/sut/audit_manifest_parity.py --drug-only`; `git status` lists only the intended files.
- [x] 6. Commit the fix and test, then the hash refresh as its own commit; confirm main CI is green; push the branch, open the PR, follow its CI.

### Out of Scope
- `src/bilun/domain/prose_rules/lab_capture_gap.py:39` passes an SUT code to `get_lab_price`, which expects a test name, so that fallback never resolves; the map fix does not change it.
- `_load_gazette_lab_prices` (`src/bilun/domain/loaders/gazette.py:449`) and `_SUT_CODE_TO_BILUN` (`constants.py:254`) have no callers.
- Renaming test-name keys (e.g. `Albumin`), adding tests to the map, the synthetic cohort's lab units, staging deploy.

### Review (2026-10-15)
- Confirmed with Safa before coding: Kalsiyum -> `L103860` (total) and CRP -> `L101850` (quantitative); merge after green CI.
- `/api/lab-prices`: PT/INR 55.96 -> 39.49, aPTT 17.09 -> 35.53, Prokalsitonin 46.06 -> 167.91, Protein 55.96 -> 7.20, Kalsiyum 17.09 -> 7.20, CRP 9.86 -> 16.46 TL; 40 rows, none at 0.00.
- Test (107 cases) fails on the old map for exactly PT, INR, aPTT, Prokalsitonin and Protein in the containment check; the exact-name pins (all 40 entries, added after review) also catch Kalsiyum and CRP. A mutation script caught 14 wrong map codes (e.g. T3 -> Revers T3, Kreatinin -> Albümin/Kreatinin) and the 5 old wrong aliases.
- `sut_coverage_evidence.json`: only the `constants.py` hash changed; the regenerated evidence parses equal and the four coverage parquets are frame-equal.
- Main moved during the work (#257, #258). After merging it (only `tasks/todo.md` conflicted; both sides kept): ruff clean; pytest 8,514 passed, 1 skipped, 4 xfailed; `compile_rules.py --check` 119 byte-identical; parity 0 issues; tree clean. Item 6 of `data/synthetic/reference/lab_reference_notes.md` now says the codes are fixed.
- PR: Safa675/Bilun#271.

## Task: Synthetic demo v3 — P0 decisions and baselines, P1 reference data, showcase story drafts (2026-10-15)

### Goal
Start `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`:
- record Safa's answers;
- keep the engine baseline;
- classify the test pins;
- build the P1 reference tables with schema tests;
- hand Safa 8 showcase story drafts to review.

The generator and the cohort do not change in this task.

### Subtasks
- [x] 1. Record the answers in the plan:
  - Q1 2026 February–September service dates;
  - Q2 one SGK-contracted private hospital;
  - Q3 Safa reviews the 8 showcase stories;
  - Q4 TİTCK price list;
  - Q5 public ICD-10 list;
  - Q6 50 patients, 100–150 bills, 8 showcase.
- [x] 2. P0 baseline: commit the engine numbers before and after the overnight fixes (`6b35d543` vs `1c22ee9c`) to `reports/synthetic-data/2026-10-15-engine-baseline.md`, with a JSON summary next to it.
- [x] 3. P0 test pins: classify each test file that pins synthetic IDs, tags, amounts or counts as drop, re-point or keep, with a fixture strategy. A read-only subagent does this; the result goes into a plan appendix.
  - Result: `plans/data/2026-10-15-synthetic-v3-test-pins.md`. P6 has 25 files and about 280 pins. The fixture strategy (cohort registry plus helper) is now in plan D4. It also found that traffic-accident detection reads `scenario_tag`/"kaza" substrings (`traffic_accident_billing.py:84-90,122-129`; `treatment_pricing.py:603-608`).
- [x] 4. P1 chapter table:
  - builder: `scripts/synthetic/reference/build_ek2b_chapters.py`, from the raw EK-2B heading rows;
  - outputs: `data/synthetic/reference/ek2b_chapters.csv` (chapter ranges, reviewable) and a code→chapter parquet;
  - a schema test, plus a check that each chapter's codes are contiguous.
  - Result: 7,175 codes in 43 chapters, each one block in the list. The pattern handles lettered ("9.A") and two-line headings. Every code in force on 2026-02-01, 2026-07-07 and 2026-09-30 has a chapter (10 tests).
- [x] 5. P1 anaesthesia groups. **Changed:** the engine's bands switch on the wrong dates, so the generator takes the bands and their dates from the list instead (`code_sets.yaml` → `surgical_group_bands`).
  - The raw EK-2B markers say the 32,561 table starts 2024-08-07 and the 39,001 table starts 2026-04-16. `_group_table_for_date` switches on 2026-01-01 and 2026-07-07.
  - Pinned by two strict `xfail` tests.
  - Filed as Safa675/Bilun#265. The re-check found a third wrong cutover: the 12001 bands are marked 04/08/2022, but the engine uses them from 2022-09-03.
- [x] 6. P1 code sets: `data/synthetic/reference/code_sets.yaml` (visits by setting, beds, ICU tiers, anaesthesia, companion). A test checks that every code exists in the catalog in force across 2026-02-01..2026-09-30.
  - Result: 15 tests pass. Notes quote the EK-2B explanation column (510120 under 24 h; 510090 bundles ventilation and monitoring; 520021 never with other procedures; 530000 once a day).
- [ ] 7. P1 EK-3 prices. **Changed:** no general dated index yet.
  - The surgical sub-annexes have full lists only up to 2025-12-13; later changes are amendment markers, the mechanism of open #227.
  - Pathways will use a small reviewed material set instead. A test checks each code's price on its service date against every snapshot and marker.
  - The general index waits for #227's fix.
- [x] 8. P1 lab reference table draft: about 40 routine and condition tests, each with EK-2B L-code, unit, sex-specific range and panel. A subagent drafts it and Safa reviews it.
  - Result: `data/synthetic/reference/lab_reference.csv` (45 billed tests, 77 result rows, 16 panels) with notes; it is a draft for Safa's review.
  - `test_reference_lab_table.py` checks codes, names and prices across the window.
  - It also found two engine bugs: the hemogram keyword match catches HbA1c, and wrong codes in `BILUN_TO_SUT_CODE` (PT/INR, aPTT, procalcitonin, protein).
- [x] 9. Price-history cleanup: already done by #248 (0 zero-length rows, 0 duplicate windows, `valid_to` honoured; checked 2026-10-15).
- [x] 10. Downloads (Q4, Q5): find the exact files (URL, name, size, terms) and ask Safa per file. Only then fetch them into a scratch folder and build the ICD-10 table and the drug crosswalk.
  - [x] 10a. Safa approved the 7 files on 2026-10-15. They are fetched into separate scratch folders, and each size matches the HEAD check (9,428,064 bytes in all):
    - SKRS `ICD10Listesi.xlsx` (15,805 codes, Turkish names) and `ICD10MSVSIliskisiListesi.xlsx` (sex flags on 97 cancer codes);
    - WHO `icd102019enMeta.zip`;
    - TİTCK licensed-product lists of 2026-02-06 and 2026-09-25;
    - SKRS e-prescription lists of 2026-02-03 and 2026-09-29.
  - **The September e-prescription list** links to another workbook. Its 3 essential-medicine-list columns are formulas over a March file, so they are not used.
  - **The WHO file** has no sex/age edits. Its licence is CC BY-ND 3.0 IGO, so it serves only as a local cross-check, and nothing derived from it is committed.
  - [x] 10b. ICD-10 table `data/synthetic/reference/icd10_tr.parquet`, built from the SKRS export:
    - code, Turkish name, parent, level, active flag, high-risk-pregnancy flag, created/updated/passive dates;
    - sex from the active SKRS ICD10MSVS rows.
    - Result: 15,804 codes (15,799 active) and 97 sex-flagged (63 F, 34 M).
    - SKRS follows an older WHO edition plus national codes (COVID-19 = U07.3, no K35.8, no X85–Y09). In the story draft, K35.8 is invalid and M48.0, M81.0 and S72.0 have sub-codes (question 12).
  - [x] 10c. Drug crosswalk `data/synthetic/reference/drug_crosswalk.parquet`:
    - one row per curated EK-4A barcode;
    - from TİTCK: product name, active ingredient, ATC code;
    - from SKRS e-prescription: ATC name and active/passive status;
    - both 2026 snapshots;
    - an exact barcode join, with the match coverage reported.
    - Result: 8,078 rows. Coverage: 8,048 matched (99.6%), 7,692 with active ingredient, 8,047 with ATC.
    - The ATC comes from the e-prescription list first, so code and name come from one row; the licence list lags the WHO ATC moves on 182 barcodes.
    - 10 barcodes with ambiguous licence rows stay blank.
    - 12 rows are filled from EK-4A old barcodes.
  - [x] 10d. Builder `scripts/synthetic/reference/build_icd10_and_drugs.py` (Polars over openpyxl, the repo's convention):
    - the download folder is passed as an argument; raw files stay outside the repo;
    - the builder refuses any input whose sha256 differs from `data/synthetic/reference/sources.yaml` (publisher, page, file URL, date, size, sha256, terms).
    - Result: it never loads external links, and two runs give byte-identical output.
    - Terms recorded as found: no data licence, footers "Tüm hakları saklıdır"; WHO is CC BY-ND, so nothing derived from it is committed.
  - [x] 10e. Tests: schema, unique keys, code formats, sex flags matching the source, crosswalk coverage, and well-formed provenance entries. The parse is cross-checked against an independent stdlib reader.
    - Result: `test_reference_icd10_drugs.py` has 24 tests and passes; the rebuild test skips without downloads.
    - With `BILUN_REFERENCE_DOWNLOADS`, all 25 pass under `python -I`, including the byte-identical rebuild.
    - The stdlib parse matches: 8 sheets, 0 differing key cells.
    - 20 deliberate faults were all caught.
    - Notes for review: `data/synthetic/reference/icd10_drugs_notes.md` (6 questions).
  - Still open for Safa:
    - drug prices: the TİTCK price list needs a login;
    - sex/age edits beyond the 97 SKRS codes: none of these files has them, so the pathway table (D2) carries sex and age per pathway.
- [x] 11. Showcase story drafts (8) for Safa's review. Each gives:
  - patient, diagnosis, setting and dates;
  - every line with a code valid on its date;
  - one injected fault and the engine rule that should catch it.

  Draft to the scratchpad first; it goes into `plans/data/` once Safa has reviewed it.
  - Result: `plans/data/2026-10-15-showcase-stories-draft.md`, with proofs in `reports/synthetic-data/2026-10-15-showcase-proofs/`.
  - All 8 faults fire, and the clean versions stay silent for their target rule.
  - Other rules misfire on every clean bill (N1–N13). I verified N1 (SUT §2.2.2.B-1(1)(a),(h),(3)), N2 (`common_billing_errors.py:527`) and N4 (P612320 "Protez ayrıca faturalandırılır").
  - The draft is waiting for Safa's review.
  - **Filed 2026-10-15 (Safa's yes):** #259–#269, 11 issues covering N1–N6, N8, N9 and N11–N13, the traffic-accident "kaza" match and the S1 strategy amount. N10 and the lab-code map are being fixed in separate sessions; N7 stays Safa's call.
  - The re-check for the issues corrected the draft: N9's amount, the cause of S1's 1.231,00, N11's scope, N13's rule count, and the N2, N4 and N1 citations. Those edits are marked "Corrected 2026-10-15".
  - The proof scripts now find the repo from their own path, and a re-run reproduced `results/` byte for byte.
- [x] 12. Verify, in sequence: ruff, the new tests, the full suite, `compile_rules.py --check`, manifest parity. One PR; merge is Safa's call.
  - Result (2026-10-15, at `4465fe3c`), all green:
    - `ruff check src/ scripts/` clean;
    - 8,382 passed and 2 xfailed (the band-date pins);
    - 134 artifacts byte-identical;
    - parity 0 issues.
  - Pushed; PR Safa675/Bilun#258 is open.

### Out of Scope
- The generator rewrite (P3–P4), the loader change (P3) and the regeneration (P7).
- Any download without Safa's yes for that file.
- Fixing #255 or #256.

## Task: Engine fixes wave 1 — false findings on correct bills (#260, #263, #265, #266, #267, #268, #270) (2026-10-15)

### Goal
Seven independent PRs, each making one rule stop misfiring on correct bills. Each keeps the rule's true positives and pins the fix with the issue's acceptance criteria as tests.

### Subtasks
- [x] 1. #270 hemogram: identify CBC lines by code (L107020, L103120) or exact parameter names, not substrings (`claim_lab.py`). `constants.py` stays untouched, because the lab-code session edits it.
  - Result: PR Safa675/Bilun#272 (`fdf2180a`), with 12 new tests.
  - Suite: 8,419 passed, 0 failed. Showcase results byte-identical.
  - The stale note in `lab_reference_notes.md` item 1 gets updated after #271 (the lab-code PR, same file) merges.
- [x] 2. #260 `tablo15_4`: stop reading `is_package_included` as "billed as package". Review `detect_vakabasi_wrong_method`, which shares the helper.
  - Result: PR Safa675/Bilun#277 (`0c5f091b`). #4 emits nothing: the payment-method check already flags the same 26 cohort cases, so a second row would double every fault. #3 is unchanged.
  - Suite: 8,411 passed, 0 failed. Showcase: tablo15_4 rows gone from S1/S5/S8.
  - Open for Safa: Tablo 15 #3/#4 may concern the outpatient visit fee (520030 vs EK-2/A), not EK-2C. That needs the El Kitabı text.
- [x] 3. #263 temporal anomaly:
  - LOS density counts services, not tariff or lab lines.
  - Ghost stay means "bed lines only".
  - No same-date overlap finding without real times.
  - Result: PR Safa675/Bilun#274 (`01e5bb7f`), 9 net new tests. Suite: 8,416 passed, 0 failed.
  - Showcase: the density warning is gone from S2/S4 and the overlap warning from S8. Cohort overlap warnings went from 29 to 0.
- [x] 4. #265 anaesthesia bands: switch on the list's markers (2022-08-04, 2024-08-07, 2026-04-16) and drop the two strict xfails in `test_reference_code_sets.py`.
  - Result: PR Safa675/Bilun#273 (`35df6544`). Bounds were verified against the raw rows; the 2024-01-09 amendment restates the same bounds, so it adds no switch date.
  - Suite: 8,418 passed, 0 failed. Showcase results byte-identical.
- [x] 5. #266 capture gap: a package line counts as submitted for its own code, with or without `P`. Never price a gap from EK-2B when the claim carries that code's package.
  - Result: PR Safa675/Bilun#275 (`1f6bfa74`), 10 new tests. Suite: 8,417 passed, 0 failed. Showcase results byte-identical.
  - Left open: package scope/window coverage (no code-based package contents in the repo).
  - Found: `lab_capture_gap.py` flags in-package labs on package bills (candidate issue).
- [x] 6. #267 §4.2.27.A:
  - Remove vitamin K and FFP names from the 4 rules' drug lists, then recompile.
  - Refresh the `sut_coverage_evidence.json` hash pins.
  - Result: PR Safa675/Bilun#278 (`e4af299f`), 11 new tests. Suite: 8,418 passed, 0 failed.
  - FFP was also removed from a fifth rule (`coumarin_noac_bleed_report_free`): same defect, and it skewed routing.
  - Two coverage-evidence lines changed (1945, 2056). #271 changes line 2020, which is not adjacent.
- [x] 7. #268 traffic accident: match explicit values, never the substring `kaza`. Stop reading `scenario_tag` if a real header field carries the accident type.
  - Result: PR Safa675/Bilun#276 (`c1f5116e`), 61 new tests. Suite: 8,468 passed, 0 failed.
  - `scenario_tag` and `department` are no longer read. Showcase results and the 50-patient demo output are unchanged.
  - Open for Safa: should a traffic accident during work use the iş kazası or the trafik kazası provision?
- [x] 8. Per PR, in sequence:
  - targeted tests, then the full suite;
  - `compile_rules.py --check` and manifest parity;
  - the showcase proofs show the rule's noise gone on the clean bills and the target faults still firing;
  - ruff.
  - Result: every branch has 0 failed. A baseline on clean `main` in a fresh worktree gave 8,407 passed / 1 skipped / 4 xfailed.
  - Full suites ran one at a time behind a shared `flock`.
  - Every target fault still fires, and `results/` was never committed.
- [x] 9. Before each push: CI on `main` is green, and the lab-code session's diff still does not touch the PR's files. One PR per fix; merges are Safa's call.
  - Result: `main` CI is green at 91fb756c.
  - Across the 7 branches and #271, the only shared file is `sut_coverage_evidence.json` (#278 vs #271), on non-adjacent lines.

### Review (2026-10-15)
- **Opened:** 7 PRs, #272–#278, with 116 new tests across them (#270 12, #265 9, #263 9, #266 10, #268 61, #260 4, #267 11).
- **Showcase noise removed:**
  - tablo15_4 on S1/S5/S8;
  - density on S2/S4;
  - overlap on S8.
  - #265, #266, #267, #268 and #270 do not change the committed showcase bills. Their cases are covered by unit tests.
- **Questions for Safa:**
  - the meaning of Tablo 15 #3/#4 (outpatient visit fee?);
  - the provision for a traffic accident during work;
  - whether `lab_capture_gap.py` (in-package labs flagged as gaps) should become an issue.
- **After merge:**
  - update `lab_reference_notes.md` item 1 (after #271);
  - remove the agent worktrees;
  - wave 2 (#261 + #264 + #269, #262) and #259, after Safa's answer.

### Out of Scope
- #259 (waits for Safa's reading of the package window), #261/#264/#269 and #262 (wave 2), #255, #256, #226, #227.
- `BILUN_TO_SUT_CODE` (the lab-code session).
- Staging (waits for Safa's yes).
- Showcase `results/` files (a historical record at 1c22ee9c; not rewritten).

## Task: Fix companion-bed (510121) ICU suppression, admission-date pricing, and billed subtraction (Safa675/Bilun#236)

### Goal
`detect_refakatci_opportunities` (`src/bilun/domain/prose_rules/refakatci.py`) suppresses companion-bed opportunities on all ICU indicator codes (`510090` and `P552001`–`P552008` / `552001`–`552008`), prices `510121` at the EK-2B rate in force on the claim's admission date instead of the undated 2026 rate, subtracts any already-billed `510121` amount on the claim into `recoverable_uplift_try`, and `RefakatciReview.confirmed_refakat_try` sums `recoverable_uplift_try`.

### Subtasks
- [x] 1. Write failing unit tests in `tests/unit/domain/prose_rules/test_refakatci.py` covering:
  - ICU suppression when a claim carries `P552001`–`P552008` (or bare `552001`–`552008`) without `510090`;
  - historical admission-date pricing (`2023-06-15` → `27.44 TL/day`, `2024-07-01` → `61.75 TL/day`, `2026-07-10` → `74.10 TL/day`);
  - subtracting already-billed `510121` lines (`actual_billed_try` and `recoverable_uplift_try = max(0.0, expected_try - actual_billed_try)`), including full billing (`recoverable_uplift_try == 0.0` and `RefakatciReview.confirmed_refakat_try == 0.0`).
- [x] 2. Update `src/bilun/domain/prose_rules/refakatci.py`:
  - Replace `_ICU_PROCEDURE_CODES = frozenset({"510090", "P55200x"})` with `_ICU_PROCEDURE_CODES` matching `510090` and `("552001", "552002", "552003", "552006", "552007", "552008")` (with or without leading `P`/`p`, case-insensitive, matching `icu_puani.py` and `yatak_icu_overlap.py`);
  - Resolve `puan` and `daily_rate` per claim as of `claim.admission_date` via `get_ek2b_price_for_date("510121", claim.admission_date, ...)` (falling back to the undated catalog only when `admission_date` predates the catalog history);
  - Sum billed `510121` lines on the claim as `actual_billed_try` and set `recoverable_uplift_try = _money(max(0.0, expected - actual_billed_try))` (and `0.0` on suppressed rows).
- [x] 3. Update `RefakatciReview.confirmed_refakat_try` in `src/bilun/domain/billing/types.py` to sum `recoverable_uplift_try` when present (without truthiness fallback when `0.0`), and add `"actual_billed_try": true` to `refakatci.opportunities` in `src/bilun/api/public_contracts.json`.
- [x] 4. Run `ruff check`, the new and existing unit tests (`test_refakatci.py`, `test_elkitabi_tablo23.py`, `test_claim_integration.py`, `test_sgk_uplift_synthetic_demos.py`, `test_orchestrator_grand_total.py`, `test_orchestrator_claim_cohort_flow.py`, `test_focused_legacy_materializer.py`), and `compile_rules.py --check` / `audit_manifest_parity.py --drug-only`; confirm zero unintended tracked file diffs.

### Out of Scope
Changing the default policy that unbilled non-ICU inpatient stays emit a confirmed uplift (`included_in_sgk_total=True`, confirmed with Safa), fixing the `valid_to` price-history loader bug (#241), or changing other prose/billing rules (#230–#234, #237–#242).

### Review (2026-10-14)
- Confirmed with Safa before coding: keep unbilled non-ICU inpatient stays in confirmed uplift (`included_in_sgk_total=True`) while fixing `P552001`–`P552008` ICU suppression, admission-date EK-2B pricing, and subtracting already-billed `510121`.
- Cohort effect on the 50 synthetic patients: `total_refakatci` drops from `34,308.30 TL` (priced at 2026's `74.10 TL/day`) to `17,709.88 TL` (priced at each claim's 2023–2024 admission-date EK-2B rate) across 22 patients.
- Verification: `ruff check` clean; 18 unit tests in `test_refakatci.py` (including RED→GREEN tests for `P552001`–`P552008`, 2023/2024/2026 admission-date rates, partial/full `510121` billing subtraction, and public response projection) + 40 billing/orchestrator integration tests pass; `compile_rules.py --check` (134 byte-identical) and `audit_manifest_parity.py --drug-only` (23 manifests, 0 issues) pass.

## Task: Fix price history valid_to, MULGA_ duplicates, and date-aware pricing in 5 rules (Safa675/Bilun#241)

### Goal
Curated EK-2B and EK-2C history tables contain zero duplicate `(code, valid_from)` or `valid_to < valid_from` rows and cap `valid_to` when a code disappears in the next snapshot; runtime readers enforce `valid_to`; and the 5 inpatient/bed/ICU/anaesthesia rules look up catalog prices as of the claim/procedure date.

### Subtasks
- [x] 1. Update `scripts/sut/build_curated_catalogs.py` (`_build_history`) to prefer non-MÜLGA raw parquets when an `effective_date` has both current and `MULGA_` files, and update `scripts/sut/_common.py` (`_add_validity_ranges`) to deduplicate `(key_col, effective_date_parsed)` (`keep="last"`) and cap `valid_to` at `next_global_eff - 1 day` when a code disappears in the next snapshot.
- [x] 2. Rebuild `data/gazette/curated/ek2b_catalog_history.parquet` and `data/gazette/curated/ek2c_catalog_history.parquet` and verify zero rows have `valid_to < valid_from` or duplicate `(code, valid_from)`, and `804460` expires before `2024-08-01`.
- [x] 3. Enforce `valid_to` in `src/bilun/domain/loaders/gazette.py`, `src/bilun/domain/pricing/temporal.py`, and `src/bilun/domain/prose_rules/catalog_membership.py`.
- [x] 4. Pass claim/procedure dates into catalog lookups in `yatak_puani.py`, `yenidogan_yatak.py`, `anestezi_puani.py`, `icu_puani.py`, and `refakatci.py` so historical claims use historical tariffs.
- [x] 5. Add unit tests for `valid_to` expiration (`get_ek2b_price_for_date("804460", "2024-08-01") is None`), history invariant checks, and historical tariff resolution in the 5 rules; run unit tests and `ruff`; commit, check `main` CI, push, open PR for `#241`, and return to `main`.

### Out of Scope
Re-generating the synthetic demo cohort parquets or changing EK-4A drug catalogs.

### Review
- Rebuilt `ek2b_catalog_history.parquet` (`69,546` rows, down from `76,673`) and `ek2c_catalog_history.parquet` (`24,063` rows, down from `26,489`) with zero `valid_to < valid_from` rows and zero duplicate `(code, valid_from)` rows.
- Enforced `valid_to` in `gazette.py`, `temporal.py`, and `catalog_membership.py`; `804460` expires on `2021-05-31` and returns `None` on `2024-08-01`.
- Wired claim/procedure dates into `yatak_puani.py`, `yenidogan_yatak.py`, `anestezi_puani.py`, `icu_puani.py`, and `refakatci.py`.

## Task: Fix temporal-anomaly surgical code prefix filter (Safa675/Bilun#237)

### Goal
`detect_procedure_time_overlap` (`src/bilun/domain/prose_rules/temporal_anomaly.py`) classifies EK-2B/EK-2C surgical procedure codes (`60xxxx`–`62xxxx` and `P60xxxx`–`P62xxxx`) as surgical when `procedure_category` lacks a surgical keyword, and never classifies `50xxxx`/`51xxxx` bed/stay tariffs (`510010`–`510121`) as surgery.

### Subtasks
- [x] 1. Write failing unit tests in `tests/unit/domain/prose_rules/test_temporal_anomaly.py` covering:
  - two same-date, same-specialty `60xxxx`–`62xxxx` (and `P60xxxx`–`P62xxxx`) lines with generic `procedure_category="islem"` / `"paket"` flagging `procedure_time_overlap`;
  - two same-date, same-specialty `51xxxx` bed/stay lines (`510010`, `510121`) not flagging `procedure_time_overlap` even when `procedure_category` is `"islem"` or `"cerrahi"`.
- [x] 2. Update `src/bilun/domain/prose_rules/temporal_anomaly.py`:
  - Change `_SURGICAL_CODE_PREFIXES` from `("50", "51")` to `("60", "61", "62")` and exclude `51xxxx` bed/stay codes (`_BED_CODE_PREFIXES = ("51",)`) in `_is_surgical`, normalizing optional leading `P`/`p` and punctuation.
- [x] 3. Run `ruff check`, `pytest` on `test_temporal_anomaly.py`, `compile_rules.py --check`, and `audit_manifest_parity.py --drug-only`.

### Out of Scope
Populating `procedure_specialty_code` in the synthetic generator (tracked under the care-pathway generator plan) or changing `detect_los_procedure_density_anomaly`.

### Review (2026-10-14)
- `_SURGICAL_CODE_PREFIXES` updated from `("50", "51")` to `("60", "61", "62")` (matching all 2,407 EK-2B surgical procedures in `600000`–`629999` and `P600000`–`P629999` in EK-2C), and `51xxxx` bed/stay tariffs (`510010`–`510121`) are excluded unconditionally in `_is_surgical`.
- Verification: `ruff check` clean; 16/16 unit tests in `test_temporal_anomaly.py` pass (RED→GREEN on 8 new cases); `compile_rules.py --check` (134 byte-identical) and `audit_manifest_parity.py --drug-only` (23 manifests, 0 issues) pass.

## Task: ILAY Phase 1 — take the real ILAY-derived files out of the repo (2026-10-15)

### Goal
`main` tracks no file under `data/synthetic/sut/claims/ilay_validation/` or `data/gazette/prose_rules/golden/ilay/`. One local copy is kept outside every repo. The specialty regression test runs on synthetic cases instead of real rows. A CI test fails if either folder comes back. This is Phase 1 of `plans/security/2026-10-14-remove-ilay-real-data-plan.md`, approved by Safa on 2026-10-15 with the synthetic-test adjustment.

### Subtasks
- [x] 1. File the issue for the specialty-name matching defects ("Kalp ve Damar Cerrahisi (KVC)"; Turkish capitals such as "İÇ HASTALIKLARI"), using the evidence from a run on `main` @ `1c22ee9c`. → Safa675/Bilun#256: 29 of the 102 specialty tokens fail in Turkish capitals, and 266 of the 404 specialty-restricted rules list at least one of them.
- [x] 2. Copy both folders to `~/bilun-local/ilay-validation/` (not a git repo, mode 700). Check the copy by checksum without printing any content.
- [x] 3. Fast-forward local `main` and create a branch from it in this checkout. Do not add a worktree, which would be one more copy of the files.
- [x] 4. `git rm -r` both folders (20 files). Add `.gitignore` lines for them.
- [x] 5. Harness (`scripts/validation/validate_drug_rules.py`, `validate_specialty_rules.py`, `build_golden_dataset.py`):
  - write and read under `$BILUN_ILAY_VALIDATION_DIR` (default `~/bilun-local/ilay-validation`);
  - refuse any path inside the repo.
- [x] 6. Replace `tests/unit/domain/prose_rules/test_specialty_real_data.py` with `test_specialty_scope_cases.py`:
  - synthetic cases for the same three rules (rule ids are the only thing read from the old files);
  - mismatch and match cases;
  - the two known matching defects as strict `xfail` cases linked to the new issue.
- [x] 7. Add `tests/unit/test_no_real_patient_data_paths.py`:
  - a pure check over tracked paths;
  - a mutation test that feeds it the forbidden paths;
  - the check run against `git ls-files`, with a filesystem fallback when the checkout has no `.git`.
- [x] 8. Update the references:
  - `scripts/validation/README.md`: output paths, and make the line-81 promise true;
  - `plans/backend/specialty-scope-validation-plan.md:157,180-181,194,269,287`: add a note;
  - `plans/update/2026-08-07-track-e-phase0-audit.md:34`: the wrong "synthetic" label;
  - tick Phase 1 in the ILAY plan.
- [x] 9. Verify (full suite run alone: 8,354 passed, 2 xfailed; an earlier run done in parallel with the artifact checks gave 4 false failures, which passed on `main` and alone; lesson added):
  - `git ls-files | grep -c -E "ilay_validation|golden/ilay"` is 0;
  - ruff on `src/` and `scripts/`;
  - the new and changed tests;
  - the full pytest suite;
  - `compile_rules.py --check` and `audit_manifest_parity.py --drug-only` (the other CI steps).
- [x] 10. Check CI on `main` (green on `1c22ee9c`), make one commit, push and open the PR. Merge is Safa's call. Return the checkout to `main`.

### Out of Scope
- Phases 2–5 of the ILAY plan: staging, live, history rewrite and laptop copies.
- Fixing the matching defects (only filed and pinned as `xfail`).
- The hash manifest entries in `data/gazette/source_authority/corpus_consumer_review_pr128.json`, left as they are on purpose (hashes only, no code reads them).

## Task: Plans and issues from the 2026-10-14 synthetic data audit

### Goal
Two reviewed plans exist in `plans/` (removing the real ILAY data; redesigning the synthetic generator), GitHub issues track the engine bugs from `reports/synthetic-data/2026-10-14-demo-cohort-audit.md` each with its evidence, and the audit, its scripts, the plans and these task files are on `main` through one docs PR.

### Subtasks
- [x] 1. ILAY footprint, by file name only (the data is never opened): tracked files, the commits and branches that contain them, and every code, test, doc, CI and deploy reference. Read-only listing of whether the staging (`/opt/bilun-staging`) and live release trees on the VPS hold copies.
  - Result: 5 files plus a second set in `golden/ilay` (15 JSON files).
  - Copies: 2 staging releases, the staging bare repository and its bundle, 2 live trees (pinned in live's own release records), and 88 laptop folders.
- [x] 2. Write `plans/security/2026-10-14-remove-ilay-real-data-plan.md` (draft done; review is subtask 7). It covers removal from the repo, staging cleanup through the wrapper, the live tree as a decision for Safa, the optional history purge with its costs, and verification steps.
- [x] 3. Generator research: reusable catalog data (EK-2B chapters and surgical groups, anaesthesia groups, bed and ICU codes, EK-3 ↔ procedure links, EK-4A groups, a drug price source), the tests that pin synthetic patient IDs, and the consumers of the schema.
  - Key results: there is no ICU-tier detector; the loader enforces the circular labels; the engine reads demo vignette prices and `scenario_tag`; about 42 test files hold about 375 pins.
- [x] 4. Write `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`. It covers Tier A first, care pathways, prices in force on the service date, labels from injected causes, plausibility validators in CI, re-pinning tests, and open questions.
- [x] 5. Confirm the E1–E5 mechanisms with file:line references, check for duplicate issues, and draft the five issue bodies.
  - No duplicates were found.
  - I re-checked every citation. E1 gained the EK-2B group table (raw 2026-07-07 rows 124–130); E5 turned out to be wrong on this cohort.
- [x] 6. Open the five issues in Safa675/Bilun and record their links in the audit report: Safa675/Bilun#230, #231, #232, #233 and #234, all labelled `bug`.
- [x] 7. Have a subagent review both plans independently against the audit and the code, then fix what it finds.
  - Verdict: the ILAY plan was "not ready" and the generator plan "ready after fixes".
  - Both plans are rewritten (rev 2). I re-checked every reviewer claim I used, against the code, the git metadata or the VPS, read-only.

- [x] 8. Safa approved the second batch (2026-10-14): the docs PR and the further engine issues, but not ILAY Phase 1. Confirmed and reshaped the seven candidates (companion bed and ICU, temporal-anomaly 50/51, duplicate material code, demo-only inputs, loader answer rows, price-history `valid_to`, ICU-tier detector), checked duplicates across all open/closed issues and PRs, and drafted the seven bodies.
- [x] 9. Re-checked each citation in the drafts against the repository code and data, then filed them in Safa675/Bilun: #236, #237, #238, #239, #240, #241 (all `bug`) and #242 (`enhancement`).
- [x] 10. Replaced the "not filed yet" lists in the generator plan (D6) and in the audit report with the new issue numbers (#236–#242).
- [x] 11. Docs PR from a branch of `main` (no extra worktree, so no further copy of the ILAY files): KVKK and secret scan of the files first (0 patient IDs, 0 token-like strings); CI of `main` green on `6b35d543` (checked before the push, rule 10); PR #235 opened and updated with #236–#242. Merge is Safa's call.
- [x] 12. Return the checkout to `main` (rule 11.5); leave no extra branch or worktree. (The PR branch stays on origin only.)

### Out of Scope
Executing either plan, fixing the engine bugs, deleting any file (locally, on the VPS or in git history), starting ILAY Phase 1 (waiting for Safa's answer), and merging the PR (Safa's call).

### Review
**Delivered so far**
- **Issues:** Safa675/Bilun#230–#234 and #236–#242 (12 total: 11 `bug`, 1 `enhancement`).
- **Plans:** `plans/security/2026-10-14-remove-ilay-real-data-plan.md` and `plans/data/2026-10-14-synthetic-demo-care-pathways-plan.md`, both rev 2.
- **Audit report** updated with all 12 issue links (#230–#234, #236–#242).
- **Audit scripts** preserved in `reports/synthetic-data/2026-10-14-audit-scripts/`.

**What the review changed**
- **ILAY plan.**
  - Added the `golden/ilay` set and the live releases' baseline copy.
  - Stopped any hand deletion on live.
  - Gated the history rewrite behind the "No force-push" exception, a backup and green CI.
  - Added three full bundles and two more real-data files in history (`reports/finans_flagged.xlsx`, the interviews docx).
- **Generator plan.**
  - Moved the fault registry before the showcase bills.
  - Tied the anaesthesia source to #230.
  - Fixed the EK-3 date claim, the drug price facts and the reconcile reuse.

**KVKK side effect**
- Two subagent logs on this laptop contain pseudonymized ILAY patient IDs: `~/.claude/projects/-home-safa-Documents-Bilun/a9cf6beb-…/subagents/agent-a225743e213a4fbab.jsonl` (6 distinct IDs) and `agent-a93e236386ee82143.jsonl` (11).
- Reported to Safa. Deleting them is his call.

## Task: Evaluate material pre-check and §3.1/§3.3 prose rules per material line (#238)

### Goal
`precheck_materials_from_claims()`, `check_material_bundling_prose()`, and `check_specialty_materials_prose()` evaluate pre-auth, bundling, and §3.1/§3.3 prose rules per `material_line_id` (preserving `material_line_id` and `claim_id` on every finding) while keeping cross-line `material_code` grouping exclusively for cross-claim MIAT interval checks.

### Subtasks
- [x] 1. Write RED unit tests in `tests/unit/domain/billing/test_claim_materials_precheck.py`, `tests/unit/domain/prose_rules/test_material_bundling.py`, and `tests/unit/domain/prose_rules/test_specialty_materials.py` covering duplicate `material_code` lines (including `F-SENTETIK-HASTA-0038-053` `GHC1220` where `MLZ-…-003` has `requires_pre_auth=True` and `MLZ-…-004` has `requires_pre_auth=False`, plus `material_line_id` and `claim_id` preservation across multi-claim contexts).
- [x] 2. Update `src/bilun/domain/billing/claim_materials.py`, `src/bilun/domain/prose_rules/material_bundling.py`, `src/bilun/domain/prose_rules/specialty_materials.py`, and `src/bilun/api/public_contracts.json` so pre-auth, bundling, and prose rules evaluate every material line and attach `material_line_id` and `claim_id`.
- [x] 3. Run unit/contract test suites (`5,359 passed` across billing/prose/materials + `608 passed` in API tests) and `ruff check` to verify GREEN and zero regressions, then return checkout to `main` (Rule 11.5).

### Out of Scope
Changing MIAT catalog rules, modifying synthetic cohort parquet files, or changing non-material prose evaluators.

### Review
- Scoped `latest_line_by_code` in `claim_materials.precheck_materials_from_claims` strictly to the cross-claim MIAT check (`if code in miat_catalog and latest_line_by_code.get(code_key) is line:`), so `pre_auth_required` and `bundled_separate_billing` evaluate every material line.
- Updated `check_material_bundling_prose` and `check_specialty_materials_prose` to key `seen` by `(material_line_id or f"idx:{idx}", rule_id)` instead of `(code or name, rule_id)`, and forwarded `material_line_id` and `claim_id` from `PatientClaimContext.material_lines` through `_violation_from_rule` and `_enrich_material_precheck_row`.
- Added `material_line_id` to `MaterialPreCheck` list schemas in `src/bilun/api/public_contracts.json`.
- Verified `F-SENTETIK-HASTA-0038-053` emits `pre_auth_required` for `MLZ-F-SENTETIK-HASTA-0038-053-003` (`GHC1220`, `requires_pre_auth=True`) and prose findings for both `MLZ-…-003` and `MLZ-…-004`.

## Task: Stop the runbook from quoting live PIDs that change on every VPS reboot

### Goal
`docs/operations/AI-RUNBOOK.md` points at the `LIVE_PIDS` pin in `staging-update.sh` instead of quoting PIDs, and says what to do when the wrapper stops after a reboot.

### Subtasks
- [x] 1. Find every place the repo quotes the live PIDs: `git grep` for 914/915, 898/899, 911/912 and "live PIDs" finds only `docs/operations/AI-RUNBOOK.md:63` ("live PIDs **914/915**"); no test or script pins that text.
- [x] 2. Replace the numbers in that sentence with "the live pair's MainPIDs and start times against the `LIVE_PIDS` pin in the script (a VPS reboot changes them; see below)".
- [x] 3. Add one short paragraph after "Interrupted transfer": the wrapper stops before any VPS write (`update_exit: not_started`, "Canlı backend beklenen PID … değil"); read the live pair first (read-only, the `systemctl show` and `/proc/<pid>/cwd` check); only if both units are in the frozen `5c89ed53` bundle, re-pin `LIVE_PIDS` in the operator's script (outside this repo) and rerun; never loosen the check. No PID numbers in the paragraph.
- [x] 4. `git diff` shows only that sentence and the new paragraph; `git grep -E "914/915|898/899|911/912"` finds nothing; `tests/unit/scripts/test_sgk_watch.py` (it names this file) passes in the CI image.
- [x] 5. One commit; CI status of `main` checked before the push (rule 10); PR opened; checks green. (PR #229, merged as `6b35d543`.)
- [x] 6. Merge is Safa's call; after the merge remove this worktree and branch and leave the main checkout on `main`. (Merged by Safa; `git worktree list` shows only the main checkout and `git branch -a` only `main`, checked 2026-10-14.)

### Out of Scope
Changing the wrapper (it lives in `~/work/bilun-deploy-plan/staging-ops`, outside the repo), `RELEASE-LANES.md`, any deploy behavior, a script that reads the live PIDs.

## Task: Make expected_rule_outputs.parquet and expected_*_payable_try optional in real_claims mode (Safa675/Bilun#240)

### Goal
`load_sut_claim_dataset(mode="real_claims")` and `read_claim_tables(mode="real_claims")` succeed when `expected_rule_outputs.parquet` is absent or empty and `expected_*_payable_try` / `expected_total_billed_try` / `discount_tier_expected` / `unit_price_try` / `scenario_tag` columns are null or absent, while present `expected_rule_outputs` rows in `synthetic_demo` and `real_claims` still validate their linkage and payable reconciliation.

### Subtasks
- [x] 1. Write failing RED unit tests in `tests/unit/domain/claims/test_loader.py` covering:
  - `load_sut_claim_dataset(claims_dir, mode="real_claims")` when `expected_rule_outputs.parquet` is absent and `expected_total_billed_try`, `expected_total_payable_try`, `expected_payable_try`, `discount_tier_expected`, `unit_price_try`, and `scenario_tag` columns are absent or null;
  - `load_sut_claim_dataset(claims_dir, mode="real_claims")` when `expected_rule_outputs.parquet` exists with 0 rows;
  - `SUTClaimDataset.from_rows` validating present `expected_rule_outputs` linkage and payable reconciliation without requiring answer rows for clean baseline claims/lines.
- [x] 2. Update `src/bilun/domain/claims/parquet_reader.py` so `read_claim_tables` resolves `mode` via `resolve_sut_data_source(..., require_clean_dir=False)` and, in `real_claims` mode, treats `expected_rule_outputs.parquet` as optional (`optional=True`, `reject_if_empty=False`, `scenario_tag` optional) and `expected_total_billed_try` on `claim_headers.parquet` as optional.
- [x] 3. Update `src/bilun/domain/claims/parsing/row_parsers.py`, `src/bilun/domain/claims/dataset_builder.py`, `src/bilun/domain/claims/totals.py`, and `src/bilun/domain/claims/validation/expected_outputs.py`:
  - Default missing `expected_payable_try` and `unit_price_try` on procedure/material/drug lines to `billed_amount_try` and missing `discount_tier_expected` on drug lines to `0.00` (while still rejecting malformed values);
  - Backfill missing `expected_total_billed_try` / `expected_total_payable_try` on `ClaimHeader` from `claim_totals` while reconciling any explicitly supplied header totals;
  - Validate linkage and payable reconciliation for all present `ExpectedRuleOutput` rows without requiring exhaustive claim/line answer rows for clean baseline claims/lines;
  - Update `src/bilun/domain/claims/README.md` to document the `real_claims` optionality contract.
- [x] 4. Run `ruff check`, the claims/deploy/synthetic/billing unit tests, update `tasks/todo.md`, commit, push `claude/fix-claims-loader-real-mode-240`, open the PR, and return to `main`.

### Out of Scope
Changing `REQUIRED_CLAIM_TABLES` / `SUT_CLAIM_FILENAMES` roster constants used by the paused strict paired-release lane, or modifying synthetic data generator scripts (`#239`, `#241`, `#242`).

### Review (2026-10-14)
- Kept `REQUIRED_CLAIM_TABLES` and `OPTIONAL_CLAIM_TABLES` intact in `src/bilun/domain/claims/schema.py` so the strict-lane source-roster contract (`tests/unit/deploy/test_generate_candidate_source_roster.py`) and `build_synthetic_claim_validation_columns()` remain untouched.
- In `src/bilun/domain/claims/parquet_reader.py`, `_effective_spec_for_mode` relaxes `EXPECTED_RULE_OUTPUTS` (`optional=True`, `reject_if_empty=False`, `scenario_tag` optional) and `CLAIM_HEADERS` (`expected_total_billed_try` optional) when `config.mode == "real_claims"`.
- In `src/bilun/domain/claims/parsing/row_parsers.py` and `src/bilun/domain/claims/dataset_builder.py`, missing `expected_payable_try` / `unit_price_try` default to `billed_amount_try`, missing `discount_tier_expected` defaults to `0.00`, and missing header `expected_total_billed_try` / `expected_total_payable_try` are backfilled from `claim_totals` while explicitly supplied values continue to be reconciled.
- In `src/bilun/domain/claims/validation/expected_outputs.py`, all present `ExpectedRuleOutput` rows still validate their claim/patient/line linkage and `expected_payable_try` reconciliation without requiring exhaustive answer rows for clean baseline claims/lines.
- Verification: `ruff check` clean; 318 unit tests across `tests/unit/domain/claims/`, `tests/unit/deploy/`, and `tests/unit/synthetic/` (including 3 RED→GREEN tests in `test_loader.py`) pass.


## Task: Complete the ingestion of the 2026-10-02 SUT package (Safa675/Bilun#217)

### Goal
`data/gazette/ingest_state.json` says `completion_scope: complete` with `last_ingested_date: 2026-10-02` after every current workbook of the official package is converted and validated, while the prose corpus, the EK-4A snapshot catalog and the clause diff stay byte-identical and the review delta is committed.

### Subtasks
Setup (read-only)
- [x] 0.1 `git fetch origin`; `.worktrees/sut-package-2026-10-02` is at the `origin/main` tip (b003ae12 or newer) and `git status` is clean. Done when both are shown.
- [x] 0.2 Choose the environment and write the choice in Review: the CI image `bilun-laptop-ci:20261008-runtime-complete` if it carries `requirements-ci.lock` (pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), else `.venv` (pandas 3.0.3, polars 1.41.2, pyarrow 24.0.0) with the byte-identity checks below as the guard.
- [x] 0.3 Record the sha256 of the files that must not change (scratchpad): `data/gazette/sut_clauses.parquet` (40b2b7eb…), `data/gazette/curated/ek4a_drugs.parquet` (6ed75694…), `data/gazette/deltas/2026-10-02_clause_diff.json` (faa8909f…), `data/gazette/curated/ek4a_history.parquet`, `data/gazette/curated/ek4a_windows.parquet`, `data/gazette/ek4a_announcements.json`, `data/gazette/sut_coverage_evidence.json`.

Fetch (one 33 MB download from sgk.gov.tr)
- [x] 1.1 `python scripts/sut/sut_fetch.py "https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06" 2026-10-02` (it downloads the same file again; the script cannot read a local ZIP). Done when: exit 0; the inventory's `zip_sha256` is `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`; 349 files, 318 workbooks (49 current, 269 MÜLGA); the 3 files already committed show no change in `git status`.

Convert and curate
- [x] 2.1 Copy `data/gazette/sut_clauses.parquet` to the scratchpad as the old side of the clause diff.
- [x] 2.2 `python scripts/sut/convert_xlsx_to_parquet.py --input-dir <input_dir> --defer-state` exits 0 and converts the 49 current workbooks (the 269 MÜLGA files are skipped by design). Verified with Polars, no row loops, per rewritten raw partition ignoring `__source_file` and `__ingested_at`: values change only in EK-1A (+N11 on one row), EK-2B (+2 rows), EK-2C (+3 net rows) and EK-3O (one row's text); every other partition differs in provenance only.
- [x] 2.3 `python scripts/sut/build_curated_catalogs.py --overwrite` exits 1 from exactly one spec, the EK-4A snapshot ("marker-dated rows", by design: `reports/sut-ingest/2026-10-10-ek4a-service-date.md`); no other spec fails; `ek4a_drugs.parquet` keeps its hash; the other curated changes derive from EK-1A, EK-2B, EK-2C or EK-3O only.
- [x] 2.4 `python scripts/sut/sut_ingest_state.py --input-dir <input_dir> --inventory <input_dir>/.sut_package_inventory.json --prepare-corpus` exits 0 and `sut_clauses.parquet` keeps its hash. If it changed: stop, restore the file and report (a corpus change forces coverage closure, `tasks/lessons.md:5-9`).

Reports
- [x] 3.1 `python scripts/sut/sut_clause_diff.py <old corpus> data/gazette/sut_clauses.parquet --new-date 2026-10-02 --legacy-input-fingerprints data/gazette/deltas/2026-10-02_clause_diff_inputs.json` exits 0 and `2026-10-02_clause_diff.json` stays byte-identical.
- [x] 3.2 `python scripts/sut/sut_delta.py 2026-08-29 2026-10-02` creates `data/gazette/deltas/2026-10-02_delta.json` (no `2026-10-02_delta_inputs.json` receipt exists, so no legacy argument). Done when its annexes and row counts agree with the independent cell diff under Evidence; a disagreement is investigated first, not waved through.

Completion
- [x] 4.1 Write `reports/sut-ingest/2026-10-13-package-2026-10-02-completion.md`: the delta table, the hashes, the commands, and the EK-4A component receipt copied verbatim. Completion removes `component_receipts` (`scripts/sut/sut_ingest_state.py:147-149`) and the service-date report does not hold those hashes.
- [x] 4.2 `python scripts/sut/sut_ingest_state.py --input-dir <input_dir> --inventory <input_dir>/.sut_package_inventory.json` exits 0. Done when `ingest_state.json` shows `completion_scope: complete`, `last_ingested_date: 2026-10-02`, `completed_package.zip_sha256` `03bf37df…`, no `pending_full_package_*`, no `component_receipts`, and `manifest_row_count` / `manifest_sha256` equal `version_manifest.parquet`.

Follow-through (small, separable)
- [x] 5.1 `tests/unit/scripts/test_sgk_watch.py` first (RED), then `scripts/sut/sgk_watch.py:48-57`: the `sut_package` and `drug_list` action texts stop pointing at the disabled SUT Monitor workflow and at the receipt that completion deletes; they point at the local steps and the service-date report.
- [x] 5.2 `docs/operations/AI-RUNBOOK.md`: a short "Local SUT package ingest" section with steps 1.1 to 4.2, because the hosted workflow cannot run.

Verify
- [x] 6.1 The CI commands of `.github/workflows/ci.yml:56-68` (ruff, `python -m pytest -q -n auto`, `compile_rules.py --check`, `audit_manifest_parity.py --drug-only`), reading every "Failures: N" and FAIL line (`tasks/lessons.md:270-280`); the SUT and EK-4A tests first.
- [x] 6.2 `git status` after pytest lists only intended paths (pytest mutates the tree, `tasks/lessons.md:109-119`); `git diff --check` is clean; `sut_coverage_evidence.json` and `src/bilun/domain/constants.py` are untouched.
- [x] 6.3 `python scripts/sut/sgk_watch.py --dry-run` (read-only listing request) reports nothing new for 2026-10-02.
- [x] 6.4 A second agent reviews the diff; real findings are fixed, skipped ones are written down with the reason.

Hand-off (nothing is pushed)
- [x] 7.1 Five local commits: (A) raw package files plus inventory, (B) generated data plus the completion report, (C) sgk_watch, its test, the runbook and one stale sentence, (D) the changelog entry, (E) plan, review and lesson. Generated data stays in its own commit (`tasks/lessons.md:429-433`).
- [ ] 7.2 Stop and report. Push, draft PR, CI check and PR review check (AGENTS.md rules 10 and 11) only on Safa's go.
- [ ] 7.3 After the merge, on Safa's go: close #217 with the PR link, remove this worktree and branch; the main checkout stays on `main`.

If any gate above fails, stop and report. No gate is loosened and no pinned hash is refreshed to make a step pass.

### Out of Scope
Rule and product follow-ups that the new data enables: procedures 608310 and 609541 (rule coverage, the "not billed together with 604070/604071/608880" exclusions), EK-1A code N11 in co-payment logic, EK-4G Satralizumab (a `.doc`; no converter exists), the retroactive 2026-09-05 marker on the bone-marrow package row. Promoting the 2026-10-02 EK-4A list into `ek4a_drugs.parquet` (regenerates the synthetic demo cohort). Fixing or re-enabling the SUT Monitor workflow and the hosted-runner refusal; letting `sut_fetch.py` read a local ZIP; the stale comment at `sut-monitor.yml:93`. Any change to the prose corpus, rules, coverage-evidence hashes or the frontend.

### Evidence (2026-10-13)
- Package: the official ZIP (32,973,194 bytes) hashes to the pinned `03bf37df…`; 349 files, 318 workbooks of which 269 are MÜLGA (repealed lists the converter skips) and 49 are current; no current workbook name carries a "Yür." date after 2026-10-13, so the future-date gate cannot trip.
- State today: `completion_scope: partial`, `pending_full_package_date: 2026-10-02`; prose corpus (8,413 rows) and EK-4A are already in (`data/gazette/ingest_state.json`).
- Independent cell diff of the package against the 2026-08-29 one (341 files identical, 6 changed):
  - EK-1A: the row "Kronik Tübülo-İnterstisyel Nefrit" gains code N11.
  - EK-2B: +608310 (Bronkoskopi, 1,073.67; amended by RG-02/10/2026-33388 art. 3-a, effective 2026-10-10) and +609541 (Özofagus atrezi primer onarımı, 25,278.02; art. 3-b, effective 2026-10-10).
  - EK-2C: +P608310 (group D, 5,456.7) and +P609541 (group A3, 215,007.17); the "Kemik İliği Nakilleri" row gains a second marker (art. 4-b, effective 2026-09-05).
  - EK-3O: HO1000 FOTOFEREZ SETİ gains only the marker "(Ek: RG-02/10/2026-33388/5 md. Yürürlük: 08/10/2026)"; its values are unchanged.
  - EK-4A: already handled (#222). EK-4G (.doc): "92. Satralizumab" added (art. 7, effective 2026-10-10).
- The hosted workflow cannot do this: `SUT Monitor` is `disabled_manually`, its builder step exits 1 on the October EK-4A list, and `ubuntu-latest` jobs are refused for this account (`reports/sut-ingest/2026-10-10-ek4a-service-date.md:75-81`).
- Gates that completion enforces: inventory bytes and workbook set, one manifest row per sheet, raw parquet equals a fresh read, corpus equals the DOCX extraction (`scripts/sut/sut_ingest_state.py:34-158`).
- Size: earlier full ingests were one ~600-file PR (#84); this one is about 350 raw-data paths plus ~48 rewritten raw parquets, most of them provenance-only.

### Decisions (before step 1.1)
1. Keep `data/gazette/curated/ek4a_drugs.parquet` as the 2026-05-23 snapshot. Recommended: yes. No runtime module reads it (only the synthetic generator), and promoting it changes the demo cohort.
2. Approve this plan as written.

### Review (2026-10-13)
Both decisions were approved as recommended. Steps 1.1 to 4.2 and the CI commands ran in `bilun-laptop-ci:20261008-runtime-complete` with `requirements-ci.lock` installed offline (Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1), the worktree mounted in. `sut_fetch.py` downloaded the 33 MB package once more; its hash equals the pinned one.
- Result: `completion_scope: complete`, `last_ingested_date: 2026-10-02`, `completed_package.zip_sha256` 03bf37df…, `manifest_sha256` equal to the file on disk. 49 workbooks converted, 48 raw partitions rewritten (44 provenance only, 4 with values). Curated: ek1a (+N11), ek2c (+P609541, amended P608310), ek3o (clause (3) and marker); ek2b unchanged. Guarded files byte-identical.
- CI commands: ruff passed; pytest 8,306 passed; `compile_rules.py --check` and manifest parity exit 0; `sgk_watch.py --dry-run` finds 0 new.
- Where the run differed from the plan: 2.3 exits 1 as predicted, from the EK-4A snapshot spec only. 3.2 shows no EK-2B or EK-2C change because `sut_delta.py` cannot see in-place amendments (report F1); the raw-level comparison in the report is the review delta. Follow-through added after the review: a changelog entry (the 2026-08-29 ingest added one), four runbook gaps and one stale sentence in the 2026-10-10 report.
- Independent review (second agent) reproduced the numbers, hashes and byte-identity. Findings and what was done:
  - Real, claims: the EK-3O clause (3) and the EK-2C bone-marrow row were described wrongly in the report and in a commit message. Fixed in both; lesson added (`tasks/lessons.md`, 2026-10-13).
  - Risk, runtime: rows with a later "Yürürlük" date are eligible from the list's file-level date, so P609541 is eligible from 2026-07-07 (report F3). Written up, not fixed: it needs service-date reading for EK-1A, EK-2B, EK-2C and EK-3O the way #219 to #222 did for EK-4A.
  - Risk: the known gaps (30 EK-2B procedures, Satralizumab) are recorded only in the report and the changelog; no issue tracks them. Left for Safa's decision.
  - Risk: the new baseline might hide announcements. Checked: none are hidden (the 4 without an issue are dated 2026-08-12 to 2026-08-29).
  - Nits fixed: runbook steps 2, 4, 5 and 6; the test also checks `raw data/` paths; changelog entry; stale monitor sentence.
  - Nit skipped: `ingest_state.json` has no trailing newline; `sut_ingest_state.py:153` writes it that way and the old file was written by the same code.
- Not done on purpose: nothing is pushed, no PR is opened, #217 stays open until the merge.

## Task: Fix demo-only vignette and scenario_tag inputs (Safa675/Bilun#239)

### Goal
`claim_strategy.py` computes optional-override package and itemized totals purely from claim/performed procedure lines and the as-of EK-2B/EK-2C catalogs (with `demo_vignette_lookup.py` removed from `src/bilun/`), and `gap_closing.py` / `fatura_inceleme.py` derive `is_emergency` from `claim_type` and `department` without reading `scenario_tag`.

### Subtasks
- [x] 1. Remove `src/bilun/domain/billing/demo_vignette_lookup.py` and `tests/unit/domain/billing/test_demo_vignette_lookup.py`, and update `tests/unit/domain/test_money_helper.py` to drop the removed module path.
- [x] 2. Update `src/bilun/domain/billing/claim_strategy.py`:
  - Inline `recommended_package_code_for_claim(claim, claim_procs)` using `claim_procs` `paket` line codes, `package_code`, and EK-2C procedure code lookups (no vignette lookup).
  - Extend `resolve_package_total_try` to fall back to `get_ek2c_entry(line.procedure_code, as_of_date=as_of)` when `package_lines` and `line.package_code` are absent.
  - Add `resolve_catalog_itemized_alternative(claim, claim_procs, performed_lines=...)` so package-only submissions (when `eligible_lines` is empty) resolve their itemized alternative from `performed_procedure_lines` or `claim_procs` via `get_ek2b_price_for_date` and `compute_session_adjusted_itemized_total` (`itemized_price_methodology = "ek2b_catalog"`).
- [x] 3. Update `src/bilun/domain/prose_rules/gap_closing.py:341-345` and `src/bilun/domain/prose_rules/fatura_inceleme.py:190-194` to derive `context["is_emergency"]` from `claim_type_lower` and `dept` (`"acil" in claim_type_lower or "emergency" in claim_type_lower or "acil" in dept or "emergency" in dept`), never `scenario_tag`.
- [x] 4. Update synthetic demo golden bands in `data/synthetic/demo_vignettes.json` (`0002` and `0003`) and test assertions in `tests/unit/domain/billing/test_billing_actions.py`, `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py`, `tests/unit/domain/billing/test_claim_strategy_sut.py`, and `tests/unit/domain/prose_rules/test_gap_closing_for_context.py` to match catalog-resolved prices and add regression tests verifying:
  - Blanking `scenario_tag` across all 50 synthetic patients leaves `compute_patient_billing_report` outputs and rule evaluations unchanged.
  - A claim with `claim_type="acil"` and `department="Ic Hastaliklari"` has `is_emergency is True` in `_build_gap_closing_context`.
- [x] 5. Run `ruff` and relevant unit tests, commit, check `main` CI (Rule 10), push `claude/fix-demo-vignette-emergency-239`, open PR for `#239`, and return to `main` (Rule 11.5).

### Out of Scope
Regenerating `data/synthetic/sut/claims/*.parquet`, removing `data/synthetic/demo_vignettes.json` from `scripts/deploy/generate_candidate_source_roster.py` (strict-lane pause rule), or changing `traffic_accident_billing.py`.

### Review
- Removed `src/bilun/domain/billing/demo_vignette_lookup.py` and `tests/unit/domain/billing/test_demo_vignette_lookup.py`.
- Added `recommended_package_code_for_claim` and `resolve_catalog_itemized_alternative` in `src/bilun/domain/billing/claim_strategy.py` so optional-override package and itemized totals resolve from claim/performed procedure lines and the as-of EK-2B/EK-2C catalogs.
- Updated `src/bilun/domain/prose_rules/gap_closing.py` and `src/bilun/domain/prose_rules/fatura_inceleme.py` so `is_emergency` is derived from `claim_type` and `department`, never `scenario_tag`.
- Verified `ruff` clean and `1,275` synthetic, billing, and deploy unit tests + `18` `test_gap_closing_for_context.py` tests pass.

---

## Task: Start the laptop CI runner automatically while jobs are queued (2026-10-12)

### Goal
A pushed PR, or a merge to main, has its backend and frontend jobs served by the laptop within about a minute without anyone starting `laptop_runner.py`, and no runner stays registered once the queue is empty.

### Subtasks
- [x] `tools/ci/laptop_watcher.py`: each run reads the jobs queued for the `bilun-laptop-ci` label (runs that are `queued` or `in_progress`; a run last updated more than a day ago is a stale record and ignored); only while jobs are queued, no runner with the label is online and the image exists, it starts `laptop_runner.py --jobs 1`, re-reads the queue after every job and stops after `--max-runs`.
- [x] Safety: a file lock stops overlapping runs; a runner that receives no job within `--pickup-timeout` is stopped with SIGTERM (the script then removes its container, volume and registration); a busy runner is never stopped; SIGTERM to the watcher is forwarded; a failing runner makes the run exit 1 and the next timer run retries.
- [x] `tools/ci/systemd/bilun-ci-watcher.service` (oneshot) and `bilun-ci-watcher.timer` (30 s after start, then 60 s after each run ends). The service runs a copy under `~/.local/share/bilun-ci`, so a PR branch checked out in a working tree cannot change code that an unattended timer runs with admin credentials.
- [x] Tests in `tests/unit/tools/test_laptop_watcher.py` with a fake GitHub and a fake process: label, status and age filter; nothing queued; online runner present; serve until empty; max runs; never-picked-up runner stopped; busy runner kept; failure stops the run; dry run; missing image; lock; missing image argument.
- [x] Real checks: `ruff check`, the new tests, `systemd-analyze --user verify`, `--dry-run` against GitHub, and one run as a transient systemd user service (gh keyring and docker are reachable there).
- [x] `docs/operations/AI-RUNBOOK.md`: install, update, status, log and stop commands, and the limits (laptop awake, Docker up, linger for logged-out use).
- [x] Independent review of the diff by a second agent (findings and what was done about them in Review below).
- [ ] PR against main. Nothing is installed on the laptop before it merges.

### Out of Scope
Installing or enabling the timer on the laptop (done by the owner after the merge), changes to `laptop_runner.py`, the CI image, the workflows or the runner labels, an always-on runner, GitHub-hosted runners.

### Review (2026-10-12)
An independent review found two real bugs and several risks; all were checked against the code before acting on them.
- Real: systemd signals the whole cgroup on stop and the watcher then forwards another SIGTERM, which can abort `laptop_runner.py`'s cleanup (its handler raises even inside `finally`). Fixed with `KillMode=mixed`, `TimeoutStopSec=120` and `SuccessExitStatus=143`.
- Real: only `RuntimeError` was caught around the status poll, so a non-JSON answer or a missing `gh` could orphan a running job. `github()` now turns every failure (missing `gh`, timeout, non-JSON) into `RuntimeError`, and the poll catches any exception and retries.
- Risk: a hung `gh` or `docker` call would stall the timer for good. Both calls have a 60 s timeout and the service has `TimeoutStartSec=8h`.
- Risk: a job that asks for a label our runner lacks would make an idle runner start and stop all day. A job now counts only if its labels are a subset of the runner's.
- Smaller: `--dry-run` reported "would start" without checking the image; a down Docker daemon was reported as a missing image; a misleading `Nice=`; runbook statements about stopping, linger with the keyring-stored `gh` login, and where the image tag lives were corrected.
- Tests: the behaviours the review found unpinned (runner-label filter, kill fallback, pickup-timeout boundary, runner command line, defaults, SIGTERM handler, non-JSON and missing-`gh` answers, a job assigned after the pickup timeout) now have tests, and the vacuous `online == []` assertion is gone. A mutation check of 14 injected regressions found one survivor (a runner that gets its job after the timeout); a test now pins it, so 14 of 14 are caught.
- Found by the first live run (a transient systemd unit serving the queued jobs): `gh` failed its very first connection with "error connecting to api.github.com" and the run exited 1 after 10 s; two retries a moment later worked. `github()` now asks again up to 3 times, 5 s apart, for a dropped connection only (a real API error such as 401 is not retried); the runbook already says to retry connection errors.
- Left as is on purpose: a status that keeps failing never stops a runner, because not knowing is not a reason to stop a job; an unpicked runner exits 1 so the failure is visible in `systemctl --user status`.

## Task: Fix icu_puani day counting and add §2.4.4.H ICU tier overbilling detector (Safa675/Bilun#242)

### Goal
`icu_puani.py` derives ICU days from billed ICU procedure lines (`510090` and `P552001`–`P552008`) without defaulting to 3rd-level `P552003` or treating the entire hospital stay as ICU days, and `detect_icu_tier_overbilling` flags 3rd-level ICU packages (`P552003` / `P552008`) billed without 3rd-level organ-support / invasive mechanical ventilation / dialysis / ECMO procedures on the episode.

### Subtasks
- [x] 1. Update `src/bilun/domain/prose_rules/icu_puani.py` (`detect_icu_puani_opportunities`) to compute ICU days from billed `510090` and `P552001`–`P552008` procedure lines (capped by hospital LOS) and remove the `_DEFAULT_INTERMEDIATE_CODE = "552003"` fallback when no intermediate package is on the claim.
- [x] 2. Implement `detect_icu_tier_overbilling` in `src/bilun/domain/prose_rules/icu_puani.py` and wire it into `src/bilun/domain/billing/engine.py` (`analyze_claim`) so 3rd-level ICU packages (`P552003` / `P552008`) without 3rd-level qualifying organ-support/ventilation/dialysis/ECMO procedure codes emit a §2.4.4.H audit-exposure finding with the price gap to 2nd-level (`P552002` / `P552007`) and 1st-level (`P552001` / `P552006`).
- [x] 3. Update and expand `tests/unit/domain/prose_rules/test_icu_puani.py` to test ward stays with 3-day ICU segments, no-default-`P552003` behavior, and `detect_icu_tier_overbilling` (with and without 3rd-level qualifying procedures); run unit tests and `ruff`; commit, check `main` CI, push, open PR for `#242`, and return to `main`.

### Out of Scope
Re-generating the synthetic demo cohort parquets or adding new columns to `ClaimHeader`.

### Review
- **Delivered:**
  - `src/bilun/domain/prose_rules/icu_puani.py`: replaced hospital-LOS day counting and the `_DEFAULT_INTERMEDIATE_CODE = "552003"` fallback with `_infer_billed_icu_days` (derived from `510090` and `P552001`–`P552008` quantities/distinct service dates, capped by hospital LOS), and implemented `detect_icu_tier_overbilling` for §2.4.4.H / EK-2/C-A 3rd-level ICU packages (`P552003` / `P552008`) billed without invasive ventilation, dialysis/hemofiltration/plasmapheresis, or ECMO/cardiopulmonary-support procedure codes.
  - `src/bilun/domain/billing/engine.py`: wired `detect_icu_tier_overbilling` into `analyze_claim` alongside `detect_yatak_icu_overlap`.
  - `tests/unit/domain/prose_rules/test_icu_puani.py`: updated `test_basamak_inferred_from_submitted_package` and added 4 unit tests covering segmented ICU day counting, no-default-`P552003`, and `detect_icu_tier_overbilling`.
- **Verification:** `78 passed` across `test_icu_puani.py`, `test_claim_compliance.py`, and `test_claim_compliance_pipeline.py`; `ruff check` clean.

## Task: Stop counting missing amounts as zero in uplift, savings and recoverable totals

### Goal
Each `?? 0` flagged in the zero-for-null sweep is classified with evidence; the ones where a missing amount is shown as a bare number now show a dash or a labelled partial figure (stacked on the billed-at-risk fix).

### Subtasks
- [x] Verify the six flagged places against the API types (`frontend/src/lib/domains/sut.ts`), the backend response models (`src/bilun/api/schemas.py`) and the callers.
- [x] Fix (a): `SessionUpliftSection` fallback sum and `PatientInvoiceTable` opportunity fallback (dash / partial note, en and tr messages); shared `sumKnownAmounts` / `amountCoverage` next to `complianceBilledAtRiskSummary`.
- [x] Leave (b) unchanged with a one-line reason comment: `OptionalOverrideSection`, `SUTOptimizerTab` grand total, `recoverableUplift`, `sutChatPageContext` copay savings.
- [x] Tests: all present, one null, all null, en and tr (`SessionUpliftSection.test.tsx`, `PatientInvoiceTable.test.tsx`, `workspaceViews.test.ts`).
- [x] `npx tsc --noEmit`, full `npx vitest run`, eslint on changed files, `npm run build`.
- [ ] Draft PR against main, stacked on the billed-at-risk PR; do not merge before the pending production deploy is activated.

### Out of Scope
Backend, rules, exactness semantics, API shape. Backend defaults of 0.0 in the response models are noted in the PR, not changed.

## Task: Never show a zero or partial sum for missing billed amounts at risk

### Goal
The compliance view's "Billed amount at risk" stat shows an exact sum only when every counted at-risk action has a billed amount; otherwise a dash or a labelled partial sum with "x of y findings".

### Subtasks
- [x] Reproduction reported by independent review (not re-run against the live API here): SENTETIK-HASTA-0003 (5 nulls shown as 0.00 TRY) and 0029 (25,000.00 TRY = 2 of 7 findings) on the synthetic cohort; 0017 (2 x 192.32) is complete and unchanged.
- [x] Add `complianceBilledAtRiskSummary` ({total, known, count}) in `frontend/src/lib/workspaceViews.ts`; `complianceBilledAtRisk` returns null instead of a partial sum; keep the `drug_indication` exclusion.
- [x] Render dash / partial hint in `ComplianceViewSection.tsx` with en and tr messages.
- [x] Tests: one null, all nulls, no nulls, drug_indication exclusion, en and tr rendering.
- [x] `npx tsc --noEmit`, full `npx vitest run`, `npm run build`.
- [ ] Draft PR against main; do not merge before the pending production deploy is activated.

### Out of Scope
Backend, rules, exactness semantics, API shape, and other aggregations (uplift/savings fallbacks) that are not this billed-at-risk total.

## Task: 5 Ekim kaynak yenilemesi ve doğrulanmış paket entegrasyonu

### Goal
Main499dff4 tabanında PR154(150 dahil), PR153(152 dahil) ve PR151'i tek kez birleştir; pozitif resmî kanıtla desteklenen 5 Ekim penceresi ve kanonik ortak veri kapanışıyla bağımsız incelenmiş draft PR ve exact-head full CI teslim et.

### Subtasks
- [x] Güncel main/5PRhead/exactCI ve repoAGENTS/lessons doğrula; özgün dirtyfiles koru.
- [x] Ayrı integration-2026-10-05 ve source-renewal-2026-10-05 çalışma ağaçlarını kur.
- [x] Semantic child planını review et; PR153→PR152 exactdiff yalnız contextmemoization üç dosyadır; prioroutcome/evidence kodu aynı, ikinci taşıma yok.
- [x] Git merge sırasıyla PR154 → PR153 → PR151; üç ort merge temiz, b5beedda; ortak evidence final üretime kadar provisional.
- [x] Kaynak writer RG33391/SGK resmî gözlemlerini 06:08:50–06:12:51UTC kaydetti; 12 [5Ekim,5Ekim] continuity eklendi, 6Ekim 12/12 review_required. Kaynak worktree'sinde dokuz tam dosya 691PASS/3warnings.
- [x] Frozen20sourcepath gerçekSHA doğrulamasıyla integration tree'ye taşındı; source tasks/todo dışlandı, eski receipt/history kimlikleri değişmedi.
- [x] Mevcut compiler iki WRITE/iki CHECK134byte-stable; coverage bütün değer/order/dtype eşitliğiyle reviewed4parquet korundu (yerel pandas serialization farkı QA'da ayrı). Consumer496input/68test/134output → catalog yalnızreportpin → final159dependency evidence kapandı.
- [x] Kaynak691PASS, birleşiksemantics306PASS ve boundaries26PASS; compiler/parity23/0/Ruff/surfacing/freshcoverage1PASS; rawcorpus40b2/vector683a/verifier73f/policy/pending55/organ3/CLOSED invariants korundu.
- [x] Ayrı incelemeci final604PASS/2warnings/37.33s ve2410watchedfile0SHAchange bildirdi; finalhashaudit/code/source P1/P2none. YeniCI henüz çalışmadı, exactheadmapping mevcuttestedfileSHA'larıyla kaydedilecek.
- [ ] CI beforepush kontrolünden sonra onaylı draft integration PR yayımla; exact final head hosted fullCI sonucunu gerçek loglarla doğrula.
- [ ] Main'e merge yapmadan verifiedtree/head/CI ve tekrar etmeyen merge planını koordinatöre teslim et.

### Out of Scope
Üretim/VPS/deploy/mainmerge, mesothelioma runtimegate açılması veya yeni klinik kriter/admission, clinical_eligibility_complete=true, tarihî boşluk/hukukaltı doldurmak, kanıtsız tarih/hash uzatmak, genel mimari, historicalold→3e deploymentverifier/servingpermission genişletmek, tüm ingest/annex yenilemesi veya özgün dirtyfiles/stash temizliği.

### Specification and plan review
Kullanıcı 2026-10-05 06:01UTC'de kaynak yenileme, sıralı paket entegrasyonu, ortak veri regeneration ve birleşik CI için 'do it' dedi. Aynı adımlar için yeniden onay gerekmez. Python3.13 mevcut Bilun .venv; Git approved remote; main499 exactAPI identical ve tümPRheadCIgreen. .agents/skills seçili ortamda mevcut değil; repoAGENTS ve ilgili role/lessons okundu. Başarı: 12 bounded family yalnız kanıtlı5Ekim source review, 6Ekim unsupported/falsecomplete; legal/gaps, exact3 organneutral ve55pending korunur; PR151 CLOSED; historicalreceiptc4→40b2 ve immutable releaseverifier korunur; current maps/produceroutputs/querysource eşitliği; bağımsızreview ve exactheadfullCIgreen. Sharedcatalog/report/coverage aşamalarında tek namedwriter; Git/publish root only. Runtime yeni semantik gerekiyorsa açık risk bildir, unaffected work devam.

### File ownership
Root: Git integration, tasks/todo, delivery-status ve yayın. Kaynak writer ayrısourceworktree: yeni5Ekimreview/captures/receipt, clinical_versions yalnızappendwindow/review, .gitattributes/docs ve source_authority/source_authority_transport/followup_request_integration/mecasermin_request_integration/mecasermin_known_as_of/enteral_ravulizumab_clinical/report_documentation_completion/renal_runtime_observations/sma_antifungal_documentary_facts dar tarih testleri. Semantic child: yalnız gerektiğinde explicitlyassigned conflict/runtime paths; şu an read-only. Closure child: final tekowner olarak compiler/rulemanifest/4coverageparquet+JSON/commonconsumerreport/catalogreportpin aşamaları root GO ile; kaynağın Oct5catalog transportu bitmeden sharedwrite yok. Bağımsızreview ayrıchild, implementationowner olamaz.


## Task: Implement public billing and protected developer access

### Goal
Implement the approved public-billing/developer-login plan, verify security and billing behavior, and publish a new reviewed PR without deploying.

### Subtasks
- [x] Review the approved plan and repository instructions; create isolated branch `feat/public-billing-developer-access` from current `origin/main` at `3db12d53` (includes deployed #99, billing UX #100 and refactors #101–106).
- [x] Implement explicit backend access policies, authoritative capabilities and public response projections.
- [x] Secure officer chatbot context/tools and bound public computation.
- [x] Implement capability-driven frontend, developer sign-in, logout/expiry and public billing workflow.
- [x] Add release migration instructions, protected health probes, credential/session cutover support and asset confidentiality verification.
- [x] Review integrated behavior, run focused tests, full CI parity and production browser security checks; resolve failures.
- [x] Review final diff, verify branch CI status, publish/attach a new PR and confirm its checks.

### Out of Scope
Merging, live deployment, live credential rotation, changing clinical/payment calculations, new real-patient datasets or multiuser/SSO provisioning.

### Review
Plan approved by the user; implementation follows `plans/security/2026-09-29-public-billing-developer-access-plan.md`. Main checkout and existing deployment are preserved. Public access defaults disabled pending the documented release cutover.

Implementation & verification evidence:
- Backend access control, authoritative session resolution, and public JSON response projections verified.
- Fixed cohort projection test `test_public_projection_preserves_cohort_business_results_and_cached_nulls` by popping internal `wavea_evidence_detail` payload before projection comparison.
- Fixed Next.js Playwright strict mode conflict on `getByRole("alert")` in `test-access-browser.mjs` by filtering on text.
- Full CI test parity:
  - Ruff check (`ruff check src/ scripts/`): clean
  - Rules compiler check (`python scripts/sut/compile_rules.py --check`): 134 rule/manifest artifacts byte-identical
  - Drug manifest parity check (`python scripts/sut/audit_manifest_parity.py --drug-only`): 23 manifests scanned, 0 issues
  - Unit tests: 964 passed in 538s
  - Cohort projection test: 1 passed in 86s
  - Vitest frontend suite: 70 files passed, 402 tests passed in 17s
  - TypeScript build check (`npx tsc --noEmit`): clean
  - Frontend production build (`next build`): clean
  - Browser E2E security tests (`node scripts/test-access-browser.mjs`): all 4 scenarios passed
  - Public asset verification (`verify_public_assets`): 52 files checked, 0 problems
  - `git diff --check`: clean

---

## Task: Use recoverable_uplift_try for bed-day and ICU totals and actions (Safa675/Bilun#233)

### Goal
`YatakPuaniReview.confirmed_yatak_try` and `collect_billing_actions` read `recoverable_uplift_try` (skipping zero-gap bed-day actions), and `IcuPuaniReview.confirmed_icu_try` uses `recoverable_uplift_try` even when it is `0.0` instead of falling back to `total_try`.

### Subtasks
- [x] 1. Update `YatakPuaniReview.confirmed_yatak_try` and `IcuPuaniReview.confirmed_icu_try` in `src/bilun/domain/billing/types.py` to use `row["recoverable_uplift_try"]` whenever `row.get("recoverable_uplift_try") is not None` (preserving `0.0`).
- [x] 2. Update `collect_billing_actions` in `src/bilun/domain/billing/billing_actions.py` to read `recoverable_uplift_try` for `yatak_puani` and skip `yatak_puani` action rows when the gap is `0.0`.
- [x] 3. Update and add unit tests in `tests/unit/domain/prose_rules/test_yatak_puani.py` and `tests/unit/domain/prose_rules/test_yatak_icu_overlap.py`; run pytest and ruff.

### Out of Scope
Re-generating the synthetic demo cohort parquets.

### Review
- **Delivered:** `YatakPuaniReview.confirmed_yatak_try` and `IcuPuaniReview.confirmed_icu_try` read `recoverable_uplift_try` when present (including `0.0`), and `collect_billing_actions` reads `recoverable_uplift_try` for `yatak_puani` and omits zero-gap bed-day action rows.
- **Verification:** `62 passed` across `test_yatak_puani.py`, `test_yatak_icu_overlap.py`, `test_icu_puani.py`, `test_billing_actions.py`, `test_claim_integration.py`, and `test_block_spec_integrity.py`; `ruff check` clean.

---

## Task: Complete hotspot refactoring delivery F — audit decomposition

### Goal
Give audit discovery, classifications, reconciliation, rendering, and CLI their own modules without changing generated outputs or the supported CLI, then publish the final focused PR after E.

### Subtasks
- [x] Create an isolated F worktree from C head `b5bae476` with D/E integration deferred until their verified merges.
- [x] Independently review the approved F boundaries, existing imports/test patch points, source root behavior, and every CLI mode before code edits.
- [x] Capture byte-exact baseline JSON/Markdown, CLI outputs and 1,119 tracked artifact hashes in this worktree before any Python test writers.
- [x] Mechanically extract model, metadata, Python source resolution, inventory validation/rollups, rendering and CLI into `scripts/audits/rule_surfacing/`; keep the old script pathname and callable compatibility.
- [x] Prove generated JSON/Markdown and all supported CLI modes are byte identical; preserve missing-surface and source-contract failures.
- [x] In a separate commit, replace only the exact-format literal deep-link map regex using the bounded token reader, with realistic valid syntax and computed/spread/unresolved rejection regressions.
- [x] Run focused audit tests, full backend gates, standalone CLI from repository and isolated cwd, sequential compiler/manifest checks, and tracked artifact drift checks.
- [x] Obtain independent review of source-vs-classification proof, path handling, imports/patch points and diff; resolve substantive findings.
- [x] Integrate verified E main, rerun affected checks, publish focused PR #106 and request task attachment; complete independent integration review.
- [ ] Verify current-revision CI/GitHub feedback and merge only after all gates pass.
- [ ] Run both frontend and backend gates on final integrated main and complete all three responsibility-locality walkthroughs in the approved plan.
- [ ] Record PR/revisions/verification and finish the agreed refactor only after the completion audit passes.

### Out of Scope
Changing detector semantics, rule coverage/classifications/counts, audit report formatting, frontend/clinical/financial behavior, canonical findings, new dependencies, production data/cache, deployment and unrelated user work.

### Review
The independent read-only inventory defines explicit ownership across `model`, `metadata`, `python_sources`, `surface_sources`, `inventory`, `render`, and `cli`, with the old script retaining compatible callables and a single root/path context. Tests patch nine old-script path globals, three path helpers, and `PATIENT_REPORT_META`; the extraction must keep those seams observable. The map reader is a separate bounded change after pure extraction. Baseline direct `python -I` behavior was captured from `/tmp` for default, check, full/chunk/combined prints and invalid arguments in `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`; successful full JSON and Markdown hashes exactly match C's baseline. All 1,119 tracked artifacts are unchanged. F can be implemented in parallel with D/E integration, but publication remains last. Worktree `/root/worktrees/bilun-audit-decomposition`, branch `refactor/hotspot-audit-decomposition`.

The frozen mechanical extraction moves audit ownership to the planned modules while retaining a script-path facade with explicit call-time `AuditContext` from the original root, patched globals and three helper callbacks. Independent review found no actionable issue: all 52 original function bodies are unchanged apart from explicit context plumbing, all 27 facade wrapper signatures and 12 metadata tables remain compatible, and import/source-proof boundaries hold. Scoped Ruff and 78 focused tests passed. All 12 captured direct CLI cases preserve exit codes and stdout; successful modes and parser-exclusivity stderr are byte-identical, while invalid-chunk exception text remains exact with expected relocated traceback frames. Generated JSON/Markdown bytes and all 1,119 tracked artifact hashes remain unchanged. Evidence and the independent review are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`. The literal-map reader was implemented and reviewed in a separate second commit.

The second stage replaces only the exact-layout map regex with a bounded literal reader in `surface_sources.py`. It accepts the existing 17-entry map plus ordinary comments/whitespace, literal quote styles, trailing commas and explicitly supported type annotations; it rejects dynamic/computed/spread/unresolved/duplicate entries and unsupported syntax. Independent review found a regex-literal false-evidence case, which was fixed by a local fail-closed top-level slash guard and four regressions; re-review found no remaining blocker and A's tokenizer/resolver remain unchanged. Before E integration, corrected source passed 122 focused tests, all 12 captured CLI exit/stdout comparisons, byte-identical full JSON/Markdown, 4,133 full backend tests (eight warnings), full/scoped Ruff, isolated direct CLI `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23/zero). All 1,119 tracked artifact hashes remained unchanged after every gate. A pre-fix interrupted run is separately labeled and not counted. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

F was rebased onto E's merged main `46a694d0`; all reviewed F source/tests remained byte-identical apart from three trimmed signature spaces with unchanged AST. [PR #106](https://github.com/Safa675/Bilun/pull/106) opened at this integrated candidate. Independent final review cleared its source and contracts. Local integrated gates passed 964 focused and 4,145 full backend tests (three/eight warnings), TypeScript, 383 frontend tests in 65 files, production build, full/scoped Ruff, isolated audit and all 12 CLI modes, exact generated JSON/Markdown, compiler `--check` (134 byte-identical artifacts) and manifest parity (23/zero). All 1,119 tracked data/report artifact hashes were unchanged after every gate. The app attachment request did not return, so attachment is unconfirmed. Its initial current-source CI run `36489935324` passed both jobs at `6fb194cd`; final documentation-only PR-head CI, merge and merge-main CI remain. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

---

## Task: Count patients with recoverable > 0 in n_patients_with_actions (Safa675/Bilun#234)

### Goal
`CohortRecoverySummary` exposes `n_patients_with_actions` (counting patients with `total_recoverable_try > 0`) while keeping `n_patients` as the loaded patient count, and `RevenueRecoverySummary.tsx` displays `n_patients_with_actions` under "Eylemli Hastalar" / "Patients with Actions".

### Subtasks
- [x] 1. Add `n_patients_with_actions: int = 0` to `CohortRecoverySummary` (`src/bilun/domain/billing/types.py`), compute it in `build_cohort_recovery_summary` (`src/bilun/domain/billing/cohort_summary.py`) and backfill in `get_revenue_recovery` (`src/bilun/api/routes/optimization.py`), and allowlist it in `src/bilun/api/public_contracts.json`.
- [x] 2. Add `n_patients_with_actions?: number` to `CohortRecoverySummary` in `frontend/src/lib/domains/sut.ts`, update `RevenueRecoverySummary.tsx` and `SUTOptimizerTab.tsx` cohort filtering, and add unit tests in backend and frontend.

### Out of Scope
Changing `n_patients` semantics or regenerating the synthetic demo cohort parquets.

### Review
- **Delivered:** Added `n_patients_with_actions` across `CohortRecoverySummary`, `cohort_summary.py`, `optimization.py`, `public_contracts.json`, `sut.ts`, `RevenueRecoverySummary.tsx`, and `SUTOptimizerTab.tsx`.
- **Verification:** Backend `test_cohort_recovery_summary.py` and frontend `RevenueRecoverySummary.test.tsx` pass; `ruff check` clean.

---

## Task: Complete hotspot refactoring delivery E — drug routing, constraints and evaluation

### Goal
Make route selection, ordered constraints and detailed-result construction independently changeable while preserving every existing public result and clinical decision. Deliver a separate PR after verified D.

### Subtasks
- [x] Review approved Phase E and the stable D implementation for ownership, public wrapper/patch seams, raw-versus-decorated violation shape and ordered constraints.
- [x] Create an isolated E worktree at C head `b5bae476`, with D integration deferred until D is verified and merged.
- [x] Add targeted dynamic-wrapper/default-loader, competing-failure precedence and primary-plus-supplemental identity tests and prove them on the unchanged monolith; re-run after D integration before source edits.
- [x] Integrate verified D main, refresh import/patch inventory, and compare the unchanged D full-output baseline.
- [x] Mechanically extract routing, constraints and evidence helpers into the three approved internal modules, retaining callable identities, public wrappers and cached objects.
- [x] Give the internal evaluator explicit rules; keep default loading in the facade and preserve first-hit, nested payload and supplemental-ID behavior.
- [x] Compare the immutable complete result snapshot and new pre-extraction tests; run focused/full backend, Ruff, isolated audit, compiler/manifest gates sequentially and tracked-artifact hash checks.
- [x] Obtain independent review of AST/signature/dependency and output parity; resolve substantive findings.
- [x] Publish E PR and request task attachment, verify current-revision CI/GitHub feedback, merge with exact-head guard after checks pass, then verify main CI.
- [x] Record PR/revision/evidence and advance to F.

### Out of Scope
New clinical rules or messages, route semantics, corpus/cache changes, canonical findings/projections, rule data/schema/artifact changes, audit parser expansion, deployment or unrelated cleanup.

### Review
The read-only map and explicit extraction traps are recorded at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e/read-only-extraction-checklist.md`. E's source changes wait for D integration; targeted baseline tests can be authored on the unchanged monolith in parallel. Worktree `/root/worktrees/bilun-drug-evaluation`, branch `refactor/hotspot-drug-evaluation`.

Three targeted groups (ten cases) passed against the unchanged C monolith at `b5bae476` before E source work: facade default-loader calls for `None` versus explicit `[]`, dynamic public detailed calls and context order/orphan behavior, first-hit precedence across overlapping failures, and primary/supplemental inner-versus-outer identities. Ruff passed. Source/test hashes and logs are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. The verified D source can be integrated provisionally before its PR merge; E publication remains dependent on D's final merged main and hosted gates.

After provisional D integration, 12 boundary/cache tests and the immutable complete comparator passed before E source edits. The reviewed extraction gives routing, constraints and evaluation their own modules while keeping all 46 other original function ASTs, 47 signatures, 44 exact callable aliases and four cache objects. The 20,339,608-byte detailed/canonical/legacy/cache/API payload snapshot remains identical. Independent review found no actionable finding, including first-hit order, raw/common nested fields and supplemental inner/outer IDs. The final isolated E source passed 868 focused tests, 4,087 full backend tests (eight warnings), full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues), with all 1,119 tracked artifact hashes unchanged after each gate. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. Rebase onto D's merged main and hosted current-revision CI remain before publication/merge.

E was rebased onto D's head-guarded merged main `ec368706` with byte-identical E source/test content. The immutable complete comparator, 868 focused tests (three warnings), Ruff and isolated audit `--check` passed again on the integrated tree; all 1,119 current tracked artifact hashes remain unchanged. D's merge-main CI run `36487251655` passed. PR publication and E current-head hosted CI remain.

E publication: [PR #105](https://github.com/Safa675/Bilun/pull/105) at `671fc9e0` passed both hosted jobs in run `36488702448`, independent review and feedback review, with no human/inline findings (Copilot reported quota exhaustion). It merged with an exact-head guard as `46a694d054ec3a557e25977de386c09405bce215` at 2026-09-28 21:57:26 UTC; the merged tree equals the tested branch. Both main CI jobs passed in run `36489455355`. The app attachment call did not return, so attachment is unconfirmed. Delivery F was then rebased onto this merged tree.

---

## Task: Restrict anaesthesia uplift to EK-2B §6 surgeries, use service-date EK-2B §4 group table, and subtract billed anaesthesia (Safa675/Bilun#230)

### Goal
`detect_anestezi_puani_opportunities` evaluates only EK-2B §6 surgical lines (`600000`–`629999`), resolves single-surgery (`550130`–`550190`) and multi-surgery same-session (`550200`–`550260`) anaesthesia groups from the service-date EK-2B §4 group table (with no 5,000 puan ceiling), subtracts already-billed anaesthesia (`550130`–`550346`) from `recoverable_uplift_try`, and cites SUT §2.2.2.A + EK-2/B §4 instead of §2.4.4.A (ESWL).

### Subtasks
- [x] 1. Restrict `_surgical_puan` in `src/bilun/domain/prose_rules/anestezi_puani.py` to EK-2B §6 surgical codes (`600000`–`629999`) so lab, exam, bed, and anaesthesia codes are skipped.
- [x] 2. Replace the wrong hardcoded `1–5000` group table in `anestezi_puani.py` with the service-date EK-2B §4 group table (`2026-07-07` onwards: A1 `>=39001`, A2 `18501–39000`, A3 `9001–18500`, B `6001–9000`, C `3005–6000`, D `1301–3004`, E `0–1300`; plus `2026-01-01`, `2022-09-03`, and `2020-03-11` historical tables) and emit one increased anaesthesia (`550200`–`550260`) per multi-surgery session.
- [x] 3. Subtract already-billed anaesthesia (`550130`–`550346`) from `recoverable_uplift_try`, update `AnesteziPuaniReview.confirmed_anestezi_try` and SUT §2.2.2.A / EK-2/B §4 citation, and update unit tests (`test_anestezi_puani.py`, `test_elkitabi_tablo23.py`).

### Out of Scope
Newborn/geriatric ASA 3–4 modifiers (`550270`–`550346`) when ASA score is not present in claim inputs.

### Review
- **Delivered:** Restricted `_surgical_puan` to EK-2B §6 (`600000`–`629999`), implemented service-date EK-2B §4 single (`550130`–`550190`) and multi-surgery (`550200`–`550260`) group tables, subtracted billed `550130`–`550346` into `recoverable_uplift_try`, updated `AnesteziPuaniReview.confirmed_anestezi_try` and SUT §2.2.2.A citation.
- **Verification:** `test_anestezi_puani.py`, `test_elkitabi_tablo23.py`, and `test_claim_integration.py` pass; `ruff check` clean.

---

## Task: Prepare and implement hotspot refactoring delivery D — drug corpus and matching

### Goal
Extract drug matching and corpus responsibilities behind the existing public module with exact output/cache compatibility, then integrate after delivery C as its own verified PR.

### Subtasks
- [x] Read the approved phase D/E boundaries and create an isolated worktree at main `63df008d`; rebase onto the verified delivery C main before publication.
- [x] Independently inventory public/private accesses, cached objects and monkeypatch seams; review the planned ownership before runtime edits.
- [x] Capture complete representative baseline detailed/canonical/legacy/cache/API results using existing fixtures, including the plan's edge cases, and save an executable before/after comparison outside tracked artifacts.
- [x] Add only meaningful missing compatibility regressions exposed by the extraction risk.
- [x] Extract pure matching and corpus/coverage responsibilities with the same cache instances and shallow-copy semantics; preserve public names and signatures.
- [x] Compare complete outputs and source/audit contracts, obtain independent review, and resolve substantive findings.
- [x] Run focused drug checks and full backend gates sequentially with tracked artifact hash checks; preserve all data and financial/clinical behavior.
- [x] Integrate the verified predecessor, publish and request task attachment for a focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record evidence and advance to delivery E.

### Out of Scope
Routing/constraint/evaluation extraction (delivery E), semantic or clinical rule changes, canonical/API/cache redesign, generated corpus/manifest rewrites, new dependencies, deployment, and live service changes.

### Review
Preparation may run in parallel with frontend deliveries in this isolated worktree; integration remains B then C then D. The user approved the full hotspot plan and unattended execution with merging only after tests and independent review pass. Runtime edits begin after the concrete baseline/ownership review. The original `/opt/Bilun` checkout remains untouched.

Baseline/ownership review is complete before runtime edits: matching owns pure predicates/normalization/specialty/INN/ICD functions; corpus owns paths/loading/manifest/subsection coverage/promotion/stop conditions. All four original decorated caches and shallow list/dictionary identities remain contracts. The immutable comparator captures 54 line cases, nine full report contexts, all 968 corpus rules, detailed/canonical/legacy/cache/API projections and coverage, including full-corpus order permutations. A second monolithic capture is byte-identical (20,339,608 bytes; SHA256 `5c046be33ba9eccf305034baac29bc1b02ff9b7542fd1e272f4154e9a403d7c1`). It verifies loaded `bilun` and `src.bilun` modules originate inside this worktree (284 origins). The focused baseline passed 122 tests including two missing public cache/default-input contracts; 1,119 tracked artifact hashes remained unchanged. Evidence and executable comparator: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-d`.

The extraction preserved all 47 original function ASTs and directly re-exports all 22 moved callables, including the four original cache objects, with no internal facade/billing dependency. The immutable complete payload snapshot is byte-identical after extraction. Independent source/runtime review found no actionable regression. Focused checks passed 858 tests; full backend passed 4,077 tests with eight warnings; full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues) passed. Hashes of all 1,119 tracked data/report artifacts are unchanged after every writer. These results apply to the isolated D source before integration on C main; publication and current-revision CI remain.

Delivery D publication: [PR #104](https://github.com/Safa675/Bilun/pull/104) at `79fefdcf` passed both hosted jobs in run `36486246248` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It merged head-guarded as `ec368706047d3b3d95ddd5e76131825aa1f18940` at 2026-09-28 21:36:38 UTC; its tree equals the tested branch. Main CI run `36487251655` passed. The app attachment call did not return, so attachment is unconfirmed.

D was rebased onto C's merged main `20873ff6` without any source/test content change. The frozen full-output comparator remained byte-identical; the integrated tree passed 858 focused tests (three warnings), Ruff and isolated audit `--check`, with hashes of all 1,119 current tracked artifacts unchanged after each check. Relative to D's original A base, only the previously reviewed B report matrix provenance differs. C's merge-main CI run `36484758171` passed. D PR publication and current-head hosted CI subsequently passed, as recorded above.

---

## Task: Narrow §3.1.4(g) coronary-stent keyword and zero informational §3.1.4 risk (#231)

### Goal
Ensure `3.1.4.(g).coronary_stents` matches only coronary stents (not tracheal, urology, or other non-coronary stents), keep informational `§3.1.4` findings at `0.0` risk amount (`0 TL` billed at risk), and continue evaluating subsequent `§3.1` rules on lines that match an informational rule.

### Subtasks
- [x] Replace bare `stent` with `stent, koroner` in `data/gazette/prose_rule_sources/material_bundling/3.1.4.yaml` and recompile `data/gazette/prose_rules/material_bundling_prose.json`.
- [x] In `src/bilun/domain/prose_rules/material_bundling.py`, set `risk_amount = 0.0` when `action.get("severity") == "info"` and do not terminate the per-line rule loop on `severity == "info"` matches.
- [x] Add unit tests in `tests/unit/domain/prose_rules/test_material_bundling.py` covering non-coronary stents (`STENT, TRAKEAL, SİLİKON`, `Üreteral J stent`), coronary stents (`KORONER STENT, İLAÇ SALINIMLI`, `STENT, KORONER, BALONA MONTE EDİLMİŞ ÇIPLAK`), zero billed-at-risk on `§3.1.4` info findings, and non-info `§3.1` rules firing alongside `§3.1.4` info findings.

### Out of Scope
Re-architecting other `§3.1.4` sub-clauses or line-level billed-at-risk deduplication (`#232`).

### Review
Replaced bare `stent` with `stent, koroner` in `3.1.4.(g).coronary_stents`, recompiled `material_bundling_prose.json`, set `risk_amount = 0.0` for `severity == "info"` findings, and allowed subsequent `§3.1` rules to evaluate after an informational rule match. Verified with `test_material_bundling.py`, `test_material_bundling_golden.py`, `test_material_bundling_gate_b.py`, and `tests/smoke/test_sut.py`.

---

## Task: Complete hotspot refactoring delivery C — section presentation decisions

### Goal
Give copay, strategy, drug review, and material presentation clear local ownership while preserving current payload precedence, row decisions, focus behavior and UI output, then deliver a separate verified PR after B.

### Subtasks
- [x] Review delivery C against the actual extracted code and tests; create an isolated branch at B commit `9a539d5d`, to integrate onto verified main before publication.
- [x] Add focused compatibility regressions and verify them against unchanged B components before rewiring those components.
- [x] Extract section-local copay/strategy models preserving existing overlapping filters, row order, first-row header selection, null/zero values, and shared `billingReportFields` behavior.
- [x] Make drug display states explicit and split substantial card/legacy/evaluation rendering while keeping section-owned refs, focus effects and the same precedence/array identity.
- [x] Split material tables into named local components while retaining simultaneous groups, order, source/coverage notices and empty/partial behavior.
- [x] Remove only the proven unreachable strategy override notice, after confirming overrides remain in their dedicated section.
- [x] Run focused tests, full frontend typecheck/tests/build, audit checks and artifact parity; exercise changing/unknown finding selection and drawers in the isolated browser preview.
- [x] Obtain independent implementation review, resolve findings and complete the hypothetical local-column-change walkthrough.
- [x] Integrate verified B main, publish and request task attachment for the focused PR, verify current-revision CI and reviews, then merge only after all gates pass.
- [x] Record evidence and advance to D.

### Out of Scope
Clinical or financial reinterpretation, new features/labels, payload or schema changes, removal of supported legacy data, new generic frameworks/dependencies, deployment, and live data/service changes.

### Review
The approved plan and read-only extraction review establish the five drug states (hidden, structured, legacy, evaluations, empty), first-non-insight copay header selection, per-row mixed shape handling, overlapping strategy categories with violations before claim rows, explicit zero-count preservation, and simultaneous material groups. Detailed scope is saved at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c-scope.md`. Worktree: `/root/worktrees/bilun-report-presentation`; branch: `refactor/hotspot-report-presentation`. B merged as [PR #102](https://github.com/Safa675/Bilun/pull/102), main `f63bb12b`, with successful main CI run `36482614267`.

Local C verification is complete against frozen source. Ten independently authored public-section compatibility cases passed on unchanged B before rewiring; after extraction, 41 focused tests and all 383 frontend tests in 65 files passed, as did final TypeScript and the production build. The 64 focused audit/source tests and isolated CLI `--check` passed. Both generated audit files are byte-identical to the B baseline, and hashes of all 1,119 tracked data/report artifacts remain unchanged. Independent source review matched 16 moved markup/helper bodies and found no local import cycles. Chromium passed 20 checks, ten per locale, on both the B baseline and C candidate; every case result is identical, with no page errors or unexpected APIs. The preview used actual patient-page content and synthetic intercepted APIs in a minimal embedded shell; it does not claim production data or full-shell visual coverage. The local-column walkthrough found `MaterialKdvReviewTable` owns its own header/cell rendering and focused test; the owning section's availability, order and other seven renderers need no change. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c`.

Delivery C publication: [PR #103](https://github.com/Safa675/Bilun/pull/103) at `b5bae476` passed hosted frontend/backend CI run `36483840115` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It was merged head-guarded as `20873ff6e66e75bb3d95b0af5206d58fe6d8d788` at 2026-09-28 21:14:27 UTC. Its merge tree matches the tested source tree. Main CI run `36484758171` passed. The app artifact attachment call is still pending; do not assume attached.

---

## Task: Deduplicate billed-at-risk per bill line across cohort and patient compliance views (#232)

### Goal
Ensure a bill line hit by $N$ compliance rules adds its `billed_try` amount once in both `build_cohort_compliance_index` / `slice_compliance_index` and `complianceBilledAtRiskSummary` while preserving all individual rule findings.

### Subtasks
- [x] Propagate `material_line_id` onto material action rows in `src/bilun/domain/billing/billing_actions.py` and allowlist it on `RecommendedActionItem` in `src/bilun/api/public_contracts.json` and `frontend/src/lib/domains/sut.ts`.
- [x] Preserve `material_line_id` on compliance index rows and deduplicate `billed_try` per `(patient_id, line_key)` in `_summarize_rows` (`src/bilun/domain/billing/cohort_compliance.py`).
- [x] Deduplicate `billed_try` per line in `complianceBilledAtRiskSummary` (`frontend/src/lib/workspaceViews.ts`) so patient-level and cohort-level billed at risk agree.
- [x] Add unit tests in `tests/unit/domain/billing/test_cohort_compliance.py` and `frontend/src/lib/workspaceViews.test.ts`.

### Out of Scope
Changing which rules fire or removing duplicate findings from the action lists.

### Review
Carried `material_line_id` onto `RecommendedActionItem` and compliance index rows, and deduplicated `billed_try` per distinct bill line in both `_summarize_rows` (`cohort_compliance.py`) and `complianceBilledAtRiskSummary` (`workspaceViews.ts`). Verified with backend pytest/ruff and frontend vitest.

---

## Task: Complete hotspot refactoring delivery B — report section extraction

### Goal
Move each existing report section into its owning module while preserving public imports, markup, behavior, and verified audit provenance, then publish and merge the independently reviewed PR after all gates pass.

### Subtasks
- [x] Confirm the approved plan and unattended authorization; use an isolated branch from merged delivery A at `63df008d` with successful main CI.
- [x] Review the 23-export inventory, helper ownership, source-resolver fixture dependency, and frontend verification requirements before implementation.
- [x] Move the 19 existing report components and genuinely shared helpers into `billing-report/`, preserving bodies and client boundaries; retain explicit named exports at the original module.
- [x] Adapt the real-extraction audit fixture to the new source graph without weakening full-output/evidence assertions.
- [x] Compare candidate audit outputs and record only explained provenance changes; verify tracked artifact hashes.
- [x] Run focused audit checks and full frontend typecheck, tests, and build; exercise the required focus/highlight/drawer/locale/partial-state flows in an isolated browser preview.
- [x] Obtain independent implementation review and resolve substantive findings; complete diff/scope checks.
- [x] Commit, check CI before push, open and attach the focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record PR/revision/verification and advance to delivery C.

### Out of Scope
Section decision cleanup (delivery C), drug engine changes, general type/schema restructuring, changes to UI or financial/clinical behavior, new dependencies, deployment, live cache/data updates, and unrelated user edits.

### Review
The existing approved plan and fresh export/helper/fixture inspection define this mechanical delivery. The user authorized unattended B–F completion and merges after tests and independent review pass. PR #101 was already merged by `Safa675` when this run resumed; its merge commit is `63df008d9ac91564247b53c83231d283754931ce`, and main CI run `36479428919` passed. The original `/opt/Bilun` checkout and its uncommitted work remain untouched. Worktree: `/root/worktrees/bilun-report-sections`; branch: `refactor/hotspot-report-sections`.

Local verification is complete at source/artifact commit `1dc0b239`: 19 component modules and shared helpers preserve all 23 facade exports and all 29 original declarations (independent AST comparisons). Baseline frontend checks passed 102 tests; final TypeScript, all 373 tests in 64 files, and production build passed. All 64 focused audit/source tests and isolated CLI `--check` passed. Only the matrix changed among 1,119 tracked artifacts: 17 added source-path occurrences across 16 of 97 rows, with every non-provenance field and all Markdown bytes unchanged. No package/lockfile changes remain.

Publication/integration: [PR #102](https://github.com/Safa675/Bilun/pull/102), head `9a539d5d`, passed hosted CI run `36481871547`. Final GitHub review fetch found no human or inline findings; Copilot reported exhausted review quota, so independent agent review provides the completed review evidence. Merged with a head-SHA guard as `f63bb12b1568f5cc02632cdeccff728a6ec9ea54` on 2026-09-28 at 20:55:32 UTC. Main CI run `36482614267` passed. Release Hold remains unchanged; no deployment occurred. The primary checkout remains on main with its original uncommitted edits preserved.

Independent structural review found no import cycles, reverse facade dependencies, or changed declarations. Playwright/system Chromium passed 14 interaction/state checks across English and Turkish, including selected-finding focus and viewport visibility, action-to-invoice highlighting, clause fetching/closing, 390px table scrolling, and exact-empty/partial-noncoverage/collapsed-legacy states. The isolated preview used the actual patient-page content and matching source hashes with intercepted synthetic APIs, `embedded=true`, a minimal provider/layout shell and fallback font; it does not claim production backend or whole-shell visual verification. Logs, scripts, hashes, parity results, and screenshots are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-b`.

---

## Task: Fatura uyumluluğu ekranını faturalama görevlisi için anlaşılır hale getir (2026-09-28)

### Goal
Mevcut eyleme dönük bulgular, Wave A inceleme gözlemleri, bilgi/izin kayıtları ve değerlendirme kapsamı hasta ekranında açıkça ayrışsın; her tekil kanıtın kimliği ve bağlantısı korunsun. Ayrıntılı kapsam ve kabul ölçütleri [UX planında](../plans/billing/2026-09-28-billing-officer-compliance-ux-plan.md).

### Subtasks
- [x] Mevcut hasta/kohort bileşenlerini, sayım kaynaklarını, sayfalama sınırını ve test kapılarını incele.
- [x] Ürün düzeni, güvenli gruplama, metin kataloğu, belirsizlik gösterimi ve doğrulama için ayrıntılı plan yaz.
- [x] Planı mevcut veri sözleşmeleri ve testlerle bağımsız olarak karşılaştır; yanlış toplulaştırma ve kayıp deep link risklerini plana işle.
- [x] Ürün planı gözden geçirilip onaylandıktan sonra uygulamaya başla.
- [x] Hasta inceleme sunum modeli, erişilebilir grup/ayrıntı etkileşimi ve seçili tekil kayıt bağlantısını uygula.
- [x] Yapısal/Wave A kapsamını, advisory bölümünü ve iki dilli açıklamaları güncelle; kohort ortak bileşen etkisini doğrula.
- [x] Odaklı davranış testleri, dar ekran yan menü kontrolü, masaüstü/mobil tarayıcı kontrolü ve tüm frontend CI kapılarını tamamla.
- [x] Son diff'i ve sayısal/finansal değişmezleri gözden geçir; incelemeye hazır yeni PR aç.

### Out of Scope
Kural motoru, backend/API/cache, finansal toplamlar, kohortta sayfalar arası gruplama, canlı dağıtım ve mevzuatın hukuki teyidi.

### Review
Plan, mevcut `ComplianceViewSection`, `WaveAEvidenceSection`, `CohortWaveAEvidenceSection`, veri tipleri ve frontend testleriyle iki bağımsız salt-okunur incelemede karşılaştırıldı. Hasta önizlemesi/kohort sayfalaması nedeniyle yalnızca yüklenmiş satırlara ait gruplama sayıları kullanıldı; tekil `evidence_id` bağlantıları korundu. Kullanıcı planı onayladı. Hasta 0043/0001 üzerinde masaüstü, 390 px mobil, klavye, sayfalama ve önizleme dışındaki seçili kayıt tarayıcıda doğrulandı; mobil yan menü tercihi masaüstünde korunuyor. Tam frontend doğrulaması: 64 Vitest dosyasında 373 test, TypeScript ve üretim derlemesi geçti. Backend/API/cache/kural kararları ve finansal hesaplar değiştirilmedi. İncelemeye hazır [PR #100](https://github.com/Safa675/Bilun/pull/100) açıldı; ilk [GitHub CI koşusunda](https://github.com/Safa675/Bilun/actions/runs/36469974065) backend ve frontend başarılı.

---

## Task: Implement hotspot refactoring delivery A and open a draft PR

### Goal
Make the surfacing audit follow supported patient component imports and named re-exports while preserving source evidence, then publish the verified first implementation delivery as a draft PR.

### Subtasks
- [x] Confirm the user-approved hotspot plan and create an isolated worktree on current main `46ae9fdf`, including the merged billing-officer UX work.
- [x] Capture the baseline audit output, focused tests, generated-artifact hashes, and relevant current source contracts.
- [x] Implement the bounded frontend component-source adapter and integrate it without changing application behavior or the later-phase map reader.
- [x] Add meaningful moved-component and missing/false-evidence regressions; preserve existing audit checks.
- [x] Independently review the implementation and resolve findings.
- [x] Run the applicable full backend gates, audit parity checks, and artifact-drift inspection; record results.
- [x] Check branch CI, commit and push the reviewed changes, open and attach a draft PR, and report its CI status.

### Out of Scope
Deliveries B–F, component moves, drug-rule changes, a general TS parser, new dependencies, production data/cache changes, merge, and deployment.

### Review
Implementation authorized by the user after review of `plans/refactor/2026-09-28-bilun-hotspot-refactor-plan.md`. Delivery A is published as [draft PR #101](https://github.com/Safa675/Bilun/pull/101), attached to this task; later deliveries remain tracked in the plan. Work is isolated from the original checkout and its uncommitted planning documents. Independent review's demonstrated false-evidence cases are fixed. Full backend verification passed **4,075 tests, 8 warnings, in 734.61s**, including all 38 new regression cases and the existing committed-output parity check. Reviewed regeneration adds evidence paths to 16 rows, preserving every other serialized field and Markdown bytes. Full Ruff, isolated direct CLI checks, compiler check (**134 byte-identical rule/manifest artifacts**), and manifest parity (**23 manifests, zero issues**) pass. The final 1,091-file artifact hash comparison found only the reviewed matrix change. Base CI was green before the first push; the branch had no failed runs. Hosted PR CI started at publication; current status is available on the PR. No merge or deployment was performed.

---

## Task: Reduce full-suite runtime without reducing coverage

### Goal
Publish a reviewed implementation PR that preserves every backend/frontend test and generated SUT artifact while making full-suite local runs faster and measuring the Polars thread setting on GitHub Actions before selecting its final CI value.

### Subtasks
- [x] Independently review and confirm this plan against the measured three-file prototype and the existing CI gates before implementation.
- [x] Apply safe C YAML loading with the Python SafeLoader fallback in the rule-source and deferral-table loaders, preserving fresh parsed objects and safe-tag behavior.
- [x] Resolve the unchanged all-rule source union once in a module-scoped immutable fixture, preserving all manifest cases and assertion expressions.
- [x] Document `POLARS_MAX_THREADS=1 python -m pytest -q --durations=20` as the standard full-suite local command and add CI duration reporting, leaving the first PR revision's CI thread setting unchanged; add no wrapper, dependency, or pytest bootstrap.
- [x] Review the final source/configuration diff independently, including loader semantics, fixture lifetime, command argument handling, and CI trial attribution.
- [x] Run the complete backend suite from an empty worktree-local cache and compare all 2,774 test identities and statuses with the investigation baseline; run Ruff, compiler `--check`, and manifest parity, requiring 134 byte-identical generated artifacts and no tracked data drift.
- [x] Run all frontend CI gates on the final branch: TypeScript, the complete 320-test Vitest suite, and production build, coordinating heavy local execution with the backend run.
- [x] Record reproducible local timing, exact validation evidence, independent review, and any limitations in the review section; inspect the final diff and check existing CI before each push.
- [x] Commit, push the new branch, and open and attach a draft implementation PR after independent diff review and the completed exact-prototype gates; overlap hosted CI with final-branch local confirmation, keeping the PR draft until final local gates and repeated CI validation pass.
- [x] After the uncapped PR revision is green, add the step-scoped CI thread trial as an environment-only workflow revision; repeat uncapped/capped GitHub Actions attempts with the same source changes, compare full-test and compiler steps, retain the measured CI choice, and record the final result without projecting local speedup onto CI.

### Out of Scope
Merging or deploying; touching the live database/cache; removing, skipping, narrowing, or weakening tests; xdist; broad resolver, artifact-writer, or cleanup refactors; changing production thread settings; changing generated rules/manifests or clinical/payment semantics.

### Review
Plan reviewed and confirmed before implementation. Independent review found no correctness issues: the three backend files have AST parity with the measured prototype, parsing retains the safe fallback and fresh objects, and manifest assertions and parameters are unchanged. [PR #95](https://github.com/Safa675/Bilun/pull/95) contains the implementation on `perf/full-suite-runtime`; no merge or deployment is part of this task.

Local gates passed: **2,774 backend tests, zero skips/errors/failures, 9 warnings, 569.13s pytest / 573.18s external**, with exactly the same ordered identities/statuses as the original baseline; Ruff; compiler check **134 artifacts byte-identical** (47.54s); manifest parity **23 manifests, zero issues**; frontend TypeScript, **55 Vitest files / 320 tests**, and production build. The backend began with an absent worktree-local cache, source/configuration hashes stayed stable throughout validation, and the worktree was clean afterward with no generated-data drift. The original local baseline was 1,024.55s; host activity varies, so local percentages are not CI predictions.

Hosted comparison retained identical installed dependencies, Python 3.13.15, runner image, and cache key. Two successful attempts per configuration ran all 2,774 backend tests and reproduced all 134 compiler artifacts:

| Configuration | Python test step (seconds) | Backend job (seconds) | Compiler step (seconds) |
|---|---|---|---|
| Original main, `7a6e854f` | 329 / 336 | 404 / 415 | 34 / 38 |
| Parser/fixture changes, default threads, `782fe49f` | 231 / 167 | 289 / 225 | 19 / 11 |
| Same source, CI one-thread trial, `61e63746` | 214 / 136 | 270 / 185 | 16 / 10 |

Final decision: retain **default CI threads** and the measured **one-thread local command**. The CI trial's ranges overlap substantially with default-thread runs, and unchanged compiler/startup paths also varied across runner regions; these samples do not establish an isolated CI thread-budget benefit. The parser/fixture improvement is retained, and CI now reports its slowest 20 phases. All existing backend/frontend/compiler/build gates remain enabled. Evidence: [baseline attempts](https://github.com/Safa675/Bilun/actions/runs/36152110893), [default-thread implementation attempts](https://github.com/Safa675/Bilun/actions/runs/36260747322), [one-thread trial attempts](https://github.com/Safa675/Bilun/actions/runs/36261536404). Raw logs, source hashes, case parity, and independent reviews are retained in `/root/artifacts/bilun-test-implementation-2026-09-26`.

---

## Task: Complete the deferred PR #89 Wave A groups in one verified release (2026-09-27)

### Goal
Cover all 25 deferred detector/engine groups (18 focused and seven broad) through canonical, single-evaluation patient/cohort projections, with each authored outcome honestly classified. Ship in reviewable checkpoints on one integration branch, then activate once after a validated cache rebuild and verify the live patient and cohort experience. This is group coverage, not a claim that every possible authored rule ID fires in live data. PR #96's post-merge CI and Deploy completed successfully before this task began.

This is an explicit user-approved expansion of the original strict Wave A filter: mixed monetary outputs use existing financial sections and informational outputs use review-only presentation. Do not label those rows unpriced violations merely because their engines appeared on the deferred candidate list.

### Locked decisions from the grilling interview
- Keep the ten excluded synthetic `kind:<callable>` identities outside this release and report them honestly.
- Compliance contains only eligible, unpriced violations; positive actions are evaluations, review-only outcomes remain outside violation counts, and missing inputs remain unavailable rather than a clean pass.
- Preserve detector decision semantics; add status/skip metadata as needed. A wrong detector is held for a separate focused correction, and the combined release waits for that blocker.
- Give every distinct finding and per-line evaluation a stable source/line identity across patient, cache, cohort, API, and UI. Never collapse multiple rows into one claim identity.
- Show financial-only outcomes in existing patient and cohort financial/recovery sections with separately labeled billed/risk/uplift values and verified source/basis. If provenance or amount is unverified, show an honest review/unavailable state rather than a sourced or confirmed number. Keep existing savings/recovery totals byte/value-equivalent and do not double count or invent zero amounts.
- Show actual findings plus compact evaluated/unavailable summaries, not the full static ID catalog. Verify all cached rows and representative live triggers; use synthetic per-rule tests for rare rules with no live positive case.
- Validate the rebuilt cache and cohort before one user-visible activation; block unexplained financial drift, identity collisions, or finding-count changes; provide a tested rollback to the previous version/cache.

### Release checkpoint, 2026-09-27

The exact-main receipt preflight exposed a separate historical identity: the live PR98 serving cache has build `b1fdcb54` from code `b08c4797`, while the independently rebuilt same-input corrected baseline has build `8065e1d8` from PR98 code `4af38b28`. The issuer currently requires one baseline build ID and identical cache bytes for both, so it cannot sign honestly. A focused follow-up must preserve both identities, verify type-sensitive equality of every legacy content table between the protected serving cache and rebuilt baseline, tie that bridge to the observed old cache, and recheck both caches before receipt issuance. A changed row, missing row, malformed build, or drifted cache must block signing. After merging the correction, rebuild all candidate artifacts from its new exact `main` SHA before activation.

The follow-up now also rejects uncheckpointed DuckDB WAL sidecars at each cache hash, after independent review showed that a read-only query could otherwise observe committed rows absent from the pinned main file SHA. Crash-WAL and broken-symlink regression tests cover the trust boundary. Keep Wave A held until this correction is reviewed, merged, and re-attested from the exact new `main` SHA.

The final route/rollback review found three trust-boundary gaps and one product gap, now addressed in the integration branch. The release transaction checks both the route loaded by Caddy and the Caddyfile installed for restart; recovery reinstalls the barrier if old-route verification fails. Exact GitHub CI verification also requires the candidate SHA to remain current `main`. A protected old-pair recovery adapter seals the PR98 snapshot, stages independent backend/frontend/cache copies, and records a new PID-bound tuple after restart. Mixed cohorts now retain available evidence rows and show selected/available/unavailable coverage rather than suppressing the whole cohort.

Premerge proof at `f4daa876` includes a successful 50-patient/94-bill private candidate-pair Caddy rehearsal after rebuilding the frontend with its build-time API rewrite to port 8002. The new protected old-pair manifest and staged copy passed byte and WAL checks; its real launcher passed an isolated network-namespace rehearsal with all 50 patient and 94 bill legacy API payloads plus frontend assets matching the PR98 equivalence report. These checks are **nonactivating**. The currently pushed `5980538b` PR #97 head has green backend/frontend hosted CI; the new local integration changes still require their own exact-head CI, final merge SHA build, signed receipt, supervised rollback/public barrier verification, and live sign-off. Wave A remains inactive.

PR #98's EK-3B correction is merged and serving, with a protected old runtime/cache/environment snapshot. Draft PR #97 contains the 25-group patient, bill, cohort, API, and UI integration. Production Wave A remains inactive. A traced candidate build for the earlier `a7754c1c` head passed all-cache structural and same-input legacy/financial parity on 50 patients and 94 bills, and a real old/candidate private Caddy rehearsal restored the old pair. That artifact is **not** a release candidate for later code heads.

The release implementation now has a signed startup receipt, exact main-CI issuer, private candidate launcher, actual loaded-Caddy route adapter, old/barrier/candidate route preparation with retained old static assets, a sealed manifest producer, concrete public/private HTTP probes, and a journaled activation/recovery CLI. These are code checkpoints, not activation evidence. The old serving backend still lacks an in-memory code SHA, so the release uses protected byte/behavioral equivalence and keeps that limitation explicit. Final code must still be merged, rebuilt from the exact main SHA, privately rehearsed again, signed only after all independent gates, and switched through the public barrier with rollback verified.

The previous PR #97 head `29e21241` had a red backend CI run because the rule-surfacing audit still looked for the old capability string. The audit now requires the signed startup check and draft cache; its 26 tests pass, including removal-of-signature rejection. A local full suite at the previous head produced 3,988 passes and exactly those 11 audit failures in 889 seconds. After the fix, 224 focused deploy/API/audit tests, Ruff, and manifest parity passed; generated rules and the next hosted CI run remain pending. Never treat the draft PR, an earlier candidate, or a prepared route manifest as authorization to change the public route.

### Subtasks
- [ ] Reconcile all 25 groups: the historical PR #89 baseline has 516 hidden static inventory identities (20 focused entries including a synthetic radiation grouping, plus 496 broad authored IDs) and 526 possible runtime IDs (30 focused plus 496 broad). After source-backed corrections, track 32 focused identities across 18 groups, of which 29 can currently emit rows: #9 and #22 are unavailable until missing dates are ingested, the unsupported hyperthermia grouping cannot emit, and two distinct radiation course candidates were added. Keep the 496 broad authored identities separate from claims of live evaluability. Check emitted IDs, source rows, `billable`/review semantics, input availability, stable identity, monetary paths, and the ten explicit exclusions.
- [ ] Capture baseline code/data identities, financial totals, current patient/cohort payloads, and active cache build ID without changing production state; record representative and negative cases.
- [x] Write detailed focused, broad, and financial/release architecture maps in `plans/billing/`; independently review and approve this task plan and those maps before production code changes.
- [x] Inventory the four flat-only monetary focused outputs from their detector results and patient-report totals before implementing their display; identify exact amount basis, source strength, and whether they currently participate in headline calculations.
- [ ] Extend the canonical finding/evaluation contract with per-rule outcome classification, stable distinct finding/evaluation identities, honest missing-input/skip status, source evidence, review-only status, and a separate typed financial projection while preserving detector decisions.
- [ ] Integrate the 18 focused groups into one-pass evaluation, including explicit classification of the four money-bearing groups and source-derived identity for multirow detectors; add group-level regressions.
- [x] Correct the duplicate-exam ten-day false negative in a separately reviewed detector change, with A/day1 and two B/day2-3 line regressions and unchanged existing cases.
- [x] Resolve the admission 60-day detector's use of service-range end as a purported submission date: official handbook and current SUT do not support the old inference; legacy false emission removed and a per-claim unavailable evaluation added for the missing period-closure date (`5af8985a`; 35 targeted tests/Ruff and independent review passed).
- [x] Correct Tablo 15 #22's mismatch predicate separately: the official handbook concerns an outpatient exam date versus acceptance date, which is not ingested; false inpatient/procedure-date emissions are removed and per-claim unavailable status records the missing input (`632fc517`; 57 targeted tests/Ruff and independent review passed).
- [x] Correct the donor detector's unreachable category branch from official El Kitabı §4.2/Table 15 #24: same-claim donor-preparation evidence now flags distinct exam lines as review-only, with no claim of confirmed MEDULA donor identity (`e22f0261`; 34 direct/provenance tests and Ruff passed).
- [x] Correct the dental GA zero/credit-only anesthesia false positive in a separately reviewed detector change, without inferring a missing uplift.
- [x] Correct yatak zero/credit-only bed false positives and non-ICU evidence attribution separately, preserving the existing bed-day financial calculation (commit `9689247f`; 22 direct tests and Ruff passed; independent review approved).
- [x] Correct radiation predicates against current EK-2B explanatory cells: design, planning, dose, device, application, and session limits now use source-backed review evidence, grouped multi-day quantities are not treated as confirmed same-day excess, and billed amount stays separate from null unverified risk. Distinct 800370 and 800430 course identities were added; unsupported hyperthermia grouping is unavailable. Detector/direct integration passed 49 tests and Ruff with independent source/diff review (`e0ca7875`). Full inventory/report/cache parity remains a release gate.
- [x] Correct the dental precious-metal matcher in a separate Q9 detector checkpoint: reject term-local negations such as `altın içermeyen`, `platin içermeyen`, and `altınsız`, preserve independently affirmative metal/product matches and first-winner/raw ordering, and verify real material-line regressions against the official July/August 2026 §2.4.1(1) source evidence before promotion (`2ee13b08`; 102 targeted tests/Ruff and independent review passed). Free-text ambiguity remains a classification hold.
- [x] Correct EK-3B-1/2 false findings in a separate, independently reviewed checkpoint: separate lexical candidates from matched/not-matched/unavailable annex applicability; honor sterile-glove, inpatient syringe and blood-strip, dressing oxygen, and viscosupplementation exceptions; preserve ordinary glove, urine-strip, and inflow-catheter cases. Use actual owned claim/header facts, clear stale derived flags, expose nullable regulatory status without changing package CSV flags, and require resolved eligibility before any material uplift. Prove dictionary/typed validator, pricing DTO, precheck, uplift, source-line identity, and full patient/bill/cohort financial deltas. If legacy money changes, merge this correction separately and recapture the same-input Wave A baseline before release; never waive financial parity.
- [x] Keep the EK-3B reference catalog source-only: mark entries not evaluated for a patient, preserve conditional exceptions, remove the unsupported effective-date display, and avoid blanket non-reimbursable labels. Retain its collection keys for compatibility and test the rendered explanation.
- [ ] Classify transplant carveouts, missing monetary source/basis, and unverified dental uplift as review/unavailable with null confirmed amount, preserving existing patient/cohort totals.
- [ ] For line-owned financial reviews, show an observed billed charge only when it is reconciled to the exact procedure claim line, with a distinct source/basis field; keep unverified risk or recoverable uplift null and outside all totals. Independently match the observed charge against pinned procedure Parquet before activation. Dental claim-level expected fee remains unavailable as net recovery without a verified basis.
- [ ] Freeze and independently review the exact 496-ID broad classification matrix: source authority/version, authored action meaning, predicate sufficiency, claim-field provenance, proof or withholding gate, and stable reason for every ID, including all 31 `ai_generated_pending_review` rows; retain raw parity and fail closed when an authored condition/action/source digest changes.
- [ ] Integrate the seven broad engines with rule-level authored-action classification and status metadata; account for every authored ID as eligible finding, positive, review, monetary, or unavailable without blanket conversion to violations.
- [ ] Carry canonical nonfinancial, review-only, and financial projections through patient report, cache, cohort index, API, and old-cache fallback; prove identity parity and bounded honest status summaries without new aggregate money.
- [ ] Persist each bill's exhaustive v2 evidence in a separate build-scoped table keyed by `patient_id::claim_id`; keep default bill JSON bounded, validate exact bill/detail key sets and claim ownership, and reconcile bill previews/coverage against its own detail. Do not equate a bill slice with patient evidence filtered by claim when cross-claim context can differ.
- [ ] Reconcile the existing `validate_claim()` public `violations`/validity contract with typed positive/review outcomes; migrate its API, chatbot, frontend validator, and tests together so public counts no longer call permitted or informational actions violations, retaining a documented compatibility path.
- [ ] Render eligible findings and review-only statuses in the existing patient/cohort Compliance UI and sourced monetary outcomes in the existing patient/cohort financial sections; preserve links, pagination, and old-cache honesty.
- [ ] Update surfacing inventory and regression gates so the 25 groups are classified correctly, visible where eligible, and not double counted; retain the ten excluded synthetic identities.
- [ ] Implement a single-activation release gate according to `plans/billing/2026-09-27-wavea-release-gate.md`: listener-aware read-only discovery, protected and privately rehearsed **actually serving** old runtime/cache/effective env/Caddy tuple, and independently reviewed legacy-equivalence attestation without a fabricated old code SHA. Current P0 correctly blocks because old health lacks code SHA, frontend `.env` drifted after its listener started, and protected snapshots are missing.
- [ ] Build an immutable candidate backend/cache/frontend on private :8002/:3099 and verify it through a private :3100 route: stable source-byte manifest, all patient/bill/cohort payloads and financial/action parity, exact CI/code/frontend/build identity, old/new client and asset behavior, plus resource/duration evidence. Never alter :8001/:3000 or the public route during preparation.
- [ ] Replace the current frontend-first deploy with one Caddy maintenance barrier and one public route switch to the verified candidate pair, under a shared lock and fsynced recoverable journal. Recheck SHA/artifact/input identity immediately before switching; rehearse rollback to the old :8001/:3000 routes and restart from protected artifacts on disposable fixtures. Split the 25-minute workflow if measured preparation/recovery cannot fit without weakening same-SHA/stale-head guarantees.
- [ ] Run focused domain, API/cache, frontend, financial, and release-gate tests; then run full backend/frontend CI-equivalent checks, generated-artifact checks, and a no-drift financial snapshot comparison.
- [ ] Independently review the final source, classification, UI, and release diff; resolve all correctness findings and re-run affected checks.
- [ ] Check branch CI before pushes; publish reviewable checkpoint commits/PR, obtain final hosted CI and review feedback, then merge for one production activation.
- [ ] Verify the merged production deploy, active cache build, every cached patient/cohort payload, representative live findings and statuses, financial-path identity/amount labels, unchanged totals, and rollback readiness; record exact evidence and remaining limits.

### Out of Scope
The ten synthetic-identity rows previously excluded from Wave A; new clinical/regulatory rule decisions; new claim-data ingestion solely to make dormant authored IDs fire; changing existing savings/recovery totals; treating positive or review-only outcomes as compliance violations; activating partial checkpoints in production.

### Review
Plan independently reviewed and approved for staged implementation by three agents after correction of classification, identity-count, detector-correctness, retained-client, and deployment-timeout gaps. Product integration and production payload baseline capture remain pending. Latest main is `bbf9acaf` (merged PR #96); its [post-merge CI](https://github.com/Safa675/Bilun/actions/runs/36316401829) and [Deploy](https://github.com/Safa675/Bilun/actions/runs/36316669982) passed. The original read-only audit found 18 focused groups (20 static inventory identities, expanding to 30 possible emitted runtime IDs because radiation had 11 IDs) and seven broad engines (496 authored IDs) hidden. Subsequent correctness fixes changed the current focused tracked/emittable inventory as recorded above; these IDs are possibilities, not guaranteed live findings. Financial, positive, review, missing-input, and stable-identity classification must precede activation. A read-only synthetic baseline at `bbf9acaf` covers 50 patients, 94 bills, and 636 legacy validator rows; its 5.25 MB JSON is saved outside the worktree at `/root/artifacts/bilun-wavea-2026-09-27/baseline-synthetic.json` (SHA-256 `12cfec6940a2beae19de08881e56c88bd018bc166a24ee9e56f536317ff4f5b3`). Patient report baseline sums: SGK uplift/recoverable ₺348,340.41, audit exposure ₺673,902.64, action count 452; bill report financial sums match, with 563 bill actions. These are synthetic comparison fixtures, not production values. A read-only production `/health` response on 2026-09-27 reported `status=ok`, `database_reachable=true`, `cache_ready=true`, active build `b1fdcb54-0abb-426a-94fb-f00d006144a7`, and gazette version `2026-07-07`. This establishes only the health/build baseline; authenticated patient/cohort payloads and source-code identity still need capture before release. A read-only unauthenticated request to `/api/compliance-index?limit=1` returned HTTP 401, so the health response is not a substitute for private payload verification.

Checkpoint commits on the integration branch: `c19293ff` adds seven real line IDs and fixes duplicate-exam matching (independent review, 46 focused tests/Ruff); `f45f7f54` adds stable per-line evaluation IDs through patient/cohort and fixes mixed old/new dedup (independent review, 82 targeted tests/Ruff); `f64ee242` records the reviewed plan and four-group financial inventory; `845f6850` freezes all 496 broad corpus IDs with conservative candidate classifications (independent review, 15 tests/Ruff); `d46dc53b` verifies canonical finding IDs and fails on conflicts (independent review, 25 cohort/API tests/Ruff); `f553edb0` fixes zero/credit-only dental anesthesia false positives (independent review, 18 direct tests/Ruff). All commits are local; the 25-group product, public API/UI, full release gate, full CI, merge and live verification remain outstanding.

Further reviewed local checkpoints: `9689247f` corrects ICU-overlap charge/evidence attribution; `8acce3ab` adds 42-ID information-only payment traceability metadata; `5af8985a` and `632fc517` remove false #9/#22 date verdicts and add unavailable-status helpers; `e22f0261` corrects donor same-claim evidence; `e0ca7875` aligns radiation review candidates with current EK-2B and leaves excess risk null. Read-only release-host findings are recorded in `reports/rule-engine-surfacing/2026-09-27-wavea-host-preflight.md`. These remain local checkpoints, with no public activation.

`0151aeec` adds an independently reviewed, still unintegrated focused adapter for all 18 groups: 32 tracked identities, 29 presently emittable, source-owned line IDs, quarantined stale #9/#22/hyperthermia rows, explicit missing/unavailable statuses, and no confirmed financial amount. Final focused and existing El Kitabı tests passed 28 cases with Ruff. The public report/cache/UI remain unchanged until the later integration checkpoint.

`3b801e9e` subsequently integrated the 18 focused groups into the canonical patient/bill report in one detector pass. The 50-patient/94-bill same-input synthetic comparison against the `bbf9acaf` baseline found **0/50 patient and 0/94 bill differences in legacy report fields**, with unchanged ₺348,340.41 SGK/recoverable sums, ₺673,902.64 audit sum, and 452 patient/563 bill action counts. The separate focused-evidence checkpoint now adds source-linked review and null-amount financial rows, exhaustive 32-ID status detail in a build-scoped patient table, exact cohort counters and sparse paginated review/financial rows, and draft-gated API/old-cache fallback. Its cache trial wrote 50 patient detail rows and one index alongside the 50 reports/94 bills in 122.48 seconds wall time, using about 1.05 GiB peak RSS. The 50-patient detail has 52 review rows and no financial trigger; an additional real-detector fixture verifies both review and financial rows through patient/bill/cache/cohort APIs. Rebuilding the sparse index from those detail blobs produces 52 rows in a 285 KB JSON singleton. Current default patient JSON averages 83 KB; trimming the 32 focused statuses from that default is the next bounded-payload checkpoint. The draft cohort fallback measured 171 ms median across the 50 reports versus 21 ms for a stored-index slice; it stays fail closed on missing/corrupt index or rows. The focused evidence/API/cache suites passed **118 tests**, changed-file Ruff and diff check; a production app integration test also verified unauthenticated 401 and authenticated 200 for all new evidence endpoints. This is an independently reviewed draft-only checkpoint; the seven broad groups, UI, complete-25 attestation, full CI, and release gate remain pending.

`3daf489b` wires all 25 groups into report/cache/API as draft-only evidence, including 50 patient and 94 independently scoped bill details. The matched-input build used four-row bill-detail writes and completed in 126.28 seconds with 1,448,152 KB peak RSS, versus 131.46 seconds/1,654,232 KB before streaming and 122.48 seconds/1,097,784 KB for the focused-only build. Default JSON averaged 65.3 KB per patient and 46.0 KB per bill. Legacy report fields differed in 0/50 patients and 0/94 bills; SGK ₺348,340.41, audit ₺673,902.64, and 477/638 current patient/bill actions were unchanged. The 528-rule, 25-group evidence is still unavailable publicly until independent source/financial/rollback attestation and one activation pass.

---

## Task: Correct EK-3B annex applicability before Wave A activation

### Goal
Prevent EK-3B-1/2 lexical matches from becoming unsupported billing violations, reimbursement decisions, or material uplift; preserve exact source-line ownership and record any resulting financial baseline change separately.

### Subtasks
- [x] Pin and compare official SGK July/August 2026 annex workbooks, extract the exception rows, inspect current SGK notices, and document the limit of historical service-date applicability.
- [x] Audit every existing consumer of EK-3B match flags and money, including legacy validator, material pricing, patient/bill precheck, uplift, and cohort totals; record the before-change baseline boundary.
- [x] Define an immutable tri-state annex assessment (`matched`, `not_matched`, `unavailable`) with candidate row, match kind, and stable reason; keep lexical matching separate and expose only confirmed candidates through old boolean helpers.
- [x] Apply the source exceptions and use/setting qualifiers to both dictionary and typed paths: surgical sterile gloves; inpatient disposable syringes; inpatient blood-sugar strips without broadening that condition to urine strips; dressing-only oxygen; conditional viscosupplementation; preserve ordinary gloves and exact inflow-catheter matches.
- [x] Recompute nullable regulatory flags from actual claim/header facts, clear stale derived flags, and keep the independent package CSV `is_bundled` fact unchanged. Legacy material pricing and API DTOs must distinguish unknown from reimbursable or excluded.
- [x] Keep unresolved or fuzzy-only annex matches out of material uplift; require affirmative resolved eligibility, with regression cases for source-line ownership, duplicate names, code-resolved candidates, stale flags, and missing care/clinical-use facts.
- [x] Run focused suites, full financial patient/bill/cohort comparison, Ruff and generated-artifact checks; independently review the correction and publish it as an isolated checkpoint/PR if existing decisions or money change.
- [ ] Rebuild and pin a new same-input Wave A baseline after the correction is merged, then keep the combined 25-group activation blocked until full-cache parity and rollback gates pass.

PR #98 merged at `4af38b28` after green hosted backend/frontend CI; the synthetic patient/bill/cohort financial trees remained unchanged. Its production deployment and post-merge baseline capture remain separate Wave A release gates.

### Out of Scope
Changing package CSV flags, inventing clinical use or care setting, promoting unknown materials to payable, changing unrelated monetary rules, or treating the 2026 annex file name alone as proof of every earlier service interval.

### Review
The interface and consumer boundary were reviewed before edits against the pinned annex rows and the read-only monetary impact audit. The official consolidated announcement and current GSS listing were checked on 2026-09-27; historical service-date applicability remains a source-manifest gate.

---

## Task: Fix PR #94 CI after repricing removal

### Goal
Make PR #94's backend CI pass by reconciling the committed registry-coverage artifact and cohort-tier test with the retired repricing rule, without changing service-date pricing or unrelated coverage data.

### Subtasks
- [x] Remove only the obsolete `gazette_repricing` row from `sut_registry_coverage.parquet` and verify every remaining row equals the current registry-derived summary.
- [x] Update the cohort-tier test to the current 8/16/26 split and assert former demo patient 0011 is no longer Tier A.
- [x] Run the exact backend CI gates on the final branch: Ruff, full Python test suite, rule compiler artifact check, and manifest parity audit; inspect binary/test diff.
- [x] Commit and push the fix to PR #94, then confirm the new CI result.

### Out of Scope
Restoring the repricing algorithm, broad synthetic regeneration, other SUT coverage changes, PR merge, deployment, or production cache rebuild.

### Review
Local verification passed on the narrow fix: Ruff; full Python suite **2774 passed, 9 warnings**; rule compiler `--check` found **134 byte-identical artifacts**; manifest parity scanned **23 manifests with 0 issues**; targeted registry and cohort-tier suites passed. The parquet change contains only the obsolete registry row removal, with all 46 survivor rows/schema/order unchanged. Full pytest and an interrupted duplicate compiler check temporarily rewrote unrelated drug manifests; their generated changes were cleaned before commit. Fix commit `10d04811` was pushed to PR #94; GitHub CI run `36150469229` completed successfully for backend and frontend.

---

## Task: Publish gazette repricing removal PR

### Goal
Put the completed and verified removal on a fresh branch from current `origin/main`, then open a reviewable PR containing only that removal.

### Subtasks
- [x] Confirm the old PR #92 branch is merged and choose a fresh branch from current `origin/main`.
- [x] Audit and commit the removal patch without unrelated or sensitive additions.
- [x] Transfer the commit to a fresh `origin/main` branch; resolve any conflicts and verify the resulting diff and focused checks.
- [x] Push the branch, open and attach a PR, and confirm its commit/file scope.

### Out of Scope
Merging the PR, deploying, rebuilding production caches, or adding a replacement pricing rule.

### Review
Opened PR #94 on `fix/remove-unsupported-gazette-repricing` against current `main`; the first PR commit contains only the 70-file repricing-removal patch and no older PR #92 commits. Fresh-branch verification: 104 focused backend tests passed (one existing pytest deprecation warning), 134 remaining rule/manifest artifacts were byte-identical, surfacing audit check and Ruff passed, and the worktree/diff were clean before publication. No deployment, production cache rebuild, or merge was performed.

---

## Task: Remove unsupported post-service gazette repricing rule

### Goal
Remove the 30-day price-staleness opportunity from Bilun's runtime and product surfaces so no later SUT tariff increase is shown as recoverable for an earlier procedure.

### Subtasks
- [x] Inventory all runtime, API, frontend, registry, compiler, synthetic, test, and generated references; lock the deletion boundary.
- [x] Remove the detector, billing adapter, runtime registration, rule metadata, opportunity fields and totals, and API projections without changing service-date price lookups.
- [x] Remove patient/cohort UI sections, deep links, translations, frontend types and tests for the opportunity.
- [x] Remove dedicated fixtures, synthetic scenario generation, demos, tests, and generated rule/audit artifacts that specifically advertise repricing.
- [x] Update current architecture/coverage documentation so it no longer claims this rule is implemented; leave historical plans/reports identifiable as historical when appropriate.
- [x] Verify no live repricing references remain, run focused backend/frontend checks and relevant generated-artifact checks, and record results.

### Out of Scope
Changing valid temporal EK-2/B or EK-2/C lookups, adding a replacement pricing detector, editing unrelated SUT rules, regenerating all synthetic cohort data without a dependency need, deployment, or production cache rebuild. PR publication is tracked separately above.

### Review
Removed the post-service repricing evaluator, billing adapter, API/report/cohort fields, registry/compiler entry, patient and optimizer UI, translations, synthetic demo, and current documentation claims. Historical EK-2/B and EK-2/C service-date price lookups remain. Removed the dedicated rule source/compiled JSON/empty manifest/golden and regenerated the rule-surfacing audit matrix and report. The checked-in synthetic cohort was already out of sync with a pristine-HEAD regeneration, so only retired scenario tags, one demo workbook column, and one obsolete metadata row were mechanically scrubbed from its binary artifacts; all other logical records/cells were verified unchanged.

Verification: backend focused suites 139 passed; synthetic billing 22 passed; frontend focused Vitest 63 passed and `tsc --noEmit` passed; temporal pricing 2 passed; synthetic validator and Tier A assertion passed; rule compiler `--check`, surfacing inventory `--check`, changed-file Ruff, compileall, and `git diff --check` passed. A broader `tests/unit` run reached 231 passed with no failures, then was interrupted because it was still at 7% after two minutes. No deployment or production cache rebuild was performed.

---

## Task: Phase 5 Checkpoint 4 — loop-complete closure metadata

### Goal
Record truthful loop-complete metadata for the verified Checkpoint 4 without modifying production code, tests, generated audit artifacts, plans, or configuration.

### Subtasks
- [x] Replace pending-commit closure status/phase/status values with truthful `loop_complete` wording.
- [x] Record the exact final acceptance results, artifact-hash reconciliation, added-line secret/patient-data scan, and temporary symlink check.
- [x] Preserve empty blockers, explicit exclusions/deferred Wave B/C/D scope, and the no-push/no-merge/no-deploy/no-cache-rebuild boundary.
- [x] Run JSON parsing and `git diff --check` after the metadata-only update.

### Out of Scope
Production code, tests, generated audit artifacts, plans, configuration, detector medical semantics, new detector migrations, projection rule-ID allowlists, registry dispatch changes, pricing or financial behavior, production cache rebuilds, commits, pushes, PRs, merges, deployments, and deferred Wave B/C/D or broad prose-family candidates.

### Review
Loop is complete and verified. Final acceptance evidence is focused inventory `17 passed in 2.53s`; authoritative combined backend `272 passed, 1 warning in 32.46s`; frontend `4 passed files, 29 passed tests`; `npx tsc --noEmit` exit 0; generator `--check` exit 0; compileall exit 0; `git diff --check` exit 0; artifact hash reconciliation pass; added-line secret/patient-data scan pass; and temporary frontend/node_modules symlink absent. Blockers are empty. Deferred Wave B/C/D and broad prose-family candidates remain outside scope and require separately approved future scope. No push, PR, merge, deploy, or production cache rebuild occurred; no commit was created. This loop is ready for the acceptance commit, but no further action is required in this loop.

---

## Task: Phase 5 Checkpoint 2 — generic cohort/cache/API projection

### Goal
Project all five supported canonical nonfinancial `RuleFinding` rules through existing patient/bill cache payloads, the generic cohort compliance index, and existing API routes with stable identity, honest evaluation availability, and unchanged financial totals.

### Subtasks
- [x] RED→GREEN: add the smallest cohort regression proving a selected Wave A canonical finding was rejected, then remove the K21/K26 product gate with generic fail-closed serialized-contract validation.
- [x] Remove the rule-ID allowlist and consume canonical serialized findings/evaluations generically without duplicating per-rule mappings, rebuilding finding IDs, or calling detectors.
- [x] Preserve canonical `finding_id == action_id` and validate patient/claim/line ownership and generic line-kind source identity across patient → cache → cohort → API.
- [x] Carry canonical finding fields needed by patient/bill/cohort consumers, including identities, detail/source/severity/evaluation metadata, existing display fields, and null money, while collapsing exact duplicates.
- [x] Aggregate evaluations generically by `(rule_id, claim_id)` so distinct claim evaluations and missing-input statuses are retained; keep missing top-level cache artifacts unavailable rather than fake zero.
- [x] Extend synthetic cache/API regressions for Wave A visibility, future-rule passthrough, stable line-kind IDs, duplicate collapse, null money/unchanged totals, invalid-row fail-closed behavior, and K21/K26 compatibility.
- [x] Run required domain/cache/API tests, compile changed Python files, enforce the no-allowlist/no-ID-rebuild invariant, and run `git diff --check`; record exact evidence in the checkpoint journal.
- [x] Set state to `checkpoint2_accepted` after independent Chief review.

### Out of Scope
Frontend changes, detector-set expansion or medical logic changes, audit generator/matrix/report changes, pricing formulas or financial semantics, DuckDB schema migration, new API routes, deployment or production-cache work, source dirty work, commits, pushes, PRs, merges, and any rule outside the five canonical rules.

### Review
Checkpoint 2 is accepted by Chief. `cohort_compliance.py` now projects serialized findings/evaluations generically with no rule-ID allowlist and no finding-ID reconstruction; canonical IDs are copied unchanged, future well-formed rules pass through, exact duplicates collapse deterministically, and evaluations retain distinct `(rule_id, claim_id)` statuses. Existing cache/API routes and payload JSON were reused without schema migration or cache rebuild. Independent verification: `255 passed, 1 warning` for all billing-domain tests plus claim-compliance and compliance-index API suites; financial invariance `4 passed, 1 warning`; compileall, `git diff --check`, and the forbidden-symbol invariant passed. Audit generator/matrix updates remain intentionally deferred to Checkpoint 4; frontend work is authorized next as Checkpoint 3.

---

## Task: Phase 5 Checkpoint 1 — canonical finding contract + domain plumbing

### Goal
Implement one canonical nonfinancial rule-finding evaluation path for K21, K26, `tablo15_10`, `tablo15_20`, and `tablo15_5`, preserving legacy analyzer output while making patient claim-compliance projection reuse the precomputed batch.

### Subtasks
- [x] RED→GREEN: add deterministic claim/procedure/drug/material finding identity and typed `RuleFinding` / `RuleEvaluation` / batch contract.
- [x] RED→GREEN: add canonical one-pass evaluation for exactly the five authorized detectors, including explicit missing-input evaluations, ownership validation, normalization, de-duplication, deterministic ordering, and null money.
- [x] RED→GREEN: route `analyze_claim` through the canonical evaluation for the five detectors while preserving legacy flat violations and detector order/fields.
- [x] RED→GREEN: make `compute_patient_billing_report` evaluate the batch once and make `project_claim_compliance` a pure projection with zero detector/analyzer calls.
- [x] RED→GREEN: surface the three selected Tablo 15 findings in patient `claim_compliance`, preserving K21/K26 identity/serialization compatibility, duplicate handling, missing context behavior, and unchanged financial totals.
- [x] Run the required focused suites, compileall, and `git diff --check`; record exact RED/GREEN and final verification evidence in the checkpoint journal.
- [x] After all tests are green, update checkpoint state and complete this review section with exact changed paths/results.

### Out of Scope
New Wave A cohort visibility, API/schema/route changes, cache schema changes, frontend work, audit generator/matrix/report changes, pricing/totals semantics, detector medical/regulatory semantics, deployment, production cache rebuild, pushes, merges, and migration of any detector outside the five authorized rules. A minimal existing-K21/K26 cohort compatibility fix was accepted because canonical five-component IDs otherwise regressed across patient and cohort projections.

### Review
Checkpoint 1 is accepted by Chief. Canonical finding identity includes URL-quoted `line_kind` between `claim_id` and `line_id`; K21/K26 cohort projection preserves and validates that identity without surfacing the three Wave A rules yet. Compileall exited 0; focused domain/cohort/API verification passed `96 passed, 1 warning`; the full billing-domain plus claim-compliance API gate passed `244 passed, 1 warning`; `git diff --check` exited 0. Phase 5 Checkpoint 2 is now authorized; frontend work remains pending its acceptance.

---

## Task: Rule Engine surfacing audit + generic finding surface (2026-09-18)

### Goal
Execute `plans/billing/2026-09-18-rule-engine-surfacing-audit-plan.md`: produce exact runtime/visible/hidden/duplicate/financial counts and the complete hidden-rule list before migrating additional existing rules into a generic finding surface.

### Subtasks
- [x] Freeze audit definitions and baseline: registry family, runtime detector, finding kind, visibility, duplicate, and money semantics.
- [x] Build a deterministic static inventory of `analyze_claim` and `compute_patient_billing_report` runtime calls and reconcile it with `RULE_REGISTRY` without treating the registry as a dispatcher.
- [x] Trace every runtime output through report fields, `recommended_actions`, `claim_compliance`, totals, cache/API, and patient/cohort frontend surfaces.
- [x] Generate the machine-readable coverage matrix plus human audit report with exact counts, hidden list, duplicate groups, and financial/nonfinancial classification.
- [x] Add an inventory completeness regression so new runtime detectors cannot appear without a surfacing classification.
- [ ] Review the audit output and lock migration scope before changing runtime/UI behavior.
- [ ] Define one canonical finding contract and migrate the approved hidden nonfinancial validation wave without one-off per-rule wiring.
- [ ] Verify patient/cohort reachability, old-cache honesty, stable finding identities, duplicate behavior, and unchanged financial totals for nonfinancial migrations.

### Dispatch scope: baseline audit only (Phases 0-4)
- [x] Phase 0: freeze taxonomy, source revision, registry breakdown, canonical runtime entrypoints, and product projection entrypoints.
- [x] Phase 1: generate a deterministic static runtime inventory for `analyze_claim` and `compute_patient_billing_report`, including gated calls and registry/artifact reconciliation.
- [x] Phase 2: trace every runtime output through report fields, recommended actions, claim compliance, dedicated sections, and monetary totals.
- [x] Phase 3: trace cache/API plus patient/cohort frontend reachability and deep-link behavior; treat Rule Database as metadata only.
- [x] Phase 4: generate the exact JSON matrix and Markdown audit report, including hidden findings, duplicate groups, unknown mappings, and separate inventory-level counts.
- [x] Add and execute completeness tests for canonical runtime calls, the current two-rule claim-compliance allowlist, registry-only classification, and unmapped runtime-call failure.
- [x] Review the Phase 0-4 diff and executed evidence, create coherent local audit checkpoint commit(s), and stop at `ready_for_review` for Chief acceptance.

### Out of Scope
New SUT/medical detectors, diagnosis-procedure medical-necessity logic, coverage-status metric manipulation, unrelated pricing/recovery changes, and production deployment/cache rebuild during the audit phases.

---

## Task: PR87 claim-compliance correctness fixes (2026-09-18)

### Goal
Implement `plans/billing/2026-09-18-pr87-claim-compliance-fixes-plan.md` on `feat/compliance-k21-k26` so K21/K26 are correct, cohort evaluation payloads are bounded, and claim-compliance findings have their own reachable server-side pagination path.

### Subtasks
- [x] Enforce same-day K21 semantics and replace the different-day regression.
- [x] Reconcile K26 diagnosis presence from header plus normalized primary diagnoses while preserving blank-vs-unavailable behavior.
- [x] Replace unbounded cohort evaluation identities with exact counts plus bounded non-evaluated details and truncation metadata.
- [x] Fetch and paginate `surface=claim_compliance` independently in the frontend, preserving active patient/cohort filters and total-count badges.
- [x] Make claim-compliance monetary summary values nullable in TypeScript and render them nonfinancially.
- [x] Run focused backend/frontend tests, Ruff, TypeScript, changed-file ESLint, then full backend/frontend suites where feasible.
- [x] Record exact verification outcomes in `tasks/k21-k26-result.md` and complete this review section.

### Out of Scope
New SUT detectors, monetary integration for claim-compliance, broad compliance redesign, diagnosis-conflict adjudication, production cache rebuild/deploy, pushing or merging the branch.

### Review
Implemented from plan commit `58f3308a` on `feat/compliance-k21-k26`. K21 now joins bundled services to exact 510090 dates. K26 reconciles a nonblank header diagnosis with normalized primary `ClaimDiagnosis` rows while preserving explicit-blank versus unavailable provenance. Cohort cache data stores per-patient status counts plus at most 20 non-evaluated details; API responses expose exact filtered counts without unbounded successful evaluation identities. Compliance surfaces are fetched and paginated server-side; large patient cohorts fall back to a JSON POST when the GET query would exceed 6,000 characters. Claim-compliance money remains nullable/nonfinancial and old-cache absence stays unavailable.

Final verification on the final tree: focused backend **84 passed**; focused frontend **22 passed**; full backend **2631 passed**; full frontend **266 passed**. Changed-file Ruff, ESLint, TypeScript, and `git diff --check` passed. Independent review first found and drove fixes for stale cohort aggregate state and backend-first rolling-deploy compatibility; the final fresh `codex review --uncommitted` returned **0 findings / patch is correct (0.91 confidence)**. Its read-only sandbox could not run pytest, so the writable-workspace suites above are the execution evidence. No production cache rebuild/deploy, push, merge, or commit was performed.

---

## Task: K21 + K26 reviewer blockers

### Goal
Prevent late-money inference crashes and show accurate scoped presentation counts while retaining legacy actions and financial totals.

### Subtasks
- [x] Confirm the three requested fixes and existing test/runtime conventions; review this narrow plan against the request.
- [x] Use full inference for cohort rows and regress >100 null-money findings before a monetary legacy row, including preserved totals and row money.
- [x] Count scoped claim findings in patient/claim KPI and tab badge only; regress patient, claim and legacy-only counts.
- [x] Omit the claim-compliance dashboard badge for old caches and assert rendered absence.
- [x] Run focused backend/frontend tests, changed-file lint and tsc; record exact outcomes in tasks/k21-k26-result.md.

### Out of Scope
Pagination redesign, broad refactoring, other detectors, money/action integration, other worktrees, commits, pushes and live changes.

### Review
46 backend and 18 frontend tests passed; final tsc and Ruff passed. Changed-file ESLint found only the existing PatientWorkspaceViews navigation-effect error; HEAD stdin lint reproduced the same error, and all other touched frontend files passed lint. No suppression or out-of-scope navigation rewrite. Full inference regression demonstrated red before/green after; scoped counts and old-cache badge have rendered assertions. Exact commands, limitations and results recorded in tasks/k21-k26-result.md. No commit/push/live changes.

---

## Task: K21 + K26 reporting reachability

### Goal
Expose only the existing ICU bundled leakage and missing diagnosis detectors through full-context reporting, cache/API and native compliance UI without any money contribution.

### Subtasks
- [x] Verify normal ingestion provenance and positive/negative scenarios before wiring detectors.
- [x] Add backward-compatible availability tracking and a narrow report-owned nonfinancial projection with stable claim/line identities.
- [x] Connect cache/index/API and native frontend filtering/rendering with patient links.
- [x] Run real-function ingestion integration tests, financial regressions, frontend tests, typecheck and lint sequentially for pytest.
- [x] Replace unbounded evaluation rows with a compact summary and closed, bounded details; verify 120-evaluation rendered regression.
- [x] Inspect artifact drift and record exact evidence in tasks/k21-k26-result.md.

### Out of Scope
Engine merging, validator changes, other detectors, rule catalogs, shipped data, live services, commits, pushes and PR creation.

### Review
K21/K26 implemented through normal ingestion/context, report-owned nonfinancial projection, cache/index/API and native UI. Chief independently reported 71 backend tests and 9 frontend tests passing before the final compact-summary change; typecheck and Ruff passed. Final UI verification: dashboard Vitest file 10/10 passed; ESLint passed for the test and table. Large-list regression verifies 120 evaluations, correct counts, closed details bounded to 20 entries, distinct unknown/clean empty states, findings, links and null money. Prior status inspection showed only scoped source/tests/tasks changes, no catalog/generated-data drift; no new broad inspection or backend run in this final finish. Evidence and limitations: tasks/k21-k26-result.md. No commits, pushes or live changes.

---

## Task: 2026-08-29 SUT rule corpus (PR 80 follow-through)

### Goal
PR 80 ingest is on this branch; encoded YAML/wave keys resolve against the 2026-08-29 clause corpus; compile + coverage artifacts are regenerated; the two new grandfathering bents are encoded; inventory/coverage goldens match the live 08-29 corpus.

### Subtasks
- [x] Remap stale `coord#hash` cites in YAML + `gate_b_wave_config.py` to new hashes (similarity-matched)
- [x] Remap positional `C*` `gate_b_sources` + `clause_type_overrides.yaml` (07-01 → 08-29 id shift)
- [x] Update YAML messages for real law changes (4.1.4.c, 4.2.1.C-3/C-5.a, 4.2.8.A.b, 4.2.14.C KLL, 4.2.15.D-2 radiology)
- [x] Encode new `4.2.1.C-3.d` and `4.2.1.C-5.d` grandfathering rules
- [x] `compile_rules.py` then `compile_rules.py --check`
- [x] `build_sut_coverage.py`
- [x] Changelog
- [x] Recompile §4.2.1 against current coverage so empty-hash `is_in_force=false` ghosts leave traces (pending 16+2)
- [x] Skip extractor empty-hash out-of-force rows in Gate B export
- [x] Freeze coverage/C* inventory goldens to live 08-29 counts (215 gaps / 28 deontic / 215 C* / 249+15 eligible)
- [x] Recompute w4 tier_b resolved C* set from live YAML cites
- [x] Decision note for accepted remap tolerances
- [x] Targeted pytest; `git status` after (pytest can mutate artifacts)
- [x] Full `tests/unit` (2564 passed, 9 skipped)
- [x] Commit, push, update PR #84

### Review
PR 80 ingest is on this branch. Encoded YAML/wave keys resolve against the 2026-08-29 corpus. Gate B export skips extractor empty-hash out-of-force copies. Historical wave2/r6 manifests remapped by clause_key. `tests/unit`: 2564 passed. Do not merge #80 separately; this PR already contains `5f05d3a4`.

### Out of Scope

### Out of Scope
Merging PR 80 itself; encoding unencoded AMENDED coords (2.4.2.B-1.(2), 4.1.4.(4), 4.2.14.B.(1), 4.2.15.D-1.(3)); deferral_table historical stale hashes not on the compile path; synthetic cohort regen.

---

## Task: Chrome tab navigation — left-click replaces, “Yeni sekmede aç” stays

### Goal
Left-click / sidebar navigate in this strip tab (replace unless that tab already exists). Ctrl/middle/right “Yeni sekmede aç” add a background tab and stay; if it already exists, switch to it. The menu click must not fall through onto the patient link.

### Locked decisions (2026-09-03 grill)
- Left-click a patient on Hastalar: this strip tab **becomes** that patient (Hastalar gone).
- Left-click patient B from patient A: this tab becomes B (A gone), unless B already exists → switch to B, leave A.
- Sidebar Hastalar: same rule (replace this tab if Hastalar is not already a tab; switch if it is).
- “Yeni sekmede aç” / Ctrl / middle: not open yet → add unselected tab, **stay**. Already open → switch to it.
- Click-through after the context menu is a bug, not “open and go”.

### Subtasks
- [x] `applyWorkspaceSync` replaces the active tab when the dest is new; still switches when dest exists
- [x] `useOpenPatientBackground` stays on add; `router.push` when that tab already exists
- [x] Context menu swallows the ghost click so the patient link does not navigate
- [x] Update workspace tab unit tests; vitest + tsc
- [x] Browser: left-click replaces; “Yeni sekmede aç” stays on Hastalar with a new unselected tab

### Review
“Yeni sekmede aç” was navigating because the menu click fell through onto the patient link. Menu now adds a background tab and stays on Hastalar. Left-click replaces this strip tab (Hastalar becomes that patient) unless the dest tab already exists, in which case it switches. Ctrl/middle match the menu. Playwright: menu on 0001 stayed on `/?tab=patients` with both tabs; left-click 0043 replaced Hastalar and kept 0001.

### Out of Scope
Chrome “switch immediately” preference; duplicate strip tabs for the same patient; drag-reorder.

---

## Task: Keep local Next.js from OOM-exiting

### Goal
`http://localhost:3000` stays up; Turbopack is not allowed to fill the Node heap and vanish.

### Subtasks
- [x] Switch `next dev` to webpack (Turbopack leaked ~15GB and exited)
- [x] Restart frontend; confirm `/login` returns 200

### Review
Cause was Next 16 Turbopack OOM (~15GB), not a closed browser tab. Dev server now uses webpack. `/login` 200 at http://localhost:3000.

### Out of Scope
Fixing the Turbopack leak itself; changing Node version.

---

## Task: Chrome-gestures to open patient strip tabs

### Goal
Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” on any patient profile link add an in-app strip tab and leave the current view. Five patients = five of those clicks while staying on Hastalar.

### Locked decisions (2026-09-02)
- Workspace strip tabs only (never a new browser window).
- Per-row Chrome gestures, no multi-select.
- Every patient-id navigation: cohort table, compliance, red kuyruğu, revenue/optimizer lists, Ctrl+K, in-workspace patient search.

### Subtasks
- [x] `openBackground` on the workspace store (`ensureWorkspaceTab`, do not change `activeTabId`)
- [x] Shared `PatientTabLink` + context menu; helper tests for href → view and modifier detection
- [x] Cohort table: real patient href + row Ctrl/middle/right-click stay on Hastalar
- [x] Replace remaining patient `<Link>`s (compliance, findings, red kuyruğu, optimizer)
- [x] Ctrl+K and PatientSearch: same gestures; Ctrl+Enter in palette opens background and stays open
- [x] i18n en/tr `openInNewTab`
- [x] vitest + tsc; browser: five Ctrl-clicks on Hastalar leave you on the list with five new strip tabs

### Review
Chrome gestures open in-app strip tabs without leaving the current view. `openBackground` keeps `activeTabId` unchanged. Cohort, compliance, red kuyruğu, optimizer, Ctrl+K, and in-workspace PatientSearch all use the same Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” path. `npx vitest` 249 passed, `npx tsc --noEmit` clean. Browser on http://localhost:3000 Hastalar: five Ctrl-clicks stayed on `/` with five new strip tabs; right-click showed “Open in new tab” and added SENTETIK-HASTA-0039 while still on the list.

### Out of Scope
Multi-select; native browser “Open in new tab”; Shift+click new window.

---

## Task: Chrome-style workspace tabs (equal width, no cap, scroll)

### Goal
The tab strip behaves like Chrome: every open tab is the same width, they keep a standard size until they hit the search/feedback cluster, then they shrink together. No 6-tab cap, no silent LRU close, no `+N`. When they hit min width, a scroll arrow reaches the rest.

### Locked decisions (2026-09-02)
- Equal width (not content-sized).
- Sections AND patients stay as tabs; sidebar click still opens a tab.
- No cap, no eviction; close only via ×.
- Kill `+N`. At min width: hidden-scrollbar track + scroll chevron (Chrome), not an overflow menu.

### Subtasks
- [x] Remove `WORKSPACE_MAX_TABS` eviction from `applyWorkspaceSync`, `ensureWorkspaceTab`, and `readWorkspaceSession`; update unit tests (opening a 7th tab must keep all 7)
- [x] Delete `countInlineWorkspaceTabs` / `splitWorkspaceTabs` and the `+N` overflow UI
- [x] Tab track: `flex-1 min-w-0`, each tab `flex: 1 1 13rem; min-width: 4.5rem; max-width: 13rem` so few tabs stay standard-sized with empty space before search, many tabs shrink equally
- [x] When `n × min-width` exceeds the track: keep min width, `overflow-x` hidden (no visible scrollbar), left/right chevrons, wheel scrolls the track, activating or opening a tab scrolls it into view
- [x] Close/split stay hover-only and must not inflate min width (overlay, not extra flex space)
- [x] i18n: overflow string → scroll-more aria labels (en + tr)
- [x] `npx vitest` + `npx tsc --noEmit` green
- [x] Browser: 3 tabs stay ~208px with a gap before search; 8+ tabs shrink together; more than fit at 72px → chevron, no `+N`; closing a tab restores width; chat-dock open shrinks available width

### Review
Chrome-style strip is live. No 6-tab LRU cap; no `+N`. Playwright: 3 tabs = 208px equal with a gap before search; 8 tabs = 159px equal filling the track; 18 tabs at 720px = 72px min + left scroll chevron. App is running at http://localhost:3000.

### Out of Scope
Drag-reorder, tab groups, a Chrome “new tab” `+` button, pinned tabs, changing how sidebar/search opens tabs, raising keep-alive of hidden patient panes.

---

## Task: Fit workspace tabs to top-bar width

### Goal
The workspace tab strip shows every open tab that actually fits; `+N` appears only when remaining tabs cannot fit beside the search/feedback actions.

### Subtasks
- [x] Add a pure `countInlineWorkspaceTabs` / `splitWorkspaceTabs` helper (fit-to-width, keep active tab inline)
- [x] Unit-test the helper: all fit, overflow needed, tiny bar, active tab in overflow
- [x] Replace the hardcoded `WORKSPACE_INLINE_TABS = 5` split in `WorkspaceTabStrip` with ResizeObserver measurement
- [x] Close the overflow menu when it becomes empty; remeasure on resize and chat-dock inset
- [x] Run `npx vitest` on the helper + `npx tsc --noEmit`
- [x] Verify in the browser: 6 open tabs on a wide window show all; shrinking the window reveals `+N`; no large gap before search

### Review
Root cause was `WORKSPACE_INLINE_TABS = 5`: the 6th tab always went into `+1` regardless of leftover width. Overflow is now measured with ResizeObserver. Playwright: 1600px viewport → 6 inline tabs, no `+N`; 720px → `+4` with the active tab kept visible.

### Out of Scope
Changing `WORKSPACE_MAX_TABS` (still 6). Redesigning tab chrome, labels, or the overflow dropdown itself.

---

## Task: Fix Hermes Cursor proxy HTTP 502 Invalid User API Key

### Goal
Telegram/gateway POSTs to `127.0.0.1:8765` authenticate with the stored Cursor user key instead of a foreign Bearer, so CreateAgent no longer returns 401.

### Subtasks
- [x] Confirm stored `CURSOR_API_KEY` still works for catalog + SDK oneshot (no key echo)
- [x] Prove incoming Hermes `Authorization` is what CreateAgent uses (prefix/len only)
- [x] Patch proxy to always use systemd `CURSOR_API_KEY`; ignore non-`crsr_` Bearer
- [x] Restart `hermes-cursor-proxy`; smoke POST with dummy Bearer + real CLI
- [x] Add gateway `EnvironmentFile` only if `hermes setup` is not mid-run — skipped; setup still on pts/0, proxy fix is sufficient
- [x] Document cause in this review section

### Review
The 502 was not a bad Cursor key. Hermes Telegram sent `Authorization: Bearer no-key-required` to the loopback proxy; the proxy forwarded that to CreateAgent and Cursor 401'd. Proxy now ignores non-`crsr_` Bearers and uses systemd `CURSOR_API_KEY`. Smoke: POST with the placeholder header returned `AUTHFIX_OK` (CreateAgent 200). Retry the Telegram turn; no gateway restart needed.

### Out of Scope
Replacing the live Hermes tree; changing default Muse Spark model; printing the API key.

---

## Task: Wire Cursor Grok into Contabo Hermes (Hermes stays the agent)

Full plan: `plans/ops/2026-08-29-hermes-cursor-provider-vps.md`

### Goal
On `contabo-vps`, Hermes can use Cursor-billed Grok 4.6 / Composer while Hermes keeps tools, memory, and Telegram. Default model stays `muse-spark-1.2-contributor`.

### Subtasks
- [x] Inventory VPS Hermes 0.20.0, gateway unit, plugins, env (no CURSOR_API_KEY yet)
- [x] Drop `cursor_sdk_client.py` (Nous #88212 / hermes-agent-sdk) into the install
- [x] Loopback OpenAI proxy on `127.0.0.1:8765` with Cursor tools disabled
- [x] `pip install cursor-sdk` in the Hermes venv
- [x] systemd user unit `hermes-cursor-proxy`
- [x] `custom_providers` entry; do not change default model
- [x] Add `CURSOR_API_KEY` when available; smoke `grok-4.6` oneshot
- [x] Restart gateway only if `hermes setup` is not mid-run

### Out of Scope
Replacing `/usr/local/lib/hermes-agent` with a fork; Cloud Agent handoff plugins; reverse-engineered `api2.cursor.sh` proxies.

---

## Task: Rebuild SUT coverage parquet + pin RULE_REGISTRY in CI

Full plan: `plans/billing/2026-08-23-demo-coverage-rebuild-and-registry-pin.md`

### Goal
Kural Veritabanı shows SUT clause text for `blood_component_isbt128_barcode` and `yatak_icu_overlap`, and CI fails if a `RULE_REGISTRY` id is missing from `sut_registry_coverage.parquet`.

### Subtasks
- [x] Branch `chore/sut-coverage-rebuild-registry-pin` from up-to-date `main`
- [x] Add `tests/unit/domain/sut/test_registry_coverage_artifact.py` (set equality + blood/yatak `matched_clause_count > 0`; fail if parquet missing)
- [x] Confirm that test **fails** on current parquet (missing those two ids)
- [x] Run `python scripts/sut/build_sut_coverage.py`
- [x] Confirm parquet has 47 rows, ids == `set(RULE_BY_ID)`, blood 3, yatak 12, icu 9
- [x] Re-run the new test + `tests/unit/domain/sut/test_rules_catalog.py` — green (full suite: 2583 passed)
- [x] Commit parquet + test (+ drift fix below, atomic) — `5a3ad53`; manifest sync `34849c6`
- [x] Open PR (#79), CI green (backend 6m13s + frontend)
- [ ] Merge to `main` — BLOCKED on branch protection (review required); needs Safa's merge click or explicit --admin go-ahead (deploy.yml follows)
- [ ] Verify production: `zero_clause_matches` length 6, those two rules have clause cards in the browser (after merge + deploy)

### Drift surfaced by the rebuild (fixed in-PR)
The parquet committed at `1c38126` was stale-at-birth: a pristine-worktree repro
proved that commit's own builder disagreed with it for 5 §4.2 clauses. Fixed via
`deferral_table.yaml` entries (C003658/C003756/C003834 tier_c_deferred, C004257
existing entry un-dropped, C004299 non_actionable) + `load_deferral_table`
resolves non-encode-eligible rows and same-clause_key content duplicates +
`repair_untraced` honest set aligned with the audit + compiled 4201/4210
manifests regenerated + 6 committed-manifest pins recalibrated.

### Out of Scope
Synthetic `skipped_no_data` fields; Fatura İnceleme UI; filling the remaining six zero-clause rows; rebuilding coverage inside CI.

---

## Task: Purge fake "demo"-coded claim lines from the synthetic cohort

**Rev 2 (2026-08-22)** — patched after plan review. Review verified against repo:
all 8 gap claims + 3 fact corrections confirmed. Do-not-implement-as-written lifted;
this rev addresses every item.

### Goal
No claim line in the synthetic cohort carries a fabricated `demo` code. All 13
fake-coded lines are removed at the generator (not filtered out of the parquet),
their scenario machinery is deleted or re-anchored, and the cohort is regenerated
+ cache rebuilt + verified end-to-end.

### Background (verified findings)
- 13 fake-coded lines exist, in 4 families:
  - **Drug-indication demos (6)** — patients 0014,0015,0016,0017,0019,0020,
    codes `SUT-DEMO-BEV/NIVO/DARA/PEM/TRAS/TRAB`.
  - **MEDULA 0411 drug anchor (1)** — patient 0031, code `SUT-DEMO-BEV`.
  - **Material-prose demos (2)** — patients 0021 (`SUT-DEMO-OPT`), 0022 (`SUT-DEMO-GRF`).
  - **§3.3/L4.4 keyword demos (4)** — patient 0001, codes `DEMO-L44-W1/W2/CL1/SS1`.
- None of these codes exist in any real catalog (0 hits in `ek4a_drugs` + all `ek3*`).
- **Fact correction (rev 2):** 5 of 6 oncology BRANDS DO exist in EK-4A
  (OPDIVO×2, DARZALEX×3, KEYTRUDA×1, HERCEPTIN×1, YONDELIS×1); only
  AVASTIN/bevacizumab is absent. Replacement is still out of scope (Safa chose
  deletion), but the earlier "cannot be replaced" claim was overstated for 5/6.
- **Fact correction (rev 2):** patient 0001 is **Tier C** filler (not "unranked").
  The other 9 demo patients are Tier B. Tier A is untouched.
- Rule engines match by drug name/INN and material-name keywords, NOT by code — the
  fake codes are cosmetic placeholders, but the lines are load-bearing for showcases.

### DECISION POINTS (confirmed by Safa 2026-08-22)
- **D1 — MEDULA 0411 (patient 0031):** CONFIRMED re-anchor from `drug` → `claim`
  (claim-level rejection, same pattern as scenario 0032). Keeps the MEDULA Red-Queue
  scenario but drops the fake-coded drug line.
  - *Verified alternative (not taken):* the same claim carries a REAL drug line
    `A16712` (MEXIA XR 14 MG); anchoring 0411 to it would keep drug semantics with
    no fake code. Claim-level kept because it is simpler and matches the confirmed
    decision; `related_line_*` is display-only, playbook matches on `sonuc_kodu 0411`.
- **D2 — Patients 0014–0022 after demo removal:** CONFIRMED keep them as ordinary
  background patients (no renumbering), but strip their scenario entries from
  `demo_manifest.json` / `demo_vignettes.json` and the tier lists. They fall to Tier C.

### ACCEPTED PRODUCT LOSS (recorded, not a surprise after regen)
After the purge, no synthetic patient showcases these in the UI (engines + unit
tests remain; live cohort demos do not):
- §4.2 drug indication (6 oncology lines, 0014–0020) — gone from cohort
- §3.3 optical lens upgrade (0021) and hip-graft no-pay (0022) — gone from cohort
- §3.3 keyword L4.4 (0001, the original UI complaint) — gone (intended)
Kept: §3.1 material prose real codes (0023 OP1592, 0024 OP1000), claim readiness
(0033 OP2000), MEDULA 0411 red-queue (claim-level), all Tier A live demos.

### Subtasks

**Phase 0 — Baseline**
- [x] 0.1 Re-confirm the 13 lines + codes with a fresh parquet read; record counts (drug=7, material=6).
- [x] 0.2 D1/D2 confirmed by Safa: re-anchor MEDULA-0411 to claim-level; keep 0014–0022 as background patients.

**Phase 1 — Generator surgery (`scripts/synthetic/`)**
- [x] 1.1 `gen/specs.py`: delete `_DRUG_INDICATION_DEMO_SPECS` (all 6 SUT-DEMO).
- [x] 1.2 `gen/specs.py`: remove `optical_lens_upgrade` + `hip_graft_no_pay` from `_MATERIAL_PROSE_DEMO_SPECS` (KEEP `kdv_ceiling_exceeded`=OP1592, `procurement_incomplete`=OP1000).
- [x] 1.3 `gen/specs.py`: re-anchor `_MEDULA_DEMO_SPECS["0031"]` drug→claim (per D1).
- [x] 1.4 `gen/patients.py`: delete demo wiring for 0014–0020 (drug) and 0021–0022 (material OPT/GRF); KEEP 0023–0024.
- [x] 1.5 `gen/orchestrate.py`: drop `_DRUG_INDICATION_DEMO_SPECS` import + `drug_indication_demo/spec` wiring, **AND delete the inline drug-row injector block (~lines 405–458: `if drug_indication_spec:` → `ctx.drug_claims.append` + `ctx.expected.append`)** — leaving it would let fake lines be re-created. Keep `material_prose_spec` path (still used by 0023/0024 + claim_readiness).
- [x] 1.6 `gen/reconcile.py`: delete active `_inject_specialty_keyword_demo_rows`.
- [x] 1.7 `gen/materials_flags.py`: delete dead duplicate `_inject_specialty_keyword_demo_rows`.
- [x] 1.8 `gen/workbook.py`: remove its import + the `_inject_specialty_keyword_demo_rows(materials, claims)` call.
- [x] 1.9 `gen/__init__.py` + `generators.py`: remove `_DRUG_INDICATION_DEMO_SPECS` re-exports.
- [x] 1.10 `gen/medula_anchor.py`: delete now-unused `drug` anchor branch (dead-code cleanup).

**Phase 2 — Validator (`validate_sut_synthetic_data.py`)**
- [x] 2.1 Delete `_validate_drug_indication_demos` + `DRUG_INDICATION_DEMO_PATIENTS` + `DRUG_INDICATION_DEMO_TIER_B_FIELDS` + its call site (~line 1278).
- [x] 2.2 Remove 0021/0022 from `MATERIAL_PROSE_DEMO_PATIENTS` / `MATERIAL_PROSE_DEMO_MATERIAL_CODES` / `MATERIAL_PROSE_DEMO_FLAG_EXPECTATIONS` (KEEP 0023/0024).
- [x] 2.3 Keep `DRUG_INDICATION_WORKBOOK_COLUMNS` + §4.2 drug columns (still required schema); keep `_empty_drug_indication_fields` / `_ensure_drug_indication_columns`.
- [x] 2.4 **(rev 2)** Gate/delete the MEDULA `0411` drug-content branch (~lines 966–978): it requires a drug anchor with `uzmanlik_kurulu_raporu_var=False`, which no longer exists after the claim-level re-anchor. Skip the check when the anchor type is claim-level.

**Phase 3 — Curated data + golden + docs**
- [x] 3.1 `demo_manifest.json`: remove `scenario_by_index` entries 0014–0017,0019–0022 and drop the same 8 indices from `tier_b_patient_indices` (KEEP 0018, 0023–0028, 0030–0033); 0031 stays (claim-level).
- [x] 3.2 `demo_vignettes.json`: remove vignettes 0014–0017,0019–0022; keep 0031 (update its description if it references the drug anchor).
- [x] 3.3 **(rev 2)** Trim `data/gazette/prose_rules/golden/material_prose_sprint2.json` (remove the 0021/SUT-DEMO-OPT and 0022/SUT-DEMO-GRF entries). Update human docs that advertise the purged patients: `data/synthetic/README.md`, `docs/gazette/partial-coverage-scope.md`. (`DEMO_COHORT.md` is auto-regenerated by the generator — verify after regen.)

**Phase 4 — Tests**
- [x] 4.1 `test_sgk_uplift_synthetic_demos.py`: delete `TestDrugIndicationSyntheticDemo`; remove the 2 SUT-DEMO params from `TestMaterialProseSyntheticDemo` (keep kdv/procurement); keep the MEDULA 0411 param (claim-level still passes).
- [x] 4.2 `test_claim_drug_indication.py`: KEEP (engine test, in-memory fixtures); optionally rename fixture `SUT-DEMO-BEV`→neutral token.
- [x] 4.3 `frontend/.../SutBillingReportSections.test.tsx`: optionally rename fixture `SUT-DEMO-OPT`→neutral token.
- [x] 4.4 **(rev 2)** `tests/unit/api/test_patient_billing_drug_indication_api.py`: delete/rewrite the 0014, 0017, 0019 tests (they pin violation counts against cohort patients that lose their drug lines).
- [x] 4.5 **(rev 2)** `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`: delete `test_keyword_demo_material_names_present` (asserts DEMO-L44 material names in a live-built workbook).
- [x] 4.6 **(rev 2)** `tests/unit/synthetic/test_vignette_golden.py`: remove 0014–0017,0019–0022 from `test_sprint_demo_indices_0012_to_0033_documented` index list (keep 0012,0018,0023–0028,0030,0031,0033).
- [x] 4.7 **(rev 2)** `tests/unit/synthetic/test_cohort_tiers.py`: update hardcoded counts `tier_b == 24 → 16`, `tier_c == 17 → 25` (8 indices move B→C).

**Phase 5 — Regenerate + validate**
- [x] 5.1 Run `python scripts/synthetic/generate_sut_synthetic_data_v2.py` (runs validator + Tier A assert).
- [x] 5.2 Assert 0 `demo` codes remain — **(rev 2)** across `claims/*.parquet` (drug_code, material_code, equivalence_group), `clean/*.parquet`, AND the `sentetik_sut_v2_50_hasta.xlsx` sheets (the generator writes the workbook too; parquet-only grep is insufficient).
- [x] 5.3 Confirm Tier A patients (0002,0003,0006,0009,0010,0011,0013,0029,0038) still pass `assert_tier_a_post_regen.py`.

**Phase 6 — Test suite + typecheck**
- [x] 6.1 `pytest` (at minimum: `tests/unit/synthetic/`, `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`, `tests/unit/api/test_patient_billing_drug_indication_api.py`, `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py`, `test_claim_drug_indication.py`, MEDULA suite).
- [x] 6.2 Frontend `vitest` + `tsc --noEmit` if any fixture renamed.

**Phase 7 — Cache rebuild + end-to-end**
- [x] 7.1 Rebuild billing cache (`BILUN_STARTUP_POLICY=rebuild` + restart backend); confirm `/health` shows a completed build (not `active_build:null`).
- [x] 7.2 Spot-check a regenerated Tier B patient + the API to confirm no `demo` codes surface.

### Out of Scope
- Touching the real rule engines (`drug_indication.py`, specialty-prose, §3.3 keyword rules) — they stay.
- The real-coded material demos: `kdv_ceiling_exceeded` (OP1592), `procurement_incomplete` (OP1000), claim-readiness (OP2000).
- All Tier A showcase patients and the MEDULA scenarios with real-coded anchors.
- Replacing the 6 oncology demo codes with real EK-4A barcodes (5/6 brands DO exist in EK-4A — feasible in principle — but deletion was the chosen path; not requested).
- Renumbering patients or changing the 50-patient cohort size.

### Review
**Done 2026-08-22. Purge complete and verified end-to-end.**

- **Purge:** all 13 fake-coded lines removed at the generator (7 drug `SUT-DEMO-*`,
  2 material `SUT-DEMO-OPT/GRF`, 4 material `DEMO-L44-*`). Zero `SUT-DEMO`/`DEMO-L44`
  cells remain in `claims/*.parquet`, `clean/*.parquet`, and the `.xlsx` (verified).
  Remaining "demo" strings are only legit scenario-tag names of kept demos (copay
  exemption, payment-method) and internal line-IDs of kept real-coded material demos.
- **Regen:** `generate_sut_synthetic_data_v2.py` passes (validator + Tier A assert).
  Tier counts now B=16 / C=25 (8 purged indices moved B→C).
- **Cache:** rebuilt offline (`BILUN_STARTUP_POLICY=rebuild`), new build
  `a5bb830b` activated; active build has 0 demo-code cells across every VARCHAR
  column (the 121 "demo" cells first seen were from superseded builds — filter by
  `build_id`).
- **Tests:** 2570 unit tests pass; frontend `SutBillingReportSections` 26 pass;
  `tsc --noEmit` clean.

**Pre-existing drift fixed along the way (NOT caused by the purge).** The cohort was
last regenerated 2026-06-28 (`21aa6a9`); 318 commits later — incl. the 2026-07-01
SUT amendment (`5e82c31`), 163 newly-wired billing rules, and a generator RNG-path
change — the committed data was stale. Regen surfaced it; fixed:
- 3 validator bugs (missing `hasta_katilim_payi_profilleri` sheet, over-strict
  vignette-manifest alignment, EK-3B-1/2 derived flags wrongly required in parquet).
- Recalibrated drift-pinned goldens/tests: Tier A 0003 band (6300→6750),
  `test_f011` (6300→6750), `test_f015` (new §2.2.1 613080 violation + 3 doc rows),
  `test_0001`→retargeted to 0045-078 (0001-001 flipped to itemized),
  `test_copay_outcome_kind` rate patient 0012→0002.

**Accepted product loss (per D1/D2):** cohort no longer showcases §4.2 drug-indication
(0014–0020), §3.3 optical/hip-graft (0021–0022), or §3.3 keyword L4.4 (0001) — engines
+ unit tests remain. MEDULA 0411 kept as claim-level rejection.

**Not committed** (left for Safa to review/push). Backend left running on the rebuilt
cache (port 8001).

---

## Task: Fill TÜBİTAK 1812 pitch deck template (RV1) with Bilun content — Turkish

**Date: 2026-08-22**

### Goal
Produce a filled, panel-ready Turkish pitch deck from
`/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_Sablonu.pptx` (19 slides),
using ONLY facts from existing sources (no invented numbers):
- AGY112 iş planı formu (`BIGG/Medipol/1812_agy_112_pdf_form_v1.2.pdf`) — primary source
- Başvuru formu (`112 Numaralı İş Fikri Çağrı Dokümanı.doc`) — thematic area (Sağlık ve İyi Yaşam), TRL 4→7
- `Bilun Extras/Presentations/Bilun.pptx` (TR investor deck) — team/advisors, market framing
- Kent Hastanesi interview docs (customer validation evidence)

### Subtasks
- [x] Extract template structure (all 19 slides, shapes, tables, guide rails)
- [x] Extract content from AGY112 form, call doc, TR deck, interviews
- [x] Write plan (this file)
- [x] Python script (python-pptx): fill every placeholder/table with Bilun content, preserving run formatting
- [x] Delete guide-rail scaffolding per template's own instruction ("Nihai sunumdan önce bu rehber alanını silin") + kullanım notu + "Önerilen görsel/Eklenebilecek Unsurlar" boxes
- [x] Fix slide 12 "İŞ PAKETİ 7" → 6; replace generic timeline milestones with Bilun milestones
- [x] Fill checklist slide (18) with Evet + slide refs; adapt backup slide list (19)
- [x] Save as NEW file `RV1_1812_Pitch_Deck_BILUN.pptx` (template untouched)
- [x] Verify: reopen output — zero `[...]` placeholders except `[LOGO / ÜRÜN GÖRSELİ]` and `[FOTOĞRAF]`; zero guide shapes; all table cells filled (231 ops, all tables N/N); rendered to PDF via LibreOffice and visually inspected slides 1/2/7/12 — layout intact

### Content decisions (flagged to user)
- Numbers come verbatim from AGY form even where the form is internally inconsistent
  (2M TL vs 350K TL price points; 5M vs 15M at 12/2028) — deck quotes each section's
  own figure; inconsistencies flagged in final message.
- Slide 13 budget split (45/20/25/10%) is explicitly marked "taslak" — no Bilun budget
  document exists; total = 900.000 TL for %3 equity per current 1812 model.
- Customer validation stated honestly: sözlü pilot onayı, imzalı sözleşme yok.

### Out of Scope
- Adding real images (logo, photos, screenshots) — placeholders kept.
- Fixing AGY form's internal inconsistencies (flagged only).
- Modifying the template file itself.

### Review
Delivered: `/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_BILUN.pptx` (19 slides, Turkish).
- All 19 slides filled from AGY112 form + call doc + TR investor deck + Kent Hastanesi interviews; no invented numbers.
- Guide rails / kullanım notu / scaffolding boxes deleted per the template's own "nihai sunumdan önce silin" instruction.
- Slide 12: 6 work packages with Bilun milestones (KVKK veri aktarımı → 10+ kurum hedefi); "İŞ PAKETİ 7" typo fixed.
- Slides 16/18: risk matrix from AGY 5.1 (5 risks, real B plans, KVKK/etik note); checklist all Evet with slide refs.
- Verification: text dump (0 leftover placeholders), raw-XML spot check, LibreOffice PDF render + visual inspection.
- Known template quirk: small circle cards on slides 2–6 overflow slightly with full sentences — acceptable, polish in PowerPoint if desired.
- Flagged to user: AGY form internal inconsistencies kept as-is per section (2M vs 350K ₺ price points; 5M vs 15M ₺ at 12/2028; 45K vs 50K ₺ unit cost); slide 13 budget split marked "taslak".
- User must still add: logo/ürün görseli (slide 1) and 3 team photos (slide 14).

---

## Task: Reconcile financials (tiered pricing), fill Maliyet Formu (1.35M TL), fix deck overflow

**Date: 2026-08-23**

### Goal
Apply the approved tiered-pricing framing (2M ₺ flagship tier / ~350K ₺ blended ARPU)
consistently across (a) pitch deck, (b) AGY112 fillable PDF; fill Maliyet_Formu.docx with a
1.350.000 ₺ budget tied to work packages; shorten circle-card copy on deck slides 2–6.

### Subtasks
- [x] Plan (this section)
- [x] Deck: 1.35M investment (slides 13/15), slide 13 rows = Maliyet Formu categories, tiered-price notes (slides 7/10/15), shortened circle cards (slides 2–6), checklist row 13 note
- [x] Maliyet_Formu.docx → fill 5 tables (personel 990K / M013 150K / M015 150K / diğer 60K = 1.350.000), save as Maliyet_Formu_BILUN.docx
- [x] AGY fillable PDF: §1.4 tier note; §2.3 tier paragraph; §2.4 break-even sentence → 2M/50K/1.95M/5.4M; 4.4-2 diğer değişken 25K→30K; §4.2 350K→blended; 4.3 milestone 15M→~5M; §4.5 15M→8.75M+; save as v1.3_BILUN.pdf
- [x] Verify: deck re-render slides 2–6/13 visually (circles fit, tables clean); maliyet docx dump (totals 990+150+150+60=1.350K); PDF field dump (all 7 fields updated)

### Budget design (1.350.000 ₺)
- PERSONEL 990.000 (%73): Safa 1,0×18×33K=594K; Enes 0,5×12×33K=198K (Ay 7–18, mezuniyet sonrası); Kadir 0,5×12×33K=198K
- ALET/YAZILIM 150.000 (%11): 2× geliştirme bilgisayarı 90K; TR bulut barındırma+hesaplama 60K
- HİZMET 150.000 (%11): YMM 30K; hukuk 45K; sağlık ekonomisi 45K; sızma testi 30K
- DİĞER 60.000 (%5): seyahat 25K; TÜRKPATENT+telif harçları 15K; iletişim/ofis 20K
- MALZEME: boş (yazılım ürünü)
- Estimates flagged: monthly 33K ≈ 2026 asgari ücret işveren maliyeti tahmini; oranlar kullanıcı onayına açık.

### Out of Scope
- Changing any other AGY content; PRODİS submission; equity % (kept %3, flagged).

### Review
Delivered (all in /home/safa/Documents/BIGG/Medipol/):
- RV1_1812_Pitch_Deck_BILUN.pptx — regenerated: 1,35M ₺ yatırım (slayt 13/15); slayt 13
  satırları Maliyet Formu kategorileriyle birebir; tier notları (7/10/15); daire kartları kısaltıldı
  (2–6, render ile doğrulandı); checklist satırı güncellendi.
- Maliyet_Formu_BILUN.docx — 5 tablo dolu; TOPLAM 1.350.000 ₺.
- 1812_agy_112_pdf_form_v1.3_BILUN.pdf — 7 alan düzeltildi; tüm finansal ifadeler artık
  tier modeliyle tutarlı (2M amiral / ~350K blended; 4.4 tablosu 2M/50K/1.95M/5.4M).
Flagli tahminler (kullanıcı onayına açık): personel 33K ₺/ay ≈ 2026 asgari ücret işveren
maliyeti tahmini; Enes/Kadir 0,5 oran × Ay 7–18 (mezuniyet sonrası); pay oranı %3 korundu.
## Task: Build 5 jury-Q&A backup presentations (TÜBİTAK 1812 RV1)

**Date: 2026-08-23** — source table: RV1 deck slide 19 "Hazır Bulundurulması Gereken Yedek Slaytlar".
Output: `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`

### Goal
Five Turkish backup decks, facts-only (every number cited to AGY-112 v1.3 / RV1 deck /
interviews / repo artifacts; internal inconsistencies flagged, never silently picked).

### Subtasks
- [x] Extract facts via 3 parallel agents (technical; finance/IP/risk; competitor/customer) with "no source" lists
- [x] Write build script (python-pptx, 16:9, quiet design) producing 5 decks
- [x] Deck 1 Teknik Mimari & Test: pipeline, rule lifecycle, Track E diff (8263/94/26/0), coverage numbers (4757/2431/55/2271/622=%13,1), test protocol (2580 pytest + 242 frontend), fact-check 28 units (12/15/1/0), determinism+security, 6 zero-rows limits
- [x] Deck 2 Patent & FSMH: "Henüz başvuru yok" honest; legal rationale; ticari sır+telif+marka (Sınıf 9/42); FSMH envanteri; kurucu→AŞ devir; no EPO search / no university protocol (do not claim)
- [x] Deck 3 Rakip & Müşteri: statüko (Cerebral field quotes), Bizmed/EczAILab/RaporınAI, CodaMetrix/Waystar/Optum (unverified caveats), Olive AI lessons; Kent interviews verbatim; "Sözlü pilot onayı — imzalı sözleşme yok"; TAM/SAM/SOM AGY basis + inconsistency footnotes; Almalı paper 0.13–1.72% caveat
- [x] Deck 4 Finans & Ortaklık: price layers (2M flagship + 15–45K SaaS + %3–4 prim), unit economics, break-even both bases (2.8 vs ~6), milestones, 1812 budget %73/11/11/5 (Maliyet Formu empty-template caveat), %100 kurucu + %10 ESOP + %60 floor, investment path
- [x] Deck 5 Regülasyon & Risk: not-a-medical-device position; KVKK roadmap; etik kurul note; AGY 5-risk matrix table; expanded indicators/responsibles
- [x] Verify: LibreOffice PDF render of all 5; visual inspection of decks 3+4 (tables fit, TR intact, footers present)
- [x] Review section in this file

### Out of Scope
Redesigning RV1 main deck; adding logos/photos; inventing missing artifacts (LoI, EPO search, filled Maliyet Formu).

### Review
Delivered 2026-08-23 to `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`:
Yedek_1_Teknik_Mimari_ve_Test (8 slayt), Yedek_2_Patent_ve_FSMH_Devir_Plani (4),
Yedek_3_Rakip_ve_Musteri_Analizi (7), Yedek_4_Finans_ve_Ortaklik_Yapisi (7),
Yedek_5_Regulasyon_ve_Risk_Matrisi (7). Facts-only: every slide carries a source
footer (AGY-112 v1.3 §, RV1 slayt, interview date, repo path). Internal
inconsistencies (1M vs 2M price, 2.8 vs 6 break-even, TAM bases, 5.40 vs 5.46M
fixed cost, %3-7 vs measured %0.13-1.72) are flagged on-slide, never silently
picked. Missing artifacts NOT claimed: no patent/EPO search, no LoI, no signed
pilot contract, empty Maliyet Formu, no university devir protokolü — each slide
states the honest status instead.
## Task: Phase B migration scope lock (2026-09-19)

### Goal
Produce a Chief-reviewable `migration_scope_proposed` decision for the smallest coherent hidden, unpriced compliance migration slice without changing runtime, API, cache, frontend, or test behavior.

### Subtasks
- [x] Re-read the accepted audit plan, matrix, audit report, state, and journal; derive Wave A candidates only from matrix rows that satisfy every required eligibility condition.
- [x] Select the smallest coherent first vertical slice and document exact detectors, stable emitted rule IDs/kinds, explicit exclusions, and deferred candidates with reasons.
- [x] Define the one-evaluation canonical data flow, initial `RuleFinding` contract, identity/serialization rules, and exact implementation/test file map from domain through patient/cohort Compliance UX.
- [x] Define hard invariants, verification commands, and bounded implementation checkpoints for contract/domain, backend projection/cache/API, frontend surfaces, and CI regression.
- [x] Write `reports/rule-engine-surfacing/2026-09-19-migration-scope.md` and update state/journal while preserving accepted audit counts, hashes, and checkpoint provenance; leave state at `migration_scope_proposed` with next action Chief review.
- [x] Verify only the four authorized files changed, JSON remains valid, provenance/counts/hashes are preserved, no runtime behavior changed, and record the review evidence below.

### Out of Scope
Phase 5 implementation; runtime detector changes; API/cache schema or behavior changes; frontend changes; test behavior changes; financial/revenue migrations; production cache rebuild/deploy; commits, pushes, or merges.

### Review
Phase B proposes exactly three Tablo 15 line-integrity detectors for the first Wave A vertical: `detect_unreported_lab_result`, `detect_missing_drug_barcode`, and `detect_material_identity_errors`. The decision document derives them from the accepted matrix, records their stable rule/line identities, excludes all verified rerun equivalents and synthetic/financial/aggregate/catalog-only rows, defines the one-evaluation `RuleFinding` architecture, maps implementation/test files, and defers all remaining candidates with reasons.

State is `migration_scope_proposed` / `proposed`, phase remains 4, implementation remains `not_started`, and Chief review is the next action. Verification: the accepted starting checkpoint was confirmed as `5122d63472fcc8eb7182e7d45d3daf14c24c7a67`; `jq empty tasks/rule-engine-surfacing-loop/state.json` passed; the committed plan, audit generator, focused audit test, accepted matrix, and accepted audit SHA-256 values recomputed exactly to the hashes retained in state; all accepted audit counts remained unchanged; `git diff --exit-code -- src/bilun frontend tests scripts` passed; `git diff --check` passed; and trailing-whitespace inspection of all four authorized files found no matches. `git status --short` showed only the requested report/state/journal/todo paths. No runtime tests were run because this checkpoint intentionally changes no runtime or test behavior.

Chief review: accepted after independent matrix/source/rerun reconciliation. The next authorized unit is Phase 5 Checkpoint 1 only: canonical finding/evaluation contract and domain plumbing for K21, K26, and the three selected Tablo 15 line-integrity rules.
## Task: Final VPS correction — finding deep links and missing evaluations

### Goal
Consume canonical `finding` patient deep links with deterministic generic row highlighting and preserve only legitimate canonical `claim_id=null` unavailable evaluations in cohort counts, with truthful closure metadata and focused GREEN verification.

### Subtasks
- [x] Reopen the closure state against the current VPS worktree and record the exact migration-scope identity correction before implementation.
- [x] Add focused frontend RED regressions for route finding-query propagation, canonical finding selection/highlighting, and unknown-finding safe fallback.
- [x] Add focused backend RED regressions for counting a legitimate null-claim missing-input evaluation and rejecting malformed null-claim evaluations.
- [x] Run the new frontend and backend regressions and capture the expected RED evidence without changing production behavior first.
- [x] Parse `finding` in the patient route and pass it through the existing generic patient Compliance view to visibly select/highlight the canonical matching row while preserving legacy `action_id` fallback and safe unknown handling.
- [x] Update cohort evaluation validation to retain only well-formed null-claim unavailable evaluations with explicit missing-input metadata, without fabricating claim IDs or changing finding identity, deduplication, financial fields, or totals.
- [x] Run only the affected frontend/backend focused suites, `npx tsc --noEmit`, changed-module/test compileall, `git diff --check`, and invariant scans for financial/rule-allowlist/generated-cache changes.
- [x] Record exact GREEN results, changed files, remaining blockers, and no-commit/no-push boundary in this plan, the loop journal, and closure state; mark loop complete only after all focused gates are GREEN.

### Out of Scope
Financial formulas or totals, detector/rule semantics, rule-ID allowlists, canonical finding identity changes, new routes or schemas, broad/full test suites, generated dependency/cache files, production cache rebuilds, deploys, commits, pushes, PRs, merges, and patient data or credentials.

### Review
Implemented and verified the final VPS correction. Patient URLs now parse and propagate the generic `finding` query through the existing Compliance view; canonical `finding_id` rows visibly highlight, legacy `action_id` remains the fallback, and unknown/missing IDs leave normal rendering unchanged. Cohort validation now preserves only well-formed JSON-null claim evaluations with unavailable status and non-empty required/missing-input metadata, retains deterministic identity semantics without fabricating claims, and keeps financial rows/totals unchanged. Focused backend passed `22 passed, 1 warning`; frontend passed `5 files, 38 tests`; `npx tsc --noEmit`, compileall, Ruff, `git diff --check`, and invariant scans passed. One unrelated HTTP/cache dedup integration test exceeded the bounded 60-second VPS runner timeout; the financial regression passed. No commit, push, PR, merge, deploy, or production cache rebuild occurred.
## Task: Drug indication correctness, canonicalization, and UX — correction pass 1

### Goal
Resolve the independent-review blockers in the first-pass Drug Indication implementation: make route arbitration semantic and order-independent, restore the public legacy contract, keep live/cache/API/UI projections truthful and consistent, and leave the production correction ready for independent review.

### Subtasks
- [x] Add RED regressions for reversed/permuted full-corpus M06/M08 arbitration, canonical diagnosis ordering, corpus-derived diagnosis-specific/ICD-less families, public `validate_claim()`, cache/API round-trip counts, legacy normalization, noncoverage, deep-link selection, empty states, nonfinancial summaries, severity/contract fields, truncation metadata, and fail-closed structured validation.
- [x] Make route arbitration semantic and order-independent; return bounded `ambiguous_route` evidence instead of selecting by corpus order, and prevent ICD-less rules from establishing indication applicability.
- [x] Restore the complete public `/validate-claim` legacy projection, including `rule`, user-safe message, drug identity, explicit nonfinancial values, and stable canonical identities.
- [x] Unify live and cached report normalization/serialization and derive missing nested counts from structured findings/legacy violations without disagreement.
- [x] Add narrowly scoped honest normalization for genuine legacy cache payloads, including old empty/no-result and mixed modern/legacy payloads.
- [x] Represent `not_in_encoded_corpus` as a distinct bounded evaluation/manual-review state without inventing missing inputs, violations, routes, or financial values.
- [x] Thread exact `selectedFindingId` deep links through patient Drug Indication cards; add safe exact selection/highlighting and unknown-ID fallback.
- [x] Fix not-applicable, evaluation-only, noncoverage, and legacy progressive-disclosure UI states.
- [x] Preserve null/nonfinancial Drug Indication semantics through index, filtering, HTTP, and frontend summary/rendering paths.
- [x] Carry severity and every retained structured cohort field through action, cache/cohort, API, and frontend contracts; remove any intentionally patient-only fields from cohort output.
- [x] Add bounded-evidence counts/flags and truthful route/observed-diagnosis truncation disclosures, including available SUT source labels.
- [x] Tighten structured-entry validation fail-closed while retaining honest legacy parent compatibility, and remove plan trailing whitespace.
- [x] Run every requested RED/GREEN verification gate, direct original-vs-reversed corpus probe, deferred-path hash check, and changed-file security/artifact scan; record exact results here.

### Out of Scope
New §4.2 rules or corpus rewrites, broad Wave A/B/C/D expansion, frontend ICD disease dictionaries, financial/recovery semantics, production cache rebuild or deployment, dependency-lock changes, pushes, merges, PRs, and changes to `main`.

### Review — superseded first-pass evidence
The earlier first-pass review claimed completion, but independent review found blocking gaps in semantic arbitration, public legacy serialization, cached/live normalization, legacy-cache honesty, corpus noncoverage, deep-link consumption, empty-state UX, nonfinancial cohort semantics, projection contracts, truncation disclosure, and structured validation. That review is superseded; no audit checkpoint is claimed here.

### Correction pass status
Production correction and the post-production audit checkpoint are ready for independent review. The resumed saved worktree established a RED baseline of `28 failed, 124 passed`; after the bounded corrections, the exact requested suite passed `155 passed in 12.66s`, the affected backend corpus/API/cohort/financial suite passed `661 passed, 2 warnings in 67.53s`, and frontend Drug Indication/dashboard/deep-link coverage passed `3 files, 59 tests`. The direct M06.9/M08.0 probe produced byte-identical original/reversed/permuted payloads with honest `ambiguous_route` results and no selected rule.

After production commit `0e709489a54339f9fd4c2d143f0ce30a53ffb94c`, the deferred audit generator/test/matrix/Markdown checkpoint was refreshed with that exact source revision. The explicit noncoverage contract is that present but unencoded drug lines remain `not_in_encoded_corpus` manual-review evaluations, contribute no violation or money, invent no missing input, and make the Drug Indication/report rollup `partial_exact`. The CI repair focused suite passed `46 passed in 49.67s`; the exact backend CI command passed `2771 passed, 9 warnings in 1120.68s`; all 137 generated SUT rule/manifest artifacts were byte-identical; the surfacing generator `--check`, full-source Ruff, changed-file Ruff, and `git diff --check` passed. No merge, deploy, production cache rebuild, branch switch, or `main` change occurred.

---
## Task: Restore trustworthy frontend asset verification in Deploy

### Goal
Make the production deployment check find its verifier, accept healthy Next.js assets, reject missing assets, and run only after successful CI on this repository's main push.

### Subtasks
- [x] Reproduce the missing verifier on the GitHub runner and the escaped-asset false 404s against the live login page.
- [x] Add a same-repository main-push guard, ensure the VPS deploys only the exact commit whose CI passed, and check out that trusted CI commit on the Deploy runner without persisting checkout credentials.
- [x] Parse escaped Flight asset paths without retaining the escape backslash; preserve de-duplication and checks for real missing assets.
- [x] Add a regression using raw escaped Flight HTML and a local mock server, covering valid direct and Flight-only assets plus a genuinely missing asset.
- [x] Run focused verifier tests, source/workflow checks, and the verifier against the live login page; confirm the expected asset set has no malformed URLs.
- [x] Review the workflow privilege boundary, final diff, and focused test evidence independently.
- [x] Commit on an isolated branch, check existing branch CI, push, open a reviewable PR, and verify its backend/frontend CI checks.
- [x] Record final results and any remaining deployment limitation in this review section.

### Out of Scope
Additional Wave A detectors or rule migration, changes to production cache or pricing, and unrelated deployment architecture. Merging and production deployment wait for review of this specific PR.

### Review
Plan independently reviewed and approved before implementation, with a same-repository main-push gate, read-only checkout of the triggering CI SHA, and a remote SHA match before checkout or service work. Evidence: latest failed Deploy run 36263168625 completed the VPS step but could not find `scripts/deploy/verify_frontend_assets.py` in the runner workspace. The existing verifier separately found 16 malformed escaped URLs among 33 extracted live references; the corresponding clean assets returned 200. A diagnostic run found 23 unique healthy assets; this observed count is not a permanent contract. The workflow currently fetches latest main at deploy time, so an older green CI could otherwise ship a newer unverified commit; compare remote main with the triggering successful CI SHA before changing services.

Implementation verification: two escaped-Flight regressions failed against the old parser. Independent review caught a multiply escaped Flight-only path that the first fix still missed; its regression failed before the follow-up correction and passed after it. The focused file now passes 10/10 tests in 3.46 seconds from this worktree. Ruff and `git diff --check` passed. The workflow parsed as YAML, its deploy shell block passed `bash -n`, and targeted assertions checked its guard/checkout/remote-SHA ordering. The corrected verifier checked the live `/login` endpoint: 23/23 local assets returned nonempty HTTP 200 responses with zero malformed backslash URLs. Independent final diff review found no remaining blocker.

[PR #96](https://github.com/Safa675/Bilun/pull/96) contains the code on `fix/deploy-asset-verification`. Existing branch CI had zero runs before the push. Its [first hosted CI run](https://github.com/Safa675/Bilun/actions/runs/36315626985) completed successfully on commit `a55bb2a4` with both backend and frontend jobs green. The actual Deploy workflow can only validate this change after it lands on `main` and that main commit's CI succeeds; production deployment and merge remain outside this PR implementation task.

---


## Task: Resolve public-access review findings

### Goal
Fix the three verified PR #107 regressions on a branch based on verified current source, with regression tests and one new commit in a draft pull request from current main.

### Subtasks
- [x] Read current repository instructions and verify immutable current main source and PR state.
- [x] Bound outgoing chat context to 20 messages, 8,000 characters per message, and 32,000 total characters; validate new questions before persistence and preserve display history.
- [x] Remove the special developer exemption for username `test`; explicitly configure test allowlists and cover session revocation.
- [x] Include both supported LLM credential environment variables in public-asset scanning and cover the CLI environment path.
- [x] Run focused regressions, relevant broader checks where available, and independent review; record exact verification limits.
- [ ] Confirm the publication target, check its CI and current source, create one new commit and verify its remote contents when authorized.

### Out of Scope
No deployment, real LLM requests, main-branch updates, merges, or unrelated changes. The user approved a new pull request; merge and deployment remain out of scope.

### Plan Review
Reviewed against the three reproduced findings and current main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274. Server limits remain unchanged; frontend display history remains complete. Allowlist policy is the sole developer authority. Only supported credential names are added to the existing scanner.


### Verification Review
- Full frontend Vitest: 71 files, 419 tests passed.
- Frontend TypeScript and production build passed.
- Asset scanner: 14 focused pytest cases passed, including four formerly missed LLM-key leak cases and redacted output.
- Revocation: eight real-session cases passed in an isolated real-auth/middleware harness; the original source failed the two `test` username unset/empty allowlist cases. Thirteen existing password/credential/token tests also passed in isolation.
- Scoped Python Ruff and compileall passed. Independent review found no blocking issue.
- Local Python is 3.12 and the backend checkout is partial; full backend pytest, generated-rule parity, and manifest checks require hosted CI on the published commit. Component handler tests use mocked React hooks; no browser interaction coverage is claimed.
- Original main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274 was rechecked before branch creation; its backend and frontend CI passed. Exact new-commit hosted CI remains pending at publication.

## Task: Fix compatible health cache probes

### Goal
Return truthful health readiness while the running API owns a writable load-only cache connection, without mutating the cache or disturbing that connection.

### Subtasks
- [x] Verify current main source, repository instructions, existing health contract, and the DuckDB mixed-configuration failure.
- [x] Add regressions for existing writable and verified read-only runtime connections, missing caches, non-mutating fallback probes, and probe cleanup.
- [x] Reuse an existing runtime cursor only for the same database; otherwise open an independent read-only probe without initializing runtime state.
- [x] Run RED/GREEN regressions, focused lint and compilation, and independent review.
- [ ] Check base CI, publish one atomic commit on a new branch, open a draft pull request, and verify exact-commit hosted CI.

### Out of Scope
No merge, deployment, production database access, schema migration, cache build, or Wave A rule/activation changes.

### Plan Review
Reviewed against current main 05aba8152087cf049cebcd70ce1629e03ca94649 and the authorized health fix. Preserve the HTTP readiness and detail-access contracts. The probe executes SELECTs only, never calls get_cache_con/get_cache_reader (which can initialize schema), closes only its owned cursor/connection, and does not create a missing database. Success requires active-build health to pass with both runtime access modes while failure paths remain 503 and leave the runtime connection usable.

### Verification Review
- The original probe failed the real load-only singleton regression and misreported an existing writable database with an empty pointer as unreachable (RED: 2 failed, 8 passed).
- The final focused connection suite passed 17/17 tests with DuckDB 1.5.6, including both runtime access modes, repeated and parallel probes, first-reader initialization serialization, missing/other database paths, no schema initialization, byte-identical read-only fallback, startup-not-ready, and owned-cursor cleanup on success/error.
- Scoped Ruff and Python compilation passed.
- Local execution uses Python 3.12 with a partial checkout and an isolated import harness that loads the exact health functions, runtime, storage connection and schema modules. Full application imports, HTTP health tests, Python 3.13, and the full backend/Frontend suite are reserved for hosted CI on the published commit.
- Base main 05aba8152087cf049cebcd70ce1629e03ca94649 has passing backend and frontend checks. No production state was changed.

- Independent review reran all 17 focused regressions successfully and found no remaining blocking issue. The initialization-race case exercises real runtime initialization while the fallback probe holds the cache lock.

## Task: Fix secondary procedure payable bases

### Goal
Apply each procedure occurrence's session factor to its own whole-line payable, add regression coverage, and publish a draft PR with verified CI.

### Subtasks
- [x] Verify current main, repository instructions, pricing semantics, and downstream callers.
- [x] Add failing synthetic regressions for unequal line amounts, duplicate normalized codes, package memberships, quantities, exclusions, fallback amounts, and rounding.
- [x] Replace primary-derived amounts with own-line amounts while preserving occurrence alignment and existing blood caps.
- [x] Run focused regression and integration tests, repository quality gates where available, and independent review.
- [x] Reconcile the two F011 synthetic golden expectations exposed by hosted CI with exact own-line arithmetic.
- [ ] Check base CI, publish an atomic commit on a new branch, open a draft PR, and verify remote commit and hosted CI.

### Out of Scope
No merge, deployment, production records, blood/session overlap arbitration, blood applicability changes, historical catalog ranking fixes, or Wave A changes.

### Plan Review
Reviewed against main 45f97a64385c7b1959c44125b949f2d2e3e1e90b and the authorized standalone secondary-pricing fix. Preserve expected-payable/billed fallback, whole-line quantity semantics, exclusion filters, session grouping, final-total rounding, and existing blood caps. Use source-order factors without normalized-code collisions, retaining the factor-1 fallback for empty/invalid codes. Success includes 1000 + 100 at 30% = 1030, conservation for discount-only factors, and correct downstream DRG/strategy comparisons. Tests use synthetic records and explicit catalog fixtures.

### Verification Review
- RED: the original implementation failed 31 of 35 focused amount/occurrence cases. GREEN: the final focused selection passed 99 tests across session factors, amounts, specialties, DRG uplift, strategy, care-setting review, unbundling, and session uplift. Four existing tests requiring missing dental/synthetic assets were deselected from this focused run.
- New strategy and DRG regressions exercise the real session calculation: a 1100 package produces no false uplift, while a 1000 package produces exactly 30. The payment-compliance exclusion fixture keeps its real eligibility checks and now asserts the correct own-line total, 1885.96, with deterministic catalog ranking.
- Full source/script Ruff, changed-test Ruff, and changed-file Python compilation passed. Independent review reran the 60-case core suite and found no blocking source issue.
- Local verification uses Python 3.12 and a partial source/data checkout. Full pytest was attempted but stopped at collection on missing manifests/raw source assets and a missing requests dependency. Generated-rule checking also requires the absent manifests; manifest parity scanned zero files, so it is not counted as a pass. Complete Python 3.13 backend tests, generated-artifact/parity checks, and frontend gates remain for hosted CI on the published commit.
- Base main 45f97a64385c7b1959c44125b949f2d2e3e1e90b was rechecked with successful backend and frontend checks before publication. No production state was changed.
- First hosted run on 8567ee5: frontend passed all 419 tests and all frontend gates; backend passed 4290 tests with two stale F011 golden failures. SHA-verified synthetic rows and independent review confirm primary 600160 has payable 1800 and secondary 600150 has payable 2200 at 25%, giving itemized 2350 and package-9000 uplift 6650. Updated only the exact vignette/action expectations, added explicit itemized/package assertions, and retained existing tolerances. Five registry/lookup tests and Ruff/compilation passed; the complete hosted rerun remains pending for the follow-up commit.

## Task: Reconcile blood and session uplift

### Goal
Compute one recoverable gap per shared blood/session procedure line using the existing minimum-ceiling composition, then publish a separate draft PR with verified hosted CI.

### Subtasks
- [x] Verify current main after PR111, repository instructions, detector/report consumers, and encoded ceiling composition.
- [x] Add failing direct and report regressions for overlap, no-gap constraints, review-only amounts, identities, ordering, and partial overlap.
- [x] Share the session secondary assessment, cap its blood-line ceiling, and exclude its exact line identities from the independent blood detector.
- [x] Run focused tests, repository quality gates where available, and independent review.
- [ ] Check base CI, publish an atomic scoped commit, open a draft PR, and monitor hosted CI to completion.

### Out of Scope
No merge, deployment, production records, blood-rule package applicability changes, patient-history fixes, historical catalog ranking changes, or Wave A changes.

### Plan Review
Reviewed against main 09749e23f8ba6907f7addca8c7fddea8b66f8475 and the authorized F02 roadmap. Independent review agrees that matching opportunities must compose actual monetary ceilings with min, consistent with the existing session-adjusted payable calculation. A shared secondary-line assessment must cover lines without positive session gaps; ownership remains in the session block so DRG/add-on de-duplication consumes reconciled amounts. Keep the existing clinical-review restriction even when a blood cap reduces a review gap below its heuristic threshold. Never identify opportunities by code alone. Preserve independent lines and blood-only sessions, inputs, rounding, and existing package applicability. Python 3.12/partial data are available locally; hosted CI provides the full Python 3.13 and frontend gates.


### Verification Review
- Reproduced on merged main 09749e2: plasma billed 200 with session ceiling 340.41 and blood ceiling 408.50 emitted 140.41 + 208.50 = 348.91. The reconciled session-owned gap is 140.41; billed plus uplift is 340.41.
- RED: 15 of the first 17 new regressions failed before the fix. GREEN: all 26 final regressions pass, including the actual report assembler, DRG/add-on input boundaries, recommended actions, API serialization, live/cached recovery summaries, and cohort totals for confirmed and review-only cases.
- The broader focused selection passes 135 tests; two existing tests requiring absent synthetic claim tables are explicitly deselected. Source/script Ruff, changed-test Ruff, changed-file compilation, and diff whitespace checks pass.
- Independent review found no blocking issue and passed 104 focused cases plus 1,440 synthetic parameter combinations across amounts, quantities, fractions, incision/specialty settings, and ordering.
- Local Python is 3.12 with a partial source/data checkout. Full pytest was attempted and stopped on nine collection errors from missing manifests/raw source assets and requests. Generated-rule checking reports absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. The complete Python 3.13 backend, generated-artifact/parity, and frontend gates remain for hosted CI.
- Base main 09749e2 has successful backend and frontend checks. No production state, rule JSON, or unrelated task was changed.
- First hosted run on 98a296c passed 4316 backend tests and all frontend gates, with two scoped failures: the new ceiling evidence fields were absent from the frozen public DTO, and the blood demo still expected the duplicate confirmed 310 TRY. Added only those two scalar DTO fields with patient/bill public-projection assertions that retain private-field filtering. SHA-verified synthetic claim 0004 has blood list/payable 1000, billed 50, and primary P611720 billed 101019.30: min(300,360)-50 = 250, retaining the existing clinical-review restriction. Updated the demo to pin those exact amounts, identity, and zero confirmed blood uplift. The 26 regressions plus the actual 0004 test pass locally; hosted rerun remains the final gate.

## Task: Preserve bill-scoped claim history

### Goal
Restore known same-patient evidence for existing dated rules while keeping every bill's monetary lines and emitted findings limited to that bill, based on verified main 0e40e09f.

### Subtasks
- [x] Reproduce MIAT and ICU failures on verified main and add failing regression tests
- [x] Retain separate historical claim/procedure/material rows when slicing a bill, preserving active-row semantics and rejecting foreign or orphan history
- [x] Route MIAT, ICU overlap, duplicate exam/test and SCT temporal checks through history with their existing per-event date boundaries; scope results to active rows
- [x] Cover boundary dates, future/foreign evidence, repeated slicing, patient behavior, report/cohort additivity, public projection and cache serialization
- [x] Run focused suites, full pytest, lint and artifact checks; disclose environmental gaps
- [ ] Obtain independent diff review, verify main and prior CI, publish a separate draft PR, then monitor and fix scoped CI failures until terminal

### Out of Scope
Other audit findings; new rules or changes to rule constants and authored authority; broad Wave A work; real patient data; access/authentication changes; merge/deploy

### Plan Review
Independent reviewer confirmed the separate history design and the known consumers. History views must replace any retained active-claim rows with current active rows so repeated slicing and dataclass replacements cannot resurrect stale inputs. Duplicate detectors must see prerequisite history before filtering emitted target rows; focused projection must validate historic evidence without broadening source ownership. ICU report/audit rows, MIAT legacy/prose and SCT checks keep their existing dated predicates. Existing unavailable treatment-course/prior-therapy metadata remains unchanged. Success: ICU service bed 3→2 days, MIAT warning restored, unchanged current-bill billed totals and no future/foreign-triggered findings. Local partial checkout limitations will be distinguished from complete hosted CI.

### Verification Review
- RED on verified main 0e40e09f: all five new direct regressions failed (MIAT, ICU bed reconciliation, duplicate exams, duplicate tests, and SCT prior-transplant eligibility). GREEN: all 39 expanded regressions pass, covering date-window boundaries, unknown/future dates, ownership, active-row replacement, repeated slicing, and source-order ties.
- Real report/cohort runs cover single-worker and threaded bill calculations, current-bill money, per-patient additivity, another patient's isolation, focused evidence ownership, public projection, and a DuckDB bill-row round trip. The public DTO adds only ICU overlap day/date evidence and MIAT claim/section/package-code attribution; unknown/private fields still filter out.
- Independent review passed 132 focused tests and 960 bill slices over 240 seeded input orderings, comparing MIAT/ICU/exam/test/SCT results with the same bill's full-patient findings. A same-day SCT tie-order regression caught during review was fixed with identity-preserving history overlays and permutation regressions.
- The combined local focused selection passes 234 tests, including the actual 50-patient/per-bill synthetic report suite, existing public access/probe tests, and deterministic surfacing inventory. Source/script and changed-test Ruff pass.
- Full pytest was attempted on the local Python 3.12 partial checkout and stops at nine collection errors from missing manifests/raw source data and the requests dependency. Generated-rule checking requires absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. Complete Python 3.13 backend, frontend and artifact/parity gates remain for hosted CI.
- Main 0e40e09f was rechecked immediately before publication: backend, frontend and release-hold checks are successful. No rule constants, source authority, broad rule expansion, access controls, production data, merge or deployment are changed.
- First hosted CI395 on db322e6 passed 4356 backend tests and all frontend gates. Its sole failure was an existing deployment-verifier test explicitly asserting that cross-claim ICU evidence disappears from a bill. Updated that test to require exact ICU evidence parity with the service claim's patient finding while asserting service-only claim inventory and evaluation scope. No runtime code changed. The deployment/cache/history selection passes 61 tests locally; full hosted rerun remains the final gate.


---

## Task: Simplify single-VPS Wave A releases

### Goal
Provide one prepare/status/activate/rollback release interface with version-aware current-cache verification, exact final-artifact attestation and coherent paired recovery on ports 8001/3000.

### Subtasks
- [x] Verify source against main 3f5540cf and read repository instructions and prior tested rollout helpers.
- [x] Bound changes to release tooling, versioned activation integration and focused fault-injection/regression tests.
- [x] Implement original-five and strict current full-v2 baseline comparison across all persisted report/evidence rows without rewriting inputs.
- [x] Confirm and implement the paired-release state machine, preserving current history/mutable state and attesting actual final serving bytes.
- [x] Add operator prepare/status/activate/rollback interface and concise migration/runbook documentation.
- [x] Add explicit opt-in preparation snapshot maintenance for the initial writable load-only deployment; default refuses unsupported online snapshots before stopping services, and durable recovery restores the unchanged old pair before builds.
- [x] Independently verify baseline and candidate build-config environments against their stored hashes, preserving exact historical metadata.
- [x] Build the preparation bundle from explicit machine/input paths: consistent serving snapshot and retained baseline roster, fresh detached target/frontend, traced cache and all verification/rehearsal/signing gates; test fail-closed ordering, default no-mutation snapshot rejection and explicit recoverable snapshot-maintenance integration.
- [x] Verify rollback for failures around both service stops/restarts, database/source/frontend switches, interruption and retry; preserve all historical/mutable state.
- [ ] Obtain independent review and resolve substantive findings.
- [ ] Run applicable local checks, publish only changed blobs on a new draft PR, then verify full hosted CI at the exact final head.

### Out of Scope
Merging or deploying, user-computer/VPS operations, production credential/security/network configuration changes, broad runtime or billing redesign, historical crash attribution, data pruning, and unrelated cleanup.

### Review
User approved this PR. Work uses the authorized GitHub connector and isolated cloud workspace because the declined local task will not be retried. Source inventory is partial only for unavailable data/binary assets, so publication must derive from the verified complete remote base tree and include changed files only. Current-baseline design is confirmed: version comes from complete persisted evidence/report contracts, not API feature visibility or unchanged build_meta schema; original-five migration remains supported; current full-v2 comparisons validate both sides and normalize only independently bound identity fields. The paired transaction design must explicitly bind the final serving database; changing bytes after signing or weakening hashes is prohibited. No production command is executed during implementation.

Snapshot design decision: the current ordinary load-only service owns a writable DuckDB connection. Do not claim an undocumented hot-copy snapshot. The authorized PR includes explicit opt-in snapshot maintenance with warnings, shared locking, durable recovery and interruption tests; actual VPS execution remains out of scope. Later read-only online snapshot support requires tested reader-lock semantics.

## Task: Date-aware SUT drug amendments

### Goal
Select source-verified amendments by the actual drug service date, preserve older rule behavior and disclose missing temporal or clinical evidence.

### Subtasks
- [x] Verify current-main blobs and baseline focused tests.
- [x] Review plan and official October amendment evidence with coordinator.
- [ ] Add a versioned, source-pinned amendment catalog and strict date resolver.
- [ ] Integrate affected drug evaluation with explicit unresolved clinical gates.
- [ ] Propagate optional drug service dates through dict adapters and typed evidence.
- [ ] Add boundary, historical, unknown-date, source and no-false-compliance tests.
- [ ] Run focused and aggregate tests, lint and independently review selected-file overlay.

### Out of Scope
No merge, deployment, VPS access, invented clinical criteria, blanket source dates or claims that historical lower bounds are verified. Other SUT groups remain separate workstreams.

### Verified implementation contract
The service date is optional `drug_context.service_date`, mapped to the actual drug line, never the server date. Date-aware selection uses half-open validity intervals and fails closed on absent, invalid, overlapping or unsupported versions. The three explicitly annotated October 10 successor clauses are source-backed partial evaluations, not complete eligibility decisions. Legacy clinical checks may still run before that boundary, with an explicit unverified historical-version review. Thiotepa stays quarantined; no active amendment is inferred from consolidation. Temporal records do not inflate encoded-rule coverage. Public evidence is bounded and allowlisted, with source IDs/dates/hashes but no raw rule payload. Stream B owns the form/type; this stream owns backend contracts and domain tests.
## Task: 4 Ekim 2026 sınırlı klinik kaynak incelemesi

### Goal
Resmî pozitif kanıt varsa yalnız desteklenen klinik inceleme gününü eklemek; kanıt yetersizse 4 Ekim inceleme gerekliliğini koruyan, kaynak ve yürürlük sınırları doğrulanmış dar sonuç teslim etmek.

### Subtasks
- [x] Ana dizüstü kirli dosyalarını koru; 499dff4 tabanında bağımsız worktree oluştur ve repo talimatlarını oku.
- [x] 4 Ekim SGK ilan dizini, Resmî Gazete günlük içerik ve mükerrer göstergesini canlı resmî kaynaklardan gözle.
- [x] PR128 49af201 başındaki 10 Ekim ilaç / 2 Kasım organ nakli sınırlarını resmî belgeyle eşleştir.
- [x] Kanıt ve ortak dosya sahipliğini üst göreve bildir; clinical_versions.json sahipliği çözülmeden yazma. Üst görev tek yazarlığı 4 Ekim'de açıkça verdi; corpus sahibi patch aktaracak.
- [x] Yeterli kanıt halinde yeni gözlem/makbuz ve tek günlük pencereyi ekle; yetersizse salt inceleme kanıtını ve açık engeli kaydet.
- [x] Tarihsel boşluk, hukuki alt sınır, klinik kapsam, ertesi gün ve tahrif edilmiş kanıt kontrollerini hedefli çalıştır.
- [x] Bağımsız inceleme yaptır; doğrulanmış dar sonucu ve kalan engelleri Türkçe teslim et.

- [x] Yeni pencere eklendiğinde geçmiş continuity günü kendi makbuz kimliğini korusun; dar provenance düzeltmesini regresyonla doğrula.

### Out of Scope
Corpus/parquet yenilemesi, genel mimari, tam tıbbi ödeme uygunluğu, merge, VPS ve deploy.

### Specification and plan review
Kullanıcının devredilen talimatı kapsamı ve küçük taslak PR akışını onaylıyor. Yeni hukuki tarih veya hash çıkarımı yapılmayacak. 12 mevcut aile, Python kaynak otoritesi kataloğu ve hedefli pytest katmanı kullanılacak. Başarı: yalnız gözlenen gün için pozitif resmî kanıt veya dürüst kapalı sonuç; tarihi boşlukları doldurmayan ve clinical_eligibility_complete=false sonucunu koruyan doğrulama. Ortak dosya yazımı üst görevin sahiplik paylaşımına bağlı.

### Progress evidence
Baseline gerçekten çalıştırıldı: `/home/safa/Documents/Bilun/.venv/bin/python -m pytest tests/unit/domain/prose_rules/test_clinical_source_authority.py -q`: 100 passed (2.70s). Aynı runtime ile `scripts/sut/verify_clinical_source_authority.py --check`: 12 aile, 17 yerel asset, through 2026-10-03, exit 0. Yarım fetch commit nesnesi kontrol edildi: 49af201 mevcut. Geçici transport kesintisinde belirsiz yazım tekrarlanmadı; tek yazım bu plan.

New-window implementation review: Yeni pozitif 4 Ekim kanıtı aynı gün ve dört gerekli kategori için dondurulduktan sonra ayrı tek günlük pencere eklenecek. İncelemede mevcut resolver'ın geçmiş continuity gününe son makbuz metadata'sını atadığı görüldü; yalnız eşleşen continuity penceresinin makbuz kimliğini koruyan dar düzeltme kapsamda. Bu, evaluator değişikliği veya yeni mimari değil.

Frozen source result: 4 Ekim RG normal sayı 33390 günlük içerik, current homepage/Son Mükerrer göstergesi (6 Eylül), SGK GSS yeni SUT ilanları (2 Ekim) ve 3 Ekim ayrı ilaç geri ödeme yönetmeliği aynı gün 18:16:11 UTC'de başarılı HTTP200 gözlemlerle donduruldu. Canlı SGK değişiklik DOCX SHA a717ac7e9e932449461c353fcb3d3845ed834d104f35a75505c53185bbcfccbb ve konsolide DOCX SHA227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573 önceki proof ile bayt düzeyinde aynı. Yeni strict makbuz sgk-rg-clinical-2026-10-04T182213Z: 12 aile, 5 gözlem/4 tür, aynı İstanbul günü, tüm capture ve raw-byte hash kontrolleri exit0. Kanıt bütünlüğü ve resmî dijital imza farklıdır; birlikte yeniden yazılıp pinlenen tüm veriyi runtime bağımsız resmî doğruluk diye onaylamaz.

Commencement result: Resmî SGK konsolide body/w:p indeks1096 organ 02/11/2026;5572/5579/6056 ff/gg/aaaa ilaç10/10/2026. Takvim hesabıyla tarih üretilmedi. Gerçek ilaç temporal suite34 passed; helper suite2 passed; üç ilaç×09/10/11Ekim/None=12 doğrudan assertion geçti. Organ tarih alan runtime selector bulunmadı; PR128 yeni GateB(4)/(5) çıplak koordinatları eski transfer/donör anlamlarıyla çarpışabilir. Bu veri uyumluluğu görevinin açık inceleme konusu, bu kaynak PR'ı çözmez.

### Review
Son dokuz dosyalık hedefli paket, kaynak/HTTP/evaluator/observation testleri ve ilaç temporal testleriyle gerçekten çalıştı: **538 passed, 3 warnings, 17.82s**. Normal sandbox'ta TestClient/AnyIO portal askısı görüldü; izin incelemesinden geçen minimal in-process client 0.34s'de geçti ve aynı tam paket onaylanan ortamda exit0 tamamlandı. Gerçek server/port veya VPS kullanılmadı. Scoped Ruff ve `git diff --check` exit0. Final verifier:12 aile/25 repo-local asset/through2026-10-04, clinical_eligibility_complete=false; `/tmp/bilun-source-authority-assets-20261004.json`.

Bağımsız final diff incelemesinde P1/P2 bulgu yok. Eski katalog tüm alanları/pencereleri korunmuş; yalnız12 tek günlük pencere ve bir makbuz eklenmiş. Bağımsız36 gerçek3/4/5Ekim tarih kontrolü ve final8proof hash kontrolü geçti; ayrı HTTP dışı hedefli koşu394passed39deselected. İncelemecinin yarım HTTP koşusu exit130 ile durduruldu, pass sayılmadı. Kaynak sahibi full HTTP538pass sonucunu yukarıda ayrı doğruladı.

Yayın sırası: Bu kaynak yenilemesi mevcut9639c457 corpus üzerinde bağımsız dar taslak PR olacak. Corpus sahibinin gerçek veri geçişi+catalog seam paketi bunun üstüne ikinci taslak PR olarak taşınacak; ilk kaynak PR'ında corpus veya binding değişikliği yok. Merge/deploy yok.

## Task: PR150 kaynak CI onarımı

### Goal
Mevcut c4f736b kaynak ağacındaki üç doğrulanmış CI hatasını yalnız desteklenmeyen gün fixture'ı ve türetilmiş coverage kanıt hashleriyle düzeltmek; corpus ve dört coverage parquet dosyasını byte düzeyinde korumak.

### Subtasks
- [x] future_source SMA/antifungal fixture'ını ilk desteklenmeyen 5 Ekim'e taşı; not_evaluated ve sıfır predicate beklentilerini koru.
- [x] Mevcut coverage generator'ını geçici dizine çalıştır; dört özgün parquet dosyasının Git HEAD byte eşitliğini ve geçici çıktıyla tam schema/frame eşitliğini doğrula, yalnız mevcut helper'larla sut_coverage_evidence.json dosyasını yenile.
- [x] Coverage evidence ve documentary facts testlerini, anlamlı kaynak paketini, compile_rules.py --check ve 23 manifest parity kapısını çalıştır.
- [x] Değişen dosyaların dar kapsamını, corpus/parquet hashlerinin korunduğunu ve gerçek test sonuçlarını üst göreve teslim et.
- [x] Üst görevin açık yetkisiyle kaynak pencere uzatması, future fixture ve coverage hash kapanışı için kısa önleyici ders kaydı ekle.

### Out of Scope
Corpus geçişi, diğer branch dosyaları, runtime klinik veya tarih penceresi değişiklikleri, frontend kodu, commit/push/merge/deploy. Git işlemleri üst görevin sorumluluğunda.

### Specification and plan review
Üst görev üç hatanın düzeltmesini açıkça yetkilendirdi. DAY+2=4 Ekim artık geçerli kaynak günüdür; ilk desteklenmeyen gün 5 Ekim'dir. Kanıt yenilemesi yalnız dört kalıcı parquet dosyasının Git HEAD ile byte eşitliği ve generator çıktısıyla tam schema/frame eşitliği doğrulandığında uygulanacak; input corpus SHA256 9639c4578223ff46a40499270af5043d229ab2a1a1c3783114b43b64787384ac korunacak. Kaynak kapsamı sekiz yeni 4 Ekim gözlem/makbuz dosyasıyla kapalıdır. Plan uygulamadan önce mevcut generator ve CI komutlarıyla doğrulandı.

Plan refinement before evidence write: Geçici generator Arrow24.0.0 kullanıyor, kayıtlı parquet writer Arrow25.0.1; schema ve frame eşit olsa da serileştirilmiş byte farklı. Bu ayrım üst göreve bildirildi ve yalnız evidence yenilemesi açıkça yeniden yetkilendirildi. Dört özgün parquet ve input corpus Git HEAD ile byte düzeyinde aynı doğrulandı; evidence mevcut build_drug_coverage_evidence helper'ına özgün kalıcı coverage frame verilerek ve coverage_dependency_hashes helper'ıyla gerçek repo dosyaları hashlenerek oluşturuldu. Geçici parquet dosyalarının hiçbiri repo'ya yazılmadı.

### Review
Tek birleşik 11 dosyalık kaynak/ilaç temporal/documentary/coverage paketi gerçekten çalıştı: **721 passed, 2 warnings, 36.17s**. Normal sandbox'taki önceki documentary-only HTTP koşusu asılı kaldığı için exit130 ile durduruldu ve pass sayılmadı; birleşik koşu izin incelemesinden geçen süreç içi TestClient ortamında exit0 tamamlandı. Full backend suite yeniden çalıştırılmadı.

`compile_rules.py --check`: **134 rule/manifest artifacts byte-identical**, exit0. `audit_manifest_parity.py --drug-only`: **23 scanned, 23 with traces, 0 issues**, exit0. Kaynak verifier: **12 families, 25 repository-local assets, through2026-10-04**, exit0. Scoped Ruff ve git diff --check geçti. Dört kalıcı coverage parquet ve 9639 corpus Git HEAD byte hashleriyle aynı; JSON envanteri file_sha256 dışında değişmedi. Kaynak/test/evidence düzeltmesi ve görev/ders belgeleri dışında yazım yok; commit/push üst göreve bırakıldı.

Frontend job111504177367 yalnız bir kez individual rerun edildi; aynı c4f736b kaynak başını kullanan job111510110080'de **83 files/575 tests, typecheck, build, public-assets52files** geçti. Backend yeniden çalıştırılmadı; ilk run'ın başarısız backend sonucu tam CI başarısı sayılmaz. Bağımsız final kaynak diff incelemesi üst görev tarafından atandı.


## Task: PR128 corpus'unu kaynak PR'ı üstünde mekanik doğrulamayla taşı

### Consumer scope update and ownership — 2026-10-04
Üst görev, konumsal consumer uyumluluğunu mevcut veri uyumluluğu kapsamına açıkça aldı: eski coverage ile yeni corpus arasında toplam 4.177 key/4.174 hash uyumsuzluğu ve 36 manifestte 3.066 farklı kayda kayan C* atfı doğrulandı. Provisional dosyalar nihai diye kopyalanmaz. Aşağıdaki gerekli bağımlılıklar önceki beş dosyalık başlangıç kapsamını tamamlar; genel mimari ve klinik tarih/sınır/predicate değişiklikleri eklenmez.

- [x] authority_audit: aynı metnin bent/prose kaymasını mevcut canonical override ile düzelt; compiler ve gerekli manifest/rule çıktılarını mevcut üreticilerle yenile. Tam metin/parent/context değişen atıfları otomatik taşıma; kesin engeli raporla.
- [x] corpus_seam_review: nihai manifest/rule/catalog/source-authority kapanışından mevcut build_sut_coverage.py ile sut_clause_coverage.parquet, sut_coverage_by_rule.parquet, sut_coverage_by_section.parquet, sut_registry_coverage.parquet ve sut_coverage_evidence.json dosyalarını yeniden üret; gerçek consumer ID/key/fullhash ve negatif eski artifact testlerini doğrula.
- [x] independent_review: gerçek corpus40b2 ile hazır local-hash-v1/512 embedding dosyasının 4.090 ID/body/vector eşitliğini bağımsız doğrula ve exact dosyayı kur; 14 retrieval testi ve sıcak indeks kontrolünü çalıştır. Runtime mimarisini genişletme.
- [x] root: kaynak PR'ın bağımsız coverage_evidence pin kapanışını doğrula, gerekiyorsa kaynak corpus'u değiştirmeyen dar evidence düzeltmesini ayrı tut; ortak plan/katalog ve son Git yayını sahipliğini koru.
- [ ] Nihai source/migration/consumer testleri, scoped Ruff, compile --check, manifest parity, evidence closure ve bağımsız inceleme sonucundan sonra ikinci draft PR/full CI durumunu kaydet.

Coverage üretimi diğer girdi sahiplerinin FINALmanifestready sinyaline kadar bekler. Kaynak PR bağımsızdır; merge/deploy/VPS yapılmaz. Mevcut görevde Git yayını yalnız root tarafından yapılır.

### Existing consumer gates — scope confirmed for the night run
Üst görev mevcut veri uyumluluğu kod/test/inceleme/CI akışını tekrar onay almadan tamamlamayı onayladı. Negatif gerçek tüketici kanıtı organ kaynaklarının yalnız pending metadata ile korunmadığını, kaldırılan Carmustine guard-rule'ın ise mevcut correction kapısını atladığını gösterdi. Gerekli düzeltme mevcut iki tüketicinin dar kaynak kapısındadır; yeni klinik aile, genel admission mimarisi, tarih penceresi veya tıbbi predicate eklenmez.

- [x] boundary_audit: treatment_pricing mevcut legacy ve typed tüketicisinde explicit source_review_required durumunu predicate/ödeme sonucu öncesinde tarafsız review çıktısına taşı; kaynak inceleme flag'i olmayan kuralları koru, negatif ve normal tüketici regresyonlarını çalıştır.
- [x] authority_audit: organ kaynak locators/pending marker/policy digest verisini mevcut kapı sözleşmesiyle koordine et; değişen criteria'yı encoded sayma. İlaç correction guard'ının kaldırılmış geçersiz cite-rule'a bağlı olmadan source_target_mismatch davranışını korumasını mevcut temporal seam'de doğrula/düzelt.
- [x] authority_audit: deferral kaynak geçmişiyle kanıtlanan kayıtları mevcut canonical/ID sözleşmesiyle taşı; aynı key'deki farklı body/context veya çelişen judgment'ı otomatik medikal sınıfa atama, belirsiz kalanları açık raporla.
- [x] authority_audit: değişmeyen 2.4.1.(1) dental tam metin/context'i resmî October2 DOCX ile doğrula; mevcut dental_source_proof içinde yalnız gözlenen October2 snapshot sürümünü destekle ve ilgili mevcut policy digestini yenile. Hizmet tarihi/attestation alt sınırlarını, kaynak body hash'ini ve parasal davranışı değiştirme; unsupported snapshot/değişmiş body negatiflerini koru.

### Changed-source compiler contract — reviewed before implementation

Yalnız mevcut treatment_pricing_2_4 ailesinin üç değişmiş kaynak kaydı source_review_required=true, pending verification ve boş gate_b_sources ile derlenecek; tarihsel atıflar inert açıklama/makbuzda korunacak. İki mevcut consumer flag'i predicate öncesi tarafsız review olarak ele alır. Guard'ı olmayan ailelerde review-only marker kabul edilmez; normal encoded atıfların active/fullkey/heading kuralları gevşetilmez. İki değişmiş ff/gg kaydı ve bir yanlış hedefli Carmustine executable kaydı kaldırılırken mevcut temporal correction review davranışı korunur. Bu veri/derleyici sınırına pozitif/negatif test ve bağımsız inceleme gerekir.

Kaynak PR150 exact head58a73b117e71d9610d7e51cf854c3a23aba4fd7b tam CI476 başarılı:8069 backend/575 frontend,134 byte-identical artifacts,23 manifest/0issue. Corpus çalışma ağacı bu head'e ff edilmiş, başlangıç mekanik makbuzunun c4f736be baseline kanıtı değişmemiştir.

### Goal
Kaynak PR c4f736be tabanından PR128 corpus40b2 geçişini aynı klinik tarih ve binding sözleşmesiyle doğrulayıp ikinci dar PR için incelemeye hazır dosya paketi teslim etmek.

### Subtasks
- [x] Temiz corpus-transition worktree tabanı c4f736be ve 17f3694c kod/test kapsamını doğrula; mevcut repo talimatlarını oku.
- [x] Yalnız 17f3694c içindeki beş verifier/diff/test dosyasını ve iki clause-delta açıklama düzeltmesini taşı.
- [x] Gerçek PR128 candidate corpus ve tek atıf yapılan October2 DOCX baytlarını/hash'lerini doğrula; gerekli dosyaları seçerek hazırla.
- [x] Henüz değişmemiş c4f736be baseline katalog/corpus'u üzerinde yeni mechanical migration receipt üret; eski owner receipt'ini kopyalama.
- [x] Gerçek candidate corpus'u kur, katalogda yalnız corpus pinini ve Oct4 review evidence'e yeni receipt pinini ekle; tüm aile/pencere/hukuk/source alanlarını aynen koru.
- [x] Migration verifier/testleri ve kaynak PR'ın 538 hedefli testini onaylanan in-process ortamda gerçekten çalıştır; asset closure ve diff kontrollerini kaydet.
- [x] Exact CI generated gate engelini mevcut dar override/dependency yüzeyinde incele; önerilen ek dosya kapsamını yazmadan önce üst göreve bildir.
- [x] Aynı fulltext ve literal b) Word maddesi kanıtıyla mevcut YAML'da yalnız 4.2.8.A.b#2882a47a türünü bent olarak sabitle; başka key/opaque ID'ye taşınmadığını test et ve generated gate'i yeniden çalıştır.
- [x] Son dosya listesini, gerçek test sonuçlarını ve kalan engelleri üst göreve teslim et; bağımsız incelemeyi bekle.

### Out of Scope
Merge, deploy, VPS, commit/push, PR yayınlama; owner/parent repo yazımı; ingest_state, genel manifest/annex ve tüm442 PR asset'inin taşınması; klinik tarih, hukukî sınır, binding, schema/runtime değişiklikleri ve yeni ödeme uygunluğu iddiası.

### Specification and plan review
Üst görev iki PR sırasını ve bu dar implement paketini açıkça onayladı. Hedef Python3.13 mevcut Bilun .venv'dir. Başarı: c4f736be baseline ile gerçek PR128 Git blobu arasında72 unique binding/8 proof dosyası/12 aile bağlam uyumu; actual installed corpus40b2 ve yeniden üretilmiş makbuzla verifier/test geçişi;5Ekim fail-closed ve source PR continuity receipt fix'i aynen kalır. Plan kapsamı delegated talimatla eşleştirilerek implement öncesi gözden geçirildi.

### Progress evidence
Narrow dependency plan reviewed before write: Üst görev mevcut canonical YAML override desteği ile tek tür düzeltmesini gerekli corpus dependency olarak onayladı. Eski C004159 ve yeni C004167 için full normalized text SHA256 `2882a47a74ff4d7ab0194f6eb1ed4a2aeef8653bd3e370268280d125cc395d24`, coordinate4.2.8.A.b,section4.2.8.A,parent4.2.8,letterb,in_force ve non-heading aynıdır. Git DOCX direct body w:p indeksleri4377/4385 literal `b)` ile başlar ve full normalize edilmiş Word metni corpus'a birebir eşittir. Öneri yalnız `data/gazette/clause_type_overrides.yaml` canonical key→bent ve `tests/unit/scripts/test_stable_clause_type_overrides.py` persistent regression guard'dır; corpus, runtime/schema/strict encode şartı veya generated çıktı değiştirilmez. Kesin dosya/kanıt üst göreve yazmadan önce bildirildi.

Fresh receipt `corpus_migration_pr128.json` c4f736be kaynak baseline'ından gerçek49af2019 candidate Git blobu ile yeniden üretildi:12 aile/8 binding dosyası/72 unique binding; SHA256 `3c7f781b8e223adc6073e69b1dff4af7b5b0e7cb106814a1ca016dde8b3c5bde`. Kurulu corpus gerçek40b2,8413 satır,1421343 bayt. Katalogu yalnız corpus pinini ve Oct4 makbuz evidence satırını geri alarak karşılaştıran assertion tüm eski alanların birebir korunduğunu doğruladı; source_authority.py c4f736be ile bayt düzeyinde aynı. Yalnız tek October2 DOCX taşındı; ingest_state, annexler ve genel manifestler değişmedi.

Son 12 dosyalık birleşik pytest koşusu onaylanan in-process ortamda gerçekten tamamlandı: **579 passed, 3 warnings, 28.54s**. `TESTING=1 BILUN_AUTH_OPTIONAL=1 BILUN_AUTH_USERNAME= BILUN_AUTH_PASSWORD= BILUN_SESSION_SECRET= PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, pytest `--confcutdir=tests/unit -p no:cacheprovider -o faulthandler_timeout=30` kullanıldı. İlk koşudaki tek hata renal testin eski opaque ID beklentisiydi; beklenti runtime collector'dan değil sabit6 canonical clause key ve kurulu corpus lookup'tan türetildi. Oct4 parity günü migration testlerine eklendi; Oct5 review_required kaldı. Scoped Ruff ve `git diff --check` exit0. Kaynak verifier `--check --json-output /tmp/bilun-corpus-transition-source-assets-20261004.json`:12 aile/26 asset/through2026-10-04, exit0.

Exact CI `scripts/sut/audit_manifest_parity.py --drug-only`:23 manifest/23 trace/0 issue, exit0. `scripts/sut/compile_rules.py --check`:exit1, `csv_wave_clause_ids_metabolic_mid` hedefinde `4.2.8.A.b#2882a47a` candidate C004167(prose) strict encode-eligible şartını karşılamıyor. Aynı metin/key eski corpus'ta C004159(bent); candidate raw Git blobu da prose. Compiler finally bloğu önceden var olan çıktıları geri yükledi; git durumunda generated artifact değişikliği yok. Engelin dar dependency teşhisi sürüyor, bu gate başarılı diye sayılmadı.

### Final producer dependency closure — 2026-10-04

Üst görev, gerekli consumer source guard, runtime/code ve Git/draft PR akışını yetkilendirdi. Başlangıç owner paketinin Out of Scope listesi bu sonraki yetkiyi kısıtlamaz. Genel mimari, yeni medikal predicate/eligibility, tarih uzatması, merge/deploy/VPS kapsam dışında kalır.

Yenilenmiş coverage engine-owned ID envanteri yedi mevcut GateB manifestinin çıktısını değiştirdi. Mevcut compiler WRITE 43 hedefte exit 0; CHECK 134 artifact için byte eşitliği ve drug parity 23/23, sıfır issue ile tamamlandı. Mevcut 939 kural JSON'u byte düzeyinde değişmedi. Eklenen 214 trace aynı baseline full body/parent/context kaynaklarına eşleşti: 80 encoded trace mevcut kural cite'lerinden, 134 deferred trace mevcut authored judgment'tan geldi. Dört trace, existing other-engine primary ownership filtresiyle export'tan çıktı; eski trace payload değişimi sıfır. Provisional/current envanter ile final in-memory normalized producer, yedi engine-owned ID kümesinde birebir aynı doğrulandı.

Consumer report SHA256 `e348650810218bed7e7c8eec18be7e4161d66feda859f8103fa51a4a2bec456d`; catalog SHA256 `07d86ce0a1a978683a72457abe9400a954b0b1e69e9e8ce94b8d308ae2e24471`. 457 fixed input ve 134 monitored output pini kapalıdır (128 mevcut, 6 açıkça absent). Yalnız Oct4 review içindeki mekanik report pini yenilendi; kaynak pencereleri, hukukî sınırlar, tarihsel boşluklar ve clinical_eligibility_complete=false korundu. Kaynak verifier 12 family/27 asset, through Oct4 ile exit 0.

Önceki birleşik author testi **1.662 passed, 3 warnings, 33.65s** ayrı aşamadır. Coverage üreticisinin mevcut authored normalizer çağrısı ve stable source catalog fixture paketi **101 passed, 1 warning, 6.41s** tamamlandı.

Son beş coverage dosyası existing CLI ile final girdilerden üretildi; **124 passed, 1 warning, 7.57s**. 150 dependency hash'i freeze öncesi/sonrası ve evidence içinde birebir aynı; source corpus 40b2 değişmedi. 4.781 aktif satırın immutable ID/key/full body/context alanları ve production-normalized 31 kaynak alanında sıfır uyuşmazlık var. Meşru duplicate-key ekstra 111 satırın multiplicity'si korundu. Root final coverage sonrası compiler --check (134 byte-identical), global Ruff src/scripts, git diff --check ve 58-parent catalog deep comparison exit 0. Yalnız corpus pini ve iki mekanik evidence kaydı geri alınınca katalog tamamen parent ile eşit: version/date/legal/history/receipt alanları değişmedi.

Final coverage evidence SHA256 `6a4d26407b1c3ad8d365a523912aaff5dc4b2002562b07fffef1ea150c4d3092`; diğer dört parquet hash'i bu dosyada gerçek dosya baytlarıyla kayıtlıdır. Bağımsız final test hükmü ve hosted full CI henüz bu kayıtta başarı sayılmadı.

### Independent final review

Tek bağımsız birleşik paket gerçekten **468 passed, 2 mevcut RefResolver warnings, 25.25s** tamamlandı; failure/skip yok, 15 retrieval testi dahil. HTTP/fullsuite veya generator çalıştırılmadı; ayrı task-2 basetemp kullanıldı. Bağımsız source verifier 12 family/27 asset, through Oct4 exit 0. Son read-only assertions exit 0: 457 input, 29 test hash'i, 134 output (128 mevcut/6 deliberate absent) ve 150 coverage dependency hash'i birebir eşit. Katalog 58-parent ile yalnız corpus pini ve iki mekanik kanıt kaydı dışında tamamen aynı. 36 family/date kontrolünde Oct3–4 admitted, Oct5 uncovered_service_date/review_required, clinical_eligibility_complete=false. 4.781 coverage satırının 31 normalized kaynak alanı eşit; gerçek PR128 corpus 8.413 satır/40b2 byte uyumlu. Embedding 4.090×512 local-hash vektörlerinin tamamı yeniden hesaplanarak birebir eşleşti; body hash mismatch sıfır, cold/warm index aynı ve beş query kaynakla uyumlu. Runtime retrieval hash guard eklenmedi; doğrulanan mevcut artifact ve CI coherency testidir.

Bağımsız code/data review P1/P2 bulgu yok; yedi manifestin ek 214 atfı ve 500 mevcut trace payload eşitliği ayrı salt okunur incelemede doğrulandı. Geniş 44-manifest audit'indeki iki copay sorunu 58-parent ile aynı ve bu değişiklikte giderilmiş sayılmadı. Hosted full CI hâlâ bekleniyor; merge/deploy/VPS yapılmadı.

## Task: Corpus CI484 gerçek hatalarını dar kaynak/consumer kapılarıyla düzelt

### Goal
PR154 e11bd142 üzerindeki gerçek 41 backend hatasını mekanik fixture bağımlılığı ile gerçek runtime/snapshot driftini ayırarak düzelt; tarihsel serving izinlerini ve klinik sınırları koruyarak yeni exact head için hosted CI ve bağımsız incelemeyi tamamla.

### Subtasks
- [x] Root: CI484 logunu sakla ve 41 failure sınıflamasını gerçek kaynak/projection kanıtıyla kaydet; frontend tek retry sonucunu backendden ayrı raporla.
- [x] authority_audit: domain/prose stale C* beklentilerini old9639→40b2 aynı full body/context kanıtıyla değiştir; gerekirse yalnız test amaçlı static source identity helper/fixture sahipliğini seam ile paylaş. Consumer çıktısını oracle yapma.
- [x] corpus_seam_review: scripts/GateB/context fixture'ları ve negatif mutasyon hedeflerini gerçek kanıtlı kaynak satırlarına taşı; strict rejection beklentilerini koru. 4.2.14.C census'u bağımsız current source inventory ile doğrula.
- [x] boundary_audit: semantic fingerprint, focused legacy eşitliği, dental fallback, runtime coverage, pipeline smoke ve mevcut surfacing raporlarının gerçek kök nedenini önce bildir. Expected değerlerini yalnız CI geçsin diye değiştirme; gerekli mevcut dar consumer düzeltmesini projection/source kanıtı ve negatif test ile yap.
- [x] independent_review: özellikle historical old→3e release verifier fingerprint/source/serving kapsamının genişlemediğini, fixture bağımsızlığı ve negatif davranışın korunduğunu salt okuyarak doğrula.
- [x] Root: sahipler final code/test/output freeze bildirdikten sonra mekanik consumer report/catalog pin ve coverage evidence kapanışını mevcut helper'larla yenilet; dört coverage parquet'in değişmeden kaldığını veya gerçek gerekçeli üretim farkını açıkça doğrula.
- [ ] Gerçek değişen hedefli testler, compiler/parity/Ruff/source closure ve bağımsız review sonrası yalnız CI hata düzeltmesini commit/push et; yeni head hosted full CI sonucunu ayrı kaydet.

### Out of Scope
Yeni klinik yorum/predicate, tarih penceresi/hukukî sınır uzatma, genel mimari, historical old→3e fingerprintlerini global yeniden baselining, yeni serving transition izni, diğer PR151/152/153 entegrasyonu, frontend kodu, local fullsuite tekrarları, merge/deploy/VPS.

### Specification and plan review
Üst görev mevcut corpus geçişi kapsamındaki mekanik fixture/generated rapor düzeltmelerini açıkça onayladı; kritik fingerprint/dental/legacy durumlarında kaynak/projection kanıtı ve negatif test olmadan gevşetme yasak. Plan owner'lara uygulama öncesi bildirildi. Kaynak PR150 exact58a ve başarılı CI476 değişmez. CI484 gerçek sonuç **41 failed, 8239 passed, 27 warnings, 1124.41s**; compiler/parity backend failure nedeniyle hosted çalışmadı, başarılı sayılmaz. Frontend ilk job111533647997 typecheck/575 test geçti, build font-query hatasıyla düştü. Run bitince yalnız o job için bir rerun kabul edildi; backend rerun yapılmadı. Log task-2/corpus-ci484-backend-failure.log içinde.

### CI484 repair evidence before common closure

CI484 gerçek 41 failure node: 13 domain source-ID fixture, 20 scripts/GateB/source-context fixture, 8 kritik boundary alanı. Kritik alanlar iki gerçek consumer/package hatası (optional dental fallback None ve pipeline seçilen DOCX input-dir eşleşmesi), iki source/projection fixture, bir tarihsel public-coverage fixture ve üç existing surfacing generated-report kontrolüdür. Hosted ilk backend sonucu 41 failed/8239 passed kalır; ayrı frontend tek retry job111538195898 575 test/typecheck/build/public52 ile başarılıdır. Bu sonuç bütün CI başarısı sayılmaz.

Owner koşuları ayrı gerçek aşamalardır: authority RED13 failed/371 passed → GREEN393 passed13.18s; seam RED19 failed/47 passed (committed writer eski test hariç) → GREEN68 passed16.68s; boundary birleşik136 passed22.40s. Bunların toplamı fullsuite sonucu olarak kullanılmaz. 4214c writer tmp_path'a yazar; 655 census bağımsız gerçek source inventory ile hesaplanır. Static fixture131 aktif kimlik taşır; inactive C004584 remap edilmez,10 aynı full body/context eşleşmesi komşulukla ayrıştırılır.

Bağımsız salt okunur inceleme actual immutable Git3f/3e public generatorlarını yeniden çalıştırdı: baseline6ff617…/28input/c556eaf… ve product375aed…/30input/fa4e9ce… fixture/provenance birebir eşleşti. Release verifier/deploy source byte-unchanged; old→current ve current→current actualcoverage reddedilir, üç current route fingerprint pozitif kontrolü korunur. Consumer helper'dan bağımsız131source ve262komşuluk pini doğrulandı. Surfacing97row94byte-equivalent dictionary, exact3invaliddrugIDremoved, financial findings359→359. Ortak report/catalog/evidence kapanışı, final tek focused gate ve yeni exacthead hosted CI henüz pending.

### Final CI repair closure before publication

Consumer report SHA256 b273b9b6a972d5e963a55bda0e5731b35c1b06d7ff6bcf491c63d414e19820c8 (1466826B); catalog b4e65f80f2846699875679ce5ef74d6f55280aac6415189262ddebe89a154194 (19550B). Actual maps467 input/60 test/134 output(128present+6expectedabsent) sıfır uyuşmazlıkla kapandı; yeni3helper ve3historicalpublicfixture açıkça test provenance girdileridir, production/serving yetkisi değildir. Catalog yalnız existingconsumerreportSHA alanında değişti. Finalcoverageevidence227efe04c7cc785b4560d0f9e1b5b3712d1dd9d8e67ac6494809a08161f11dbe (127548B)150dependency içerir; yalnızcatalog/reporthashleri değişti, dörtcoverageparquet HEADe11 ile byte-identical kaldı.

Root compiler --check134byte-identical, drugparity23/23zeroissues, globalRuffsrc/scripts ve gitdiff--check gerçekten exit0. Tek son bağımsız pytest174passed/2mevcutwarnings/30.11s, exit0: CI484 original41failurenode (kanıtlı yeniden adlandırmalar dahil), helper/dental/pipeline negatives, historicalgolden/currentrejection, kaynak/coverageclosure ve11retrieval testi. JUnit sayımıyla ayrışan dört index initialization testi bu174 sayısında yoktur; yalnız bu eksik dört test ayrıca gerçekten4passed/0.20s ile tamamlandı. Son retrieval kapsamı11+4 ayrı koşudur. Independentfinalreadonly467/60/134/150hashpin,58-parentdeepcatalogcomparison,36family/date ve12family/27assetsourceclosure assertions exit0. Full hosted CI yenihead için henüz çalışmadı; bu174 sonuç CI484 history41fail/8239pass veya fullsuite sonucu ile toplanmaz. Merge/deploy/VPS yapılmadı.

CI repair bağımsız final code/data review: P1/P2 bulgu yok; post-test pin/dış hash/diff kontrolleri geçti. Tam actual komutlar ve sonuçlar task-2/independent-ci484-final-commands.json, review makbuzu task-2/independent-ci484-review-result.json içinde. Hosted yenihead fullCI sonucu bu incelemeye dahil değildir.

## Task: Exact-source EK-4A and idempotent SUT ingestion

### Goal
Publish a small verified draft PR repairing the producer and metadata while preserving clause history and admitting only exact-source EK-4A data.

### Subtasks
- [x] Verify current remote main and closed PR128 in a clean isolated worktree.
- [x] Prove stale-state/self-comparison root cause and write exact path plan in plans/update/2026-10-05-ek4a-ingest-idempotence.md.
- [x] Complete official-source decoded schema/key/history/name/discount/date comparison; record final exact source and partition before writing.
- [x] Preserve historical dated clause reports with positive, negative and idempotent rerun tests.
- [x] Repair exact-input completion and future-date handling without claiming full ingestion of partial source capture.
- [x] Admit exact current/MÜLGA EK-4A source/raw and honest partial manifest/state; preserve runtime curated bytes per approved deferral.
- [x] Run focused regression and canonical artifact checks.
- [ ] Open new draft PR, finish independent exact-head review and hosted full CI.

### Out of Scope
Main writes, merge, force push, deploy/VPS, secrets/auth setup, sourceauthority/clinical catalog/coverage edits, new payment or clinical interpretation, and duplicate local full-suite runs.

### Review

Final combined focused gate after the independent fetch finding: 250 passed in 22.15s. Global Ruff, compiler --check (134 byte-identical artifacts), drug manifest parity (23/23, zero issues) and git diff --check passed. Current main remains 3d29a1fe. Source/raw/manifest/state rerun preserves all six admitted file bytes; runtime EK-4A 8078, corpus 8413 and historical clause reports remain byte-identical to base. Official future markers prevent pre-October-10 curation; current catalog promotion and full 318-workbook October reconciliation are explicitly deferred. Draft PR162 is open. Independent review reproduced the exact source/raw and historical report proof; its fetch process-death P2 is fixed by atomic publication, with four abrupt-exit and two concurrent-publication regressions. Revised exact-head review and hosted full CI remain pending; no laptop full-suite repeat.
## Task: App UI overhaul, phase 0: screenshot baseline and numbers-parity capture (2026-10-07)

### Goal
One command produces the screenshot set, the numbers-parity JSON and the layout metrics for the plan routes from a local production build on the synthetic cohort, and a second command proves that two runs show the same numbers; the shipped UI does not change.

### Subtasks
- [x] Add `frontend/scripts/lib/numbers-parity.mjs`: pure functions that normalise rendered text and tokenise money (EN and TR forms, one canonical key), counts, percents and honesty markers, and that compare two runs; add `numbers-parity.test.mjs` (vitest picks it up) with EN/TR money, date masking, compare and exception cases.
- [x] Add `frontend/scripts/capture-screens.mjs`: CLI, identity (public by default, dev optional), chat stub, per-state settle, expand-all, extraction, screenshots, metrics, run-meta, fail-loud rules, `--compare`.
- [x] Put the verified local run commands (backend cache, backend with `--timeout-keep-alive 65`, build, start, capture) in the script header and run them from a clean shell.
- [x] Run the full capture twice on one build: `numbers/` and `text/` are byte-identical (`diff -r`), `metrics/` is identical at 1440 and 1280 except the deep-link scroll offset (390 px patient-page heights may differ by up to about 60 px, measured 19 to 59 px on 6 of 60 files); EN and TR canonical money maps are equal for every state.
- [x] Negative checks: backend stopped or injected 5xx gives a non-zero exit and no partial baseline; `--compare` fails on a changed amount and passes on an identical run.
- [x] Record the baseline set from a build whose `frontend/src` equals `approved/main` (`git diff approved/main --stat -- frontend/src` is empty) into `lanes/ui/baseline`.
- [x] `npx tsc --noEmit`, `npx vitest run`, `npm run build` stay green; `git diff approved/main --name-only` lists only the two scripts, the test and `tasks/todo.md`.

### Out of Scope
Any change under `frontend/src`, any backend, rule, amount, exactness or API change, the deploy lane, phases 1 to 8 of the plan, fixing the pre-existing 404 of `/api/frontend-config`, committing screenshots or recordings.

### Review (2026-10-07)
- Changed paths: `frontend/scripts/capture-screens.mjs`, `frontend/scripts/lib/numbers-parity.mjs`, `frontend/scripts/lib/numbers-parity.test.mjs`, this file. Nothing under `frontend/src`, no `package.json` or lockfile, no backend, no `.gitignore`.
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 85 files / 614 tests passed (84 / 596 before plus the new 18); `npm run build` exit 0.
- Local run: backend :18001 (public billing mode, `--timeout-keep-alive 65`), `next start` :13000, capture with system Chrome 154. Full matrix: 86 numbers files, 86 text, 60 metrics, 120 PNG, `failedRoutes: []`, `warnings: []`, 325 to 338 s.
- Determinism: two full runs, `diff -r numbers` and `diff -r text` empty (86 + 86 files); `metrics/` identical except `deepLink.top` and 6 patient pages at 390x844 (height and first-money top differ by 19 to 59 px, the chat textarea autosize race); 95 of 120 PNGs byte-identical, so PNGs are evidence only. EN and TR money maps equal in 43 of 43 states.
- Fail loud (all run): injected 500 on one billing report gives exit 1 and no numbers file for that route; backend stopped gives exit 1 with only `run-meta.json`; backend without public billing gives exit 2; a proxy reporting `is_synthetic: false` gives exit 2. `--compare`: identical run passes; a changed amount, a hidden partial marker, a missing state and a changed identity fail; a multiplicity-only change warns and fails with `--strict-multiplicity`; the allow list suppresses exactly its entries and prints unused ones.
- Additions to the scout's code: unknown options, bad values and unknown route ids exit 2 instead of being ignored; `--out` must not already hold capture output (`--overwrite` replaces it) so a run never mixes with stale files; the deep-link route needs a finding on patient 0029 or `--no-extras`; unused allow entries are printed by `--compare`. The header no longer points at a plan file that is not in the repo.
- Baseline: `lanes/ui/baseline` (outside the repo, not committed), captured with `frontend/src` equal to `approved/main` (`c44aa78c`); `run-meta.json` records `dirty: true` because the two scripts and this file were not committed yet.
- Not run: Node 20 and Node 26, the standalone deploy runtime, a real LLM key (the chat is stubbed), `npm run lint`, backend pytest (forbidden in this lane), the developer identity (`--identity dev`, only run by the scout).

## Task: App UI overhaul, phase 0 fixer round: make the parity guard honest (2026-10-07)

### Goal
Every blocking finding of the phase-0 review is either fixed in the capture tool or answered with a measured reason, so that a pass of `--compare` can no longer hide a missing amount that became "0.00 TRY", two swapped amounts, or uncertainty wording that was collapsed away.

### Subtasks
- [x] Verify each finding against the code and the recorded baseline (scenarios re-run with the old tool: F1, F2, F3 and F4 reproduced; F5, F7, F8 and F9 reproduced in the browser or on disk; F6 and A5 measured).
- [x] numbers-parity: fail when the zero-amount count rises or a lone "-" placeholder disappears; never print "PARITY OK: no number changed" when warnings exist.
- [x] numbers-parity: record standalone amounts under their label and fail when a label that exists in both runs now holds other amounts.
- [x] numbers-parity: compare honesty wording by lines (default view: failure, expanded page: warning), add the "not evaluated", "missing inputs" and "amount unverified" families, fold Turkish dotted and dotless i so CSS-uppercased text still matches.
- [x] numbers-parity: warn when a baseline default-view amount is no longer in the default view; refuse to compare runs of different schema (schema 2).
- [x] capture: decide default-view visibility from the layout (probes in `lib/page-probes.mjs`, `--self-test` proves it in Chrome), write `<state>.visible.txt` next to `<state>.txt`.
- [x] capture: add money overlap and clipped-amount metrics, the TR postfix amount form and the chat input height to the metrics; print and record routes with collisions.
- [x] capture: add the 14 other Compliance and Reference Tools sub-views as routes (`lib/capture-routes.mjs`, drift test against `workspaceSubtabs.ts`).
- [x] capture: `--overwrite` stages the new run in `<out>.incomplete` and replaces the old output only after a complete run.
- [x] capture: errors go through `safeMessage` (no call log, no cookie, no ANSI codes) before they reach stderr, the log or run-meta.json.
- [x] Re-run tsc, vitest, build; re-record the baseline with the new tool and prove it is deterministic.

### Out of Scope
Anything under `frontend/src`, backend, rules, amounts, exactness, API shapes; fixing the app's chat textarea sizing or the deep-link scroll offset (they are app behaviour; Phase 1 replaces the chat panel); the other lanes; committing screenshots or baselines.

### Review (2026-10-07, fixer round)
Findings, one by one (all re-run against the old tool first; "answer" means a measured reason instead of a code change):
- F1 zero amount from a missing amount: correct. Old tool: `compareRuns` ok, warning only, "PARITY OK: no number changed", exit 0. Now `zero_amount_added` and `placeholder_removed` fail (default mode), and the last line is "PARITY OK WITH n WARNINGS ... not proof" whenever a warning exists.
- F2 amounts compared as an unlabelled multiset: correct. Now every amount that stands alone on the line under a label is recorded (`labelled`, 704 labels in the 86 old states) and a label that exists in both runs with other amounts fails (`label_amount_changed`). Limit, by design: amounts inside table rows or prose have no label, and it is text adjacency, not DOM structure.
- F3 marker presence only and missing vocabulary: correct. Now counted by lines (default view: failure, expanded page: warning) and extended by not evaluated, missing inputs, amount unverified, partial totals. "Unknown date" is not a UI string (no hit in `frontend/src`), so it was not added.
- F4 Turkish case folding: correct. `foldText` maps İ and ı to i before matching; tests cover KISMİ KESİN, KULLANILAMIYOR, DEĞERLENDİRİLMEDİ, TUTAR DOĞRULANMADI.
- F5 innerText keeps CSS-collapsed text: correct (Chrome 154: height 0, max-height 0, grid 0fr, opacity 0, clipped sr-only box, left -9999px; excluded only display none, [hidden], visibility hidden, closed details). Now the default view is read from the layout (`lib/page-probes.mjs`); `node scripts/capture-screens.mjs --self-test` proves it in Chrome (also with the probe weakened: it fails). In today's UI the two readings are identical (checked on Patients, Revenue, Compliance, patients 0003 and 0017), so the baseline numbers did not change; the guard protects Phase 6.
- F6 coverage: correct. 14 more routes (7 Compliance and 7 Reference Tools sub-views, 84 more states, 170 in total); a drift test ties the ids to `workspaceSubtabs.ts`. A baseline default-view amount that leaves the default view but stays on the page is a warning (`default_view_amount_hidden`), not a failure, and there is no must-stay-visible list: Phase 2 collapses on purpose, so a person reviews each warning.
- F7 money wrap blind in TR and no overlap measure: correct. `moneyOverlapCount` (two text boxes sharing a line band) and `moneyClippedCount` (amount cut off by a clipping ancestor or the page) now exist, plus the TR postfix form "9000.00 ₺". They find the split-pane collisions of the review (EN 1440: 5, EN 1280: 7, TR 1440: 8, TR 1280: 9; confirmed on the PNGs) and the cut-off bill chips on patient 0003; single-pane desktop routes report 0 overlaps.
- F8 `--overwrite` deleted the baseline before the preflight: correct. The new run is staged in `<out>.incomplete` and replaces the old output only after a complete run (run: backend down gives exit 1 with all 34 old files intact; success path replaces everything).
- F9 session cookie in stderr and run-meta.json: correct. `safeMessage` drops the call log and ANSI codes and redacts registered secrets (run: fake env file and closed port gives exit 1, zero hits for bilun:session, the secret and ESC in stderr, stdout and run-meta.json). Not run: `--identity dev` against a real backend.
- F10 marker vocabulary and TR case: same defects as F3 and F4, fixed together.
- A5 metrics jitter at 390: the 45 px bound was too tight, the tool is not at fault. Cause found: `SutInlineAIPanel.tsx` sizes the chat textarea once at mount (`syncInputHeight`, effect on `input` only) while the width is not final, so the textarea is 114, 133 or 144 px tall in the baseline instead of 55 or 75 px, and it flips between runs. `metrics.chatInputHeight` now records it. Measured: of 48 files at 390 the two final runs differ in 1 (tr patient-0029: chat 144 vs 133, scrollHeight, firstTableRowTop and firstMoney.top all 11 px apart, nothing left unexplained). The review saw up to 59 px (3 lines). At 1440 and 1280 all 96 metrics files are identical. `deepLink.top` is the page's own scroll offset, not a stable number. This is app behaviour, so it stays; the criterion now reads "identical at 1440 and 1280, and at 390 identical after removing the chatInputHeight difference".

Results:
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 87 files / 641 tests passed (614 before: parity tests 18 to 40, routes 2, safe message 3); `npm run build` exit 0 (API_PROXY_TARGET unset, like CI); `npx eslint` on the scripts exit 0; `--self-test` OK.
- Baseline re-recorded because the stored JSON gained fields (schema 2) at `lanes/ui/baseline`: 170 states, 144 route captures, 288 PNG, 631 s, no failed route, cohort 50. The schema-1 baseline is kept at `lanes/ui/baseline-schema1-e20a206a`; comparing against it exits 2 with a re-record hint. The 86 old states have the same expanded text (86 of 86 files) and the same money, counts and percents as before, so the app recorded is the same (`frontend/src` equals `approved/main`).
- Determinism, two full runs: `diff -r numbers` (170 files) and `diff -r text` (340 files) empty; `--compare --strict-multiplicity` exit 0 with 0 failures and 0 warnings; metrics identical at 1440 and 1280, see A5 for 390; 263 of 288 PNGs byte-identical (evidence only).
- Reviewer scenarios through the real CLI (`--compare`) on the new baseline: null money to 0.00 exit 1; swapped amounts exit 1; one of two Partial exact lines or two of three unavailable lines collapsed exit 1; Not evaluated lines removed exit 1; TR uppercase partial line removed exit 1; unchanged control exit 0; headline amounts leaving the default view exit 0 with "WITH 19 WARNINGS"; a merged duplicate exit 0 with "WITH 1 WARNING".
- The run-meta.json of the baseline records the sha256 of the five tool files; `git.dirty` is true because the commit came after the recording, the hashes match the committed files. One trailing blank line of `numbers-parity.mjs` was removed after the recording (whitespace only, diff checked); its hash in run-meta.json was updated and the old value is kept in `toolHashNote`.
- Not run: Node 20 and Node 26, GitHub CI, `npm run lint` on all of `src`, backend pytest (forbidden in this lane), `--identity dev` against a real backend, a real LLM key (chat stubbed). Servers on 18001 and 13000 were stopped by PID; scratch captures under `~/.cache/ui-capture-tmp` and `.next` were removed.

## Task: App UI overhaul, phase 0 fixer round 2: close the guard's remaining blind spots (2026-10-07)

### Goal
The seven blocking findings of the second phase-0 review are each either fixed in the capture tool (with a failing case first) or answered with a measured reason, so that the baseline covers all 50 patients, the Source drawer and the wording a collapse would hide, and a collapsed box can no longer pass as visible.

### Subtasks
- [x] Verify each finding against the code and the recorded baseline before touching anything (baseline text, the live app on 18001/13000, Chrome 154).
- [x] Page walk: add `page-2` to `page-N` states for the Patients tab (`?p=N`, primary size, both locales), fail the route when the pages do not show every cohort patient, record the pager of every captured route in the metrics, list paged tables that are not walked (Reference Tools Drugs, Compliance Materials) in run-meta.
- [x] Source drawer: add `source-drawer` (page-level drawer opened by "Inspect clause") and `source-drawer-copay` (the second drawer instance) per primary patient where the button exists; include the modal dialog in the scope (nested scopes counted once); add a viewport PNG per drawer state.
- [x] Marker vocabulary: add the families that today's uncertainty lines need (could not be verified, cannot evaluate, estimated, manual review, no value inferred, no match, not exact, more findings available) in EN and TR, tested against the real strings of `messages/en` and `messages/tr`; bump the schema to 3 so an old baseline is refused.
- [x] Labels: compare label keys case- and dotted-i-folded, and warn (with a count) for every baseline label that holds amounts and has no counterpart in the candidate, so a renamed label is never skipped silently.
- [x] Probes: decide hidden for a clipping box from its content box (padding and border do not keep a collapsed box visible), also for a transform that scales a box to nothing and for a clip-path inset that clips everything; add the padded cases to the self-test first (they fail today).
- [x] CI: move the self-test cases into `lib/probe-selftest.mjs` and run them from vitest when Chrome is installed (skipped with a visible reason otherwise), so `npx vitest run` guards the probe.
- [x] Wave A: record in run-meta whether the backend serves Wave A evidence (it does not in a local synthetic run; the receipt cannot be issued here), print it at the end of a capture and write the limit into the header; no data is faked.
- [x] Re-run tsc, vitest, build; re-record `lanes/ui/baseline` with the schema-3 tool (the schema-2 baseline is kept), prove determinism with a second run, replay the reviewers' scenarios through the real CLI.

### Out of Scope
Anything under `frontend/src`; backend, rules, amounts, exactness, API shapes; faking or stubbing Wave A evidence or a signed activation receipt; walking all 270 pages of Reference Tools Drugs; the split-pane drawer state; opening every clause button (one per kind and patient); fixing app behaviour the tool only measures; the other lanes; committing screenshots or baselines.

### Review (2026-10-07, fixer round 2)
Findings, one by one (each reproduced against the old tool or the recorded baseline before any change):
- F1 Patients table captured for page 1 of 5: correct (baseline: "Page 1 of 5", 10 rows, 10 amounts; 40 of 50 patients in no file). Fixed: states `page-2` to `page-5` through `?p=N` at the primary size in both locales; the route fails unless the pages show all 50 cohort patients (verified live: 5 pages, 50 distinct ids, `?p=6` clamps to page 5, which the tool also rejects). Reference Tools Drugs (page 1 of 270) and Compliance Materials (rows 1-100 of 163) are NOT walked: 270 pages of reference data is not worth 540 states, and Materials has no URL page param. They are recorded as data (`run-meta.json` `limits.unwalkedPagers`, `metrics/*.json` `pagers`), printed at the end of a run and named in the header and in the baseline README. The Materials gap (63 findings and their amounts) matters for Phases 3 and 4.
- F2 Source drawer in no state: correct (0 hits of "Legislation" or "Mevzuat" in 170 states). Fixed: `source-drawer` (page-level drawer, first "Inspect clause" button) and `source-drawer-copay` (the second instance in the copay section) for patients 0003, 0029 and, copay only, 0017; the modal dialog renders outside `#main-content`, so dialogs are part of the scope (nested scopes counted once, `scopesOf`); one viewport PNG per drawer state. Limits found while doing it: on the three primary patients the Compliance findings table has no row with a clause key, so only Recommended actions rows (revenue view) and copay links open a drawer; patient 0017 has no "Inspect clause" button (listed in `skippedStates`); other clauses, the split pane and the drawer's loading and error states are not captured. The drawer text is Turkish in both locales and its kicker reads "Legislation" or "Mevzuat".
- F3 uncertainty wording outside the vocabulary: correct (tokenise returned `{}` for all seven lines). Fixed: families unverified, estimated, manualReview, notInferred, mismatch, notExact, incompleteList, and cannotCompute widened to "cannot evaluate" (EN and TR), tested against the real strings read from `messages/en` and `messages/tr` (28 key checks plus the estimate lines) and by the review's repro. The vocabulary is words, not meaning: a line worded differently is not protected until its words are added (header of `numbers-parity.mjs`). Schema is now 3, so a schema-2 baseline is refused (exit 2).
- F4 renamed or re-cased label skipped silently: correct. Fixed: labels are compared folded (case, dotted and dotless i), so the review's repro (swap plus re-case) now fails with `label_amount_changed`; a baseline label with amounts that has no counterpart is a `label_not_in_candidate` warning with the label and its amounts (the verdict then says "WITH n WARNINGS"), and `--strict-labels` turns it into a failure that an allow entry (kind labelled) can waive. Limit that stays: a swap hidden behind a rename cannot be told from a rename; by default it is a warning (exit 0), so a script that gates only on the exit code must pass `--strict-labels`.
- F5 and F7 padded or bordered collapsed box counted as visible: correct (all four review cases, plus a padded grid child, `scaleY(0)`, `scaleX(0)` and `clip-path: inset(50%)` or `inset(0 0 100% 0)` were kept). Fixed in `page-probes.mjs`: a clipping box is hidden when its content box (clientWidth or clientHeight minus padding) is under 2 px; a transform that shrinks a laid-out box to nothing; a clip-path inset that leaves no area. The 10 hidden cases (and 4 visible controls: padded box, absolute badge in the padding, translate and scale, a small inset) were added to the self-test first and failed on the old probe, then passed; three weakened probes (no content-box rule, no transform rule, no clip-path rule) make the vitest test fail. Not detected, and said so in the header: other clip-path shapes, `color: transparent`, `text-indent: -9999px`, text covered by another element.
- F5 CI part: the self-test cases moved to `lib/probe-selftest.mjs`; `page-probes.test.mjs` runs them in system Chrome under `npx vitest run` and is skipped (visibly) when no Chrome is installed (`BILUN_CHROME_PATH`, `/usr/bin/google-chrome`, `/opt/google/chrome/chrome`). The ubuntu runner image of GitHub is documented to include Google Chrome, but I have not verified that here and could not run GitHub CI: that is the open risk of this round (if Chrome is missing there the test is skipped, not failed).
- F6 Wave A never rendered: correct and NOT fixable here. The backend serves Wave A only with a signed release receipt (`wavea_capability_unavailable`), which a local synthetic run cannot have, and faking it would put invented data in a baseline. Recorded as data (`run-meta.json` `limits.waveAEvidence`, a line at the end of every run), in the header and in the baseline README. Consequence, stated plainly: the Phase 2 criterion "page height at 1440 with default collapses at most 3,500 px, measured by the Phase 0 script" cannot be judged honestly with this baseline (patient 0003 is 5,657 px here without the largest block), and the collapse rule "partial and unavailable stay in the header line" must be tested with component fixtures or on an environment that serves Wave A.

Results:
- Gates (Node 22.16.0; CI uses Node 20, GitHub CI is the final arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 88 files / 684 tests passed (87 / 641 before: parity 40 to 77, routes 2 to 7, probes 1 new file); `npm run build` exit 0 (API_PROXY_TARGET unset, like CI); `npx eslint scripts` exit 0; `--self-test` OK.
- Baseline re-recorded at `lanes/ui/baseline` (schema 3, commit 2f57b401, clean tree, six tool hashes in run-meta): 188 states, 144 route captures, 298 PNG, 702 s, no failed route, cohort 50. The schema-2 baseline is kept at `lanes/ui/baseline-schema2-00088602`. New states: 8 pages, 10 drawers. The 170 old states: all 340 text files byte-identical to the schema-2 baseline (so the new probe rules and the dialog scope change nothing today), money, counts, percents, placeholders and labelled identical, old marker counts identical; only new marker kinds appear.
- Determinism, two full runs (A at 78d80d5f, B at 2f57b401, the only tool change between them is `--strict-labels`): `diff -r numbers` (188) and `diff -r text` (376) empty; `--compare B A --strict-multiplicity --strict-labels` exit 0 with 0 failures and 0 warnings; metrics identical at 1440 and 1280 (96 of 96) and at 390 except 4 patient pages whose every difference equals the `chatInputHeight` difference (30, -30, -30, -11 px); 267 of 298 PNGs byte-identical (evidence only).
- Review scenarios through the real CLI (`--compare` on the new baseline): control exit 0; "could not be verified" line hidden in the default view exit 1 (`marker_hidden_in_default_view unverified`); "cannot evaluate" line hidden exit 1; TR "doğrulanamadı" line hidden exit 1; "is estimated from the EK-3" line hidden exit 1; amounts swapped and labels re-cased exit 1 (2 x `label_amount_changed`); one amount of a patient on page 3 changed exit 1; page 5 of the Patients table missing exit 1; Source drawer state missing exit 1; amounts swapped and labels renamed exit 0 with "WITH 2 WARNINGS" and exit 1 with `--strict-labels`.
- Not run: Node 20 and Node 26, GitHub CI, `npm run lint` on all of `src`, backend pytest (forbidden in this lane), `--identity dev` against a real backend, a real LLM key (chat stubbed), the split-pane drawer, a walk of Drugs and Materials.
- Cleanup: backend (18001) and `next start` (13000) stopped by PID, ports free; `.next`, scratch captures under `~/.cache/ui-capture-tmp` and the scenario work dirs removed.

## Task: App UI overhaul, phase 1: page frame, content first (2026-10-07)

### Goal
At 1440x900 and 1280x800 the first Patients table row is above y = 300 and the patient money summary is in the first screen; the chat is a one-line collapsed bar that calls the model only after it is opened, the cohort filter is one toolbar row, the patient page has no standalone search card, and a sub-view tab reads "Parent · Subtab"; no amount, count, exactness state, rule or API changes.

### Subtasks
- [x] Dock model: add `"collapsed"` to `SutChatDockPosition` and make it the store default (owner decision D1); add `lib/chatDockPreference.ts` (key `bilun:chat-dock`, SSR-safe read and write, an unknown value gives the default) with a test; the store action `setAiDockPosition` remembers the user's choice, `NavigationProvider` applies the saved choice in a layout effect after hydration, `WorkspaceSplitLayout` forces right-to-center with `setState` so it never overwrites the saved dock, and `AppSidebar` reads the saved dock itself for its first width.
- [x] `SutInlineAIPanel`: render the collapsed one-line bar ("Ask Bilun…" plus dock buttons) after all hooks; one collapse/open button in both states that hands keyboard focus to its twin; new prop `allowRightDock` (false while a split view is open: collapse and open stay, the right column goes); the component's own default dock stays `center`.
- [x] Auto-brief gate on every path (mount debounce, locale change) and a new effect that briefs once when the panel opens; keep `dock` out of the context effect's dependencies so docking or collapsing never aborts a stream; the Regenerate button lives only in the open panel.
- [x] Pages: replace `chatDock !== "center"` with `isChatDockedRight(chatDock)` in `app/page.tsx` and `app/patient/[id]/page.tsx` (the helper lives in `lib/chatDockPreference.ts`, not in `lib/chatDockLayout.ts`, which reads a constant of the panel module that page tests mock away); both pages pass `onDockChange={setChatDock}` and `allowRightDock={!splitActive}`; `lib/chatPanelMount.test.ts` stays green unchanged.
- [x] Patient page: remove the card at `app/patient/[id]/page.tsx:515-550` (breadcrumb, patient search, description) and its dead code (`handlePatientSelect`, four imports); keep `components/ui/PatientSearch.tsx`; "Back to patients" stays; Ctrl+K and the tab-strip search button remain the patient search, and a test pins that Quick Open finds a patient by id and opens it.
- [x] `CohortFilterBar`: one `Toolbar` row (four labelled controls with fixed widths, "Clear filters" while a filter is active, the "N of M patients" chip, no header text), props and the three callers unchanged; no "0 of 0 patients" while the list is empty (not loaded, or failed); component test in EN and TR.
- [x] Spacing so the first Patients row is above y = 300 (prototype measured 286, plan-literal edits alone about 340): `.sut-app-main` top padding 1rem, invoice table card `md` padding, `space-y-4` in `SUTPatients`, `SUTCompliance` and `SUTRevenue`, toolbar `py-2`, chat bar `py-1` and `mb-3`; the content width (`max-w-7xl`) is unchanged.
- [x] Tab label: `resolveTabInfo` returns `"Parent · Subtab"` as `label` (the same text as `fullTitle`); raise `WORKSPACE_TAB_MAX_PX` from 208 to 280 so none of the 22 labels is cut in EN or TR; update the 15 label assertions in `lib/workspaceSubtabs.test.ts` and add the 22-label matrix test with the real messages.
- [x] Messages (EN and TR): add `chat.actions.collapse`, `chat.actions.expand`, `chat.collapsed.prompt`, `chat.collapsed.working`; remove `cohort.filterBar.description` and the seven keys of the removed card (`patient.page.breadcrumbAria`, `workspace`, `patient`, `patientUnknown`, `searchEyebrow`, `searchPlaceholder`, `searchDescription`); keep `cohort.patientSearch.ageSuffix` and `patientDetails` (used by `lib/cohortFilter.ts`).
- [x] Tests: `navigationStore.test.ts` (default collapsed; only a user choice is remembered), `chatDockLayout.test.ts`, panel tests (collapsed markup EN/TR, split-view controls, no brief while collapsed, one brief on open, no abort on collapse, locale change while collapsed), patient page pane test (no search card, chat props), `WorkspaceQuickOpen.test.tsx`, `CohortFilterBar.test.tsx`, `chatDockPreference.test.ts`.
- [x] Gates: `npx tsc --noEmit`, `npx vitest run`, `npm run build`; `npx eslint` on the touched files shows nothing beyond the 8 existing problems; a full capture of the branch compared with `lanes/ui/baseline` using `--strict-multiplicity --strict-labels` ends in PARITY OK without warnings, and the line-by-line text diff shows only the expected lines removed and added.
- [x] Browser checks (probes in the spec appendix): 0 chat requests on load and exactly 1 after Open on the 5 home tabs a billing user sees (Rule Database is developer-only) and a patient page, the saved dock restored without hydration errors for collapsed, center, right and an unknown value, expand inside a split view, focus handoff, Quick Open by Ctrl+K and by the strip button in EN and TR, 390 px loads identical.

### Out of Scope
Phase 2 and later (summary row, next actions, Source drawer, collapsing secondary blocks), any backend, rule, amount, exactness or API change, deleting `components/ui/PatientSearch.tsx`, mobile and tablet layout (Phase 7), motion (Phase 6), a cookie so the server can render the saved dock, syncing the dock between browser tabs, the `/api/frontend-config` 404, the `0.00 TRY` values the API itself returns, committing screenshots or baselines.

### Review (2026-10-07)
What was built: the scout's verified prototype (`lanes/ui/phase-1/spec.md`, Appendix A) was read in full (all 1,723 lines) and applied with `git apply -p1`; the only change on top is that three test files lost a trailing blank line (`git diff --check` was not clean). 33 files under `frontend/src` (29 changed, 4 new: `lib/chatDockPreference.ts` and three new test files) plus this entry; no backend, `package.json`, lockfile, workflow or capture-tool file.

Gates (Node 22.16.0; CI uses Node 20 and stays the arbiter), on the final tree:
- `npx tsc --noEmit` exit 0; `npx vitest run` 91 files / 711 tests passed (baseline 88 / 684); `npm run build` exit 0 (`API_PROXY_TARGET=http://127.0.0.1:18001`).
- `npx eslint` on the 32 touched `.ts` and `.tsx` files: 7 problems, all pre-existing (`app/patient/[id]/page.tsx` 78, 295, 305, 375 and `CohortFilterBar.tsx` 47, `AppSidebar.tsx` 90, `PatientInvoiceTable.tsx` 136; the lines moved by 1 or 2 where imports were removed). The eighth known problem (`WorkspaceTabStrip.tsx:24`) is in a file this phase does not touch. `SutInlineAIPanel.tsx` is clean.

Acceptance, measured on a real `next build` and `next start` of this branch (backend 18001, frontend 13000, synthetic cohort of 50, chat endpoint stubbed because there is no LLM key):
- Full capture: 188 states in 645 s, no failed route, same 2 skipped states as the baseline (patient 0017 has no "Inspect clause" button).
- First Patients table row top: 286 at EN and TR, 1440x900 and 1280x800 (baseline 612, 612, 612, 630). First amount of the three patients: top 507 (baseline 852); headline amounts end at 552 to 589 (EN) and 552 to 559 (TR), inside both viewport heights. Compliance and Revenue first amount moves up 318 px; patient pages are 345 px shorter, Compliance and Revenue 318 px.
- No chat request without a user action: 0 `POST /api/chat` on load on the 5 home tabs and patient 0003, 0 after five client-side tab switches, exactly 1 after "Open chat", still 1 after collapse and reopen; a tab switch while open briefs the new tab once (2 in total, as today). Focus moves to "Collapse chat" after Open and to "Open chat" after Collapse.
- Saved dock (12 loads, 6 values x 2 pages): `bilun:chat-dock` restores collapsed, center and right; "left", "garbage" and no value give the collapsed bar; no React or hydration error. Saved right: panel fixed, `--chat-dock-inset-right` 412 px, sidebar rail 64 px, section `w-full`. Collapsed and center keep `mx-auto max-w-7xl` (width 1172 and 1012, no horizontal scroll). A split view shows "Open chat" and no "Dock right"; after Open one request, Collapse and Center buttons; a saved right dock is still `right` in storage after a split opens.
- Cohort filter: one toolbar row, 77 px high at 1440 and 1280, EN and TR, inactive and active (`?cohortSex=E`); at 1100 px it wraps to two rows (115 to 119 px), which the plan does not cover. No "0 of 0 patients": not in the server HTML, not while `/api/patients` is slow, not after a 500; "50 of 50 patients" when settled.
- Patient page: no search input, no combobox, no breadcrumb; "Back to patients" present (12 cells). Quick Open finds a patient by Ctrl+K and by the strip button in EN and TR and opens it. Tab labels: 22 of 22 equal "Parent · Subtab" in EN and TR, 0 cut at 280 px; the live strip shows "Compliance · Copay Rates". 390 px: no textarea, three loads of Patients, 0003 and 0017 have identical heights (1095, 9521, 7827); horizontal-scroll flags unchanged. Deep link `?section=claim-compliance&finding=...`: `found` true in 6 of 6 cells (offset unstable, as the baseline README says). Split view metrics (money overlaps 5, 7, 8, 9 and wraps) unchanged.

What the numbers guard compared and what it cannot see (do not read "PARITY OK: no number changed" as a claim about everything):
- `--compare lanes/ui/baseline <candidate> --strict-multiplicity --strict-labels` exit 0: 188 states, 0 failures, 0 warnings. It compared the set of amounts, counts, percents and uncertainty wording per state and the standalone amounts under their labels (about 10 percent of the amounts). Amounts inside table rows, bill chips and prose are compared as a set, so a swap between rows would not fail it; clipped text counts as visible; it does not see controls, order, the tab strip, layout, requests, the saved dock or hydration.
- Because of that, two extra checks were run: `diff -rq` of the numbers folders (188 of 188 files byte-identical) and the in-order text check `textdiff.py` (spec Appendix C): 376 text files, 2,680 expected lines removed (chat card, filter header, patient search card and breadcrumb), 0 files with an unexpected difference; one injected defect (two headline amounts swapped) made it exit 1. By hand (script, not by eye) the 30 headline label and value pairs (5 labels x patients 0003, 0017, 0029 x EN and TR, 1440x900, default view) are identical, including the two `0.00 TRY` / `₺0,00` recoverable values of 0017 and 0029 that the API returns itself. The default view holds 536 uncertainty-wording lines (partial, unavailable, not evaluated, could not be verified, estimated and the TR forms) before and after; the 188 lines that disappear are the chat stub answer "temporarily unavailable" (one per state; a collapsed chat does not brief), which is not billing wording.
- A reviewer must still compare the rows and columns of the bill picker, findings table, summary row and Patients table pages 1 to 5 by hand, and repeat the pairs for 0003, 0017 and 0029; the guard and my scripts are not a substitute.

Deviations from the plan (all taken from the scout's recommendations D-1 to D-4; the owner decided D1 to D5 of the plan, not these four):
- D-1 tab width: `WORKSPACE_TAB_MAX_PX` 208 to 280, because "Parent · Subtab" is cut in 12 (EN) and 13 (TR) of 22 tabs at 208 px. Fewer tabs fit before the strip scrolls.
- D-2 the plan range `page.tsx:515-550` also held the breadcrumb; it is removed with the search card ("Back to patients" and the header keep the information).
- D-3 the filter chip is hidden while the cohort list is empty (the old chip read "0 of 0 patients" for missing data). A genuinely empty cohort also shows no chip.
- D-4 the plan's own edits give a first row at about 340, not below 300; six extra spacing trims (global `.sut-app-main` top padding 1rem, invoice card padding `md`, `space-y-4` on three tabs, toolbar `py-2`, chat bar `py-1` and `mb-3`) reach 286. The content width is unchanged.
- The component default dock stays `center` (seven existing static-markup tests); the collapsed default lives in the store. `components/ui/PatientSearch.tsx` is kept (dead code, delete later).

Not run: Node 20 and GitHub CI; `npm run lint` over all of `src`; backend pytest (forbidden in this lane); a real LLM key (opening the panel with live answers and chat error states; the endpoint was stubbed); the developer identity; Wave A evidence (not rendered locally, so Phase 2 page-height targets cannot be judged); the split-pane Source drawer; Reference Tools Drugs and Materials past page 1; a pixel-by-pixel visual review (four screenshots were looked at: Patients, patient 0003, the split view, the deep link); the five injected-defect checks of the scout were not repeated (one was); the 390 px capture beyond the three-load height check.

Cleanup: backend (18001) and `next start` (13000) stopped by PID, both ports free; `frontend/.next`, `tsconfig.tsbuildinfo` and the scratch captures under `~/.cache/ui-capture-tmp/p1` removed. Known limits for the PR: a user with a saved non-default dock sees the collapsed bar between the server HTML and hydration (a cookie would avoid it); the dock does not sync between browser tabs; Quick Open returns at most 8 results and none before a character is typed (the removed card listed 20).

## Task: App UI overhaul, phase 1 fixer round: review findings (2026-10-07)

### Goal
Each blocking finding of the phase-1 review is either fixed with a measured result or answered with a measured reason, and the page-frame behaviour of the collapsed default (layout class, saved dock, split-view rule, sidebar first width) is pinned by tests that fail when it is broken.

### Subtasks
- [x] Verify each finding on a production build of `78f7b0f2` (backend 18001, frontend 13000, synthetic cohort): finding 2 (right dock header) and finding 3 (patient select) reproduced with the numbers of the review; finding 1 reproduced in the code, the API payload and the phase-0 baseline text; findings 4 and 5 reproduced by mutation.
- [x] `SutInlineAIPanel`: the header row wraps (`flex-wrap`), the control group sits at the end (`ml-auto`), so four controls beside "Patient: <id>" never run past the viewport edge; a test pins the markup.
- [x] `CohortFilterBar`: patient select 310 px with `pr-3`, sex 116 px (`min-w-0`), age 112 px, doctor 120 px, plus a `title` with the full label; a test pins widths, padding and title.
- [x] Tests for the default-state layout class: patient page (collapsed, center, right, embedded) in `page.panes.test.tsx`, new `app/page.test.tsx` (also the `allowRightDock` rule of the home page).
- [x] Tests for the restore half of the dock: new `navigationContext.test.tsx` (saved dock applied after the first render, never written back, unknown value gives the default, blocked storage), `WorkspaceSplitLayout.test.tsx` (right becomes centre without a write), `AppSidebar.test.tsx` (saved right dock gives the 64 px rail from the first paint).
- [x] Mutation checks of every new test (13 mutations, all caught); tsc, vitest, build.
- [x] Browser checks of the fixes on the final build in EN and TR at 1440 and 1280, single pane and split pane; pixel check that no filter control clips its own text; widths 360 to 1024 for horizontal scroll.
- [x] Full capture of the final tree (188 states) compared with the baseline and with the capture of `78f7b0f2`; it caught that a fixed 310 px select made 20 states scroll sideways at 390 px, so the patient select is `w-full` below 640 px.
- [ ] Finding 1 (frontend "0.00 TRY" from a sum of nulls) is NOT fixed in this phase; see Review.

### Out of Scope
Finding 1 (`complianceBilledAtRisk` / `audit_exposure_try ?? 0`, present on `main`, changes a shown amount, so it belongs to Phase 2 where the figures move into the summary row); the P3 items of the reviews (focus after Open, two tab stops in the bar, contrast, cookie for the saved dock, sidebar width of a saved right dock inside a split view, deep-link scroll margin); backend, rules, amounts, exactness, API shapes; Phase 2 and later.

### Review (2026-10-07, fixer round)
Findings, one by one (each re-run on a production build of `78f7b0f2`: backend 18001, frontend 13000, synthetic cohort of 50, Chrome 154):
- Honesty P2, `complianceBilledAtRisk` (`lib/workspaceViews.ts:90-96`, used at `ComplianceViewSection.tsx:72,95`, and `audit_exposure_try ?? 0` at :73): correct, and not caused by Phase 1. Live API for SENTETIK-HASTA-0003: the 4 `billing_strategy` compliance findings and the `drug_indication` finding all have `billed_try` and `audit_risk_try` null, so the card prints "Billed amount at risk 0.00 TRY" from a sum of nulls (`sum + (billed_try ?? 0)`); the phase-0 baseline `text/en/1440x900/patient-0003/default.visible.txt:113-114` already has the same pair. NOT fixed here, by decision: it changes an amount that is on screen (the baseline would no longer match, which is the proof this phase relies on), it is a calculation-level change in a figure Phase 2 moves into the new summary row anyway, and the owner limited this phase to the page frame. Phase 2 must show a dash or "unavailable" (not 0.00) for `complianceBilledAtRisk` when no at-risk action carries a billed amount, and for `audit_exposure_try` when it is null, with a test that feeds null amounts and asserts no "0.00".
- UX P2, right-dock header cut off on the patient page: correct. Before: "Dock right" at x 1420-1448 of a 1440 viewport (8 of 28 px outside) in EN, 1441 in TR, panel scrollWidth 387 > clientWidth 378. Fix: the header row wraps (`flex-wrap`, control group `ml-auto`, title block `min-w-0`), so the four controls take their own row when the subtitle is long. After, EN and TR, 1440 and 1280, patient page and home tab: the last button ends at 1419 (1259 at 1280), scrollWidth equals clientWidth (378), nothing outside. In a split pane (no right dock) the open card keeps its controls on the title row at 570 px (EN 1440) and 490 px (TR 1280), seen in screenshots.
- UX P2, patient select cuts its label: correct, and the suggested fix is not enough. The review's text widths are right (EN 219 px, TR 238 px, widest of the cohort 220 and 239 for SENTETIK-HASTA-0032), but Chrome's native select reserves room for its arrow on top of the CSS padding. A pixel compare of the control against a 250 px wider twin shows the Turkish label still cut at 290 px and at 300 px with the default `pr-8`, intact from about 310 px, and intact from about 288 px with `pr-3`. Chosen: 310 px with `pr-3` (about 22 px to spare), sex 116 px (`min-w-0`), age 112 px, doctor 120 px, so the row with "Clear filters" and the chip still fits one line at 1280 px; the select also gets a `title` with the full label. Below 640 px the patient select is `w-full` (a fixed 310 px made 20 states scroll sideways at 390 px; found by the capture metrics, not by the first probe). Checked: 96 controls (24 states: EN and TR, 1440 and 1280, Patients, Compliance and Revenue, patients 0003, 0032, 0040, 0006, with a patient and a sex filter active), 0 clipped, toolbar 77 px (one row) in all; a negative control with the select forced to 250 px is flagged in EN and TR; widths 360 to 1024: no horizontal page scroll. At 360 to 430 px the closed select is 214 to 284 px wide, so a long label is still cut there (tooltip only); phones are Phase 7.
- Regression P2, no test for the layout class of the default state: correct (mutations M1, M2 passed 711 tests). Added: patient page (collapsed, center, right, embedded) in `page.panes.test.tsx`; new `app/page.test.tsx` for the home page (also its `allowRightDock`).
- Regression P2, restore half of the dock and the split-view rule untested: correct (M4, M5, M6 passed). Added `stores/navigationContext.test.tsx` (the saved dock is applied after the first render and never written back; unknown value, empty value and blocked storage give the default), `components/shell/WorkspaceSplitLayout.test.tsx` (right becomes centre with no storage write; collapsed and centre untouched; no change without a split), `components/shell/AppSidebar.test.tsx` (a saved right dock gives the 64 px rail and `--shell-sidebar-width` 64px from the first paint; 220 px otherwise; the user's own collapse wins).
- Mutation checks (scratch edits of the source, restored from the index): M1 patient page `chatDock !== "center"`, M2 same on the home page, M4 provider ignores the saved dock, M5 split layout uses the persisting action, M6 sidebar ignores the saved dock, M10 and M11 `allowRightDock` always true (home and patient page), M12 header no longer wraps, M13 patient select 250 px, M14 no `title`, M15 fixed 310 px on phones, M16 default select padding, M17 sex select min width back: all 13 fail the new tests.

Results:
- Gates (Node 22.16.0; CI uses Node 20 and stays the arbiter): `npx tsc --noEmit` exit 0; `npx vitest run` 95 files / 737 tests passed (91 / 711 before: 4 new files, 26 new tests); `npm run build` exit 0; `npx eslint` on the 9 touched files: 1 problem, the existing `react-hooks/set-state-in-effect` at `CohortFilterBar.tsx:48` (and the jsx-ast-utils notice from the existing JSX comment inside `trailing`); `git diff --check` clean.
- Full capture of the final tree (`node scripts/capture-screens.mjs`, 188 states, no failed route, the same 2 skipped states): `--compare lanes/ui/baseline <run> --strict-multiplicity --strict-labels` exit 0, 188 states, 0 failures, 0 warnings. What that proves and what it does not: it compares the set of amounts, counts, percents and uncertainty wording per state, and the standalone amounts under their labels (about 10 percent of the amounts); amounts inside table rows, bill chips and prose are compared as a set, so a swap between rows would not fail it, clipped text counts as visible, and it does not see controls, order, the tab strip, width or the saved dock. Because of that: the `numbers` folder (188 files) and the `text` folder (376 files) are byte-identical to the capture of `78f7b0f2`, whose rows and columns the honesty review compared by hand against the baseline (patients 0003, 0017, 0029, every state, EN and TR). This round restructures no table, bill picker, findings row or summary row; it changes widths, one header row and tests.
- Metrics against the capture of `78f7b0f2`: all 96 files at 1440x900 and 1280x800 are identical (money wraps 838, overlaps 37, clipped 2,702, horizontal scroll flags 8, the same totals). At 390x844 the 20 filter-bar states (Patients, Compliance with its 7 sub-views and Revenue, EN and TR) are 69 or 70 px shorter, and no state changed its horizontal scroll flag; `deepLink.top` differs, as the capture README says it may.
- Browser probes are scratch scripts outside the repo (right-dock header, select pixel check, narrow widths 360 to 1024, split pane with the chat open, home tab with a split pane: toolbar 189 px high in a 610 px pane, no overflow).
- Not run: Node 20 and GitHub CI, `npm run lint` over all of `src`, backend pytest (forbidden in this lane), a real LLM key (chat stubbed), Wave A evidence, Safari and Firefox, Windows and macOS scrollbars, a phone or tablet device, the P3 items of the reviews.
- Cleanup: backend (18001) and `next start` (13000) stopped by PID, ports free; `frontend/.next` and the scratch captures under `~/.cache/ui-capture-tmp` removed.
