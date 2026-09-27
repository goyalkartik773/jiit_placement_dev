"""FastAPI application factory for the Gmail placement backend.

Run from the repository root::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import load_settings
from app.utils.logging import log_event, setup_logging

import logging

log = logging.getLogger("app.api")


def create_app() -> FastAPI:
    settings = load_settings()
    setup_logging(settings.log_level)

    application = FastAPI(
        title="JIIT Placement Gmail Backend",
        version="1.0.0",
        description=(
            "Two-step placement pipeline: Step 1 syncs raw Gmail messages into "
            "PostgreSQL (status PENDING), Step 2 classifies and extracts them "
            "into normalized placement tables. Deterministic parsing first; "
            "LLM fallback is optional and disabled by default."
        ),
    )

    from app.api import router as api_router
    from app.container import Container

    application.state.container = Container(settings)
    application.include_router(api_router)

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.on_event("startup")
    def _startup() -> None:
        log_event(
            log,
            "app.start",
            llm_enabled=settings.llm_enabled,
            source_groups=list(settings.gmail.source_groups),
        )

    return application


app = create_app()
