"""invoices: add provider_session_id and rename external_id -> client_reference

Revision ID: b2f4a3c7e108
Revises: e9a7c2b81f04
Create Date: 2026-05-21 00:00:00.000000

Two related changes to the ``invoices`` table:

1. Add a nullable ``provider_session_id`` column to store the provider-side
   session identifier (e.g. Stripe ``cs_…``). This unlocks the stale-PENDING
   reconciliation path the existing TODO in ``PaymentHandler.create_invoice``
   flagged: a future sweep job can call the provider's GET session endpoint
   directly to recover from lost webhooks, which is impossible today because
   we only persist our echoed-back client reference. Xendit rows leave it
   NULL — its API is addressable by our client reference, so a separate
   session id isn't needed.

2. Rename ``external_id`` → ``client_reference``. The column stores our own
   ``syft-{uuid}`` token that we send to the provider and they echo back in
   webhooks. The old name suggested it was provider-assigned, which was
   misleading. Pair this with the new ``provider_session_id`` (their token)
   and the schema is self-documenting: ``client_reference`` is ours,
   ``provider_session_id`` is theirs.

The matching index is dropped and recreated under the new name to stay
unique and aligned with the column it covers.
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
    # Add provider_session_id + its index (batched so SQLite gets a clean
    # table rebuild rather than per-statement ALTERs).
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(
            sa.Column("provider_session_id", sa.String(), nullable=True)
        )
        batch_op.create_index(
            "idx_invoice_provider_session_id",
            ["provider_session_id"],
            unique=False,
        )

    # Rename external_id → client_reference. SQLite 3.25+ supports native
    # RENAME COLUMN, and alembic batch mode can't co-locate a rename with
    # an index drop/create against the new name (it fails resolving the
    # not-yet-renamed column when constructing the shadow table). Doing
    # each step at the top level keeps it linear and engine-native.
    op.drop_index("idx_invoice_external_id", table_name="invoices")
    op.alter_column(
        "invoices",
        "external_id",
        new_column_name="client_reference",
    )
    op.create_index(
        "idx_invoice_client_reference",
        "invoices",
        ["client_reference"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_invoice_client_reference", table_name="invoices")
    op.alter_column(
        "invoices",
        "client_reference",
        new_column_name="external_id",
    )
    op.create_index(
        "idx_invoice_external_id",
        "invoices",
        ["external_id"],
        unique=True,
    )

    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_index("idx_invoice_provider_session_id")
        batch_op.drop_column("provider_session_id")
