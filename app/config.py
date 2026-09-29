"""Runtime configuration for the Gmail placement backend.

Secrets never live in tracked source: the PostgreSQL password and the **Gmail
IMAP app password** are read from environment variables or the git-ignored
``.env`` file at the project root (the loader from ``placement_pipeline.config``
runs on import and keeps existing environment variables winning).

Mail transport is IMAP + app password (``imaplib``, stdlib only) - the Gmail
REST API/OAuth material (``credentials.json`` / ``token.json``) is gone.

Nothing here is ever logged - see :mod:`app.utils.logging`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Importing placement_pipeline.config loads the git-ignored .env file.
from placement_pipeline.config import PROJECT_ROOT  # noqa: F401  (side effect)

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


# --------------------------------------------------------------------------- #
# LLM provider router (hybrid extraction for offer-type emails)
# --------------------------------------------------------------------------- #

#: Provider priority order.  Every provider is tried before giving up.
LLM_PROVIDER_ORDER: tuple[str, ...] = ("gemini", "groq", "deepseek")

#: ``provider -> (account count, env var template)``.  One variable per
#: account; accounts round-robin inside their provider.
LLM_ACCOUNT_SPECS: dict[str, tuple[int, str]] = {
    "gemini": (6, "GEMINI_API_KEY_{n}"),
    "groq": (5, "GROQ_API_KEY_{n}"),
    "deepseek": (4, "DEEPSEEK_API_KEY_{n}"),
}

#: Expected variables - the names only ever leave this module, never values.
LLM_ENV_VARS: tuple[str, ...] = tuple(
    template.format(n=n)
    for _, (count, template) in LLM_ACCOUNT_SPECS.items()
    for n in range(1, count + 1)
)


class LLMConfigError(RuntimeError):
    """Raised at startup when the hybrid layer is enabled but keys are missing.

    The message lists **variable names only** - never a key value.
    """


@dataclass(frozen=True)
class LLMAccount:
    provider: str
    #: Human-readable log label: ``gemini_1``, ``groq_2``, ``deepseek_4``.
    label: str
    key: str


@dataclass(frozen=True)
class LLMConfig:
    #: False disables the hybrid layer (offline tests); never silently partial.
    enabled: bool
    #: Ordered by :data:`LLM_PROVIDER_ORDER`, round-robin inside a provider.
    accounts: tuple[LLMAccount, ...]
    models: dict[str, str]
    base_urls: dict[str, str]
    timeout: float
    #: Exponential backoff between retries (seconds).
    backoff_base: float
    backoff_cap: float
    #: Circuit breaker: skip an account for this long after N failures.
    breaker_threshold: int
    breaker_seconds: int
    #: A long-lived outage (auth / no balance) opens the breaker for longer.
    breaker_seconds_hard: int
    #: Below this the result is still accepted but flagged ``low_confidence``.
    low_confidence: float
    #: Body characters sent to the model (the rest is truncated, never lost -
    #: the deterministic parser still sees the full text).
    max_body_chars: int
    #: 429/quota is not an account *failure* (it would trip the breaker after
    #: only a couple of hits and lock the whole pool out mid-corpus); it just
    #: rests that account for this long - or for the provider's own
    #: ``Retry-After`` / "please retry in Ns" hint, whichever is longer.
    quota_cooldown: float = 60.0
    #: Minimum spacing between two calls to the **same account** (seconds).
    #: Providers meter per key, so this keeps a burst under the per-minute
    #: quota instead of earning a 429 (0 disables pacing).
    min_interval: float = 0.0
    #: When every account of a provider is cooling, wait this long once for
    #: the cheapest cooldown instead of declaring the provider unavailable.
    #: When every account of a provider is cooling, wait this long for the
    #: soonest one to come back instead of declaring the provider down.
    #: Kept small on purpose: waiting out a full 60 s Gemini quota window
    #: when Groq can answer immediately would be far more expensive than
    #: the failover the spec already asks for.
    max_pool_wait: float = 15.0
    #: How many such waits a single extraction may take per provider.
    pool_wait_rounds: int = 2


_DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "openai/gpt-oss-120b",
    "deepseek": "deepseek-chat",
}

_DEFAULT_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
}


def load_llm_config() -> LLMConfig:
    """Build the router configuration from the environment.

    Every expected variable must be present when the hybrid layer is enabled;
    a missing one raises :class:`LLMConfigError` naming it (fail fast instead
    of silently running a provider short).  Values are never echoed.
    """
    enabled = _env("PLACEMENT_HYBRID_LLM", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if not enabled:
        return LLMConfig(
            enabled=False,
            accounts=(),
            models=dict(_DEFAULT_MODELS),
            base_urls=dict(_DEFAULT_BASE_URLS),
            timeout=float(_env("PLACEMENT_LLM_TIMEOUT", "60")),
            backoff_base=float(_env("PLACEMENT_LLM_BACKOFF_BASE", "0.5")),
            backoff_cap=float(_env("PLACEMENT_LLM_BACKOFF_CAP", "8")),
            breaker_threshold=_env_int("PLACEMENT_LLM_BREAKER_THRESHOLD", 2),
            breaker_seconds=_env_int("PLACEMENT_LLM_BREAKER_SECONDS", 120),
            breaker_seconds_hard=_env_int(
                "PLACEMENT_LLM_BREAKER_HARD_SECONDS", 1800
            ),
            low_confidence=float(_env("PLACEMENT_LLM_LOW_CONFIDENCE", "0.5")),
            max_body_chars=_env_int("PLACEMENT_LLM_MAX_BODY_CHARS", 24000),
            quota_cooldown=float(_env("PLACEMENT_LLM_QUOTA_COOLDOWN", "60")),
            min_interval=float(_env("PLACEMENT_LLM_MIN_INTERVAL", "0")),
            max_pool_wait=float(_env("PLACEMENT_LLM_MAX_POOL_WAIT", "15")),
            pool_wait_rounds=_env_int("PLACEMENT_LLM_POOL_WAIT_ROUNDS", 2),
        )

    accounts: list[LLMAccount] = []
    missing: list[str] = []
    for provider in LLM_PROVIDER_ORDER:
        count, template = LLM_ACCOUNT_SPECS[provider]
        for n in range(1, count + 1):
            name = template.format(n=n)
            value = os.environ.get(name)
            if not value:
                missing.append(name)
                continue
            accounts.append(
                LLMAccount(provider=provider, label=f"{provider}_{n}", key=value)
            )
    if missing:
        raise LLMConfigError(
            "Hybrid LLM extraction is enabled but these environment variables "
            "are missing: " + ", ".join(missing) + ". Set them (see "
            ".env.example) or set PLACEMENT_HYBRID_LLM=false to run the "
            "deterministic parser only."
        )

    return LLMConfig(
        enabled=True,
        accounts=tuple(accounts),
        models={
            provider: _env(f"PLACEMENT_LLM_MODEL_{provider.upper()}", default_model)
            for provider, default_model in _DEFAULT_MODELS.items()
        },
        base_urls={
            provider: _env(
                f"PLACEMENT_LLM_URL_{provider.upper()}", default_url
            ).rstrip("/")
            for provider, default_url in _DEFAULT_BASE_URLS.items()
        },
        timeout=float(_env("PLACEMENT_LLM_TIMEOUT", "60")),
        backoff_base=float(_env("PLACEMENT_LLM_BACKOFF_BASE", "0.5")),
        backoff_cap=float(_env("PLACEMENT_LLM_BACKOFF_CAP", "8")),
        breaker_threshold=_env_int("PLACEMENT_LLM_BREAKER_THRESHOLD", 2),
        breaker_seconds=_env_int("PLACEMENT_LLM_BREAKER_SECONDS", 120),
        breaker_seconds_hard=_env_int("PLACEMENT_LLM_BREAKER_HARD_SECONDS", 1800),
        low_confidence=float(_env("PLACEMENT_LLM_LOW_CONFIDENCE", "0.5")),
        max_body_chars=_env_int("PLACEMENT_LLM_MAX_BODY_CHARS", 24000),
        quota_cooldown=float(_env("PLACEMENT_LLM_QUOTA_COOLDOWN", "60")),
        min_interval=float(_env("PLACEMENT_LLM_MIN_INTERVAL", "0")),
        max_pool_wait=float(_env("PLACEMENT_LLM_MAX_POOL_WAIT", "15")),
        pool_wait_rounds=_env_int("PLACEMENT_LLM_POOL_WAIT_ROUNDS", 2),
    )


@dataclass(frozen=True)
class GmailConfig:
    """Mail transport settings: IMAP + app password (Gmail OAuth retired).

    Every value is env-driven; names only are ever reported on failure.
    """

    #: Gmail SMTP/IMAP endpoint (``imap.gmail.com`` for Google Workspace/Gmail).
    imap_host: str
    imap_port: int
    #: Mailbox account.  Requires 2-Step Verification so an app password exists.
    imap_email: str
    #: 16-character Gmail **app password** - never the account password, never
    #: logged, only ever handed to ``imaplib``.
    imap_app_password: str
    #: Folder to SELECT/watch (Gmail exposes one INBOX; other providers differ).
    imap_mailbox: str
    #: Polling interval for the auto-watcher (IMAP IDLE falls back to this).
    imap_poll_seconds: int
    #: Mark ``\Seen`` only after the row is committed (or confirmed a duplicate).
    imap_mark_seen_after_store: bool
    #: Use the IMAP ``IDLE`` extension when offered; polling is the fallback.
    imap_idle_enabled: bool
    #: Backoff bounds for dropped connections / transient IMAP errors.
    imap_backoff_base_seconds: int
    imap_backoff_cap_seconds: int
    #: Poison-mail valve: a row still ``PENDING`` after this many retries is
    #: marked ``FAILED`` by the watcher so one bad mail cannot loop forever.
    imap_max_retries: int
    source_groups: tuple[str, ...]
    #: Ids requested per IMAP search page (mirrors the old Gmail list page).
    page_size: int
    max_attachment_bytes: int
    request_timeout: float
    #: Minimum spacing between IMAP command *groups* (a full backfill paces
    #: itself instead of hammering the server; 0 disables pacing).
    min_interval_ms: int


@dataclass(frozen=True)
class Settings:
    database_url: str
    log_level: str
    gmail: GmailConfig
    llm_enabled: bool
    gemini_api_key: Optional[str]
    gemini_model: str
    gemini_base_url: str
    #: Multi-account router used for offer-type emails (hybrid pipeline).
    #: Loading it is what fails fast on missing ``*_API_KEY_*`` variables.
    hybrid: LLMConfig
    table_prefix: str = field(default="")


def load_settings() -> Settings:
    groups = tuple(
        g.strip()
        for g in _env("GMAIL_SOURCE_GROUPS").split(",")
        if g.strip()
    ) or DEFAULT_SOURCE_GROUPS
    gmail = GmailConfig(
        imap_host=_env("IMAP_HOST", "imap.gmail.com"),
        imap_port=_env_int("IMAP_PORT", 993),
        imap_email=_env("IMAP_EMAIL"),
        imap_app_password=_env("IMAP_APP_PASSWORD"),
        imap_mailbox=_env("IMAP_MAILBOX", "INBOX"),
        imap_poll_seconds=max(5, _env_int("IMAP_POLL_SECONDS", 60)),
        imap_mark_seen_after_store=(
            _env_bool("IMAP_MARK_SEEN_AFTER_STORE")
            if _env("IMAP_MARK_SEEN_AFTER_STORE")
            else True
        ),
        imap_idle_enabled=_env_bool("IMAP_IDLE_ENABLED"),
        imap_backoff_base_seconds=max(1, _env_int("IMAP_BACKOFF_BASE", 2)),
        imap_backoff_cap_seconds=max(5, _env_int("IMAP_BACKOFF_CAP", 300)),
        imap_max_retries=_env_int("IMAP_MAX_RETRIES", 5),
        source_groups=groups,
        page_size=_env_int("GMAIL_PAGE_SIZE", 100),
        max_attachment_bytes=_env_int("GMAIL_MAX_ATTACHMENT_BYTES", 5 * 1024 * 1024),
        request_timeout=float(_env("GMAIL_REQUEST_TIMEOUT", "30")),
        min_interval_ms=_env_int("GMAIL_MIN_INTERVAL_MS", 1100),
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
        hybrid=load_llm_config(),
    )
