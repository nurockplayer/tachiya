"""coupon redemption audit

Revision ID: 20260509_0002
Revises: 20260509_0001
Create Date: 2026-05-09 21:45:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0002"
down_revision: str | None = "20260509_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tachiya_coupon_redemption_audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("coupon_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("redemption_token", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tachiya_coupon_redemption_audit_events_coupon_id",
        "tachiya_coupon_redemption_audit_events",
        ["coupon_id"],
    )
    op.create_index(
        "ix_tachiya_coupon_redemption_audit_events_created_at",
        "tachiya_coupon_redemption_audit_events",
        ["created_at"],
    )
    op.create_index(
        "ix_tachiya_coupon_redemption_audit_events_idempotency_key",
        "tachiya_coupon_redemption_audit_events",
        ["idempotency_key"],
    )
    op.create_index(
        "ix_tachiya_coupon_redemption_audit_events_redemption_token",
        "tachiya_coupon_redemption_audit_events",
        ["redemption_token"],
    )
    op.create_index(
        "ix_tachiya_coupon_redemption_audit_events_status",
        "tachiya_coupon_redemption_audit_events",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_coupon_redemption_audit_events_status",
        table_name="tachiya_coupon_redemption_audit_events",
    )
    op.drop_index(
        "ix_tachiya_coupon_redemption_audit_events_redemption_token",
        table_name="tachiya_coupon_redemption_audit_events",
    )
    op.drop_index(
        "ix_tachiya_coupon_redemption_audit_events_idempotency_key",
        table_name="tachiya_coupon_redemption_audit_events",
    )
    op.drop_index(
        "ix_tachiya_coupon_redemption_audit_events_created_at",
        table_name="tachiya_coupon_redemption_audit_events",
    )
    op.drop_index(
        "ix_tachiya_coupon_redemption_audit_events_coupon_id",
        table_name="tachiya_coupon_redemption_audit_events",
    )
    op.drop_table("tachiya_coupon_redemption_audit_events")
