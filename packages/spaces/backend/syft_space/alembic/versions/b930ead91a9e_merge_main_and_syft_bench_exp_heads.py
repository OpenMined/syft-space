"""merge main and syft-bench-exp heads

Revision ID: b930ead91a9e
Revises: b7c8d9e0f1a2, f7c2d9e4a1b3
Create Date: 2026-11-22 09:02:02.462503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # Added for SQLModel support


# revision identifiers, used by Alembic.
revision: str = 'b930ead91a9e'
down_revision: Union[str, None] = ('b7c8d9e0f1a2', 'f7c2d9e4a1b3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
