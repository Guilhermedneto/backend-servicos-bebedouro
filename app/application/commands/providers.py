import uuid
from dataclasses import dataclass

from app.application.interfaces import CategoryRepository, Geocoder, PhotoStorage, ProviderRepository
from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.domain.entities import new_photo
from app.domain.validators import normalize_text, validate_whatsapp

ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

MAX_CATEGORIES = 4


def resolve_categories(categories_repo: CategoryRepository, category_ids: list[str]) -> list[dict]:
    """Valida e resolve de 1 a 4 categorias ativas, preservando a ordem e removendo duplicatas."""
    unique_ids = list(dict.fromkeys(category_ids))
    if not unique_ids or len(unique_ids) > MAX_CATEGORIES:
        raise ValidationFailedError(
            f"Selecione de 1 a {MAX_CATEGORIES} ramos de atuação.",
            code="INVALID_CATEGORY_COUNT",
            details={"field": "categoryIds"},
        )
    resolved = []
    for category_id in unique_ids:
        category = categories_repo.get(category_id)
        if not category or not category.get("active"):
            raise ValidationFailedError(
                "Ramo de atuação inválido: selecione categorias existentes e ativas.",
                code="INVALID_CATEGORY",
                details={"field": "categoryIds"},
            )
        resolved.append({"id": category["id"], "name": category["name"]})
    return resolved


def _get_own_provider(providers: ProviderRepository, provider_id: str) -> dict:
    provider = providers.get(provider_id)
    if not provider:
        raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
    return provider


@dataclass
class UpdateProviderProfileCommand:
    provider_id: str
    name: str
    category_ids: list[str]
    bairro: str
    rua: str
    numero: str
    whatsapp: str
    description: str


class UpdateProviderProfileHandler:
    def __init__(
        self, providers: ProviderRepository, categories: CategoryRepository, geocoder: Geocoder
    ) -> None:
        self._providers = providers
        self._categories = categories
        self._geocoder = geocoder

    def handle(self, cmd: UpdateProviderProfileCommand) -> dict:
        provider = _get_own_provider(self._providers, cmd.provider_id)
        whatsapp = validate_whatsapp(cmd.whatsapp)
        if cmd.category_ids != provider.get("categoryIds", []):
            categories = resolve_categories(self._categories, cmd.category_ids)
            provider["categories"] = categories
            provider["categoryIds"] = [c["id"] for c in categories]
            provider["categorySearch"] = normalize_text(" ".join(c["name"] for c in categories))

        address = provider["address"]
        address_changed = (
            cmd.bairro != address["bairro"] or cmd.rua != address["rua"] or cmd.numero != address["numero"]
        )
        if address_changed:
            provider["coordinates"] = self._geocoder.geocode(cmd.rua, cmd.numero, cmd.bairro)
        provider["address"] = {"cidade": "Bebedouro", "bairro": cmd.bairro, "rua": cmd.rua, "numero": cmd.numero}
        provider["bairroSearch"] = normalize_text(cmd.bairro)
        provider["name"] = cmd.name
        provider["nameSearch"] = normalize_text(cmd.name)
        provider["whatsapp"] = whatsapp
        provider["description"] = cmd.description
        return self._providers.update(provider)


@dataclass
class UploadPhotoCommand:
    provider_id: str
    content_type: str
    data: bytes


class UploadPhotoHandler:
    def __init__(self, providers: ProviderRepository, storage: PhotoStorage) -> None:
        self._providers = providers
        self._storage = storage

    def handle(self, cmd: UploadPhotoCommand) -> dict:
        settings = get_settings()
        provider = _get_own_provider(self._providers, cmd.provider_id)
        if len(provider["photos"]) >= settings.max_photos:
            raise ValidationFailedError(
                f"Limite de {settings.max_photos} fotos atingido. Exclua uma foto para enviar outra.",
                code="PHOTO_LIMIT_REACHED",
            )
        if cmd.content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationFailedError(
                "Formato de imagem não suportado. Envie JPEG, PNG ou WebP.",
                code="INVALID_PHOTO_FORMAT",
            )
        if len(cmd.data) > settings.max_photo_bytes:
            raise ValidationFailedError(
                "Imagem muito grande. O tamanho máximo é 5 MB.",
                code="PHOTO_TOO_LARGE",
            )
        ext = ALLOWED_CONTENT_TYPES[cmd.content_type]
        blob_name = f"{provider['id']}/{uuid.uuid4().hex}.{ext}"
        url = self._storage.upload(blob_name, cmd.data, cmd.content_type)
        photo = new_photo(url, blob_name, is_cover=len(provider["photos"]) == 0)
        provider["photos"].append(photo)
        self._providers.update(provider)
        return photo


@dataclass
class DeletePhotoCommand:
    provider_id: str
    photo_id: str


class DeletePhotoHandler:
    def __init__(self, providers: ProviderRepository, storage: PhotoStorage) -> None:
        self._providers = providers
        self._storage = storage

    def handle(self, cmd: DeletePhotoCommand) -> dict:
        provider = _get_own_provider(self._providers, cmd.provider_id)
        photo = next((p for p in provider["photos"] if p["id"] == cmd.photo_id), None)
        if not photo:
            raise NotFoundError("Foto não encontrada.", code="PHOTO_NOT_FOUND")
        provider["photos"] = [p for p in provider["photos"] if p["id"] != cmd.photo_id]
        if photo["isCover"] and provider["photos"]:
            provider["photos"][0]["isCover"] = True
        updated = self._providers.update(provider)
        self._storage.delete(photo["blobName"])
        return updated


@dataclass
class SetCoverPhotoCommand:
    provider_id: str
    photo_id: str


class SetCoverPhotoHandler:
    def __init__(self, providers: ProviderRepository) -> None:
        self._providers = providers

    def handle(self, cmd: SetCoverPhotoCommand) -> dict:
        provider = _get_own_provider(self._providers, cmd.provider_id)
        if not any(p["id"] == cmd.photo_id for p in provider["photos"]):
            raise NotFoundError("Foto não encontrada.", code="PHOTO_NOT_FOUND")
        for photo in provider["photos"]:
            photo["isCover"] = photo["id"] == cmd.photo_id
        return self._providers.update(provider)
