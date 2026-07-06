from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.fixtures.demo import demo_graph
from app.graph.search import GraphSearch
from app.models.api import AnalyzeRequest, AnalyzeResponse, CapabilityResponse, QuestionRequest
from app.repositories.errors import RepositoryError
from app.services.ai import AIExplanationService, OpenAIResponsesClient
from app.services.analysis_cache import (
    AnalysisCache,
    AnalysisCacheExpiredError,
    AnalysisCacheMissError,
)
from app.services.analyzer import CodebaseAnalyzer

router = APIRouter(prefix="/api")
analysis_cache = AnalysisCache()


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
    analysis_id = analysis_cache.store(repository, graph)
    return AnalyzeResponse(analysis_id=analysis_id, repository=repository, graph=graph)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    analyzer = CodebaseAnalyzer()
    try:
        repository, graph = await analyzer.analyze_repository(request.repository)
    except RepositoryError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc
    analysis_id = analysis_cache.store(repository, graph)
    return AnalyzeResponse(analysis_id=analysis_id, repository=repository, graph=graph)


@router.post("/question")
async def question(request: QuestionRequest) -> object:
    try:
        record = analysis_cache.get(request.analysis_id)
    except AnalysisCacheExpiredError as exc:
        raise HTTPException(
            status_code=410,
            detail="Analysis expired. Re-run repository analysis before asking questions.",
        ) from exc
    except AnalysisCacheMissError as exc:
        raise HTTPException(
            status_code=404,
            detail="Analysis not found. Re-run repository analysis before asking questions.",
        ) from exc

    search = GraphSearch()
    answer = search.answer(record.graph, request.question)
    if not request.use_ai:
        return answer
    ai_service = AIExplanationService(client=OpenAIResponsesClient.from_environment())
    return await ai_service.explain(answer, record.graph)
