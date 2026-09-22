"""benchmark connections and targets

Two tables and nothing else. Autogenerate also offered a pile of unrelated
drift — wallet and invoice column types, index shapes on ingestion jobs — that
predates this change; carrying it along would mean a migration nobody can read
and a rollback nobody can reason about.

Revision ID: f612f5b93dbc
Revises: a3f7c15e9b42
Create Date: 2026-09-14 18:47:18.599204

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f612f5b93dbc"
down_revision: str | None = "a3f7c15e9b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "benchmark_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("space_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("chroma_host", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("chroma_port", sa.Integer(), nullable=False),
        sa.Column("container", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        # Settings, and what the benchmark last said about itself. All
        # nullable: NULL throughout is the honest state — nothing was set and
        # nobody has asked.
        sa.Column("instrument", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("probe", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("capabilities", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("fields", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("defaults", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("reachable", sa.Boolean(), nullable=False),
        sa.Column("detail", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_benchmark_connections_id"),
        "benchmark_connections",
        ["id"],
        unique=False,
    )

    op.create_table(
        "benchmark_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("collection", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("probe", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("schedule", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("schedule_at", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("last_job", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # The endpoint goes, its benchmark settings go with it. The connection
        # only loosens: switching benchmarks must not throw away what the owner
        # configured per endpoint.
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["benchmark_connections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_id", name="uq_benchmark_target_endpoint"),
    )
    op.create_index(
        op.f("ix_benchmark_targets_id"), "benchmark_targets", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_targets_id"), table_name="benchmark_targets")
    op.drop_table("benchmark_targets")
    op.drop_index(
        op.f("ix_benchmark_connections_id"), table_name="benchmark_connections"
    )
    op.drop_table("benchmark_connections")
