"""station hub identity moves off the wallet

The SyftHub token, its owner, and the station's satellite are properties of
the station, not of a payment gateway: one token verifies buyers for every
wallet, and one satellite covers the station's origin however many wallets
it grows. The wallet columns are dropped outright rather than deprecated —
no station has been deployed with data worth carrying forward.

Revision ID: b8c4e1f70a35
Revises: 7aac9a29ff18
Create Date: 2026-09-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c4e1f70a35"
down_revision: str | None = "7aac9a29ff18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the identity columns to station_config; drop them from wallets."""
    with op.batch_alter_table("station_config") as batch_op:
        batch_op.add_column(
            sa.Column(
                "hub_pat",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(sa.Column("hub_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "satellite_id",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default="",
            )
        )

    with op.batch_alter_table("wallets") as batch_op:
        batch_op.drop_column("hub_pat")
        batch_op.drop_column("hub_user_id")


def downgrade() -> None:
    """Put the identity back on the wallet, unpopulated."""
    with op.batch_alter_table("wallets") as batch_op:
        batch_op.add_column(sa.Column("hub_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("hub_pat", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
        )

    with op.batch_alter_table("station_config") as batch_op:
        batch_op.drop_column("satellite_id")
        batch_op.drop_column("hub_user_id")
        batch_op.drop_column("hub_pat")
