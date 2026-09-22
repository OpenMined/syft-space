"""Assembling a run's settings out of three layers.

The layers are applied in one and only one order: the installation's default →
the space's instrument → the node's probe. The order is neither symmetric nor
arbitrary — the closer a layer is to a specific node, the more authority it
has, because it was set by whoever knows most about that node.

The assembly happens on every launch, not once when the target is created.
That is a deliberate choice: an amended installation default — a new judge
model, a raised answer ceiling — has to reach every node by itself. The
settings snapshot is written into the job and into the run after the assembly,
and it is what explains yesterday's numbers; but it explains the past, it does
not determine the future.
"""

from __future__ import annotations

from typing import Any

from syft_benchmark.config import Settings, SpaceConfig, get_settings
from syft_benchmark.control.schemas import Instrument, Layer, Probe
from syft_benchmark.db import store
from syft_benchmark.db.models import Target


def merge(base: Settings, *layers: Layer) -> Settings:
    """The process's settings with the layers applied.

    Args:
        base: The installation's defaults — the environment and .env
        layers: The layers in ascending order of authority

    Returns:
        A new settings object. The original is not changed: one process serves
        several nodes at once, and amending the shared object for one of them
        would leak into the rest.

    Raises:
        ValueError: a layer sets a field the settings do not have — that is a
            typo in the contract, and swallowed silently it would mean a
            setting that changes nothing
    """
    values: dict[str, Any] = base.model_dump()
    known = set(type(base).model_fields)
    for layer in layers:
        for field, value in layer.overrides().items():
            if field not in known:
                raise ValueError(f"the settings do not know the field {field!r}")
            values[field] = value
    return type(base)(**values)


def settings_for(
    target: Target, base: Settings | None = None
) -> tuple[Settings, SpaceConfig]:
    """What to measure this target with, and how.

    Returns:
        The process's settings for this node and its description. The
        retrieval parameters stay in the settings and are left empty in the
        node's description: two places for one value would mean that one of
        them silently loses, and working out which would take reading the code.
    """
    settings = base or get_settings()
    conf = merge(
        settings,
        Instrument.model_validate(target.instrument or {}),
        Probe.model_validate(target.probe or {}),
    )
    # The empty values are filled in here rather than read as they are: column
    # defaults are applied on insert, and on a row not yet written they are None.
    space = SpaceConfig(
        key=target.key,
        title=target.title or "",
        url=target.url,
        endpoint=target.endpoint or "",
        # Opened here, at the last moment before the call that needs it. It is
        # sealed in the credentials and is never handed out to a UI or a log.
        token=store.secret(settings, store.target_secret(target.key)),
        container=target.container or "",
        chroma_host=target.chroma_host or "localhost",
        chroma_port=target.chroma_port or 0,
        collection=target.collection or "",
    )
    return conf, space
