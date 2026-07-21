import logging

from fastapi import APIRouter, Depends, Header, Request

from app.application.commands.subscriptions import ProcessWebhookHandler
from app.presentation import deps

logger = logging.getLogger("servicos-bebedouro.stripe")
router = APIRouter(prefix="/api/stripe", tags=["stripe"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    providers=Depends(deps.get_provider_repo),
    stripe=Depends(deps.get_stripe_service),
    users=Depends(deps.get_user_repo),
    email_service=Depends(deps.get_email_service),
):
    payload = await request.body()
    try:
        ProcessWebhookHandler(providers, stripe, users, email_service).handle(payload, stripe_signature)
    except Exception as error:
        logger.warning("Webhook do Stripe rejeitado: %s", error)
        return {"received": False}
    return {"received": True}
