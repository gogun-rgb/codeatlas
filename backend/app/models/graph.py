from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeType(StrEnum):
    FILE = "FILE"
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"


class EdgeType(StrEnum):
    IMPORTS = "IMPORTS"
    CONTAINS = "CONTAINS"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"


class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: EdgeType
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeGraph(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchCandidate(BaseModel):
    node: GraphNode
    score: float
    reasons: list[str] = Field(default_factory=list)


class GraphQuestionAnswer(BaseModel):
    question: str
    candidates: list[SearchCandidate]
    deterministic_answer: str
    ai_status: str = "disabled"
    ai_explanation: str | None = None
    ai_references: list[dict[str, str]] = Field(default_factory=list)
