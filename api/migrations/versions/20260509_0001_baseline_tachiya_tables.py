"""baseline tachiya tables

Revision ID: 20260509_0001
Revises:
Create Date: 2026-05-09 21:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tachiya_demo_coupons",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("coupon_id", sa.String(), nullable=False),
        sa.Column("voucher_code", sa.String(), nullable=False),
        sa.Column("saleor_voucher_id", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("redemption_token", sa.String(), nullable=True),
        sa.Column("coupon_type", sa.String(), nullable=False),
        sa.Column("tcg_cost", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("redemption_token"),
        sa.UniqueConstraint("voucher_code"),
    )
    op.create_index(
        "ix_tachiya_demo_coupons_coupon_id",
        "tachiya_demo_coupons",
        ["coupon_id"],
    )
    op.create_index(
        "ix_tachiya_demo_coupons_status",
        "tachiya_demo_coupons",
        ["status"],
    )
    op.create_index(
        "ix_tachiya_demo_coupons_created_at",
        "tachiya_demo_coupons",
        ["created_at"],
    )

    op.create_table(
        "tachiya_identity_audit_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tachiya_identity_audit_events_action",
        "tachiya_identity_audit_events",
        ["action"],
    )
    op.create_index(
        "ix_tachiya_identity_audit_events_actor",
        "tachiya_identity_audit_events",
        ["actor"],
    )
    op.create_index(
        "ix_tachiya_identity_audit_events_created_at",
        "tachiya_identity_audit_events",
        ["created_at"],
    )
    op.create_index(
        "ix_tachiya_identity_audit_events_source",
        "tachiya_identity_audit_events",
        ["source"],
    )
    op.create_index(
        "ix_tachiya_identity_audit_events_target",
        "tachiya_identity_audit_events",
        ["target"],
    )

    op.create_table(
        "tachiya_identity_mappings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("saleor_customer_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_subject", sa.String(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_subject",
            name="uq_tachiya_identity_provider_subject",
        ),
    )
    op.create_index(
        "ix_tachiya_identity_mappings_external_subject",
        "tachiya_identity_mappings",
        ["external_subject"],
    )
    op.create_index(
        "ix_tachiya_identity_mappings_provider",
        "tachiya_identity_mappings",
        ["provider"],
    )
    op.create_index(
        "ix_tachiya_identity_mappings_saleor_customer_id",
        "tachiya_identity_mappings",
        ["saleor_customer_id"],
    )

    op.create_table(
        "tachiya_points_ledger",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), server_default="manual", nullable=False),
        sa.Column("reference_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "entry_type",
            "reference_id",
            name="uq_tachiya_points_ledger_idempotency",
        ),
    )
    op.create_index(
        "ix_tachiya_points_ledger_reference_id",
        "tachiya_points_ledger",
        ["reference_id"],
    )
    op.create_index(
        "ix_tachiya_points_ledger_source_type",
        "tachiya_points_ledger",
        ["source_type"],
    )
    op.create_index(
        "ix_tachiya_points_ledger_user_id", "tachiya_points_ledger", ["user_id"]
    )

    op.create_table(
        "tachiya_referral_relationships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("referrer_id", sa.String(), nullable=False),
        sa.Column("referee_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referee_id"),
    )
    op.create_index(
        "ix_tachiya_referral_relationships_referee_id",
        "tachiya_referral_relationships",
        ["referee_id"],
    )
    op.create_index(
        "ix_tachiya_referral_relationships_referrer_id",
        "tachiya_referral_relationships",
        ["referrer_id"],
    )

    op.create_table(
        "tachiya_referral_rewards",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("referrer_id", sa.String(), nullable=False),
        sa.Column("referee_id", sa.String(), nullable=False),
        sa.Column("order_total_amount", sa.Integer(), nullable=False),
        sa.Column("reward_points", sa.Integer(), nullable=False),
        sa.Column("ledger_entry_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index(
        "ix_tachiya_referral_rewards_order_id", "tachiya_referral_rewards", ["order_id"]
    )
    op.create_index(
        "ix_tachiya_referral_rewards_referee_id",
        "tachiya_referral_rewards",
        ["referee_id"],
    )
    op.create_index(
        "ix_tachiya_referral_rewards_referrer_id",
        "tachiya_referral_rewards",
        ["referrer_id"],
    )

    op.create_table(
        "tachiya_webhook_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_tachiya_webhook_events_event_id", "tachiya_webhook_events", ["event_id"]
    )
    op.create_index(
        "ix_tachiya_webhook_events_event_type",
        "tachiya_webhook_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tachiya_webhook_events_event_type", table_name="tachiya_webhook_events"
    )
    op.drop_index(
        "ix_tachiya_webhook_events_event_id", table_name="tachiya_webhook_events"
    )
    op.drop_table("tachiya_webhook_events")

    op.drop_index(
        "ix_tachiya_referral_rewards_referrer_id", table_name="tachiya_referral_rewards"
    )
    op.drop_index(
        "ix_tachiya_referral_rewards_referee_id", table_name="tachiya_referral_rewards"
    )
    op.drop_index(
        "ix_tachiya_referral_rewards_order_id", table_name="tachiya_referral_rewards"
    )
    op.drop_table("tachiya_referral_rewards")

    op.drop_index(
        "ix_tachiya_referral_relationships_referrer_id",
        table_name="tachiya_referral_relationships",
    )
    op.drop_index(
        "ix_tachiya_referral_relationships_referee_id",
        table_name="tachiya_referral_relationships",
    )
    op.drop_table("tachiya_referral_relationships")

    op.drop_index(
        "ix_tachiya_points_ledger_user_id", table_name="tachiya_points_ledger"
    )
    op.drop_index(
        "ix_tachiya_points_ledger_source_type", table_name="tachiya_points_ledger"
    )
    op.drop_index(
        "ix_tachiya_points_ledger_reference_id", table_name="tachiya_points_ledger"
    )
    op.drop_table("tachiya_points_ledger")

    op.drop_index(
        "ix_tachiya_identity_mappings_saleor_customer_id",
        table_name="tachiya_identity_mappings",
    )
    op.drop_index(
        "ix_tachiya_identity_mappings_provider", table_name="tachiya_identity_mappings"
    )
    op.drop_index(
        "ix_tachiya_identity_mappings_external_subject",
        table_name="tachiya_identity_mappings",
    )
    op.drop_table("tachiya_identity_mappings")

    op.drop_index(
        "ix_tachiya_identity_audit_events_target",
        table_name="tachiya_identity_audit_events",
    )
    op.drop_index(
        "ix_tachiya_identity_audit_events_source",
        table_name="tachiya_identity_audit_events",
    )
    op.drop_index(
        "ix_tachiya_identity_audit_events_created_at",
        table_name="tachiya_identity_audit_events",
    )
    op.drop_index(
        "ix_tachiya_identity_audit_events_actor",
        table_name="tachiya_identity_audit_events",
    )
    op.drop_index(
        "ix_tachiya_identity_audit_events_action",
        table_name="tachiya_identity_audit_events",
    )
    op.drop_table("tachiya_identity_audit_events")

    op.drop_index(
        "ix_tachiya_demo_coupons_created_at", table_name="tachiya_demo_coupons"
    )
    op.drop_index("ix_tachiya_demo_coupons_status", table_name="tachiya_demo_coupons")
    op.drop_index(
        "ix_tachiya_demo_coupons_coupon_id", table_name="tachiya_demo_coupons"
    )
    op.drop_table("tachiya_demo_coupons")
