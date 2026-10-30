"""the model catalogue

``model_catalog``: one provider's model list per row, as a whole JSON
document — read and written whole, so rows per model would buy nothing.
Nothing is seeded: the snapshot shipped with the code is read wherever the
table has no row.

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
