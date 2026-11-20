"""Dev stubs: print links to the console (like Laravel's `log` mail driver).
Replace the bodies with SMTP / SES / Resend / SendGrid in production."""

import logging

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


def send_password_reset_email(to: str, token: str) -> None:
    logger.info("Password reset for %s -> %s/reset-password?token=%s", to, settings.frontend_url, token)


def send_verification_email(to: str, token: str) -> None:
    logger.info("Verify email for %s -> %s/verify-email?token=%s", to, settings.frontend_url, token)
