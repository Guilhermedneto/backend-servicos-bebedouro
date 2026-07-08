from fastapi import APIRouter, Depends, Query

from app.application.commands.admin import (
    AdminDeleteReviewCommand,
    AdminDeleteReviewHandler,
    ApproveProviderCommand,
    ApproveProviderHandler,
    CreateCategoryCommand,
    CreateCategoryHandler,
    DeactivateProviderCommand,
    DeactivateProviderHandler,
    DeactivateUserCommand,
    DeactivateUserHandler,
    DeleteCategoryCommand,
    DeleteCategoryHandler,
    RemoveProviderCommand,
    RemoveProviderHandler,
    RemoveUserCommand,
    RemoveUserHandler,
    UpdateCategoryCommand,
    UpdateCategoryHandler,
)
from app.application.queries.admin import (
    GetDashboardHandler,
    ListAllCategoriesHandler,
    ListAllReviewsHandler,
    ListProvidersAdminHandler,
    ListProvidersAdminQuery,
    ListUsersHandler,
)
from app.presentation import deps
from app.presentation.schemas import CategoryCreateRequest, CategoryUpdateRequest

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(deps.require_admin)])


@router.get("/dashboard")
def dashboard(
    users=Depends(deps.get_user_repo),
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    return GetDashboardHandler(users, providers, reviews).handle()


@router.get("/users")
def list_users(users=Depends(deps.get_user_repo)):
    return ListUsersHandler(users).handle()


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, users=Depends(deps.get_user_repo)):
    DeactivateUserHandler(users).handle(DeactivateUserCommand(user_id=user_id))
    return {"id": user_id, "active": False}


@router.delete("/users/{user_id}", status_code=204)
def remove_user(
    user_id: str,
    users=Depends(deps.get_user_repo),
    reviews=Depends(deps.get_review_repo),
    providers=Depends(deps.get_provider_repo),
):
    RemoveUserHandler(users, reviews, providers).handle(RemoveUserCommand(user_id=user_id))


@router.get("/providers")
def list_providers(
    status: str | None = Query(default=None),
    providers=Depends(deps.get_provider_repo),
    users=Depends(deps.get_user_repo),
):
    return ListProvidersAdminHandler(providers, users).handle(ListProvidersAdminQuery(status=status))


@router.post("/providers/{provider_id}/approve")
def approve_provider(
    provider_id: str,
    providers=Depends(deps.get_provider_repo),
    users=Depends(deps.get_user_repo),
    email_service=Depends(deps.get_email_service),
):
    updated = ApproveProviderHandler(providers, users, email_service).handle(
        ApproveProviderCommand(provider_id=provider_id)
    )
    return {"id": updated["id"], "status": updated["status"]}


@router.post("/providers/{provider_id}/deactivate")
def deactivate_provider(provider_id: str, providers=Depends(deps.get_provider_repo)):
    updated = DeactivateProviderHandler(providers).handle(
        DeactivateProviderCommand(provider_id=provider_id)
    )
    return {"id": updated["id"], "status": updated["status"]}


@router.delete("/providers/{provider_id}", status_code=204)
def remove_provider(
    provider_id: str,
    providers=Depends(deps.get_provider_repo),
    users=Depends(deps.get_user_repo),
    reviews=Depends(deps.get_review_repo),
    storage=Depends(deps.get_photo_storage),
):
    RemoveProviderHandler(providers, users, reviews, storage).handle(
        RemoveProviderCommand(provider_id=provider_id)
    )


@router.get("/categories")
def list_categories(
    categories=Depends(deps.get_category_repo), providers=Depends(deps.get_provider_repo)
):
    return ListAllCategoriesHandler(categories, providers).handle()


@router.post("/categories", status_code=201)
def create_category(body: CategoryCreateRequest, categories=Depends(deps.get_category_repo)):
    created = CreateCategoryHandler(categories).handle(CreateCategoryCommand(name=body.name))
    return {"id": created["id"], "name": created["name"], "active": created["active"]}


@router.put("/categories/{category_id}")
def update_category(
    category_id: str,
    body: CategoryUpdateRequest,
    categories=Depends(deps.get_category_repo),
    providers=Depends(deps.get_provider_repo),
):
    updated = UpdateCategoryHandler(categories, providers).handle(
        UpdateCategoryCommand(category_id=category_id, name=body.name, active=body.active)
    )
    return {"id": updated["id"], "name": updated["name"], "active": updated["active"]}


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: str,
    categories=Depends(deps.get_category_repo),
    providers=Depends(deps.get_provider_repo),
):
    DeleteCategoryHandler(categories, providers).handle(DeleteCategoryCommand(category_id=category_id))


@router.get("/reviews")
def list_reviews(
    reviews=Depends(deps.get_review_repo), providers=Depends(deps.get_provider_repo)
):
    return ListAllReviewsHandler(reviews, providers).handle()


@router.delete("/reviews/{provider_id}/{review_id}", status_code=204)
def delete_review(
    provider_id: str,
    review_id: str,
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    AdminDeleteReviewHandler(providers, reviews).handle(
        AdminDeleteReviewCommand(review_id=review_id, provider_id=provider_id)
    )
