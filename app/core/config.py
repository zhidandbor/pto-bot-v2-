from __future__ import annotations

from typing import Literal

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr = Field(alias="BOT_TOKEN")
    bot_mode: Literal["polling", "webhook"] = Field(default="polling", alias="BOT_MODE")

    webhook_url: str = Field(default="", alias="WEBHOOK_URL")
    webhook_host: str = Field(default="0.0.0.0", alias="WEBHOOK_HOST")
    webhook_port: int = Field(default=8080, alias="WEBHOOK_PORT")
    webhook_path: str = Field(default="/webhook", alias="WEBHOOK_PATH")

    superadmin_id: int = Field(alias="SUPERADMIN_ID")

    database_url: str = Field(alias="DATABASE_URL")

    default_recipient_email: str = Field(default="", alias="DEFAULT_RECIPIENT_EMAIL")
    default_cooldown_minutes: int = Field(default=30, alias="DEFAULT_COOLDOWN_MINUTES")

    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: SecretStr = Field(default=SecretStr(""), alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_starttls: bool = Field(default=True, alias="SMTP_STARTTLS")
    mail_sender: str = Field(default="", alias="MAIL_SENDER")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")

    context_ttl_seconds: int = Field(default=3600, alias="CONTEXT_TTL_SECONDS")
    pending_action_ttl_seconds: int = Field(default=600, alias="PENDING_ACTION_TTL_SECONDS")