"""create query_events table

Revision ID: bea0d8425000
Revises:
Create Date: 2026-04-01 12:25:36.699874

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bea0d8425000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "query_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint_slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("user_email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("revenue_amount", sa.Float(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("query_text", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_qe_tenant_dataset",
        "query_events",
        ["tenant_id", "dataset_id"],
        unique=False,
    )
    op.create_index(
        "idx_qe_tenant_endpoint",
        "query_events",
        ["tenant_id", "endpoint_id"],
        unique=False,
    )
    op.create_index(
        "idx_qe_tenant_timestamp",
        "query_events",
        ["tenant_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_qe_tenant_user", "query_events", ["tenant_id", "user_email"], unique=False
    )
    op.create_index(op.f("ix_query_events_id"), "query_events", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_query_events_id"), table_name="query_events")
    op.drop_index("idx_qe_tenant_user", table_name="query_events")
    op.drop_index("idx_qe_tenant_timestamp", table_name="query_events")
    op.drop_index("idx_qe_tenant_endpoint", table_name="query_events")
    op.drop_index("idx_qe_tenant_dataset", table_name="query_events")
    op.drop_table("query_events")

