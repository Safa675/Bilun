"""Public chat admission and conservative, durable provider-use reservations.

The SQLite ledger is shared by workers and survives restarts. Reservations are
never refunded: failures/cancellation can still incur provider usage. This is a
token allowance, not a measurement of billed dollars or exact tokenization.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from contextlib import aclosing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request

from src.bilun.shared.exceptions import RateLimitError, ServiceUnavailableError

PUBLIC_REQUEST_TIMEOUT_SEC = 90
PUBLIC_MAX_PROVIDER_CALLS = 4
PUBLIC_MAX_OUTPUT_TOKENS = 2048
PUBLIC_MAX_PROVIDER_BYTES = 131072
PUBLIC_CONCURRENT_REQUESTS = 4
PUBLIC_CONCURRENT_PER_CLIENT = 2
PUBLIC_REQUESTS_PER_MINUTE = 15

_budget: ContextVar[PublicChatLease | None] = ContextVar("public_chat_budget", default=None)
_workers = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bilun-chat")
_work_slots = threading.BoundedSemaphore(8)


async def bounded_chat_work(fn: Callable, *args, **kwargs):
    """Bound queued/running sync work even when an awaiting request times out.

Python threads cannot be forcibly cancelled. Hold the slot until the actual
worker finishes, rather than releasing it when asyncio stops waiting for it.
    """
    slots = _work_slots
    if not slots.acquire(blocking=False):
        raise RateLimitError("Chat is busy. Please try again shortly.")
    try:
        future = _workers.submit(fn, *args, **kwargs)
    except BaseException:
        slots.release()
        raise
    future.add_done_callback(lambda _future: slots.release())
    return await asyncio.wrap_future(future)


def client_identity(request: Request) -> str:
    """Use the ASGI client, never unverified request forwarding headers.

The ASGI server must trust forwarding only from the configured loopback reverse
proxy (never '*'). Direct callers cannot select a bucket with X-Forwarded-For.
    """
    return request.client.host if request.client else "unknown"


def _configuration() -> tuple[Path, int]:
    try:
        allowance = int(os.getenv("BILUN_PUBLIC_CHAT_DAILY_TOKEN_BUDGET", "0"))
        raw_path = os.getenv("BILUN_PUBLIC_CHAT_BUDGET_DB", "")
        path = Path(raw_path)
        if allowance <= 0 or not raw_path or not path.is_absolute():
            raise ValueError
        # The operator creates a private writable parent; never choose a
        # transient location silently or reset the ledger when it is absent.
        if not path.parent.is_dir() or path.is_symlink():
            raise ValueError
        return path, allowance
    except (ValueError, OSError):
        raise ServiceUnavailableError("Public chat is not configured. Please try later.") from None


@contextmanager
def _connection(path: Path):
    conn = sqlite3.connect(path, timeout=2, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute("CREATE TABLE IF NOT EXISTS usage (day INTEGER PRIMARY KEY, reserved INTEGER NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, client TEXT NOT NULL, started REAL NOT NULL, active INTEGER NOT NULL)")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


@dataclass
class PublicChatLease:
    path: Path
    allowance: int
    identifier: str
    calls: int = 0

    def reserve(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Reserve before sending each provider request; fail closed on errors."""
        if self.calls >= PUBLIC_MAX_PROVIDER_CALLS:
            raise RateLimitError("Chat reached its request limit. Please try a shorter question.")
        output_tokens = min(int(payload.get("max_tokens", PUBLIC_MAX_OUTPUT_TOKENS)), PUBLIC_MAX_OUTPUT_TOKENS)
        prepared = {**payload, "max_tokens": output_tokens}
        size = len(json.dumps(prepared, ensure_ascii=False).encode("utf-8"))
        if size > PUBLIC_MAX_PROVIDER_BYTES:
            raise RateLimitError("Chat context is too large. Please start a shorter conversation.")
        # UTF-8 bytes deliberately overestimate normal text tokenization; count
        # schemas/framing too, and reserve the complete maximum output.
        reservation = size + output_tokens
        now = time.time()
        day = int(now // 86400)
        try:
            with _connection(self.path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("INSERT OR IGNORE INTO usage VALUES (?, 0)", (day,))
                used = conn.execute("SELECT reserved FROM usage WHERE day=?", (day,)).fetchone()[0]
                if used + reservation > self.allowance:
                    raise RateLimitError("Today's public chat allowance is exhausted. Please try later.")
                conn.execute("UPDATE usage SET reserved=reserved+? WHERE day=?", (reservation, day))
                conn.commit()
        except (sqlite3.Error, OSError):
            raise ServiceUnavailableError("Public chat is temporarily unavailable.") from None
        self.calls += 1
        return prepared

    def release(self) -> None:
        try:
            with _connection(self.path) as conn:
                conn.execute("UPDATE requests SET active=0 WHERE id=?", (self.identifier,))
        except (sqlite3.Error, OSError):
            # The recorded lease expires after the bounded stream deadline.
            pass


def admit_public_chat(request: Request, *, user_role: str) -> PublicChatLease | None:
    from src.bilun.api.access import is_public_billing_enabled

    if user_role == "dev" or not is_public_billing_enabled():
        return None
    path, allowance = _configuration()
    now = time.time()
    identifier = uuid.uuid4().hex
    client = client_identity(request)
    try:
        with _connection(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM requests WHERE started < ?", (now - PUBLIC_REQUEST_TIMEOUT_SEC - 10,))
            conn.execute("DELETE FROM usage WHERE day < ?", (int(now // 86400) - 2,))
            active = conn.execute("SELECT COUNT(*) FROM requests WHERE active=1").fetchone()[0]
            per_client = conn.execute("SELECT COUNT(*) FROM requests WHERE active=1 AND client=?", (client,)).fetchone()[0]
            recent = conn.execute("SELECT COUNT(*) FROM requests WHERE client=? AND started>?", (client, now - 60)).fetchone()[0]
            if active >= PUBLIC_CONCURRENT_REQUESTS or per_client >= PUBLIC_CONCURRENT_PER_CLIENT or recent >= PUBLIC_REQUESTS_PER_MINUTE:
                raise RateLimitError("Chat is busy. Please try again shortly.")
            used = conn.execute("SELECT reserved FROM usage WHERE day=?", (int(now // 86400),)).fetchone()
            if used and used[0] >= allowance:
                raise RateLimitError("Today's public chat allowance is exhausted. Please try later.")
            conn.execute("INSERT INTO requests VALUES (?, ?, ?, 1)", (identifier, client, now))
            conn.commit()
    except (sqlite3.Error, OSError):
        raise ServiceUnavailableError("Public chat is temporarily unavailable.") from None
    return PublicChatLease(path, allowance, identifier)


def authorize_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    lease = _budget.get()
    return lease.reserve(payload) if lease else payload


async def public_chat_stream(producer: Any, lease: PublicChatLease):
    token = _budget.set(lease)
    try:
        # The SSE producer owns the deadline so it also covers queue
        # backpressure. A timeout here would span yields into the caller.
        async with aclosing(producer()) as stream:
            async for item in stream:
                yield item
    finally:
        _budget.reset(token)
        lease.release()
