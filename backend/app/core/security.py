"""Single-worker operator authorization and bounded request admission."""

import secrets
import sqlite3
import time
from collections import deque
from datetime import UTC, datetime

from fastapi.responses import JSONResponse

from app.core.config import get_settings


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app
        self.minute = deque()
        self.day = ""
        self.daily = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = get_settings()
        headers = dict(scope["headers"])
        path, method = scope["path"], scope["method"]

        async def reject(status, code):
            response = JSONResponse(
                {"error": {"code": code, "message": code.replace("_", " ")}},
                status_code=status,
            )
            await response(scope, receive, send)

        if settings.environment == "production":
            host = headers.get(b"host", b"").decode("latin1").split(":")[0]
            if host not in settings.trusted_hosts:
                return await reject(400, "invalid_host")
            if path in {"/docs", "/redoc", "/openapi.json", "/"}:
                return await reject(404, "not_found")
            sensitive = method not in {"GET", "HEAD", "OPTIONS"} or path.startswith(
                "/api/v1/assistant"
            )
            if sensitive:
                expected = ("Bearer " + settings.operator_token.get_secret_value()).encode("utf-8")
                actual = headers.get(b"authorization", b"")
                if not secrets.compare_digest(actual, expected):
                    return await reject(401, "operator_authentication_required")
        if settings.environment == "production" and path.startswith("/api/v1/assistant"):
            now = time.monotonic()
            while self.minute and self.minute[0] <= now - 60:
                self.minute.popleft()
            day = datetime.now(UTC).date().isoformat()
            if day != self.day:
                self.day, self.daily = day, 0
            if len(self.minute) >= settings.ai_requests_per_minute:
                return await reject(429, "ai_rate_limit")
            if settings.ai_usage_file:
                with sqlite3.connect(settings.ai_usage_file, timeout=2) as usage:
                    usage.execute("BEGIN IMMEDIATE")
                    usage.execute(
                        "CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, n INTEGER)"
                    )
                    row = usage.execute("SELECT n FROM usage WHERE day = ?", (day,)).fetchone()
                    count = row[0] if row else 0
                    if count < settings.ai_daily_request_cap:
                        usage.execute(
                            "INSERT INTO usage VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET n=n+1",
                            (day,),
                        )
                        usage.execute("DELETE FROM usage WHERE day < ?", (day,))
                    self.daily = count
            if self.daily >= settings.ai_daily_request_cap:
                return await reject(429, "ai_daily_cap")
            self.minute.append(now)
            self.daily += 1
        # Buffer only up to the limit, before multipart parsing or database work.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > settings.max_request_bytes:
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
