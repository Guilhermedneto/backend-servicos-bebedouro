from fastapi import APIRouter

from app.domain.plans import PLAN_PHOTO_LIMITS, PLAN_PRICING

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("")
def list_plans():
    """Catálogo público de planos: preços, limites de foto e recursos, para a UI."""
    return {
        "free": {
            "name": "Gratuito",
            "photoLimit": PLAN_PHOTO_LIMITS["free"],
            "pricing": None,
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
            "features": [
                "Tudo do Essencial",
                "Até 10 fotos",
                "Aparece no topo das buscas",
                "Selo de destaque e vitrine na página inicial",
            ],
        },
    }
