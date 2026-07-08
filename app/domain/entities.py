import uuid
from datetime import datetime, timezone
from enum import Enum

from app.domain.validators import normalize_text


class Role(str, Enum):
    USER = "user"
    PROVIDER = "provider"
    ADMIN = "admin"


class ProviderStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def new_user_doc(name: str, email: str, password_hash: str, role: Role) -> dict:
    return {
        "id": new_id(),
        "name": name,
        "email": email.lower(),
        "passwordHash": password_hash,
        "role": role.value,
        "active": True,
        "refreshJtis": {},
        "resetTokenHash": None,
        "resetTokenExpiresAt": None,
        "createdAt": now_iso(),
    }


def new_provider_doc(
    user_id: str,
    name: str,
    document_encrypted: str,
    document_type: str,
    categories: list[dict],
    bairro: str,
    rua: str,
    numero: str,
    whatsapp: str,
    description: str,
    coordinates: dict | None,
) -> dict:
    return {
        "id": new_id(),
        "userId": user_id,
        "name": name,
        "nameSearch": normalize_text(name),
        "documentEncrypted": document_encrypted,
        "documentType": document_type,
        "categories": categories,
        "categoryIds": [c["id"] for c in categories],
        "categorySearch": normalize_text(" ".join(c["name"] for c in categories)),
        "address": {"cidade": "Bebedouro", "bairro": bairro, "rua": rua, "numero": numero},
        "bairroSearch": normalize_text(bairro),
        "whatsapp": whatsapp,
        "description": description,
        "photos": [],
        "status": ProviderStatus.PENDING.value,
        "coordinates": coordinates,
        "ratingAvg": 0.0,
        "ratingCount": 0,
        "createdAt": now_iso(),
        "approvedAt": None,
    }


def new_review_doc(provider_id: str, user_id: str, user_name: str, rating: int, comment: str) -> dict:
    created = now_iso()
    return {
        "id": new_id(),
        "providerId": provider_id,
        "userId": user_id,
        "userName": user_name,
        "rating": rating,
        "comment": comment,
        "createdAt": created,
        "updatedAt": created,
    }


def new_category_doc(name: str) -> dict:
    return {
        "id": new_id(),
        "name": name,
        "nameSearch": normalize_text(name),
        "active": True,
        "createdAt": now_iso(),
    }


def new_photo(url: str, blob_name: str, is_cover: bool) -> dict:
    return {"id": new_id(), "url": url, "blobName": blob_name, "isCover": is_cover}
