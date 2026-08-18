"""add reason to space requests

Revision ID: 90a7ee9e38d9
Revises: 1ae48660264f
Create Date: 2026-07-21 12:50:17.957088

"""

from collections.abc import Sequence

import sqlmodel  # Added for SQLModel support
from alembic import op
from sqlalchemy import Column

# revision identifiers, used by Alembic.
revision: str = "90a7ee9e38d9"
down_revision: str | None = "1ae48660264f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "space_requests",
        Column(
            "reason",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",  # existing rows predate the field
        ),
    )


def downgrade() -> None:
    op.drop_column("space_requests", "reason")
