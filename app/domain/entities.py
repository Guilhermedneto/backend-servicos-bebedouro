import uuid
from datetime import datetime, timezone
from enum import Enum

from app.domain.plans import Plan, SubscriptionStatus
from app.domain.validators import normalize_text


class Role(str, Enum):
    USER = "user"
    PROVIDER = "provider"
    ADMIN = "admin"


class ProviderStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


class BusinessType(str, Enum):
    COMMERCE = "commerce"
    SERVICE = "service"


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
    business_type: str,
    categories: list[dict],
    bairro: str,
    rua: str,
    numero: str,
    whatsapp: str,
    description: str,
    coordinates: dict | None,
    plan: str,
    billing_cycle: str | None,
    subscription_status: str,
    is_trial: bool = False,
    trial_ends_at: str | None = None,
) -> dict:
    return {
        "id": new_id(),
        "userId": user_id,
        "name": name,
        "nameSearch": normalize_text(name),
        "documentEncrypted": document_encrypted,
        "documentType": document_type,
        "businessType": business_type,
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
        "whatsappClicks": 0,
        "plan": plan,
        "billingCycle": billing_cycle,
        "subscriptionStatus": subscription_status,
        "isTrial": is_trial,
        "trialEndsAt": trial_ends_at,
        "cancelAtPeriodEnd": False,
        "isPremium": plan == Plan.PREMIUM.value and subscription_status == SubscriptionStatus.ACTIVE.value,
        "stripeCustomerId": None,
        "stripeSubscriptionId": None,
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


def new_category_doc(name: str, business_type: str) -> dict:
    return {
        "id": new_id(),
        "name": name,
        "nameSearch": normalize_text(name),
        "businessType": business_type,
        "active": True,
        "createdAt": now_iso(),
    }


def new_photo(url: str, blob_name: str, is_cover: bool) -> dict:
    return {"id": new_id(), "url": url, "blobName": blob_name, "isCover": is_cover}


def new_trial_claim_doc(document_hash: str, email_hash: str, name_hash: str, provider_id: str) -> dict:
    return {
        "id": new_id(),
        "documentHash": document_hash,
        "emailHash": email_hash,
        "nameHash": name_hash,
        "providerId": provider_id,
        "claimedAt": now_iso(),
    }
