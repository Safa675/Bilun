"""Method/route authorization and final JSON projection before compression."""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from functools import lru_cache

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import compile_path, get_route_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .access import ROUTE_POLICY, has_developer_access, identity_from_request
from .auth import is_auth_configured, is_auth_optional
from .public_responses import project_public_response, public_error

_BODY_LIMIT = 256 * 1024
_JSON_RESPONSE_LIMIT = 32 * 1024 * 1024
_VALIDATION_REQUESTS_PER_MINUTE = 20
_VALIDATION_CONCURRENCY = 2
_BATCH_SURFACES = frozenset({"/api/compliance-index", "/api/wavea-evidence-index", "/api/wavea-evidence-rows"})
_PUBLIC_SELECTION_LIMIT = 500
_validation_lock = threading.Lock()
_validation_windows: dict[str, deque[float]] = {}
_validation_running = 0


def registered_routes(app):
    """Walk both eager and lazy included FastAPI routers in dispatch order."""
    def walk(routes, prefix=""):
        for route in routes:
            included = getattr(route, "original_router", None)
            if included is not None:
                yield from walk(included.routes, prefix + route.include_context.prefix)
            elif hasattr(route, "path") and hasattr(route, "methods"):
                yield route, prefix + route.path
    yield from walk(app.routes)


@lru_cache(maxsize=256)
def _route_regex(path):
    return compile_path(path)[0]


def _resolve_route(scope: Scope, method: str) -> str | None:
    # Use the actual mounted table, not just registry pattern matching: a new
    # unclassified static route must not inherit an existing parameter route.
    path = get_route_path(scope)
    for route, template in registered_routes(scope["app"]):
        if method in route.methods and _route_regex(template).match(path):
            return template
    return None


def _begin_validation(ip: str) -> bool:
    global _validation_running
    now = time.monotonic()
    with _validation_lock:
        stale = [key for key, window in _validation_windows.items() if not window or window[-1] < now - 60]
        for key in stale:
            del _validation_windows[key]
        if len(_validation_windows) >= 4096 and ip not in _validation_windows:
            return False
        window = _validation_windows.setdefault(ip, deque())
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= _VALIDATION_REQUESTS_PER_MINUTE or _validation_running >= _VALIDATION_CONCURRENCY:
            return False
        window.append(now)
        _validation_running += 1
        return True


def _end_validation() -> None:
    global _validation_running
    with _validation_lock:
        _validation_running -= 1


def _selection_is_bounded(value) -> bool:
    """Support existing repeated/comma-separated selectors with finite work."""
    if value is None:
        return True
    if not isinstance(value, list) or len(value) > _PUBLIC_SELECTION_LIMIT:
        return False
    count = 0
    for item in value:
        if not isinstance(item, str) or len(item) > 4096:
            return False
        selected = item.split(",")
        if any(len(part) > 128 for part in selected):
            return False
        count += len(selected)
    return count <= _PUBLIC_SELECTION_LIMIT


class SessionGateMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        identity = identity_from_request(request)
        request.state.bilun_identity = identity
        # Preserve the repository's explicit local/test setup, never activate
        # this bypass merely because credentials are absent.
        bypass = not is_auth_configured() and is_auth_optional()
        route_path = _resolve_route(scope, scope["method"])
        policy = ROUTE_POLICY.get((scope["method"], route_path))

        if scope["method"] == "OPTIONS" and "origin" in request.headers:
            preflight_method = request.headers.get("access-control-request-method", "")
            template = _resolve_route(scope, preflight_method)
            if (preflight_method, template) in ROUTE_POLICY:
                # The inner CORS middleware validates its explicit origin list;
                # preflight returns no protected response data.
                await self.app(scope, receive, send)
                return

        async def reject(status: int) -> None:
            await JSONResponse(public_error(status), status_code=status, headers={"Cache-Control": "no-store"})(scope, receive, send)

        if not bypass:
            if policy is None:
                await reject(404)
                return
            if policy == "developer" and not has_developer_access(identity):
                await reject(403 if identity.authenticated else 401)
                return
            if policy == "billing" and "billing" not in identity.capabilities:
                await reject(401)
                return

        public_result = not bypass and not has_developer_access(identity) and policy == "billing"
        validation_request = public_result and route_path == "/api/validate-claim"
        if public_result:
            if len(scope.get("query_string", b"")) > 8192 or len(scope.get("path", "")) > 2048:
                await reject(413)
                return
            if route_path in _BATCH_SURFACES and not _selection_is_bounded(request.query_params.getlist("patient_id")):
                await reject(413)
                return
        if not bypass and scope["method"] == "POST":
            # Read bounded input before expensive JSON/model/evaluator work.
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > _BODY_LIMIT:
                    await reject(413)
                    return
                if not message.get("more_body", False):
                    break
            if public_result and (validation_request or route_path in _BATCH_SURFACES):
                try:
                    payload = json.loads(body)
                    materials = payload.get("materials", []) if isinstance(payload, dict) else []
                    if validation_request and isinstance(materials, list) and len(materials) > 100:
                        await reject(413)
                        return
                    if route_path in _BATCH_SURFACES and isinstance(payload, dict) and not _selection_is_bounded(payload.get("patient_id")):
                        await reject(413)
                        return
                except (ValueError, UnicodeDecodeError):
                    await reject(422)
                    return
            replayed = False

            async def replay_receive() -> Message:
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            downstream_receive = replay_receive
        else:
            downstream_receive = receive

        if validation_request and not _begin_validation(request.client.host if request.client else "unknown"):
            await reject(429)
            return

        response_start: Message | None = None
        chunks = bytearray()
        project_json = False
        output_overflow = False

        async def public_send(message: Message) -> None:
            nonlocal response_start, project_json, output_overflow
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "private, no-store"
                # Health and auth own small explicit response contracts. Health
                # may grant a dedicated release probe detailed diagnostics.
                chat_stream = route_path == "/api/chat" and message["status"] < 400 and "text/event-stream" in headers.get("content-type", "")
                # A public JSON handler switching to a raw/plaintext response
                # must not silently bypass its reviewed output contract.
                project_json = public_result and not chat_stream
                if project_json:
                    response_start = message
                    return
            elif message["type"] == "http.response.body" and project_json:
                if not output_overflow:
                    chunks.extend(message.get("body", b""))
                    if len(chunks) > _JSON_RESPONSE_LIMIT:
                        output_overflow = True
                        chunks.clear()
                if message.get("more_body", False):
                    return
                assert response_start is not None
                status = response_start["status"]
                try:
                    if output_overflow:
                        raise ValueError("Public response exceeds output limit")
                    raw_payload = json.loads(chunks)
                    payload = public_error(status) if status >= 400 else project_public_response(raw_payload, route_path)
                    if status == 409 and isinstance(raw_payload, dict) and raw_payload.get("code") == "validation_contract_upgrade_required":
                        payload["code"] = "validation_contract_upgrade_required"
                    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
                except (ValueError, TypeError, KeyError):
                    status = 503
                    payload = public_error(status)
                    encoded = json.dumps(payload).encode()
                headers = MutableHeaders(scope=response_start)
                headers["Content-Length"] = str(len(encoded))
                headers["Content-Type"] = "application/json"
                for key in ("etag", "last-modified"):
                    if key in headers:
                        del headers[key]
                response_start["status"] = status
                await send(response_start)
                await send({"type": "http.response.body", "body": encoded})
                return
            await send(message)

        try:
            await self.app(scope, downstream_receive, public_send)
        finally:
            if validation_request:
                _end_validation()
