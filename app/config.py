"""Runtime configuration for the Gmail placement backend.

Secrets never live in tracked source: the PostgreSQL password and the Gmail
OAuth material are read from environment variables or the git-ignored ``.env``
file at the project root (the loader from ``placement_pipeline.config`` runs on
import and keeps existing environment variables winning).

Nothing here is ever logged — see :mod:`app.utils.logging`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Importing placement_pipeline.config loads the git-ignored .env file.
from placement_pipeline.config import PROJECT_ROOT  # noqa: F401  (side effect)

#: Gmail readonly scope — the backend never writes to the mailbox.
GMAIL_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/gmail.readonly",)

#: Default Google Groups.  ``jiitengg2027`` / ``jaypeeengg2027`` are the two
#: groups proven by the saved corpus; the other three come from the platform
#: spec and are harmless when their lists are empty. Override with
#: ``GMAIL_SOURCE_GROUPS=group1@googlegroups.com,group2@googlegroups.com``.
DEFAULT_SOURCE_GROUPS: tuple[str, ...] = (
    "jiitengg2027@googlegroups.com",
    "jiitintgt2027@googlegroups.com",
    "jiitmtech2027@googlegroups.com",
    "jiitmca2027@googlegroups.com",
    "jaypeeengg2027@googlegroups.com",
)


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_bool(name: str) -> bool:
    return _env(name).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def database_url() -> str:
    """SQLAlchemy URL built from the same env chain the parser uses.

    ``PLACEMENT_DATABASE_URL`` wins, otherwise the ``PLACEMENT_PG_*`` /
    ``PGPASSWORD`` variables shared with ``placement_pipeline.config``.
    """
    explicit = _env("PLACEMENT_DATABASE_URL")
    if explicit:
        return explicit
    host = _env("PLACEMENT_PG_HOST", "localhost")
    port = _env("PLACEMENT_PG_PORT", "5432")
    dbname = _env("PLACEMENT_PG_DB", "jiit_placement")
    user = _env("PLACEMENT_PG_USER", "postgres")
    password = _env("PLACEMENT_PG_PASSWORD") or _env("PGPASSWORD")
    auth = f"{user}:{password}@" if password else f"{user}@"
    return f"postgresql+psycopg2://{auth}{host}:{port}/{dbname}"


def _default_credentials_path() -> Path:
    override = _env("GMAIL_CREDENTIALS_PATH")
    if override:
        return Path(override).expanduser()
    # Shared with the .NET admin's OAuth client (same mailbox, same consent).
    return PROJECT_ROOT.parent / "JIITPlacement" / "credentials.json"


def _default_token_path() -> Path:
    override = _env("GMAIL_TOKEN_PATH")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "JIITPlacement" / "token.json"
    return PROJECT_ROOT / ".gmail_token.json"


@dataclass(frozen=True)
class GmailConfig:
    credentials_path: Path
    token_path: Path
    application_name: str
    scopes: tuple[str, ...]
    source_groups: tuple[str, ...]
    page_size: int
    max_attachment_bytes: int
    request_timeout: float


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_level: str
    gmail: GmailConfig
    llm_enabled: bool
    gemini_api_key: Optional[str]
    gemini_model: str
    gemini_base_url: str
    table_prefix: str = field(default="")


def load_settings() -> Settings:
    groups = tuple(
        g.strip()
        for g in _env("GMAIL_SOURCE_GROUPS").split(",")
        if g.strip()
    ) or DEFAULT_SOURCE_GROUPS
    gmail = GmailConfig(
        credentials_path=_default_credentials_path(),
        token_path=_default_token_path(),
        application_name=_env("GMAIL_APPLICATION_NAME", "JIIT Placement Backend"),
        scopes=GMAIL_SCOPES,
        source_groups=groups,
        page_size=_env_int("GMAIL_PAGE_SIZE", 100),
        max_attachment_bytes=_env_int("GMAIL_MAX_ATTACHMENT_BYTES", 5 * 1024 * 1024),
        request_timeout=float(_env("GMAIL_REQUEST_TIMEOUT", "30")),
    )
    return Settings(
        database_url=database_url(),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        gmail=gmail,
        llm_enabled=_env_bool("PLACEMENT_LLM_ENABLED"),
        gemini_api_key=_env("GEMINI_API_KEY") or None,
        gemini_model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
        gemini_base_url=_env(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
        ).rstrip("/"),
    )
