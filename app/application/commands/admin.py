from dataclasses import dataclass

from app.application.commands.reviews import recalc_provider_rating
from app.application.interfaces import (
    CategoryRepository,
    EmailService,
    PhotoStorage,
    ProviderRepository,
    ReviewRepository,
    UserRepository,
)
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.domain.entities import ProviderStatus, new_category_doc, now_iso
from app.domain.validators import normalize_text


def _get_provider(providers: ProviderRepository, provider_id: str) -> dict:
    provider = providers.get(provider_id)
    if not provider:
        raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
    return provider


def _get_user(users: UserRepository, user_id: str) -> dict:
    user = users.get(user_id)
    if not user:
        raise NotFoundError("Usuário não encontrado.", code="USER_NOT_FOUND")
    return user


@dataclass
class ApproveProviderCommand:
    provider_id: str


class ApproveProviderHandler:
    def __init__(
        self, providers: ProviderRepository, users: UserRepository, email_service: EmailService
    ) -> None:
        self._providers = providers
        self._users = users
        self._email = email_service

    def handle(self, cmd: ApproveProviderCommand) -> dict:
        provider = _get_provider(self._providers, cmd.provider_id)
        was_pending = provider["status"] == ProviderStatus.PENDING.value
        provider["status"] = ProviderStatus.ACTIVE.value
        if not provider.get("approvedAt"):
            provider["approvedAt"] = now_iso()
        updated = self._providers.update(provider)
        if was_pending:
            user = self._users.get(provider["userId"])
            if user:
                settings = get_settings()
                self._email.send(
                    to=user["email"],
                    subject="Cadastro aprovado — Serviços Bebedouro",
                    html=(
                        f"<p>Olá, {provider['name']}.</p>"
                        f"<p>Seu cadastro foi aprovado! Seu perfil já está visível na plataforma.</p>"
                        f'<p><a href="{settings.frontend_url}/prestador/{provider["id"]}">Ver meu perfil</a></p>'
                    ),
                )
        return updated


@dataclass
class DeactivateProviderCommand:
    provider_id: str


class DeactivateProviderHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, cmd: DeactivateProviderCommand) -> dict:
        provider = _get_provider(self._providers, cmd.provider_id)
        provider["status"] = ProviderStatus.DEACTIVATED.value
        return self._providers.update(provider)


@dataclass
class RemoveProviderCommand:
    provider_id: str


class RemoveProviderHandler:
    def __init__(
        self,
        providers: ProviderRepository,
        users: UserRepository,
        reviews: ReviewRepository,
        storage: PhotoStorage,
    ) -> None:
        self._providers = providers
        self._users = users
        self._reviews = reviews
        self._storage = storage

    def handle(self, cmd: RemoveProviderCommand) -> None:
        provider = _get_provider(self._providers, cmd.provider_id)
        for photo in provider["photos"]:
            self._storage.delete(photo["blobName"])
        self._reviews.delete_by_provider(provider["id"])
        self._providers.delete(provider["id"])
        user = self._users.get(provider["userId"])
        if user:
            self._users.delete(user["id"])


@dataclass
class DeactivateUserCommand:
    user_id: str


class DeactivateUserHandler:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def handle(self, cmd: DeactivateUserCommand) -> dict:
        user = _get_user(self._users, cmd.user_id)
        user["active"] = False
        user["refreshJtis"] = {}
        return self._users.update(user)


@dataclass
class RemoveUserCommand:
    user_id: str


class RemoveUserHandler:
    def __init__(
        self, users: UserRepository, reviews: ReviewRepository, providers: ProviderRepository
    ) -> None:
        self._users = users
        self._reviews = reviews
        self._providers = providers

    def handle(self, cmd: RemoveUserCommand) -> None:
        user = _get_user(self._users, cmd.user_id)
        user_reviews = self._reviews.list_by_user(user["id"])
        affected_providers = {r["providerId"] for r in user_reviews}
        for review in user_reviews:
            self._reviews.delete(review["id"], review["providerId"])
        for provider_id in affected_providers:
            recalc_provider_rating(self._providers, self._reviews, provider_id)
        self._users.delete(user["id"])


@dataclass
class CreateCategoryCommand:
    name: str


class CreateCategoryHandler:
    def __init__(self, categories: CategoryRepository) -> None:
        self._categories = categories

    def handle(self, cmd: CreateCategoryCommand) -> dict:
        existing = [c for c in self._categories.list_all() if c["nameSearch"] == normalize_text(cmd.name)]
        if existing:
            raise ConflictError("Já existe uma categoria com este nome.", code="CATEGORY_EXISTS")
        return self._categories.create(new_category_doc(cmd.name))


@dataclass
class UpdateCategoryCommand:
    category_id: str
    name: str
    active: bool


class UpdateCategoryHandler:
    def __init__(self, categories: CategoryRepository, providers: ProviderRepository) -> None:
        self._categories = categories
        self._providers = providers

    def handle(self, cmd: UpdateCategoryCommand) -> dict:
        category = self._categories.get(cmd.category_id)
        if not category:
            raise NotFoundError("Categoria não encontrada.", code="CATEGORY_NOT_FOUND")
        category["name"] = cmd.name
        category["nameSearch"] = normalize_text(cmd.name)
        category["active"] = cmd.active
        return self._categories.update(category)


@dataclass
class DeleteCategoryCommand:
    category_id: str


class DeleteCategoryHandler:
    def __init__(self, categories: CategoryRepository, providers: ProviderRepository) -> None:
        self._categories = categories
        self._providers = providers

    def handle(self, cmd: DeleteCategoryCommand) -> None:
        category = self._categories.get(cmd.category_id)
        if not category:
            raise NotFoundError("Categoria não encontrada.", code="CATEGORY_NOT_FOUND")
        if self._providers.count_by_category(category["id"]) > 0:
            raise ConflictError(
                "Esta categoria está em uso por prestadores e não pode ser removida. "
                "Você pode desativá-la para ocultá-la de novos cadastros.",
                code="CATEGORY_IN_USE",
            )
        self._categories.delete(category["id"])


@dataclass
class AdminDeleteReviewCommand:
    review_id: str
    provider_id: str


class AdminDeleteReviewHandler:
    def __init__(self, providers: ProviderRepository, reviews: ReviewRepository) -> None:
        self._providers = providers
        self._reviews = reviews

    def handle(self, cmd: AdminDeleteReviewCommand) -> None:
        review = self._reviews.get(cmd.review_id, cmd.provider_id)
        if not review:
            raise NotFoundError("Avaliação não encontrada.", code="REVIEW_NOT_FOUND")
        self._reviews.delete(review["id"], cmd.provider_id)
        recalc_provider_rating(self._providers, self._reviews, cmd.provider_id)
