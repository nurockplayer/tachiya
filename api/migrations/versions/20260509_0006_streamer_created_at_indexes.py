"""streamer created_at indexes

Revision ID: 20260509_0006
Revises: 20260509_0005
Create Date: 2026-05-10 00:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260509_0006"
down_revision: str | None = "20260509_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tachiya_streamer_profiles_created_at",
        "tachiya_streamer_profiles",
        ["created_at"],
    )
    op.create_index(
        "ix_tachiya_streamer_product_assignments_created_at",
        "tachiya_streamer_product_assignments",
        ["created_at"],
    )
    op.create_index(
        "ix_tachiya_streamer_revenue_share_records_created_at",
        "tachiya_streamer_revenue_share_records",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_streamer_revenue_share_records_created_at",
        table_name="tachiya_streamer_revenue_share_records",
    )
    op.drop_index(
        "ix_tachiya_streamer_product_assignments_created_at",
        table_name="tachiya_streamer_product_assignments",
    )
    op.drop_index(
        "ix_tachiya_streamer_profiles_created_at",
        table_name="tachiya_streamer_profiles",
    )
