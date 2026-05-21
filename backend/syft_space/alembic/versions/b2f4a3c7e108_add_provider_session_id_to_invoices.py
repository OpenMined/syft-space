"""add provider_session_id to invoices

Revision ID: b2f4a3c7e108
Revises: e9a7c2b81f04
Create Date: 2026-05-21 00:00:00.000000

Adds a nullable ``provider_session_id`` column to ``invoices`` so we can
store the provider-side session identifier (e.g. Stripe ``cs_…``) alongside
our own ``external_id`` (= ``reference_id``).

This unlocks the stale-PENDING reconciliation path the existing TODO in
``PaymentHandler.create_invoice`` flagged: a future sweep job can call the
provider's GET session endpoint directly to recover from lost webhooks,
which is impossible today because we only persist our echoed-back
reference id.

Xendit rows are unaffected — its gateway never sets a separate session id
and the column stays NULL for those invoices.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f4a3c7e108"
down_revision: str | None = "e9a7c2b81f04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(
            sa.Column("provider_session_id", sa.String(), nullable=True)
        )
        batch_op.create_index(
            "idx_invoice_provider_session_id",
            ["provider_session_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_index("idx_invoice_provider_session_id")
        batch_op.drop_column("provider_session_id")
