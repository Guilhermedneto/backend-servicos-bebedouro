from dataclasses import dataclass

from app.application.interfaces import ProviderRepository
from app.core.errors import NotFoundError
from app.domain.entities import ProviderStatus
from app.domain.plans import effective_plan, is_premium, photo_limit, shows_full_profile
from app.domain.validators import mask_document, normalize_text
from app.core.security import decrypt_value

SORT_OPTIONS = {"rating", "reviews", "recent"}


def _cover_url(provider: dict) -> str | None:
    for photo in provider["photos"]:
        if photo["isCover"]:
            return photo["url"]
    return provider["photos"][0]["url"] if provider["photos"] else None


def to_card(provider: dict) -> dict:
    full = shows_full_profile(provider)
    return {
        "id": provider["id"],
        "name": provider["name"],
        "categoryNames": [c["name"] for c in provider["categories"]],
        "bairro": provider["address"]["bairro"],
        "plan": effective_plan(provider),
        "isPremium": is_premium(provider),
        "whatsapp": provider["whatsapp"] if full else None,
        "ratingAvg": provider["ratingAvg"] if full else 0.0,
        "ratingCount": provider["ratingCount"] if full else 0,
        "coverUrl": _cover_url(provider) if full else None,
    }


def to_public_profile(provider: dict) -> dict:
    full = shows_full_profile(provider)
    return {
        "id": provider["id"],
        "name": provider["name"],
        "categoryIds": provider["categoryIds"],
        "categoryNames": [c["name"] for c in provider["categories"]],
        "address": provider["address"],
        "coordinates": provider["coordinates"],
        "plan": effective_plan(provider),
        "isPremium": is_premium(provider),
        "whatsapp": provider["whatsapp"] if full else None,
        "description": provider["description"] if full else None,
        "photos": (
            [{"id": p["id"], "url": p["url"], "isCover": p["isCover"]} for p in provider["photos"]]
            if full
            else []
        ),
        "ratingAvg": provider["ratingAvg"] if full else 0.0,
        "ratingCount": provider["ratingCount"] if full else 0,
        "coverUrl": _cover_url(provider) if full else None,
    }


@dataclass
class ListProvidersQuery:
    search: str | None
    category_id: str | None
    sort: str
    page: int
    page_size: int


class ListProvidersHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, query: ListProvidersQuery) -> dict:
        sort = query.sort if query.sort in SORT_OPTIONS else "recent"
        page = max(query.page, 1)
        offset = (page - 1) * query.page_size
        items, total = self._providers.list_public(
            search=normalize_text(query.search.strip()) if query.search else None,
            category_id=query.category_id,
            sort=sort,
            offset=offset,
            limit=query.page_size,
        )
        return {
            "items": [to_card(p) for p in items],
            "page": page,
            "pageSize": query.page_size,
            "total": total,
            "hasMore": offset + len(items) < total,
        }


class ListFeaturedHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, limit: int = 8) -> list[dict]:
        return [to_card(p) for p in self._providers.list_featured(limit)]


@dataclass
class GetPublicProviderQuery:
    provider_id: str


class GetPublicProviderHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, query: GetPublicProviderQuery) -> dict:
        provider = self._providers.get(query.provider_id)
        if not provider or provider["status"] != ProviderStatus.ACTIVE.value:
            raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
        return to_public_profile(provider)


@dataclass
class GetMyProviderQuery:
    user_id: str


class GetMyProviderHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, query: GetMyProviderQuery) -> dict:
        provider = self._providers.find_by_user_id(query.user_id)
        if not provider:
            raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
        # O dono vê sempre o perfil completo, independentemente do plano vigente.
        profile = {
            "id": provider["id"],
            "name": provider["name"],
            "categoryIds": provider["categoryIds"],
            "categoryNames": [c["name"] for c in provider["categories"]],
            "address": provider["address"],
            "coordinates": provider["coordinates"],
            "whatsapp": provider["whatsapp"],
            "description": provider["description"],
            "photos": [
                {"id": p["id"], "url": p["url"], "isCover": p["isCover"]} for p in provider["photos"]
            ],
            "ratingAvg": provider["ratingAvg"],
            "ratingCount": provider["ratingCount"],
            "coverUrl": _cover_url(provider),
            "status": provider["status"],
            "plan": provider.get("plan", "essential"),
            "effectivePlan": effective_plan(provider),
            "isPremium": is_premium(provider),
            "billingCycle": provider.get("billingCycle"),
            "subscriptionStatus": provider.get("subscriptionStatus", "active"),
            "cancelAtPeriodEnd": provider.get("cancelAtPeriodEnd", False),
            "photoLimit": photo_limit(effective_plan(provider)),
            "documentMasked": mask_document(
                decrypt_value(provider["documentEncrypted"]), provider["documentType"]
            ),
            "documentType": provider["documentType"],
            "createdAt": provider["createdAt"],
        }
        return profile
