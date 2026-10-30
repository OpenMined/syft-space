"""Stored overrides of removed settings are cleared by a migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa

from syft_benchmark.config import env_settings
from syft_benchmark.control.schemas import Instrument, RunRequest
from syft_benchmark.db.models import InstallationSettings, Job, Target
from syft_benchmark.db.session import session_scope

KEY = "pytest-dropped-settings"
# The migration tests clear the settings row they seed.
CLEARS_SETTINGS = True
VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"
MIGRATION = VERSIONS / "8e2c5a1f7b30_drop_extractive_mode_settings.py"
OPEN_BOOK_MIGRATION = VERSIONS / "b7e4d1c9a2f6_drop_the_open_book_arm.py"
LEFTOVERS = {"extractive_mode": "auto", "spacy_models": {"en": "en_core_web_sm"}}
EVERY_ARM = ["closed_book", "open_book", "model_with_context"]
ARMS = ["closed_book", "model_with_context"]


def _migration(path: Path = MIGRATION) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.needs_db
def test_the_migration_clears_the_leftover_keys(clean: None) -> None:
    instrument = {"concurrency": 2, **LEFTOVERS}
    with session_scope(env_settings()) as session:
        session.add(
            InstallationSettings(id=1, values={"retrieval_top_k": 7, **LEFTOVERS})
        )
        session.add(Target(key=KEY, url="http://space:8080", instrument=instrument))
        for state in ("queued", "done"):
            session.add(
                Job(
                    id=f"{KEY}-{state}",
                    target=KEY,
                    state=state,
                    params={"instrument": instrument},
                )
            )

    with session_scope(env_settings()) as session:
        for statement in _migration().STATEMENTS:
            session.execute(sa.text(statement))

    with session_scope(env_settings()) as session:
        values = session.get(InstallationSettings, 1).values  # type: ignore[union-attr]
        target = session.get(Target, KEY)
        queued = session.get(Job, f"{KEY}-queued")
        done = session.get(Job, f"{KEY}-done")
        assert target is not None and queued is not None and done is not None
        assert values == {"retrieval_top_k": 7}
        assert target.instrument == {"concurrency": 2}
        assert queued.params == {"instrument": {"concurrency": 2}}
        # A finished job keeps its params as it ran.
        assert done.params == {"instrument": instrument}
        Instrument.model_validate(target.instrument)
        RunRequest.model_validate(queued.params)


@pytest.mark.needs_db
def test_the_migration_drops_the_open_book_arm(clean: None) -> None:
    with session_scope(env_settings()) as session:
        session.add(
            InstallationSettings(id=1, values={"arms": EVERY_ARM, "concurrency": 2})
        )
        session.add(
            Target(key=KEY, url="http://space:8080", instrument={"arms": EVERY_ARM})
        )
        for state in ("queued", "done"):
            session.add(
                Job(
                    id=f"{KEY}-{state}",
                    target=KEY,
                    state=state,
                    params={"instrument": {"arms": EVERY_ARM}},
                )
            )

    with session_scope(env_settings()) as session:
        for statement in _migration(OPEN_BOOK_MIGRATION).STATEMENTS:
            session.execute(sa.text(statement))

    with session_scope(env_settings()) as session:
        values = session.get(InstallationSettings, 1).values  # type: ignore[union-attr]
        target = session.get(Target, KEY)
        queued = session.get(Job, f"{KEY}-queued")
        done = session.get(Job, f"{KEY}-done")
        assert target is not None and queued is not None and done is not None
        assert values == {"arms": ARMS, "concurrency": 2}
        assert target.instrument == {"arms": ARMS}
        assert queued.params == {"instrument": {"arms": ARMS}}
        # A finished job keeps its params as it ran.
        assert done.params == {"instrument": {"arms": EVERY_ARM}}
        Instrument.model_validate(target.instrument)


@pytest.mark.needs_db
def test_an_arms_list_left_empty_is_removed(clean: None) -> None:
    """A layer that named only the dropped arm inherits its arms afterwards."""
    only = ["open_book"]
    with session_scope(env_settings()) as session:
        session.add(InstallationSettings(id=1, values={"arms": only, "concurrency": 2}))
        session.add(
            Target(
                key=KEY,
                url="http://space:8080",
                instrument={"arms": only, "concurrency": 3},
            )
        )
        session.add(
            Job(
                id=f"{KEY}-queued",
                target=KEY,
                state="queued",
                params={"instrument": {"arms": only, "concurrency": 3}},
            )
        )

    with session_scope(env_settings()) as session:
        for statement in _migration(OPEN_BOOK_MIGRATION).STATEMENTS:
            session.execute(sa.text(statement))

    with session_scope(env_settings()) as session:
        values = session.get(InstallationSettings, 1).values  # type: ignore[union-attr]
        target = session.get(Target, KEY)
        queued = session.get(Job, f"{KEY}-queued")
        assert target is not None and queued is not None
        assert values == {"concurrency": 2}
        assert target.instrument == {"concurrency": 3}
        assert queued.params == {"instrument": {"concurrency": 3}}
        RunRequest.model_validate(queued.params)
