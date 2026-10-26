"""drop the benchmark card tables

Benchmark results stay inside the Space and are read from the benchmark's own
jobs, so ``endpoint_quality_cards`` and ``benchmark_settings`` are unused.
Downgrade recreates them empty.

Revision ID: b7d2e4f19a60
Revises: f8bb6df81871
Create Date: 2026-10-25 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e4f19a60"
down_revision: str | None = "f8bb6df81871"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("benchmark_settings")
    op.drop_index(
        "idx_quality_card_endpoint_checked", table_name="endpoint_quality_cards"
    )
    op.drop_index(
        op.f("ix_endpoint_quality_cards_id"), table_name="endpoint_quality_cards"
    )
    op.drop_table("endpoint_quality_cards")


def downgrade() -> None:
    op.create_table(
        "endpoint_quality_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("fabrication_rate", sa.Float(), nullable=True),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("reliable", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("retracted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_endpoint_quality_cards_id"),
        "endpoint_quality_cards",
        ["id"],
        unique=False,
    )
    op.create_index(
        "idx_quality_card_endpoint_checked",
        "endpoint_quality_cards",
        ["endpoint_id", "checked_at"],
        unique=False,
    )
    op.create_table(
        "benchmark_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "mode",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="off",
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
