from fastapi import APIRouter, Depends, Query, UploadFile

from app.application.commands.providers import (
    DeletePhotoCommand,
    DeletePhotoHandler,
    SetCoverPhotoCommand,
    SetCoverPhotoHandler,
    TrackWhatsappClickCommand,
    TrackWhatsappClickHandler,
    UpdateProviderProfileCommand,
    UpdateProviderProfileHandler,
    UploadPhotoCommand,
    UploadPhotoHandler,
)
from app.application.commands.reviews import (
    CreateReviewCommand,
    CreateReviewHandler,
    DeleteOwnReviewCommand,
    DeleteOwnReviewHandler,
    UpdateReviewCommand,
    UpdateReviewHandler,
)
from app.application.commands.subscriptions import (
    CancelSubscriptionCommand,
    CancelSubscriptionHandler,
    ChangePlanCommand,
    ChangePlanHandler,
    StartCheckoutCommand,
    StartCheckoutHandler,
)
from app.application.queries.providers import (
    GetMyProviderHandler,
    GetMyProviderQuery,
    GetPublicProviderHandler,
    GetPublicProviderQuery,
    ListFeaturedHandler,
    ListProvidersHandler,
    ListProvidersQuery,
)
from app.application.queries.reviews import (
    GetMyReviewHandler,
    GetMyReviewQuery,
    ListProviderReviewsHandler,
    ListProviderReviewsQuery,
)
from app.core.config import get_settings
from app.presentation import deps
from app.presentation.schemas import ChangePlanRequest, ReviewRequest, UpdateProviderRequest

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
def list_providers(
    search: str | None = Query(default=None, max_length=100),
    categoryId: str | None = Query(default=None),
    sort: str = Query(default="recent"),
    page: int = Query(default=1, ge=1),
    providers=Depends(deps.get_provider_repo),
):
    return ListProvidersHandler(providers).handle(
        ListProvidersQuery(
            search=search,
            category_id=categoryId,
            sort=sort,
            page=page,
            page_size=get_settings().page_size,
        )
    )


@router.get("/featured")
def list_featured(providers=Depends(deps.get_provider_repo)):
    return ListFeaturedHandler(providers).handle()


@router.put("/me/plan")
def change_my_plan(
    body: ChangePlanRequest,
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    storage=Depends(deps.get_photo_storage),
    stripe=Depends(deps.get_stripe_service),
):
    return ChangePlanHandler(providers, storage, stripe).handle(
        ChangePlanCommand(
            provider_id=user["providerId"],
            email=user["email"],
            plan=body.plan,
            billing_cycle=body.billingCycle,
        )
    )


@router.post("/me/subscription/cancel")
def cancel_my_subscription(
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    stripe=Depends(deps.get_stripe_service),
    email_service=Depends(deps.get_email_service),
):
    return CancelSubscriptionHandler(providers, stripe, email_service).handle(
        CancelSubscriptionCommand(provider_id=user["providerId"], email=user["email"])
    )


@router.post("/me/checkout")
def start_my_checkout(
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    stripe=Depends(deps.get_stripe_service),
):
    return StartCheckoutHandler(providers, stripe).handle(
        StartCheckoutCommand(provider_id=user["providerId"], email=user["email"])
    )


@router.get("/me")
def get_my_provider(
    user=Depends(deps.require_provider), providers=Depends(deps.get_provider_repo)
):
    return GetMyProviderHandler(providers).handle(GetMyProviderQuery(user_id=user["id"]))


@router.put("/me")
def update_my_provider(
    body: UpdateProviderRequest,
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    categories=Depends(deps.get_category_repo),
    geocoder=Depends(deps.get_geocoder),
):
    UpdateProviderProfileHandler(providers, categories, geocoder).handle(
        UpdateProviderProfileCommand(
            provider_id=user["providerId"],
            name=body.name,
            category_ids=body.categoryIds,
            bairro=body.bairro,
            rua=body.rua,
            numero=body.numero,
            whatsapp=body.whatsapp,
            description=body.description,
        )
    )
    return GetMyProviderHandler(providers).handle(GetMyProviderQuery(user_id=user["id"]))


@router.post("/me/photos", status_code=201)
def upload_photo(
    file: UploadFile,
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    storage=Depends(deps.get_photo_storage),
):
    data = file.file.read()
    return UploadPhotoHandler(providers, storage).handle(
        UploadPhotoCommand(
            provider_id=user["providerId"],
            content_type=file.content_type or "",
            data=data,
        )
    )


@router.delete("/me/photos/{photo_id}", status_code=204)
def delete_photo(
    photo_id: str,
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
    storage=Depends(deps.get_photo_storage),
):
    DeletePhotoHandler(providers, storage).handle(
        DeletePhotoCommand(provider_id=user["providerId"], photo_id=photo_id)
    )


@router.put("/me/photos/{photo_id}/cover")
def set_cover_photo(
    photo_id: str,
    user=Depends(deps.require_provider),
    providers=Depends(deps.get_provider_repo),
):
    return SetCoverPhotoHandler(providers).handle(
        SetCoverPhotoCommand(provider_id=user["providerId"], photo_id=photo_id)
    )


@router.get("/{provider_id}")
def get_provider(provider_id: str, providers=Depends(deps.get_provider_repo)):
    return GetPublicProviderHandler(providers).handle(GetPublicProviderQuery(provider_id=provider_id))


@router.post("/{provider_id}/whatsapp-click", status_code=204)
def track_whatsapp_click(provider_id: str, providers=Depends(deps.get_provider_repo)):
    TrackWhatsappClickHandler(providers).handle(TrackWhatsappClickCommand(provider_id=provider_id))


@router.get("/{provider_id}/reviews")
def list_reviews(
    provider_id: str,
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    return ListProviderReviewsHandler(providers, reviews).handle(
        ListProviderReviewsQuery(provider_id=provider_id)
    )


@router.get("/{provider_id}/reviews/me")
def get_my_review(
    provider_id: str,
    user=Depends(deps.require_common_user),
    reviews=Depends(deps.get_review_repo),
):
    return GetMyReviewHandler(reviews).handle(
        GetMyReviewQuery(provider_id=provider_id, user_id=user["id"])
    )


@router.post("/{provider_id}/reviews", status_code=201)
def create_review(
    provider_id: str,
    body: ReviewRequest,
    user=Depends(deps.require_common_user),
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    return CreateReviewHandler(providers, reviews).handle(
        CreateReviewCommand(
            provider_id=provider_id,
            user_id=user["id"],
            user_name=user["name"],
            rating=body.rating,
            comment=body.comment,
        )
    )


@router.put("/{provider_id}/reviews/me")
def update_review(
    provider_id: str,
    body: ReviewRequest,
    user=Depends(deps.require_common_user),
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    return UpdateReviewHandler(providers, reviews).handle(
        UpdateReviewCommand(
            provider_id=provider_id,
            user_id=user["id"],
            rating=body.rating,
            comment=body.comment,
        )
    )


@router.delete("/{provider_id}/reviews/me", status_code=204)
def delete_review(
    provider_id: str,
    user=Depends(deps.require_common_user),
    providers=Depends(deps.get_provider_repo),
    reviews=Depends(deps.get_review_repo),
):
    DeleteOwnReviewHandler(providers, reviews).handle(
        DeleteOwnReviewCommand(provider_id=provider_id, user_id=user["id"])
    )
