# Lessons

Persistent lessons captured from corrections during work. Reviewed at the start of every session per AGENTS.md §1.

Format per entry:
- Date
- Mistake pattern (not just the incident)
- Rule that prevents recurrence

---

## 2026-06-19 — Don't advise on a subsystem's data dependencies without reading the compute path

**Pattern:** When asked "do I need to rebuild the cache after the SUT replace?", I correctly identified the stale-process issue but hedged the *correctness* answer with "the rebuild may not visibly change much because claim lines carry their own billed_amount." That hedge was unverified speculation — I hadn't yet traced whether the DRG compute path actually reads EK-2C. When I finally did trace it (`src/bilun/domain/analytics/drg.py:196 get_ek2c_price_for_date`), it confirmed DRG pricing DOES depend directly on the rebuilt EK-2C catalog. So the cache rebuild IS a correctness requirement, not optional — my hedge downplayed a real staleness bug (later confirmed as audit finding B-C2/B-C7: no staleness detection mechanism exists). The backend audit (3 parallel subagents) later surfaced that the entire read-write-connection + no-staleness-check architecture means stale data is served silently with no self-healing.

**Rule:** Before advising whether a data-source change requires a downstream cache/recompute rebuild:
1. Read the actual compute path that produces the cached artifact — grep for `read_parquet` / `get_ek2*` / catalog lookups in the domain layer, not just the cache layer's `data_loader.py` (which only reads patient/cohort parquets, not gazette catalogs).
2. Distinguish "cache reads gazette catalogs directly" (rebuild definitely needed) from "cache only reads pre-computed patient summaries" (gazette changes are baked in at build time, so rebuild still needed).
3. Never hedge with "may not change much" without a concrete trace showing the dependency is absent. If you haven't traced it, say "I need to verify whether the DRG compute reads EK-2C" — don't guess.
4. A running process holding a DB lock is ALWAYS a stale-data signal worth surfacing prominently, not a footnote — DuckDB single-writer semantics mean that process has the pre-rebuild data in memory and will serve it until killed.

---

## 2026-06-19 — Latent pipeline bugs surface during data-source swaps; verify the full chain end-to-end

**Pattern:** Replacing the active SUT tebliği (2026.01.17 → 2026.04.08) exposed TWO pre-existing latent bugs that were invisible as long as the committed parquets were never rebuilt: (1) `xlrd` was never declared in `requirements.txt`/`pyproject.toml`, so all `.xls`-sourced annexes (EK-1A, EK-3B-1/2, EK-3C-1, EK-2Ç) silently failed conversion — the committed parquets were artifacts from a prior machine that had xlrd. (2) `_find_raw_parquet` (`scripts/sut/_common.py`) deliberately skipped `effective_date=unknown` partitions, which broke EK-1A (legitimately undated `.xls`, no date in filename) even though its raw parquet existed. Both only surfaced when the full pipeline ran fresh.

**Rule:** A "data source swap" (new tebliği, new SUT package, new cohort) is never just a file replacement — it is a **full-pipeline smoke test**. Before declaring the swap done, run the *entire* chain fresh (convert → curate → extract → load) and verify EVERY catalog/annex produced non-zero output, not just the ones that passed. Specifically:
1. After `convert_xlsx_to_parquet.py`, check the "Failures: N" line — if N > 0, read the failure reasons before proceeding; they are usually a dependency gap (`xlrd`, `odfpy`), not a data problem.
2. After `build_curated_catalogs.py`, grep for `[!!]` / `FAIL` / `missing` — a silently-empty curated catalog (0 rows) means an upstream annex wasn't found, even if conversion reported success.
3. A committed parquet that can't be rebuilt from declared dependencies is a **lie in git** — always confirm `pip install -r requirements.txt` on a clean venv reproduces every committed artifact.
4. When a lookup filter has a "skip X" rationale comment (like `unknown` partitions here), check whether X can legitimately apply to in-scope data before trusting the skip.

---

## 2026-06-19 — "Değişiklik tebliği" (delta) ≠ "İşlenmiş Güncel SUT" (consolidated) — don't patch rules from delta text

**Pattern:** After downloading the 23.05.2026 SUT tebliği, I initially assumed it was a full SUT and proposed patching BILUN's `drug_indication_prose.json` directly from its delta text. Reality: the download was a 1675-word Resmî Gazette delta (only MADDE 1-10 changes), NOT a consolidated SUT. BILUN's rule encoder workflow extracts rules from the *full consolidated SUT docx* via `extract_sut_prose.py` + human golden-file review — patching a hand-curated rule from delta text bypasses that review, sources from a non-canonical document, and risks stylistic mismatch.

