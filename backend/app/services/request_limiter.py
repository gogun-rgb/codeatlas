from __future__ import annotations

import os
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request


class RequestLimitExceededError(Exception):
    pass


@dataclass(frozen=True)
class LimiterConfig:
    analyze_requests: int = 10
    analyze_window_seconds: int = 10 * 60
    question_quota: int = 50
    ai_quota: int = 10
    max_tracked_analyses: int = 256
    trust_x_forwarded_for: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("analyze_requests", self.analyze_requests),
            ("analyze_window_seconds", self.analyze_window_seconds),
            ("question_quota", self.question_quota),
            ("ai_quota", self.ai_quota),
            ("max_tracked_analyses", self.max_tracked_analyses),
        ):
            if value < 1:
                raise ValueError(f"{name} must be a positive integer")

    @classmethod
    def from_environment(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
    ) -> LimiterConfig:
        return cls(
            analyze_requests=_positive_int_from_env(
                "CODEATLAS_ANALYZE_RATE_LIMIT",
                cls.analyze_requests,
                getenv,
            ),
            analyze_window_seconds=_positive_int_from_env(
                "CODEATLAS_ANALYZE_RATE_WINDOW_SECONDS",
                cls.analyze_window_seconds,
                getenv,
            ),
            question_quota=_positive_int_from_env(
                "CODEATLAS_QUESTION_QUOTA",
                cls.question_quota,
                getenv,
            ),
            ai_quota=_positive_int_from_env(
                "CODEATLAS_AI_QUOTA",
                cls.ai_quota,
                getenv,
            ),
            max_tracked_analyses=_positive_int_from_env(
                "CODEATLAS_LIMITER_MAX_TRACKED_ANALYSES",
                cls.max_tracked_analyses,
                getenv,
            ),
            trust_x_forwarded_for=_bool_from_env(
                "CODEATLAS_TRUST_X_FORWARDED_FOR",
                cls.trust_x_forwarded_for,
                getenv,
            ),
        )


class RequestLimiter:
    def __init__(
        self,
        config: LimiterConfig | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._config = config or LimiterConfig.from_environment()
        self._now = now or time.time
        self._analyze_windows: dict[str, deque[float]] = {}
        self._question_counts: OrderedDict[str, int] = OrderedDict()
        self._ai_counts: OrderedDict[str, int] = OrderedDict()

    @classmethod
    def from_environment(cls) -> RequestLimiter:
        return cls(config=LimiterConfig.from_environment())

    @property
    def config(self) -> LimiterConfig:
        return self._config

    @property
    def tracked_analyze_clients(self) -> int:
        return len(self._analyze_windows)

    @property
    def tracked_question_analyses(self) -> int:
        return len(self._question_counts)

    def check_analyze(self, client_key: str) -> None:
        now = self._now()
        self._prune_analyze(now)
        window = self._analyze_windows.setdefault(client_key, deque())
        cutoff = now - self._config.analyze_window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= self._config.analyze_requests:
            raise RequestLimitExceededError()
        window.append(now)

    def check_question(self, analysis_id: str) -> None:
        self._increment_analysis_count(
            self._question_counts,
            analysis_id,
            self._config.question_quota,
        )

    def check_ai(self, analysis_id: str) -> None:
        self._increment_analysis_count(self._ai_counts, analysis_id, self._config.ai_quota)

    def _increment_analysis_count(
        self,
        counts: OrderedDict[str, int],
        analysis_id: str,
        limit: int,
    ) -> None:
        current = counts.get(analysis_id, 0)
        if current >= limit:
            raise RequestLimitExceededError()
        if analysis_id not in counts and len(counts) >= self._config.max_tracked_analyses:
            counts.popitem(last=False)
        counts[analysis_id] = current + 1
        counts.move_to_end(analysis_id)

    def _prune_analyze(self, now: float) -> None:
        cutoff = now - self._config.analyze_window_seconds
        empty_keys: list[str] = []
        for key, window in self._analyze_windows.items():
            while window and window[0] <= cutoff:
                window.popleft()
            if not window:
                empty_keys.append(key)
        for key in empty_keys:
            self._analyze_windows.pop(key, None)


def client_key_from_request(request: Request, config: LimiterConfig) -> str:
    if config.trust_x_forwarded_for:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        first_forwarded = next(
            (part.strip() for part in forwarded_for.split(",") if part.strip()),
            "",
        )
        if first_forwarded:
            return f"xff:{first_forwarded}"
    if request.client and request.client.host:
        return f"client:{request.client.host}"
    return "client:unknown"


def _positive_int_from_env(
    name: str,
    default: int,
    getenv: Callable[[str], str | None],
) -> int:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _bool_from_env(
    name: str,
    default: bool,
    getenv: Callable[[str], str | None],
) -> bool:
    raw = getenv(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")
