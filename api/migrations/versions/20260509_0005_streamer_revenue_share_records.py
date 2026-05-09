"""streamer revenue share records

Revision ID: 20260509_0005
Revises: 20260509_0004
Create Date: 2026-05-09 23:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0005"
down_revision: str | None = "20260509_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tachiya_streamer_revenue_share_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("streamer_profile_id", sa.String(), nullable=False),
        sa.Column("streamer_slug", sa.String(), nullable=False),
        sa.Column("gross_amount", sa.Integer(), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("share_amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["streamer_profile_id"], ["tachiya_streamer_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            "streamer_slug",
            name="uq_tachiya_streamer_revenue_share_order_streamer",
        ),
    )
    op.create_index(
        "ix_tachiya_streamer_revenue_share_records_order_id",
        "tachiya_streamer_revenue_share_records",
        ["order_id"],
    )
    op.create_index(
        "ix_tachiya_streamer_revenue_share_records_status",
        "tachiya_streamer_revenue_share_records",
        ["status"],
    )
    op.create_index(
        "ix_tachiya_streamer_revenue_share_records_streamer_profile_id",
        "tachiya_streamer_revenue_share_records",
        ["streamer_profile_id"],
    )
    op.create_index(
        "ix_tachiya_streamer_revenue_share_records_streamer_slug",
        "tachiya_streamer_revenue_share_records",
        ["streamer_slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_streamer_revenue_share_records_streamer_slug",
        table_name="tachiya_streamer_revenue_share_records",
    )
    op.drop_index(
        "ix_tachiya_streamer_revenue_share_records_streamer_profile_id",
        table_name="tachiya_streamer_revenue_share_records",
    )
    op.drop_index(
        "ix_tachiya_streamer_revenue_share_records_status",
        table_name="tachiya_streamer_revenue_share_records",
    )
    op.drop_index(
        "ix_tachiya_streamer_revenue_share_records_order_id",
        table_name="tachiya_streamer_revenue_share_records",
    )
    op.drop_table("tachiya_streamer_revenue_share_records")
