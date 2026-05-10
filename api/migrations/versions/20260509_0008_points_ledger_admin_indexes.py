"""points ledger admin indexes

Revision ID: 20260509_0008
Revises: 20260509_0007
Create Date: 2026-05-10 01:05:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260509_0008"
down_revision: str | None = "20260509_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tachiya_points_ledger_entry_type",
        "tachiya_points_ledger",
        ["entry_type"],
    )
    op.create_index(
        "ix_tachiya_points_ledger_created_at",
        "tachiya_points_ledger",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_points_ledger_created_at",
        table_name="tachiya_points_ledger",
    )
    op.drop_index(
        "ix_tachiya_points_ledger_entry_type",
        table_name="tachiya_points_ledger",
    )
