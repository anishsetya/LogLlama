from __future__ import annotations

import json
import os
import time
import uuid
from urllib import parse, request

import pytest

import logllama
from logllama.config import load_dotenv


pytestmark = pytest.mark.integration


DEFAULT_MODEL = "gemini-3.5-flash-lite"
RUN_FLAG = "RUN_LOGLLAMA_GEMINI_INTEGRATION"
SUCCESS_RUNS_ENV = "LOGLLAMA_GEMINI_SUCCESS_RUNS"


def _require_real_gemini() -> None:
    load_dotenv()
    if os.getenv(RUN_FLAG) != "1":
        pytest.skip(f"Set {RUN_FLAG}=1 to run Gemini integration tests.")
    if not os.getenv("GEMINI_API_KEY"):
        pytest.fail("GEMINI_API_KEY is required when RUN_LOGLLAMA_GEMINI_INTEGRATION=1.")
    if not os.getenv("LOGLLAMA_API_KEY"):
        pytest.fail("LOGLLAMA_API_KEY is required when RUN_LOGLLAMA_GEMINI_INTEGRATION=1.")


def _success_runs() -> int:
    try:
        return min(10, max(1, int(os.getenv(SUCCESS_RUNS_ENV, "1"))))
    except ValueError:
        pytest.fail(f"{SUCCESS_RUNS_ENV} must be an integer between 1 and 10.")


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


def test_wrong_gemini_key_posts_error_event_to_backend() -> None:
    genai = pytest.importorskip("google.genai")
    types = pytest.importorskip("google.genai.types")
    _require_real_gemini()

    endpoint = _require_backend()
    model = os.getenv("LOGLLAMA_GEMINI_TEST_MODEL", DEFAULT_MODEL)
    request_id = f"gemini-wrong-{uuid.uuid4().hex}"
    client = logllama.wrap_gemini(
        genai.Client(api_key="logllama-intentionally-wrong-gemini-key"),
        api_key=os.environ["LOGLLAMA_API_KEY"],
        endpoint=endpoint,
        service_name="sdk-integration-tests",
        environment="test",
        capture_prompts=False,
        capture_responses=False,
        capture_errors=True,
        sample_rate=1,
        capture_otel=False,
    )

    with pytest.raises(Exception):
        client.models.generate_content(
            model=model,
            contents="This request should fail authentication.",
            config=types.GenerateContentConfig(max_output_tokens=1),
            logllama_metadata={
                "route": "/tests/gemini-capture",
                "request_id": request_id,
                "tags": ["integration", "gemini", "wrong-key"],
            },
        )

    event = _wait_for_backend_request(endpoint, request_id)
    assert event["status"] == "error"
    assert event["provider"] == "gemini"
    assert event["operation"] == "models.generate_content"
    assert event["prompt"]["_logllama_capture"] == "disabled"
    assert event["response"] is None
    assert event["error_type"]
    assert event["retry_count"] == 0
    assert event["model_parameters"]["max_output_tokens"] == 1


def test_valid_gemini_key_captures_full_instrumentation_for_bounded_calls() -> None:
    genai = pytest.importorskip("google.genai")
    types = pytest.importorskip("google.genai.types")
    _require_real_gemini()

    endpoint = _require_backend()
    model = os.getenv("LOGLLAMA_GEMINI_TEST_MODEL", DEFAULT_MODEL)
    client = logllama.wrap_gemini(
        genai.Client(api_key=os.environ["GEMINI_API_KEY"]),
        api_key=os.environ["LOGLLAMA_API_KEY"],
        endpoint=endpoint,
        service_name="sdk-integration-tests",
        environment="test",
        version="0.1.0",
        git_sha="integration-test",
        redact_keys=["api_key"],
        max_prompt_size=4000,
        max_response_size=4000,
        sample_rate=1,
        capture_otel=False,
    )

    for run_index in range(_success_runs()):
        request_id = f"gemini-valid-{run_index}-{uuid.uuid4().hex}"
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: ok",
            config=types.GenerateContentConfig(
                max_output_tokens=16,
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
            logllama_metadata={
                "route": "/tests/gemini-capture",
                "request_id": request_id,
                "tenant_id": "test_tenant_enterprise",
                "tags": ["integration", "gemini", "instrumentation"],
                "custom_metadata": {
                    "feature": "gemini_full_capture",
                    "api_key": "must-be-redacted",
                },
            },
        )

        event = _wait_for_backend_request(endpoint, request_id)
        assert response.text.strip().lower() == "ok"
        assert event["status"] == "success"
        assert event["provider"] == "gemini"
        assert event["operation"] == "models.generate_content"
        assert event["provider_request_id"] == response.response_id
        assert event["retry_count"] >= 0
        assert event["model_parameters"]["max_output_tokens"] == 16
        assert event["model_parameters"]["thinking_config"]["thinking_level"] == "MINIMAL"
        assert event["request_id"] == request_id
        assert event["route"] == "/tests/gemini-capture"
        assert event["tenant_id"] == "test_tenant_enterprise"
        assert event["custom_metadata"]["feature"] == "gemini_full_capture"
        assert event["custom_metadata"]["api_key"] == "[REDACTED]"
        assert event["total_tokens"] > 0
