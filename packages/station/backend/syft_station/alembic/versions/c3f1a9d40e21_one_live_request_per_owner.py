"""one live request per owner

Revision ID: c3f1a9d40e21
Revises: 7b9962a74b24
Create Date: 2026-08-04 12:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f1a9d40e21"
down_revision: str | None = "7b9962a74b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Backstop for the submit-handler guard: SyftHub supports one space per
# user, so at most one request per owner may be in a slot-holding state.
# Must stay in sync with OWNER_SLOT_STATUSES in requests/entities.py.
_LIVE_STATUSES = "('pending', 'provisioning', 'active', 'failed')"


def upgrade() -> None:
    op.create_index(
        "uq_owner_live_request",
        "space_requests",
        ["owner_email"],
        unique=True,
        sqlite_where=sa.text(f"status IN {_LIVE_STATUSES}"),
    )


def downgrade() -> None:
    op.drop_index("uq_owner_live_request", table_name="space_requests")
