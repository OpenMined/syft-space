"""space restart required

Revision ID: 7b9962a74b24
Revises: 473130f36a71
Create Date: 2026-08-03 14:53:28.494361

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b9962a74b24"
down_revision: str | None = "473130f36a71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "spaces",
        sa.Column(
            "restart_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),  # existing rows predate the field
        ),
    )


def downgrade() -> None:
    op.drop_column("spaces", "restart_required")
