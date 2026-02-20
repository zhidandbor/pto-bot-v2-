from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SmtpMailer:
    settings: Settings

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((aiosmtplib.errors.SMTPException, OSError)),
    )
    async def send(self, *, to_email: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise RuntimeError("SMTP_HOST is empty")

        msg = EmailMessage()
        msg["From"] = self.settings.mail_sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username or None,
            password=self.settings.smtp_password.get_secret_value() or None,
            start_tls=self.settings.smtp_starttls,
            use_tls=self.settings.smtp_use_tls,
            timeout=30,
        )
        logger.info("smtp_sent", to=to_email, subject=subject)
