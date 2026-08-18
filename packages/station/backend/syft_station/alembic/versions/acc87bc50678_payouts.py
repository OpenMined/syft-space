"""payouts

Revision ID: acc87bc50678
Revises: 2fd6d56a6876
Create Date: 2026-07-23 15:22:06.934144

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # Added for SQLModel support
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acc87bc50678"
down_revision: str | None = "2fd6d56a6876"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payouts_space_id"), "payouts", ["space_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payouts_space_id"), table_name="payouts")
    op.drop_table("payouts")
