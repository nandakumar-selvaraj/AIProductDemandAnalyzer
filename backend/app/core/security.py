"""Fail-closed production authorization and bounded single-worker admission."""

import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.services.auth_service import AuthError, authenticate_request, cookie_name, csrf_token

# Explicitly reviewed read routes only: future routes are private by default.
PUBLIC_READ = re.compile(
    r"/api/v1/(?:dashboard/summary|products|products/[1-9][0-9]*/analytics|"
    r"stores|sales/summary|forecasts/(?:latest|runs|[1-9][0-9]*/(?:predictions|evaluation))|"
    r"recommendations)"
)
DEMO_CHAT = "/api/v1/demo/assistant"


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app
        self.windows = defaultdict(deque)
        self.daily = {}

    def admit(self, settings, bucket, minute_limit, daily_limit=None):
        now = time.monotonic()
        window = self.windows[bucket]
        while window and window[0] <= now - 60:
            window.popleft()
        if len(window) >= minute_limit:
            return "rate_limit"
        if daily_limit is not None:
            day = datetime.now(UTC).date().isoformat()
            if settings.ai_usage_file:
                with sqlite3.connect(settings.ai_usage_file, timeout=2) as usage:
                    usage.execute("BEGIN IMMEDIATE")
                    usage.execute(
                        "CREATE TABLE IF NOT EXISTS admission "
                        "(bucket TEXT, day TEXT, n INTEGER, PRIMARY KEY(bucket, day))"
                    )
                    # Carry Phase 7A counts forward; upgrade must not reset the budget.
                    old = usage.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='usage'"
                    ).fetchone()
                    if old and bucket == "ai":
                        usage.execute(
                            "INSERT OR IGNORE INTO admission SELECT 'ai', day, n FROM usage"
                        )
                    row = usage.execute(
                        "SELECT n FROM admission WHERE bucket=? AND day=?", (bucket, day)
                    ).fetchone()
                    if row and row[0] >= daily_limit:
                        return "daily_cap"
                    usage.execute(
                        "INSERT INTO admission VALUES (?, ?, 1) "
                        "ON CONFLICT(bucket, day) DO UPDATE SET n=n+1",
                        (bucket, day),
                    )
                    usage.execute("DELETE FROM admission WHERE day < ?", (day,))
            else:
                key = (bucket, day)
                if self.daily.get(key, 0) >= daily_limit:
                    return "daily_cap"
                self.daily = {k: v for k, v in self.daily.items() if k[1] == day}
                self.daily[key] = self.daily.get(key, 0) + 1
        window.append(now)
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = get_settings()
        headers = dict(scope["headers"])
        path, method = scope["path"], scope["method"]
        public = False

        async def reject(status, code):
            response = JSONResponse(
                {"error": {"code": code, "message": code.replace("_", " ")}},
                status_code=status,
                headers={"Retry-After": "60"} if status == 429 else None,
            )
            response.headers["Cache-Control"] = "no-store"
            if status == 401 and settings.auth_enabled:
                response.delete_cookie(
                    cookie_name(settings),
                    path="/",
                    httponly=True,
                    secure=settings.environment == "production",
                    samesite="strict",
                )
            await response(scope, receive, send)

        if settings.environment == "production":
            host = headers.get(b"host", b"").decode("latin1").split(":")[0]
            if host not in settings.trusted_hosts:
                return await reject(400, "invalid_host")
            if path in {"/docs", "/redoc", "/openapi.json", "/"}:
                return await reject(404, "not_found")
        if settings.auth_enabled:
            login_path = path == "/api/v1/auth/login" and method == "POST"
            if login_path:
                if self.admit(settings, "login", settings.auth_login_requests_per_minute):
                    return await reject(429, "login_rate_limit")
            principal = None
            if not login_path:
                try:
                    principal = await run_in_threadpool(authenticate_request, scope, settings)
                except AuthError:
                    return await reject(401, "authentication_required")
                except SQLAlchemyError:
                    return await reject(503, "authentication_unavailable")
            scope.setdefault("state", {})["principal"] = principal
            health = method == "GET" and path in {
                "/api/v1/health",
                "/api/v1/ready",
                "/api/v1/demo/config",
            }
            docs = (
                settings.environment != "production"
                and method == "GET"
                and path
                in {
                    "/docs",
                    "/redoc",
                    "/openapi.json",
                    "/docs/oauth2-redirect",
                    "/",
                }
            )
            public = (
                settings.public_demo_enabled
                and principal is None
                and (
                    (method == "GET" and PUBLIC_READ.fullmatch(path) is not None)
                    or (method == "POST" and path == DEMO_CHAT and settings.demo_ai_enabled)
                )
            )
            if not (principal or health or public or login_path or docs):
                return await reject(401, "authentication_required")
            state_change = method not in {"GET", "HEAD", "OPTIONS"}
            if principal and principal.purpose == "api" and path.startswith("/api/v1/auth/"):
                return await reject(403, "browser_session_required")
            if login_path or (principal and principal.purpose == "browser" and state_change):
                origin = headers.get(b"origin", b"").decode("latin1")
                if origin not in settings.auth_allowed_origins:
                    return await reject(403, "csrf_origin_denied")
                if login_path:
                    if headers.get(b"x-requested-with") != b"AIProductDemandAnalyzer":
                        return await reject(403, "csrf_header_required")
                elif not secrets.compare_digest(
                    headers.get(b"x-csrf-token", b""),
                    csrf_token(settings, principal.session_id).encode(),
                ):
                    return await reject(403, "csrf_token_invalid")
            if principal:
                viewer_read = method in {"GET", "HEAD"} and (
                    PUBLIC_READ.fullmatch(path) is not None
                    or path in {"/api/v1/auth/me", "/api/v1/assistant/ready"}
                )
                viewer_post = method == "POST" and path in {
                    "/api/v1/auth/logout",
                    "/api/v1/assistant/chat",
                    "/api/v1/forecasts/evaluate",
                    "/api/v1/forecasts/backtest",
                    DEMO_CHAT,
                }
                admin_write = (
                    principal.role == "admin"
                    and method == "POST"
                    and path in {"/api/v1/ingestion/sales", "/api/v1/forecasts"}
                )
                admin_read = principal.role == "admin" and method in {"GET", "HEAD"}
                if not (
                    health or login_path or viewer_read or viewer_post or admin_write or admin_read
                ):
                    return await reject(403, "authorization_denied")
            scope.setdefault("state", {})["public_demo"] = public
            # Logged-in viewers in public-demo deployments remain on synthetic data.
            if settings.public_demo_enabled and principal and principal.role == "viewer":
                scope["state"]["public_demo"] = True
            if path == "/api/v1/ready" and not principal:
                if self.admit(settings, "readiness", 60):
                    return await reject(429, "readiness_rate_limit")
            if public:
                if self.admit(settings, "reads", settings.demo_reads_per_minute):
                    return await reject(429, "demo_rate_limit")
                if path == DEMO_CHAT:
                    origin = headers.get(b"origin")
                    if origin and origin != f"https://{host}".encode():
                        return await reject(403, "cross_origin_denied")
                    reason = self.admit(
                        settings,
                        "demo_ai",
                        settings.demo_ai_requests_per_minute,
                        settings.demo_ai_daily_cap,
                    )
                    if reason:
                        return await reject(429, "demo_ai_" + reason)
            if path.startswith("/api/v1/assistant") or path == DEMO_CHAT:
                reason = self.admit(
                    settings, "ai", settings.ai_requests_per_minute, settings.ai_daily_request_cap
                )
                if reason:
                    return await reject(429, "ai_" + reason)
        # Enforce bounds before multipart parsing or any database work.
        limit = settings.max_request_bytes
        if path == DEMO_CHAT:
            limit = min(limit, 1024)
        elif path == "/api/v1/auth/login":
            limit = min(limit, 4096)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                return await reject(413, "request_too_large")
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def secure_send(message):
            if settings.auth_enabled and message["type"] == "http.response.start":
                response_headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"cache-control", b"pragma"}
                ]
                message["headers"] = response_headers + [
                    (b"cache-control", b"no-store"),
                    (b"pragma", b"no-cache"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, secure_send)
