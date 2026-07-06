from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.graph import CodeGraph, GraphQuestionAnswer


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str


class AnalyzeResponse(BaseModel):
    analysis_id: str
    repository: str
    graph: CodeGraph


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    question: str
    use_ai: bool = False


class QuestionResponse(GraphQuestionAnswer):
    pass


class CapabilityResponse(BaseModel):
    ai_explanation_available: bool
