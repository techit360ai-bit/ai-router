"""Add one-way database migration audit records.

Revision ID: fa34bc56de78
Revises: ef12ab34cd56
Create Date: 2026-09-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "fa34bc56de78"
down_revision: Union[str, None] = "ef12ab34cd56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "database_migration_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_location", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("operator", sa.String(length=255), nullable=False),
        sa.Column("alembic_revision", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("rows_imported", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_database_migration_audits_status"),
        sa.CheckConstraint("verification_status IN ('pending', 'verified', 'failed')", name="ck_database_migration_audits_verification_status"),
    )
    op.create_index("idx_database_migration_audits_source", "database_migration_audits", ["source_sha256", "started_at"])
    op.create_index("idx_database_migration_audits_status", "database_migration_audits", ["status", "verification_status"])


def downgrade() -> None:
    op.drop_index("idx_database_migration_audits_status", table_name="database_migration_audits")
    op.drop_index("idx_database_migration_audits_source", table_name="database_migration_audits")
    op.drop_table("database_migration_audits")
