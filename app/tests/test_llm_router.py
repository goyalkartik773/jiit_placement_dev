"""LLM router: schema contract, round-robin, failover, backoff, breaker.

Every test runs against ``httpx.MockTransport`` - no network, no cost, and no
real key ever leaves the process (the accounts below are fakes).
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import (
    LLMConfig,
    LLMConfigError,
    LLMAccount,
    LLM_ACCOUNT_SPECS,
    load_llm_config,
)
from app.llm.prompt import SCHEMA_JSON, SYSTEM_PROMPT, build_user_message
from app.llm.router import LLMService, LLMUnavailable
from app.llm.schema import FinalSelectionExtraction

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

FINAL_PAYLOAD = {
    "email_type": "FINAL_SELECTION",
    "company": "Acme Corporation",
    "role": "SDE",
    "stipend": None,
    "ctc_total": 1200000.0,
    "location": "Noida",
    "students": [
        {
            "roll_number": "21103001",
            "name": "Kartik Goel",
            "program": "B.Tech",
            "branch": "CSE",
        }
    ],
    "evidence": "The following students have been offered.",
    "confidence": 0.93,
}


def make_cfg(
    accounts: list[tuple[str, str]],
    *,
    backoff_base: float = 0.0,
    backoff_cap: float = 0.0,
    breaker_threshold: int = 2,
    breaker_seconds: int = 60,
    breaker_seconds_hard: int = 600,
) -> LLMConfig:
    """``accounts`` is a list of ``(provider, key)``; labels derive from order."""
    counters: dict[str, int] = {}
    built: list[LLMAccount] = []
    for provider, key in accounts:
        counters[provider] = counters.get(provider, 0) + 1
        built.append(
            LLMAccount(
                provider=provider,
                label=f"{provider}_{counters[provider]}",
                key=key,
            )
        )
    return LLMConfig(
        enabled=True,
        accounts=tuple(built),
        models={
            "gemini": "fake-gemini",
            "groq": "fake-groq",
            "deepseek": "fake-deepseek",
        },
        base_urls={
            "gemini": "https://gemini.test",
            "groq": "https://groq.test/v1",
            "deepseek": "https://deepseek.test",
        },
        timeout=5.0,
        backoff_base=backoff_base,
        backoff_cap=backoff_cap,
        breaker_threshold=breaker_threshold,
        breaker_seconds=breaker_seconds,
        breaker_seconds_hard=breaker_seconds_hard,
        low_confidence=0.5,
        max_body_chars=24000,
        # Unit tests assert the failover chain itself; they do not want a
        # router that sits waiting for a cooldown to expire.
        max_pool_wait=0.0,
    )


def account_of(request: httpx.Request) -> str:
    """Which account a request belongs to (gemini_1, groq_2, ...)."""
    if "gemini.test" in str(request.url):
        return "gemini:" + request.url.params.get("key", "")
    auth = request.headers.get("authorization", "")
    host = str(request.url.host)
    if "groq" in host:
        return "groq:" + auth.replace("Bearer ", "")
    return "deepseek:" + auth.replace("Bearer ", "")


def gemini_ok(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 40},
        },
    )


def openai_ok(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
        },
    )


def build_service(handler, cfg: LLMConfig, *, sleeps: list | None = None):
    transport = httpx.MockTransport(handler)
    return LLMService(
        cfg,
        transport=transport,
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
    )


# --------------------------------------------------------------------------- #
# schema + prompt contract
# --------------------------------------------------------------------------- #


def test_extraction_schema_accepts_the_contract_shape():
    parsed = FinalSelectionExtraction.model_validate(FINAL_PAYLOAD)
    assert parsed.is_final()
    assert parsed.students[0].roll_number == "21103001"
    assert parsed.confidence == 0.93


def test_extraction_schema_rejects_a_bad_email_type():
    with pytest.raises(Exception):
        FinalSelectionExtraction.model_validate(
            {**FINAL_PAYLOAD, "email_type": "SHORTLIST"}
        )


def test_extraction_schema_rejects_confidence_out_of_range():
    with pytest.raises(Exception):
        FinalSelectionExtraction.model_validate({**FINAL_PAYLOAD, "confidence": 1.4})


def test_extraction_schema_rejects_a_partial_response():
    """Omitting students/evidence/confidence must fail, not invent defaults."""
    with pytest.raises(Exception):
        FinalSelectionExtraction.model_validate({"email_type": "FINAL_SELECTION"})


def test_extraction_schema_ignores_extra_keys_models_like_to_add():
    parsed = FinalSelectionExtraction.model_validate(
        {**FINAL_PAYLOAD, "why": "because", "notes": ["a"]}
    )
    assert not hasattr(parsed, "why")


def test_prompt_carries_the_verbatim_schema_and_no_fences():
    for token in (
        '"email_type"',
        '"NOT_FINAL_SELECTION"',
        '"UNCERTAIN"',
        '"students"',
        '"evidence"',
        '"confidence"',
        '"roll_number"',
        '"ctc_total"',
    ):
        assert token in SCHEMA_JSON
    assert "```" not in SCHEMA_JSON
    assert "markdown fences" in SYSTEM_PROMPT
    assert "Never infer" in SYSTEM_PROMPT
    # shortlist/registration must be named as NOT_FINAL_SELECTION triggers
    assert "pending interviews" in SYSTEM_PROMPT


def test_user_message_truncates_long_bodies():
    message = build_user_message(
        subject="S", body="x" * 500, max_body_chars=100
    )
    assert "[body truncated]" in message
    assert len(message) < 400


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #


def test_round_robin_spreads_quota_across_a_pool():
    cfg = make_cfg([("gemini", "k1"), ("gemini", "k2"), ("gemini", "k3")])
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(account_of(request))
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    labels = [
        service.extract(subject="s", body="b").account_label for _ in range(3)
    ]
    assert labels == ["gemini_1", "gemini_2", "gemini_3"]
    assert service.stats.ok_first_attempt == 3
    assert service.stats.attempts == 3
    service.close()


def test_quota_failure_falls_to_the_next_account_of_the_same_provider():
    cfg = make_cfg([("gemini", "k1"), ("gemini", "k2")])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("key") == "k1":
            return httpx.Response(429, text="rate limit exceeded")
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    result = service.extract(subject="s", body="b")
    assert result.account_label == "gemini_2"
    assert result.provider == "gemini"
    assert result.failed_over is True  # an earlier attempt failed
    assert service.stats.failovers_by_provider["gemini"] == 1
    assert service.stats.ok_after_failover == 1
    service.close()


def test_auth_failure_on_one_account_does_not_poison_the_pool():
    cfg = make_cfg([("gemini", "k1"), ("gemini", "k2")])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("key") == "k1":
            return httpx.Response(401, text="invalid api key")
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    assert service.extract(subject="s", body="b").account_label == "gemini_2"
    service.close()


def test_provider_failover_groq_then_deepseek():
    cfg = make_cfg(
        [("gemini", "g1"), ("gemini", "g2"), ("groq", "q1"), ("deepseek", "d1")]
    )
    order: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tag = account_of(request)
        order.append(tag)
        if tag.startswith("gemini"):
            return httpx.Response(429, text="quota exceeded")
        if tag.startswith("groq"):
            return openai_ok(json.dumps(FINAL_PAYLOAD))
        return openai_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    result = service.extract(subject="s", body="b")
    assert result.provider == "groq"
    assert result.failed_over is True
    # both gemini accounts tried exactly once before groq served the request
    assert order.count("gemini:g1") == 1
    assert order.count("gemini:g2") == 1
    assert order[0].startswith("gemini")
    assert order[-1].startswith("groq")
    service.close()


def test_every_provider_failing_raises_unavailable_instead_of_fabricating():
    cfg = make_cfg([("gemini", "g1"), ("groq", "q1"), ("deepseek", "d1")])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    service = build_service(handler, cfg)
    with pytest.raises(LLMUnavailable) as excinfo:
        service.extract(subject="s", body="b")
    assert service.stats.unavailable == 1
    # the reason names accounts, never keys
    assert "g1" not in str(excinfo.value.reason)
    assert "gemini_1" in str(excinfo.value.reason)
    service.close()


def test_schema_invalid_response_is_retried_once_then_fails_over():
    cfg = make_cfg([("gemini", "g1"), ("groq", "q1")])
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tag = account_of(request)
        calls.append(tag)
        if tag.startswith("gemini"):
            # valid JSON, wrong schema (missing students/evidence)
            return gemini_ok(json.dumps({"email_type": "FINAL_SELECTION"}))
        return openai_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    result = service.extract(subject="s", body="b")
    assert calls.count("gemini:g1") == 2  # retry once against the same account
    assert service.stats.schema_retries == 1
    assert result.provider == "groq"
    service.close()


def test_markdown_fences_are_tolerated_but_never_returned():
    cfg = make_cfg([("gemini", "g1")])

    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_ok("```json\n" + json.dumps(FINAL_PAYLOAD) + "\n```")

    service = build_service(handler, cfg)
    result = service.extract(subject="s", body="b")
    assert result.extraction.students[0].name == "Kartik Goel"
    service.close()


def test_not_final_selection_is_accepted_verbatim():
    cfg = make_cfg([("gemini", "g1")])
    payload = {
        "email_type": "NOT_FINAL_SELECTION",
        "company": None,
        "role": None,
        "stipend": None,
        "ctc_total": None,
        "location": None,
        "students": [],
        "evidence": "This email describes a shortlist for the technical round.",
        "confidence": 0.88,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return gemini_ok(json.dumps(payload))

    service = build_service(handler, cfg)
    result = service.extract(subject="s", body="b")
    assert result.extraction.email_type == "NOT_FINAL_SELECTION"
    assert result.extraction.students == []
    service.close()


def test_exponential_backoff_between_retries_is_capped():
    cfg = make_cfg(
        [
            ("gemini", "g1"),
            ("gemini", "g2"),
            ("gemini", "g3"),
            ("groq", "q1"),
            ("groq", "q2"),
            ("groq", "q3"),
            ("deepseek", "d1"),
        ],
        backoff_base=1.0,
        backoff_cap=4.0,
    )
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "deepseek" in str(request.url.host):
            return openai_ok(json.dumps(FINAL_PAYLOAD))
        return httpx.Response(429, text="rate limited")

    service = build_service(handler, cfg, sleeps=sleeps)
    result = service.extract(subject="s", body="b")
    assert result.provider == "deepseek"
    # first attempt never sleeps; then 1, 2, 4, 4, 4 (capped at 4)
    assert sleeps == [1.0, 2.0, 4.0, 4.0, 4.0, 4.0]
    service.close()


def test_circuit_breaker_skips_a_repeatedly_failing_account():
    cfg = make_cfg(
        [("gemini", "g1"), ("gemini", "g2")], breaker_threshold=2, breaker_seconds=300
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("key") == "g1":
            return httpx.Response(500, text="backend exploded")
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    for _ in range(3):
        service.extract(subject="s", body="b")
    # g1 fails on call 1 and call 2 (threshold 2) -> breaker opens -> skipped
    assert service.stats.attempts_by_account["gemini_1"] == 2
    assert service.stats.attempts_by_account["gemini_2"] == 3
    assert service.stats.ok == 3
    service.close()


def test_quota_429_rests_the_account_without_tripping_the_breaker():
    """A rate limit is the meter talking, not a broken account.

    It must move the request to the next account at once (429 -> failover is
    in the spec) but must NOT count towards the breaker: two 429s used to
    open a 120 s breaker, and with a whole corpus to get through that locked
    every account out and made dozens of emails fall back to the rules.
    """
    cfg = make_cfg([("gemini", "g1"), ("gemini", "g2")], breaker_threshold=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("key") == "g1":
            return httpx.Response(429, text="rate limit exceeded")
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    service = build_service(handler, cfg)
    for _ in range(3):
        result = service.extract(subject="s", body="b")
        assert result.account_label == "gemini_2"
    # g1 cooled down after its FIRST 429 and never earned a breaker trip
    assert service.stats.attempts_by_account["gemini_1"] == 1
    assert service.stats.attempts_by_account["gemini_2"] == 3
    assert service.stats.ok == 3
    service.close()


def test_pool_wait_rides_out_a_quota_cooldown_instead_of_losing_the_email():
    """When the whole pool is resting, wait it out rather than give up.

    The previous behaviour was to declare the provider unavailable the
    instant every account was cooling, so a rate-limited corpus lost tens of
    emails to ``rule_based_fallback`` even though the accounts came back a
    few seconds later.
    """
    cfg = make_cfg([("gemini", "g1")])
    cfg = LLMConfig(
        **{
            **cfg.__dict__,
            "quota_cooldown": 60.0,
            "max_pool_wait": 75.0,
            "pool_wait_rounds": 1,
        }
    )
    now = {"t": 0.0}
    calls = {"n": 0}
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="rate limit exceeded")
        return gemini_ok(json.dumps(FINAL_PAYLOAD))

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now["t"] += seconds  # the wait really happens, in fake time

    service = LLMService(
        cfg,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
        clock=lambda: now["t"],
    )

    # First email: rate limited, nothing to wait for yet -> LLMUnavailable,
    # which the caller turns into rule_based_fallback + a requeue.
    with pytest.raises(LLMUnavailable):
        service.extract(subject="s", body="b")
    assert sleeps == []

    # Second email: the account is resting; the router rides out the 60 s
    # cooldown and serves the extraction instead of dropping the email.
    result = service.extract(subject="s", body="b")
    assert sleeps == [60.0]
    assert result.account_label == "gemini_1"
    assert service.stats.attempts_by_account["gemini_1"] == 2
    service.close()


def test_disabled_config_refuses_to_call_anything():
    cfg = make_cfg([("gemini", "g1")])
    cfg = LLMConfig(**{**cfg.__dict__, "enabled": False})
    service = build_service(lambda _r: gemini_ok("{}"), cfg)
    with pytest.raises(LLMUnavailable):
        service.extract(subject="s", body="b")
    assert service.stats.calls == 1
    service.close()


# --------------------------------------------------------------------------- #
# configuration: env-only keys, fail fast
# --------------------------------------------------------------------------- #

_ENV_KEYS = [
    "GEMINI_API_KEY_1",
    "GEMINI_API_KEY_2",
    "GEMINI_API_KEY_3",
    "GEMINI_API_KEY_4",
    "GROQ_API_KEY_1",
    "GROQ_API_KEY_2",
    "GROQ_API_KEY_3",
    "DEEPSEEK_API_KEY_1",
    "DEEPSEEK_API_KEY_2",
    "DEEPSEEK_API_KEY_3",
    "DEEPSEEK_API_KEY_4",
]


def test_hybrid_disabled_reads_no_keys_at_all(monkeypatch):
    monkeypatch.setenv("PLACEMENT_HYBRID_LLM", "false")
    for name in _ENV_KEYS:
        monkeypatch.delenv(name, raising=False)
    cfg = load_llm_config()
    assert cfg.enabled is False
    assert cfg.accounts == ()


def test_missing_key_fails_fast_and_names_variables_not_values(monkeypatch):
    monkeypatch.setenv("PLACEMENT_HYBRID_LLM", "true")
    for name in _ENV_KEYS:
        monkeypatch.setenv(name, f"fake-value-{name}")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.setenv("GROQ_API_KEY_2", "")

    with pytest.raises(LLMConfigError) as excinfo:
        load_llm_config()
    message = str(excinfo.value)
    assert "GROQ_API_KEY_2" in message
    assert "fake-value" not in message  # never echo a key value


def test_all_eleven_accounts_are_grouped_in_provider_priority(monkeypatch):
    monkeypatch.setenv("PLACEMENT_HYBRID_LLM", "true")
    for index, name in enumerate(_ENV_KEYS, start=1):
        monkeypatch.setenv(name, f"fake-value-{index}")
    cfg = load_llm_config()
    assert cfg.enabled is True
    # pin the wiring itself, not just the derived account list
    assert LLM_ACCOUNT_SPECS == {
        "gemini": (4, "GEMINI_API_KEY_{n}"),
        "groq": (3, "GROQ_API_KEY_{n}"),
        "deepseek": (4, "DEEPSEEK_API_KEY_{n}"),
    }
    assert len(cfg.accounts) == len(_ENV_KEYS) == 11
    providers = [a.provider for a in cfg.accounts]
    assert providers == ["gemini"] * 4 + ["groq"] * 3 + ["deepseek"] * 4
    assert cfg.accounts[1].label == "gemini_2"
    assert cfg.accounts[3].label == "gemini_4"
    assert cfg.accounts[10].label == "deepseek_4"
    # keys are present but must never be rendered by __repr__-style logs
    assert all(a.key.startswith("fake-value") for a in cfg.accounts)
