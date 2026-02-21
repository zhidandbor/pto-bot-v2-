from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_add_materials_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # materials_requests
    # ------------------------------------------------------------------
    op.create_table(
        "materials_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "draft_id",
            sa.String(length=12),
            nullable=False,
            unique=True,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "object_id",
            sa.Integer(),
            sa.ForeignKey("objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ps_number", sa.String(length=64), nullable=True),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("counter", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("request_number", sa.String(length=128), nullable=True),
        sa.Column("recipient_email", sa.String(length=256), nullable=True),
        sa.Column("user_full_name", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),  # draft | sent | cancelled | failed
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_materials_requests_draft_id",
        "materials_requests",
        ["draft_id"],
        unique=True,
    )
    op.create_index(
        "ix_materials_requests_chat_id",
        "materials_requests",
        ["chat_id"],
    )
    op.create_index(
        "ix_materials_requests_telegram_user_id",
        "materials_requests",
        ["telegram_user_id"],
    )
    op.create_index(
        "ix_materials_requests_request_date",
        "materials_requests",
        ["request_date"],
    )
    op.create_index(
        "ix_materials_requests_status",
        "materials_requests",
        ["status"],
    )

    # ------------------------------------------------------------------
    # materials_items
    # ------------------------------------------------------------------
    op.create_table(
        "materials_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("materials_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("type_mark", sa.String(length=256), nullable=True),
        sa.Column("qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
    )
    op.create_index(
        "ix_materials_items_request_id",
        "materials_items",
        ["request_id"],
    )

    # ------------------------------------------------------------------
    # materials_group_daily_counters
    # ------------------------------------------------------------------
    op.create_table(
        "materials_group_daily_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("counter_date", sa.Date(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_counter",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "counter_date",
            "chat_id",
            name="uq_mat_group_daily_counter",
        ),
    )
    op.create_index(
        "ix_mat_group_daily_counter_date_chat",
        "materials_group_daily_counters",
        ["counter_date", "chat_id"],
    )


def downgrade() -> None:
    op.drop_table("materials_group_daily_counters")
    op.drop_table("materials_items")
    op.drop_table("materials_requests")
