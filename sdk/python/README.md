# LogLlama Python SDK

LLM observability in two lines of Python.

```bash
pip install logllama
```

```python
import logllama
from openai import OpenAI

logllama.init(api_key="YOUR_LOGLLAMA_KEY")
client = logllama.wrap_openai(OpenAI())
```

Every supported OpenAI call made through `client` is captured automatically.

```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a support email."}],
    metadata={"route": "/support/email", "user_id": "user_123"},
)
```

## Environment Variables

You can configure the SDK with a `.env` file instead of passing arguments:

```text
LOGLLAMA_API_KEY=YOUR_LOGLLAMA_KEY
LOGLLAMA_ENDPOINT=http://localhost:8000
```

Then your code becomes:

```python
import logllama
from openai import OpenAI

logllama.init()
client = logllama.wrap_openai(OpenAI())
```

## Captured Data

- provider and operation
- model
- prompt/messages
- response
- input/output/total tokens
- latency
- estimated cost, calculated by the backend
- errors
- metadata

## Privacy Controls

Disable prompt or response capture when needed:

```python
logllama.init(
    api_key="YOUR_LOGLLAMA_KEY",
    capture_prompts=False,
    capture_responses=False,
)
```

Or through environment variables:

```text
LOGLLAMA_CAPTURE_PROMPTS=false
LOGLLAMA_CAPTURE_RESPONSES=false
```

## Local Development

From this repository:

```bash
cd sdk/python
pip install -e .
```

For the local backend, use:

```text
LOGLLAMA_API_KEY=llama-dev-key
LOGLLAMA_ENDPOINT=http://localhost:8000
```

