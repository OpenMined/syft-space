"""keep benchmark cards in their own tables, not as columns on existing rows

Two tables, neither of them a widening of something that already existed.

``endpoint_quality_cards`` holds what benchmarks have said about an endpoint —
every card, not only the last one. A row per run rather than a row per
endpoint: a figure is only worth anything next to the figures before it, and an
owner deciding whether he vouches for "0.71 accuracy" wants to know it was 0.78
a month ago. Overwriting in place answered "what is true now" and threw away
the only thing that made the number readable.

Retraction is a column here, not a delete. ``retracted_at`` marks the cards the
owner has withdrawn from the marketplaces; the rows stay, because what was
published and then taken back is itself a fact about this endpoint, and because
a retraction that erased the history would make the next card look like the
first one. The current card is the newest row with ``retracted_at`` NULL, and
no such row means no benchmark has reported — which is not a score of zero and
must never be rendered as one.

``benchmark_settings`` holds ``mode``: "off" (the default) means the reporting
API is not there at all, so an existing Space keeps behaving exactly as before
and nothing new is sent anywhere. A string rather than a flag because the ways
a benchmark may be trusted will multiply; "local" is only the first of them.
Its own table rather than another column on ``settings``: that row is a grab
bag of unrelated switches already, and a feature that can be absent entirely is
better off as a row that can be absent entirely.

Singleton, with no ``tenant_id`` — deliberately matching ``settings``, which is
also one global row. Nothing in the path that reads this setting carries a
tenant, and inventing a column no query could fill would only promise a
multi-tenancy that is not there.

Revision ID: a3f7c15e9b42
Revises: a1b2c3d4e5f7
Create Date: 2026-09-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7c15e9b42"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the card history and the benchmark settings row."""
    op.create_table(
        "endpoint_quality_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("endpoint_id", sa.Uuid(), nullable=True),
        # What kind of product was measured. Without it `score` is ambiguous:
        # "finds 82%" and "correct 82%" are different claims.
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        # The headline share for that kind. Nullable because a run can fail to
        # produce one and still have something to say about fabrication.
        sa.Column("score", sa.Float(), nullable=True),
        # Questions with no answer in the corpus that were answered anyway.
        # Reported for both kinds, and nearly independent of how hard the
        # corpus is — which makes it the one figure comparable across Spaces.
        sa.Column("fabrication_rate", sa.Float(), nullable=True),
        sa.Column("samples", sa.Integer(), nullable=False),
        # Whether the benchmark vouches for the figures at all. A share nobody
        # vouches for is worse than no share: absence is visible, a bare number
        # is not.
        sa.Column("reliable", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        # The whole card, for the detail view and for re-sending after an
        # outage. JSON rather than columns: the breakdown by skill, the spread
        # across subject models and the trust block all grow, and none of them
        # is ever filtered or sorted on. NOT NULL because every row here is a
        # card that was actually reported — there is no longer such a thing as
        # a row standing for the absence of one.
        sa.Column("report", sa.JSON(), nullable=False),
        # Set when the owner withdraws the card from the marketplaces. NULL is
        # "still stands".
        sa.Column("retracted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # The endpoint goes, its cards go with it: a card is a claim about an
        # endpoint and means nothing without one.
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_endpoint_quality_cards_id"),
        "endpoint_quality_cards",
        ["id"],
        unique=False,
    )
    # Every read of this table is "the newest card for this endpoint" or "this
    # endpoint's cards, newest first". One index serves both.
    op.create_index(
        "idx_quality_card_endpoint_checked",
        "endpoint_quality_cards",
        ["endpoint_id", "checked_at"],
        unique=False,
    )

    op.create_table(
        "benchmark_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "mode",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="off",
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop both tables. No columns were borrowed, so nothing is left behind."""
    op.drop_table("benchmark_settings")
    op.drop_index(
        "idx_quality_card_endpoint_checked", table_name="endpoint_quality_cards"
    )
    op.drop_index(
        op.f("ix_endpoint_quality_cards_id"), table_name="endpoint_quality_cards"
    )
    op.drop_table("endpoint_quality_cards")
