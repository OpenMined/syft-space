"""The registry of nodes under test: a table, with a file as its seed.

The order is exactly this. The table has priority, because it is edited from
the UI and the edits have to be visible in a running process. The file
``config/spaces.json`` stays and keeps working: an installation configured by
it comes up and measures, knowing nothing about the UI. A target from the file
becomes a table row at the very first use — after that it can be configured,
and the file no longer overrides it.

There is deliberately no way back: changes from the UI are not written to the
file. A service that rewrites a human's configuration file sooner or later
wipes out something it did not understand.

Both ways in come through ``resolve``: the service's job runner and the
console's commands ask this module for a node, and get the same row with the
same layers applied.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from syft_benchmark.config import Settings, SpaceConfig, get_settings
from syft_benchmark.control.compose import settings_for
from syft_benchmark.control.schemas import Instrument, Probe, TargetSpec, TargetView
from syft_benchmark.db import session_scope, store
from syft_benchmark.db.models import Credential, Target
from syft_benchmark.llm.catalog import pin_values


def _row(spec: TargetSpec, row: Target | None = None) -> Target:
    """A table row built from a target's description."""
    target = row or Target(key=spec.key)
    target.title = spec.title
    target.url = spec.url
    target.endpoint = spec.endpoint
    target.container = spec.container
    target.chroma_host = spec.chroma_host
    target.chroma_port = spec.chroma_port
    target.collection = spec.collection
    # A moving model name is pinned as it is saved — see `catalog.pin_values`.
    # The probe names no models and goes in as it came.
    target.instrument = pin_values(spec.instrument.overrides())
    target.probe = spec.probe.overrides()
    target.enabled = spec.enabled
    # A changed schedule is replanned from scratch. Keeping the old moment would
    # mean that switching a measurement from nightly to hourly leaves it nightly
    # until the night it was already waiting for — the owner would see the new
    # interval saved and the old one running.
    if (target.schedule, target.schedule_at) != (spec.schedule, spec.schedule_at):
        target.next_run_at = None
    target.schedule = spec.schedule
    target.schedule_at = spec.schedule_at
    # The token is not here. It speaks for the Space's owner, so it is sealed
    # and lives among the credentials — `_store_token` puts it there, where a
    # session is at hand to write both in one transaction.
    target.updated_at = datetime.now(UTC)
    return target


def _store_token(session: Session, spec: TargetSpec, conf: Settings) -> None:
    """Put the target's token where tokens live, or take it away.

    The token is kept until an empty one is sent. The settings form does not
    know the previous token and cannot send it back — it is never handed out —
    so without this proviso any save of the target's name would erase its
    access.
    """
    if spec.token is None:
        return
    name = store.target_secret(spec.key)
    if spec.token:
        store.set_secret(conf, name, spec.token, session=session)
    else:
        store.clear_secret(conf, name, session=session)


def view(target: Target, *, has_token: bool = False) -> TargetView:
    """A target for the UI: without the token, but saying that there is one.

    Whether there is one is passed in rather than read here: the tokens live in
    another table now, and a view of twenty targets that went to the database
    once per target would be twenty queries to answer one boolean each.
    """
    return TargetView(
        key=target.key,
        title=target.title or "",
        url=target.url,
        endpoint=target.endpoint or "",
        container=target.container or "",
        chroma_host=target.chroma_host or "localhost",
        chroma_port=target.chroma_port or 0,
        collection=target.collection or "",
        instrument=Instrument.model_validate(target.instrument or {}),
        probe=Probe.model_validate(target.probe or {}),
        enabled=target.enabled if target.enabled is not None else True,
        schedule=target.schedule or "",
        schedule_at=target.schedule_at or "",
        next_run_at=target.next_run_at,
        has_token=has_token,
    )


def save(
    session: Session, spec: TargetSpec, settings: Settings | None = None
) -> Target:
    """Create a target or overwrite an existing one."""
    conf = settings or get_settings()
    row = session.get(Target, spec.key)
    target = _row(spec, row)
    if row is None:
        session.add(target)
    _store_token(session, spec, conf)
    session.flush()
    return target


