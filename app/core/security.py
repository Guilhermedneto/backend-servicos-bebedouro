import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.errors import UnauthorizedError


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _fernet() -> Fernet:
    return Fernet(get_settings().encryption_key.encode("utf-8"))


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def create_access_token(user_id: str, role: str, name: str, provider_id: str | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    if provider_id:
        payload["providerId"] = provider_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    exp = now + timedelta(days=settings.refresh_token_days)
    token = jwt.encode(
        {"sub": user_id, "type": "refresh", "jti": jti, "iat": now, "exp": exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti, exp


def decode_token(token: str, expected_type: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expirado.", code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Token inválido.", code="TOKEN_INVALID")
    if payload.get("type") != expected_type:
        raise UnauthorizedError("Token inválido.", code="TOKEN_INVALID")
    return payload


def generate_reset_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
