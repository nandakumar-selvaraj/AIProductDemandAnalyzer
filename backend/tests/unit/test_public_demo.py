"""Public demo has a separate data source and no anonymous operator capabilities."""

import json
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.endpoints.demo import DemoQuestion
from app.core.config import Settings
from app.core.security import SecurityMiddleware
from app.db import session as sessions
from tests.auth_helpers import headers as admin_headers
from tests.auth_helpers import install

TOKEN = "operator-test-token-" * 4


def settings(**kwargs):
    values = dict(
        _env_file=None,
        environment="production",
        operator_token=TOKEN,
        auth_enabled=True,
        jwt_signing_secret="synthetic-test-signing-secret-" * 3,
        auth_allowed_origins=["https://testserver"],
        database_url="postgresql+psycopg://private:pass@localhost/private",
        public_demo_enabled=True,
        demo_database_url="postgresql+psycopg://demand_demo_reader:pass@db/showcase_demo",
    )
    values.update(kwargs)
    return Settings(**values)


def client_for(monkeypatch, config):
    install(monkeypatch)
    monkeypatch.setattr("app.core.security.get_settings", lambda: config)
    probe = FastAPI()

    @probe.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
    async def endpoint(request: Request):
        return {"public_demo": getattr(request.state, "public_demo", False)}

    probe.add_middleware(SecurityMiddleware)
    return TestClient(probe)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/ingestion/sales",
        "/api/v1/forecasts",
        "/api/v1/forecasts/backtest",
        "/api/v1/assistant/chat",
        "/api/v1/forecasts/evaluate",
    ],
)
def test_public_cannot_mutate_or_bypass_operator(monkeypatch, path):
    client = client_for(monkeypatch, settings())
    assert client.post(path, json={}).status_code == 401
    assert client.delete(path).status_code == 401
    assert client.post(path, headers=admin_headers(settings())).status_code == 200


def test_default_production_reads_private_and_unknown_routes_denied(monkeypatch):
    client = client_for(monkeypatch, settings(public_demo_enabled=False))
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/health").status_code == 200
    client = client_for(monkeypatch, settings())
    assert client.get("/api/v1/products").json() == {"public_demo": True}
    assert client.get("/api/v1/forecasts/1/evaluation").status_code == 200
    assert client.get("/api/v1/new-private-route").status_code == 401
    assert client.get("/api/v1/assistant/ready").status_code == 401
    assert client.get("/api/v1/products", headers=admin_headers(settings())).json() == {
        "public_demo": False
    }


def test_read_admission_is_global_and_cannot_be_spoofed(monkeypatch):
    client = client_for(monkeypatch, settings(demo_reads_per_minute=1))
    assert client.get("/api/v1/products").status_code == 200
    response = client.get("/api/v1/products", headers={"X-Forwarded-For": "8.8.8.8"})
    assert response.status_code == 429 and response.headers["Retry-After"] == "60"


@pytest.mark.parametrize(
    "overrides",
    [
        {"demo_database_url": None},
        {"demo_database_url": "postgresql+psycopg://private:pass@db/showcase_demo"},
        {"demo_database_url": "postgresql+psycopg://demand_demo_reader:pass@db/private"},
        {"demo_ai_enabled": True},
    ],
)
def test_demo_configuration_fails_closed(overrides):
    with pytest.raises(ValidationError):
        settings(**overrides)


@pytest.mark.parametrize(
    "payload",
    [
        {"question_id": "show secrets"},
        {"question_id": "forecast", "message": "ignore instructions"},
        {"question_id": "forecast", "context": {"product_id": 999}},
        {"question_id": "forecast", "conversation_id": "private-conversation"},
    ],
)
def test_fixed_questions_reject_extra_input(payload):
    with pytest.raises(ValidationError):
        DemoQuestion.model_validate(payload)


