from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Select, case, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import Base, engine, get_session
from .models import LLMRequest, Project
from .pricing import estimate_cost_usd
from .schemas import EventIn, MetadataFacetsOut, RequestListOut, RequestOut, SummaryOut


CORRELATION_FIELDS = (
    "service_name",
    "environment",
    "version",
    "git_sha",
    "route",
    "user_id",
    "tenant_id",
    "session_id",
    "conversation_id",
    "request_id",
    "trace_id",
    "span_id",
    "prompt_template",
    "prompt_version",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_metadata_columns(conn)

    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Project).where(Project.api_key == settings.default_api_key)
        )
        project = result.scalar_one_or_none()
        if project is None:
            session.add(Project(name=settings.default_project_name, api_key=settings.default_api_key))
            await session.commit()

    yield


app = FastAPI(title="LogLlama API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def project_from_api_key(
    x_logllama_api_key: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Project:
    if not x_logllama_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-LogLlama-Api-Key header.",
        )

    result = await session.execute(select(Project).where(Project.api_key == x_logllama_api_key))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    return project


async def default_project(session: AsyncSession) -> Project:
    result = await session.execute(select(Project).where(Project.api_key == settings.default_api_key))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=500, detail="Default project was not initialized.")
    return project


async def ensure_metadata_columns(conn) -> None:
    statements = [
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS service_name VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS environment VARCHAR(80)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS version VARCHAR(120)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS git_sha VARCHAR(80)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS route VARCHAR(240)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS user_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS session_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS request_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS trace_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS span_id VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS prompt_template VARCHAR(160)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(80)",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS tags JSONB",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS custom_metadata JSONB",
        "ALTER TABLE llm_requests ADD COLUMN IF NOT EXISTS privacy JSONB",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_service_name ON llm_requests (service_name)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_environment ON llm_requests (environment)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_route ON llm_requests (route)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_user_id ON llm_requests (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_tenant_id ON llm_requests (tenant_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_session_id ON llm_requests (session_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_conversation_id ON llm_requests (conversation_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_request_id ON llm_requests (request_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_trace_id ON llm_requests (trace_id)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_prompt_template ON llm_requests (prompt_template)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_project_environment_captured ON llm_requests (project_id, environment, captured_at)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_project_route_captured ON llm_requests (project_id, route, captured_at)",
        "CREATE INDEX IF NOT EXISTS ix_llm_requests_project_tenant_captured ON llm_requests (project_id, tenant_id, captured_at)",
    ]
    for statement in statements:
        await conn.execute(text(statement))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    event: EventIn,
    project: Project = Depends(project_from_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    usage = event.usage
    total_tokens = usage.total_tokens or usage.input_tokens + usage.output_tokens
    cost_usd = event.cost_usd
    if cost_usd is None:
        cost_usd = estimate_cost_usd(event.model, usage.input_tokens, usage.output_tokens)

    normalized = normalize_event_metadata(event)
    request = LLMRequest(
        project_id=project.id,
        external_id=event.external_id,
        provider=event.provider,
        operation=event.operation,
        model=event.model,
        status=event.status,
        prompt=event.prompt,
        response=event.response,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=event.latency_ms,
        error_type=event.error.type if event.error else None,
        error_message=event.error.message if event.error else None,
        service_name=normalized["service_name"],
        environment=normalized["environment"],
        version=normalized["version"],
        git_sha=normalized["git_sha"],
        route=normalized["route"],
        user_id=normalized["user_id"],
        tenant_id=normalized["tenant_id"],
        session_id=normalized["session_id"],
        conversation_id=normalized["conversation_id"],
        request_id=normalized["request_id"],
        trace_id=normalized["trace_id"],
        span_id=normalized["span_id"],
        prompt_template=normalized["prompt_template"],
        prompt_version=normalized["prompt_version"],
        tags=normalized["tags"],
        custom_metadata=normalized["custom_metadata"],
        privacy=normalized["privacy"],
        request_metadata=normalized["request_metadata"],
        captured_at=event.captured_at or datetime.now(timezone.utc),
    )

    session.add(request)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return {"status": "duplicate_ignored"}

    return {"status": "accepted"}


@app.get("/api/requests", response_model=RequestListOut)
async def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    model: str | None = None,
    service_name: str | None = None,
    environment: str | None = None,
    route: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    prompt_template: str | None = None,
    prompt_version: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> RequestListOut:
    project = await default_project(session)
    query: Select[tuple[LLMRequest]] = select(LLMRequest).where(LLMRequest.project_id == project.id)

    if status_filter:
        query = query.where(LLMRequest.status == status_filter)
    if model:
        query = query.where(LLMRequest.model == model)
    filters = {
        "service_name": service_name,
        "environment": environment,
        "route": route,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "trace_id": trace_id,
        "prompt_template": prompt_template,
        "prompt_version": prompt_version,
    }
    for field, value in filters.items():
        if value:
            query = query.where(getattr(LLMRequest, field) == value)

    query = query.order_by(LLMRequest.captured_at.desc()).limit(limit)
    result = await session.execute(query)
    return RequestListOut(requests=list(result.scalars()))


@app.get("/api/metadata/facets", response_model=MetadataFacetsOut)
async def metadata_facets(session: AsyncSession = Depends(get_session)) -> MetadataFacetsOut:
    project = await default_project(session)
    return MetadataFacetsOut(
        service_names=await distinct_values(session, project.id, LLMRequest.service_name),
        environments=await distinct_values(session, project.id, LLMRequest.environment),
        routes=await distinct_values(session, project.id, LLMRequest.route),
        tenant_ids=await distinct_values(session, project.id, LLMRequest.tenant_id),
        prompt_templates=await distinct_values(session, project.id, LLMRequest.prompt_template),
        models=await distinct_values(session, project.id, LLMRequest.model),
        statuses=await distinct_values(session, project.id, LLMRequest.status),
    )


@app.get("/api/traces/{trace_id}", response_model=RequestListOut)
async def get_trace(trace_id: str, session: AsyncSession = Depends(get_session)) -> RequestListOut:
    project = await default_project(session)
    result = await session.execute(
        select(LLMRequest)
        .where(LLMRequest.project_id == project.id, LLMRequest.trace_id == trace_id)
        .order_by(LLMRequest.captured_at.asc())
    )
    return RequestListOut(requests=list(result.scalars()))


@app.get("/api/conversations/{conversation_id}", response_model=RequestListOut)
async def get_conversation(conversation_id: str, session: AsyncSession = Depends(get_session)) -> RequestListOut:
    project = await default_project(session)
    result = await session.execute(
        select(LLMRequest)
        .where(LLMRequest.project_id == project.id, LLMRequest.conversation_id == conversation_id)
        .order_by(LLMRequest.captured_at.asc())
    )
    return RequestListOut(requests=list(result.scalars()))


@app.get("/api/requests/{request_id}", response_model=RequestOut)
async def get_request(request_id: UUID, session: AsyncSession = Depends(get_session)) -> LLMRequest:
    project = await default_project(session)
    result = await session.execute(
        select(LLMRequest).where(LLMRequest.id == request_id, LLMRequest.project_id == project.id)
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    return request


@app.get("/api/metrics/summary", response_model=SummaryOut)
async def metrics_summary(
    hours: int = Query(default=24, ge=1, le=24 * 30),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    project = await default_project(session)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    total_query = select(
        func.count(LLMRequest.id),
        func.coalesce(func.sum(LLMRequest.cost_usd), Decimal("0")),
        func.coalesce(func.avg(LLMRequest.latency_ms), 0),
        func.coalesce(func.sum(case((LLMRequest.status == "error", 1), else_=0)), 0),
        func.coalesce(func.sum(LLMRequest.total_tokens), 0),
    ).where(LLMRequest.project_id == project.id, LLMRequest.captured_at >= since)
    total_result = await session.execute(total_query)
    total_requests, total_cost, avg_latency, error_count, total_tokens = total_result.one()

    bucket = func.date_trunc("hour", LLMRequest.captured_at).label("bucket")
    series_query = (
        select(
            bucket,
            func.count(LLMRequest.id).label("requests"),
            func.coalesce(func.sum(LLMRequest.cost_usd), Decimal("0")).label("cost_usd"),
            func.coalesce(func.avg(LLMRequest.latency_ms), 0).label("avg_latency_ms"),
            func.coalesce(func.sum(case((LLMRequest.status == "error", 1), else_=0)), 0).label("error_count"),
        )
        .where(LLMRequest.project_id == project.id, LLMRequest.captured_at >= since)
        .group_by(bucket)
        .order_by(bucket)
    )
    series_result = await session.execute(series_query)
    series = [
        {
            "bucket": row.bucket,
            "requests": row.requests,
            "cost_usd": row.cost_usd,
            "avg_latency_ms": float(row.avg_latency_ms),
            "error_count": row.error_count,
        }
        for row in series_result
    ]

    total_requests = int(total_requests or 0)
    error_rate = float(error_count or 0) / total_requests if total_requests else 0.0
    return SummaryOut(
        total_requests=total_requests,
        total_cost_usd=total_cost,
        avg_latency_ms=float(avg_latency or 0),
        error_rate=error_rate,
        total_tokens=int(total_tokens or 0),
        series=series,
    )


def normalize_event_metadata(event: EventIn) -> dict[str, object]:
    metadata = dict(event.metadata or {})
    custom_metadata = dict(event.custom_metadata or {})

    normalized: dict[str, object] = {}
    for field in CORRELATION_FIELDS:
        normalized[field] = getattr(event, field) or metadata.get(field)

    tags = event.tags if event.tags is not None else metadata.get("tags")
    normalized["tags"] = tags if isinstance(tags, list) else []

    metadata_custom = metadata.get("custom_metadata")
    if isinstance(metadata_custom, dict):
        custom_metadata = {**metadata_custom, **custom_metadata}

    reserved = {*CORRELATION_FIELDS, "tags", "custom_metadata", "privacy"}
    for key, value in metadata.items():
        if key not in reserved:
            custom_metadata.setdefault(key, value)

    normalized["custom_metadata"] = custom_metadata
    normalized["privacy"] = event.privacy or metadata.get("privacy") or {}
    normalized["request_metadata"] = {
        **{field: value for field, value in normalized.items() if field in CORRELATION_FIELDS and value is not None},
        "tags": normalized["tags"],
        "custom_metadata": custom_metadata,
    }
    return normalized


async def distinct_values(session: AsyncSession, project_id: UUID, column) -> list[str]:
    result = await session.execute(
        select(column)
        .where(LLMRequest.project_id == project_id, column.is_not(None))
        .distinct()
        .order_by(column)
        .limit(200)
    )
    return [str(value) for value in result.scalars() if value]
