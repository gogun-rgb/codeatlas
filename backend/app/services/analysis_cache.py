from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from app.models.graph import CodeGraph


class AnalysisCacheMissError(Exception):
    pass


class AnalysisCacheExpiredError(Exception):
    pass


@dataclass(frozen=True)
class AnalysisRecord:
    repository: str
    graph: CodeGraph
    expires_at: float


class AnalysisCache:
    def __init__(
        self,
        max_entries: int = 24,
        ttl_seconds: int = 30 * 60,
        now: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._now = now or time.time
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._records: OrderedDict[str, AnalysisRecord] = OrderedDict()

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def store(self, repository: str, graph: CodeGraph) -> str:
        self._prune_expired()
        analysis_id = self._next_unique_id()
        self._records[analysis_id] = AnalysisRecord(
            repository=repository,
            graph=graph,
            expires_at=self._now() + self._ttl_seconds,
        )
        self._enforce_bound()
        return analysis_id

    def get(self, analysis_id: str) -> AnalysisRecord:
        record = self._records.get(analysis_id)
        if record is None:
            raise AnalysisCacheMissError()
        if record.expires_at <= self._now():
            self._records.pop(analysis_id, None)
            raise AnalysisCacheExpiredError()
        self._records.move_to_end(analysis_id)
        return record

    def clear(self) -> None:
        self._records.clear()

    def _next_unique_id(self) -> str:
        for _ in range(10):
            analysis_id = self._id_factory()
            if analysis_id not in self._records:
                return analysis_id
        raise RuntimeError("Could not generate a unique analysis id")

    def _prune_expired(self) -> None:
        now = self._now()
        expired = [
            analysis_id
            for analysis_id, record in self._records.items()
            if record.expires_at <= now
        ]
        for analysis_id in expired:
            self._records.pop(analysis_id, None)

    def _enforce_bound(self) -> None:
        while len(self._records) > self._max_entries:
            self._records.popitem(last=False)
