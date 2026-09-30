"""Structured JSON logs (one object per line) with the session_id of the request or run.

Only messages and metadata are logged: never file contents, prompts or API keys (the
Gemini wrapper logs model, tokens and latency only)."""

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime

session_var: ContextVar[str | None] = ContextVar("churnlens_session", default=None)
SESSION_IN_PATH = re.compile(r"/([0-9a-f]{32})(?:/|$)")
LOGGERS = ("churnlens", "uvicorn", "uvicorn.error", "uvicorn.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        session = getattr(record, "session_id", None) or session_var.get()
        if session:
            entry["session_id"] = session
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    for name in LOGGERS:
        log = logging.getLogger(name)
        log.handlers = [handler]
        log.setLevel(level)
        log.propagate = False


def session_from_path(path: str) -> str | None:
    match = SESSION_IN_PATH.search(path)
    return match.group(1) if match else None
