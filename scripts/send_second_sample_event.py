import json
from datetime import datetime, timezone
from urllib import request


API_KEY = "llama-dev-key"
ENDPOINT = "http://localhost:8000/v1/events"


event = {
    "external_id": f"sample_chat_completion_{datetime.now(timezone.utc).timestamp()}",
    "provider": "openai",
    "operation": "chat.completions.create",
    "model": "gpt-4o",
    "status": "success",
    "prompt": [
        {"role": "system", "content": "You are a concise debugging assistant."},
        {"role": "user", "content": "Why did my LLM request get slower after deployment?"},
    ],
    "response": {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Check model changes, prompt length, retry behavior, and upstream latency around the deploy.",
                }
            }
        ]
    },
    "usage": {"input_tokens": 42, "output_tokens": 21, "total_tokens": 63},
    "latency_ms": 1486,
    "service_name": "debug-api",
    "environment": "local",
    "version": "0.1.1",
    "git_sha": "local-latency",
    "route": "/debug/latency",
    "user_id": "tester-002",
    "tenant_id": "tenant_demo",
    "session_id": "sess_debug",
    "conversation_id": "conv_debug",
    "request_id": f"req_debug_{datetime.now(timezone.utc).timestamp()}",
    "trace_id": "trace_debug",
    "span_id": "span_debug_001",
    "prompt_template": "latency_diagnosis",
    "prompt_version": "v2",
    "tags": ["debug", "latency"],
    "custom_metadata": {"release_channel": "local"},
    "privacy": {"capture_prompts": True, "capture_responses": True, "sample_rate": 1},
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
