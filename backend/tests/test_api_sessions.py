from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import create_app
from app.models.graph import CodeGraph, GraphNode, NodeType
from app.services.ai import AIExplanation, AIReference
from app.services.analysis_cache import (
    AnalysisCache,
    AnalysisCacheExpiredError,
    AnalysisCacheMissError,
)
from app.services.request_limiter import LimiterConfig, RequestLimiter


@pytest.fixture(autouse=True)
def isolated_analysis_cache() -> object:
    original_cache = routes.analysis_cache
    original_limiter = routes.request_limiter
    routes.analysis_cache = AnalysisCache(max_entries=8, ttl_seconds=60)
    routes.request_limiter = RequestLimiter()
    try:
        yield
    finally:
        routes.analysis_cache = original_cache
        routes.request_limiter = original_limiter


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


def test_questions_work_with_server_issued_analysis_id() -> None:
    client = TestClient(create_app())
    demo_response = client.get("/api/demo")
    assert demo_response.status_code == 200
    analysis_id = demo_response.json()["analysis_id"]

    response = client.post(
        "/api/question",
        json={
            "analysis_id": analysis_id,
            "question": "Where is scoring?",
            "use_ai": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deterministic_answer"].startswith("Suggested starting point")
    assert payload["candidates"]


def test_unknown_analysis_ids_are_rejected() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/question",
        json={
            "analysis_id": "unknown-analysis-id",
            "question": "Where is scoring?",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Analysis not found. Re-run repository analysis before asking questions."
    )


def test_expired_analysis_ids_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 100.0

    def clock() -> float:
        return now

    monkeypatch.setattr(
        routes,
        "analysis_cache",
        AnalysisCache(
            max_entries=8,
            ttl_seconds=1,
            now=clock,
            id_factory=lambda: "expires-soon",
        ),
    )
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]
    now = 102.0

    response = client.post(
        "/api/question",
        json={
            "analysis_id": analysis_id,
            "question": "Where is scoring?",
        },
    )

    assert response.status_code == 410
    assert response.json()["detail"] == (
        "Analysis expired. Re-run repository analysis before asking questions."
    )


def test_question_endpoint_rejects_client_controlled_graph_payload() -> None:
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]

    response = client.post(
        "/api/question",
        json={
            "analysis_id": analysis_id,
            "question": "Where is scoring?",
            "graph": _graph("src/tampered.ts").model_dump(mode="json"),
        },
    )

    assert response.status_code == 422


def test_question_quota_returns_429_after_analysis_exists() -> None:
    routes.request_limiter = RequestLimiter(LimiterConfig(question_quota=1))
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]

    first = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?"},
    )
    second = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == (
        "Question quota exceeded for this analysis. Re-run analysis to continue."
    )


class CountingAIClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create_explanation(self, question, candidates, graph) -> AIExplanation:
        self.calls += 1
        return AIExplanation(
            summary="Start with calculateScore.",
            references=[
                AIReference(path="src/lib/scoring.ts", symbol="calculateScore", reason="valid"),
            ],
        )


def test_ai_quota_exhaustion_never_invokes_ai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    routes.request_limiter = RequestLimiter(LimiterConfig(question_quota=5, ai_quota=1))
    ai_client = CountingAIClient()
    monkeypatch.setattr(
        routes.OpenAIResponsesClient,
        "from_environment",
        staticmethod(lambda: ai_client),
    )
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]

    first = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?", "use_ai": True},
    )
    second = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?", "use_ai": True},
    )

    assert first.status_code == 200
    assert first.json()["ai_status"] == "generated"
    assert second.status_code == 200
    assert second.json()["ai_status"] == "quota_exhausted"
    assert second.json()["deterministic_answer"]
    assert ai_client.calls == 1


def test_ai_quota_is_not_consumed_when_ai_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes.request_limiter = RequestLimiter(LimiterConfig(question_quota=3, ai_quota=1))
    monkeypatch.setattr(
        routes.OpenAIResponsesClient,
        "from_environment",
        staticmethod(lambda: None),
    )
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]

    first = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?", "use_ai": True},
    )
    second = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?", "use_ai": True},
    )

    assert first.status_code == 200
    assert first.json()["ai_status"] == "disabled"
    assert second.status_code == 200
    assert second.json()["ai_status"] == "disabled"


def test_repeated_questions_reuse_same_stored_analysis() -> None:
    client = TestClient(create_app())
    analysis_id = client.get("/api/demo").json()["analysis_id"]

    first = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?"},
    ).json()
    second = client.post(
        "/api/question",
        json={"analysis_id": analysis_id, "question": "Where is scoring?"},
    ).json()

    assert [item["node"]["id"] for item in first["candidates"]] == [
        item["node"]["id"] for item in second["candidates"]
    ]
    assert first["deterministic_answer"] == second["deterministic_answer"]


def test_analysis_cache_bounds_and_expiration_are_enforced() -> None:
    now = 10.0
    ids = iter(["one", "two", "three"])
    cache = AnalysisCache(
        max_entries=2,
        ttl_seconds=5,
        now=lambda: now,
        id_factory=lambda: next(ids),
    )

    first = cache.store("demo/one", _graph("one.ts"))
    second = cache.store("demo/two", _graph("two.ts"))
    third = cache.store("demo/three", _graph("three.ts"))

    assert (first, second, third) == ("one", "two", "three")
    with pytest.raises(AnalysisCacheMissError):
        cache.get(first)
    assert cache.get(second).repository == "demo/two"
    assert cache.get(third).repository == "demo/three"

    now = 16.0
    with pytest.raises(AnalysisCacheExpiredError):
        cache.get(second)


def test_server_analysis_state_does_not_leak_environment_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "unit-test-github-placeholder")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-openai-placeholder")
    client = TestClient(create_app())
    demo_payload = client.get("/api/demo").json()

    response = client.post(
        "/api/question",
        json={
            "analysis_id": demo_payload["analysis_id"],
            "question": "Where is scoring?",
            "use_ai": False,
        },
    )

    assert response.status_code == 200
    serialized = response.text + str(demo_payload)
    assert "unit-test-github-placeholder" not in serialized
    assert "unit-test-openai-placeholder" not in serialized
