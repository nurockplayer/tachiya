"""streamer product assignments

Revision ID: 20260509_0004
Revises: 20260509_0003
Create Date: 2026-05-09 23:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0004"
down_revision: str | None = "20260509_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tachiya_streamer_product_assignments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("saleor_product_id", sa.String(), nullable=False),
        sa.Column("streamer_profile_id", sa.String(), nullable=False),
        sa.Column("streamer_slug", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["streamer_profile_id"], ["tachiya_streamer_profiles.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("saleor_product_id"),
    )
    op.create_index(
        "ix_tachiya_streamer_product_assignments_saleor_product_id",
        "tachiya_streamer_product_assignments",
        ["saleor_product_id"],
    )
    op.create_index(
        "ix_tachiya_streamer_product_assignments_streamer_profile_id",
        "tachiya_streamer_product_assignments",
        ["streamer_profile_id"],
    )
    op.create_index(
        "ix_tachiya_streamer_product_assignments_streamer_slug",
        "tachiya_streamer_product_assignments",
        ["streamer_slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_streamer_product_assignments_streamer_slug",
        table_name="tachiya_streamer_product_assignments",
    )
    op.drop_index(
        "ix_tachiya_streamer_product_assignments_streamer_profile_id",
        table_name="tachiya_streamer_product_assignments",
    )
    op.drop_index(
        "ix_tachiya_streamer_product_assignments_saleor_product_id",
        table_name="tachiya_streamer_product_assignments",
    )
    op.drop_table("tachiya_streamer_product_assignments")
