"""Write fresh developer credentials to a new owner-only environment file.

Run with --username and --output. Password input is hidden and never passed
on argv. --password-stdin is available for trusted automation. This command
does not modify any running service or enable public access.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
import sys

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def render_environment(username: str, password: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,128}", username):
        raise ValueError("Username must use letters, digits, dot, underscore, @ or hyphen")
    if len(password) < 16:
        raise ValueError("Use a new developer password of at least 16 characters")
    from src.bilun.api.auth import generate_session_secret, hash_password

    values = {
        "BILUN_AUTH_USERNAME": username,
        "BILUN_AUTH_PASSWORD": hash_password(password),
        "BILUN_SESSION_SECRET": generate_session_secret(),
        "BILUN_DEV_USERNAMES": username,
        "BILUN_SESSION_TOKEN_PURPOSE": "bilun-developer-v1",
        "BILUN_HEALTH_PROBE_TOKEN": secrets.token_hex(32),
        "BILUN_COOKIE_SECURE": "1",
        "BILUN_PUBLIC_BILLING_ENABLED": "0",
    }
    return (
        "# Private developer cutover configuration. Do not commit or log.\n"
        "# Install consistently in the paired services; retire former shared credentials.\n"
        + "".join(f"{name}='{value}'\n" for name, value in values.items())
    )


def write_new_environment(path: Path, content: str) -> None:
    # O_EXCL prevents replacing an existing file or following an existing link.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args(argv)
    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("New developer password: ")
    try:
        content = render_environment(args.username, password)
        write_new_environment(args.output, content)
    except (OSError, ValueError):
        print("Unable to create credentials: use a valid username, a 16+ character password, and a new writable output path.", file=sys.stderr)
        return 1
    print("Created owner-only developer configuration. Public billing remains disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