**Rule:** Before touching any rule JSON, classify the source document first:
1. **Consolidated ("İşlenmiş Güncel 2013 SUT")** = full integrated text, ~1MB docx + EK folders. This is the ONLY valid input for the normal encoder pipeline (`extract_sut_prose.py` → clause corpus → hand-curated rule JSON). A new one warrants a full pipeline replace.
2. **Delta ("Değişiklik Yapılmasına Dair Tebliğ")** = Gazette article listing only the changed MADDE'ler (typically a few KB / few hundred words). NEVER use as a direct rule source. Its purpose is to tell you *what changed* so you can (a) flag affected rules for the next consolidated package, and (b) write a changelog entry.
3. Verify which you have by file size and content: a 30KB docx with "MADDE 1-..." headers is a delta; a 1MB docx with full BÖLÜM/§ structure is consolidated. A folder named `YYYY.MM.DD-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` containing EK subfolders is consolidated; a lone `.docx` named `...Delta...` or a raw Gazette UUID filename is a delta.
4. When a delta touches a BILUN rule, the correct action is to document it as "pending next consolidated package" in `docs/gazette/changelog.md`, NOT to hand-patch the rule.

---

## 2026-06-19 — Don't infer document content from the filename (EK-4B "diyaliz" hallucination)

**Pattern:** Recommending "ingest EK-4B to fill the dialysis gap" based purely on the annex filename/title, without reading the file or even the repo's own README. The repo README (`EK-4 LİSTELERİ/README.md:18-24`) states EK-4B is *special diet products / medical nutritionals (PKU, cystic fibrosis, cow's milk allergy)* — ~76 rows, niche pharmacy scope. Dialysis materials live in EK-3 nephrology (`ek3p_nephrology_materials.parquet`), which is already loaded. Same error class: earlier in the same session I also claimed EK-1B contained a "yatak bedeli tariff" from its title, when it is a blank per-patient invoice template (`İşlem tutarı` rows empty). Both were filename-to-content inference failures.

**Rule:** Before claiming a raw-data file contains extractable tariff/rule data — or proposing it to fill a named gap — do BOTH:
1. Read the repo's own inventory (the auto-generated `raw data/.../README.md` files are the canonical source of what each EK annex actually is, including row counts and column lists).
2. Extract the actual file content (libreoffice/pdftotext/pandas) and confirm the rows are populated, not a blank form/template.
A filename like "HAST. SUN. HİZM. VE İLAVE ÜCR" describes a *form's purpose*, not its data contents. SGK annexes split into (a) real tariff tables (.xlsx with data) and (b) blank form templates / patient consent docs (.doc/.docx). Only (a) is worth building a loader for. The audit subagent already correctly labeled EK-1B/EK-1E/EK-4B as "form/template" — trust that classification; don't re-interpret titles as data.

---

## 2026-06-19 — Prefer `ss` over `lsof` for port/PID lookups on this host

**Pattern:** AGENTS.md §5 prescribes `lsof -t -i :PORT` for the zombie-process check. On this host `lsof` fails to report the `next-server` process holding a LISTEN socket on port 3000 (returns empty, exit 1), even though the process is clearly bound. The user ran `kill -9 $(lsof -t -i :3000)`, got an empty PID list, and `kill` failed with "usage" — leaving the stale next-server alive and causing repeated `EADDRINUSE: address already in use :::3000` on `./start.sh`. `ss -ltnp "sport = :PORT"` (reads procfs) reliably surfaced the same PID.

**Rule:** For port-to-PID resolution on this machine, use `ss -ltnp "sport = :PORT" | grep -oE 'pid=[0-9]+'` as the primary tool; treat `lsof` as a fallback only. `start.sh`'s `pids_on_port` is already ordered `ss` → `lsof` → `fuser`. When a port shows EADDRINUSE but `lsof` returns nothing, switch to `ss` before concluding the port is free. Also, Next.js spawns a process tree (`sh -c next dev` → `node next dev` → `next-server`); killing only the listening PID can leave orphans that respawn — sweep with a path-scoped `pgrep`/`kill_stray_bilun_dev` after freeing the port.

---

## 2026-06-19 — Feed commit messages from a file, not a -m string, when they contain backticks

**Pattern:** Using `git commit -m "..."` with a multi-line message that contains backtick-quoted code tokens (e.g. `` `t` ``, `` `loading` ``). Bash inside the tool shell interpreted the backticks as command substitution, ran the token as a command (`/bin/bash: line 1: t: command not found`), and silently dropped the token from the committed message. The commit succeeded but the message was garbled; only caught by re-reading `git log -1 --format='%B'`.

