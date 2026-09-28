"""Multi-account LLM router: Gemini -> Groq -> DeepSeek with auto-failover.

The extractor calls :meth:`LLMService.extract` without knowing which
provider/account served the request:

* providers are tried in priority order (Gemini, Groq, DeepSeek);
* inside a provider, accounts round-robin so quota spreads evenly;
* a 429/quota or auth failure moves to the **next account of the same
  provider**, then to the next provider once the pool is exhausted;
* exponential backoff sits between retries, and a per-account circuit breaker
  skips an account for N minutes instead of hammering it;
* a 200 response whose JSON does not match the schema is retried **once** on
  the same account and then treated as a provider failure (failover).

Only account *labels* ("gemini_2") are ever logged - never a key value.
When every provider fails, :class:`LLMUnavailable` is raised so the caller can
keep the deterministic result as ``rule_based_fallback`` and requeue.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx

from app.config import LLMAccount, LLMConfig, LLM_PROVIDER_ORDER
from app.llm.prompt import SYSTEM_PROMPT, build_user_message
from app.llm.schema import FinalSelectionExtraction
from app.utils.logging import log_event

log = logging.getLogger("app.llm.router")


class LLMUnavailable(RuntimeError):
    """Every provider/account failed - the caller must fall back."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _AccountFailure(Exception):
    """One account failed; try the next account (then the next provider)."""

    def __init__(self, kind: str, detail: str = "", retry_after: float = 0.0) -> None:
        super().__init__(detail)
        #: "quota" | "auth" | "config" | "transient" | "schema"
        self.kind = kind
        self.detail = detail
        #: The provider's own "retry in Ns" / Retry-After hint, when present.
        self.retry_after = retry_after
        #: auth/balance/model-gone failures keep an account out much longer.
        self.hard = kind in ("auth", "config")


@dataclass
class LLMStats:
    """Counters surfaced in the processing stats / testing report."""

    calls: int = 0
    ok: int = 0
    ok_first_attempt: int = 0
    ok_after_failover: int = 0
    schema_retries: int = 0
    unavailable: int = 0
    attempts: int = 0
    attempts_by_account: dict[str, int] = field(default_factory=dict)
    #: Which accounts actually served a verdict (attempts includes failures).
    ok_by_account: dict[str, int] = field(default_factory=dict)
    failovers_by_provider: dict[str, int] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    #: Per-provider token spend, so a cost estimate can be priced per model.
    prompt_tokens_by_provider: dict[str, int] = field(default_factory=dict)
    completion_tokens_by_provider: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "ok": self.ok,
            "ok_first_attempt": self.ok_first_attempt,
            "ok_after_failover": self.ok_after_failover,
            "schema_retries": self.schema_retries,
            "unavailable": self.unavailable,
            "attempts": self.attempts,
            "attempts_by_account": dict(self.attempts_by_account),
            "ok_by_account": dict(self.ok_by_account),
            "failovers_by_provider": dict(self.failovers_by_provider),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "prompt_tokens_by_provider": dict(self.prompt_tokens_by_provider),
            "completion_tokens_by_provider": dict(
                self.completion_tokens_by_provider
            ),
        }


@dataclass
class LLMResult:
    """One successful, schema-validated extraction."""

    extraction: FinalSelectionExtraction
    #: "gemini_2"
    account_label: str
    provider: str
    #: True when a previous provider/account had to fail first.
    failed_over: bool
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class _AccountState:
    account: LLMAccount
    consecutive_failures: int = 0
    open_until: float = 0.0

    def available(self, now: float) -> bool:
        return now >= self.open_until


# --------------------------------------------------------------------------- #
# Provider adapters: one request shape per provider
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    """Models fence JSON despite being told not to - tolerate it, never store it."""
    return _FENCE_RE.sub("", text or "").strip()


def _json_object(text: str) -> dict:
    """Pull the first JSON object out of a model reply (fences already gone)."""
    cleaned = _strip_fences(text)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model output is not a JSON object")
    return payload


def _gemini_request(cfg: LLMConfig, account: LLMAccount, user_message: str):
    url = (
        f"{cfg.base_urls['gemini']}/v1beta/models/"
        f"{cfg.models['gemini']}:generateContent"
    )
    return {
        "url": url,
        "params": {"key": account.key},  # env-only secret, never logged
        "headers": {},
        "json": {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
        },
    }


