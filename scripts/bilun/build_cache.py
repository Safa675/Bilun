"""BILUN canonical analytics-cache rebuild CLI entry point."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from src.bilun.cache.builder import parse_args, run_build

if __name__ == "__main__":
    args = parse_args()
    build_id = run_build(args)
    print(f"Build complete: {build_id}")
    sys.exit(0)
