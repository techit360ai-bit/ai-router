"""execution_only_router

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-08-10 19:00:00.000000

Remove AI-Router-owned commercial state and retain provider execution telemetry.
Historical migrations remain unchanged so existing installations can upgrade.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paywall_hits CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_purchases CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_ledger CASCADE")

    for column in (
        "subscription_tier", "plan_id", "subscription_credits_remaining",
        "subscription_resets_at", "payg_credits_balance", "total_credits_used",
    ):
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {column} CASCADE")

    for column in ("min_tier", "credit_cost"):
        op.execute(f"ALTER TABLE ai_prompts DROP COLUMN IF EXISTS {column} CASCADE")

    for column in (
        "credits_consumed", "from_subscription", "from_payg",
        "usd_charged_payg", "subscription_tier",
    ):
        op.execute(f"ALTER TABLE ai_outputs DROP COLUMN IF EXISTS {column} CASCADE")
    op.execute("ALTER TABLE ai_outputs RENAME COLUMN cost TO provider_cost_usd")

    op.execute("ALTER TABLE ai_usage_ledger DROP CONSTRAINT IF EXISTS ai_usage_ledger_request_id_key")
    op.execute("ALTER TABLE ai_usage_ledger DROP COLUMN IF EXISTS credits_consumed")
    op.execute("ALTER TABLE ai_usage_ledger RENAME COLUMN cost_usd TO provider_cost_usd")
    op.execute("ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS attempt_number INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS error_type VARCHAR(100)")
    op.execute("ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS error_message TEXT")
    op.execute("ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE ai_usage_ledger ADD COLUMN IF NOT EXISTS ip_protected BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_request_attempt ON ai_usage_ledger (request_id, attempt_number)")

    op.execute("ALTER TABLE agent_execution_logs DROP COLUMN IF EXISTS credits_consumed")
    op.execute("ALTER TABLE agent_execution_logs RENAME COLUMN total_cost TO provider_cost_usd")
    op.execute("ALTER TABLE generated_documents RENAME COLUMN credits_consumed TO tokens_used")
    op.execute("ALTER TABLE app_scaffolds RENAME COLUMN credits_consumed TO tokens_used")
    op.execute("ALTER TABLE referral_events DROP COLUMN IF EXISTS credits_earned")
    op.execute("ALTER TABLE referral_events DROP COLUMN IF EXISTS usd_credit")
    op.execute("DROP TYPE IF EXISTS subscriptiontierenum CASCADE")
    op.execute("DROP TYPE IF EXISTS billingeventtypeenum CASCADE")


def downgrade() -> None:
    raise RuntimeError(
        "This migration intentionally removes AI-Router billing state. "
        "Restore commercial data from backup into the future backend billing service."
    )
