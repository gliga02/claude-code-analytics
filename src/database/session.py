"""SQLite engine, schema bootstrap, and session factory."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_database_path() -> Path:
    """Resolve SQLite file path. Override with PROVECTUS_DATABASE_PATH."""
    raw = os.environ.get("PROVECTUS_DATABASE_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return (_project_root() / "data" / "analytics.db").resolve()


def create_engine_instance(*, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the configured SQLite database."""
    path = get_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path.as_posix()}"
    return create_engine(url, echo=echo)


def init_schema(engine: Engine) -> None:
    """Create all tables and indexes if they do not exist."""
    Base.metadata.create_all(bind=engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
