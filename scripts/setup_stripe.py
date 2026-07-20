"""Cria (idempotente) os produtos e preços dos planos no Stripe e imprime os price IDs
para colar no .env / app settings.

Uso:
    STRIPE_SECRET_KEY=sk_test_xxx python scripts/setup_stripe.py

Cria 2 produtos (Essencial, Premium) e 4 preços recorrentes:
    essential mensal  R$ 18,00/mês
    essential anual   R$ 180,00/ano   (exibido como 12x de R$ 15,00)
    premium   mensal  R$ 25,00/mês
    premium   anual   R$ 240,00/ano   (exibido como 12x de R$ 20,00)
"""

import os
import sys

import stripe

sys.path.insert(0, ".")
from app.domain.plans import PLAN_PRICING  # noqa: E402

key = os.environ.get("STRIPE_SECRET_KEY", "")
if not key:
    print("Defina STRIPE_SECRET_KEY no ambiente.")
    sys.exit(1)
stripe.api_key = key

PRODUCTS = {
    "essential": {"name": "Serviços Bebedouro — Plano Essencial"},
    "premium": {"name": "Serviços Bebedouro — Plano Premium"},
}


def find_or_create_product(plan: str) -> str:
    lookup = f"sb_plan_{plan}"
    existing = stripe.Product.search(query=f"metadata['slug']:'{lookup}'").data
    if existing:
        return existing[0].id
    product = stripe.Product.create(name=PRODUCTS[plan]["name"], metadata={"slug": lookup})
    return product.id


def find_or_create_price(product_id: str, plan: str, cycle: str) -> str:
    cfg = PLAN_PRICING[plan][cycle]
    lookup_key = f"sb_{plan}_{cycle}"
    existing = stripe.Price.list(lookup_keys=[lookup_key], limit=1).data
    if existing:
        return existing[0].id
    price = stripe.Price.create(
        product=product_id,
        currency="brl",
        unit_amount=cfg["amount"],
        recurring={"interval": cfg["interval"]},
        lookup_key=lookup_key,
        metadata={"plan": plan, "cycle": cycle},
    )
    return price.id


env_lines = {}
for plan in ("essential", "premium"):
    product_id = find_or_create_product(plan)
    for cycle in ("monthly", "annual"):
        price_id = find_or_create_price(product_id, plan, cycle)
        env_key = f"STRIPE_PRICE_{plan.upper()}_{cycle.upper()}"
        env_lines[env_key] = price_id
        print(f"{plan} {cycle}: {price_id}")

print("\n# Cole no .env / app settings do backend:")
for k, v in env_lines.items():
    print(f"{k}={v}")
print(
    "\n# E configure o webhook no painel do Stripe apontando para:"
    "\n#   https://<backend>/api/stripe/webhook"
    "\n# eventos: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted"
    "\n# copie o 'Signing secret' para STRIPE_WEBHOOK_SECRET."
)
