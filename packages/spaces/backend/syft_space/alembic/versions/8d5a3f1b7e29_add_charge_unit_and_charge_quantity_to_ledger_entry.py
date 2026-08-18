"""add charge_unit and charge_quantity to ledger_entry

Revision ID: 8d5a3f1b7e29
Revises: 7a3c1b9e2f04
Create Date: 2026-05-14 00:00:01.000000

Adds the unit/quantity dimension to ledger entries so per-document policy
debits can be distinguished from per-request debits. Existing rows are all
per-request and are backfilled as ('request', 1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d5a3f1b7e29"
down_revision: str | None = "7a3c1b9e2f04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ledger_entry") as batch_op:
        batch_op.add_column(
            sa.Column(
                "charge_unit",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="request",
            )
        )
        batch_op.add_column(
            sa.Column(
                "charge_quantity",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )

    # Drop server_defaults once existing rows are populated; new rows must
    # specify charge_unit / charge_quantity explicitly at the application layer.
    with op.batch_alter_table("ledger_entry") as batch_op:
        batch_op.alter_column("charge_unit", server_default=None)
        batch_op.alter_column("charge_quantity", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("ledger_entry") as batch_op:
        batch_op.drop_column("charge_quantity")
        batch_op.drop_column("charge_unit")
