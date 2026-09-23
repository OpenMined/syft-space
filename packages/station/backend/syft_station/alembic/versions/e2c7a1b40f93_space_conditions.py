"""space conditions replace the restart_required flag

Revision ID: e2c7a1b40f93
Revises: b8c4e1f70a35
Create Date: 2026-09-21 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2c7a1b40f93"
down_revision: str | None = "b8c4e1f70a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RESTART_MESSAGE = (
    "Settings were changed but the space could not be restarted to apply them"
)


def upgrade() -> None:
    op.create_table(
        "space_conditions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_space_condition", "space_conditions", ["space_id", "type"], unique=True
    )
    op.create_index(
        op.f("ix_space_conditions_space_id"), "space_conditions", ["space_id"]
    )

    # Every flagged space becomes its first condition row.
    op.execute(
        sa.text(
            "INSERT INTO space_conditions (id, space_id, type, message, created_at) "
            "SELECT lower(hex(randomblob(16))), id, 'restart_required', "
            f"'{_RESTART_MESSAGE}', CURRENT_TIMESTAMP "
            "FROM spaces WHERE restart_required = 1"
        )
    )
    op.drop_column("spaces", "restart_required")


def downgrade() -> None:
    op.add_column(
        "spaces",
        sa.Column(
            "restart_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        sa.text(
            "UPDATE spaces SET restart_required = 1 WHERE id IN "
            "(SELECT space_id FROM space_conditions WHERE type = 'restart_required')"
        )
    )
    op.drop_index(op.f("ix_space_conditions_space_id"), table_name="space_conditions")
    op.drop_index("idx_space_condition", table_name="space_conditions")
    op.drop_table("space_conditions")
