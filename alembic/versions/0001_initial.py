from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("full_name", sa.String(length=256), nullable=True),
        sa.Column("is_allowed_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])

    op.create_table(
        "admins",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "groups",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dedup_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("ps_number", sa.String(length=64), nullable=True),
        sa.Column("ps_name", sa.String(length=256), nullable=True),
        sa.Column("work_type", sa.String(length=128), nullable=True),
        sa.Column("title_name", sa.String(length=256), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("work_start", sa.Date(), nullable=True),
        sa.Column("work_end", sa.Date(), nullable=True),
        sa.Column("contract_number", sa.String(length=128), nullable=True),
        sa.Column("contract_start", sa.Date(), nullable=True),
        sa.Column("contract_end", sa.Date(), nullable=True),
        sa.Column("request_number", sa.String(length=128), nullable=True),
        sa.Column("customer", sa.String(length=256), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("object_root_id", sa.Integer(), sa.ForeignKey("objects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_objects_ps_number", "objects", ["ps_number"])
    op.create_index("ix_objects_ps_name", "objects", ["ps_name"])
    op.create_index("ix_objects_title_name", "objects", ["title_name"])
    op.create_index("ix_objects_work_type", "objects", ["work_type"])

    op.create_table(
        "object_group_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("object_id", sa.Integer(), sa.ForeignKey("objects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), sa.ForeignKey("groups.chat_id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("object_id", "chat_id", name="uq_object_group_links_object_chat"),
    )
    op.create_index("ix_object_group_links_chat_id", "object_group_links", ["chat_id"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.String(length=2048), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_type", "scope_id", name="uq_rate_limits_scope"),
    )
    op.create_index("ix_rate_limits_scope", "rate_limits", ["scope_type", "scope_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "excel_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_name", sa.String(length=256), nullable=False),
        sa.Column("imported_by", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("errors_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_excel_imports_started_at", "excel_imports", ["started_at"])

    op.create_table(
        "user_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("selected_object_id", sa.Integer(), sa.ForeignKey("objects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_command", sa.String(length=256), nullable=True),
        sa.Column("pending_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pending_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("telegram_user_id", "chat_id", name="uq_user_contexts_user_chat"),
    )
    op.create_index("ix_user_contexts_user_chat", "user_contexts", ["telegram_user_id", "chat_id"])


def downgrade() -> None:
    op.drop_table("user_contexts")
    op.drop_table("excel_imports")
    op.drop_table("audit_log")
    op.drop_table("rate_limits")
    op.drop_table("settings")
    op.drop_table("object_group_links")
    op.drop_table("objects")
    op.drop_table("groups")
    op.drop_table("admins")
    op.drop_table("users")