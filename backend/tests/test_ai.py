from __future__ import annotations

import httpx
from openai import APIConnectionError

from app.graph.search import GraphSearch
from app.models.graph import CodeGraph, GraphNode, NodeType, SearchCandidate
from app.services.ai import AIExplanation, AIExplanationService, AIReference


class ValidAIClient:
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        return AIExplanation(
            summary="Start with calculateScore because it is the scoring entry point.",
            references=[
                AIReference(path="src/scoring.ts", symbol="calculateScore", reason="valid"),
            ],
        )


class InvalidPathAIClient:
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        return AIExplanation(
            summary="A made-up path is involved.",
            references=[AIReference(path="src/ghost.ts", symbol=None, reason="invalid path")],
        )


class InvalidSymbolAIClient:
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        return AIExplanation(
            summary="A made-up symbol is involved.",
            references=[
                AIReference(path="src/scoring.ts", symbol="madeUp", reason="invalid symbol")
            ],
        )


class FailingAIClient:
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        raise RuntimeError("AI client failed")


class OpenAIConnectionFailureClient:
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        raise APIConnectionError(
            request=httpx.Request("POST", "https://api.openai.test/v1/responses")
        )


def make_graph() -> CodeGraph:
    return CodeGraph(
        nodes=[
            GraphNode(
                id="file:src/scoring.ts",
                type=NodeType.FILE,
                label="scoring.ts",
                path="src/scoring.ts",
                metadata={"exports": ["calculateScore"]},
            ),
            GraphNode(
                id="function:src/scoring.ts:<module>:calculateScore:1:0:10",
                type=NodeType.FUNCTION,
                label="calculateScore",
                path="src/scoring.ts",
                metadata={"startLine": 1, "exported": True},
            ),
        ],
        edges=[],
    )


async def test_ai_service_accepts_valid_explanation() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=ValidAIClient()).explain(answer, graph)

    assert enriched.ai_status == "generated"
    assert (
        enriched.ai_explanation
        == "Start with calculateScore because it is the scoring entry point."
    )
    assert enriched.ai_references == [
        {"path": "src/scoring.ts", "symbol": "calculateScore", "reason": "valid"}
    ]
    assert enriched.deterministic_answer == answer.deterministic_answer


async def test_ai_service_discards_explanation_with_invalid_path_reference() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=InvalidPathAIClient()).explain(answer, graph)

    assert enriched.ai_status == "validation_failed"
    assert enriched.ai_explanation is None
    assert enriched.ai_references == []
    assert enriched.deterministic_answer == answer.deterministic_answer


async def test_ai_service_discards_explanation_with_invalid_symbol_reference() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=InvalidSymbolAIClient()).explain(answer, graph)

    assert enriched.ai_status == "validation_failed"
    assert enriched.ai_explanation is None
    assert enriched.ai_references == []
    assert enriched.deterministic_answer == answer.deterministic_answer


async def test_ai_client_failure_keeps_deterministic_answer() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=FailingAIClient()).explain(answer, graph)

    assert enriched.ai_status == "unavailable"
    assert enriched.ai_explanation is None
    assert enriched.deterministic_answer == answer.deterministic_answer


async def test_openai_sdk_exception_keeps_deterministic_answer_without_live_request() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=OpenAIConnectionFailureClient()).explain(
        answer,
        graph,
    )

    assert enriched.ai_status == "unavailable"
    assert enriched.ai_explanation is None
    assert enriched.ai_references == []
    assert enriched.deterministic_answer == answer.deterministic_answer


async def test_ai_service_is_disabled_without_client() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=None).explain(answer, graph)

    assert enriched.ai_status == "disabled"
    assert enriched.ai_explanation is None
    assert enriched.deterministic_answer == answer.deterministic_answer
