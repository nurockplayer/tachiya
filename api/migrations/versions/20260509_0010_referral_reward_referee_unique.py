"""referral reward referee unique

Revision ID: 20260509_0010
Revises: 20260509_0009
Create Date: 2026-05-10 16:43:00.000000
"""

from alembic import op


revision = "20260509_0010"
down_revision = "20260509_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_tachiya_referral_rewards_referee_id",
        "tachiya_referral_rewards",
        ["referee_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_tachiya_referral_rewards_referee_id",
        table_name="tachiya_referral_rewards",
    )
