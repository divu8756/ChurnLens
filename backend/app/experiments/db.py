"""Experiments database: SQLite at DATA_DIR/experiments.db, Postgres when DATABASE_URL is set.
The schema is owned by Alembic (app/experiments/migrations); init_db() upgrades to head."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def database_url(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    url = settings.DATABASE_URL
    if not url:
        path = Path(settings.DATA_DIR) / "experiments.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    # Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache(maxsize=8)
def _engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", _sqlite_pragmas)
        return engine
    return create_engine(url, pool_pre_ping=True)


def get_engine(settings: Settings | None = None) -> Engine:
    return _engine(database_url(settings))


def alembic_config(url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Percent signs in passwords must be escaped for ConfigParser interpolation.
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


_initialised: set[str] = set()


def init_db(settings: Settings | None = None) -> Engine:
    """Upgrade the schema to the latest migration (once per URL per process)."""
    url = database_url(settings)
    if url not in _initialised:
        command.upgrade(alembic_config(url), "head")
        _initialised.add(url)
    return _engine(url)


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """A session that commits on success and rolls back on any error."""
    engine = init_db(settings)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
