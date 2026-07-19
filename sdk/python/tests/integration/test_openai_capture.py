from __future__ import annotations

import os
import json
import time
import uuid
from urllib import parse, request

import pytest

import logllama


pytestmark = pytest.mark.integration


MODEL = os.getenv("LOGLLAMA_OPENAI_TEST_MODEL", "gpt-5-nano")
RUN_FLAG = "RUN_LOGLLAMA_OPENAI_INTEGRATION"


REAL_TEST_METADATA = {
    "route": "/tests/openai-capture",
    "user_id": "test_user_001",
    "tenant_id": "test_tenant_enterprise",
    "session_id": "test_session_001",
    "conversation_id": "test_conversation_001",
    "request_id": "test_request_001",
    "trace_id": "00000000000000000000000000000001",
    "span_id": "0000000000000001",
    "prompt_template": "sdk_integration_smoke",
    "prompt_version": "v1",
    "tags": ["integration", "openai", "metadata"],
    "custom_metadata": {
        "feature": "sdk_metadata_capture",
        "ci_ready": True,
        "api_key": "should_be_redacted",
    },
}


def _require_real_openai() -> None:
    if os.getenv(RUN_FLAG) != "1":
        pytest.skip(f"Set {RUN_FLAG}=1 to run OpenAI integration tests.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.fail("OPENAI_API_KEY is required when RUN_LOGLLAMA_OPENAI_INTEGRATION=1.")
    if not os.getenv("LOGLLAMA_API_KEY"):
        pytest.fail("LOGLLAMA_API_KEY is required when RUN_LOGLLAMA_OPENAI_INTEGRATION=1.")


def _require_backend() -> str:
    endpoint = os.getenv("LOGLLAMA_ENDPOINT", "http://localhost:8000").rstrip("/")
    try:
        with request.urlopen(f"{endpoint}/health", timeout=3) as response:
            if response.status != 200:
                pytest.fail(f"LogLlama backend health check returned HTTP {response.status}.")
    except Exception as exc:
        pytest.fail(f"LogLlama backend is not reachable at {endpoint}: {exc}")
    return endpoint


def _wait_for_backend_request(endpoint: str, request_id: str) -> dict:
    deadline = time.monotonic() + 10
    query = parse.urlencode({"limit": 5, "request_id": request_id})
    while time.monotonic() < deadline:
        with request.urlopen(f"{endpoint}/api/requests?{query}", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("requests"):
            return payload["requests"][0]
        time.sleep(0.25)
    pytest.fail(f"LogLlama backend did not return request_id={request_id}.")


def test_wrong_openai_api_key_posts_error_event_to_backend() -> None:
    openai = pytest.importorskip("openai")
    if os.getenv(RUN_FLAG) != "1":
        pytest.skip(f"Set {RUN_FLAG}=1 to run OpenAI integration tests.")
    if not os.getenv("LOGLLAMA_API_KEY"):
        pytest.fail("LOGLLAMA_API_KEY is required when RUN_LOGLLAMA_OPENAI_INTEGRATION=1.")

    endpoint = _require_backend()
    request_id = f"wrong-key-{uuid.uuid4().hex}"
    client = logllama.wrap_openai(
        openai.OpenAI(api_key="sk-logllama-intentionally-wrong-key"),
        api_key=os.environ["LOGLLAMA_API_KEY"],
        endpoint=endpoint,
        service_name="sdk-integration-tests",
        environment="test",
        version="0.1.0",
        git_sha="integration-test",
        capture_prompts=False,
        capture_responses=False,
        capture_errors=True,
        sample_rate=1,
    )

    with pytest.raises(Exception):
        client.responses.create(
            model=MODEL,
            input="This request should fail authentication.",
            metadata={"logllama_test": "wrong_key"},
            logllama_metadata={**REAL_TEST_METADATA, "request_id": request_id},
            max_output_tokens=1,
        )

    event = _wait_for_backend_request(endpoint, request_id)
    assert event["status"] == "error"
    assert event["provider"] == "openai"
    assert event["operation"] == "responses.create"
    assert event["service_name"] == "sdk-integration-tests"
    assert event["environment"] == "test"
    assert event["route"] == REAL_TEST_METADATA["route"]
    assert event["tenant_id"] == REAL_TEST_METADATA["tenant_id"]
    assert event["prompt"]["_logllama_capture"] == "disabled"
    assert event["response"] is None
    assert event["error_type"]


def test_valid_openai_api_key_captures_metadata_with_one_billable_call() -> None:
    openai = pytest.importorskip("openai")
    _require_real_openai()

    endpoint = _require_backend()
    request_id = f"valid-key-{uuid.uuid4().hex}"
    client = logllama.wrap_openai(
        openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"]),
        api_key=os.environ["LOGLLAMA_API_KEY"],
        endpoint=endpoint,
        service_name="sdk-integration-tests",
        environment=os.getenv("LOGLLAMA_TEST_ENVIRONMENT", "test"),
        version="0.1.0",
        git_sha="integration-test",
        redact_keys=["api_key"],
        max_prompt_size=4000,
        max_response_size=4000,
        sample_rate=1,
    )

    # This is intentionally the only billable OpenAI request in the test suite.
    response = client.responses.create(
        model=MODEL,
        instructions="Respond with exactly this sentence and no extra text: LogLlama metadata capture works.",
        input="Return the exact requested sentence.",
        metadata={"logllama_test": "valid_key"},
        logllama_metadata={**REAL_TEST_METADATA, "request_id": request_id},
        reasoning={"effort": "minimal"},
        text={"verbosity": "low"},
        max_output_tokens=120,
    )

    event = _wait_for_backend_request(endpoint, request_id)
    assert response is not None
    assert getattr(response, "status", None) != "incomplete"
    assert event["status"] == "success"
    assert event["model"]
    assert event["service_name"] == "sdk-integration-tests"
    assert event["route"] == REAL_TEST_METADATA["route"]
    assert event["user_id"] == REAL_TEST_METADATA["user_id"]
    assert event["tenant_id"] == REAL_TEST_METADATA["tenant_id"]
    assert event["session_id"] == REAL_TEST_METADATA["session_id"]
    assert event["conversation_id"] == REAL_TEST_METADATA["conversation_id"]
    assert event["request_id"] == request_id
    assert event["trace_id"] == REAL_TEST_METADATA["trace_id"]
    assert event["span_id"] == REAL_TEST_METADATA["span_id"]
    assert event["prompt_template"] == REAL_TEST_METADATA["prompt_template"]
    assert event["prompt_version"] == REAL_TEST_METADATA["prompt_version"]
    assert set(REAL_TEST_METADATA["tags"]).issubset(set(event["tags"]))
    assert event["custom_metadata"]["feature"] == "sdk_metadata_capture"
    assert event["custom_metadata"]["api_key"] == "[REDACTED]"
    assert event["privacy"]["sample_rate"] == 1
    assert event["total_tokens"] >= 0
