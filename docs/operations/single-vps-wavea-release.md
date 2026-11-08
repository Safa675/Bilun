# Single-VPS Wave A release (archived)

This runbook described the strict paired-release lane: `paired_release prepare|status|activate|rollback` for the backend/frontend pair on loopback 8001/3000, its signed Wave A activation receipt and its rollback. The lane was deleted on 2026-10-28; the git tag `archive/strict-lane` holds the scripts, the tests and the full text of this runbook (`git show archive/strict-lane:docs/operations/single-vps-wavea-release.md`).

The pair it last released (`5c89ed53`, ports 8001/3000) received no traffic after 2026-10-09 and was stopped and disabled on 2026-11-04; its bundle stays under `/root`. The current staging update is in [AI-RUNBOOK.md](AI-RUNBOOK.md) and [RELEASE-LANES.md](RELEASE-LANES.md).
