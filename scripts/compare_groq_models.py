"""Compare Groq models on real golden FINAL_SELECTION emails.

    python scripts/compare_groq_models.py

Reads the four golden offer emails straight from the corpus, runs each through
the real router with one Groq model at a time, and prints what each model
answered plus what it cost.  No keys are ever printed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("PLACEMENT_HYBRID_LLM", "true")

from sqlalchemy import select  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.llm import LLMUnavailable, get_service, reset_service, stats_snapshot  # noqa: E402
from app.models import Email  # noqa: E402
from scripts.run_backend_validation import GOLDEN  # noqa: E402

#: Golden FINAL_SELECTION samples: (gmail id, minimum offer students we expect).
SAMPLES: list[tuple[str, int]] = [
    ("19ed55cde526a30b", 4),   # the sample the current model got WRONG
    ("19ef8e389b433689", 3),   # Phase 0 bug email #1
    ("1a01489d56b0abf2", 1),
    ("19ef8235d0f7f88a", 1),
]

MODELS: list[str] = (
    sys.argv[1:]
    or ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
)
#: Which provider's model env var to write - GROQ by default, or GEMINI.
PROVIDER: str = os.environ.get("COMPARE_PROVIDER", "GROQ").upper()


def load_bodies() -> dict[str, tuple[str, str]]:
    factory = get_session_factory()
    session = factory()
    try:
        rows = session.scalars(
            select(Email).where(Email.gmail_message_id.in_([gm for gm, _ in SAMPLES]))
        ).all()
        return {r.gmail_message_id: (r.subject or "", r.body_text or "") for r in rows}
    finally:
        session.close()


def main() -> int:
    bodies = load_bodies()
    expected = dict(SAMPLES)
    spec_by_gm = {s["gm"]: s for s in GOLDEN if s["gt"] == "FINAL_SELECTION"}

    for model in MODELS:
        os.environ[f"PLACEMENT_LLM_MODEL_{PROVIDER}"] = model
        reset_service()
        settings = load_settings()
        service = get_service(settings.hybrid)
        print(f"\n===== {model} =====")
        for gm, _ in SAMPLES:
            if gm not in bodies:
                print(f"  {gm}: MISSING from corpus")
                continue
            subject, body = bodies[gm]
            want = expected[gm]
            try:
                result = service.extract(subject=subject, body=body)
            except LLMUnavailable as exc:
                print(f"  {gm}: UNAVAILABLE  {exc.reason[:160]}")
                continue
            ext = result.extraction
            got = len(ext.students)
            status = "OK " if ext.is_final() and got >= want else "WRONG"
            spec = spec_by_gm.get(gm, {})
            print(
                f"  {gm}: {status} type={ext.email_type} students={got} (want >= {want}) "
                f"company={ext.company!r} conf={ext.confidence} "
                f"{result.provider}/{result.account_label} "
                f"tokens={result.prompt_tokens}+{result.completion_tokens}"
            )
            if status == "WRONG" and ext.evidence:
                print(f"          evidence: {ext.evidence[:220]}")
        stats = stats_snapshot()
        print(
            f"  -- calls={stats['calls']} ok={stats['ok']} unavailable={stats['unavailable']} "
            f"prompt={stats['prompt_tokens']} completion={stats['completion_tokens']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
