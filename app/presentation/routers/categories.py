from fastapi import APIRouter, Depends

from app.application.queries.categories import ListActiveCategoriesHandler
from app.presentation import deps

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def list_categories(categories=Depends(deps.get_category_repo)):
    return ListActiveCategoriesHandler(categories).handle()
