"""the schema as first deployed

The whole benchmark schema as the base of the chain: what a database held at
this revision before the history was squashed. The revision id is kept, so a
database already stamped with it upgrades from here.

``server_default`` is set on every column that has one in the models and on
some the models leave to the ORM, so a write that bypasses the ORM still gets
a value.

Revision ID: a4d7e2c9f150
Revises:
Create Date: 2026-09-16 08:08:05.890447

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a4d7e2c9f150"
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
        sa.Column(
            "card",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="The card assembled after measuring, in the shape the Space "
            "accepts it in — set regardless of whether it was published",
        ),
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default="pipeline",
            comment="What operation this job is: pipeline (measure(), any "
            "combination of generate/filter/evaluate), filter, or judge",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_created_at"), "jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_jobs_kind"), "jobs", ["kind"], unique=False)
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
        sa.Column(
            "job_id",
            sa.String(length=64),
            nullable=True,
            comment="The launch that generated this pair; NULL — none it can name",
        ),
        sa.Column("status_reason", sa.String(length=32), nullable=True),
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
    # Every read of it is "this launch's questions", and the status band is
    # always part of that question — rejected ones are shown beside the rest.
    op.create_index("qa_pairs_job", "qa_pairs", ["space", "job_id", "status"])

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
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column(
            "model_sent_as",
            sa.String(length=120),
            nullable=False,
            server_default="",
            comment="The name the provider was actually given, when it differs "
            "from the identifier this service uses",
        ),
        sa.Column(
            "model_provider",
            sa.String(length=40),
            nullable=False,
            server_default="",
            comment="Whose API answered: openrouter, anthropic, ollama",
        ),
        sa.Column(
            "model_build",
            sa.String(length=120),
            nullable=False,
            server_default="",
            comment="The dated build behind the name on the day of the run. A "
            "vendor refreshes what a name serves; without this, two runs under "
            "one name look comparable when they are not",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runs_block"), "runs", ["block"], unique=False)
    op.create_index(
        op.f("ix_runs_context_mode"), "runs", ["context_mode"], unique=False
    )
    op.create_index(op.f("ix_runs_job_id"), "runs", ["job_id"], unique=False)
    op.create_index(op.f("ix_runs_profile"), "runs", ["profile"], unique=False)
    op.create_index(op.f("ix_runs_space"), "runs", ["space"], unique=False)

    op.create_table(
        "targets",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
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
            comment="The launch time HH:MM in UTC, if set",
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
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    # After both of its parents.
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
        sa.Column(
            "served_by",
            sa.String(length=64),
            nullable=False,
            server_default="",
            comment="The upstream that served the answer, when the provider is "
            "a router rather than the model's owner",
        ),
        sa.Column(
            "judge_served_by",
            sa.String(length=64),
            nullable=False,
            server_default="",
            comment="The upstream that served the verdict. Kept apart from the "
            "answer's: when a number moves, it is the first thing to rule out",
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

    op.create_table(
        "installation_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="installation_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "credentials",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("secret", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
    )

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
            postgresql.JSONB(astext_type=sa.Text()),
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

    op.create_table(
        "run_aggregates",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    """Drop the whole schema. Children before parents."""
    op.drop_table("run_aggregates")
    op.drop_table("model_catalog")
    op.drop_table("credentials")
    op.drop_table("installation_settings")
    op.drop_index("results_run", table_name="results")
    op.drop_index("results_qa_recent", table_name="results")
    op.drop_index(op.f("ix_results_verdict"), table_name="results")
    op.drop_index(op.f("ix_results_space"), table_name="results")
    op.drop_index(op.f("ix_results_expected_behavior"), table_name="results")
    op.drop_table("results")
    op.drop_table("targets")
    op.drop_index(op.f("ix_runs_space"), table_name="runs")
    op.drop_index(op.f("ix_runs_profile"), table_name="runs")
    op.drop_index(op.f("ix_runs_job_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_context_mode"), table_name="runs")
    op.drop_index(op.f("ix_runs_block"), table_name="runs")
    op.drop_table("runs")
    op.drop_index("qa_pairs_job", table_name="qa_pairs")
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
    op.drop_index(op.f("ix_jobs_kind"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_created_at"), table_name="jobs")
    op.drop_table("jobs")
