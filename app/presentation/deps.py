from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.interfaces import (
    AiSearchService,
    CategoryRepository,
    EmailService,
    Geocoder,
    PhotoStorage,
    ProviderRepository,
    ReviewRepository,
    UserRepository,
)
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.domain.entities import Role
from app.infrastructure.blob_storage import AzureBlobPhotoStorage
from app.infrastructure.email import build_email_service
from app.infrastructure.nominatim import NominatimGeocoder
from app.infrastructure.repositories import (
    CosmosCategoryRepository,
    CosmosProviderRepository,
    CosmosReviewRepository,
    CosmosUserRepository,
)

_bearer = HTTPBearer(auto_error=False)


def get_user_repo() -> UserRepository:
    return CosmosUserRepository()


def get_provider_repo() -> ProviderRepository:
    return CosmosProviderRepository()


def get_review_repo() -> ReviewRepository:
    return CosmosReviewRepository()


def get_category_repo() -> CategoryRepository:
    return CosmosCategoryRepository()


def get_photo_storage() -> PhotoStorage:
    return AzureBlobPhotoStorage()


def get_email_service() -> EmailService:
    return build_email_service()


def get_geocoder() -> Geocoder:
    return NominatimGeocoder()


def get_ai_search_service() -> AiSearchService:
    from app.infrastructure.ai_search import LangGraphAiSearchService

    return LangGraphAiSearchService(CosmosProviderRepository(), CosmosCategoryRepository())


def get_stripe_service():
    from app.infrastructure.stripe_service import StripeService

    return StripeService()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    users: UserRepository = Depends(get_user_repo),
) -> dict:
    if credentials is None:
        raise UnauthorizedError("Autenticação necessária.", code="AUTH_REQUIRED")
    payload = decode_token(credentials.credentials, expected_type="access")
    user = users.get(payload["sub"])
    if not user or not user.get("active"):
        raise UnauthorizedError("Sessão inválida.", code="SESSION_INVALID")
    user["providerId"] = payload.get("providerId")
    return user


def require_common_user(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != Role.USER.value:
        raise ForbiddenError(
            "Apenas usuários comuns podem executar esta ação.", code="ROLE_NOT_ALLOWED"
        )
    return user


def require_provider(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != Role.PROVIDER.value:
        raise ForbiddenError("Apenas prestadores podem executar esta ação.", code="ROLE_NOT_ALLOWED")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != Role.ADMIN.value:
        raise ForbiddenError("Acesso restrito ao administrador.", code="ROLE_NOT_ALLOWED")
    return user
