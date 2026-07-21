import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("servicos-bebedouro.email")


class ResendEmailService:
    def send(self, to: str, subject: str, html: str) -> None:
        settings = get_settings()
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{settings.email_from_name} <{settings.email_from}>",
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=10.0,
        )
        if response.status_code >= 400:
            logger.error("Falha ao enviar e-mail via Resend (%s): %s", response.status_code, response.text)


class ConsoleEmailService:
    """Dev fallback when RESEND_API_KEY is not configured: logs the e-mail instead of sending."""

    def send(self, to: str, subject: str, html: str) -> None:
        logger.info("[EMAIL DEV] to=%s | subject=%s | body=%s", to, subject, html)


def build_email_service():
    if get_settings().resend_api_key:
        return ResendEmailService()
    return ConsoleEmailService()
