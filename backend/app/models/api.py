from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.graph import CodeGraph, GraphQuestionAnswer

MAX_REPOSITORY_LENGTH = 200
MAX_ANALYSIS_ID_LENGTH = 64
MAX_QUESTION_LENGTH = 500


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REPOSITORY_LENGTH),
    ]


class AnalyzeResponse(BaseModel):
    analysis_id: str
    repository: str
    graph: CodeGraph


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_ANALYSIS_ID_LENGTH),
    ]
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH),
    ]
    use_ai: bool = False


class QuestionResponse(GraphQuestionAnswer):
    pass


class CapabilityResponse(BaseModel):
    ai_explanation_available: bool
