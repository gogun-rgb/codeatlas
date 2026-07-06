from __future__ import annotations

from app.graph.builder import GraphBuilder
from app.graph.search import GraphSearch
from app.models.graph import CodeGraph, SearchCandidate
from app.models.repository import Language, SourceFile
from app.parsing.registry import ParserRegistry
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


def make_graph() -> CodeGraph:
    parsed = ParserRegistry().parse_files(
        [
            SourceFile(
                path="src/scoring.ts",
                language=Language.TYPESCRIPT,
                size=80,
                content="export function calculateScore() { return 1; }\n",
            )
        ]
    )
    return GraphBuilder().build(parsed)


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


async def test_ai_service_is_disabled_without_client() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=None).explain(answer, graph)

    assert enriched.ai_status == "disabled"
    assert enriched.ai_explanation is None
    assert enriched.deterministic_answer == answer.deterministic_answer
