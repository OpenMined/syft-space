"""merge migration heads

Revision ID: f0a1b2c3d4e5
Revises: d9b3cb044bc7, e5f6a7b8c9d0
Create Date: 2026-06-05 15:35:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "f0a1b2c3d4e5"
down_revision: tuple[str, str] | None = ("d9b3cb044bc7", "e5f6a7b8c9d0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
