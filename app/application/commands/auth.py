from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.interfaces import (
    CategoryRepository,
    EmailService,
    Geocoder,
    ProviderRepository,
    UserRepository,
)
from app.core.config import get_settings
from app.application.commands.providers import resolve_categories
from app.application.commands.subscriptions import (
    create_checkout,
    initial_subscription_status,
    validate_plan_choice,
)
from app.domain.plans import PAID_PLANS, SubscriptionStatus
from app.infrastructure.stripe_service import StripeService
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_value,
    generate_reset_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.entities import Role, new_provider_doc, new_user_doc, now_iso
from app.domain.validators import validate_document, validate_whatsapp


@dataclass
class RegisterUserCommand:
    name: str
    email: str
    password: str


class RegisterUserHandler:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def handle(self, cmd: RegisterUserCommand) -> dict:
        if self._users.find_by_email(cmd.email):
            raise ConflictError("Já existe uma conta cadastrada com este e-mail.", code="EMAIL_IN_USE")
        doc = new_user_doc(cmd.name, cmd.email, hash_password(cmd.password), Role.USER)
        self._users.create(doc)
        return {"id": doc["id"]}


@dataclass
class RegisterProviderCommand:
    name: str
    document: str
    category_ids: list[str]
    bairro: str
    rua: str
    numero: str
    whatsapp: str
    description: str
    email: str
    password: str
    plan: str
    billing_cycle: str | None


class RegisterProviderHandler:
    def __init__(
        self,
        users: UserRepository,
        providers: ProviderRepository,
        categories: CategoryRepository,
        geocoder: Geocoder,
        stripe: StripeService,
    ) -> None:
        self._users = users
        self._providers = providers
        self._categories = categories
        self._geocoder = geocoder
        self._stripe = stripe

    def handle(self, cmd: RegisterProviderCommand) -> dict:
        validate_plan_choice(cmd.plan, cmd.billing_cycle)
        document_digits, doc_type = validate_document(cmd.document)
        whatsapp = validate_whatsapp(cmd.whatsapp)
        categories = resolve_categories(self._categories, cmd.category_ids)
        if self._users.find_by_email(cmd.email):
            raise ConflictError("Já existe uma conta cadastrada com este e-mail.", code="EMAIL_IN_USE")

        subscription_status = initial_subscription_status(cmd.plan)
        billing_cycle = cmd.billing_cycle if cmd.plan in PAID_PLANS else None

        coordinates = self._geocoder.geocode(cmd.rua, cmd.numero, cmd.bairro)
        user_doc = new_user_doc(cmd.name, cmd.email, hash_password(cmd.password), Role.PROVIDER)
        self._users.create(user_doc)
        provider_doc = new_provider_doc(
            user_id=user_doc["id"],
            name=cmd.name,
            document_encrypted=encrypt_value(document_digits),
            document_type=doc_type,
            categories=categories,
            bairro=cmd.bairro,
            rua=cmd.rua,
            numero=cmd.numero,
            whatsapp=whatsapp,
            description=cmd.description,
            coordinates=coordinates,
            plan=cmd.plan,
            billing_cycle=billing_cycle,
            subscription_status=subscription_status,
        )
        self._providers.create(provider_doc)
        result = {
            "id": provider_doc["id"],
            "userId": user_doc["id"],
            "status": provider_doc["status"],
            "plan": cmd.plan,
            "subscriptionStatus": subscription_status,
        }
        if subscription_status == SubscriptionStatus.PENDING_PAYMENT.value:
            checkout = create_checkout(self._stripe, provider_doc, cmd.plan, billing_cycle, cmd.email)
            result["checkoutUrl"] = checkout["url"]
        return result


@dataclass
class LoginCommand:
    email: str
    password: str


class LoginHandler:
    def __init__(self, users: UserRepository, providers: ProviderRepository) -> None:
        self._users = users
        self._providers = providers

    def handle(self, cmd: LoginCommand) -> dict:
        user = self._users.find_by_email(cmd.email)
        if not user or not verify_password(cmd.password, user["passwordHash"]):
            raise UnauthorizedError("E-mail ou senha incorretos.", code="INVALID_CREDENTIALS")
        if not user.get("active"):
            raise ForbiddenError("Esta conta está desativada.", code="ACCOUNT_DISABLED")
        return _issue_tokens(self._users, self._providers, user)


