"""lowercase stored emails

Revision ID: b13bbb37fe06
Revises: c3f1a9d40e21
Create Date: 2026-08-10 15:46:29.528390

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b13bbb37fe06"
down_revision: str | None = "c3f1a9d40e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Emails are now lowercased at the validation boundary (NormalizedEmail);
# this brings every already-stored email to the same form so equality
# comparisons and the email-keyed unique indexes see one identity per
# account.
_EMAIL_COLUMNS = [
    ("space_requests", "owner_email"),
    ("spaces", "owner_email"),
    ("invoices", "user_email"),
    ("user_balances", "user_email"),
    ("ledger_entries", "user_email"),
]

# Must stay in sync with OWNER_SLOT_STATUSES in requests/entities.py (same
# list as the uq_owner_live_request index in c3f1a9d40e21).
_LIVE_STATUSES = "('pending', 'provisioning', 'active', 'failed')"


def upgrade() -> None:
    conn = op.get_bind()

    # Lowercasing must not merge rows a unique index keeps apart — a balance
    # is money and a live request is a member's one space slot, so neither
    # may be combined silently. Abort listing the offenders; the operator
    # resolves them by hand and re-runs.
    conflicts = []
    for table, column, where in [
        ("user_balances", "user_email", ""),
        ("space_requests", "owner_email", f"WHERE status IN {_LIVE_STATUSES}"),
    ]:
        rows = conn.execute(
            sa.text(
                f"SELECT group_concat({column}, ', ') FROM {table} {where} "
                f"GROUP BY lower({column}) HAVING count(DISTINCT {column}) > 1"
            )
        ).fetchall()
        conflicts.extend(f"{table}.{column}: {row[0]}" for row in rows)
    if conflicts:
        raise RuntimeError(
            "These rows differ only by email casing and would collide once "
            "lowercased — resolve them by hand, then re-run the migration:\n"
            + "\n".join(conflicts)
        )

    for table, column in _EMAIL_COLUMNS:
        conn.execute(sa.text(f"UPDATE {table} SET {column} = lower({column})"))


def downgrade() -> None:
    # The original casing is gone; lowercase emails are valid under every
    # prior schema, so there is nothing to restore.
    pass
