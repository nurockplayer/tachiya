"""identity mapping created_at index

Revision ID: 20260509_0007
Revises: 20260509_0006
Create Date: 2026-05-10 00:50:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260509_0007"
down_revision: str | None = "20260509_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tachiya_identity_mappings_created_at",
        "tachiya_identity_mappings",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_identity_mappings_created_at",
        table_name="tachiya_identity_mappings",
    )
