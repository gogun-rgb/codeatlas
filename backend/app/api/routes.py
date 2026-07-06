from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.fixtures.demo import demo_graph
from app.graph.search import GraphSearch
from app.models.api import AnalyzeRequest, AnalyzeResponse, CapabilityResponse, QuestionRequest
from app.repositories.errors import RepositoryError
from app.services.ai import AIExplanationService, OpenAIResponsesClient
from app.services.analyzer import CodebaseAnalyzer

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/capabilities", response_model=CapabilityResponse)
async def capabilities() -> CapabilityResponse:
    client = OpenAIResponsesClient.from_environment()
    return CapabilityResponse(ai_explanation_available=client is not None)


@router.get("/demo", response_model=AnalyzeResponse)
async def demo() -> AnalyzeResponse:
    repository, graph = demo_graph()
    return AnalyzeResponse(repository=repository, graph=graph)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    analyzer = CodebaseAnalyzer()
    try:
        repository, graph = await analyzer.analyze_repository(request.repository)
    except RepositoryError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc
    return AnalyzeResponse(repository=repository, graph=graph)


@router.post("/question")
async def question(request: QuestionRequest) -> object:
    search = GraphSearch()
    answer = search.answer(request.graph, request.question)
    if not request.use_ai:
        return answer
    ai_service = AIExplanationService(client=OpenAIResponsesClient.from_environment())
    return await ai_service.explain(answer, request.graph)