**Rule:** When a commit message contains backticks (or any shell metacharacters like `$`, `` ` ``, `\`), do NOT pass it via `git commit -m`. Instead:
1. Write the message to a temp file with the Write tool.
2. `git commit -F <file>` (or `git commit --amend -F <file>` to repair).
3. Remove the temp file.
4. Always verify with `git log -1 --format='%B'` before declaring the commit done.
For simple messages with no metacharacters, `-m` is fine.

---

## 2026-06-14 / 2026-06-16 — Don't declare a runtime missing just because it isn't on PATH (REPEATED — rule strengthened)

**Pattern:** Running `npm --version` and getting "command not found", then telling the user Node/npm are not installed, when in fact Node v22.16.0 and npm 10.9.2 were present at `/home/safa/.local/node-v22.16.0-linux-x64/bin` but that directory was not in `PATH`. This was repeated on 2026-06-16 despite an existing lesson.

**Rule:** Declaring a tool/runtime unavailable is a positive claim — it requires evidence, not just a PATH miss.
1. First check: run `which <tool>` and `<tool> --version`.
2. If that fails, check known installation locations: `ls ~/.local/*/bin`, `/opt`, `/usr/local/bin`.
3. If found anywhere, prepend its `bin` directory to `PATH` and rerun the check.
4. Only conclude "not available" after steps 1–3 all fail.
5. When a prior lesson already covers this, re-read `tasks/lessons.md` before asserting the same failure again.

## 2026-06-14 — Never claim AI/LLM usage without reading the implementation

**Pattern:** Telling a user that a script “uses LLM calls” based on its docstring/output shape without opening the actual implementation. `scripts/sut/extract_sut_prose.py` and its `scripts/sut/prose/extractor.py` use deterministic regex and DOCX XML parsing, not LLMs.

**Rule:** Before asserting that any component uses AI, LLMs, embeddings, or an external model, grep the source for provider names/APIs (`openai`, `anthropic`, `gpt`, `claude`, `embed`, `transformer`, etc.) and read the implementation. If uncertain, say “I have not verified this” instead of asserting.

## 2026-05-27 — Plan before code (AGENTS.md §7)

**Pattern:** Starting a refactor or rebuild by inspecting files and writing prose without first capturing the plan in `tasks/todo.md`.

**Rule:** For any task that touches 3+ files or sets up a new system, the first artifact is `tasks/todo.md` with the structure from §7. Code writes wait until the plan is in place.

## 2026-05-27 — Premium UI is quiet, not decorated

**Pattern:** Defaulting to glassmorphism, accent-tinted glows, radial gradient backgrounds, marketing hero panels inside the product, and the brand color used for status + action + decoration simultaneously. This reads as "AI startup template", not premium SaaS.

**Rule:** When asked for premium SaaS feel:
1. One color reserved for action/focus only — never for backgrounds, never for status
2. Status semantics are separate tokens, never the brand color
3. No backdrop-blur, no glow shadows, no accent-tinted shadows, no radial gradient backgrounds
4. Motion budget: one easing, one duration (~120ms), hover/focus only — no entry animations in workspaces
5. Content over self-description: the product never explains itself inside itself
6. No `premium` in class names. Real premium products don't label themselves premium.

## 2026-05-27 — Verify font loading, don't just declare CSS variable

**Pattern:** Declaring `--font-sans: "Plus Jakarta Sans"` in CSS without loading the font via `next/font`. Browsers fall back to system fonts and the designed font never renders, but it looks like it's wired up.

**Rule:** Web font loading requires both: (1) `next/font/google` (or equivalent) import in `layout.tsx` that injects the `@font-face` and exposes a CSS variable, (2) the CSS variable referenced in `font-family` declarations. Verify by inspecting computed font in DevTools, not by reading the CSS.

## 2026-05-27 — Inventory before deleting CSS

**Pattern:** Estimating "this class is probably unused" and deleting it, then breaking a page in a corner of the app that was never opened during testing.

**Rule:** Before deleting or rewriting CSS class rules at scale, build an evidence-based inventory: extract every `.class-name` from the stylesheets, grep every `.tsx/.ts/.css` (excluding the stylesheets themselves) for each name, and partition into used/unused. Delete only the unused set outright; for the used set, rewrite the rule without changing the selector. Never delete a selector that still has JSX references — move its rule into a clearly-labeled transitional file instead.

## 2026-05-27 — `useSyncExternalStore` for browser-state subscriptions

**Pattern:** Writing a React hook that subscribes to `localStorage` (or any browser-only store) with `useState` + a `useEffect` that calls `setState(read())` on mount. ESLint's `react-hooks/set-state-in-effect` correctly flags this — it forces a double render (SSR snapshot, then mount snapshot) and races with concurrent rendering.

**Rule:** For any value that comes from a browser-only store (localStorage, sessionStorage, matchMedia, IndexedDB) and needs to drive React UI, use `useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)`. The server snapshot is `[]` / a stable empty value; the client snapshot reads the store on demand. Cache the snapshot by the underlying raw value to keep `getSnapshot` referentially stable (otherwise React tears).

## 2026-06-06 — Flatten filled PDFs when viewer focus changes appearance

**Pattern:** Filling AcroForm text fields and only adjusting `/DA` font metadata can still fail because PDF viewers redraw editable field contents on focus using their own form-rendering behavior.

**Rule:** When the deliverable is a final application PDF and the user reports font changes after clicking fields, generate a flattened copy: draw text directly onto the page with an embedded font that supports the required language, then remove form widgets. Do not keep editable fields unless editability is explicitly required.

## 2026-05-27 — Style file collapse needs a transitional layer

**Pattern:** Trying to delete a large legacy stylesheet (`sut-premium.css`) and reduce `globals.css` to <200 lines in a single phase while pages still reference the legacy classes — would break every page mid-phase.

**Rule:** When collapsing stylesheets across multiple phases, the immediate phase deletes dead rules + strips chrome from live rules, but moves the live rules into a clearly-labeled `legacy.css` (transitional) that the global stylesheet imports. Subsequent phases burn down `legacy.css` by reskinning the pages that depend on its selectors. The legacy file is only deleted once its imports are gone from all JSX. This prevents a "big bang" CSS rewrite from breaking unrelated pages.

## 2026-05-27 — Wrap legacy reskins, don't tear them open

**Pattern:** Faced with a 6-section file (`BillingSectionShell` used by Lab/Drug/Copay/Strategy/Materials/SutOptimization), the temptation is to rewrite each call site to use `<Section>` directly. That's six dangerous diffs across an 880-line file, easy to miss a wrapper, easy to break tests that assert exact strings.

**Rule:** When a private helper is reused by multiple call sites in the same file, **rewrite the helper's internals** rather than its call sites. Keep the helper's signature stable, and swap its body to wrap the new primitive. The diff stays small (~10 lines), every call site picks up the new chrome automatically, and the existing test fixture continues to validate the integration. Tear the wrapper open in a later phase only after confirming the new look is right.

## 2026-05-27 — `next build` poisons the dev-mode cache; clear `.next` before probing

**Pattern:** Running `npx next build` and then `npx next dev` against the same project produced HTTP 500 on every route with Turbopack panicking on "ArrayLengthMismatch / corrupted database" cache deserialization errors. Initial instinct was to debug the app — actual root cause was build/dev artifact conflict in `.next/`.

**Rule:** When dev-mode 500s show Turbopack/Webpack internal errors mentioning "task data", "corrupted database", or "incompatible version" — kill all `next dev` processes, `rm -rf .next/`, then restart. Don't read application code looking for the bug. This is the disk-cache equivalent of AGENTS.md §5's zombie-process check: read the actual error message, kill the artifact, restart cleanly.

## 2026-05-27 — Two-gold rule must be checked at the page level, not the component level

**Pattern:** A component-by-component reskin can each apply "one italic-gold accent" honestly, but the page that composes those components ends up with five gold uses (H1 word + KPI value + section total + savings cells + status chips), violating the deck contract.

**Rule:** The "max 2 italic-gold serif uses per screen" rule is a **page-level invariant**, not a component-level one. When a page composes multiple primitive instances, audit the rendered page for italic-gold uses and pick the two with the highest information value (typically: one H1 word + the single primary KPI money amount). All other "gold candidates" (table savings cells, section totals, secondary KPIs, success chips) must drop to navy tabular. Gold chip backgrounds (`<Chip variant="gold">`) and gold *tinted* backgrounds are not counted under this rule because they aren't Fraunces italic display type.

## 2026-05-30 — Chat auto-brief effect must not depend on streaming store writes

**Pattern:** Removing briefing dedup while persisting every SSE token to Zustand recreated `onChatStateChange` each render, retriggered the auto-brief `useEffect`, aborted in-flight requests, and spammed `/api/chat` until 429 — UI stuck on the empty placeholder.

**Rule:** Auto-brief triggers only on `[patientId, activeTab]` via a ref to `fireAutoAnalysis`. Stream tokens into local state; persist messages once on completion. Memoize `onChatStateChange` at the route level. Guard against concurrent in-flight auto requests.
