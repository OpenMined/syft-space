"""drop jobs.card; one writer_calls row per call

``jobs.card`` goes. What its readers still need moves into ``jobs.params``
where missing: the article window (``window_days``) and, where it graded the
job, the instrument judge as ``primary_judge``.

``writer_calls`` keeps one row per call: the rows of one call merge, and
``dropped`` becomes ``{kind: [drafts]}`` in place of the ``generator`` column.

Downgrade restores the columns but not the cards: those are lost.

Revision ID: 2e7b9c4f1a83
Revises: 6f1d3b8c2e47
Create Date: 2026-10-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "2e7b9c4f1a83"
down_revision: str | Sequence[str] | None = "6f1d3b8c2e47"
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

# Each call's rows fold into its first: drops keyed by kind, the system
# prompt from whichever row carried it.
MERGE_CALLS = sa.text(
    """
    WITH merged AS (
        SELECT (array_agg(id ORDER BY created_at, id))[1] AS keep,
               jsonb_object_agg(generator, dropped) AS dropped,
               max(system) AS system
        FROM writer_calls
        GROUP BY job_id, call
    )
    UPDATE writer_calls w
    SET dropped = merged.dropped, system = merged.system
    FROM merged
    WHERE w.id = merged.keep
    """
)

DROP_MERGED = sa.text(
    """
    DELETE FROM writer_calls w
    WHERE EXISTS (
        SELECT 1 FROM writer_calls o
        WHERE o.job_id = w.job_id AND o.call = w.call
          AND (o.created_at, o.id) < (w.created_at, w.id)
    )
    """
)

SPLIT_CALLS = sa.text(
    """
    INSERT INTO writer_calls (
        id, job_id, call, generator, model, document_title, file_name, passage,
        system, system_digest, "user", reply, cost_usd, latency_s, error,
        dropped, created_at
    )
    SELECT md5(w.id || ':' || kind.key), w.job_id, w.call, kind.key, w.model,
           w.document_title, w.file_name, w.passage, w.system, w.system_digest,
           w."user", w.reply, w.cost_usd, w.latency_s, w.error, kind.value,
           w.created_at
    FROM writer_calls w, jsonb_each(w.dropped) AS kind
    WHERE w.generator IS NULL
    """
)


def upgrade() -> None:
    op.execute(WINDOW_FROM_CARD)
    op.execute(PRIMARY_FROM_CARD)
    op.drop_column("jobs", "card")

    op.execute(MERGE_CALLS)
    op.execute(DROP_MERGED)
    op.drop_index("writer_calls_job", table_name="writer_calls")
    op.drop_column("writer_calls", "generator")
    op.alter_column("writer_calls", "dropped", server_default=sa.text("'{}'::jsonb"))
    op.create_index("writer_calls_job", "writer_calls", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("writer_calls_job", table_name="writer_calls")
    op.add_column(
        "writer_calls", sa.Column("generator", sa.String(length=64), nullable=True)
    )
    op.execute(SPLIT_CALLS)
    op.execute(sa.text("DELETE FROM writer_calls WHERE generator IS NULL"))
    op.alter_column("writer_calls", "generator", nullable=False)
    op.alter_column("writer_calls", "dropped", server_default=sa.text("'[]'::jsonb"))
    op.create_index(
        "writer_calls_job", "writer_calls", ["job_id", "generator", "created_at"]
    )

    op.add_column(
        "jobs",
        sa.Column("card", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
