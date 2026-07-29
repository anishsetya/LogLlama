import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    runtime_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    requests: Mapped[list["LLMRequest"]] = relationship(back_populates="project")
    provider_credentials: Mapped[list["ProviderCredential"]] = relationship(back_populates="project")
    test_plans: Mapped[list["TestPlan"]] = relationship(back_populates="project")


class LLMRequest(Base):
    __tablename__ = "llm_requests"
    __table_args__ = (
        UniqueConstraint("project_id", "external_id", name="uq_llm_requests_project_external_id"),
        Index("ix_llm_requests_project_environment_captured", "project_id", "environment", "captured_at"),
        Index("ix_llm_requests_project_route_captured", "project_id", "route", "captured_at"),
        Index("ix_llm_requests_project_tenant_captured", "project_id", "tenant_id", "captured_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    prompt: Mapped[dict | list | str | None] = mapped_column(JSONB, nullable=True)
    response: Mapped[dict | list | str | None] = mapped_column(JSONB, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), default=Decimal("0"), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    git_sha: Mapped[str | None] = mapped_column(String(80), nullable=True)
    route: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    span_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_template: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    custom_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    privacy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

    project: Mapped[Project] = relationship(back_populates="requests")


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", name="uq_provider_credentials_project_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="provider_credentials")


class TestPlan(Base):
    __tablename__ = "test_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system: Mapped[str | None] = mapped_column(Text, nullable=True)
    targets: Mapped[list] = mapped_column(JSONB, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    max_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    requested_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship(back_populates="test_plans")
