"""Bounded non-streaming business assistant contract."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intent = Literal[
    "historical", "forecast", "recommendations", "evaluation", "backtest", "general", "unsupported"
]


class AssistantContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    forecast_run_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    product_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    store_id: int | None = Field(default=None, gt=0, le=2_147_483_647)
    start_date: date | None = None
    end_date: date | None = None
    backtest_cutoff: date | None = None
    backtest_horizon_days: int = Field(default=30, ge=1, le=30)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days
            if days < 0 or days > 364:
                raise ValueError("Dates must be in order and span at most 365 inclusive days")
        return self


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: UUID | None = None
    context: AssistantContext | None = None

    @field_validator("message")
    @classmethod
    def meaningful_message(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 and char not in "\n\t\r" for char in value):
            raise ValueError("Enter a non-empty question without control characters")
        return value


class AssistantSource(BaseModel):
    id: str
    type: Literal[
        "historical", "forecast", "recommendation", "evaluation", "backtest", "application"
    ]
    label: str
    forecast_run_id: int | None = None
    product_id: int | None = None
    store_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None


class AssistantResponse(BaseModel):
    answer: str
    conversation_id: UUID
    intent: Intent
    context: AssistantContext
    sources: list[AssistantSource]
    warnings: list[str]
    generated_at: datetime
    provider_used: bool


class ModelSelection(BaseModel):
    """The model can select evidence, never supply arbitrary facts or executable tools."""

    model_config = ConfigDict(extra="forbid")
    fact_ids: list[str] = Field(min_length=1, max_length=8)
