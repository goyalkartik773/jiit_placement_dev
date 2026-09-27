"""LLM fallback for ONE ambiguous case: free-prose shortlist funnel counts.

Deterministic extraction is primary and must work with the LLM unavailable -
this module is only consulted when:

* the parser classified the email SHORTLIST, but found **no** student table
  **and no** funnel counts (pure free prose), and
* ``PLACEMENT_LLM_ENABLED=true`` with ``GEMINI_API_KEY`` set.

The prompt forbids inventing numbers: rows must be copied from sentences in
the email, each row carries its source sentence as evidence.  Any network or
parse failure returns ``None`` and the pipeline continues deterministic-only.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from app.config import Settings
from app.utils.logging import log_event

log = logging.getLogger("app.llm")

_MAX_ROWS = 12
_MAX_COUNT = 1_000_000

_PROMPT = """You extract round-progress counts from a placement email.
Return ONLY a JSON array (no markdown, no commentary) of objects:
[{{"round_name": str, "count": int, "evidence": str}}]
Rules:
- Every count MUST be a number literally written in the email (never computed).
- "evidence" is the exact sentence from the email containing that number.
- If no such counts exist, return [].
- Maximum {_MAX_ROWS} items.

Email subject: {subject}

Email body:
{body}
"""


def _extract_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON array in model output")
    return json.loads(match.group(0))


def _validate(rows: object) -> list[dict]:
    if not isinstance(rows, list):
        return []
    clean: list[dict] = []
    for row in rows[:_MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("round_name", "")).strip()
        count = row.get("count")
        if not name or not isinstance(count, int) or isinstance(count, bool):
            continue
        if count < 0 or count > _MAX_COUNT:
            continue
        clean.append(
            {
                "round_name": name[:200],
                "count": count,
                "evidence": str(row.get("evidence", "")).strip()[:1000],
            }
        )
    return clean


def extract_funnel_counts(
    settings: Settings, subject: str, body: str
) -> Optional[list[dict]]:
    """Return validated rows or ``None`` (disabled/failed -> deterministic path)."""
    if not settings.llm_enabled or not settings.gemini_api_key:
        return None

    prompt = _PROMPT.format(
        _MAX_ROWS=_MAX_ROWS, subject=(subject or "")[:500], body=(body or "")[:12000]
    )
    url = f"{settings.gemini_base_url}/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        response = httpx.post(
            url,
            params={"key": settings.gemini_api_key},  # env-only secret, never logged
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
            },
            timeout=20.0,
        )
        if response.status_code != 200:
            log_event(
                log,
                "llm.funnel_failed",
                level=logging.WARNING,
                status=response.status_code,
            )
            return None
        parts = response.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
    except Exception as exc:  # network/shape errors: stay deterministic
        log_event(
            log, "llm.funnel_failed", level=logging.WARNING, error=type(exc).__name__
        )
        return None

    try:
        rows = _validate(_extract_json_array(text))
    except (ValueError, json.JSONDecodeError):
        log_event(log, "llm.funnel_unparsable", level=logging.WARNING)
        return None

    log_event(log, "llm.funnel_rows", rows=len(rows))
    return rows or None
