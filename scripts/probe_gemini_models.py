"""Try several Gemini models with one real extraction call each."""
import os
import sys
from pathlib import Path

ROOT = Path(r"D:\jiit_placement_alerts\placement_pipeline")
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PLACEMENT_HYBRID_LLM", "true")

from sqlalchemy import select  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.db import get_session_factory  # noqa: E402
from app.llm import LLMUnavailable, get_service, reset_service  # noqa: E402
from app.models import Email  # noqa: E402

CANDIDATES = [
    "gemini-3.8-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
]
GM = "1a01489d56b0abf2"  # small FINAL_SELECTION sample: 1 offer student


def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        row = session.execute(
            select(Email).where(Email.gmail_message_id == GM)
        ).scalar_one()
        subject, body = row.subject or "", row.body_text or ""
    finally:
        session.close()

    for model in CANDIDATES:
        os.environ["PLACEMENT_LLM_MODEL_GEMINI"] = model
        reset_service()
        settings = load_settings()
        service = get_service(settings.hybrid)
        try:
            result = service.extract(subject=subject, body=body)
        except LLMUnavailable as exc:
            print(f"  {model:28s} FAIL  {exc.reason[:150]}")
            continue
        ext = result.extraction
        print(
            f"  {model:28s} OK    {result.provider}/{result.account_label} "
            f"type={ext.email_type} students={len(ext.students)} "
            f"conf={ext.confidence} tokens={result.prompt_tokens}+{result.completion_tokens}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
