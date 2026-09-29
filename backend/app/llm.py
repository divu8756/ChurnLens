"""The only module that talks to Gemini (CLAUDE.md rules 16-20).

It owns model choice, temperature, timeouts, retries, throttling and token
logging. Nodes call structured_call(); they never import the SDK directly.
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger("churnlens.llm")

Tier = Literal["pro", "fast"]

MAX_TRANSIENT_ATTEMPTS = 3  # total attempts for 429 / 5xx / timeouts
MAX_CONTENT_ATTEMPTS = 2  # blocked, empty or invalid output: 1 retry
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0
TRANSIENT_CODES = {429, 500, 502, 503, 504}
TRANSIENT_MARKERS = ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "INTERNAL")

# Indirection so tests can replace sleeping, jitter and the model factory.
_sleep: Callable[[float], None] = time.sleep
_jitter: Callable[[], float] = random.random  # noqa: S311 - backoff jitter, not crypto


class LLMUnavailable(RuntimeError):
    """The LLM could not produce a valid answer; the caller must use its fallback."""


class _ContentFailure(Exception):
    """Blocked, empty or schema-invalid response (retried once)."""


@dataclass(frozen=True)
class CallRecord:
    model: str
    tier: Tier
    schema: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    attempts: int
    outcome: Literal["ok", "failed"]


class StructuredRunnable(Protocol):
    def invoke(self, prompt: Any, **kwargs: Any) -> dict[str, Any]: ...


class ChatModel(Protocol):
    def with_structured_output(
        self, schema: type[BaseModel], *, include_raw: bool = ...
    ) -> StructuredRunnable: ...


# ---------------------------------------------------------------- throttle


class Throttle:
    """Spaces calls at least 60 / rpm seconds apart, shared across threads."""

    def __init__(
        self,
        rpm: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.interval = 60.0 / rpm
        self._clock = clock
        self._sleep = sleep
        self._next_free = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Block until a slot is free. Returns the seconds waited."""
        with self._lock:
            now = self._clock()
            start = max(now, self._next_free)
            self._next_free = start + self.interval
        wait = start - now
        if wait > 0:
            (self._sleep or _sleep)(wait)
        return wait


_throttle: Throttle | None = None
_throttle_lock = threading.Lock()


def get_throttle() -> Throttle:
    global _throttle
    rpm = get_settings().GEMINI_RPM
    with _throttle_lock:
        if _throttle is None or _throttle.interval != 60.0 / rpm:
            _throttle = Throttle(rpm)
        return _throttle


def reset_throttle() -> None:
    global _throttle
    with _throttle_lock:
        _throttle = None


# ---------------------------------------------------------------- models


def model_name(tier: Tier) -> str:
    settings = get_settings()
    if tier == "pro":
        return settings.GEMINI_MODEL
    if tier == "fast":
        return settings.GEMINI_MODEL_FAST
    raise ValueError(f"Unknown tier: {tier!r}")


def _default_factory(model: str, temperature: float, timeout_s: float) -> ChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        api_key=get_settings().GEMINI_API_KEY,
        request_timeout=timeout_s,
        retries=0,  # retries are handled here, with throttling and logging
    )


_model_factory: Callable[[str, float, float], ChatModel] = _default_factory


def set_model_factory(factory: Callable[[str, float, float], ChatModel] | None) -> None:
    """Swap the model factory (tests use FakeLLM). None restores the real one."""
    global _model_factory
    _model_factory = factory or _default_factory


def get_llm(tier: Tier, temperature: float, timeout_s: float = 60) -> ChatModel:
    return _model_factory(model_name(tier), temperature, timeout_s)


# ---------------------------------------------------------------- errors


def _error_chain(exc: BaseException) -> list[BaseException]:
    chain, seen = [], set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


_ZERO_QUOTA = re.compile(r"limit:\s*0\b")


def is_transient(exc: BaseException) -> bool:
    chain = _error_chain(exc)
    # A 429 with "limit: 0" means the model has no quota on this plan; waiting won't help.
    if any(_ZERO_QUOTA.search(f"{err} {getattr(err, 'details', '')}") for err in chain):
        return False
    for err in chain:
        if isinstance(err, TimeoutError) or "Timeout" in type(err).__name__:
            return True
        code = getattr(err, "code", None) or getattr(err, "status_code", None)
        if isinstance(code, int) and code in TRANSIENT_CODES:
            return True
        if type(err).__name__ in {"ModelRateLimitError", "GoogleRateLimitError", "GoogleAPIError"}:
            return True
        if any(marker in str(err) for marker in TRANSIENT_MARKERS):
            return True
    return False


_RETRY_DELAY = re.compile(r"retry[_ ]?delay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I)
_RETRY_IN = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.I)


def retry_delay_hint(exc: BaseException) -> float | None:
    """Seconds the API asked us to wait (RetryInfo.retryDelay), if any."""
    for err in _error_chain(exc):
        text = f"{err} {getattr(err, 'details', '')}"
        for pattern in (_RETRY_DELAY, _RETRY_IN):
            match = pattern.search(text)
            if match:
                return float(match.group(1))
    return None


