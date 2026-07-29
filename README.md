# LogLlama

LLM observability in two lines of Python.

LogLlama captures OpenAI, Anthropic, and Gemini requests, provides client-side provider switching and approved comparison tests, and shows costs, latency, tokens, prompts, responses, errors, and metadata in a developer dashboard.

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

with logllama.context(
    route="/demo",
    user_id="local-dev",
    tenant_id="tenant_demo",
    conversation_id="conv_demo",
    prompt_template="hello_world",
    prompt_version="v1",
):
    client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}],
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

For provider-neutral calls:

```python
llm = logllama.LLM(
    openai=openai_client,
    anthropic=anthropic_client,
    gemini=gemini_client,
    models={
        "openai": "gpt-model",
        "anthropic": "claude-model",
        "gemini": "gemini-model",
    },
)

response = llm.generate("Explain this error.", provider="anthropic")
```

## What Is Included

- Python SDK with OpenAI, Anthropic, and Gemini request capture.
- Provider-neutral `LLM.generate(..., provider=...)` routing.
- Admin-approved, concurrent cross-provider comparison tests.
- Managed provider credentials with startup/background SDK caching.
- FastAPI ingestion backend.
- PostgreSQL storage through SQLAlchemy.
- React dashboard for request logs, cost, latency, token usage, prompts, responses, metadata, and errors.
- First-class enterprise correlation fields for service, environment, route, tenant, user, request, trace, conversation, prompt template, and prompt version.
- SDK privacy controls for prompt/response capture, key redaction, payload size limits, metadata allowlists/denylists, and sampling.
- Optional FastAPI request context helper and OpenTelemetry trace/span capture.
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

AWS Secrets Manager is an optional backend dependency:

```bash
pip install -r requirements-aws.txt
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
LOGLLAMA_DEFAULT_RUNTIME_KEY=llama-runtime-key
LOGLLAMA_DEFAULT_PROJECT_NAME=Development
LOGLLAMA_ADMIN_API_KEY=llama-admin-key
LOGLLAMA_SECRET_BACKEND=memory
```

SDK:

```text
LOGLLAMA_API_KEY=llama-dev-key
LOGLLAMA_RUNTIME_KEY=llama-runtime-key
LOGLLAMA_ENDPOINT=http://localhost:8000
LOGLLAMA_TIMEOUT_SECONDS=1
LOGLLAMA_CAPTURE_PROMPTS=true
LOGLLAMA_CAPTURE_RESPONSES=true
LOGLLAMA_SERVICE_NAME=demo-api
LOGLLAMA_ENVIRONMENT=local
LOGLLAMA_VERSION=0.1.0
LOGLLAMA_GIT_SHA=local-dev
LOGLLAMA_TAGS=demo,local
LOGLLAMA_REDACT_KEYS=password,authorization,api_key,email
LOGLLAMA_MAX_PROMPT_SIZE=20000
LOGLLAMA_MAX_RESPONSE_SIZE=50000
LOGLLAMA_METADATA_ALLOWLIST=service_name,environment,route,user_id,tenant_id,trace_id
LOGLLAMA_METADATA_DENYLIST=ssn,credit_card
LOGLLAMA_SAMPLE_RATE=1
LOGLLAMA_CAPTURE_ERRORS=true
LOGLLAMA_CAPTURE_OTEL=true
LOGLLAMA_ENABLED=true
```

`LOGLLAMA_SECRET_BACKEND=memory` is development-only and loses managed keys when the backend restarts. Production choices are `aws`, `vault`, and `openbao`; the backend stores only secret references and fingerprints in PostgreSQL.

Vault and OpenBao share the same KV v2 configuration:

```text
LOGLLAMA_SECRET_BACKEND=openbao
LOGLLAMA_SECRET_STORE_ADDR=http://127.0.0.1:8200
LOGLLAMA_SECRET_STORE_TOKEN=replace-me
LOGLLAMA_SECRET_STORE_MOUNT=secret
LOGLLAMA_SECRET_STORE_TIMEOUT_SECONDS=2
```

The token should be injected into the backend process by the deployment environment, not stored in the admin portal. Managed provider credentials are fetched with the separate runtime key during SDK startup and refreshed in the background, never during a normal model call. This keeps secret-manager network latency out of customer model requests.
Non-loopback Vault and OpenBao endpoints must use HTTPS.

Benchmark local secret-store control-plane latency with:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python benchmarks/secret_store_latency.py \
  --vault-addr http://127.0.0.1:8200 --vault-token test-token \
  --openbao-addr http://127.0.0.1:8300 --openbao-token test-token
```

Measure the full SDK preload endpoint separately:

```bash
cd backend
PYTHONPATH=. .venv/bin/python benchmarks/runtime_preload_latency.py \
  --endpoint http://127.0.0.1:8000 \
  --runtime-key llama-runtime-key
```

## API

- `POST /v1/events` ingests SDK events. Requires `X-LogLlama-Api-Key`.
- `POST /v1/test-plans` requests an admin-approved provider comparison.
- `GET /v1/test-plans/{id}` checks the immutable comparison plan.
- `GET /v1/runtime/provider-credentials` preloads managed credentials. Requires `X-LogLlama-Runtime-Key`.
- `/api/admin/provider-credentials` manages write-only provider secrets.
- `/api/admin/test-plans` lists, approves, and rejects comparison plans.
- `GET /api/requests` lists captured requests.
- `GET /api/requests?tenant_id=...&route=...&trace_id=...` filters captured requests by enterprise correlation fields.
- `GET /api/requests/{request_id}` fetches one captured request.
- `GET /api/metadata/facets` returns filter values for the dashboard.
- `GET /api/traces/{trace_id}` returns all requests for one distributed trace.
- `GET /api/conversations/{conversation_id}` returns all requests in one AI conversation.
- `GET /api/metrics/summary` returns dashboard metrics.
- `GET /health` checks service health.

## SDK Integration Tests

The SDK includes opt-in OpenAI integration tests under `sdk/python/tests/integration`.

```bash
cd sdk/python
python -m pip install -e ".[test]"
python -m pytest
```

Run the real OpenAI scenarios only when credentials are available:

```bash
RUN_LOGLLAMA_OPENAI_INTEGRATION=1 \
OPENAI_API_KEY=sk-... \
python -m pytest tests/integration -m integration
```

The valid-key test makes exactly one billable OpenAI request. The wrong-key test uses an intentionally invalid OpenAI key to validate SDK error capture.

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
