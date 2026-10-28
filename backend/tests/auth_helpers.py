"""Synthetic principal for pre-existing middleware tests; real JWT tests are separate."""

from datetime import UTC, datetime, timedelta

from app.services.auth_service import Principal, csrf_token


def headers(settings):
    return {
        "Cookie": "middleware-test-admin",
        "Origin": "https://testserver",
        "X-CSRF-Token": csrf_token(settings, "a" * 64),
    }


def install(monkeypatch):
    def principal(scope, settings):
        if dict(scope["headers"]).get(b"cookie") == b"middleware-test-admin":
            return Principal(
                "synthetic-admin",
                "admin@example.invalid",
                "admin",
                "a" * 64,
                datetime.now(UTC) + timedelta(minutes=30),
            )
        return None

    monkeypatch.setattr("app.core.security.authenticate_request", principal)
