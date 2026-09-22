"""The installation's settings and its secrets, as they are actually stored.

One place where a setting is **written** — the row. A value that can be written
in two places is a value that disagrees with itself on the day somebody edits
the wrong one.

The environment is not a seed; it is the layer **under** the row, read-only and
supplied by whoever deployed the service:

    the built-in defaults -> the environment -> this row
        -> the Space's instrument -> the node's probe

Seeding was the first design and it was wrong. The container's compose file sets
the addresses that differ inside a container, and a one-time seed would have
applied them on the first start and ignored them for ever after — leaving an
installation pointed at a model provider inside itself.

Secrets follow the same order, and nothing copies them into the store by itself:
``set_secret`` does that, and until it is called the service says at startup
which keys it is still reading from the environment in the clear.

Reading is cached, because ``get_settings`` is called from several dozen places.
Every write here clears it.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from syft_benchmark.config import (
    BOOTSTRAP_FIELDS,
    SECRET_FIELDS,
    Settings,
    stored_fields,
)
from syft_benchmark.db.crypto import Cipher, SecretsNotConfigured, cipher_from
from syft_benchmark.db.models import Credential, InstallationSettings
from syft_benchmark.db.session import session_scope

# The one row. A constant rather than a magic number in four queries, and the
# table has a constraint that agrees with it.
ROW_ID = 1

# How a Space's token is named among the credentials. Prefixed rather than bare
# so that a target can never be called `judge_key`: the name is the associated
# data the ciphertext is bound to, and two things sharing a name would mean one
# could be opened in the other's place.
TARGET_PREFIX = "target:"


def target_secret(key: str) -> str:
    """The credential name a target's token is stored under."""
    return f"{TARGET_PREFIX}{key}"


# Names a credential may not take. They belong to the bootstrap and are read
# from the environment, so storing something under one of them would produce a
# secret that is never consulted — and nothing is harder to debug than a key
# that was definitely set and definitely not used.
RESERVED_NAMES: frozenset[str] = BOOTSTRAP_FIELDS


class SettingRejected(ValueError):
    """A setting that may not be written where it was being written."""


@dataclass(frozen=True, slots=True)
class SecretInfo:
    """What may be said about a stored secret: that it is there, and when."""

    name: str
    updated_at: datetime


@dataclass
class _Cached:
    """What was read from the database, and for which database."""

    url: str
    values: dict[str, Any]
    secrets: dict[str, str]


_lock = threading.Lock()
_cache: _Cached | None = None
# One complaint per process about an unreadable store. The doctor runs against
# a database that may be down, alembic runs before the table exists, and a
# warning per settings lookup would bury the one line that says why.
_warned = False


def invalidate() -> None:
    """Forget what was read. Every write here calls it."""
    global _cache
    with _lock:
        _cache = None


def cipher(base: Settings) -> Cipher:
    """The cipher for this installation.

    Raises:
        SecretsNotConfigured: no master key — and then a secret is not stored
            rather than stored in the clear
    """
    return cipher_from(base.secret_key, base.secret_keys_retired)


# --- reading ----------------------------------------------------------------


def apply(base: Settings) -> Settings:
    """The environment's settings with the stored ones laid over them.

    A database that cannot be read is not an error here: the doctor is expected
    to run against one that is down and say so, and migrations run before the
    table exists.
    """
    stored = _load(base)
    if stored is None:
        return base

    values: dict[str, Any] = base.model_dump()
    values.update(stored.values)
    values.update(stored.secrets)
    return type(base)(**values)


def read(base: Settings) -> dict[str, Any]:
    """The overrides the installation has set, as they are stored."""
    stored = _load(base)
    return dict(stored.values) if stored else {}


def secrets(base: Settings) -> list[SecretInfo]:
    """Which secrets are stored and when — never the values."""
    with session_scope(base) as session:
        rows = session.scalars(select(Credential).order_by(Credential.name))
        return [SecretInfo(name=r.name, updated_at=r.updated_at) for r in rows]


def secret(base: Settings, name: str) -> str | None:
    """One secret, opened. None — there is none under that name."""
    with session_scope(base) as session:
        row = session.get(Credential, name)
        if row is None:
            return None
        return cipher(base).open(name, row.secret, row.nonce, row.key_id)


def _load(base: Settings) -> _Cached | None:
    global _cache, _warned
    with _lock:
        if _cache is not None and _cache.url == base.database_url:
            return _cache
        try:
            with session_scope(base) as session:
                loaded = _Cached(
                    url=base.database_url,
                    values=_row_values(session),
                    secrets=_secret_values(session, base),
                )
        except SQLAlchemyError as exc:
            if not _warned:
                _warned = True
                logger.warning(
                    f"the stored settings could not be read, the built-in "
                    f"defaults and the environment are in force: {exc}"
                )
            return None
        _cache = loaded
        return loaded


def _row_values(session: Session) -> dict[str, Any]:
    row = session.get(InstallationSettings, ROW_ID)
    if row is None:
        return {}
    allowed = stored_fields()
    # Filtered on the way out as well as on the way in. A field that stopped
    # being a setting, or one that moved into the bootstrap, must not come back
    # to life because it is still sitting in an old row.
    return {k: v for k, v in (row.values or {}).items() if k in allowed}


