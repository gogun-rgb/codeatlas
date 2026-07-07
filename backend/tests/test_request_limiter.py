from __future__ import annotations

import pytest
from fastapi import Request

from app.services.request_limiter import (
    LimiterConfig,
    RequestLimiter,
    RequestLimitExceededError,
    client_key_from_request,
)


def test_analyze_requests_inside_limit_pass_and_next_fails() -> None:
    limiter = RequestLimiter(
        LimiterConfig(analyze_requests=2, analyze_window_seconds=60),
        now=lambda: 100.0,
    )

    limiter.check_analyze("client:a")
    limiter.check_analyze("client:a")

    with pytest.raises(RequestLimitExceededError):
        limiter.check_analyze("client:a")


def test_analyze_window_expiration_restores_access() -> None:
    now = 100.0
    limiter = RequestLimiter(
        LimiterConfig(analyze_requests=1, analyze_window_seconds=60),
        now=lambda: now,
    )

    limiter.check_analyze("client:a")
    now = 161.0
    limiter.check_analyze("client:a")

    assert limiter.tracked_analyze_clients == 1


def test_independent_client_keys_do_not_share_analyze_quota() -> None:
    limiter = RequestLimiter(
        LimiterConfig(analyze_requests=1, analyze_window_seconds=60),
        now=lambda: 100.0,
    )

    limiter.check_analyze("client:a")
    limiter.check_analyze("client:b")

    with pytest.raises(RequestLimitExceededError):
        limiter.check_analyze("client:a")


def test_independent_analysis_ids_do_not_share_question_quota() -> None:
    limiter = RequestLimiter(LimiterConfig(question_quota=1))

    limiter.check_question("analysis-a")
    limiter.check_question("analysis-b")

    with pytest.raises(RequestLimitExceededError):
        limiter.check_question("analysis-a")


def test_question_quota_is_deterministic() -> None:
    limiter = RequestLimiter(LimiterConfig(question_quota=2))

    limiter.check_question("analysis-a")
    limiter.check_question("analysis-a")

    with pytest.raises(RequestLimitExceededError):
        limiter.check_question("analysis-a")


def test_ai_quota_is_stricter_than_question_quota() -> None:
    limiter = RequestLimiter(LimiterConfig(question_quota=3, ai_quota=1))

    limiter.check_question("analysis-a")
    limiter.check_ai("analysis-a")
    limiter.check_question("analysis-a")

    with pytest.raises(RequestLimitExceededError):
        limiter.check_ai("analysis-a")


def test_invalid_configuration_fails_safely() -> None:
    with pytest.raises(ValueError):
        LimiterConfig(analyze_requests=0)
    with pytest.raises(ValueError):
        LimiterConfig.from_environment(lambda name: "0" if name == "CODEATLAS_AI_QUOTA" else None)
    with pytest.raises(ValueError):
        LimiterConfig.from_environment(
            lambda name: "sometimes" if name == "CODEATLAS_TRUST_X_FORWARDED_FOR" else None
        )


def test_stale_analyze_windows_are_pruned() -> None:
    now = 100.0
    limiter = RequestLimiter(
        LimiterConfig(analyze_requests=1, analyze_window_seconds=60),
        now=lambda: now,
    )
    limiter.check_analyze("client:a")

    now = 161.0
    limiter.check_analyze("client:b")

    assert limiter.tracked_analyze_clients == 1


def test_analysis_quota_tracking_is_bounded() -> None:
    limiter = RequestLimiter(LimiterConfig(max_tracked_analyses=2))

    limiter.check_question("analysis-a")
    limiter.check_question("analysis-b")
    limiter.check_question("analysis-c")

    assert limiter.tracked_question_analyses == 2


def test_client_key_ignores_forwarded_for_by_default() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/analyze",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
            "client": ("127.0.0.1", 12345),
        }
    )

    assert client_key_from_request(request, LimiterConfig()) == "client:127.0.0.1"


def test_client_key_uses_forwarded_for_only_when_configured() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/analyze",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
            "client": ("127.0.0.1", 12345),
        }
    )

    assert (
        client_key_from_request(request, LimiterConfig(trust_x_forwarded_for=True))
        == "xff:203.0.113.10"
    )
