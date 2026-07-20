import logging
from dataclasses import dataclass

from app.application.interfaces import PhotoStorage, ProviderRepository
from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.domain.plans import (
    PAID_PLANS,
    BillingCycle,
    Plan,
    SubscriptionStatus,
    is_premium,
    photo_limit,
)
from app.infrastructure.stripe_service import PaymentUnavailableError, StripeService

logger = logging.getLogger("servicos-bebedouro.subscriptions")


def validate_plan_choice(plan: str, billing_cycle: str | None) -> None:
    if plan not in {p.value for p in Plan}:
        raise ValidationFailedError("Plano inválido.", code="INVALID_PLAN", details={"field": "plan"})
    if plan in PAID_PLANS:
        if billing_cycle not in {c.value for c in BillingCycle}:
            raise ValidationFailedError(
                "Selecione a periodicidade (mensal ou anual).",
                code="INVALID_BILLING_CYCLE",
                details={"field": "billingCycle"},
            )


def initial_subscription_status(plan: str) -> str:
    """Estado inicial da assinatura ao escolher um plano.

    - free: ativo na hora.
    - pago + Stripe configurado: aguardando pagamento.
    - pago + sem Stripe em dev: ativo na hora (permite testar sem gateway).
    - pago + sem Stripe em produção: pagamento indisponível.
    """
    if plan == Plan.FREE.value:
        return SubscriptionStatus.ACTIVE.value
    settings = get_settings()
    if settings.stripe_enabled:
        return SubscriptionStatus.PENDING_PAYMENT.value
    if settings.is_production:
        raise PaymentUnavailableError(
            "Pagamento indisponível no momento. Tente novamente mais tarde."
        )
    logger.warning("Stripe não configurado — ativando plano pago '%s' automaticamente (dev).", plan)
    return SubscriptionStatus.ACTIVE.value


def sync_premium_flag(provider: dict) -> None:
    provider["isPremium"] = is_premium(provider)


def _checkout_urls() -> tuple[str, str]:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/meu-perfil?pagamento=sucesso", f"{base}/meu-perfil?pagamento=cancelado"


def create_checkout(stripe: StripeService, provider: dict, plan: str, billing_cycle: str, email: str) -> dict:
    success_url, cancel_url = _checkout_urls()
    return stripe.create_checkout_session(
        provider_id=provider["id"],
        email=email,
        plan=plan,
        billing_cycle=billing_cycle,
        success_url=success_url,
        cancel_url=cancel_url,
        customer_id=provider.get("stripeCustomerId"),
    )


def _trim_photos_to_limit(provider: dict, storage: PhotoStorage, limit: int) -> None:
    photos = provider.get("photos", [])
    if len(photos) <= limit:
        return
    keep, remove = photos[:limit], photos[limit:]
    if keep and not any(p["isCover"] for p in keep):
        keep[0]["isCover"] = True
    provider["photos"] = keep
    for photo in remove:
        storage.delete(photo["blobName"])


@dataclass
class ChangePlanCommand:
    provider_id: str
    email: str
    plan: str
    billing_cycle: str | None


class ChangePlanHandler:
    def __init__(
        self, providers: ProviderRepository, storage: PhotoStorage, stripe: StripeService
    ) -> None:
        self._providers = providers
        self._storage = storage
        self._stripe = stripe

    def handle(self, cmd: ChangePlanCommand) -> dict:
        validate_plan_choice(cmd.plan, cmd.billing_cycle)
        provider = self._providers.get(cmd.provider_id)
        if not provider:
            raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")

        if cmd.plan == Plan.FREE.value:
            self._stripe.cancel_subscription(provider.get("stripeSubscriptionId") or "")
            provider["plan"] = Plan.FREE.value
            provider["billingCycle"] = None
            provider["subscriptionStatus"] = SubscriptionStatus.ACTIVE.value
            provider["stripeSubscriptionId"] = None
            _trim_photos_to_limit(provider, self._storage, photo_limit(Plan.FREE.value))
            sync_premium_flag(provider)
            self._providers.update(provider)
            return {"plan": Plan.FREE.value, "subscriptionStatus": SubscriptionStatus.ACTIVE.value}

        status = initial_subscription_status(cmd.plan)
        provider["plan"] = cmd.plan
        provider["billingCycle"] = cmd.billing_cycle
        provider["subscriptionStatus"] = status
        _trim_photos_to_limit(provider, self._storage, photo_limit(cmd.plan))
        sync_premium_flag(provider)
        self._providers.update(provider)

        if status == SubscriptionStatus.PENDING_PAYMENT.value:
            checkout = create_checkout(self._stripe, provider, cmd.plan, cmd.billing_cycle, cmd.email)
            return {"plan": cmd.plan, "subscriptionStatus": status, "checkoutUrl": checkout["url"]}
        return {"plan": cmd.plan, "subscriptionStatus": status}


@dataclass
class StartCheckoutCommand:
    provider_id: str
    email: str


class StartCheckoutHandler:
    """Recria a sessão de checkout de um plano pago que ainda está pendente de pagamento."""

    def __init__(self, providers: ProviderRepository, stripe: StripeService) -> None:
        self._providers = providers
        self._stripe = stripe

    def handle(self, cmd: StartCheckoutCommand) -> dict:
        provider = self._providers.get(cmd.provider_id)
        if not provider:
            raise NotFoundError("Prestador não encontrado.", code="PROVIDER_NOT_FOUND")
        plan = provider.get("plan")
        if plan not in PAID_PLANS:
            raise ValidationFailedError("Nenhum pagamento pendente para este plano.", code="NO_PENDING_PAYMENT")
        checkout = create_checkout(
            self._stripe, provider, plan, provider.get("billingCycle") or "monthly", cmd.email
        )
        return {"checkoutUrl": checkout["url"]}


class ProcessWebhookHandler:
    def __init__(self, providers: ProviderRepository, stripe: StripeService) -> None:
        self._providers = providers
        self._stripe = stripe

    def handle(self, payload: bytes, signature: str) -> None:
        event = self._stripe.construct_event(payload, signature)
        etype = event["type"]
        obj = event["data"]["object"]

        if etype == "checkout.session.completed":
            provider_id = (obj.get("metadata") or {}).get("providerId") or obj.get("client_reference_id")
            provider = self._providers.get(provider_id) if provider_id else None
            if not provider:
                logger.warning("Webhook checkout sem prestador correspondente: %s", provider_id)
                return
            provider["subscriptionStatus"] = SubscriptionStatus.ACTIVE.value
            provider["stripeCustomerId"] = obj.get("customer")
            provider["stripeSubscriptionId"] = obj.get("subscription")
            sync_premium_flag(provider)
            self._providers.update(provider)
            logger.info("Assinatura ativada para prestador %s", provider_id)

        elif etype in {"customer.subscription.deleted", "customer.subscription.updated"}:
            provider_id = (obj.get("metadata") or {}).get("providerId")
            provider = self._providers.get(provider_id) if provider_id else None
            if not provider:
                return
            active = etype == "customer.subscription.updated" and obj.get("status") == "active"
            provider["subscriptionStatus"] = (
                SubscriptionStatus.ACTIVE.value if active else SubscriptionStatus.CANCELED.value
            )
            sync_premium_flag(provider)
            self._providers.update(provider)
