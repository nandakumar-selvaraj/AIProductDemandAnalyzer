"""Real Argon2/JWT/cookie/session tests in an isolated in-memory auth database."""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth import router
from app.core.config import Settings, get_settings
from app.core.security import SecurityMiddleware
from app.db.base import Base
from app.models.auth import AuthSession, User
from app.services.auth_service import PASSWORDS, cookie_name

PASSWORD = "Synthetic-test-password!123"
ORIGIN = "https://testserver"
LOGIN_HEADERS = {"Origin": ORIGIN, "X-Requested-With": "AIProductDemandAnalyzer"}


@pytest.fixture
def auth_system(monkeypatch):
    config = Settings(
        _env_file=None,
        environment="production",
        auth_enabled=True,
        jwt_signing_secret=secrets.token_hex(32),
        operator_token=secrets.token_hex(32),
        auth_allowed_origins=[ORIGIN],
        database_url="postgresql+psycopg://test:test@localhost/test",
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        for role in ("admin", "viewer"):
            db.add(
                User(
                    email=f"{role}@example.invalid",
                    role=role,
                    password_hash=PASSWORDS.hash(PASSWORD),
                )
            )
        db.commit()
    monkeypatch.setattr("app.core.security.get_settings", lambda: config)
    monkeypatch.setattr("app.services.auth_service.get_session_factory", lambda: factory)
    monkeypatch.setattr("app.api.v1.endpoints.auth.get_session_factory", lambda: factory)
    probe = FastAPI()
    probe.include_router(router, prefix="/api/v1")
    probe.dependency_overrides[get_settings] = lambda: config

    @probe.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    def protected(request: Request):
        return {"role": getattr(request.state, "principal", None).role}

    probe.add_middleware(SecurityMiddleware)
    client = TestClient(probe, base_url=ORIGIN)
    yield client, config, factory
    client.close()
    engine.dispose()


def sign_in(client, role="viewer", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"email": f"{role}@example.invalid", "password": password},
        headers=LOGIN_HEADERS,
    )


def test_login_cookie_and_me(auth_system):
    client, config, _ = auth_system
    response = sign_in(client)
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "viewer"
    assert "token" not in response.json()
    header = response.headers["set-cookie"]
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=1800"):
        assert flag in header
    assert "Domain=" not in header
    assert response.headers["Cache-Control"] == "no-store"
    token = client.cookies.get(cookie_name(config))
    assert token and PASSWORD not in token
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json() == response.json()


def test_generic_credentials_and_disabled_user(auth_system):
    client, _, factory = auth_system
    wrong = sign_in(client, password="wrong-password")
    missing = sign_in(client, role="missing")
    with factory() as db:
        user = db.scalar(select(User).where(User.role == "viewer"))
        user.is_active = False
        db.commit()
    disabled = sign_in(client)
    assert wrong.status_code == missing.status_code == disabled.status_code == 401
    assert wrong.json() == missing.json() == disabled.json()
    assert PASSWORD not in disabled.text


@pytest.mark.parametrize(
    "case",
    [
        "expired",
        "tampered",
        "issuer",
        "audience",
        "nbf",
        "missing_exp",
        "missing_sub",
        "algorithm",
        "subject",
    ],
)
def test_jwt_validation(auth_system, case):
    client, config, _ = auth_system
    assert sign_in(client).status_code == 200
    raw = client.cookies.get(cookie_name(config))
    claims = jwt.decode(
        raw,
        config.jwt_signing_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=config.jwt_audience,
        issuer=config.jwt_issuer,
    )
    secret = config.jwt_signing_secret.get_secret_value()
    algorithm = "HS256"
    if case == "expired":
        claims["exp"] = int((datetime.now(UTC) - timedelta(seconds=1)).timestamp())
    elif case == "issuer":
        claims["iss"] = "evil"
    elif case == "audience":
        claims["aud"] = "evil"
    elif case == "nbf":
        claims["nbf"] = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    elif case == "missing_exp":
        del claims["exp"]
    elif case == "missing_sub":
        del claims["sub"]
    elif case == "subject":
        claims["sub"] = "invalid-subject"
    elif case == "algorithm":
        algorithm = "HS384"
    elif case == "tampered":
        secret = secrets.token_hex(32)
    client.cookies.clear()
    client.cookies.set(cookie_name(config), jwt.encode(claims, secret, algorithm=algorithm))
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/products").status_code == 401


def test_logout_revokes_captured_token(auth_system):
    client, config, factory = auth_system
    session = sign_in(client).json()
    raw = client.cookies.get(cookie_name(config))
    response = client.post(
        "/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
    )
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    with factory() as db:
        assert db.scalar(select(AuthSession)).revoked_at is not None
    client.cookies.clear()
    client.cookies.set(cookie_name(config), raw)
    assert client.get("/api/v1/products").status_code == 401


def test_db_expiry_and_disabled_checks(auth_system):
    client, _, factory = auth_system
    sign_in(client)
    with factory() as db:
        db.scalar(select(AuthSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    sign_in(client)
    with factory() as db:
        db.scalar(select(User).where(User.role == "viewer")).is_active = False
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_and_login_origin(auth_system):
    client, _, _ = auth_system
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "viewer@example.invalid", "password": PASSWORD}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "viewer@example.invalid", "password": PASSWORD},
            headers={**LOGIN_HEADERS, "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    data = sign_in(client).json()
    assert client.post("/api/v1/forecasts/evaluate", headers={"Origin": ORIGIN}).status_code == 403
    assert (
        client.post(
            "/api/v1/forecasts/evaluate", headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/forecasts/evaluate",
            headers={"Origin": ORIGIN, "X-CSRF-Token": data["csrf_token"]},
        ).status_code
        == 200
    )


@pytest.mark.parametrize("role", ["admin", "viewer"])
def test_role_matrix_and_operator_token_cannot_bypass(auth_system, role):
    client, config, _ = auth_system
    assert client.get("/api/v1/products").status_code == 401
    assert (
        client.get(
            "/api/v1/products",
            headers={"Authorization": "Bearer " + config.operator_token.get_secret_value()},
        ).status_code
        == 401
    )
    data = sign_in(client, role=role).json()
    headers = {"Origin": ORIGIN, "X-CSRF-Token": data["csrf_token"]}
    for path in ("/products", "/dashboard/summary", "/forecasts/latest", "/stores"):
        assert client.get("/api/v1" + path).status_code == 200
    for path in ("/forecasts/evaluate", "/forecasts/backtest", "/assistant/chat"):
        assert client.post("/api/v1" + path, headers=headers).status_code == 200
    for path in ("/ingestion/sales", "/forecasts"):
        assert client.post("/api/v1" + path, headers=headers).status_code == (
            200 if role == "admin" else 403
        )
    assert client.post("/api/v1/new-administration", headers=headers).status_code == 403


def test_login_rate_limit(auth_system):
    client, config, _ = auth_system
    config.auth_login_requests_per_minute = 1
    assert sign_in(client, password="bad").status_code == 401
    assert sign_in(client).status_code == 429


def test_role_change_takes_effect_without_reissuing_jwt(auth_system):
    client, _, factory = auth_system
    data = sign_in(client, role="admin").json()
    with factory() as db:
        db.scalar(select(User).where(User.role == "admin")).role = "viewer"
        db.commit()
    assert (
        client.post(
            "/api/v1/forecasts", headers={"Origin": ORIGIN, "X-CSRF-Token": data["csrf_token"]}
        ).status_code
        == 403
    )
