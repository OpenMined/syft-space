"""space wallet opt out

Revision ID: 2fd6d56a6876
Revises: d47fcdc8e8a9
Create Date: 2026-07-23 15:08:52.165705

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2fd6d56a6876"
down_revision: str | None = "d47fcdc8e8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "spaces",
        sa.Column(
            "wallet_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),  # existing rows predate the field
        ),
    )


def downgrade() -> None:
    op.drop_column("spaces", "wallet_opt_out")
