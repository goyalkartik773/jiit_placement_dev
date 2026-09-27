"""Structured JSON logging with secret redaction.

Every log line is one JSON object: ``{"ts", "level", "event", ...fields}``.
Any field whose name looks like a secret (token, password, key, ...) is
replaced with ``"***"`` so OAuth material can never leak into logs.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

_SECRET_KEY_RE = re.compile(r"(token|secret|password|authorization|api[-_]?key)", re.I)

#: Fields that are always masked regardless of value type.
_REDACTED = "***"


def _scrub(key: str, value: Any) -> Any:
    if _SECRET_KEY_RE.search(key):
        return _REDACTED
    if isinstance(value, dict):
        return {k: _scrub(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(key, v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """One JSON object per line; ``extra={"fields": {...}}`` carries context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                payload[key] = _scrub(str(key), value)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if any(getattr(h, "_placement_json", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._placement_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    # uvicorn's access log adds noise; our own events are the signal.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_event(
    logger: logging.Logger, event: str, *, level: int = logging.INFO, **fields: Any
) -> None:
    """Emit one structured event: ``log_event(log, "sync.page", fetched=100)``."""
    logger.log(level, event, extra={"fields": fields})
