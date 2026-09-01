"""add satellite id to marketplaces

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-31 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the satellite registration column to ``marketplaces``.

    Nullable: an existing row has not registered yet, and NULL is what the
    registrar reads as "no satellite known, get-or-create one".
    """
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.add_column(
            sa.Column(
                "satellite_id",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Drop the satellite registration column from ``marketplaces``."""
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.drop_column("satellite_id")
