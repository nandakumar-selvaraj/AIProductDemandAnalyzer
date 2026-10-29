"""Purpose-separated, revocable Bearer credentials and unchanged cookie CSRF."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.main import app
from app.models.auth import ApiToken, User
from app.services.auth_service import cookie_name, issue_session
from tests.unit import test_authentication as helpers
from tests.unit.test_authentication import ORIGIN, sign_in


@pytest.fixture
def auth_system(monkeypatch):
    yield from helpers.auth_system.__wrapped__(monkeypatch)


def issue(config, factory, role="admin"):
    with factory() as db:
        user = db.scalar(select(User).where(User.role == role))
        return issue_session(db, user, config, api_minutes=10)[0]


def bearer(token):
    return {"Authorization": "Bearer " + token}


def test_openapi_bearer_scheme_and_cookie_alternative():
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["ApiBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/ingestion/sales"]["post"]["security"] == [
        {"BrowserSession": []},
        {"ApiBearer": []},
    ]
    assert schema["paths"]["/api/v1/auth/me"]["get"]["security"] == [{"BrowserSession": []}]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]


@pytest.mark.parametrize("role", ["admin", "viewer"])
def test_bearer_role_enforcement_without_cookie_csrf(auth_system, role):
    client, config, factory = auth_system
    token = issue(config, factory, role)
    assert client.get("/api/v1/products", headers=bearer(token)).status_code == 200
    assert client.post("/api/v1/ingestion/sales", headers=bearer(token)).status_code == (
        200 if role == "admin" else 403
    )
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=bearer(token)).status_code == 403


@pytest.mark.parametrize(
    "case",
    [
        "expired",
        "revoked",
        "db_expired",
        "disabled",
        "purpose",
        "missing_purpose",
        "audience",
        "issuer",
        "signature",
        "session_table",
    ],
)
def test_invalid_api_token(auth_system, case):
    client, config, factory = auth_system
    token = issue(config, factory)
    secret = config.jwt_signing_secret.get_secret_value()
    claims = jwt.decode(token, secret, algorithms=["HS256"], audience=config.jwt_audience + ":api")
    with factory() as db:
        row = db.get(ApiToken, claims["jti"])
        if case == "revoked":
            row.revoked_at = datetime.now(UTC)
        if case == "db_expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if case == "disabled":
            db.get(User, claims["sub"]).is_active = False
        if case == "session_table":
            db.delete(row)
        db.commit()
    if case == "expired":
        claims["exp"] = int((datetime.now(UTC) - timedelta(seconds=1)).timestamp())
    if case == "purpose":
        claims["purpose"] = "browser"
    if case == "missing_purpose":
        del claims["purpose"]
    if case == "audience":
        claims["aud"] = config.jwt_audience
    if case == "issuer":
        claims["iss"] = "wrong-issuer"
    if case == "signature":
        secret = "wrong-key" * 10
    token = jwt.encode(claims, secret, algorithm="HS256")
    assert client.get("/api/v1/products", headers=bearer(token)).status_code == 401


def test_token_transport_separation_and_mixed_credentials(auth_system):
    client, config, factory = auth_system
    api = issue(config, factory)
    session = sign_in(client, "admin").json()
    browser = client.cookies.get(cookie_name(config))
    # Bearer headers cannot switch an existing cookie request out of CSRF checks.
    assert client.post("/api/v1/ingestion/sales", headers=bearer(api)).status_code == 401
    client.cookies.clear()
    assert client.get("/api/v1/products", headers=bearer(browser)).status_code == 401
    client.cookies.set(cookie_name(config), api)
    assert client.get("/api/v1/products").status_code == 401
    client.cookies.clear()
    sign_in(client, "admin")
    assert client.post("/api/v1/ingestion/sales").status_code == 403
    assert (
        client.post(
            "/api/v1/ingestion/sales",
            headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]},
        ).status_code
        == 403
    )


def test_api_role_is_read_from_database(auth_system):
    client, config, factory = auth_system
    token = issue(config, factory)
    with factory() as db:
        db.scalar(select(User).where(User.role == "admin")).role = "viewer"
        db.commit()
    assert client.post("/api/v1/ingestion/sales", headers=bearer(token)).status_code == 403


@pytest.mark.parametrize("minutes", [0, 16])
def test_lifetime_bounds(auth_system, minutes):
    _, config, factory = auth_system
    with factory() as db, pytest.raises(ValueError):
        issue_session(db, db.scalar(select(User)), config, api_minutes=minutes)


def test_owner_cli_issuance_and_revocation(auth_system, monkeypatch, tmp_path, capsys):
    from scripts import manage_api_tokens

    client, config, factory = auth_system
    monkeypatch.setattr(manage_api_tokens, "get_settings", lambda: config)
    monkeypatch.setattr(manage_api_tokens, "get_engine", lambda: factory.kw["bind"])
    output = tmp_path / "private.token"
    monkeypatch.setattr(
        "sys.argv",
        ["manage_api_tokens", "issue", "--email", "admin@example.invalid", "--output", str(output)],
    )
    manage_api_tokens.main()
    token = output.read_text().strip()
    assert token not in capsys.readouterr().out
    assert client.get("/api/v1/products", headers=bearer(token)).status_code == 200
    with pytest.raises(FileExistsError):
        manage_api_tokens.main()
    assert output.read_text().strip() == token
    monkeypatch.setattr(
        "sys.argv", ["manage_api_tokens", "revoke", "--email", "admin@example.invalid"]
    )
    manage_api_tokens.main()
    assert client.get("/api/v1/products", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("action", ["disable", "set-role", "reset-password"])
def test_user_management_revokes_api_tokens(auth_system, monkeypatch, action):
    from scripts import manage_users

    client, config, factory = auth_system
    token = issue(config, factory)
    monkeypatch.setattr(manage_users, "get_engine", lambda: factory.kw["bind"])
    args = ["manage_users", action, "--email", "admin@example.invalid"]
    if action == "set-role":
        args.extend(["--role", "viewer"])
    if action == "reset-password":
        monkeypatch.setattr(manage_users.getpass, "getpass", lambda _: "Synthetic-new-password!123")
    monkeypatch.setattr("sys.argv", args)
    manage_users.main()
    assert client.get("/api/v1/products", headers=bearer(token)).status_code == 401
