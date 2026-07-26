import logging
from datetime import datetime, timezone

from app.application.commands.subscriptions import sync_premium_flag
from app.application.interfaces import EmailService, ProviderRepository, UserRepository
from app.core.config import get_settings
from app.domain.plans import SubscriptionStatus

logger = logging.getLogger("servicos-bebedouro.trial")


def _send_trial_ended_email(email_service: EmailService, provider: dict, to: str) -> None:
    app_name = get_settings().email_from_name
    email_service.send(
        to=to,
        subject="Período de avaliação encerrado — Serviços Bebedouro",
        html=(
            f"<p>Olá, {provider['name']}.</p>"
            f"<p>Seu período de avaliação gratuita do plano Essencial chegou ao fim.</p>"
            f"<p>Seu perfil passou a ser exibido publicamente como <strong>Gratuito</strong> — mas fique "
            f"tranquilo, suas fotos e avaliações continuam guardadas.</p>"
            f"<p>Para manter seu perfil completo, com fotos, WhatsApp e avaliações, contrate um plano "
            f"quando quiser pelo painel do prestador.</p>"
            f"<p>Com carinho,<br>Equipe {app_name}</p>"
        ),
    )


class ExpireTrialsHandler:
    """Roda periodicamente: encerra trials do Essencial que passaram dos 6 meses, sem
    apagar nenhum dado — apenas o perfil completo deixa de ser exibido publicamente."""

    def __init__(
        self, providers: ProviderRepository, users: UserRepository, email_service: EmailService
    ) -> None:
        self._providers = providers
        self._users = users
        self._email = email_service

    def handle(self) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        expired = self._providers.list_expired_trials(now_iso)
        for provider in expired:
            provider["subscriptionStatus"] = SubscriptionStatus.CANCELED.value
            sync_premium_flag(provider)
            self._providers.update(provider)
            user = self._users.get(provider["userId"])
            if user:
                _send_trial_ended_email(self._email, provider, user["email"])
            logger.info("Trial encerrado para o prestador %s", provider["id"])
        return len(expired)
