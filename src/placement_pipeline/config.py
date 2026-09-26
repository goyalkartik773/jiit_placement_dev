"""Runtime configuration for the placement pipeline.

Secrets never live in tracked source: the PostgreSQL password is taken from
``PLACEMENT_PG_PASSWORD`` / ``PGPASSWORD`` or an optional git-ignored ``.env``
file at the project root.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the git-ignored .env file, if present.

    Existing environment variables always win.
    """
    if not ENV_PATH.is_file():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _dsn() -> str:
    explicit = os.environ.get("PLACEMENT_PG_DSN")
    if explicit:
        return explicit
    host = os.environ.get("PLACEMENT_PG_HOST", "localhost")
    dbname = os.environ.get("PLACEMENT_PG_DB", "jiit_placement")
    user = os.environ.get("PLACEMENT_PG_USER", "postgres")
    parts = [f"host={host}", f"dbname={dbname}", f"user={user}"]
    password = os.environ.get("PLACEMENT_PG_PASSWORD") or os.environ.get("PGPASSWORD")
    if password:
        parts.append(f"password={password}")
    return " ".join(parts)


#: Connection string for the mail-corpus PostgreSQL database.
PG_DSN: str = _dsn()

#: SQLite destination for the extracted placement facts.
SQLITE_PATH: Path = Path(
    os.environ.get("PLACEMENT_SQLITE_PATH") or (PROJECT_ROOT / "data" / "placement.sqlite3")
)

#: Month names used for date extraction (full + abbreviated).
MONTHS: dict[str, int] = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
