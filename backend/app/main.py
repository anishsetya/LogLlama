from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Select, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import Base, engine, get_session
from .models import LLMRequest, Project
from .pricing import estimate_cost_usd
from .schemas import EventIn, RequestListOut, RequestOut, SummaryOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        request_metadata=event.metadata,
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
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> RequestListOut:
    project = await default_project(session)
    query: Select[tuple[LLMRequest]] = select(LLMRequest).where(LLMRequest.project_id == project.id)

    if status_filter:
        query = query.where(LLMRequest.status == status_filter)
    if model:
        query = query.where(LLMRequest.model == model)

    query = query.order_by(LLMRequest.captured_at.desc()).limit(limit)
    result = await session.execute(query)
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