def _gemini_text(data: dict) -> tuple[str, int, int]:
    parts = data["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts)
    usage = data.get("usageMetadata") or {}
    return (
        text,
        int(usage.get("promptTokenCount") or 0),
        int(usage.get("candidatesTokenCount") or 0),
    )


def _openai_request_factory(provider: str):
    def build(cfg: LLMConfig, account: LLMAccount, user_message: str) -> dict:
        return {
            "url": f"{cfg.base_urls[provider]}/chat/completions",
            "params": {},
            "headers": {"Authorization": f"Bearer {account.key}"},
            "json": {
                "model": cfg.models[provider],
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            },
        }

    return build


def _openai_text(data: dict) -> tuple[str, int, int]:
    choice = data["choices"][0]["message"]["content"] or ""
    usage = data.get("usage") or {}
    return (
        choice,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
    )


#: provider -> (request builder, response text extractor)
_ADAPTERS: dict[str, tuple[Callable, Callable]] = {
    "gemini": (_gemini_request, _gemini_text),
    "groq": (_openai_request_factory("groq"), _openai_text),
    "deepseek": (_openai_request_factory("deepseek"), _openai_text),
}


_RETRY_IN_RE = re.compile(r"retry in ([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)


def _retry_after(response: httpx.Response) -> float:
    """Seconds the provider asks us to wait, if it says so.

    Gemini answers with ``Please retry in 50.7s`` in the error body, Groq with
    a ``Retry-After`` header.  Either is a better cooldown guess than a fixed
    one, so an account rests exactly as long as it needs to.
    """
    candidates: list[float] = []
    header = response.headers.get("retry-after", "")
    if header:
        try:
            candidates.append(float(header))
        except ValueError:
            pass
    match = _RETRY_IN_RE.search(response.text or "")
    if match:
        candidates.append(float(match.group(1)))
    return max(candidates, default=0.0)


def _classify(status_code: int, body: str) -> str:
    lowered = (body or "").lower()
    if status_code == 429 or "rate limit" in lowered or "quota" in lowered:
        return "quota"
    if status_code in (401, 402, 403) or "invalid api key" in lowered or "insufficient balance" in lowered:
        return "auth"
    if status_code == 404:
        # "model is no longer available to this account" - retrying the same
        # request on this account can never succeed, so park it for long.
        return "config"
    if status_code >= 500:
        return "transient"
    if status_code >= 400:
        return "transient"
    return "transient"


class LLMService:
    """Internal abstraction the extractor calls; provider choice stays here."""

    def __init__(
        self,
        cfg: LLMConfig,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = cfg
        self.stats = LLMStats()
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self._client = httpx.Client(timeout=cfg.timeout, transport=transport)
        self._pools: dict[str, list[_AccountState]] = {}
        self._cursor: dict[str, int] = {}
        #: monotonic time of the last request per account label (pacing)
        self._last_call: dict[str, float] = {}
        for provider, accounts in self._group(cfg.accounts):
            self._pools[provider] = [_AccountState(account=a) for a in accounts]
            self._cursor[provider] = 0

    @staticmethod
    def _group(accounts: tuple[LLMAccount, ...]) -> list[tuple[str, list[LLMAccount]]]:
        grouped: dict[str, list[LLMAccount]] = {}
        for account in accounts:
            grouped.setdefault(account.provider, []).append(account)
        return list(grouped.items())

    # -- circuit breaker ---------------------------------------------------- #

    def _next_account(self, provider: str) -> Optional[_AccountState]:
        pool = self._pools[provider]
        now = self._clock()
        for _ in range(len(pool)):
            with self._lock:
                index = self._cursor[provider] % len(pool)
                self._cursor[provider] = (index + 1) % len(pool)
            state = pool[index]
            if state.available(now):
                return state
        return None  # every account in the pool is on cooldown

    def _pool_wait(self, provider: str) -> float:
        """Seconds until the soonest account of ``provider`` recovers."""
        now = self._clock()
        opens = [s.open_until for s in self._pools[provider] if s.open_until > now]
        return max(0.0, min(opens) - now) if opens else 0.0

    def _record_failure(
        self, state: _AccountState, kind: str, retry_after: float = 0.0
    ) -> None:
        if kind == "quota":
            # A 429 is the meter talking, not a broken account: rest it for as
            # long as the provider asks (or ``quota_cooldown`` if it does not
            # say), but do NOT count it towards the breaker - two rate limits
            # must not lock a healthy account out mid-corpus.
            seconds = max(retry_after, self.cfg.quota_cooldown)
            state.open_until = max(state.open_until, self._clock() + seconds)
            log_event(
                log,
                "llm.account_cooldown",
                account=state.account.label,
                kind=kind,
                seconds=round(seconds, 1),
            )
            return

        state.consecutive_failures += 1
        threshold = max(1, self.cfg.breaker_threshold)
        if state.consecutive_failures >= threshold:
            seconds = (
                self.cfg.breaker_seconds_hard
                if kind in ("auth", "config")
                else self.cfg.breaker_seconds
            )
            state.open_until = self._clock() + seconds
            log_event(
                log,
                "llm.account_cooldown",
                level=logging.WARNING,
                account=state.account.label,
                kind=kind,
                seconds=seconds,
            )

    def _record_success(self, state: _AccountState) -> None:
        state.consecutive_failures = 0
        state.open_until = 0.0

    # -- one account attempt ------------------------------------------------ #

    def _attempt(self, state: _AccountState, user_message: str) -> LLMResult:
        provider = state.account.provider
        build_request, extract_text = _ADAPTERS[provider]
        request = build_request(self.cfg, state.account, user_message)

        self._pace(state.account.label)
        try:
            response = self._client.post(
                request["url"],
                params=request["params"],
                headers=request["headers"],
                json=request["json"],
            )
        except Exception as exc:  # network/timeout
            raise _AccountFailure("transient", type(exc).__name__) from exc

        if response.status_code != 200:
            raise _AccountFailure(
                _classify(response.status_code, response.text),
                f"HTTP {response.status_code}",
                _retry_after(response),
            )

        try:
            data = response.json()
            text, prompt_tokens, completion_tokens = extract_text(data)
            payload = _json_object(text)
            extraction = FinalSelectionExtraction.model_validate(payload)
        except Exception as exc:
            # Schema/shape failure: retried once on the SAME account by the
            # caller, then treated as a provider failure.
            raise _AccountFailure("schema", type(exc).__name__) from exc

        try:
            latency = int(response.elapsed.total_seconds() * 1000)
        except Exception:  # no timing on a canned/fake response
            latency = 0

        return LLMResult(
            extraction=extraction,
            account_label=state.account.label,
            provider=provider,
            failed_over=False,
            latency_ms=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    # -- public API --------------------------------------------------------- #

    def extract(self, *, subject: str, body: str) -> LLMResult:
        """Run the fixed prompt through the router; raise :class:`LLMUnavailable`."""
        with self._lock:
            self.stats.calls += 1
        if not self.cfg.enabled or not self.cfg.accounts:
            raise LLMUnavailable("hybrid LLM extraction is disabled")

        user_message = build_user_message(
            subject=subject,
            body=body,
            max_body_chars=self.cfg.max_body_chars,
        )

        providers = [p for p in LLM_PROVIDER_ORDER if p in self._pools]
        failures: list[str] = []
        call_attempts = 0

        for provider in providers:
            pool_size = len(self._pools[provider])
            schema_retry_done: set[str] = set()
            waits = 0

            # One pass over the pool: every account gets exactly one try per
            # provider (the schema retry happens inside the same iteration),
            # then we move on to the next provider instead of hammering it.
            tried: set[str] = set()
            while len(tried) < pool_size:
                state = self._next_account(provider)
                if state is None:
                    # Every account is resting - most often on a short quota
                    # cooldown.  Waiting out the soonest one beats declaring
                    # the whole provider unavailable and losing the email.
                    wait = self._pool_wait(provider)
                    if wait > 0 and wait <= self.cfg.max_pool_wait and waits < self.cfg.pool_wait_rounds:
                        waits += 1
                        log_event(
                            log,
                            "llm.pool_wait",
                            level=logging.INFO,
                            provider=provider,
                            wait_s=round(wait, 1),
                            round=waits,
                        )
                        self._sleep(wait)
                        tried.clear()  # cooldowns may have expired
                        continue
                    failures.append(
                        f"{provider}: all accounts cooling down"
                        + (f" ({wait:.0f}s)" if wait else "")
                    )
                    break
                if state.account.label in tried:
                    failures.append(f"{provider}: accounts exhausted")
                    break
                tried.add(state.account.label)

                with self._lock:
                    self.stats.attempts += 1
                    call_attempts += 1
                    label = state.account.label
                    self.stats.attempts_by_account[label] = (
                        self.stats.attempts_by_account.get(label, 0) + 1
                    )

                delay = self._backoff(call_attempts)
                if delay:
                    self._sleep(delay)

                try:
                    result = self._attempt(state, user_message)
                except _AccountFailure as failure:
                    self._record_failure(state, failure.kind, failure.retry_after)
                    failures.append(f"{label}: {failure.kind} {failure.detail}")
                    with self._lock:
                        self.stats.failovers_by_provider[provider] = (
                            self.stats.failovers_by_provider.get(provider, 0) + 1
                        )

                    if failure.kind == "schema" and label not in schema_retry_done:
                        # "retry once against the same account"
                        schema_retry_done.add(label)
                        with self._lock:
                            self.stats.schema_retries += 1
                        try:
                            result = self._attempt(state, user_message)
                        except _AccountFailure as again:
                            self._record_failure(
                                state, again.kind, again.retry_after
                            )
                            failures.append(
                                f"{label}: schema-retry {again.kind}"
                            )
                            continue
                        self._record_success(state)
                        return self._finish(
                            result,
                            failed_over=call_attempts > 1,
                            provider=provider,
                        )
                    continue

                self._record_success(state)
                return self._finish(
                    result, failed_over=call_attempts > 1, provider=provider
                )
            # pool exhausted -> fall through to the next provider

        with self._lock:
            self.stats.unavailable += 1
        reason = "; ".join(failures[:8]) or "no account available"
        raise LLMUnavailable(reason)

    def _pace(self, label: str) -> None:
        """Keep ``min_interval`` between two calls to the same account.

        Providers meter per key (Gemini: 20 free requests/minute), so spacing
        the requests is cheaper than earning a 429 and a cooldown.
        """
        if self.cfg.min_interval <= 0:
            return
        wait = self._last_call.get(label, 0.0) + self.cfg.min_interval - self._clock()
        if wait > 0:
            self._sleep(wait)
        with self._lock:
            self._last_call[label] = self._clock()

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff, capped; never sleeps before the very first try."""
        if attempt <= 1:
            return 0.0
        return min(self.cfg.backoff_cap, self.cfg.backoff_base * (2 ** (attempt - 2)))

    def _finish(
        self, result: LLMResult, *, failed_over: bool, provider: str
    ) -> LLMResult:
        result.failed_over = failed_over
        with self._lock:
            self.stats.ok += 1
            if failed_over:
                self.stats.ok_after_failover += 1
            else:
                self.stats.ok_first_attempt += 1
            self.stats.ok_by_account[result.account_label] = (
                self.stats.ok_by_account.get(result.account_label, 0) + 1
            )
            self.stats.prompt_tokens += result.prompt_tokens
            self.stats.completion_tokens += result.completion_tokens
            self.stats.prompt_tokens_by_provider[provider] = (
                self.stats.prompt_tokens_by_provider.get(provider, 0)
                + result.prompt_tokens
            )
            self.stats.completion_tokens_by_provider[provider] = (
                self.stats.completion_tokens_by_provider.get(provider, 0)
                + result.completion_tokens
            )
        log_event(
            log,
            "llm.extract_ok",
            account=result.account_label,
            provider=provider,
            email_type=result.extraction.email_type,
            confidence=round(result.extraction.confidence, 3),
            students=len(result.extraction.students),
            failed_over=failed_over,
            latency_ms=result.latency_ms,
        )
        return result

    def close(self) -> None:
        self._client.close()


# --------------------------------------------------------------------------- #
# Process-wide instance (round-robin/circuit state must survive per-email calls)
# --------------------------------------------------------------------------- #

_service: Optional[LLMService] = None
_service_lock = threading.Lock()


def get_service(cfg: LLMConfig) -> LLMService:
    """Return the shared service for ``cfg`` (rebuilt if the config changed)."""
    global _service
    with _service_lock:
        if _service is None or _service.cfg != cfg:
            if _service is not None:
                _service.close()
            _service = LLMService(cfg)
        return _service


def reset_service() -> None:
    """Drop the shared service (tests / a fresh processing run)."""
    global _service
    with _service_lock:
        if _service is not None:
            _service.close()
        _service = None


def stats_snapshot() -> dict:
    with _service_lock:
        return _service.stats.as_dict() if _service is not None else {}
