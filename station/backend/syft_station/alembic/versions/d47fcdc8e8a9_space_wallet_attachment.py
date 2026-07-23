"""space wallet attachment

Revision ID: d47fcdc8e8a9
Revises: a296941268de
Create Date: 2026-07-23 14:06:54.217585

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d47fcdc8e8a9"
down_revision: str | None = "a296941268de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("spaces", sa.Column("wallet_id", sa.Uuid(), nullable=True))


def downgrade() -> None:
    op.drop_column("spaces", "wallet_id")