def backoff_seconds(attempt: int, hint: float | None = None) -> float:
    """Exponential backoff with jitter; never shorter than the API's hint."""
    base = min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** (attempt - 1)))
    delay = base * (0.5 + _jitter() / 2)
    return max(delay, hint or 0.0)


# ---------------------------------------------------------------- calls


def _finish_reason(raw: Any) -> str | None:
    metadata = getattr(raw, "response_metadata", None) or {}
    reason = metadata.get("finish_reason")
    return str(reason) if reason is not None else None


def _usage(raw: Any) -> tuple[int, int]:
    usage = getattr(raw, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0)


def _check_result(result: dict[str, Any], schema: type[BaseModel]) -> BaseModel:
    raw = result.get("raw")
    reason = _finish_reason(raw)
    if reason is not None and reason != "STOP":
        raise _ContentFailure(f"finish_reason={reason}")
    if result.get("parsing_error") is not None:
        raise _ContentFailure(f"invalid output: {type(result['parsing_error']).__name__}")
    parsed = result.get("parsed")
    if parsed is None:
        raise _ContentFailure("empty response")
    if not isinstance(parsed, schema):
        parsed = schema.model_validate(parsed)
    return parsed


_listeners: list[Callable[[CallRecord], None]] = []


def add_usage_listener(listener: Callable[[CallRecord], None]) -> None:
    """Receive a CallRecord after every structured_call (used by telemetry)."""
    _listeners.append(listener)


def remove_usage_listener(listener: Callable[[CallRecord], None]) -> None:
    if listener in _listeners:
        _listeners.remove(listener)


def _emit(record: CallRecord) -> None:
    logger.info(
        "llm_call model=%s tier=%s schema=%s latency_ms=%d input_tokens=%d "
        "output_tokens=%d attempts=%d outcome=%s",
        record.model, record.tier, record.schema, record.latency_ms,
        record.input_tokens, record.output_tokens, record.attempts, record.outcome,
    )
    for listener in list(_listeners):
        try:
            listener(record)
        except Exception:  # a broken listener must never break an LLM call
            logger.exception("usage listener failed")


@dataclass
class _Outcome:
    parsed: BaseModel | None
    error: str
    exc: BaseException | None
    overloaded: bool  # transient retries exhausted; another model may still work


def _call_model(
    model: str, tier: Tier, temperature: float, prompt: Any,
    schema: type[BaseModel], timeout_s: float,
) -> _Outcome:
    runnable = _model_factory(model, temperature, timeout_s).with_structured_output(
        schema, include_raw=True
    )
    throttle = get_throttle()
    started = time.monotonic()
    input_tokens = output_tokens = 0
    transient_attempts = content_attempts = attempts = 0
    outcome = _Outcome(None, "unknown error", None, overloaded=False)

    while True:
        attempts += 1
        throttle.acquire()
        try:
            result = runnable.invoke(prompt)
            in_tok, out_tok = _usage(result.get("raw"))
            input_tokens += in_tok
            output_tokens += out_tok
            outcome.parsed = _check_result(result, schema)
            break
        except _ContentFailure as exc:
            content_attempts += 1
            outcome.error, outcome.exc = str(exc), exc
            if content_attempts >= MAX_CONTENT_ATTEMPTS:
                break
        except Exception as exc:
            outcome.exc = exc
            if not is_transient(exc):
                outcome.error = type(exc).__name__
                break
            transient_attempts += 1
            outcome.error = f"transient {type(exc).__name__}"
            if transient_attempts >= MAX_TRANSIENT_ATTEMPTS:
                outcome.overloaded = True
                break
            _sleep(backoff_seconds(transient_attempts, retry_delay_hint(exc)))

    _emit(CallRecord(
        model, tier, schema.__name__, int((time.monotonic() - started) * 1000),
        input_tokens, output_tokens, attempts, "ok" if outcome.parsed is not None else "failed",
    ))
    return outcome


def structured_call[T: BaseModel](
    tier: Tier,
    temperature: float,
    prompt: Any,
    schema: type[T],
    timeout_s: float = 60,
) -> T:
    """Call Gemini and return a validated `schema` instance.

    Transient errors (429, 5xx, timeouts) are retried up to 3 attempts with
    backoff. Blocked, empty or invalid responses get 1 retry. If the model
    stays overloaded and GEMINI_MODEL_FALLBACK is set, the fallback model is
    tried the same way. Anything else raises LLMUnavailable so the node's
    fallback runs.
    """
    primary = model_name(tier)
    fallback = get_settings().GEMINI_MODEL_FALLBACK
    outcome = _call_model(primary, tier, temperature, prompt, schema, timeout_s)
    if outcome.parsed is None and outcome.overloaded and fallback and fallback != primary:
        logger.warning("llm_fallback from=%s to=%s", primary, fallback)
        outcome = _call_model(fallback, tier, temperature, prompt, schema, timeout_s)
    if outcome.parsed is not None:
        return cast(T, outcome.parsed)
    raise LLMUnavailable(
        f"{schema.__name__} via {tier} model failed: {outcome.error}"
    ) from outcome.exc
