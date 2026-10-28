"""Small, stateless public showcase; no free-form input or operator capabilities."""

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.db.session import get_demo_db
from app.schemas.assistant import AssistantRequest, AssistantResponse
from app.services.ai_provider import AIProvider, ProviderError, get_ai_provider
from app.services.assistant_conversations import AssistantError, Conversation
from app.services.assistant_service import answer, prepare

router = APIRouter(prefix="/demo", tags=["Public Demo"])
QUESTIONS = {
    "forecast": "Explain the latest forecast.",
    "historical": "What are the highest historical sales products?",
    "accuracy": "How accurate are the forecasts?",
}


class DemoQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: Literal["forecast", "historical", "accuracy"]


@router.get("/config")
def demo_config(settings: Settings = Depends(get_settings)):
    return {
        "enabled": settings.public_demo_enabled,
        "label": "Historical synthetic demo data — not real business results",
        "assistant_enabled": settings.public_demo_enabled
        and settings.demo_ai_enabled
        and settings.ai_enabled,
        "questions": [{"id": key, "label": value} for key, value in QUESTIONS.items()],
    }


def demo_ai_available(settings: Settings = Depends(get_settings)) -> Settings:
    if not (settings.public_demo_enabled and settings.demo_ai_enabled and settings.ai_enabled):
        raise HTTPException(
            503, detail={"code": "demo_ai_disabled", "message": "Demo AI is disabled."}
        )
    return settings


@router.post("/assistant", response_model=AssistantResponse)
async def demo_assistant(
    question: DemoQuestion,
    settings: Settings = Depends(demo_ai_available),
    db: Session = Depends(get_demo_db),
    provider: AIProvider = Depends(get_ai_provider),
):
    request = AssistantRequest(message=QUESTIONS[question.question_id])
    conversation = Conversation(owner=uuid4())

    def read_and_release():
        try:
            return prepare(db, request, conversation, settings)
        finally:
            db.rollback()

    try:
        intent, context, evidence = await run_in_threadpool(read_and_release)
        return await answer(
            request, conversation, uuid4(), intent, context, evidence, provider, settings
        )
    except (AssistantError, ProviderError) as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            503, detail={"code": "demo_data_unavailable", "message": "Demo data is unavailable."}
        ) from exc
