"""Stored overrides of removed settings are cleared by a migration."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from sqlalchemy import delete

from syft_benchmark.config import env_settings
from syft_benchmark.control.schemas import Instrument, RunRequest
from syft_benchmark.db import store
from syft_benchmark.db.models import InstallationSettings, Job, Target
from syft_benchmark.db.session import session_scope

KEY = "pytest-dropped-settings"
MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "8e2c5a1f7b30_drop_extractive_mode_settings.py"
)
LEFTOVERS = {"extractive_mode": "auto", "spacy_models": {"en": "en_core_web_sm"}}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("drop_extractive", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db_ready() -> bool:
    try:
        with session_scope(env_settings()) as session:
            session.execute(sa.text("select 1"))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


@pytest.fixture
def clean() -> Iterator[None]:
    def wipe() -> None:
        with session_scope(env_settings()) as session:
            session.execute(delete(Target).where(Target.key == KEY))
            session.execute(delete(Job).where(Job.target == KEY))
            session.execute(delete(InstallationSettings))
        store.invalidate()

    wipe()
    yield
    wipe()


def test_the_settings_are_gone() -> None:
    assert "extractive_mode" not in Instrument.model_fields
    with pytest.raises(ValueError):
        Instrument.model_validate({"extractive_mode": "auto"})


@pytest.mark.skipif(not _db_ready(), reason="the benchmark database is unavailable")
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
