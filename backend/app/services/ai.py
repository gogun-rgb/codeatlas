from __future__ import annotations

import json
import os
from typing import Protocol

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from app.models.graph import CodeGraph, GraphQuestionAnswer, SearchCandidate


class AIReference(BaseModel):
    path: str
    symbol: str | None = None
    reason: str


class AIExplanation(BaseModel):
    summary: str = Field(min_length=1)
    references: list[AIReference] = Field(default_factory=list)


class AIClient(Protocol):
    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        pass


class AIExplanationService:
    def __init__(self, client: AIClient | None = None) -> None:
        self._client = client

    async def explain(
        self,
        answer: GraphQuestionAnswer,
        graph: CodeGraph,
    ) -> GraphQuestionAnswer:
        if self._client is None:
            return answer.model_copy(update={"ai_status": "disabled"})
        try:
            explanation = await self._client.create_explanation(
                answer.question,
                answer.candidates,
                graph,
            )
        except (OpenAIError, RuntimeError, ValidationError, json.JSONDecodeError):
            return answer.model_copy(update={"ai_status": "unavailable"})

        validated = validate_ai_explanation(graph, explanation)
        if validated is None:
            return answer.model_copy(update={"ai_status": "validation_failed"})
        return answer.model_copy(
            update={
                "ai_status": "generated",
                "ai_explanation": validated.summary,
                "ai_references": [reference.model_dump() for reference in validated.references],
            }
        )


class OpenAIResponsesClient:
    def __init__(self, api_key: str, model: str = "gpt-5.5") -> None:
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_environment(cls) -> OpenAIResponsesClient | None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key)

    async def create_explanation(
        self,
        question: str,
        candidates: list[SearchCandidate],
        graph: CodeGraph,
    ) -> AIExplanation:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)
        context = build_candidate_context(candidates, graph)
        response = await client.responses.create(
            model=self._model,
            store=False,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Explain code graph search results for a beginner. "
                        "Use only the provided graph context. Do not invent paths or symbols. "
                        "Mention a file path or symbol name only when it appears in your "
                        "structured references."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "candidate_context": context},
                        separators=(",", ":"),
                    ),
                },
            ],
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "codeatlas_explanation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["summary", "references"],
                        "properties": {
                            "summary": {"type": "string"},
                            "references": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["path", "symbol", "reason"],
                                    "properties": {
                                        "path": {"type": "string"},
                                        "symbol": {"type": ["string", "null"]},
                                        "reason": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
            reasoning={"effort": "low"},
        )
        output_text = response.output_text
        return AIExplanation.model_validate_json(output_text)


def build_candidate_context(
    candidates: list[SearchCandidate],
    graph: CodeGraph,
) -> list[dict[str, object]]:
    by_path: dict[str, list[str]] = {}
    for node in graph.nodes:
        if node.type in {"FUNCTION", "CLASS"}:
            by_path.setdefault(node.path, []).append(node.label)

    context: list[dict[str, object]] = []
    for candidate in candidates[:6]:
        node = candidate.node
        context.append(
            {
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "path": node.path,
                "score": candidate.score,
                "reasons": candidate.reasons,
                "symbols_in_file": sorted(by_path.get(node.path, [])),
                "metadata": {
                    key: value
                    for key, value in node.metadata.items()
                    if key
                    in {
                        "startLine",
                        "endLine",
                        "language",
                        "imports",
                        "exports",
                        "externalImports",
                        "unresolvedLocalImports",
                        "importedBy",
                    }
                },
            }
        )
    return context


def validate_ai_explanation(graph: CodeGraph, explanation: AIExplanation) -> AIExplanation | None:
    paths = {node.path for node in graph.nodes}
    symbols_by_path: dict[str, set[str]] = {}
    for node in graph.nodes:
        if node.type in {"FUNCTION", "CLASS"}:
            symbols_by_path.setdefault(node.path, set()).add(node.label)

    valid_references: list[AIReference] = []
    for reference in explanation.references:
        if reference.path not in paths:
            return None
        if reference.symbol and reference.symbol not in symbols_by_path.get(reference.path, set()):
            return None
        valid_references.append(reference)
    return explanation.model_copy(update={"references": valid_references})
