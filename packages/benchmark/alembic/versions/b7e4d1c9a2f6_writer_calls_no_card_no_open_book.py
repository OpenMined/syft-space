"""writer calls; drop jobs.card and the open_book arm

``writer_calls``: a job's writer calls that threw drafts away or failed, one
row per call, ``dropped`` keyed by kind. Deleted with their job by
``discard_run``.

``jobs.card`` goes. What its readers still need moves into ``jobs.params``
where missing: the article window (``window_days``) and, where it graded the
job, the instrument judge as ``primary_judge``.

``ContextMode`` has two arms, closed_book and model_with_context, and a stored
``arms`` list naming ``open_book`` would not parse. The value is removed from
the installation row, every target's instrument, and the instrument of jobs
still queued; a list left empty is removed, so the layer inherits its arms
rather than measuring none. Finished jobs keep their params as they ran; runs
measured under the arm keep their ``context_mode`` and are left out of the
status views.

Downgrade restores ``jobs.card`` empty and drops ``writer_calls``; the cards
and the writer calls are lost.

Revision ID: b7e4d1c9a2f6
Revises: a4d7e2c9f150
Create Date: 2026-10-29 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7e4d1c9a2f6"
down_revision: str | Sequence[str] | None = "a4d7e2c9f150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WINDOW_FROM_CARD = sa.text(
    """
    UPDATE jobs
    SET params = coalesce(params, '{}'::jsonb) || jsonb_build_object(
        'window_days', (card -> 'dataset' -> 'window_days')::int
    )
    WHERE jsonb_typeof(card -> 'dataset' -> 'window_days') = 'number'
      AND (params -> 'window_days') IS NULL
    """
)

PRIMARY_FROM_CARD = sa.text(
    """
    UPDATE jobs
    SET params = coalesce(params, '{}'::jsonb) || jsonb_build_object(
        'primary_judge', card -> 'instrument' ->> 'judge'
    )
    WHERE (params -> 'primary_judge') IS NULL
      AND coalesce(card -> 'instrument' ->> 'judge', '') <> ''
      AND EXISTS (
          SELECT 1 FROM results res
          JOIN runs r ON r.id = res.run_id
          WHERE r.job_id = jobs.id
            AND res.judge_model = jobs.card -> 'instrument' ->> 'judge'
      )
    """
)

ARM = "'open_book'"

OPEN_BOOK_STATEMENTS = (
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

CARD_COMMENT = (
    "The card assembled after measuring, in the shape the Space "
    "accepts it in — set regardless of whether it was published"
)


def upgrade() -> None:
    op.create_table(
        "writer_calls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("call", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("document_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("passage", sa.Text(), nullable=False, server_default=""),
        sa.Column("system", sa.Text(), nullable=False, server_default=""),
        sa.Column("system_digest", sa.String(length=64), nullable=False),
        sa.Column("user", sa.Text(), nullable=False, server_default=""),
        sa.Column("reply", sa.Text(), nullable=False, server_default=""),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_s", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "dropped",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("writer_calls_system", "writer_calls", ["job_id", "system_digest"])
    op.create_index("writer_calls_job", "writer_calls", ["job_id", "created_at"])
    # A pair's writer call is looked up in its job's log by call id, and a call
    # is logged once.
    op.create_index(
        "writer_calls_call", "writer_calls", ["job_id", "call"], unique=True
    )

    op.execute(WINDOW_FROM_CARD)
    op.execute(PRIMARY_FROM_CARD)
    op.drop_column("jobs", "card")

    for statement in OPEN_BOOK_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # The removed arm does not exist; the moved params stay where they are.
    op.add_column(
        "jobs",
        sa.Column(
            "card",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=CARD_COMMENT,
        ),
    )
    op.drop_index("writer_calls_call", table_name="writer_calls")
    op.drop_index("writer_calls_job", table_name="writer_calls")
    op.drop_index("writer_calls_system", table_name="writer_calls")
    op.drop_table("writer_calls")
