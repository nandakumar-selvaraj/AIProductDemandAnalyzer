import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.ai_provider import OllamaProvider, ProviderError
from tests.unit.test_assistant import settings


def native(content='{"fact_ids":["f1"]}', **extra):
    return {"done": True, "done_reason": "stop", "message": {"content": content}, **extra}


def test_native_contract_and_model_readiness():
    requests = []

    async def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
        return httpx.Response(200, json=native())

    async def exercise():
        provider = OllamaProvider(settings(ai_temperature=0.2), httpx.MockTransport(handler))
        assert await provider.ready()
        assert (await provider.select_evidence({"evidence": []})).fact_ids == ["f1"]

    asyncio.run(exercise())
    request = requests[-1]
    assert str(request.url) == "http://private-model:8080/api/chat"
    body = json.loads(request.content)
    assert body["think"] is False and body["stream"] is False
    assert body["options"]["temperature"] == 0.2
    assert body["options"]["num_predict"] == 512
    assert body["format"]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("mode", "code", "status"),
    [
        ("offline", "ai_unavailable", 503),
        ("timeout", "ai_timeout", 504),
        ("empty", "ai_invalid_response", 502),
        ("badjson", "ai_invalid_response", 502),
        ("truncated", "ai_invalid_response", 502),
        ("model", "ai_model_unavailable", 503),
        ("context", "ai_context_overflow", 422),
        ("large", "ai_invalid_response", 502),
    ],
)
def test_sanitized_errors_and_no_retries(mode, code, status):
    calls = []

    async def handler(request):
        calls.append(request)
        if mode == "offline":
            raise httpx.ConnectError("secret internal URL", request=request)
        if mode == "timeout":
            raise httpx.ReadTimeout("secret details", request=request)
        if mode == "model":
            return httpx.Response(404, text="secret model details")
        if mode == "context":
            return httpx.Response(400, text="context length exceeded secret")
        if mode == "large":
            return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(
            200,
            json=native(
                ""
                if mode == "empty"
                else "not JSON"
                if mode == "badjson"
                else '{"fact_ids":["f1"]}',
                done_reason="length" if mode == "truncated" else "stop",
            ),
        )

    provider = OllamaProvider(settings(), httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error:
        asyncio.run(provider.select_evidence({}))
    assert (error.value.code, error.value.status) == (code, status)
    assert "secret" not in str(error.value) and len(calls) == 1


def test_deadline_cancellation_and_slot_release():
    cancelled = []

    async def handler(request):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)

    async def exercise():
        provider = OllamaProvider(settings(ai_timeout_seconds=1), httpx.MockTransport(handler))
        task = asyncio.create_task(provider.select_evidence({}))
        await asyncio.sleep(0.01)
        with pytest.raises(ProviderError, match="busy"):
            await provider.select_evidence({})
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not provider.gate.locked()
        with pytest.raises(ProviderError) as failure:
            await provider.select_evidence({})
        assert failure.value.code == "ai_timeout"

    asyncio.run(exercise())
    assert len(cancelled) == 2


def test_async_openai_sdk_path_is_configurable_and_disables_retries(monkeypatch):
    captured = []

    class FakeSDK:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def chat(self):
            return SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def create(self, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop", message=SimpleNamespace(content='{"fact_ids":["f1"]}')
                    )
                ]
            )

    provider = OllamaProvider(settings(ai_ollama_transport="openai"))

    async def exercise():
        async with provider._sdk() as sdk:
            assert sdk.max_retries == 0
        monkeypatch.setattr(provider, "_sdk", FakeSDK)
        assert (await provider.select_evidence({})).fact_ids == ["f1"]

    asyncio.run(exercise())
    assert captured[0]["max_tokens"] == 512 and captured[0]["stream"] is False
    assert captured[0]["reasoning_effort"] == "none"


@pytest.mark.parametrize("models", [[], ["bad"], [{"name": "other"}], None])
def test_missing_or_malformed_model_list_is_not_ready(models):
    provider = OllamaProvider(
        settings(), httpx.MockTransport(lambda req: httpx.Response(200, json={"models": models}))
    )
    assert not asyncio.run(provider.ready())


@pytest.mark.parametrize(
    "updates",
    [
        {"ai_temperature": -1},
        {"ai_timeout_seconds": 0},
        {"ai_max_output_tokens": 0},
        {"ai_base_url": "http://private-model/not-v1"},
        {"ai_model": ""},
    ],
)
def test_invalid_provider_settings_fail_validation(updates):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        settings(**updates)
