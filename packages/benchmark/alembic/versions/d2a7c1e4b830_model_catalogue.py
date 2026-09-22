"""the model catalogue

One table, so that a model stops being a string somebody typed: a typo in a
model name reaches the provider verbatim and is refused after the pass has been
paid for.

A whole document per source rather than a row per model. The list is read whole
and written whole, and three hundred entries are filtered in memory faster than
a query would be planned; rows would buy joins nobody performs and cost a
migration every time a provider adds a field.

Nothing is seeded here. The snapshot that ships with the code is read wherever
this table holds no row, which is what lets an installation with no way out of
the perimeter draw a form with models in it — and a migration that copied it in
would freeze it at the version of the day it ran.

Revision ID: d2a7c1e4b830
Revises: 9bb3816f998f
Create Date: 2026-09-20 14:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2a7c1e4b830"
down_revision: str | Sequence[str] | None = "9bb3816f998f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_catalog",
        sa.Column(
            "source",
            sa.String(length=40),
            nullable=False,
            comment="The provider this catalogue came from. There is exactly one "
            "current catalogue per provider, and a refresh replaces it",
        ),
        sa.Column(
            "document",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="The catalogue itself: the entries and the pins that resolve "
            "moving names such as a vendor's -latest",
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When it was last fetched. Shown beside the picker: a "
            "catalogue whose age is invisible is one nobody thinks to refresh",
        ),
        sa.Column(
            "model_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Denormalised out of the document so that how old this is and "
            "how much is in it can be answered without loading all of it",
        ),
        sa.PrimaryKeyConstraint("source"),
    )


def downgrade() -> None:
    op.drop_table("model_catalog")
