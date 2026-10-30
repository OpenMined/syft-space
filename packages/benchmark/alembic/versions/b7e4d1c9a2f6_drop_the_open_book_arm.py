"""drop the open_book arm from stored settings

``ContextMode`` has two arms, closed_book and model_with_context, and a stored
``arms`` list naming ``open_book`` would not parse. The value is removed from
the installation row, every target's instrument, and the instrument of jobs
still queued; a list left empty is removed, so the layer inherits its arms
rather than measuring none. Finished jobs keep their params as they ran; runs
measured under the arm keep their ``context_mode`` and are left out of the
status views.

``jobs.kind`` gets the comment the model declares.

Revision ID: b7e4d1c9a2f6
Revises: 7c3e5a9d1b62
Create Date: 2026-10-29 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e4d1c9a2f6"
down_revision: str | Sequence[str] | None = "7c3e5a9d1b62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARM = "'open_book'"

STATEMENTS = (
    f"""
    UPDATE installation_settings
    SET values = CASE
        WHEN (values -> 'arms') - {ARM} = '[]'::jsonb THEN values - 'arms'
        ELSE jsonb_set(values, '{{arms}}', (values -> 'arms') - {ARM})
    END
    WHERE jsonb_typeof(values -> 'arms') = 'array'
      AND (values -> 'arms') ? {ARM}
    """,
    f"""
    UPDATE targets
    SET instrument = CASE
        WHEN (instrument -> 'arms') - {ARM} = '[]'::jsonb THEN instrument - 'arms'
        ELSE jsonb_set(instrument, '{{arms}}', (instrument -> 'arms') - {ARM})
    END
    WHERE jsonb_typeof(instrument -> 'arms') = 'array'
      AND (instrument -> 'arms') ? {ARM}
    """,
    f"""
    UPDATE jobs
    SET params = CASE
        WHEN (params -> 'instrument' -> 'arms') - {ARM} = '[]'::jsonb
            THEN params #- '{{instrument,arms}}'
        ELSE jsonb_set(
            params, '{{instrument,arms}}', (params -> 'instrument' -> 'arms') - {ARM}
        )
    END
    WHERE state = 'queued'
      AND jsonb_typeof(params -> 'instrument' -> 'arms') = 'array'
      AND (params -> 'instrument' -> 'arms') ? {ARM}
    """,
)


KIND_COMMENT = (
    "What operation this job is: pipeline (measure(), any "
    "combination of generate/filter/evaluate), filter, or judge"
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))
    op.alter_column(
        "jobs",
        "kind",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        comment=KIND_COMMENT,
    )


def downgrade() -> None:
    # The removed value named an arm that does not exist.
    pass
