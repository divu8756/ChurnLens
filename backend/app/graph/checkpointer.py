"""Checkpointer factory: SQLite at DATA_DIR/checkpoints.db, Postgres if DATABASE_URL is set."""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.config import Settings, get_settings


def create_checkpointer(settings: Settings | None = None) -> BaseCheckpointSaver:
    settings = settings or get_settings()
    if settings.DATABASE_URL:
        return _postgres(settings.DATABASE_URL)
    return _sqlite(Path(settings.DATA_DIR) / "checkpoints.db")


def _sqlite(path: Path) -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    # The API runs the graph in background threads, so allow cross-thread use;
    # SqliteSaver serialises access with its own lock.
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def _postgres(url: str) -> BaseCheckpointSaver:
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg import Connection
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "DATABASE_URL is set but the Postgres checkpointer is not installed. "
            "Install langgraph-checkpoint-postgres and psycopg[binary]."
        ) from exc
    conn = Connection.connect(url, autocommit=True, prepare_threshold=0, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()
    return saver
