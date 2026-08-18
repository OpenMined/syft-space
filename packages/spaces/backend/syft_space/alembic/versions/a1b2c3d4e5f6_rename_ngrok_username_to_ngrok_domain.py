"""rename ngrok_username to ngrok_domain

Revision ID: a1b2c3d4e5f6
Revises: 616fe141adf9
Create Date: 2026-03-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "616fe141adf9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("ngrok_domain", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.drop_column("settings", "ngrok_username")


def downgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("ngrok_username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.drop_column("settings", "ngrok_domain")
