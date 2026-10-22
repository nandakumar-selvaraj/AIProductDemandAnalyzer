from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RowIssue(BaseModel):
    """Description of one rejected CSV row (line numbers include the header)."""

    row: int = Field(ge=1, description="CSV line number, including the header row", examples=[4])
    reason: str = Field(
        description="Reason the row was rejected", examples=["sales must be a non-negative integer"]
    )


class IngestionSummary(BaseModel):
    """Counts and validation issues returned after processing a sales CSV."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "records_read": 3,
                    "inserted": 1,
                    "updated": 1,
                    "rejected": 1,
                    "skipped": 0,
                    "validation_only": False,
                    "issues": [{"row": 4, "reason": "sales must be a non-negative integer"}],
                }
            ]
        }
    )

    records_read: int = Field(description="CSV data rows examined", examples=[3])
    inserted: int = Field(description="New daily sales records inserted", examples=[1])
    updated: int = Field(description="Existing daily sales records updated", examples=[1])
    rejected: int = Field(description="Rows rejected during validation", examples=[1])
    skipped: int = Field(
        description="Duplicate source rows ignored; the last duplicate is applied", examples=[0]
    )
    validation_only: bool = Field(
        default=False,
        description="Whether the request only validated data without writing to PostgreSQL",
    )
    issues: list[RowIssue] = Field(
        default_factory=list, description="Up to 100 rejected-row details"
    )


class HealthResponse(BaseModel):
    status: str = Field(description="Service state", examples=["ok", "ready"])


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code", examples=["invalid_csv"])
    message: str = Field(
        description="Safe summary of the error",
        examples=["CSV must include date, store, item, and sales columns"],
    )
    details: list[dict[str, Any]] | None = Field(
        default=None, description="Optional request validation details"
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail
