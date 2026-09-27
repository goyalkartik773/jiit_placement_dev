"""SQLAlchemy engine/session management for the backend.

One central PostgreSQL database (``jiit_placement``). Tests point the engine
at a dedicated schema inside the *same* database via :func:`configure`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import load_settings

_engine: Optional[Engine] = None
_factory: Optional[sessionmaker[Session]] = None
_url: Optional[str] = None


def configure(url: Optional[str] = None) -> None:
    """(Re)build the engine/session factory. ``url=None`` restores settings."""
    global _engine, _factory, _url
    if _engine is not None:
        _engine.dispose()
    _url = url
    _engine = None
    _factory = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            _url or load_settings().database_url,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _factory


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
