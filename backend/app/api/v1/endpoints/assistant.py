"Non-streaming local-first assistant; no model-controlled tools or database writes."

import asyncio
import logging
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.schemas.ingestion import ErrorResponse
from app.services.ai_provider import AIProvider, ProviderError, get_ai_provider
from app.services.assistant_conversations import AssistantError, conversations
from app.services.assistant_service import answer, prepare

router = APIRouter(prefix="/assistant", tags=["Assistant"])
logger = logging.getLogger(__name__)


def enabled(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.ai_enabled:
        raise HTTPException(
            503,
            detail={
                "code": "ai_disabled",
                "message": "AI Assistant is disabled. Configure the backend AI settings.",
            },
        )
    return settings


@router.get("/ready", responses={503: {"model": ErrorResponse}})
async def readiness(
    settings: Settings = Depends(enabled), provider: AIProvider = Depends(get_ai_provider)
):
    if not await provider.ready():
        raise HTTPException(
            503,
            detail={
                "code": "ai_not_ready",
                "message": "AI provider or configured model is not ready.",
            },
        )
    return {"status": "ready", "provider": settings.ai_provider}


@router.post(
    "/chat",
    response_model=AssistantResponse,
    responses={status: {"model": ErrorResponse} for status in (404, 409, 429, 502, 503, 504)},
)
async def chat(
    request: AssistantRequest,
    http_request: Request,
    x_assistant_session: UUID = Header(...),
    settings: Settings = Depends(enabled),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> AssistantResponse:
    conversation_id = None
    completed = False
    started = time.monotonic()
    try:
        conversation_id, conversation = conversations.begin(
            x_assistant_session,
            request.conversation_id,
            settings.ai_conversation_ttl_seconds,
            settings.ai_max_conversations,
        )

        def read_and_release():
            try:
                return prepare(db, request, conversation, settings)
            finally:
                db.rollback()

        # All synchronous SQL is off the event loop and releases its connection before inference.
        intent, context, evidence = await run_in_threadpool(read_and_release)

        generation = asyncio.create_task(
            answer(
                request,
                conversation,
                conversation_id,
                intent,
                context,
                evidence,
                provider,
                settings,
            )
        )
        try:
            while not generation.done():
                done, _ = await asyncio.wait({generation}, timeout=0.2)
                if not done and await http_request.is_disconnected():
                    raise AssistantError(
                        "assistant_cancelled", "The client cancelled the request.", 499
                    )
            result = await generation
        finally:
            if not generation.done():
                generation.cancel()
            await asyncio.gather(generation, return_exceptions=True)
        conversations.finish(
            conversation_id,
            context,
            intent,
            request.message,
            result.answer,
            settings.ai_max_history_messages,
        )
        completed = True
        logger.info(
            "Assistant completed intent=%s sources=%s provider_used=%s elapsed_ms=%s",
            intent,
            len(result.sources),
            result.provider_used,
            round((time.monotonic() - started) * 1000),
        )
        return result
    except (AssistantError, ProviderError) as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    except SQLAlchemyError as exc:
        logger.warning("Assistant business data query failed (%s)", type(exc).__name__)
        raise HTTPException(
            503,
            detail={
                "code": "assistant_data_unavailable",
                "message": "Business data is unavailable. Check database readiness.",
            },
        ) from exc
    finally:
        if conversation_id is not None and not completed:
            conversations.abort(conversation_id)
