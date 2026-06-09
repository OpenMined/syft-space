"""add system_prompt to endpoints

Revision ID: e5f6a7b8c9d0
Revises: cd1cf206c880
Create Date: 2026-04-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "cd1cf206c880"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable ``system_prompt`` column to the ``endpoints`` table."""
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.add_column(
            sa.Column(
                "system_prompt",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Drop the ``system_prompt`` column from the ``endpoints`` table."""
    with op.batch_alter_table("endpoints") as batch_op:
        batch_op.drop_column("system_prompt")
