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
- [ ] Commit only relocate files; open PR

### Out of Scope
- Moving `scripts/agent` checkers
- User’s unrelated local deletions / login WIP
- `git pull`

### Review
- Worktree from `origin/main` @ cb80207; no pull.
- LLM block reads `MEM0_LLM_BASE_URL` / `MEM0_LLM_MODEL` / `MEM0_LLM_PROVIDER`.
- Call path: `python -m agents.memory.{load,save}`.
