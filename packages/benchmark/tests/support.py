"""Database and control-API helpers shared by the test modules.

``wipe`` clears every row the tests write under a pytest key; the ``clean``
fixture in ``conftest.py`` calls it with the module's ``SPACE``/``KEY``/``JOB``
constants. ``control_client`` and ``console_auth`` stand up the control API and
a console session the way an owner would: PUT the target, POST a session.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import delete, or_

from syft_benchmark.config import get_settings
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import store
from syft_benchmark.db.models import (
    Credential,
    InstallationSettings,
    Job,
    ProcessedUnit,
    QaPair,
    Result,
    Run,
    RunAggregate,
    Target,
    WriterCall,
)
from syft_benchmark.db.session import session_scope

TOKEN = "test-control-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
# A measurement is queued only with a web check model to screen its questions.
WEB_CHECK_MODEL = "openai/gpt-5.1"


def wipe(
    *keys: str, jobs: tuple[str, ...] | list[str] = (), settings: bool = False
) -> None:
    """Delete what the tests wrote under these Space/target keys and job ids.

    Children first: verdicts, runs, pairs, processed units, then the job rows
    (by target or by id) with their aggregates and writer calls, then the
    targets. ``settings`` also clears the installation row and every stored
    credential, and drops the store's cache that would answer from them.
    """
    with session_scope() as session:
        if keys:
            session.execute(delete(Result).where(Result.space.in_(keys)))
            session.execute(delete(Run).where(Run.space.in_(keys)))
            session.execute(delete(QaPair).where(QaPair.space.in_(keys)))
            session.execute(delete(ProcessedUnit).where(ProcessedUnit.space.in_(keys)))
        if jobs:
            session.execute(delete(WriterCall).where(WriterCall.job_id.in_(jobs)))
            session.execute(delete(RunAggregate).where(RunAggregate.job_id.in_(jobs)))
        if keys or jobs:
            session.execute(
                delete(Job).where(or_(Job.target.in_(keys), Job.id.in_(jobs)))
            )
        if keys:
            session.execute(delete(Target).where(Target.key.in_(keys)))
        if settings:
            session.execute(delete(Credential))
            session.execute(delete(InstallationSettings))
    if settings:
        # After the deletes: the cache is what the store would otherwise go on
        # answering from.
        store.invalidate()


def add_rows(*rows: Any) -> None:
    """Store the rows in one transaction, each flushed before the next.

    Flushed one by one, a row may point at one added just before it.
    """
    with session_scope() as session:
        for row in rows:
            session.add(row)
            session.flush()


def control_client(**update: Any) -> TestClient:
    """The control API with the test token and a web check model, over the
    assembled settings.

    Deliberately not entered as a context manager: that would start the worker
    and the ticker, and they would run the jobs a test queues against a node
    that is not there.
    """
    conf = get_settings().model_copy(
        update={"control_token": TOKEN, "filter_model": WEB_CHECK_MODEL, **update}
    )
    return TestClient(create_app(conf))


def register_target(client: TestClient, key: str, **fields: Any) -> None:
    """PUT a target at a node address that resolves nowhere."""
    body = TargetSpec(key=key, url="http://space.invalid", **fields)
    made = client.put(
        f"/targets/{key}", json=body.model_dump(mode="json"), headers=AUTH
    )
    assert made.status_code == 200, made.text


def mint_session(client: TestClient, key: str) -> dict[str, str]:
    """A console session for one target, as its bearer header."""
    minted = client.post(f"/targets/{key}/session", headers=AUTH)
    assert minted.status_code == 200, minted.text
    return {"Authorization": f"Bearer {minted.json()['token']}"}


def console_auth(client: TestClient, key: str, **fields: Any) -> dict[str, str]:
    """Register the target and open a console session on it."""
    register_target(client, key, **fields)
    return mint_session(client, key)
