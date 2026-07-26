from fastapi import APIRouter, Depends

from app.domain.plans import PLAN_PHOTO_LIMITS, PLAN_PRICING
from app.domain.trial import TRIAL_MONTHS, TRIAL_SLOTS
from app.presentation import deps

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("")
def list_plans(trial_claims=Depends(deps.get_trial_claim_repo)):
    """Catálogo público de planos: preços, limites de foto e recursos, para a UI."""
    slots_left = max(TRIAL_SLOTS - trial_claims.count(), 0)
    return {
        "free": {
            "name": "Gratuito",
            "photoLimit": PLAN_PHOTO_LIMITS["free"],
            "pricing": None,
            "trial": None,
            "features": [
                "Exibe nome, endereço e localização no mapa",
                "Sem fotos",
                "Sem botão de WhatsApp",
                "Sem avaliações",
            ],
        },
        "essential": {
            "name": "Essencial",
            "photoLimit": PLAN_PHOTO_LIMITS["essential"],
            "pricing": PLAN_PRICING["essential"],
            "trial": {
                "available": slots_left > 0,
                "months": TRIAL_MONTHS,
                "slotsLeft": slots_left,
            },
            "features": [
                "Perfil completo",
                "Até 5 fotos",
                "Botão de WhatsApp",
                "Avaliações de clientes",
            ],
        },
        "premium": {
            "name": "Premium",
            "photoLimit": PLAN_PHOTO_LIMITS["premium"],
            "pricing": PLAN_PRICING["premium"],
            "trial": None,
            "features": [
                "Tudo do Essencial",
                "Até 10 fotos",
                "Aparece no topo das buscas",
                "Selo de destaque e vitrine na página inicial",
            ],
        },
    }
