"""Shared mem0 configuration for the 3 employee agents.

Each agent (Reimbursement / Full-stack / Data Engineer) gets its own memory namespace
via mem0's `user_id` field. Cross-namespace isolation is enforced by mem0's filter
mechanism — verified 2026-07-20.

Storage layout:
- Qdrant vectors: `<MEM0_DATA_DIR>/qdrant/` (local disk, no server needed)
- SQLite history: `<MEM0_DATA_DIR>/history.db`
- MEM0_DATA_DIR defaults to `reports/agent/.mem0/` (gitignored, persisted on host via
  the reports/ :rw mount when run inside the OpenHands sandbox).

LLM: Z-API GLM-4.6 (cheaper than 5.2 — fact extraction doesn't need deep reasoning).
Embedder: BAAI/bge-small-en (local, CPU-runnable, 384-dim, no API, ~130MB one-time download).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Valid role namespaces — enforced to prevent typos leaking into mem0.
ROLES = ("reimbursement_engineer", "fullstack_engineer", "data_engineer")

# Where Qdrant + SQLite history live. MUST be on a writable mount.
# Priority:
#   1. MEM0_DATA_DIR env var (explicit override)
#   2. /workspace/reports/.mem0  (the OpenHands sandbox :rw reports mount)
#   3. <repo>/reports/agent/.mem0 (laptop fallback — repo is writable locally)
# The repo is :ro inside the sandbox, so we check the sandbox path first.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SANDBOX_RW = Path("/workspace/reports/.mem0")
if _SANDBOX_RW.parent.exists() and os.access(_SANDBOX_RW.parent, os.W_OK):
    _default_data_dir = _SANDBOX_RW
else:
    _default_data_dir = PROJECT_ROOT / "reports" / "agent" / ".mem0"
MEM0_DATA_DIR = Path(os.environ.get("MEM0_DATA_DIR", _default_data_dir))


def build_config() -> dict[str, Any]:
    """Build the mem0 config dict. Reads Z_API_KEY from env (never hardcoded)."""
    api_key = os.environ.get("Z_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Z_API_KEY env var not set. mem0 needs it for the LLM fact-extraction call. "
            "Set it in the sandbox env or pass via -e Z_API_KEY=... when launching."
        )

    MEM0_DATA_DIR.mkdir(parents=True, exist_ok=True)

    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": str(MEM0_DATA_DIR / "qdrant"),
                "collection_name": "bilun_agents",
                # CRITICAL: must match the embedder's output dim or searches crash with
                # "shapes (0,1536) and (384,) not aligned". bge-small-en = 384.
                "embedding_model_dims": 384,
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {"model": "BAAI/bge-small-en"},
        },
        "llm": {
            "provider": "openai",  # OpenAI-compatible — works with Z-API
            "config": {
                "model": "glm-4.6",
                "api_key": api_key,
                "openai_base_url": "https://api.z.ai/api/coding/paas/v4",
            },
        },
        # Disable mem0's graph memory (requires an extra LLM store we don't need) and
        # telemetry. Keep history_db so we can audit what was extracted.
        "graph_store": None,
        "history_db_path": str(MEM0_DATA_DIR / "history.db"),
    }


def get_memory():
    """Construct a configured Memory instance. Imports mem0 lazily so the rest of
    scripts/agent/ doesn't pay the import cost when mem0 isn't being used."""
    from mem0 import Memory
    return Memory.from_config(build_config())


def validate_role(role: str) -> str:
    """Validate + return the role namespace. Raises on unknown role (typo guard)."""
    if role not in ROLES:
        raise ValueError(f"Unknown role {role!r}. Must be one of {ROLES}.")
    return role
