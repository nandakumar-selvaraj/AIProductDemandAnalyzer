"""Production boundaries and hosted inference use no real external services."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import SecurityMiddleware
from app.main import app
from app.services.ai_provider import HostedProvider, ProviderError

DB = "postgresql+psycopg://test:test@localhost/test"
TOKEN = "a" * 64


def production(**kwargs):
    return Settings(
        _env_file=None, database_url=DB, environment="production", operator_token=TOKEN, **kwargs
    )


def test_production_fails_closed():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=DB, environment="production")
    with pytest.raises(ValidationError):
        production(trusted_hosts=["*"])
    with pytest.raises(ValidationError):
        production(
            ai_enabled=True,
            ai_provider="openai",
            ai_base_url="http://host/v1",
            ai_model="model",
            ai_api_key="secret",
        )


def test_operator_gate_before_database_and_body(monkeypatch):
    settings = production(max_request_bytes=10)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    client = TestClient(app)
    for path in ("/api/v1/ingestion/sales", "/api/v1/forecasts", "/api/v1/assistant/chat"):
        assert client.post(path, content=b"x" * 100).status_code == 401
    assert client.get("/docs").status_code == 404
    assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/v1/health").status_code == 200
    assert (
        client.post(
            "/api/v1/ingestion/sales",
            content=b"x" * 11,
            headers={"Authorization": f"Bearer {TOKEN}"},
        ).status_code
        == 413
    )


def test_rate_and_daily_cap(monkeypatch):
    settings = production(ai_requests_per_minute=1, ai_daily_request_cap=2)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    client = TestClient(SecurityMiddleware(app))
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client.get("/api/v1/assistant/ready", headers=headers)
    assert client.get("/api/v1/assistant/ready", headers=headers).status_code == 429


@pytest.mark.parametrize("mode", ["ok", "invalid", "timeout", "auth", "truncated"])
def test_hosted_contract(mode):
    calls = []

    async def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer test-secret"
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "model"}]})
        import json

        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["stream"] is False
        assert body["max_tokens"] == 512
        if mode == "timeout":
            raise httpx.ReadTimeout("private credentials")
        if mode == "auth":
            return httpx.Response(401, text="private credentials")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if mode == "truncated" else "stop",
                        "message": {
                            "content": "bad" if mode == "invalid" else '{"fact_ids":["f1"]}'
                        },
                    }
                ]
            },
        )

    async def exercise():
        provider = HostedProvider(
            production(
                ai_enabled=True,
                ai_provider="openai",
                ai_base_url="https://host/v1",
                ai_model="model",
                ai_api_key="test-secret",
            ),
            httpx.MockTransport(handler),
        )
        assert await provider.ready()
        if mode == "ok":
            assert (await provider.select_evidence({})).fact_ids == ["f1"]
        else:
            with pytest.raises(ProviderError) as exc:
                await provider.select_evidence({})
            assert "private credentials" not in str(exc.value)

    asyncio.run(exercise())
    assert len(calls) == 2


def test_daily_cap_survives_middleware_recreation(monkeypatch, tmp_path):
    settings = production(ai_usage_file=str(tmp_path / "usage.sqlite"), ai_daily_request_cap=1)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    TestClient(SecurityMiddleware(app)).get("/api/v1/assistant/ready", headers=headers)
    response = TestClient(SecurityMiddleware(app)).get("/api/v1/assistant/ready", headers=headers)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai_daily_cap"
