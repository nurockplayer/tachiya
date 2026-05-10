"""webhook event received_at index

Revision ID: 20260509_0009
Revises: 20260509_0008
Create Date: 2026-05-10 01:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260509_0009"
down_revision: str | None = "20260509_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tachiya_webhook_events_received_at",
        "tachiya_webhook_events",
        ["received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_webhook_events_received_at",
        table_name="tachiya_webhook_events",
    )
