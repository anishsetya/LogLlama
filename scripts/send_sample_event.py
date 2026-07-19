import json
from datetime import datetime, timezone
from urllib import request


API_KEY = "llama-dev-key"
ENDPOINT = "http://localhost:8000/v1/events"


event = {
    "external_id": "sample_chat_completion_001",
    "provider": "openai",
    "operation": "chat.completions.create",
    "model": "gpt-4o-mini",
    "status": "success",
    "prompt": [{"role": "user", "content": "Explain observability in one sentence."}],
    "response": {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Observability helps developers understand what a system is doing and why.",
                }
            }
        ]
    },
    "usage": {"input_tokens": 18, "output_tokens": 14, "total_tokens": 32},
    "latency_ms": 842,
    "service_name": "demo-api",
    "environment": "local",
    "version": "0.1.0",
    "git_sha": "local-dev",
    "route": "/demo",
    "user_id": "local-dev",
    "tenant_id": "tenant_demo",
    "session_id": "sess_demo",
    "conversation_id": "conv_demo",
    "request_id": "req_demo_001",
    "trace_id": "trace_demo",
    "span_id": "span_demo_001",
    "prompt_template": "observability_explainer",
    "prompt_version": "v1",
    "tags": ["demo", "docs"],
    "custom_metadata": {"feature": "quickstart"},
    "privacy": {"capture_prompts": True, "capture_responses": True, "sample_rate": 1},
    "metadata": {"legacy_route": "/demo"},
    "captured_at": datetime.now(timezone.utc).isoformat(),
}


body = json.dumps(event).encode("utf-8")
req = request.Request(
    ENDPOINT,
    data=body,
    method="POST",
    headers={"Content-Type": "application/json", "X-LogLlama-Api-Key": API_KEY},
)

with request.urlopen(req, timeout=5) as response:
    print(response.status, response.read().decode("utf-8"))
