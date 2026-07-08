import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("servicos-bebedouro.email")


class SendGridEmailService:
    def send(self, to: str, subject: str, html: str) -> None:
        settings = get_settings()
        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {settings.sendgrid_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": settings.email_from, "name": settings.email_from_name},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=10.0,
        )
        if response.status_code >= 400:
            logger.error("Falha ao enviar e-mail via SendGrid (%s): %s", response.status_code, response.text)


class ConsoleEmailService:
    """Dev fallback when SENDGRID_API_KEY is not configured: logs the e-mail instead of sending."""

    def send(self, to: str, subject: str, html: str) -> None:
        logger.info("[EMAIL DEV] to=%s | subject=%s | body=%s", to, subject, html)


def build_email_service():
    if get_settings().sendgrid_api_key:
        return SendGridEmailService()
    return ConsoleEmailService()
