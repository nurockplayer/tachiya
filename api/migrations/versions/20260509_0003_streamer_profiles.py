"""streamer profiles

Revision ID: 20260509_0003
Revises: 20260509_0002
Create Date: 2026-05-09 23:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0003"
down_revision: str | None = "20260509_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tachiya_streamer_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("saleor_collection_id", sa.String(), nullable=True),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("saleor_collection_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        "ix_tachiya_streamer_profiles_saleor_collection_id",
        "tachiya_streamer_profiles",
        ["saleor_collection_id"],
    )
    op.create_index(
        "ix_tachiya_streamer_profiles_slug",
        "tachiya_streamer_profiles",
        ["slug"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_streamer_profiles_slug",
        table_name="tachiya_streamer_profiles",
    )
    op.drop_index(
        "ix_tachiya_streamer_profiles_saleor_collection_id",
        table_name="tachiya_streamer_profiles",
    )
    op.drop_table("tachiya_streamer_profiles")
