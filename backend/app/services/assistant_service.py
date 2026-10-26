"Controlled intent routing and numerical grounding with bounded evidence selection."

import json
import re
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.assistant import AssistantContext, AssistantRequest, AssistantResponse, Intent
from app.services.ai_provider import AIProvider, ProviderError
from app.services.assistant_conversations import AssistantError, Conversation
from app.services.assistant_data import Evidence, retrieve


def classify(question: str, previous: Intent = "general") -> Intent:
    text = question.lower()
    if re.search(
        (
            "\\b(sql|password|credentials?|secrets?|api.?key|system "
            "prompt)\\b|ignore.{0,30}instructions|\\b(buy|order|purchase)\\s+\\d"
        ),
        text,
    ):
        return "unsupported"
    if "backtest" in text:
        return "backtest"
    if any(
        term in text
        for term in [
            "how does",
            "how do",
            "what is wape",
            "what does wape",
            "what is mae",
            "what does mae",
            "cutoff date",
            "difference between",
            "calculated",
            "forecasting work",
            "what is demand forecasting",
            "how should a business interpret",
            "recommendations generated",
        ]
    ):
        return "general"
    if any(term in text for term in ["mae", "wape", "accura", "reliab", "evaluation", "coverage"]):
        return "evaluation"
    if any(term in text for term in ["histor", "sales", "sold", "sell"]):
        return "historical"
    if any(
        term in text
        for term in [
            "recommend",
            "stocking",
            "increas",
            "decreas",
            "insufficient",
            "reduc",
            "declin",
        ]
    ):
        return "recommendations"
    if any(term in text for term in ["forecast", "predict", "future demand", "expected demand"]):
        return "forecast"
    if any(
        term in text
        for term in ["histor", "sales", "sold", "sell", "trend", "across stores", "compare stores"]
    ):
        return "historical"
    if text.startswith(("what about", "how about", "and ", "why", "explain", "show more")):
        return previous
    return "unsupported"


def resolve_context(request: AssistantRequest, previous: AssistantContext) -> AssistantContext:
    values = previous.model_dump()
    if request.context is not None:
        values.update(request.context.model_dump(exclude_unset=True))
    for kind, field in [
        ("product", "product_id"),
        ("store", "store_id"),
        ("run", "forecast_run_id"),
    ]:
        ids = set(re.findall(rf"\b{kind}\s*(?:id\s*)?#?\s*([+-]?\d+)", request.message, re.I))
        if len(ids) > 1:
            raise AssistantError("ambiguous_context", f"Ask about one {kind} ID at a time.")
        if ids:
            values[field] = int(ids.pop())
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", request.message)
    if dates:
        if len(dates) == 1 and "backtest" in request.message.lower():
            values["backtest_cutoff"] = dates[0]
        elif len(dates) == 2:
            values.update(start_date=dates[0], end_date=dates[1])
        else:
            raise AssistantError(
                "invalid_date_range",
                "Provide both start and end dates in ISO format, or use the context controls.",
            )
    if "backtest" in request.message.lower():
        horizon = re.search(r"\b(\d+)\s*[- ]?days?\b", request.message, re.I)
        if horizon:
            values["backtest_horizon_days"] = int(horizon.group(1))
    try:
        return AssistantContext.model_validate(values)
    except ValidationError as exc:
        raise AssistantError(
            "invalid_context",
            (
                "Use positive IDs and an ordered historical date range of at most "
                "365 inclusive days."
            ),
        ) from exc


def prepare(db: Session, request: AssistantRequest, conversation: Conversation, settings: Settings):
    intent = classify(request.message, conversation.intent)
    if intent == "unsupported":
        if "highest-demand" in request.message.lower():
            return (
                intent,
                conversation.context.model_copy(),
                Evidence(
                    warnings=[
                        (
                            "Do you mean highest recorded historical sales or highest "
                            "persisted predicted demand? Please specify actual sales or "
                            "forecasts."
                        )
                    ]
                ),
            )
        return (
            intent,
            conversation.context.model_copy(),
            Evidence(
                warnings=[
                    (
                        "Ask about historical product sales, persisted forecasts, demand "
                        "recommendations, forecast evaluation or application rules. SQL, "
                        "credentials and unsupported purchase quantities are not "
                        "available."
                    )
                ]
            ),
        )
    context = resolve_context(request, conversation.context)
    try:
        evidence = retrieve(db, intent, context, request.message, settings)
    except ValueError as exc:
        raise AssistantError(
            "invalid_date_range",
            "The historical date scope is unavailable or exceeds 365 inclusive days.",
        ) from exc
    return intent, context, evidence


async def answer(
    request: AssistantRequest,
    conversation: Conversation,
    conversation_id,
    intent: Intent,
    context: AssistantContext,
    evidence: Evidence,
    provider: AIProvider,
    settings: Settings,
) -> AssistantResponse:
    used = False
    if not evidence.facts:
        text = "I cannot provide a grounded finding for this question and scope. " + " ".join(
            evidence.warnings
        )
        sources = []
    else:
        payload = {
            "question": request.message,
            "history": [
                row
                for row in conversation.history[-settings.ai_max_history_messages :]
                if row["role"] == "user"
            ],
            "evidence": [],
        }
        # Count UTF-8 bytes conservatively against a character-named compatibility setting.
        while (
            len(json.dumps(payload, ensure_ascii=False).encode())
            > settings.ai_context_char_limit // 2
            and payload["history"]
        ):
            payload["history"].pop(0)
        chosen_facts = []
        for fact in evidence.facts[: settings.ai_max_context_records]:
            candidate = {**payload, "evidence": chosen_facts + [fact]}
            if (
                len(json.dumps(candidate, ensure_ascii=False).encode())
                > settings.ai_context_char_limit
            ):
                break
            chosen_facts.append(fact)
        if not chosen_facts:
            raise AssistantError(
                "context_limit",
                (
                    "Question and evidence exceed the context budget. Shorten the "
                    "question or select a narrower scope."
                ),
            )
        if len(chosen_facts) < len(evidence.facts):
            evidence.warnings.append(
                f"Context budget includes {len(chosen_facts)} of {len(evidence.facts)} "
                f"retrieved evidence records."
            )
        payload["evidence"] = chosen_facts
        selection = await provider.select_evidence(payload)
        by_id = {fact["id"]: fact["text"] for fact in chosen_facts}
        ids = list(dict.fromkeys(selection.fact_ids))
        if any(key not in by_id for key in ids):
            raise ProviderError(
                "ai_ungrounded_response",
                "The AI selected unsupported evidence. No unverified answer was used.",
                502,
            )
        # Only verified statements are rendered: arbitrary model prose/numbers are never trusted.
        text = (
            "Application explanation:\n"
            if intent == "general"
            else "Based on verified business data for this scope:\n"
        ) + "\n\n".join(f"[{key}] {by_id[key]}" for key in ids)
        sources = [source for source in evidence.sources if source.id in ids]
        used = True
    return AssistantResponse(
        answer=text,
        conversation_id=conversation_id,
        intent=intent,
        context=context,
        sources=sources,
        warnings=list(dict.fromkeys(evidence.warnings)),
        generated_at=datetime.now(UTC),
        provider_used=used,
    )
