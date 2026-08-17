"""add verified production decision outcomes

Revision ID: bc23de45fa67
Revises: ab12cd34ef56
Create Date: 2026-08-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "bc23de45fa67"
down_revision: Union[str, None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "decision_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("policy_id", sa.String(length=120), nullable=False),
        sa.Column("predicted_score", sa.Float(), nullable=True),
        sa.Column("predicted_probability", sa.Float(), nullable=True),
        sa.Column("predicted_positive", sa.Boolean(), nullable=True),
        sa.Column("observed_positive", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("evidence", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", "domain", name="uq_decision_outcome_domain"),
    )
    op.create_index("idx_decision_outcome_policy_domain", "decision_outcomes", ["policy_id", "domain"])
    op.create_index("idx_decision_outcome_observed", "decision_outcomes", ["observed_at"])


def downgrade() -> None:
    op.drop_index("idx_decision_outcome_observed", table_name="decision_outcomes")
    op.drop_index("idx_decision_outcome_policy_domain", table_name="decision_outcomes")
    op.drop_table("decision_outcomes")
