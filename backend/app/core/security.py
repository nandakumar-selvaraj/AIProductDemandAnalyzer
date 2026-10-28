"""Fail-closed production authorization and bounded single-worker admission."""

import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi.responses import JSONResponse

from app.core.config import get_settings

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
            await response(scope, receive, send)

        if settings.environment == "production":
            host = headers.get(b"host", b"").decode("latin1").split(":")[0]
            if host not in settings.trusted_hosts:
                return await reject(400, "invalid_host")
            if path in {"/docs", "/redoc", "/openapi.json", "/"}:
                return await reject(404, "not_found")
            expected = ("Bearer " + settings.operator_token.get_secret_value()).encode("utf-8")
            operator = secrets.compare_digest(headers.get(b"authorization", b""), expected)
            health = method == "GET" and path in {
                "/api/v1/health",
                "/api/v1/ready",
                "/api/v1/demo/config",
            }
            public = (
                settings.public_demo_enabled
                and (
                    (method == "GET" and PUBLIC_READ.fullmatch(path) is not None)
                    or (method == "POST" and path == DEMO_CHAT and settings.demo_ai_enabled)
                )
                and not operator
            )
            if not (operator or health or public):
                return await reject(401, "operator_authentication_required")
            scope.setdefault("state", {})["public_demo"] = public
            if path == "/api/v1/ready" and not operator:
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
        limit = (
            min(settings.max_request_bytes, 1024)
            if path == DEMO_CHAT
            else settings.max_request_bytes
        )
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

        await self.app(scope, bounded_receive, send)