def drop(session: Session, key: str, settings: Settings | None = None) -> bool:
    """Remove a target. Its measurement history stays: it is about the endpoint.

    The token goes with it. Keeping a sealed secret for a target nobody can
    name any more would be keeping a secret nobody will ever use and nobody
    will think to remove.
    """
    row = session.get(Target, key)
    if row is None:
        return False
    session.delete(row)
    store.clear_secret(settings or get_settings(), store.target_secret(key), session)
    return True


def has_token(session: Session, key: str) -> bool:
    """Whether this target has a stored token."""
    return session.get(Credential, store.target_secret(key)) is not None


def tokens_for(session: Session, keys: list[str]) -> set[str]:
    """Which of these targets have a token — in one query, for a list view."""
    if not keys:
        return set()
    names = {store.target_secret(key): key for key in keys}
    found = session.scalars(select(Credential.name).where(Credential.name.in_(names)))
    return {names[name] for name in found}


def seed(session: Session, settings: Settings | None = None) -> int:
    """Carry into the table those targets from the file that are not there yet.

    Returns:
        How many targets were created. Existing ones are left alone: the file
        is a seed, not a source of truth, and re-reading it over a configured
        target would mean cancelling the owner's work on every restart.
    """
    conf = settings or get_settings()
    try:
        spaces = conf.load_spaces()
    except FileNotFoundError:
        return 0
    known = {key for (key,) in session.execute(select(Target.key))}
    added = 0
    for space in spaces:
        if space.key in known:
            continue
        spec = TargetSpec(
            key=space.key,
            title=space.title,
            url=space.url,
            endpoint=space.endpoint,
            token=space.token,
            container=space.container,
            chroma_host=space.chroma_host,
            chroma_port=space.chroma_port,
            collection=space.collection,
            probe=Probe(
                retrieval_top_k=space.retrieval_top_k,
                similarity_threshold=space.similarity_threshold,
            ),
        )
        session.add(_row(spec))
        _store_token(session, spec, conf)
        added += 1
    return added


def all_targets(session: Session, *, enabled_only: bool = False) -> list[Target]:
    """All targets in the order they were created."""
    stmt = select(Target).order_by(Target.created_at, Target.key)
    if enabled_only:
        stmt = stmt.where(Target.enabled.is_(True))
    return list(session.scalars(stmt))


def resolve(
    keys: list[str] | None = None, settings: Settings | None = None
) -> list[tuple[Settings, SpaceConfig]]:
    """The nodes under test, each with the settings it is measured by.

    The file is read only to fill an empty table, so there is exactly one
    answer to "where is this node's index and what is it measured with", and it
    is the answer the UI edits.

    The layers come with it. A node configured from the Space carries an
    instrument and a probe, and a console run that ignored them would write
    verdicts obtained under other settings into the same database, under the
    same node, with nothing to tell them apart afterwards.

    Args:
        keys: Which nodes; empty — every one of them, in key order
        settings: The installation's settings; the process's own by default

    Returns:
        Pairs of (the settings for this node, the node itself), in the order
        the keys were given, or by key when they were not.

    Raises:
        KeyError: a key no row answers to. The message names the known ones —
            a typo and an unregistered node look identical otherwise
    """
    conf = settings or get_settings()
    with session_scope(conf) as session:
        # The file is a seed and nothing else: it fills a table that has none
        # of its keys yet, and a node configured since is never overwritten.
        seed(session, conf)
        rows = {
            row.key: row for row in session.scalars(select(Target).order_by(Target.key))
        }
        if keys:
            unknown = [key for key in keys if key not in rows]
            if unknown:
                raise KeyError(
                    f"no such node in the registry: {', '.join(unknown)} "
                    f"(registered: {', '.join(rows) or 'none'})"
                )
            chosen = [rows[key] for key in keys]
        else:
            chosen = list(rows.values())
        # Inside the session: a row read here is handed over as plain settings
        # and a plain description, so nothing downstream touches a detached
        # object.
        return [settings_for(row, conf) for row in chosen]
