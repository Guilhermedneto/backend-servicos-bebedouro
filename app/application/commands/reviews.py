from dataclasses import dataclass

from app.application.interfaces import DuplicateReviewError, ProviderRepository, ReviewRepository
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.domain.entities import ProviderStatus, new_review_doc, now_iso
from app.domain.plans import shows_full_profile


def recalc_provider_rating(
    providers: ProviderRepository, reviews: ReviewRepository, provider_id: str
) -> None:
    provider = providers.get(provider_id)
    if not provider:
        return
    count, avg = reviews.aggregate_for_provider(provider_id)
    provider["ratingCount"] = count
    provider["ratingAvg"] = round(avg, 1) if count else 0.0
    providers.update(provider)


def _get_active_provider(providers: ProviderRepository, provider_id: str) -> dict:
    provider = providers.get(provider_id)
    if not provider or provider["status"] != ProviderStatus.ACTIVE.value:
        raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
    return provider


@dataclass
class CreateReviewCommand:
    provider_id: str
    user_id: str
    user_name: str
    rating: int
    comment: str


class CreateReviewHandler:
    def __init__(self, providers: ProviderRepository, reviews: ReviewRepository) -> None:
        self._providers = providers
        self._reviews = reviews

    def handle(self, cmd: CreateReviewCommand) -> dict:
        provider = _get_active_provider(self._providers, cmd.provider_id)
        if not shows_full_profile(provider):
            raise ForbiddenError(
                "Este prestador está no plano gratuito e não recebe avaliações.",
                code="REVIEWS_NOT_ALLOWED",
            )
        doc = new_review_doc(cmd.provider_id, cmd.user_id, cmd.user_name, cmd.rating, cmd.comment)
        try:
            created = self._reviews.create(doc)
        except DuplicateReviewError:
            raise ConflictError(
                "Você já avaliou este prestador. Edite sua avaliação existente.",
                code="REVIEW_ALREADY_EXISTS",
            )
        recalc_provider_rating(self._providers, self._reviews, cmd.provider_id)
        return created


@dataclass
class UpdateReviewCommand:
    provider_id: str
    user_id: str
    rating: int
    comment: str


class UpdateReviewHandler:
    def __init__(self, providers: ProviderRepository, reviews: ReviewRepository) -> None:
        self._providers = providers
        self._reviews = reviews

    def handle(self, cmd: UpdateReviewCommand) -> dict:
        _get_active_provider(self._providers, cmd.provider_id)
        review = self._reviews.find_by_user_and_provider(cmd.user_id, cmd.provider_id)
        if not review:
            raise NotFoundError("Você ainda não avaliou este prestador.", code="REVIEW_NOT_FOUND")
        review["rating"] = cmd.rating
        review["comment"] = cmd.comment
        review["updatedAt"] = now_iso()
        updated = self._reviews.update(review)
        recalc_provider_rating(self._providers, self._reviews, cmd.provider_id)
        return updated


@dataclass
class DeleteOwnReviewCommand:
    provider_id: str
    user_id: str


class DeleteOwnReviewHandler:
    def __init__(self, providers: ProviderRepository, reviews: ReviewRepository) -> None:
        self._providers = providers
        self._reviews = reviews

    def handle(self, cmd: DeleteOwnReviewCommand) -> None:
        review = self._reviews.find_by_user_and_provider(cmd.user_id, cmd.provider_id)
        if not review:
            raise NotFoundError("Avaliação não encontrada.", code="REVIEW_NOT_FOUND")
        self._reviews.delete(review["id"], cmd.provider_id)
        recalc_provider_rating(self._providers, self._reviews, cmd.provider_id)
