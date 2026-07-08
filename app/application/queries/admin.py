from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.application.interfaces import (
    CategoryRepository,
    ProviderRepository,
    ReviewRepository,
    UserRepository,
)
from app.application.queries.categories import to_category_dto
from app.application.queries.reviews import to_review_dto
from app.domain.entities import ProviderStatus, Role


class GetDashboardHandler:
    def __init__(
        self, users: UserRepository, providers: ProviderRepository, reviews: ReviewRepository
    ) -> None:
        self._users = users
        self._providers = providers
        self._reviews = reviews

    def handle(self) -> dict:
        with ThreadPoolExecutor(max_workers=4) as pool:
            total_users = pool.submit(self._users.count_by_role, Role.USER.value)
            active = pool.submit(self._providers.count_by_status, ProviderStatus.ACTIVE.value)
            pending = pool.submit(self._providers.count_by_status, ProviderStatus.PENDING.value)
            reviews = pool.submit(self._reviews.count_all)
        return {
            "totalUsers": total_users.result(),
            "activeProviders": active.result(),
            "pendingProviders": pending.result(),
            "totalReviews": reviews.result(),
        }


class ListUsersHandler:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def handle(self) -> list[dict]:
        return [
            {
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "active": u["active"],
                "createdAt": u["createdAt"],
            }
            for u in self._users.list_by_role(Role.USER.value)
        ]


@dataclass
class ListProvidersAdminQuery:
    status: str | None


class ListProvidersAdminHandler:
    def __init__(self, providers: ProviderRepository, users: UserRepository) -> None:
        self._providers = providers
        self._users = users

    def handle(self, query: ListProvidersAdminQuery) -> list[dict]:
        status = query.status if query.status in {s.value for s in ProviderStatus} else None
        providers = self._providers.list_admin(status)
        emails = {u["id"]: u["email"] for u in self._users.list_by_role(Role.PROVIDER.value)}
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "email": emails.get(p["userId"], ""),
                "categoryName": ", ".join(c["name"] for c in p["categories"]),
                "bairro": p["address"]["bairro"],
                "whatsapp": p["whatsapp"],
                "status": p["status"],
                "ratingAvg": p["ratingAvg"],
                "ratingCount": p["ratingCount"],
                "createdAt": p["createdAt"],
            }
            for p in providers
        ]


class ListAllCategoriesHandler:
    def __init__(self, categories: CategoryRepository, providers: ProviderRepository) -> None:
        self._categories = categories
        self._providers = providers

    def handle(self) -> list[dict]:
        usage = self._providers.category_usage_counts()
        result = []
        for category in self._categories.list_all():
            dto = to_category_dto(category)
            dto["providersCount"] = usage.get(category["id"], 0)
            result.append(dto)
        return result


class ListAllReviewsHandler:
    def __init__(self, reviews: ReviewRepository, providers: ProviderRepository) -> None:
        self._reviews = reviews
        self._providers = providers

    def handle(self) -> list[dict]:
        reviews = self._reviews.list_all()
        provider_names: dict[str, str] = {}
        result = []
        for review in reviews:
            provider_id = review["providerId"]
            if provider_id not in provider_names:
                provider = self._providers.get(provider_id)
                provider_names[provider_id] = provider["name"] if provider else "(removido)"
            dto = to_review_dto(review)
            dto["providerName"] = provider_names[provider_id]
            result.append(dto)
        return result
