# LogLlama

LLM observability in two lines of Python.

LogLlama captures OpenAI requests, stores them in PostgreSQL, and shows costs, latency, tokens, prompts, responses, errors, and metadata in a developer dashboard.

## Quick SDK Usage

For local development from this repo:

```bash
cd sdk/python
pip install -e .
```

In your app:

```python
import logllama
from openai import OpenAI

logllama.init(api_key="llama-dev-key")
client = logllama.wrap_openai(OpenAI(api_key="your-openai-key"))

client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello"}],
    metadata={"route": "/demo", "user_id": "local-dev"},
)
```

Or configure with `.env`:

```text
LOGLLAMA_API_KEY=llama-dev-key
LOGLLAMA_ENDPOINT=http://localhost:8000
```

Then:

```python
import logllama
from openai import OpenAI

logllama.init()
client = logllama.wrap_openai(OpenAI())
```

The older `track_openai(...)` API still works, but `init(...)` + `wrap_openai(...)` is the preferred developer flow.

## What Is Included

- Python SDK with OpenAI request capture.
- FastAPI ingestion backend.
- PostgreSQL storage through SQLAlchemy.
- React dashboard for request logs, cost, latency, token usage, prompts, responses, metadata, and errors.
- Docker Compose for local PostgreSQL.

## Project Layout

```text
backend/        FastAPI API and database models
sdk/python/     Python SDK package
dashboard/      React dashboard
examples/       Minimal instrumented OpenAI app
scripts/        Local sample event senders
```

## Local Setup

1. Start PostgreSQL:

```bash
PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH /Applications/Docker.app/Contents/Resources/bin/docker compose up -d postgres
```

If `docker` is already on your PATH, this also works:

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

Open the local dashboard URL printed by Vite, usually:

```text
http://127.0.0.1:5173
```

If that port is occupied, Vite may use `5174`.

4. Send a sample captured request without an OpenAI key:

```bash
python3 scripts/send_sample_event.py
python3 scripts/send_second_sample_event.py
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
LOGLLAMA_TIMEOUT_SECONDS=1
LOGLLAMA_CAPTURE_PROMPTS=true
LOGLLAMA_CAPTURE_RESPONSES=true
LOGLLAMA_ENABLED=true
```

## API

- `POST /v1/events` ingests SDK events. Requires `X-LogLlama-Api-Key`.
- `GET /api/requests` lists captured requests.
- `GET /api/requests/{request_id}` fetches one captured request.
- `GET /api/metrics/summary` returns dashboard metrics.
- `GET /health` checks service health.

## Packaging Status

The SDK is structured for PyPI packaging, but it has not been published from this repo yet.

Build locally:

```bash
cd sdk/python
python -m build
```

Publish later, after creating PyPI credentials:

```bash
python -m twine upload dist/*
```

