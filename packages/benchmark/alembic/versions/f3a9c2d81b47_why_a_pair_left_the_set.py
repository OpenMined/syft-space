"""why a pair left the set, as a code

``qa_pairs.status_reason``: a machine code of why a pair is not active
(grounding, retrieval_gate, duplicate, owner, web_answerable, other).
``status_note`` stays the free text beside it.

Backfill for rejected and retired rows: the notes the grounding review and
the retrieval gate write are recognised by their wording; anything else is
``other``. Pending and active rows stay NULL.

Revision ID: f3a9c2d81b47
Revises: d7b41f2a9c60
Create Date: 2026-10-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a9c2d81b47"
down_revision: str | Sequence[str] | None = "d7b41f2a9c60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Prefixes of the notes written by generation/validate.py.
GROUNDING_PREFIXES = (
    "nothing to check: no claims were listed",
    "the gold answer has no content words",
    "the short gold answer is not in the chunk",
    "the gold answer rests on what is not in the chunk",
)
# Suffix of review_claims' note: "<n> of <m> claims follow from the chunk".
GROUNDING_SUFFIX = " claims follow from the chunk"

# Prefixes of the notes written by generation/control.py and filter_stage.py.
GATE_PREFIXES = (
    "retrieval answers the question",
    "retrieval unreachable",
    "the gate did not run",
    "control question not checked",
)


def upgrade() -> None:
    op.add_column(
        "qa_pairs",
        sa.Column("status_reason", sa.String(length=32), nullable=True),
    )

    params: dict[str, str] = {"suffix": "%" + GROUNDING_SUFFIX}
    grounding = ["status_note LIKE :suffix"]
    for n, prefix in enumerate(GROUNDING_PREFIXES):
        params[f"g{n}"] = prefix + "%"
        grounding.append(f"status_note LIKE :g{n}")
    gate = []
    for n, prefix in enumerate(GATE_PREFIXES):
        params[f"r{n}"] = prefix + "%"
        gate.append(f"status_note LIKE :r{n}")

    op.get_bind().execute(
        sa.text(
            "UPDATE qa_pairs SET status_reason = CASE "
            f"WHEN {' OR '.join(gate)} THEN 'retrieval_gate' "
            f"WHEN {' OR '.join(grounding)} THEN 'grounding' "
            "ELSE 'other' END "
            "WHERE status IN ('rejected', 'retired')"
        ),
        params,
    )


def downgrade() -> None:
    op.drop_column("qa_pairs", "status_reason")
