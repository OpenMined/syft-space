"""Assembling a run's settings out of three layers.

Applied in one order: the installation's default → the target's instrument →
the node's probe; the closer a layer is to a node, the more authority it has.
The assembly happens on every launch, so an amended installation default
reaches every node by itself.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from syft_benchmark.config import (
    MODEL_DEFAULT,
    Settings,
    SpaceConfig,
    get_settings,
    stored_fields,
)
from syft_benchmark.control.schemas import Instrument, Layer, Probe
from syft_benchmark.db import store
from syft_benchmark.db.models import Target
from syft_benchmark.llm import judge_providers, subject_providers
from syft_benchmark.report.job_params import configured_panel


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


def target_panel(target: Target, base: Settings) -> list[str]:
    """The judges configured for the target, primary first."""
    conf = merge(
        base,
        Instrument.model_validate(target.instrument or {}),
        Probe.model_validate(target.probe or {}),
    )
    return configured_panel(conf)


def effective_defaults(conf: Settings) -> dict[str, Any]:
    """What an unset instrument or probe field resolves to, at each layer.

    Read by ``/defaults`` (the whole shape, for the connection-wide settings
    form) and by ``GET /console/probe`` (the probe layer only).
    """
    dumped = conf.model_dump(mode="json")
    # Every layer field is a settings field of the same name (``merge`` insists
    # on it), so the layers are read off the settings by field; the three
    # exceptions are the values the settings hold in another shape.
    resolved: dict[str, Any] = {
        "subject_models": [p.model for p in subject_providers(conf)],
        "judge_models": [p.model for p in judge_providers(conf)],
        "judge_temperature": (
            MODEL_DEFAULT if conf.judge_temperature is None else conf.judge_temperature
        ),
    }

    def layer(fields: Iterable[str]) -> dict[str, Any]:
        return {f: resolved[f] if f in resolved else getattr(conf, f) for f in fields}

    return {
        "instrument": Instrument(**layer(Instrument.model_fields)),
        "probe": Probe(**layer(Probe.model_fields)),
        # The bottom layer, asked of the settings rather than listed again;
        # ``stored_fields`` keeps every secret out.
        "installation": {field: dumped[field] for field in sorted(stored_fields())},
    }
