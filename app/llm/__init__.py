"""Hybrid extraction layer: LLM is authoritative for offer-type emails.

``app.llm.router.LLMService`` hides which provider/account served a request;
``app.llm.prompt`` holds the single fixed prompt; ``app.llm.schema`` is the
Pydantic contract every response must satisfy before anything is written.
"""

from __future__ import annotations

from app.llm.router import (
    LLMResult,
    LLMService,
    LLMStats,
    LLMUnavailable,
    get_service,
    reset_service,
    stats_snapshot,
)
from app.llm.schema import NON_FINAL_TYPES, FinalSelectionExtraction, LLMStudent

__all__ = [
    "FinalSelectionExtraction",
    "LLMResult",
    "LLMService",
    "LLMStats",
    "LLMUnavailable",
    "LLMStudent",
    "NON_FINAL_TYPES",
    "get_service",
    "reset_service",
    "stats_snapshot",
]
