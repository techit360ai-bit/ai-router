import pgvector.sqlalchemy
"""fix_embeddings

Revision ID: 79e83ff518e5
Revises: 323a1fc13be9
Create Date: 2026-04-13 22:03:39.670224
"""
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy as pgvector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "79e83ff518e5"
down_revision = "323a1fc13be9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert existing ARRAY columns to pgvector VECTOR type
    op.alter_column("idea_embeddings", "embedding",
        existing_type=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
        type_=pgvector.Vector(dim=1536),
        existing_nullable=True
    )

    op.alter_column("user_skill_embeddings", "embedding",
        existing_type=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
        type_=pgvector.Vector(dim=1536),
        existing_nullable=True
    )


def downgrade() -> None:
    # Revert back to ARRAY
    op.alter_column("user_skill_embeddings", "embedding",
        existing_type=pgvector.Vector(dim=1536),
        type_=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
        existing_nullable=True
    )

    op.alter_column("idea_embeddings", "embedding",
        existing_type=pgvector.Vector(dim=1536),
        type_=postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)),
        existing_nullable=True
    )
