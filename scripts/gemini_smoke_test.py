"""One real Gemini call through the wrapper. Run manually, never in CI.

    backend/.venv/bin/python scripts/gemini_smoke_test.py [pro|fast]

Prints the model, the parsed answer and token counts. Never prints the key.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pydantic import BaseModel  # noqa: E402

from app import llm  # noqa: E402


class SmokeAnswer(BaseModel):
    answer: str
    word_count: int


def main() -> int:
    tier = sys.argv[1] if len(sys.argv) > 1 else "fast"
    if tier not in ("pro", "fast"):
        print("usage: gemini_smoke_test.py [pro|fast]")
        return 2
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    records: list[llm.CallRecord] = []
    llm.add_usage_listener(records.append)
    try:
        result = llm.structured_call(
            tier, 0, "Reply with the single word 'ready' and its word count.", SmokeAnswer,
            timeout_s=30,
        )
    except llm.LLMUnavailable as exc:
        print(f"FAILED: {exc}")
        return 1
    rec = records[-1]
    print(f"model={rec.model} answer={result.answer!r} word_count={result.word_count} "
          f"input_tokens={rec.input_tokens} output_tokens={rec.output_tokens} "
          f"latency_ms={rec.latency_ms}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
