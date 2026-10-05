"""freeze each finished job's primary judge

Sets ``jobs.params.primary_judge`` for every finished job with verdicts and no
such key: the job card's instrument judge if it graded the job, else the first
judge to grade it. From then on settings and card rebuilds leave it alone.

Revision ID: 7d3f1b6e9a52
Revises: 5c2e9a7d4b13
Create Date: 2026-10-04 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d3f1b6e9a52"
down_revision: str | Sequence[str] | None = "5c2e9a7d4b13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FREEZE = sa.text(
    """
    WITH seen AS (
        SELECT r.job_id, res.judge_model, min(res.created_at) AS first_at
        FROM results res
        JOIN runs r ON r.id = res.run_id
        WHERE r.job_id IS NOT NULL
          AND res.judge_model NOT IN ('', 'owner override')
        GROUP BY r.job_id, res.judge_model
    ),
    chosen AS (
        SELECT j.id,
               coalesce(
                   (SELECT s.judge_model FROM seen s
                     WHERE s.job_id = j.id
                       AND s.judge_model = j.card -> 'instrument' ->> 'judge'),
                   (SELECT s.judge_model FROM seen s
                     WHERE s.job_id = j.id
                     ORDER BY s.first_at, s.judge_model
                     LIMIT 1)
               ) AS judge
        FROM jobs j
        WHERE j.state NOT IN ('queued', 'running')
          AND j.params -> 'primary_judge' IS NULL
    )
    UPDATE jobs
    SET params = coalesce(jobs.params, '{}'::jsonb)
                 || jsonb_build_object('primary_judge', chosen.judge)
    FROM chosen
    WHERE chosen.id = jobs.id AND chosen.judge IS NOT NULL
    """
)


def upgrade() -> None:
    op.execute(FREEZE)


def downgrade() -> None:
    op.execute(sa.text("UPDATE jobs SET params = params - 'primary_judge'"))
