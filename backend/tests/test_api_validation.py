from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import create_app
from app.models.api import MAX_QUESTION_LENGTH, MAX_REPOSITORY_LENGTH
from app.models.graph import CodeGraph, GraphNode, NodeType
from app.services.analysis_cache import AnalysisCache
from app.services.request_limiter import LimiterConfig, RequestLimiter


class FakeAnalyzer:
    seen_repository: str | None = None

    async def analyze_repository(self, repository: str) -> tuple[str, CodeGraph]:
        self.__class__.seen_repository = repository
        return repository, _graph("src/app.ts")


def _graph(path: str) -> CodeGraph:
    return CodeGraph(
        nodes=[
            GraphNode(
                id=f"file:{path}",
                type=NodeType.FILE,
                label=path.rsplit("/", 1)[-1],
                path=path,
                metadata={},
            )
        ],
        edges=[],
    )


def test_analyze_strips_repository_whitespace(monkeypatch) -> None:
    original_cache = routes.analysis_cache
    original_limiter = routes.request_limiter
    monkeypatch.setattr(routes, "analysis_cache", AnalysisCache(max_entries=8, ttl_seconds=60))
    monkeypatch.setattr(routes, "request_limiter", RequestLimiter())
    monkeypatch.setattr(routes, "CodebaseAnalyzer", FakeAnalyzer)
    try:
        client = TestClient(create_app())
        response = client.post("/api/analyze", json={"repository": "  demo/repo  "})
    finally:
        routes.analysis_cache = original_cache
        routes.request_limiter = original_limiter

    assert response.status_code == 200
    assert FakeAnalyzer.seen_repository == "demo/repo"
    assert response.json()["repository"] == "demo/repo"


def test_empty_repository_after_whitespace_normalization_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post("/api/analyze", json={"repository": "   "})

    assert response.status_code == 422


def test_repository_over_max_length_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post("/api/analyze", json={"repository": "x" * (MAX_REPOSITORY_LENGTH + 1)})

    assert response.status_code == 422


def test_empty_analysis_id_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/question",
        json={"analysis_id": "   ", "question": "Where is scoring?"},
    )

    assert response.status_code == 422


def test_empty_question_after_whitespace_normalization_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/question",
        json={"analysis_id": "analysis-123", "question": "   "},
    )

    assert response.status_code == 422


def test_question_exactly_at_max_length_is_accepted(monkeypatch) -> None:
    original_cache = routes.analysis_cache
    original_limiter = routes.request_limiter
    monkeypatch.setattr(routes, "analysis_cache", AnalysisCache(max_entries=8, ttl_seconds=60))
    monkeypatch.setattr(routes, "request_limiter", RequestLimiter())
    try:
        client = TestClient(create_app())
        analysis_id = client.get("/api/demo").json()["analysis_id"]
        response = client.post(
            "/api/question",
            json={"analysis_id": analysis_id, "question": "x" * MAX_QUESTION_LENGTH},
        )
    finally:
        routes.analysis_cache = original_cache
        routes.request_limiter = original_limiter

    assert response.status_code == 200


def test_question_over_max_length_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/question",
        json={"analysis_id": "analysis-123", "question": "x" * (MAX_QUESTION_LENGTH + 1)},
    )

    assert response.status_code == 422


def test_extra_fields_are_rejected() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/question",
        json={
            "analysis_id": "analysis-123",
            "question": "Where is scoring?",
            "graph": {"nodes": [], "edges": []},
        },
    )

    assert response.status_code == 422


def test_analyze_rate_limit_returns_429(monkeypatch) -> None:
    original_cache = routes.analysis_cache
    original_limiter = routes.request_limiter
    monkeypatch.setattr(routes, "analysis_cache", AnalysisCache(max_entries=8, ttl_seconds=60))
    monkeypatch.setattr(
        routes,
        "request_limiter",
        RequestLimiter(LimiterConfig(analyze_requests=1, analyze_window_seconds=600)),
    )
    monkeypatch.setattr(routes, "CodebaseAnalyzer", FakeAnalyzer)
    try:
        client = TestClient(create_app())
        first = client.post("/api/analyze", json={"repository": "demo/repo"})
        second = client.post("/api/analyze", json={"repository": "demo/repo"})
    finally:
        routes.analysis_cache = original_cache
        routes.request_limiter = original_limiter

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "Analyze rate limit exceeded. Try again later."
