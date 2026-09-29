"""FakeLLM: a stand-in for Gemini in tests. Never calls the network.

Fixtures are keyed by schema class name. Each key maps to one fixture or a
list of fixtures consumed in order (the last one repeats). A fixture is:
- a Pydantic instance or dict: a successful response (dicts are validated,
  so an invalid dict behaves like malformed model output),
- an Exception instance: raised from invoke(),
- a FakeResponse: full control over finish_reason, parsed value and usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError


@dataclass
class FakeResponse:
    parsed: Any = None
    finish_reason: str = "STOP"
    input_tokens: int = 10
    output_tokens: int = 5
    parsing_error: Exception | None = None


@dataclass
class FakeLLM:
    fixtures: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    # Matches the model factory signature used by app.llm.set_model_factory.
    def __call__(self, model: str, temperature: float, timeout_s: float) -> _FakeChatModel:
        return _FakeChatModel(self, model, temperature, timeout_s)

    def _next(self, schema_name: str) -> Any:
        if schema_name not in self.fixtures:
            raise KeyError(f"FakeLLM has no fixture for schema {schema_name!r}")
        value = self.fixtures[schema_name]
        if isinstance(value, list):
            if not value:
                raise KeyError(f"FakeLLM fixtures for {schema_name!r} are exhausted")
            return value.pop(0) if len(value) > 1 else value[0]
        return value


@dataclass
class _FakeChatModel:
    owner: FakeLLM
    model: str
    temperature: float
    timeout_s: float

    def with_structured_output(
        self, schema: type[BaseModel], *, include_raw: bool = False
    ) -> _FakeRunnable:
        return _FakeRunnable(self, schema, include_raw)


@dataclass
class _FakeRunnable:
    chat: _FakeChatModel
    schema: type[BaseModel]
    include_raw: bool

    def invoke(self, prompt: Any, **kwargs: Any) -> dict[str, Any]:
        self.chat.owner.calls.append({
            "model": self.chat.model,
            "temperature": self.chat.temperature,
            "schema": self.schema.__name__,
            "prompt": prompt,
        })
        fixture = self.chat.owner._next(self.schema.__name__)
        if isinstance(fixture, Exception):
            raise fixture
        response = fixture if isinstance(fixture, FakeResponse) else FakeResponse(parsed=fixture)

        parsed, error = response.parsed, response.parsing_error
        if isinstance(parsed, dict):
            try:
                parsed = self.schema.model_validate(parsed)
            except ValidationError as exc:
                parsed, error = None, exc
        elif isinstance(parsed, str):
            parsed, error = None, ValueError("output is not valid JSON")

        raw = AIMessage(
            content="",
            response_metadata={"finish_reason": response.finish_reason},
            usage_metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.input_tokens + response.output_tokens,
            },
        )
        return {"raw": raw, "parsed": parsed, "parsing_error": error}
