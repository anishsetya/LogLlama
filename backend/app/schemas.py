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
    service_name: str | None = Field(default=None, max_length=160)
    environment: str | None = Field(default=None, max_length=80)
    version: str | None = Field(default=None, max_length=120)
    git_sha: str | None = Field(default=None, max_length=80)
    route: str | None = Field(default=None, max_length=240)
    user_id: str | None = Field(default=None, max_length=160)
    tenant_id: str | None = Field(default=None, max_length=160)
    session_id: str | None = Field(default=None, max_length=160)
    conversation_id: str | None = Field(default=None, max_length=160)
    request_id: str | None = Field(default=None, max_length=160)
    trace_id: str | None = Field(default=None, max_length=160)
    span_id: str | None = Field(default=None, max_length=160)
    prompt_template: str | None = Field(default=None, max_length=160)
    prompt_version: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = None
    custom_metadata: dict[str, Any] | None = None
    privacy: dict[str, Any] | None = None
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
    service_name: str | None
    environment: str | None
    version: str | None
    git_sha: str | None
    route: str | None
    user_id: str | None
    tenant_id: str | None
    session_id: str | None
    conversation_id: str | None
    request_id: str | None
    trace_id: str | None
    span_id: str | None
    prompt_template: str | None
    prompt_version: str | None
    tags: list[str] | None
    custom_metadata: dict[str, Any] | None
    privacy: dict[str, Any] | None
    request_metadata: dict[str, Any] | None
    captured_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestListOut(BaseModel):
    requests: list[RequestOut]


class MetadataFacetsOut(BaseModel):
    service_names: list[str]
    environments: list[str]
    routes: list[str]
    tenant_ids: list[str]
    prompt_templates: list[str]
    models: list[str]
    statuses: list[str]


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
