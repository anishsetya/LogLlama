import pytest
from pydantic import ValidationError

from app.schemas import EventIn


def test_event_accepts_provider_observability_fields():
    event = EventIn(
        provider="gemini",
        operation="models.generate_content",
        model="gemini-test",
        provider_request_id="gemini-request-123",
        retry_count=2,
        model_parameters={"temperature": 0.2, "max_output_tokens": 16},
        status="success",
    )

    assert event.provider_request_id == "gemini-request-123"
    assert event.retry_count == 2
    assert event.model_parameters["temperature"] == 0.2


def test_event_rejects_negative_retry_count():
    with pytest.raises(ValidationError):
        EventIn(
            provider="gemini",
            operation="models.generate_content",
            retry_count=-1,
            status="error",
        )
