import logging

import pytest
from google.genai.errors import ClientError, ServerError
from langchain_google_genai.chat_models import GoogleRateLimitError
from pydantic import BaseModel

from app import llm
from app.llm_fake import FakeLLM, FakeResponse


class Verdict(BaseModel):
    label: str
    score: float


GOOD = {"label": "churn", "score": 0.7}


def rate_limit_error(retry_delay: str | None = None) -> Exception:
    details = []
    if retry_delay:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": retry_delay})
    cause = ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                        "message": "quota exceeded", "details": details}})
    try:
        raise GoogleRateLimitError("Error calling model (RESOURCE_EXHAUSTED)") from cause
    except GoogleRateLimitError as exc:
        return exc


@pytest.fixture
def sleeps(monkeypatch):
    recorded: list[float] = []
    monkeypatch.setattr(llm, "_sleep", recorded.append)
    monkeypatch.setattr(llm, "_jitter", lambda: 1.0)  # deterministic backoff
    llm.reset_throttle()
    yield recorded
    llm.reset_throttle()


@pytest.fixture
def fake(sleeps):
    fake_llm = FakeLLM()
    llm.set_model_factory(fake_llm)
    yield fake_llm
    llm.set_model_factory(None)


# ---------------------------------------------------------------- throttle


def test_throttle_spaces_calls_by_interval():
    now = [100.0]
    waits: list[float] = []
    throttle = llm.Throttle(rpm=60, clock=lambda: now[0], sleep=waits.append)
    for _ in range(3):
        throttle.acquire()
    assert waits == [1.0, 2.0]  # first call free, then 1 s apart


def test_throttle_does_not_wait_after_idle_time():
    now = [0.0]
    waits: list[float] = []
    throttle = llm.Throttle(rpm=30, clock=lambda: now[0], sleep=waits.append)
    throttle.acquire()
    now[0] = 10.0  # longer than the 2 s interval
    assert throttle.acquire() == 0
    assert waits == []


def test_throttle_is_shared_and_follows_rpm(monkeypatch):
    llm.reset_throttle()
    first = llm.get_throttle()
    assert llm.get_throttle() is first
    assert first.interval == pytest.approx(60 / 600)
    monkeypatch.setenv("GEMINI_RPM", "10")
    llm.get_settings.cache_clear()
    assert llm.get_throttle().interval == pytest.approx(6.0)
    llm.reset_throttle()


# ---------------------------------------------------------------- tiers


def test_tier_maps_to_env_model(fake):
    fake.fixtures = {"Verdict": GOOD}
    llm.structured_call("pro", 0, "p", Verdict)
    llm.structured_call("fast", 0.3, "p", Verdict)
    assert [(c["model"], c["temperature"]) for c in fake.calls] == [
        ("test-pro-model", 0), ("test-fast-model", 0.3)]


def test_unknown_tier_is_rejected():
    with pytest.raises(ValueError, match="Unknown tier"):
        llm.model_name("huge")


# ---------------------------------------------------------------- retries


def test_success_returns_schema_instance(fake):
    fake.fixtures = {"Verdict": GOOD}
    result = llm.structured_call("fast", 0, "p", Verdict)
    assert result == Verdict(**GOOD)


def test_429_then_success_retries_and_succeeds(fake, sleeps):
    fake.fixtures = {"Verdict": [rate_limit_error(), GOOD]}
    assert llm.structured_call("fast", 0, "p", Verdict).label == "churn"
    assert len(fake.calls) == 2
    backoffs = [s for s in sleeps if s >= 1]
    assert backoffs == [llm.BACKOFF_BASE_S]  # 2 s * (0.5 + 1.0 / 2)


def test_retry_honours_api_retry_delay(fake, sleeps):
    fake.fixtures = {"Verdict": [rate_limit_error("17s"), GOOD]}
    llm.structured_call("fast", 0, "p", Verdict)
    assert 17.0 in sleeps


def test_server_errors_give_up_after_three_attempts(fake):
    fake.fixtures = {"Verdict": [ServerError(503, {"error": {"code": 503,
                                                             "status": "UNAVAILABLE"}})]}
    with pytest.raises(llm.LLMUnavailable, match="transient"):
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == llm.MAX_TRANSIENT_ATTEMPTS


def test_timeout_is_retried(fake):
    fake.fixtures = {"Verdict": [TimeoutError("read timed out"), GOOD]}
    assert llm.structured_call("pro", 0, "p", Verdict).score == 0.7
    assert len(fake.calls) == 2


def test_non_transient_error_fails_immediately(fake):
    fake.fixtures = {"Verdict": [ClientError(401, {"error": {"code": 401,
                                                             "status": "UNAUTHENTICATED"}})]}
    with pytest.raises(llm.LLMUnavailable) as info:
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == 1
    assert isinstance(info.value.__cause__, ClientError)


def test_blocked_response_raises_after_one_retry(fake):
    fake.fixtures = {"Verdict": [FakeResponse(parsed=None, finish_reason="SAFETY")]}
    with pytest.raises(llm.LLMUnavailable, match="SAFETY"):
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == 2


