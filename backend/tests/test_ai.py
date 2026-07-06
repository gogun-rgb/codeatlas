from __future__ import annotations

from app.graph.builder import GraphBuilder
from app.graph.search import GraphSearch
from app.models.graph import CodeGraph, SearchCandidate
from app.models.repository import Language, SourceFile
from app.parsing.registry import ParserRegistry
from app.services.ai import AIExplanation, AIExplanationService, AIReference


class FakeAIClient:
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
                AIReference(path="src/ghost.ts", symbol=None, reason="invalid path"),
                AIReference(path="src/scoring.ts", symbol="madeUp", reason="invalid symbol"),
            ],
        )


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


async def test_ai_service_post_validates_paths_and_symbols() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=FakeAIClient()).explain(answer, graph)

    assert enriched.ai_status == "generated"
    assert (
        enriched.ai_explanation
        == "Start with calculateScore because it is the scoring entry point."
    )
    assert enriched.ai_references == [
        {"path": "src/scoring.ts", "symbol": "calculateScore", "reason": "valid"}
    ]


async def test_ai_service_is_disabled_without_client() -> None:
    graph = make_graph()
    answer = GraphSearch().answer(graph, "Where is scoring?")

    enriched = await AIExplanationService(client=None).explain(answer, graph)

    assert enriched.ai_status == "disabled"
    assert enriched.ai_explanation is None