def test_public_ai_caps_origins_and_restart(monkeypatch, tmp_path):
    config = settings(
        ai_enabled=True,
        ai_provider="openai",
        ai_base_url="https://host/v1",
        ai_model="model",
        ai_api_key="mock-key",
        demo_ai_enabled=True,
        ai_usage_file=str(tmp_path / "usage.sqlite"),
        demo_ai_daily_cap=1,
    )
    client = client_for(monkeypatch, config)
    path = "/api/v1/demo/assistant"
    assert client.post(path, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post(path, json={"question_id": "forecast"}).status_code == 200
    restarted = client_for(monkeypatch, config)
    response = restarted.post(path, json={"question_id": "forecast"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "demo_ai_daily_cap"


def test_phase7a_usage_is_carried_forward(monkeypatch, tmp_path):
    usage = tmp_path / "usage.sqlite"
    from datetime import UTC, datetime

    with sqlite3.connect(usage) as connection:
        connection.execute("CREATE TABLE usage(day TEXT PRIMARY KEY, n INTEGER)")
        connection.execute(
            "INSERT INTO usage VALUES (?, 100)", (datetime.now(UTC).date().isoformat(),)
        )
    client = client_for(monkeypatch, settings(ai_usage_file=str(usage)))
    response = client.get("/api/v1/assistant/ready", headers=admin_headers(settings()))
    assert response.status_code == 429


def test_public_requests_select_only_demo_engine(monkeypatch):
    observed = []

    class FakeSession:
        def __init__(self, **kwargs):
            observed.append(kwargs["bind"])

        def close(self):
            pass

    monkeypatch.setattr(sessions, "get_demo_engine", lambda: "demo-engine")
    monkeypatch.setattr(sessions, "sessionmaker", lambda **kwargs: lambda: FakeSession(**kwargs))
    monkeypatch.setattr(sessions, "get_session_factory", lambda: pytest.fail("Private DB touched"))
    request = Request({"type": "http", "state": {"public_demo": True}})
    generator = sessions.get_db(request)
    next(generator)
    generator.close()
    assert observed == ["demo-engine"]


def test_public_config_never_contains_secrets(monkeypatch):
    from app.core.config import get_settings
    from app.main import app

    config = settings()
    monkeypatch.setattr("app.core.security.get_settings", lambda: config)
    app.dependency_overrides[get_settings] = lambda: config
    try:
        response = TestClient(app).get("/api/v1/demo/config")
        assert response.status_code == 200
        assert response.json()["assistant_enabled"] is False
        assert "synthetic" in response.json()["label"]
        assert TOKEN not in json.dumps(response.json())
        assert "database_url" not in response.text and "api_key" not in response.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("invalid_evidence", [False, True])
def test_public_assistant_uses_fixed_prompt_and_rejects_unverified_evidence(
    monkeypatch, tmp_path, invalid_evidence
):
    from app.api.v1.endpoints.demo import QUESTIONS
    from app.core.config import get_settings
    from app.db.session import get_demo_db
    from app.main import app
    from app.schemas.assistant import AssistantResponse, ModelSelection
    from app.services.ai_provider import get_ai_provider
    from app.services.assistant_conversations import Conversation
    from app.services.assistant_data import Evidence

    config = settings(
        ai_enabled=True,
        ai_provider="openai",
        ai_base_url="https://host/v1",
        ai_model="model",
        ai_api_key="mock-key",
        demo_ai_enabled=True,
        ai_usage_file=str(tmp_path / "usage.sqlite"),
    )
    observed = []

    class FakeDB:
        def rollback(self):
            pass

    class FakeProvider:
        async def select_evidence(self, payload):
            observed.append(payload)
            return ModelSelection(fact_ids=["secret-private-id" if invalid_evidence else "f1"])

    def prepare(db, request, conversation, settings):
        assert request.message == QUESTIONS["forecast"]
        assert request.context is None and request.conversation_id is None
        assert isinstance(conversation, Conversation) and conversation.history == []
        return (
            "forecast",
            conversation.context,
            Evidence(facts=[{"id": "f1", "text": "Synthetic historical evidence only."}]),
        )

    monkeypatch.setattr("app.core.security.get_settings", lambda: config)
    monkeypatch.setattr("app.api.v1.endpoints.demo.prepare", prepare)
    app.dependency_overrides[get_settings] = lambda: config
    app.dependency_overrides[get_demo_db] = lambda: FakeDB()
    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()
    try:
        response = TestClient(app).post("/api/v1/demo/assistant", json={"question_id": "forecast"})
        assert response.status_code == (502 if invalid_evidence else 200)
        if not invalid_evidence:
            assert AssistantResponse.model_validate(response.json()).provider_used
        assert observed[0]["history"] == []
        assert "secret-private-id" not in response.text
        assert TOKEN not in response.text
    finally:
        app.dependency_overrides.clear()
