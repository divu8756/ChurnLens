"""Per-session file storage under DATA_DIR/{session_id}, and expiry cleanup."""

import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import get_settings

SESSION_TTL_S = 2 * 60 * 60
RAW_FILE = "raw.parquet"
META_FILE = "meta.json"
_ID = re.compile(r"^[0-9a-f]{32}$")


class SessionNotFound(LookupError):
    """Unknown or expired session (the API answers 410)."""


def new_session_id() -> str:
    return uuid.uuid4().hex


def session_dir(session_id: str) -> Path:
    # Validate the id so a crafted value can never escape DATA_DIR.
    if not _ID.match(session_id):
        raise SessionNotFound(session_id)
    return Path(get_settings().DATA_DIR) / "sessions" / session_id


def create_session() -> tuple[str, Path]:
    session_id = new_session_id()
    path = session_dir(session_id)
    path.mkdir(parents=True, exist_ok=False)
    return session_id, path


def require_session(session_id: str) -> Path:
    path = session_dir(session_id)
    if not (path / META_FILE).exists():
        raise SessionNotFound(session_id)
    return path


def write_meta(path: Path, meta: dict[str, Any]) -> None:
    (path / META_FILE).write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")


def read_meta(session_id: str) -> dict[str, Any]:
    return json.loads((require_session(session_id) / META_FILE).read_text(encoding="utf-8"))


def save_raw(path: Path, frame: pd.DataFrame) -> Path:
    target = path / RAW_FILE
    frame.to_parquet(target, index=False)
    return target


def cleanup_expired(max_age_s: float = SESSION_TTL_S, now: float | None = None) -> list[str]:
    """Delete session folders older than max_age_s. Returns the deleted ids."""
    root = Path(get_settings().DATA_DIR) / "sessions"
    if not root.exists():
        return []
    now = time.time() if now is None else now
    deleted = []
    for child in root.iterdir():
        if not child.is_dir() or not _ID.match(child.name):
            continue
        if now - child.stat().st_mtime > max_age_s:
            shutil.rmtree(child, ignore_errors=True)
            deleted.append(child.name)
    return deleted
