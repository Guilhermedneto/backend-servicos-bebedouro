from dataclasses import dataclass

from app.application.interfaces import ProviderRepository, ReviewRepository
from app.core.errors import NotFoundError
from app.domain.entities import ProviderStatus


def to_review_dto(review: dict) -> dict:
    return {
        "id": review["id"],
        "providerId": review["providerId"],
        "userId": review["userId"],
        "userName": review["userName"],
        "rating": review["rating"],
        "comment": review["comment"],
        "createdAt": review["createdAt"],
        "updatedAt": review["updatedAt"],
    }


@dataclass
class ListProviderReviewsQuery:
    provider_id: str


class ListProviderReviewsHandler:
    def __init__(self, providers: ProviderRepository, reviews: ReviewRepository) -> None:
        self._providers = providers
        self._reviews = reviews

    def handle(self, query: ListProviderReviewsQuery) -> list[dict]:
        provider = self._providers.get(query.provider_id)
        if not provider or provider["status"] != ProviderStatus.ACTIVE.value:
            raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
        return [to_review_dto(r) for r in self._reviews.list_by_provider(query.provider_id)]


@dataclass
class GetMyReviewQuery:
    provider_id: str
    user_id: str


class GetMyReviewHandler:
    def __init__(self, reviews: ReviewRepository) -> None:
        self._reviews = reviews

    def handle(self, query: GetMyReviewQuery) -> dict | None:
        review = self._reviews.find_by_user_and_provider(query.user_id, query.provider_id)
        return to_review_dto(review) if review else None
