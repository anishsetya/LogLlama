from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsagePayload(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ErrorPayload(BaseModel):
    type: str | None = None
    message: str | None = None


class EventIn(BaseModel):
    external_id: str | None = None
    provider: str = Field(default="openai", max_length=40)
    operation: str = Field(default="chat.completions.create", max_length=120)
    model: str | None = None
    status: str = Field(pattern="^(success|error)$")
    prompt: Any = None
    response: Any = None
    usage: UsagePayload = Field(default_factory=UsagePayload)
    cost_usd: Decimal | None = None
    latency_ms: int = Field(default=0, ge=0)
    error: ErrorPayload | None = None
    metadata: dict[str, Any] | None = None
    captured_at: datetime | None = None


class RequestOut(BaseModel):
    id: UUID
    external_id: str | None
    provider: str
    operation: str
    model: str | None
    status: str
    prompt: Any
    response: Any
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    error_type: str | None
    error_message: str | None
    request_metadata: dict[str, Any] | None
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestListOut(BaseModel):
    requests: list[RequestOut]


class MetricPoint(BaseModel):
    bucket: datetime
    requests: int
    cost_usd: Decimal
    avg_latency_ms: float
    error_count: int


class SummaryOut(BaseModel):
    total_requests: int
    total_cost_usd: Decimal
    avg_latency_ms: float
    error_rate: float
    total_tokens: int
    series: list[MetricPoint]