@dataclass
class RefreshTokenCommand:
    refresh_token: str


class RefreshTokenHandler:
    def __init__(self, users: UserRepository, providers: ProviderRepository) -> None:
        self._users = users
        self._providers = providers

    def handle(self, cmd: RefreshTokenCommand) -> dict:
        payload = decode_token(cmd.refresh_token, expected_type="refresh")
        user = self._users.get(payload["sub"])
        if not user or not user.get("active"):
            raise UnauthorizedError("Sessão inválida.", code="SESSION_INVALID")
        jtis = user.get("refreshJtis", {})
        if payload["jti"] not in jtis:
            raise UnauthorizedError("Sessão expirada ou revogada.", code="SESSION_REVOKED")
        del jtis[payload["jti"]]
        return _issue_tokens(self._users, self._providers, user)


@dataclass
class LogoutCommand:
    refresh_token: str


class LogoutHandler:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def handle(self, cmd: LogoutCommand) -> None:
        try:
            payload = decode_token(cmd.refresh_token, expected_type="refresh")
        except UnauthorizedError:
            return
        user = self._users.get(payload["sub"])
        if user and payload["jti"] in user.get("refreshJtis", {}):
            del user["refreshJtis"][payload["jti"]]
            self._users.update(user)


@dataclass
class RequestPasswordResetCommand:
    email: str


class RequestPasswordResetHandler:
    def __init__(self, users: UserRepository, email_service: EmailService) -> None:
        self._users = users
        self._email = email_service

    def handle(self, cmd: RequestPasswordResetCommand) -> None:
        settings = get_settings()
        user = self._users.find_by_email(cmd.email)
        if not user or not user.get("active"):
            return
        token, token_hash = generate_reset_token()
        user["resetTokenHash"] = token_hash
        user["resetTokenExpiresAt"] = (
            datetime.now(timezone.utc).timestamp() + settings.reset_token_minutes * 60
        )
        self._users.update(user)
        link = f"{settings.frontend_url}/redefinir-senha?token={token}"
        self._email.send(
            to=user["email"],
            subject="Recuperação de senha — Serviços Bebedouro",
            html=(
                f"<p>Olá, {user['name']}.</p>"
                f"<p>Para redefinir sua senha, acesse o link abaixo. Ele expira em 1 hora.</p>"
                f'<p><a href="{link}">{link}</a></p>'
                f"<p>Se você não solicitou a redefinição, ignore este e-mail.</p>"
            ),
        )


@dataclass
class ResetPasswordCommand:
    token: str
    new_password: str


class ResetPasswordHandler:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def handle(self, cmd: ResetPasswordCommand) -> None:
        user = self._users.find_by_reset_token_hash(hash_token(cmd.token))
        if not user:
            raise BadRequestError(
                "Link de recuperação inválido ou já utilizado. Solicite um novo.",
                code="INVALID_OR_EXPIRED_TOKEN",
            )
        expires_at = user.get("resetTokenExpiresAt") or 0
        if datetime.now(timezone.utc).timestamp() > expires_at:
            raise BadRequestError(
                "Link de recuperação expirado. Solicite um novo.",
                code="INVALID_OR_EXPIRED_TOKEN",
            )
        user["passwordHash"] = hash_password(cmd.new_password)
        user["resetTokenHash"] = None
        user["resetTokenExpiresAt"] = None
        user["refreshJtis"] = {}
        self._users.update(user)


def _issue_tokens(users: UserRepository, providers: ProviderRepository, user: dict) -> dict:
    provider_id = None
    provider_status = None
    if user["role"] == Role.PROVIDER.value:
        provider = providers.find_by_user_id(user["id"])
        if provider:
            provider_id = provider["id"]
            provider_status = provider["status"]
    access = create_access_token(user["id"], user["role"], user["name"], provider_id)
    refresh, jti, exp = create_refresh_token(user["id"])
    now_ts = datetime.now(timezone.utc).timestamp()
    jtis = {k: v for k, v in user.get("refreshJtis", {}).items() if v > now_ts}
    jtis[jti] = exp.timestamp()
    user["refreshJtis"] = jtis
    users.update(user)
    result = {
        "accessToken": access,
        "refreshToken": refresh,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]},
    }
    if provider_id:
        result["user"]["providerId"] = provider_id
        result["user"]["providerStatus"] = provider_status
    return result
