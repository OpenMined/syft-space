"""The control API: the key, the target routes, the provider and the progress.

Without a key the API does not exist; with a wrong one it refuses. A target
survives a round trip without its token ever coming back out. The provider is
described without naming the key, role by role. A running job reads its
cancellation on every report, whether or not the progress write goes out.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from syft_benchmark.config import (
    ContextMode,
    JobPhase,
    JobState,
    Settings,
    get_settings,
)
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import targets as registry
from syft_benchmark.control.app import create_app
from syft_benchmark.control.schemas import Instrument, Probe, TargetSpec
from syft_benchmark.db.models import Job, Target
from syft_benchmark.db.session import session_scope

from support import AUTH

KEY = "pytest-target"


# --- the key and the target routes -----------------------------------------


@pytest.mark.needs_db
def test_without_a_key_the_control_api_does_not_exist() -> None:
    """Not "you may not" but "there is nothing here" — as with the mode off."""
    open_app = TestClient(
        create_app(get_settings().model_copy(update={"control_token": ""}))
    )
    assert open_app.get("/capabilities").status_code == 503
    assert open_app.get("/health").status_code == 200


@pytest.mark.needs_db
def test_a_wrong_key_is_refused(client: TestClient) -> None:
    assert (
        client.get("/targets", headers={"Authorization": "Bearer no"}).status_code
        == 401
    )


@pytest.mark.needs_db
def test_the_generators_are_offered_in_the_registry_order(client: TestClient) -> None:
    """The order the list arrives in is the order every page draws it in.

    The registry ends with the control generators, whose correct answer is a
    refusal: they qualify the measurement, they are not the first sight of it.
    """
    from syft_benchmark.generation.generators import CONTROL_KEYS, GENERATORS

    reply = client.get("/capabilities", headers=AUTH)
    assert reply.status_code == 200, reply.text
    offered = reply.json()["generators"]
    assert offered == list(GENERATORS)
    assert set(offered[-len(CONTROL_KEYS) :]) == set(CONTROL_KEYS)
    assert offered[-1] == "false_premise"


@pytest.mark.needs_db
def test_a_target_survives_a_round_trip(client: TestClient, clean: Any) -> None:
    body = TargetSpec(
        key=KEY,
        title="A test node",
        url="http://space.invalid",
        endpoint="ep",
        token="secret",
        instrument=Instrument(arms=[ContextMode.CLOSED_BOOK]),
        probe=Probe(retrieval_top_k=7),
    ).model_dump(mode="json")

    made = client.put(f"/targets/{KEY}", json=body, headers=AUTH)
    assert made.status_code == 200, made.text
    assert "secret" not in made.text
    assert made.json()["has_token"] is True

    got = client.get(f"/targets/{KEY}", headers=AUTH).json()
    assert got["probe"]["retrieval_top_k"] == 7
    assert got["instrument"]["arms"] == ["closed_book"]


@pytest.mark.needs_db
def test_the_key_in_the_address_and_in_the_body_must_agree(
    client: TestClient, clean: Any
) -> None:
    """Otherwise saving under one name would create a target under another."""
    body = TargetSpec(key="other", url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{KEY}", json=body, headers=AUTH).status_code == 422


def test_the_token_never_comes_back_out() -> None:
    """The Space access token is not handed outwards — only the flag that it exists.

    The flag is passed in rather than read off the row: the token does not live
    on the row, and a view that went to the database for it would make
    a list of twenty targets twenty queries.
    """
    row = Target(key="k", url="http://space", endpoint="ep")
    item = registry.view(row, has_token=True)
    assert item.has_token is True
    assert "token" not in {c.name for c in Target.__table__.columns}


# --- the model provider ----------------------------------------------------


def test_the_provider_is_described_without_naming_the_key() -> None:
    """The key leaves the service's environment neither by value nor as a hint of place.

    The benchmark does the computing, the bill goes to the key's owner, and
    there is no reason for a second copy of the secret to live in a service
    that never talks to the provider. What travels outwards is exactly what
    tells the owner what they are being measured with and at whose expense.
    """
    from syft_benchmark.control.installation_routes import provider_info

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-v1-secret-value",
        llm_app_name="stand",
        external_hosts=["openrouter.ai"],
    )
    info = provider_info(conf)
    assert info.key_set is True
    assert "secret" not in info.model_dump_json()
    assert info.url == "https://openrouter.ai/api/v1"
    assert info.external_hosts == ["openrouter.ai"]


def test_a_role_with_its_own_provider_is_shown_as_its_own() -> None:
    """The generator normally stays inside the perimeter, the subjects do not.

    One answer of "the provider is such-and-such" for every role is sometimes
    simply wrong, and the owner, looking at it, would think the documents go
    nowhere.
    """
    from syft_benchmark.control.installation_routes import provider_info

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="outer",
        generator_url="http://localhost:11434",
    )
    roles = {role.role: role for role in provider_info(conf).roles}
    assert roles["generator"].own is True
    assert roles["generator"].url == "http://localhost:11434"
    assert roles["subject"].own is False
    assert roles["subject"].url == "https://openrouter.ai/api/v1"


def test_each_role_says_whether_it_stays_inside_the_perimeter() -> None:
    """The perimeter rule decides the "on this machine" label, nothing else."""
    from syft_benchmark.control.installation_routes import provider_info

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        generator_url="http://ollama:11434",
        judge_url="http://[2606:4700::1111]/v1",
        subject_url="http://192.168.1.20:11434",
    )
    info = provider_info(conf)
    roles = {role.role: role.local for role in info.roles}
    assert info.local is False
    assert roles == {
        "generator": True,
        "subject": False,  # a private network address is outside
        "judge": False,
        "filter": False,  # follows the models under test
    }


# --- carrying the cancellation into the measurement ------------------------


@pytest.mark.needs_db
def test_the_cancellation_is_read_even_when_the_progress_write_is_held_back(
    clean: Any,
) -> None:
    """Holding back an UPDATE is thrift; holding back the flag is spending.

    Progress is written no more often than once every BEAT_SECONDS; the
    cancellation flag is read on every report, or a run goes on asking paid
    questions for the rest of the interval after the owner has pressed stop.
    """
    with session_scope() as session:
        session.add(
            Job(
                id="pytest-beat",
                target=KEY,
                state=JobState.RUNNING.value,
                phase=JobPhase.EVALUATE.value,
                params={},
                trigger="manual",
                message="",
                error="",
                created_at=datetime.now(UTC),
            )
        )

    reporter = job_queue.Reporter("pytest-beat", Settings())
    reporter._write(force=True)
    assert reporter.cancelled is False

    with session_scope() as session:
        job = session.get(Job, "pytest-beat")
        assert job is not None
        job.cancel_requested = True

    # Immediately after a forced write, so the throttle is certainly shut.
    reporter._write()

    assert reporter.cancelled is True

    with session_scope() as session:
        session.execute(delete(Job).where(Job.id == "pytest-beat"))


@pytest.mark.needs_db
def test_a_phase_that_writes_nothing_can_still_ask_whether_to_stop(clean: Any) -> None:
    """Generation reports no progress at all.

    A flag that only ever arrived on the back of a write would never reach it,
    and a stop pressed during a build on a paid model would do nothing for the
    tens of minutes it runs.
    """
    with session_scope() as session:
        session.add(
            Job(
                id="pytest-ask",
                target=KEY,
                state=JobState.RUNNING.value,
                phase=JobPhase.GENERATE.value,
                params={},
                trigger="manual",
                message="",
                error="",
                created_at=datetime.now(UTC),
            )
        )

    reporter = job_queue.Reporter("pytest-ask", Settings())
    assert reporter.stop_requested() is False

    with session_scope() as session:
        job = session.get(Job, "pytest-ask")
        assert job is not None
        job.cancel_requested = True

    assert reporter.stop_requested() is True

    with session_scope() as session:
        session.execute(delete(Job).where(Job.id == "pytest-ask"))
