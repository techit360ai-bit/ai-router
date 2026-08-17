"""add GSIS v2 persistence, recommendations, benchmarks, and config audit

Revision ID: cd34ef56a7b9
Revises: bc23de45fa67
Create Date: 2026-08-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "cd34ef56a7b9"
down_revision: Union[str, None] = "bc23de45fa67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json():
    return postgresql.JSON(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "gsis_v2_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("detected_stage", sa.String(length=20), nullable=False),
        sa.Column("declared_stage", sa.String(length=30), nullable=True),
        sa.Column("gsis", sa.Float(), nullable=True),
        sa.Column("stage_health", sa.Float(), nullable=True),
        sa.Column("momentum", sa.Float(), nullable=True),
        sa.Column("pmf", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("readiness_status", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("data_coverage", sa.Float(), nullable=True),
        sa.Column("health_classification", sa.String(length=30), nullable=True),
        sa.Column("bottleneck", sa.String(length=80), nullable=True),
        sa.Column("scorecard", _json(), nullable=False),
        sa.Column("calculated_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("idx_gsis_v2_profile_stage", "gsis_v2_profiles", ["detected_stage"])
    op.create_index("idx_gsis_v2_profile_updated", "gsis_v2_profiles", ["updated_at"])

    op.create_table(
        "gsis_v2_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("gsis", sa.Float(), nullable=True),
        sa.Column("detected_stage", sa.String(length=20), nullable=False),
        sa.Column("momentum", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("readiness_score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("data_coverage", sa.Float(), nullable=True),
        sa.Column("trigger", sa.String(length=80), nullable=False),
        sa.Column("scorecard", _json(), nullable=False),
        sa.Column("snapshotted_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gsis_v2_snapshot_project_time", "gsis_v2_snapshots", ["project_id", "snapshotted_at"])
    op.create_index("idx_gsis_v2_snapshot_stage", "gsis_v2_snapshots", ["detected_stage"])

    op.create_table(
        "gsis_v2_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("success_metric", sa.Text(), nullable=True),
        sa.Column("expected_impact", sa.String(length=20), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("time_horizon_days", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("outcome_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gsis_v2_recommendation_project", "gsis_v2_recommendations", ["project_id", "created_at"])

    op.create_table(
        "gsis_v2_recommendation_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=120), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=True),
        sa.Column("observed_value", sa.Float(), nullable=True),
        sa.Column("expected_value", sa.Float(), nullable=True),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("evidence", _json(), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["gsis_v2_recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id"),
    )

    op.create_table(
        "gsis_v2_benchmarks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=120), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("business_model", sa.String(length=60), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("geography", sa.String(length=100), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("p25", sa.Float(), nullable=True),
        sa.Column("median", sa.Float(), nullable=True),
        sa.Column("p75", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("as_of", sa.TIMESTAMP(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gsis_v2_benchmark_lookup", "gsis_v2_benchmarks", ["metric", "stage", "business_model", "industry", "geography"])

    op.create_table(
        "gsis_v2_config_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("config", _json(), nullable=False),
        sa.Column("changed_by", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gsis_v2_config_audit_version", "gsis_v2_config_audits", ["version", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_gsis_v2_config_audit_version", table_name="gsis_v2_config_audits")
    op.drop_table("gsis_v2_config_audits")
    op.drop_index("idx_gsis_v2_benchmark_lookup", table_name="gsis_v2_benchmarks")
    op.drop_table("gsis_v2_benchmarks")
    op.drop_table("gsis_v2_recommendation_outcomes")
    op.drop_index("idx_gsis_v2_recommendation_project", table_name="gsis_v2_recommendations")
    op.drop_table("gsis_v2_recommendations")
    op.drop_table("gsis_v2_snapshots")
    op.drop_index("idx_gsis_v2_profile_updated", table_name="gsis_v2_profiles")
    op.drop_index("idx_gsis_v2_profile_stage", table_name="gsis_v2_profiles")
    op.drop_table("gsis_v2_profiles")
