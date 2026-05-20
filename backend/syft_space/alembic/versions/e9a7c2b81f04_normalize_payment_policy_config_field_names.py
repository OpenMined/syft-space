"""normalize payment policy configuration field names

Revision ID: e9a7c2b81f04
Revises: 8d5a3f1b7e29
Create Date: 2026-05-20 13:30:00.000000

Canonicalizes legacy payment policy configurations:

- Renames `price_per_request` / `price_per_document` to `price` (the
  unified field introduced when MPP and Xendit configs were merged).
- Sets `unit_type` to the canonical singular value (`"request"` /
  `"document"`), replacing the legacy plural `"requests"` form that
  predates the typed Literal field.

These shapes lived in the DB before the per-document pricing refactor.
The runtime accepts the old field names via AliasChoices on input, but
read paths surface the raw JSON to the frontend, so the UI was breaking
on legacy rows. This migration normalizes them once.

No app code is imported. The coercion rules are inlined so future
refactors of the policy config classes don't break replays of this
migration.
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9a7c2b81f04"
down_revision: str | None = "8d5a3f1b7e29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Map policy_type -> (legacy price key, canonical unit_type)
_PAYMENT_TYPES: dict[str, tuple[str, str]] = {
    "xendit_per_request": ("price_per_request", "request"),
    "xendit_per_document": ("price_per_document", "document"),
    "mpp_per_request": ("price_per_request", "request"),
    "mpp_per_document": ("price_per_document", "document"),
}


def _load_config(raw: object) -> dict:
    """SQLite stores JSON as TEXT; other backends may return dicts."""
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _select_payment_policies(bind):
    return bind.execute(
        sa.text(
            "SELECT id, policy_type, configuration FROM policies "
            "WHERE policy_type IN :types"
        ).bindparams(sa.bindparam("types", expanding=True)),
        {"types": list(_PAYMENT_TYPES)},
    ).fetchall()


def _write_config(bind, row_id, new_config: dict) -> None:
    bind.execute(
        sa.text("UPDATE policies SET configuration = :cfg WHERE id = :id"),
        {"cfg": json.dumps(new_config), "id": row_id},
    )


def upgrade() -> None:
    bind = op.get_bind()
    for row_id, policy_type, config_raw in _select_payment_policies(bind):
        config = _load_config(config_raw)
        legacy_key, canonical_unit = _PAYMENT_TYPES[policy_type]

        new_config = dict(config)
        # Rename legacy price key. If both exist, `price` wins (canonical),
        # the legacy key is just dropped.
        if legacy_key in new_config and "price" not in new_config:
            new_config["price"] = new_config.pop(legacy_key)
        else:
            new_config.pop(legacy_key, None)
        # Force canonical unit_type — overrides plural forms and adds when
        # missing. Safe because per-type the canonical value is determined
        # by policy_type, not by config content.
        new_config["unit_type"] = canonical_unit

        if new_config != config:
            _write_config(bind, row_id, new_config)


def downgrade() -> None:
    bind = op.get_bind()
    for row_id, policy_type, config_raw in _select_payment_policies(bind):
        config = _load_config(config_raw)
        legacy_key, _ = _PAYMENT_TYPES[policy_type]

        new_config = dict(config)
        if "price" in new_config:
            new_config[legacy_key] = new_config.pop("price")
        new_config.pop("unit_type", None)

        if new_config != config:
            _write_config(bind, row_id, new_config)
