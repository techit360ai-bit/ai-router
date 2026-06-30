"""ai_usage_ledger

Revision ID: b6c1d9f2a4e7
Revises: 79e83ff518e5
Create Date: 2026-06-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b6c1d9f2a4e7"
down_revision: Union[str, None] = "79e83ff518e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_ledger",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.String(length=100), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column("credits_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("idx_ai_usage_provider_model", "ai_usage_ledger", ["provider", "model"])
    op.create_index("idx_ai_usage_request_id", "ai_usage_ledger", ["request_id"])
    op.create_index("idx_ai_usage_task_type", "ai_usage_ledger", ["task_type"])
    op.create_index("idx_ai_usage_user_created", "ai_usage_ledger", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_ai_usage_user_created", table_name="ai_usage_ledger")
    op.drop_index("idx_ai_usage_task_type", table_name="ai_usage_ledger")
    op.drop_index("idx_ai_usage_request_id", table_name="ai_usage_ledger")
    op.drop_index("idx_ai_usage_provider_model", table_name="ai_usage_ledger")
    op.drop_table("ai_usage_ledger")
