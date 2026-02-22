from __future__ import annotations

import email.mime.multipart
import email.mime.text
from dataclasses import dataclass
from email.mime.application import MIMEApplication

import aiosmtplib

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MaterialsEmailDispatcher:
    """Адаптер отправки Excel-заявки на e-mail.

    SmtpMailer поддерживает только text/plain без вложений,
    поэтому здесь используется отдельный aiosmtplib.send().
    """

    settings: Settings

    async def send_with_attachment(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        attachment_bytes: bytes,
        attachment_filename: str,
    ) -> None:
        if not self.settings.smtp_host:
            raise RuntimeError("SMTP_HOST не задан — отправка недоступна")

        msg = email.mime.multipart.MIMEMultipart()
        msg["From"] = self.settings.mail_sender
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))

        part = MIMEApplication(attachment_bytes, Name=attachment_filename)
        part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
        msg.attach(part)

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
        logger.info(
            "materials_email_sent",
            to=to_email,
            subject=subject,
            filename=attachment_filename,
        )
