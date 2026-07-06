"""add dataset_selection table, backfill from and strip configuration blobs

Revision ID: f1a2b3c4d5e6
Revises: 758674b03ba7
Create Date: 2026-07-01 10:00:00.000000

Normalizes the dataset selection list out of the ``datasets.configuration``
JSON blob into a dedicated ``dataset_selection`` table (one row per selected
item), making add/remove selection atomic and the table the single source of
truth for the selection.

Upgrade:
- creates the table
- backfills one row per existing selected item, read from each dataset's
  configuration blob
- strips the selection key from each configuration blob

Downgrade is lossless: the selection key is reconstructed into each
configuration blob from the table rows before the table is dropped.

No app code is imported. The dtype -> selection-key mapping and the per-source
item shapes are inlined so future refactors of the config/source classes don't
break replays of this migration.

DB engine: SQLite. ``configuration`` is stored as JSON TEXT.
"""

import json
import uuid
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (kept for AutoString parity with sibling migrations)
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "758674b03ba7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# dtype -> the flat configuration key holding its selection list.
# Inlined literal (NOT imported) so this migration stays a frozen historical fact.
_SELECTION_KEY: dict[str, str] = {
    "local_file": "filePaths",
    "wordpress": "selectedItems",
}


def _load_config(raw: object) -> dict:
    """SQLite stores JSON as TEXT; other backends may return dicts."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _iter_selection_items(dtype: str, config: dict) -> Iterator[tuple[str, str | None]]:
    """Yield ``(item_id, description)`` for a dataset's selection entries.

    Handles both stored shapes:
    - local_file: ``[{"path": ..., "description": ...}, ...]``
    - wordpress:  ``["{post_type}:{id}", ...]`` (bare strings, no description)
    """
    key = _SELECTION_KEY.get(dtype)
    if key is None:
        return
    entries = config.get(key)
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, dict):
            item_id = entry.get("path")
            description = entry.get("description")
        else:
            item_id = entry
            description = None
        if item_id:
            yield str(item_id), description


# Lightweight typed table handle for the backfill insert. Typed columns let
# SQLAlchemy serialize UUID/datetime exactly as the ORM does.
_selection_table = sa.table(
    "dataset_selection",
    sa.column("id", sa.Uuid()),
    sa.column("dataset_id", sa.Uuid()),
    sa.column("item_id", sa.String()),
    sa.column("description", sa.String()),
    sa.column("added_at", sa.DateTime()),
)


def upgrade() -> None:
    op.create_table(
        "dataset_selection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "item_id", name="uq_dataset_selection"),
    )
    op.create_index(
        op.f("ix_dataset_selection_dataset_id"),
        "dataset_selection",
        ["dataset_id"],
        unique=False,
    )

    # Backfill: one row per selected item from each dataset's configuration.
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = bind.execute(
        sa.text("SELECT id, dtype, configuration FROM datasets")
    ).fetchall()

    pending: list[dict] = []
    for ds_id, dtype, config_raw in rows:
        config = _load_config(config_raw)
        for item_id, description in _iter_selection_items(dtype, config):
            pending.append(
                {
                    "id": uuid.uuid4(),
                    "dataset_id": ds_id
                    if isinstance(ds_id, uuid.UUID)
                    else uuid.UUID(str(ds_id)),
                    "item_id": item_id,
                    "description": description,
                    "added_at": now,
                }
            )

    if pending:
        op.bulk_insert(_selection_table, pending)

    # Strip the selection key from each configuration blob — the table is
    # now the single source of truth for the selection.
    for ds_id, dtype, config_raw in rows:
        key = _SELECTION_KEY.get(dtype)
        if key is None:
            continue
        config = _load_config(config_raw)
        if key not in config:
            continue
        config.pop(key)
        bind.execute(
            sa.text("UPDATE datasets SET configuration = :cfg WHERE id = :id"),
            {"cfg": json.dumps(config), "id": ds_id},
        )


def downgrade() -> None:
    # Reconstruct the selection key in each configuration blob from the
    # table rows (inverse of the upgrade strip), then drop the table.
    bind = op.get_bind()
    selections: dict[str, list[tuple[str, str | None]]] = {}
    for dataset_id, item_id, description in bind.execute(
        sa.text(
            "SELECT dataset_id, item_id, description FROM dataset_selection "
            "ORDER BY added_at"
        )
    ):
        selections.setdefault(str(dataset_id), []).append((item_id, description))

    for ds_id, dtype, config_raw in bind.execute(
        sa.text("SELECT id, dtype, configuration FROM datasets")
    ).fetchall():
        key = _SELECTION_KEY.get(dtype)
        picks = selections.get(str(ds_id))
        if key is None or not picks:
            continue
        config = _load_config(config_raw)
        if dtype == "local_file":
            config[key] = [
                {"path": item_id, "description": description or ""}
                for item_id, description in picks
            ]
        else:
            config[key] = [item_id for item_id, _ in picks]
        bind.execute(
            sa.text("UPDATE datasets SET configuration = :cfg WHERE id = :id"),
            {"cfg": json.dumps(config), "id": ds_id},
        )

    op.drop_index(
        op.f("ix_dataset_selection_dataset_id"), table_name="dataset_selection"
    )
    op.drop_table("dataset_selection")
