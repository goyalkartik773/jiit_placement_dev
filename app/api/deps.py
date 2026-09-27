"""FastAPI dependencies (container + database session)."""

from __future__ import annotations

from fastapi import Request

from app.container import Container

__all__ = ["get_container", "get_session"]


def get_container(request: Request) -> Container:
    return request.app.state.container


# Re-exported so route modules import everything from one place.
from app.db import get_session  # noqa: E402
