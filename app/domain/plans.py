from enum import Enum


class Plan(str, Enum):
    FREE = "free"
    ESSENTIAL = "essential"
    PREMIUM = "premium"


class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"  # free sempre; pago após confirmação de pagamento
    PENDING_PAYMENT = "pending_payment"  # pago aguardando o Stripe confirmar
    CANCELED = "canceled"  # assinatura encerrada → volta a exibir como free


PAID_PLANS = {Plan.ESSENTIAL.value, Plan.PREMIUM.value}

PLAN_PHOTO_LIMITS = {
    Plan.FREE.value: 0,
    Plan.ESSENTIAL.value: 5,
    Plan.PREMIUM.value: 10,
}

# Preços em centavos de BRL. O ciclo "annual" é cobrado uma vez ao ano
# (12 × valor mensal com desconto) e exibido como "12x de R$ X".
PLAN_PRICING = {
    Plan.ESSENTIAL.value: {
        BillingCycle.MONTHLY.value: {"amount": 1800, "interval": "month", "installment": 1800},
        BillingCycle.ANNUAL.value: {"amount": 18000, "interval": "year", "installment": 1500},
    },
    Plan.PREMIUM.value: {
        BillingCycle.MONTHLY.value: {"amount": 2500, "interval": "month", "installment": 2500},
        BillingCycle.ANNUAL.value: {"amount": 24000, "interval": "year", "installment": 2000},
    },
}


def photo_limit(plan: str) -> int:
    return PLAN_PHOTO_LIMITS.get(plan, PLAN_PHOTO_LIMITS[Plan.ESSENTIAL.value])


def effective_plan(provider: dict) -> str:
    """Plano em vigor para exibição/regras: cai para 'free' se a assinatura não estiver ativa."""
    plan = provider.get("plan", Plan.ESSENTIAL.value)
    if plan == Plan.FREE.value:
        return Plan.FREE.value
    if provider.get("subscriptionStatus") != SubscriptionStatus.ACTIVE.value:
        return Plan.FREE.value
    return plan


def is_premium(provider: dict) -> bool:
    return effective_plan(provider) == Plan.PREMIUM.value


def shows_full_profile(provider: dict) -> bool:
    """Free exibe apenas nome, endereço e mapa; planos pagos ativos exibem tudo."""
    return effective_plan(provider) != Plan.FREE.value
