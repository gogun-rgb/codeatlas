from __future__ import annotations

from pydantic import BaseModel

from app.models.graph import CodeGraph, GraphQuestionAnswer


class AnalyzeRequest(BaseModel):
    repository: str


class AnalyzeResponse(BaseModel):
    repository: str
    graph: CodeGraph


class QuestionRequest(BaseModel):
    question: str
    graph: CodeGraph
    use_ai: bool = False


class QuestionResponse(GraphQuestionAnswer):
    pass


class CapabilityResponse(BaseModel):
    ai_explanation_available: bool