def _secret_values(session: Session, base: Settings) -> dict[str, str]:
    """The sealed provider keys, opened, under the field names they belong to.

    A stale row is left out rather than raising: a settings lookup that threw
    would take the service down over one secret nobody can open.
    """
    out: dict[str, str] = {}
    rows = list(
        session.scalars(select(Credential).where(Credential.name.in_(SECRET_FIELDS)))
    )
    if not rows:
        return out
    try:
        box = cipher(base)
    except SecretsNotConfigured:
        logger.warning(
            "secrets are stored but BENCH_SECRET_KEY is not set — the provider "
            "keys cannot be opened and no call will be authorised"
        )
        return out
    for row in rows:
        try:
            out[row.name] = box.open(row.name, row.secret, row.nonce, row.key_id)
        except Exception as exc:  # noqa: BLE001 - a stale row must not be fatal
            logger.warning(f"the secret {row.name!r} could not be opened: {exc}")
    return out


# --- writing ----------------------------------------------------------------


def write(base: Settings, values: dict[str, Any]) -> dict[str, Any]:
    """Replace the installation's overrides with these.

    A whole document rather than a patch: "absent means unchanged" would give
    the owner no way to unset a field ever again.

    Raises:
        SettingRejected: a field the settings do not have, or one that may not
            be stored here
    """
    checked = validate(base, values)
    with session_scope(base) as session:
        row = session.get(InstallationSettings, ROW_ID)
        if row is None:
            row = InstallationSettings(id=ROW_ID, values=checked)
            session.add(row)
        else:
            row.values = checked
            row.updated_at = datetime.now(UTC)
    invalidate()
    return checked


def validate(base: Settings, values: dict[str, Any]) -> dict[str, Any]:
    """Check the overrides and return them in the shape they are stored in.

    A real check: the values are laid over the settings and the settings are
    built, so a bound only the model knows is caught here rather than at three
    in the morning when the schedule fires.

    Model names are pinned on the way in: ``~vendor/thing-latest`` means a
    different model every few months, so what is stored is what it meant on the
    day it was chosen.
    """
    from syft_benchmark.llm.catalog import pin_values

    values = pin_values(values, base)
    allowed = stored_fields()
    for field in values:
        if field in SECRET_FIELDS:
            raise SettingRejected(
                f"{field!r} is a secret and is not kept with the settings — "
                f"set it as a credential"
            )
        if field in BOOTSTRAP_FIELDS:
            raise SettingRejected(
                f"{field!r} is read from the environment and cannot be set from "
                f"here: it is either needed before this row can be read, or it "
                f"is the perimeter, which is not for whoever holds an API key"
            )
        if field not in allowed:
            raise SettingRejected(f"the settings do not know the field {field!r}")

    merged: dict[str, Any] = base.model_dump()
    merged.update(values)
    # ValidationError from here becomes a 422; its message names the field.
    checked = type(base)(**merged)
    dumped = checked.model_dump(mode="json")
    return {field: dumped[field] for field in values}


def set_secret(
    base: Settings, name: str, value: str, session: Session | None = None
) -> None:
    """Store one secret, sealed.

    Raises:
        SecretsNotConfigured: there is no master key, and nothing is written.
            A fallback to plain text is how an installation ends up with half
            its secrets encrypted and no record of which half
    """
    if not value:
        raise ValueError(
            f"the secret {name!r} is empty — use clear_secret to remove it"
        )
    blob, nonce, key_id = cipher(base).seal(name, value)

    def store_in(active: Session) -> None:
        row = active.get(Credential, name)
        if row is None:
            active.add(Credential(name=name, secret=blob, nonce=nonce, key_id=key_id))
        else:
            row.secret, row.nonce, row.key_id = blob, nonce, key_id
            row.updated_at = datetime.now(UTC)

    # A session may be passed in so that a secret and the row it belongs to are
    # written in one transaction: a target saved and its token stored apart
    # would leave the token behind when the save is rolled back.
    if session is not None:
        store_in(session)
    else:
        with session_scope(base) as own:
            store_in(own)
    invalidate()


def clear_secret(base: Settings, name: str, session: Session | None = None) -> bool:
    """Remove a secret. True — there was one."""

    def drop_in(active: Session) -> bool:
        row = active.get(Credential, name)
        if row is None:
            return False
        active.delete(row)
        return True

    if session is not None:
        gone = drop_in(session)
    else:
        with session_scope(base) as own:
            gone = drop_in(own)
    if gone:
        invalidate()
    return gone


def rotate(base: Settings) -> int:
    """Re-seal every secret under the active key.

    The middle step of a rotation: make the new key active, move the old one to
    the retired list, run this, then throw the old key away. Rows already on
    the active key are skipped, so an interrupted rotation is finished by
    re-running it.

    Returns:
        How many secrets were re-sealed
    """
    box = cipher(base)
    moved = 0
    with session_scope(base) as session:
        for row in session.scalars(select(Credential)):
            if row.key_id == box.active_id:
                continue
            plain = box.open(row.name, row.secret, row.nonce, row.key_id)
            row.secret, row.nonce, row.key_id = box.seal(row.name, plain)
            row.updated_at = datetime.now(UTC)
            moved += 1
    invalidate()
    return moved


# --- what is still in the clear ---------------------------------------------


def env_secrets(base: Settings) -> list[str]:
    """Which secrets are being read from the environment rather than the store.

    Not an error, and not fixed behind the operator's back: copying the key
    into the database would leave the plaintext in the file anyway. What the
    service owes them is to name it, so that "encrypted at rest" is never
    believed about a key that is not.
    """
    stored = {item.name for item in secrets(base)}
    return sorted(
        field
        for field in SECRET_FIELDS
        if getattr(base, field, "") and field not in stored
    )


def warn_about_env_secrets(base: Settings) -> None:
    """Say, once at startup, which keys are not in the store."""
    loose = env_secrets(base)
    if loose:
        logger.warning(
            f"read from the environment in the clear, not from the sealed "
            f"store: {', '.join(loose)}. To store them: "
            f"`syft-benchmark secrets set <name>`, then take them out of .env"
        )
