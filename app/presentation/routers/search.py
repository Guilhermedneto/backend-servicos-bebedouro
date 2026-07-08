from fastapi import APIRouter, Depends

from app.application.queries.ai_search import AiSearchHandler, AiSearchQuery
from app.presentation import deps
from app.presentation.schemas import AiSearchRequest

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/ai")
def ai_search(body: AiSearchRequest, service=Depends(deps.get_ai_search_service)):
    return AiSearchHandler(service).handle(AiSearchQuery(question=body.question))
