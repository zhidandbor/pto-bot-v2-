from __future__ import annotations

import email.mime.multipart
import email.mime.text
import re
from dataclasses import dataclass
from email.mime.application import MIMEApplication

import aiosmtplib

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# CR / LF — запрещенные символы в заголовках email (RFC 5322)
_HEADER_INJECT_RE = re.compile(r"[\r\n]")


def _sanitize_header(value: str, field: str) -> str:
    """
    Удаляет CR/LF из заголовка email для предотвращения header injection.
    Логирует warning при обнаружении попытки инъекции.
    """
    if _HEADER_INJECT_RE.search(value):
        logger.warning(
            "email_header_injection_attempt",
            field=field,
            value=value[:80],
        )
        return _HEADER_INJECT_RE.sub("", value)
    return value


def _sanitize_filename(name: str) -> str:
    """
    Удаляет CR/LF и двойные кавычки из имени файла для Content-Disposition.
    Двойная кавычка в имени позволяет выйти из квотированной строки filename="...".
    """
    clean = _HEADER_INJECT_RE.sub("", name)
    return clean.replace('"', "")


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

        # FIX: санитация заголовков до подстановки в сообщение
        safe_to = _sanitize_header(to_email, "To")
        safe_subject = _sanitize_header(subject, "Subject")
        safe_filename = _sanitize_filename(attachment_filename)

        msg = email.mime.multipart.MIMEMultipart()
        msg["From"] = self.settings.mail_sender
        msg["To"] = safe_to
        msg["Subject"] = safe_subject

        msg.attach(email.mime.text.MIMEText(body, "plain", "utf-8"))

        part = MIMEApplication(attachment_bytes, Name=safe_filename)
        part["Content-Disposition"] = f'attachment; filename="{safe_filename}"'
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
            to=safe_to,
            subject=safe_subject,
            filename=safe_filename,
        )
