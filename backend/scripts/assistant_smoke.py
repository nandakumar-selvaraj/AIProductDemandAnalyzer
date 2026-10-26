"""Opt-in Ollama probe: python -m scripts.assistant_smoke [--api-url URL]."""

import argparse
import asyncio
import json
import time
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.services.ai_provider import OllamaProvider, ProviderError


async def probe(api_url: str | None = None, both: bool = False) -> int:
    settings = get_settings()
    provider = OllamaProvider(settings)
    if not settings.ai_enabled or not await provider.ready():
        print("Provider is disabled or configured Ollama model is not installed/ready.")
        return 1
    modes = ["native", "openai"] if both else [settings.ai_ollama_transport]
    for mode in modes:
        adapter = OllamaProvider(settings.model_copy(update={"ai_ollama_transport": mode}))
        started = time.monotonic()
        try:
            result = await adapter.select_evidence(
                {
                    "question": "Select connectivity evidence.",
                    "history": [],
                    "evidence": [{"id": "f1", "text": "Connectivity verified."}],
                }
            )
            assert result.fact_ids == ["f1"]
        except (ProviderError, AssertionError) as exc:
            print(f"{mode} failed: {exc}")
            return 1
        print(f"{mode}: valid visible structured answer, {time.monotonic() - started:.2f}s")
    if api_url:
        async with httpx.AsyncClient(
            timeout=settings.ai_timeout_seconds + 10, trust_env=False
        ) as client:
            owner = {"X-Assistant-Session": str(uuid4())}
            conversation_id = None
            base = api_url.rstrip("/")
            latest = await client.get(base + "/forecasts/latest")
            latest.raise_for_status()
            run = latest.json()
            if run is None:
                print("No completed forecast run; run-dependent smoke checks cannot execute.")
                return 1
            predictions = await client.get(
                base + f"/forecasts/{run['id']}/predictions", params={"page": 1, "page_size": 1}
            )
            predictions.raise_for_status()
            rows = predictions.json()["items"]
            if not rows:
                print("Completed run has no prediction rows; scoped smoke checks cannot execute.")
                return 1
            product, store = rows[0]["product_id"], rows[0]["store_id"]
            for question in [
                "How does this application calculate forecasts?",
                f"What is the forecast for product {product}?",
                "How reliable is this forecast?",
                f"How many units did product {product} sell?",
                f"Explain the recommendation for product {product} and store {store}.",
            ]:
                started = time.monotonic()
                response = await client.post(
                    api_url.rstrip("/") + "/assistant/chat",
                    headers=owner,
                    json={"message": question, "conversation_id": conversation_id},
                )
                response.raise_for_status()
                data = response.json()
                assert data["answer"].strip() and data["conversation_id"]
                conversation_id = data["conversation_id"]
                print(
                    json.dumps(
                        {
                            "question": question,
                            "intent": data["intent"],
                            "sources": len(data["sources"]),
                            "context": data["context"],
                            "elapsed_seconds": round(time.monotonic() - started, 2),
                        }
                    )
                )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", help="Explicit local FastAPI base including /api/v1")
    parser.add_argument("--both-transports", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(probe(args.api_url, args.both_transports)))
