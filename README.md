# LogLlama

AI-native observability for LLM apps. This first MVP captures OpenAI requests from a Python SDK, ingests them through FastAPI, stores them in PostgreSQL, and shows them in a simple React dashboard.

## What Is Included

- Python SDK for wrapping an OpenAI client.
- FastAPI ingestion backend.
- PostgreSQL storage through SQLAlchemy.
- React dashboard for request logs, cost, latency, token usage, and errors.
- Docker Compose for local PostgreSQL.

## Project Layout

```text
backend/        FastAPI API and database models
sdk/python/     Python SDK package
dashboard/      React dashboard
examples/       Minimal instrumented OpenAI app
```

## Local Setup

1. Start PostgreSQL:

```bash
docker compose up -d postgres
```

2. Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend seeds a default project with this SDK key:

```text
llama-dev-key
```

3. Start the dashboard:

```bash
cd dashboard
npm install
npm run dev
```

4. Use the SDK from an app:

```bash
cd sdk/python
pip install -e .
```

```python
from openai import OpenAI
from logllama import track_openai

client = track_openai(
    OpenAI(api_key="your-openai-key"),
    api_key="llama-dev-key",
)

client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello"}],
)
```

Or send a sample captured request without an OpenAI key:

```bash
python scripts/send_sample_event.py
```

## Environment Variables

Backend:

```text
DATABASE_URL=postgresql+asyncpg://logllama:logllama@localhost:5432/logllama
LOGLLAMA_DEFAULT_API_KEY=llama-dev-key
LOGLLAMA_DEFAULT_PROJECT_NAME=Development
```

SDK:

```text
LOGLLAMA_API_KEY=llama-dev-key
LOGLLAMA_ENDPOINT=http://localhost:8000
```

## API

- `POST /v1/events` ingests SDK events. Requires `X-LogLlama-Api-Key`.
- `GET /api/requests` lists captured requests.
- `GET /api/requests/{request_id}` fetches one captured request.
- `GET /api/metrics/summary` returns dashboard metrics.
- `GET /health` checks service health.
