"""Chat history per session (session folder, so it expires with the session)."""

import json
import threading
from pathlib import Path
from typing import Any

from app.chat.agent import HISTORY_MESSAGES

HISTORY_FILE = "chat.json"
_lock = threading.Lock()


def load(session_dir: Path) -> list[dict[str, Any]]:
    path = session_dir / HISTORY_FILE
    with _lock:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def append(session_dir: Path, *messages: dict[str, Any]) -> list[dict[str, Any]]:
    """Add messages and keep only the last HISTORY_MESSAGES."""
    path = session_dir / HISTORY_FILE
    with _lock:
        history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        history = [*history, *messages][-HISTORY_MESSAGES:]
        path.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
        return history
