"""One-off probe: what are the real rate limits of the Gemini/Groq keys?

    python scripts/probe_rate_limits.py

Prints status codes only - never a key value.  Used to tune the router's
pacing / circuit-breaker so a full-corpus run does not lock every account out.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from placement_pipeline.config import _load_dotenv  # noqa: E402,F401


def probe(label: str, url: str, headers: dict, params: dict, body: dict,
          n: int = 6, gap: float = 0.4) -> list[int]:
    print(f"--- {label} ---")
    codes: list[int] = []
    for i in range(n):
        started = time.time()
        try:
            response = httpx.post(
                url, headers=headers, params=params, json=body, timeout=30
            )
            codes.append(response.status_code)
            retry_after = response.headers.get("retry-after", "")
            body_text = (response.text or "").replace("\n", " ")[:110]
            elapsed = int((time.time() - started) * 1000)
            print(
                f"  try{i + 1}: {response.status_code}  {elapsed}ms  "
                f"retry-after={retry_after!r}  {body_text}"
            )
        except Exception as exc:  # pragma: no cover - diagnostic script
            print(f"  EXC {type(exc).__name__} {str(exc)[:80]}")
        time.sleep(gap)
    print(f"  codes: {codes}")
    return codes


def main() -> int:
    k1 = os.environ.get("GEMINI_API_KEY_1", "")
    g1 = os.environ.get("GROQ_API_KEY_1", "")
    if not k1 or not g1:
        print("keys missing from environment")
        return 1

    probe(
        "gemini_1 (6x, 0.4s gap)",
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent",
        {},
        {"key": k1},
        {
            "contents": [{"role": "user", "parts": [{"text": "say hi"}]}],
            "generationConfig": {"maxOutputTokens": 8},
        },
    )

    probe(
        "groq_1 (6x, 0.4s gap)",
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {g1}"},
        {},
        {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
