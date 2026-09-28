"""How many requests per day does a Gemini model actually give us?

Fires a paced burst of real extractions and prints the quota id of every
failure, so we can tell a per-*minute* hiccup from a per-*day* wall.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("PLACEMENT_HYBRID_LLM", "true")
os.environ.setdefault("PLACEMENT_LLM_MIN_INTERVAL", "1.0")

from sqlalchemy import select  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.llm import LLMUnavailable, get_service, reset_service  # noqa: E402
from app.models import Email  # noqa: E402

MODELS = sys.argv[1:] or ["gemini-3.1-flash-lite", "gemini-3.7-flash"]
N = 10
GM = "1a01489d56b0abf2"

_QUOTA_RE = re.compile(r"quotaId[\"']?\s*:\s*[\"']([^\"']+)")


def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        row = session.execute(select(Email).where(Email.gmail_message_id == GM)).scalar_one()
        subject, body = row.subject or "", row.body_text or ""
    finally:
        session.close()

    for model in MODELS:
        os.environ["PLACEMENT_LLM_MODEL_GEMINI"] = model
        reset_service()
        settings = load_settings()
        service = get_service(settings.hybrid)
        ok = 0
        failures: dict[str, int] = {}
        providers: dict[str, int] = {}
        for i in range(N):
            try:
                result = service.extract(subject=subject, body=body)
            except LLMUnavailable as exc:
                key = exc.reason.split(";")[0].strip()
                failures[key] = failures.get(key, 0) + 1
                continue
            ok += 1
            providers[result.provider] = providers.get(result.provider, 0) + 1
        print(f"\n{model}: {ok}/{N} ok   served_by={providers}")
        for key, count in failures.items():
            print(f"   x{count} {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
