## Task: Optimize CI Speed (setup-uv + pytest-xdist)

### Goal
Speed up GitHub Actions backend CI from ~6 minutes down to ~1.5 minutes by adopting `astral-sh/setup-uv@v5` with caching and running `pytest` in parallel with `-n auto`.

### Subtasks
- [x] Update `.github/workflows/ci.yml` backend job with `setup-uv@v5` (cache enabled) and `pytest -n auto -q`
- [x] Verify workflow YAML syntax and local compatibility
- [x] Commit changes to `experiment/workspace-shell`
- [x] Push to GitHub and observe CI execution duration on PR #69

### Review
- Backend dependency installation migrated from `pip` (34s) to `uv` (~2s).
- Test execution parallelized across runner cores via `pytest -n auto` (275s -> ~60s).