def test_empty_response_is_a_failure(fake):
    fake.fixtures = {"Verdict": [FakeResponse(parsed=None)]}
    with pytest.raises(llm.LLMUnavailable, match="empty"):
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == 2


def test_invalid_json_is_retried(fake):
    fake.fixtures = {"Verdict": ["{not json", GOOD]}
    assert llm.structured_call("fast", 0, "p", Verdict) == Verdict(**GOOD)
    assert len(fake.calls) == 2


def test_schema_invalid_output_is_retried_then_fails(fake):
    fake.fixtures = {"Verdict": [{"label": "churn"}]}  # missing score
    with pytest.raises(llm.LLMUnavailable, match="invalid output"):
        llm.structured_call("fast", 0, "p", Verdict)
    assert len(fake.calls) == 2


# ---------------------------------------------------------------- logging


def test_logs_tokens_but_not_prompt(fake, caplog):
    fake.fixtures = {"Verdict": FakeResponse(parsed=GOOD, input_tokens=123, output_tokens=45)}
    records: list[llm.CallRecord] = []
    llm.add_usage_listener(records.append)
    try:
        with caplog.at_level(logging.INFO, logger="churnlens.llm"):
            llm.structured_call("pro", 0, "SECRET PROMPT TEXT", Verdict)
    finally:
        llm.remove_usage_listener(records.append)
    assert "input_tokens=123" in caplog.text and "output_tokens=45" in caplog.text
    assert "SECRET PROMPT TEXT" not in caplog.text
    assert records[0].model == "test-pro-model" and records[0].outcome == "ok"


def test_failed_call_is_logged_with_summed_tokens(fake, caplog):
    fake.fixtures = {"Verdict": [FakeResponse(parsed=None, finish_reason="SAFETY",
                                              input_tokens=10, output_tokens=0)]}
    with caplog.at_level(logging.INFO, logger="churnlens.llm"), \
            pytest.raises(llm.LLMUnavailable):
        llm.structured_call("pro", 0, "p", Verdict)
    assert "outcome=failed" in caplog.text and "input_tokens=20" in caplog.text


# ---------------------------------------------------------------- helpers


def test_backoff_grows_and_is_capped(monkeypatch):
    monkeypatch.setattr(llm, "_jitter", lambda: 1.0)
    assert [llm.backoff_seconds(n) for n in (1, 2, 3)] == [2.0, 4.0, 8.0]
    assert llm.backoff_seconds(20) == llm.BACKOFF_CAP_S
    assert llm.backoff_seconds(1, hint=30) == 30


def test_is_transient_classification():
    assert llm.is_transient(rate_limit_error())
    assert llm.is_transient(TimeoutError())
    assert not llm.is_transient(ValueError("bad input"))


def test_zero_quota_429_is_not_retried(fake):
    cause = ClientError(429, {"error": {
        "code": 429, "status": "RESOURCE_EXHAUSTED",
        "message": "Quota exceeded for metric: free_tier_requests, limit: 0, model: x-pro",
    }})
    try:
        raise GoogleRateLimitError("RESOURCE_EXHAUSTED") from cause
    except GoogleRateLimitError as exc:
        fake.fixtures = {"Verdict": [exc]}
    with pytest.raises(llm.LLMUnavailable):
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == 1


# ---------------------------------------------------------------- fallback model


def overloaded() -> Exception:
    return ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE"}})


def test_overloaded_model_falls_back(fake, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FALLBACK", "test-backup-model")
    llm.get_settings.cache_clear()
    fake.fixtures = {"Verdict": [overloaded(), overloaded(), overloaded(), GOOD]}
    assert llm.structured_call("pro", 0, "p", Verdict) == Verdict(**GOOD)
    assert [c["model"] for c in fake.calls] == ["test-pro-model"] * 3 + ["test-backup-model"]


def test_no_fallback_for_content_failures(fake, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FALLBACK", "test-backup-model")
    llm.get_settings.cache_clear()
    fake.fixtures = {"Verdict": [FakeResponse(parsed=None, finish_reason="SAFETY")]}
    with pytest.raises(llm.LLMUnavailable):
        llm.structured_call("pro", 0, "p", Verdict)
    assert {c["model"] for c in fake.calls} == {"test-pro-model"}


def test_fallback_failure_still_raises(fake, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FALLBACK", "test-backup-model")
    llm.get_settings.cache_clear()
    fake.fixtures = {"Verdict": [overloaded()]}
    with pytest.raises(llm.LLMUnavailable, match="transient"):
        llm.structured_call("pro", 0, "p", Verdict)
    assert len(fake.calls) == 2 * llm.MAX_TRANSIENT_ATTEMPTS


def test_wrong_type_output_is_a_content_failure(fake):
    fake.fixtures = {"Verdict": [FakeResponse(parsed=123), GOOD]}
    assert llm.structured_call("fast", 0, "p", Verdict) == Verdict(**GOOD)
    assert len(fake.calls) == 2


def test_max_attempts_can_be_lowered(fake):
    fake.fixtures = {"Verdict": [overloaded()]}
    with pytest.raises(llm.LLMUnavailable):
        llm.structured_call("pro", 0, "p", Verdict, max_attempts=1)
    assert len(fake.calls) == 1
