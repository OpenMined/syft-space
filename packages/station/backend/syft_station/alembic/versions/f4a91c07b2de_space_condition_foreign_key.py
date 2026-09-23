"""space_conditions.space_id gets its foreign key

Revision ID: f4a91c07b2de
Revises: e2c7a1b40f93
Create Date: 2026-09-22 15:40:00.000000

The conditions table was created without the constraint, so the ORM could not
declare a relationship over it. SQLite can't ALTER a constraint in, so the
table is rebuilt (batch mode) — and any orphan rows are dropped first, since
FK enforcement is on (SQLiteConfig.enable_foreign_keys) and the rebuild would
otherwise fail on them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a91c07b2de"
down_revision: str | None = "e2c7a1b40f93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM space_conditions WHERE space_id NOT IN (SELECT id FROM spaces)"
        )
    )
    with op.batch_alter_table("space_conditions", schema=None) as batch:
        batch.create_foreign_key(
            "fk_space_conditions_space_id", "spaces", ["space_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("space_conditions", schema=None) as batch:
        batch.drop_constraint("fk_space_conditions_space_id", type_="foreignkey")
