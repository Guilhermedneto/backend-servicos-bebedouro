import logging

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger("servicos-bebedouro.stripe")


class PaymentUnavailableError(AppError):
    status_code = 503
    code = "PAYMENT_UNAVAILABLE"


class StripeService:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        if settings.stripe_enabled:
            import stripe

            stripe.api_key = settings.stripe_secret_key
            self._stripe = stripe
        else:
            self._stripe = None

    @property
    def enabled(self) -> bool:
        return self._stripe is not None

    def create_checkout_session(
        self,
        *,
        provider_id: str,
        email: str,
        plan: str,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
        customer_id: str | None,
    ) -> dict:
        if not self._stripe:
            raise PaymentUnavailableError("Pagamento indisponível no momento.")
        price_id = self._settings.stripe_price_id(plan, billing_cycle)
        if not price_id:
            raise PaymentUnavailableError(
                "Preço do plano não configurado no Stripe.", code="STRIPE_PRICE_MISSING"
            )
        params = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": provider_id,
            "metadata": {"providerId": provider_id, "plan": plan, "billingCycle": billing_cycle},
            "subscription_data": {"metadata": {"providerId": provider_id, "plan": plan}},
        }
        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = email
        session = self._stripe.checkout.Session.create(**params)
        return {"url": session.url, "sessionId": session.id}

    def construct_event(self, payload: bytes, signature: str) -> dict:
        if not self._stripe:
            raise PaymentUnavailableError("Pagamento indisponível no momento.")
        return self._stripe.Webhook.construct_event(
            payload, signature, self._settings.stripe_webhook_secret
        )

    def cancel_subscription(self, subscription_id: str) -> None:
        if not self._stripe or not subscription_id:
            return
        try:
            self._stripe.Subscription.cancel(subscription_id)
        except Exception as error:  # cancelamento é best-effort
            logger.warning("Falha ao cancelar assinatura %s: %s", subscription_id, error)
