#!/usr/bin/env python3
"""Run Tier-C Bucket B, C, D encode waves in order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    scripts = [
        _REPO / "scripts/sut/encode_tier_c_bucket_b.py",
        _REPO / "scripts/sut/encode_tier_c_bucket_c.py",
        _REPO / "scripts/sut/encode_tier_c_bucket_d.py",
    ]
    for script in scripts:
        print(f"\n=== {script.name} ===")
        rc = subprocess.call([sys.executable, str(script)])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
