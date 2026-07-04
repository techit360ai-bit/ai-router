"""trust_engine_lite

Revision ID: d4f5e6a7b8c9
Revises: b6c1d9f2a4e7
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d4f5e6a7b8c9"
down_revision: Union[str, None] = "b6c1d9f2a4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_VALUES = (
    "UNVERIFIED",
    "PENDING",
    "VERIFIED",
    "EXPIRED",
    "FAILED",
    "DISCONNECTED",
)
SOURCE_VALUES = (
    "EMAIL",
    "PHONE",
    "GITHUB",
    "LINKEDIN",
    "DOMAIN",
    "WEBSITE",
    "ORGANIZATION",
    "DEPLOYMENT",
    "PRODUCT_ANALYTICS",
    "TEAM",
    "MILESTONE",
)


def _status_enum(create_type: bool = False) -> postgresql.ENUM:
    return postgresql.ENUM(
        *STATUS_VALUES,
        name="verificationstatusenum",
        create_type=create_type,
    )


def _source_enum(create_type: bool = False) -> postgresql.ENUM:
    return postgresql.ENUM(
        *SOURCE_VALUES,
        name="verificationsourceenum",
        create_type=create_type,
    )


def upgrade() -> None:
    bind = op.get_bind()
    _status_enum(create_type=True).create(bind, checkfirst=True)
    _source_enum(create_type=True).create(bind, checkfirst=True)
    op.execute("ALTER TYPE prompttypeenum ADD VALUE IF NOT EXISTS 'TRUST'")

    status_enum = _status_enum()
    source_enum = _source_enum()

    op.create_table(
        "trust_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("github_connected", sa.Boolean(), nullable=False),
        sa.Column("linkedin_connected", sa.Boolean(), nullable=False),
        sa.Column("domain_verified", sa.Boolean(), nullable=False),
        sa.Column("organization_verified", sa.Boolean(), nullable=False),
        sa.Column("deployment_live", sa.Boolean(), nullable=False),
        sa.Column("product_activity_verified", sa.Boolean(), nullable=False),
        sa.Column("github_repo_count", sa.Integer(), nullable=False),
        sa.Column("github_commit_count", sa.Integer(), nullable=False),
        sa.Column("github_contributor_count", sa.Integer(), nullable=False),
        sa.Column("github_last_activity_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("deployments_30d", sa.Integer(), nullable=False),
        sa.Column("last_deployment_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("mau", sa.Integer(), nullable=False),
        sa.Column("dau", sa.Integer(), nullable=False),
        sa.Column("growth_rate_pct", sa.Float(), nullable=False),
        sa.Column("retention_rate_pct", sa.Float(), nullable=False),
        sa.Column("verified_team_count", sa.Integer(), nullable=False),
        sa.Column("milestone_count", sa.Integer(), nullable=False),
        sa.Column("verification_status", status_enum, nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("badges", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("last_sync_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trust_profile_user", "trust_profiles", ["user_id"])
    op.create_index("idx_trust_profile_project", "trust_profiles", ["project_id"])
    op.create_index("idx_trust_profile_status", "trust_profiles", ["verification_status"])
    op.create_index("idx_trust_profile_score", "trust_profiles", ["trust_score"])

    op.create_table(
        "trust_verification_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("verification_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("verification_id"),
    )
    op.create_index(
        "idx_trust_history_user_created",
        "trust_verification_history",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_trust_history_subject",
        "trust_verification_history",
        ["subject_type", "subject_id", "created_at"],
    )
    op.create_index(
        "idx_trust_history_source_status",
        "trust_verification_history",
        ["source", "status"],
    )
    op.create_index("idx_trust_history_expiry", "trust_verification_history", ["expires_at"])
    op.create_index("idx_trust_history_hash", "trust_verification_history", ["metadata_hash"])

    op.create_table(
        "trust_timeline_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("visibility", sa.String(length=30), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_trust_timeline_user_created",
        "trust_timeline_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_trust_timeline_project_created",
        "trust_timeline_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "idx_trust_timeline_event",
        "trust_timeline_events",
        ["event_type", "created_at"],
    )
    op.create_index("idx_trust_timeline_visibility", "trust_timeline_events", ["visibility"])

    op.create_table(
        "trust_badge_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("badge_type", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("source", source_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_trust_badge_user_status",
        "trust_badge_snapshots",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_trust_badge_project_status",
        "trust_badge_snapshots",
        ["project_id", "status"],
    )
    op.create_index(
        "idx_trust_badge_type_expiry",
        "trust_badge_snapshots",
        ["badge_type", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_trust_badge_type_expiry", table_name="trust_badge_snapshots")
    op.drop_index("idx_trust_badge_project_status", table_name="trust_badge_snapshots")
    op.drop_index("idx_trust_badge_user_status", table_name="trust_badge_snapshots")
    op.drop_table("trust_badge_snapshots")

    op.drop_index("idx_trust_timeline_visibility", table_name="trust_timeline_events")
    op.drop_index("idx_trust_timeline_event", table_name="trust_timeline_events")
    op.drop_index("idx_trust_timeline_project_created", table_name="trust_timeline_events")
    op.drop_index("idx_trust_timeline_user_created", table_name="trust_timeline_events")
    op.drop_table("trust_timeline_events")

    op.drop_index("idx_trust_history_hash", table_name="trust_verification_history")
    op.drop_index("idx_trust_history_expiry", table_name="trust_verification_history")
    op.drop_index("idx_trust_history_source_status", table_name="trust_verification_history")
    op.drop_index("idx_trust_history_subject", table_name="trust_verification_history")
    op.drop_index("idx_trust_history_user_created", table_name="trust_verification_history")
    op.drop_table("trust_verification_history")

    op.drop_index("idx_trust_profile_score", table_name="trust_profiles")
    op.drop_index("idx_trust_profile_status", table_name="trust_profiles")
    op.drop_index("idx_trust_profile_project", table_name="trust_profiles")
    op.drop_index("idx_trust_profile_user", table_name="trust_profiles")
    op.drop_table("trust_profiles")

    bind = op.get_bind()
    _source_enum().drop(bind, checkfirst=True)
    _status_enum().drop(bind, checkfirst=True)
    # PostgreSQL enum values cannot be safely removed in a generic downgrade;
    # prompttypeenum.TRUST is intentionally left in place.
