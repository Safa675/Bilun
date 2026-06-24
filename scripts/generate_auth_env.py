#!/usr/bin/env python3
"""Generate the three auth env vars for the shared-password gate.

Usage:
    python scripts/generate_auth_env.py <username> <password>

Prints BILUN_AUTH_USERNAME, BILUN_AUTH_PASSWORD (PBKDF2 hash), and
BILUN_SESSION_SECRET (random), ready to paste into .env.

The password is never printed in plaintext — only its hash. The session secret
is freshly random on every run (rotating it revokes all existing sessions).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable so `from src.bilun.api.auth import ...`
# works when run from anywhere.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.bilun.api.auth import generate_session_secret, hash_password  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    username, password = sys.argv[1], sys.argv[2]
    if not username.strip() or not password:
        print("Error: username and password must be non-empty.", file=sys.stderr)
        return 2

    print("# Paste these into your .env (backend + frontend read the same vars).")
    print(f"BILUN_AUTH_USERNAME={username}")
    print(f"BILUN_AUTH_PASSWORD={hash_password(password)}")
    print(f"BILUN_SESSION_SECRET={generate_session_secret()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
