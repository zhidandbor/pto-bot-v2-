from __future__ import annotations

from datetime import datetime, date
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_allowed_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Group(Base):
    __tablename__ = "groups"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)

    ps_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ps_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    work_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)

    work_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    contract_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    request_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(256), nullable=True)

    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    object_root_id: Mapped[int | None] = mapped_column(ForeignKey("objects.id", ondelete="SET NULL"), nullable=True)
    object_root: Mapped["Object | None"] = relationship(remote_side=[id])

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ObjectGroupLink(Base):
    __tablename__ = "object_group_links"
    __table_args__ = (UniqueConstraint("object_id", "chat_id", name="uq_object_group_links_object_chat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[int] = mapped_column(ForeignKey("objects.id", ondelete="CASCADE"), nullable=False)
    chat_id: Mapped[int] = mapped_column(ForeignKey("groups.chat_id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RateLimit(Base):
    __tablename__ = "rate_limits"
    __table_args__ = (UniqueConstraint("scope_type", "scope_id", name="uq_rate_limits_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    last_request_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExcelImport(Base):
    __tablename__ = "excel_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    imported_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    errors_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class UserContext(Base):
    __tablename__ = "user_contexts"
    __table_args__ = (UniqueConstraint("telegram_user_id", "chat_id", name="uq_user_contexts_user_chat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    selected_object_id: Mapped[int | None] = mapped_column(ForeignKey("objects.id", ondelete="SET NULL"), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pending_command: Mapped[str | None] = mapped_column(String(256), nullable=True)
    pending_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
