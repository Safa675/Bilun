## Task: Agent memory env + relocate

### Goal
mem0 LLM URL/model env’den okunur; paket `scripts/agent/memory/` → `agents/memory/` taşınır; PR `main`’e, **pull yok**, local silmeler PR’a girmez.

### Subtasks
- [x] Plan: `plans/tooling/agent-memory-env-and-relocate.md`
- [x] Branch from `origin/main` (worktree; no pull)
- [x] `agents/memory/` + env LLM config + `agents/__init__.py`
- [x] Update `agents/.env.example`, prompts, related plans
- [x] Delete `scripts/agent/memory/`
- [x] Smoke import / clear error without `Z_API_KEY`
- [x] Commit + PR — https://github.com/Safa675/Bilun/pull/45
- [x] Resolve `tasks/todo.md` merge conflict with main (#44)

### Out of Scope
- Moving `scripts/agent` checkers
- User’s unrelated local deletions / login WIP
- `git pull`

### Review
- Worktree from `origin/main`; **no pull** of local dirty worktrees.
- LLM block reads `MEM0_LLM_BASE_URL` / `MEM0_LLM_MODEL` / `MEM0_LLM_PROVIDER`.
- Call path: `python -m agents.memory.{load,save}`.

---

## Task: SUT pipeline cleanup PR (A+B+C) — DONE (#44)

### Goal
Hard-delete spent SUT pipeline debris after #43 on branch `chore/sut-pipeline-cleanup`. CI green; no intentional opaque-identity changes.

### Subtasks
- [x] Hard-investigate Slice C keep/delete
- [x] Branch `chore/sut-pipeline-cleanup` from main
- [x] Slice A: delete backfill / _split_generators / restamp; docs; dead compile append/shared
- [x] Slice B: rewrite payment/copay/material tests → delete facades
- [x] Slice C: delete material export CLIs + R5 test; drop sync subprocesses; thin drug CSV export; rewrite/drop related tests
- [x] Verify zero imports of deleted modules; pytest + compile --check
- [x] Open PR — https://github.com/Safa675/Bilun/pull/44 (merged)

### Out of Scope
- `_PAYMENT_SESSION_MANIFEST_STUB` (live coverage) — KEEP
- `infer_defer_themes` / `_encode_tier` / `_heuristic_inn` — KEEP
- Collision YAML C* / parquet clause_id / Fatura F* / migrate tool / wave C* inventories
- Frontend dead-code

### Slice C decision (investigated)
| Item | Verdict |
|------|---------|
| material export CLIs ×3 + R5 triage test | **DELETE** — gitignored CSVs; not compile path; only sync/tests |
| sync_gate_b_in_force L1.4 subprocesses | **REWRITE** — drop those runs |
| drug_indication_gate_b CSV/`__main__` | **THIN** — keep primitives |
| `_PAYMENT_SESSION_MANIFEST_STUB` | **KEEP** — live sibling manifest |

### Review
- Slice C investigated: material export CLIs not on compile path → hard-delete; drug module thinned to primitives; payment stub kept.
- A+B+C implemented on `chore/sut-pipeline-cleanup`. Focused pytest 60 passed; `compile_rules.py --check` green; zero py imports of deleted modules.
- Intentionally left: collision YAML C*, parquet clause_id, Fatura F*, migrate tool, wave C* inventories, `_PAYMENT_SESSION_MANIFEST_STUB`.
- Merged via #44.
