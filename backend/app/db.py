"""SQLite engine, schema bootstrap, and session helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
SCHEMA_PATH = APP_DIR / "models" / "schema.sql"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "app.db"

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _resolve_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env = os.environ.get("MYPLAN_DB_PATH")
    return Path(env) if env else DEFAULT_DB_PATH


def get_database_url(db_path: str | Path | None = None) -> str:
    path = _resolve_db_path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _enable_foreign_keys(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def apply_schema(target_engine: Engine | None = None) -> None:
    """Run schema.sql (CREATE TABLE IF NOT EXISTS) against the engine."""
    eng = target_engine or engine
    if eng is None:
        raise RuntimeError("Call init_engine() before apply_schema()")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    raw = eng.raw_connection()
    try:
        raw.executescript(sql)
        raw.commit()
    finally:
        raw.close()


def init_engine(db_path: str | Path | None = None) -> Engine:
    """Create engine, turn on FKs, apply schema. Safe to call on every startup."""
    global engine, SessionLocal
    url = get_database_url(db_path)
    engine = create_engine(
        "sqlite:///D:/my-plan/my-plan-main/backend/data/app.db",  # 绝对路径，直指真库
        connect_args={"check_same_thread": False},
        future=True,
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    apply_schema(engine)
    return engine


def init_db(db_path: str | Path | None = None) -> Engine:
    """Alias used at application startup."""
    return init_engine(db_path)


@contextmanager
def get_session() -> Iterator[Session]:
    """Commit on success, rollback on error. Used by scripts and services."""
    if SessionLocal is None:
        init_engine()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
