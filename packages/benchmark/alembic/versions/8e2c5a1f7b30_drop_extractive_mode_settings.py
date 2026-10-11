"""drop the extractive_mode and spacy_models settings

Fill-in-the-blank items are written by the LLM only, and the settings that
chose a path are gone. ``Instrument`` and ``RunRequest`` forbid unknown keys,
so the keys are removed from the stored overrides: the installation row,
every target's instrument, and the instrument of jobs still queued. Finished
jobs keep their params as they ran.

Revision ID: 8e2c5a1f7b30
Revises: 7d3f1b6e9a52
Create Date: 2026-10-11 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8e2c5a1f7b30"
down_revision: str | Sequence[str] | None = "7d3f1b6e9a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEYS = "ARRAY['extractive_mode', 'spacy_models']"

STATEMENTS = (
    f"""
    UPDATE installation_settings
    SET values = values - {KEYS}
    WHERE values ?| {KEYS}
    """,
    f"""
    UPDATE targets
    SET instrument = instrument - {KEYS}
    WHERE instrument ?| {KEYS}
    """,
    f"""
    UPDATE jobs
    SET params = jsonb_set(
        params, '{{instrument}}', (params -> 'instrument') - {KEYS}
    )
    WHERE state = 'queued'
      AND jsonb_typeof(params -> 'instrument') = 'object'
      AND (params -> 'instrument') ?| {KEYS}
    """,
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    # The removed values were overrides of settings that no longer exist.
    pass
