# Agent memory: env LLM config + `agents/memory` relocate

**Branch:** `chore/agent-memory-env-relocate` (from `origin/main`; **no `git pull`** — local deletions must not be restored)  
**Goal:** mem0 LLM endpoint/model env’den okusun; agent memory ürün `scripts/` ağacından çıksın.

---

## Why

1. `scripts/agent/memory/config.py` içinde `glm-4.6` + `https://api.z.ai/api/coding/paas/v4` sabit. Z coding plan değişince URL/model kod patch ister.
2. Agentic workforce (OpenHands employee agents) ürün pipeline’ı değil; `scripts/sut/` ile aynı ağaçta durmamalı. Yer: `agents/memory/` (yanında role prompt’ları var).

---

## Scope

### In

- Move `scripts/agent/memory/{__init__,config,load,save}.py` → `agents/memory/`
- Add `agents/__init__.py` (empty) so `python -m agents.memory.load` works
- LLM config via env (with safe defaults matching today’s Z coding plan):
  - `Z_API_KEY` (already required)
  - `MEM0_LLM_BASE_URL` (default: current z.ai coding paas URL)
  - `MEM0_LLM_MODEL` (default: `glm-4.6`)
  - `MEM0_LLM_PROVIDER` (default: `openai` — OpenAI-compatible client)
- Update `agents/.env.example` with the new vars + short comment
- Update call sites:
  - `agents/reimbursement/system-prompt.md`
  - `plans/tooling/mem0-integration-design.md` (path notes)
  - `plans/deployment/vps-openhands-smoke-test.md` (path check)
- Fix `PROJECT_ROOT` after move (`parents[2]` from `agents/memory/`, not `parents[3]`)
- Delete old `scripts/agent/memory/` package (no long-lived shim — update refs in same PR)

### Out of scope

- Moving `scripts/agent/*.py` checkers (`stale_clause_refs`, `pipeline_smoke`, …) — later optional
- Changing embedder / Qdrant layout
- Docker-compose for mem0 (still not required; on-disk Qdrant stays)
- Touching user’s unrelated local deletions (raw SUT packages, plans cleanup, login WIP, etc.)
- `git pull` / resetting local deletes

---

## Subtasks

- [x] Plan + `tasks/todo.md`
- [x] Create branch from `origin/main` without pull (worktree)
- [x] Implement `agents/memory/` + env-driven LLM block
- [x] Update `.env.example` + prompts/docs paths
- [x] Remove `scripts/agent/memory/`
- [x] Smoke: `build_config` without key → clear error; env override; imports
- [ ] Commit only memory/relocate files; open PR → `main`

---

## Env contract (after)

```bash
Z_API_KEY=...                         # required
MEM0_LLM_BASE_URL=https://api.z.ai/api/coding/paas/v4   # optional override
MEM0_LLM_MODEL=glm-4.6                # optional override
MEM0_LLM_PROVIDER=openai              # optional
MEM0_DATA_DIR=/var/lib/bilun-mem0     # optional (already documented)
```

Usage:

```bash
python -m agents.memory.load --role reimbursement_engineer
python -m agents.memory.save --role reimbursement_engineer --report reports/agent/reimbursement/findings-….md
```

---

## Risk / notes

- Sandbox still needs `Z_API_KEY` forwarded into OpenHands agent env (existing lesson).
- Default URL/model keep current behavior if env unset — plan change = env-only.
- PR must not include bulk `raw data/` deletions from the dirty worktree.
