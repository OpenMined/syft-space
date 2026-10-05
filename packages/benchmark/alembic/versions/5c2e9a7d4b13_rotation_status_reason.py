"""rotation as a status reason

Pairs the rotation took out of the set (freshness window, a newer cohort, the
set cap) carry ``status_reason = 'rotation'``. Backfilled from the notes the
rotation writes; anything else keeps its reason.

Revision ID: 5c2e9a7d4b13
Revises: 0b6e8d4f2a19
Create Date: 2026-10-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5c2e9a7d4b13"
down_revision: str | Sequence[str] | None = "0b6e8d4f2a19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The notes generation/rotation.py writes when it retires a pair.
ROTATION_NOTES = {
    "cohort": "cohort % replaced the previous one",
    "window": "the document is outside the %-day window",
    "cap": "over the set cap",
}


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE qa_pairs SET status_reason = 'rotation' "
            "WHERE status = 'retired' AND status_reason = 'other' "
            "AND (status_note LIKE :cohort OR status_note LIKE :window "
            "OR status_note = :cap)"
        ),
        ROTATION_NOTES,
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE qa_pairs SET status_reason = 'other' "
            "WHERE status_reason = 'rotation'"
        )
    )
