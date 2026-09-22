"""initial schema

The whole benchmark schema in one file. It replaces the eight migrations that
built it up between ``3d8460084d2d`` and ``9abbfe2cb726``: the initial tables,
then processed units keyed by generator, eval blocks, the three arms and the
audit trail, dataset cohorts, targets and jobs for the control API, a target's
collection, and a job's current pass.

Collapsed because nothing is deployed from them. A chain is worth keeping only
while some database is partway along it; with no such database the eight steps
recorded the order in which the schema was thought up, not anything a future
run needs to repeat. Once a real installation exists this file becomes history
like any other, and the next change is a migration on top of it.

The schema here is the one the eight produced -- verified by building both and
diffing the dumps -- with two deliberate differences.

``server_default`` is kept on every column that had one, including the sixteen
that only ever existed to backfill a column being added to a populated table.
They no longer have that job here, a fresh table having no rows to fill, but
the models do not declare them: dropping them would quietly change what a write
that bypasses the ORM does, and that is not what collapsing a chain is for.

The three ``targets`` comments read as the models word them rather than as the
old migrations did. The two had drifted, ``alembic check`` was reporting it,
and the models are what the code is written against.

Revision ID: fbf33c5dff4d
Revises:
Create Date: 2026-09-16 08:08:05.890447

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fbf33c5dff4d"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the whole schema."""
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        # Which pass is running, and how far into itself it has got.
        sa.Column("arm", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("block", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("step_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_created_at"), "jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_jobs_state"), "jobs", ["state"], unique=False)
    op.create_index(op.f("ix_jobs_target"), "jobs", ["target"], unique=False)

    op.create_table(
        "processed_units",
        sa.Column("space", sa.String(length=64), nullable=False),
        sa.Column("generator", sa.String(length=64), nullable=False),
        sa.Column("unit_id", sa.String(length=200), nullable=False),
        sa.Column("cohort", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "unit_kind",
            sa.String(length=16),
            nullable=False,
            comment="chunk | document",
        ),
        sa.Column("pairs_made", sa.Integer(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("space", "generator", "unit_id", "cohort"),
    )

    op.create_table(
        "qa_pairs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("space", sa.String(length=64), nullable=False),
        sa.Column("collection", sa.String(length=200), nullable=False),
        sa.Column("cohort", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "generator",
            sa.String(length=64),
            nullable=False,
            comment="Item type: masking, MCQ and so on",
        ),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("doc_id", sa.String(length=200), nullable=False),
        sa.Column("chunk_id", sa.String(length=200), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column(
            "distractors", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # "answer" rather than a blank: the half of the set with no answer in
        # the corpus is the exception, and it is stated, never inferred.
        sa.Column(
            "expected_behavior",
            sa.String(length=20),
            nullable=False,
            server_default="answer",
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_note", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "space", "generator", "question_hash", "cohort", name="qa_pairs_unique"
        ),
    )
    op.create_index(op.f("ix_qa_pairs_cohort"), "qa_pairs", ["cohort"], unique=False)
    op.create_index(
        op.f("ix_qa_pairs_expected_behavior"),
        "qa_pairs",
        ["expected_behavior"],
        unique=False,
    )
    op.create_index(op.f("ix_qa_pairs_space"), "qa_pairs", ["space"], unique=False)
    op.create_index(op.f("ix_qa_pairs_status"), "qa_pairs", ["status"], unique=False)
    op.create_index("qa_pairs_chunk", "qa_pairs", ["space", "chunk_id"], unique=False)
    op.create_index(
        "qa_pairs_cohort", "qa_pairs", ["space", "cohort", "status"], unique=False
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("space", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("context_mode", sa.String(length=32), nullable=False),
        sa.Column(
            "context_source",
            sa.String(length=32),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "profile", sa.String(length=64), nullable=False, server_default="default"
        ),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "block", sa.String(length=20), nullable=False, server_default="direct"
        ),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "model_vendor",
            sa.String(length=40),
            nullable=False,
            server_default="",
            comment="The provider of the model under test",
        ),
        sa.Column("judge_model", sa.String(length=120), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runs_block"), "runs", ["block"], unique=False)
    op.create_index(
        op.f("ix_runs_context_mode"), "runs", ["context_mode"], unique=False
    )
    op.create_index(op.f("ix_runs_profile"), "runs", ["profile"], unique=False)
    op.create_index(op.f("ix_runs_space"), "runs", ["space"], unique=False)

    op.create_table(
        "targets",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("container", sa.String(length=120), nullable=False),
        sa.Column("chroma_host", sa.String(length=200), nullable=False),
        sa.Column("chroma_port", sa.Integer(), nullable=False),
        sa.Column(
            "collection",
            sa.String(length=200),
            nullable=False,
            server_default="",
            comment="The collection name in the index; empty — the target key is used",
        ),
        sa.Column(
            "instrument",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Override for the what-we-measure-with layer",
        ),
        sa.Column(
            "probe",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Override for the how-we-ask layer",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule", sa.String(length=20), nullable=False),
        sa.Column(
            "schedule_at",
            sa.String(length=5),
            nullable=False,
            comment="The launch time HH:MM, if set",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # Last: the only table with foreign keys, and both of its parents have to
    # exist before it does.
    op.create_table(
        "results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("qa_id", sa.String(length=64), nullable=False),
        sa.Column("space", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("endpoint_response_type", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "expected_behavior",
            sa.String(length=20),
            nullable=False,
            server_default="answer",
        ),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("grounded_note", sa.Text(), nullable=False),
        sa.Column("retrieval_hit", sa.Boolean(), nullable=True),
        sa.Column("retrieval_rank", sa.Integer(), nullable=True),
        sa.Column("retrieved", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "audit",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("latency_s", sa.Float(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("judge_model", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["qa_id"], ["qa_pairs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_results_expected_behavior"),
        "results",
        ["expected_behavior"],
        unique=False,
    )
    op.create_index(op.f("ix_results_space"), "results", ["space"], unique=False)
    op.create_index(op.f("ix_results_verdict"), "results", ["verdict"], unique=False)
    op.create_index(
        "results_qa_recent", "results", ["space", "qa_id", "created_at"], unique=False
    )
    op.create_index("results_run", "results", ["run_id"], unique=False)


def downgrade() -> None:
    """Drop the whole schema. Children before parents."""
    op.drop_index("results_run", table_name="results")
    op.drop_index("results_qa_recent", table_name="results")
    op.drop_index(op.f("ix_results_verdict"), table_name="results")
    op.drop_index(op.f("ix_results_space"), table_name="results")
    op.drop_index(op.f("ix_results_expected_behavior"), table_name="results")
    op.drop_table("results")
    op.drop_table("targets")
    op.drop_index(op.f("ix_runs_space"), table_name="runs")
    op.drop_index(op.f("ix_runs_profile"), table_name="runs")
    op.drop_index(op.f("ix_runs_context_mode"), table_name="runs")
    op.drop_index(op.f("ix_runs_block"), table_name="runs")
    op.drop_table("runs")
    op.drop_index("qa_pairs_cohort", table_name="qa_pairs")
    op.drop_index("qa_pairs_chunk", table_name="qa_pairs")
    op.drop_index(op.f("ix_qa_pairs_status"), table_name="qa_pairs")
    op.drop_index(op.f("ix_qa_pairs_space"), table_name="qa_pairs")
    op.drop_index(op.f("ix_qa_pairs_expected_behavior"), table_name="qa_pairs")
    op.drop_index(op.f("ix_qa_pairs_cohort"), table_name="qa_pairs")
    op.drop_table("qa_pairs")
    op.drop_table("processed_units")
    op.drop_index(op.f("ix_jobs_target"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_state"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_created_at"), table_name="jobs")
    op.drop_table("jobs")
