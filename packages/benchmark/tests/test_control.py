"""The control layer: the settings layers, the target registry and the job queue.

Some of the checks need a live database: the queue is a row two threads look
at, and a stubbed session would check a conspiracy of stubs rather than the
behaviour. Without a database such checks are skipped rather than lying green.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete

from syft_benchmark.config import (
    ContextMode,
    DatasetMode,
    JobPhase,
    JobState,
    Settings,
    get_settings,
)
from syft_benchmark.control import jobs as job_queue
from syft_benchmark.control import targets as registry
from syft_benchmark.control.app import create_app
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import (
    Instrument,
    Layer,
    Probe,
    RunRequest,
    TargetSpec,
)
from syft_benchmark.db.models import Job, Target
from syft_benchmark.db.session import session_scope

TOKEN = "test-control-token"
KEY = "pytest-target"


# --- the settings layers ----------------------------------------------------


def test_the_nearer_layer_wins() -> None:
    """The probe outranks the instrument, the instrument the defaults.

    The order is asymmetric in meaning: the closer a layer is to a particular
    node, the more whoever set it knew about that node.
    """
    base = Settings(retrieval_top_k=5, judge_model="base-judge")
    out = merge(base, Instrument(judge_model="panel"), Probe(retrieval_top_k=11))
    assert out.judge_model == "panel"
    assert out.retrieval_top_k == 11


def test_an_unset_field_inherits_and_does_not_zero_anything() -> None:
    """An unset field means "take it from above", not zero.

    Without that distinction a settings form opened and closed without a single
    edit would have zeroed the freshness window and the similarity threshold.
    """
    base = Settings(document_window_days=30, similarity_threshold=0.4)
    out = merge(base, Probe())
    assert out.document_window_days == 30
    assert out.similarity_threshold == 0.4


def test_an_explicit_empty_list_is_a_decision_and_survives() -> None:
    """An empty list of disabled generators means "do not disable any".

    It is indistinguishable from unset by looks and opposite in meaning, which
    is why merging goes by the fields that were set, not by the non-empty ones.
    """
    base = Settings(disabled_generators=["mcq"])
    assert merge(base, Probe(disabled_generators=[])).disabled_generators == []


def test_merging_the_source_settings_leaves_them_alone() -> None:
    """One process measures several nodes: an edit to the shared object would leak."""
    base = Settings(retrieval_top_k=5)
    merge(base, Probe(retrieval_top_k=42))
    assert base.retrieval_top_k == 5


def test_a_model_name_keeps_the_quotes_of_nowhere_it_came_from() -> None:
    """A list pasted in the shape it has in a config file is still a list.

    On the DemoSyft rig every one of 288 calls was refused with 400 because the
    names reached the provider as `"qwen/qwen3.6-plus"`, quotes and all: the
    form split the pasted list on the comma and took nothing off. The run went
    through all six passes and came back with no verdicts.
    """
    instrument = Instrument(
        subject_models=[
            '"deepseek/deepseek-r1-0528"',
            '["x-ai/grok-4.20"',
            '"qwen/qwen3.6-plus"]',
        ],
        generator_model=" anthropic/claude-opus-5 ",
    )
    assert instrument.subject_models == [
        "deepseek/deepseek-r1-0528",
        "x-ai/grok-4.20",
        "qwen/qwen3.6-plus",
    ]
    assert instrument.generator_model == "anthropic/claude-opus-5"


def test_a_value_that_is_not_one_model_name_is_refused_here_not_at_the_provider() -> (
    None
):
    """What no trimming can repair is refused, and the reason is said.

    The wrappers at the ends are leftovers of a copy; a comma or a space in the
    middle is a whole list in one field, and guessing where to split it is not
    this layer's business. Refusing costs a message; passing it on costs a run.
    """
    for bad in ('"a/b", "c/d"', "a b", "openai/gpt 5"):
        with pytest.raises(ValidationError):
            Instrument(subject_models=[bad])
    with pytest.raises(ValidationError):
        Instrument(judge_model='"a/b"x"')
    with pytest.raises(ValidationError):
        Instrument(judge_models=[""])


def test_a_stored_layer_still_opens_after_the_check_arrived() -> None:
    """A row saved before the check must not be readable only from the database.

    The target the owner has to fix is read back through this same model. If
    reading it raised, the form that fixes it would not open either, and the
    one way out would be an UPDATE by hand.
    """
    saved = {"subject_models": ['"qwen/qwen3.6-plus"'], "judge_model": '"x/y"'}
    healed = Instrument.model_validate(saved)
    assert healed.subject_models == ["qwen/qwen3.6-plus"]
    assert healed.judge_model == "x/y"


def test_a_field_the_settings_do_not_know_is_refused() -> None:
    """A typo in the contract is a setting that silently changes nothing."""

    class Odd(Layer):
        nonsense: int = 0

    with pytest.raises(ValueError, match="do not know the field"):
        merge(Settings(), Odd(nonsense=1))


def test_the_target_layers_reach_the_settings() -> None:
    row = Target(
        key="k",
        url="http://space",
        endpoint="ep",
        instrument={"judge_model": "panel"},
        probe={"dataset_mode": DatasetMode.ROLLING.value, "retrieval_top_k": 7},
    )
    conf, space = settings_for(row, Settings())
    assert conf.judge_model == "panel"
    assert conf.dataset_mode is DatasetMode.ROLLING
    assert conf.retrieval_top_k == 7
    assert space.key == "k" and space.endpoint == "ep"


def test_search_parameters_live_in_one_place_only() -> None:
    """Two places for one value would mean one of them silently loses.

    The retrieval parameters stay in the settings; in the node's description
    they are empty, and ``retrieval_for`` takes them from where they are.
    """
    row = Target(
        key="k", url="http://space", endpoint="ep", probe={"retrieval_top_k": 7}
    )
    conf, space = settings_for(row, Settings())
    assert space.retrieval_top_k is None
    assert conf.retrieval_for(space) == (7, conf.similarity_threshold)


# --- the target: what is visible from outside -------------------------------


def test_the_token_never_comes_back_out() -> None:
    """The Space access token is not handed outwards — only the flag that it exists.

    The flag is passed in rather than read off the row: the token does not live
    on the row any more, and a view that went to the database for it would make
    a list of twenty targets twenty queries.
    """
    row = Target(key="k", url="http://space", endpoint="ep")
    item = registry.view(row, has_token=True)
    assert item.has_token is True
    assert "token" not in {c.name for c in Target.__table__.columns}


def test_a_target_keeps_only_what_was_set() -> None:
    """A target holds an overlay, not a snapshot: a default must reach it itself."""
    row = registry._row(
        TargetSpec(
            key="k",
            url="http://space",
            endpoint="ep",
            probe=Probe(retrieval_top_k=7),
        )
    )
    assert row.probe == {"retrieval_top_k": 7}


# --- job states -------------------------------------------------------------


def test_a_cancelled_job_is_finished_and_not_an_error() -> None:
    """A measurement stopped by its owner is finished, not broken: the data stayed."""
    assert JobState.CANCELLED.final
    assert JobState.QUEUED.final is False
    assert JobState.RUNNING.final is False


# --- a live database --------------------------------------------------------


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.target == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Any:
    """Clear away the target and its jobs — before and after."""

    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.target == KEY))
            session.execute(delete(Target).where(Target.key == KEY))

    wipe()
    yield
    wipe()


@pytest.fixture
def client() -> Any:
    """An API client with a configured key.

    Deliberately without a context manager: it would raise the worker thread,
    and that would set about running the jobs created in the test against a
    non-existent node.
    """
    conf = get_settings().model_copy(update={"control_token": TOKEN})
    return TestClient(create_app(conf))


AUTH = {"Authorization": f"Bearer {TOKEN}"}


@needs_db
def test_without_a_key_the_control_api_does_not_exist() -> None:
    """Not "you may not" but "there is nothing here" — as with the mode off."""
    open_app = TestClient(
        create_app(get_settings().model_copy(update={"control_token": ""}))
    )
    assert open_app.get("/capabilities").status_code == 503
    assert open_app.get("/health").status_code == 200


@needs_db
def test_a_wrong_key_is_refused(client: TestClient) -> None:
    assert (
        client.get("/targets", headers={"Authorization": "Bearer no"}).status_code
        == 401
    )


@needs_db
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


@needs_db
def test_the_key_in_the_address_and_in_the_body_must_agree(
    client: TestClient, clean: Any
) -> None:
    """Otherwise saving under one name would create a target under another."""
    body = TargetSpec(key="other", url="http://space.invalid").model_dump(mode="json")
    assert client.put(f"/targets/{KEY}", json=body, headers=AUTH).status_code == 422


@needs_db
def test_the_same_target_is_not_measured_twice_at_once(
    client: TestClient, clean: Any
) -> None:
    """A double press of the button must not mean a double measurement of one node."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json"),
        headers=AUTH,
    )
    first = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    second = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH)
    assert first.status_code == 202
    assert second.json()["id"] == first.json()["id"]


@needs_db
def test_a_disabled_target_is_not_measured(client: TestClient, clean: Any) -> None:
    spec = TargetSpec(key=KEY, url="http://space.invalid", enabled=False)
    client.put(f"/targets/{KEY}", json=spec.model_dump(mode="json"), headers=AUTH)
    assert client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).status_code == 409


@needs_db
def test_a_queued_job_is_dropped_on_the_spot(client: TestClient, clean: Any) -> None:
    """No work has been done on it yet — so there is nothing to finish either."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(key=KEY, url="http://space.invalid").model_dump(mode="json"),
        headers=AUTH,
    )
    job_id = client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).json()["id"]
    stopped = client.post(f"/jobs/{job_id}/cancel", headers=AUTH)
    assert stopped.json()["state"] == JobState.CANCELLED.value
    assert client.post(f"/jobs/{job_id}/cancel", headers=AUTH).status_code == 409


@needs_db
def test_a_run_keeps_the_layers_it_was_asked_with(
    client: TestClient, clean: Any
) -> None:
    """A trial run with a different threshold must not rewrite the target's setting."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(
            key=KEY, url="http://space.invalid", probe=Probe(retrieval_top_k=3)
        ).model_dump(mode="json"),
        headers=AUTH,
    )
    request = RunRequest(probe=Probe(retrieval_top_k=9)).model_dump(mode="json")
    job_id = client.post(f"/targets/{KEY}/runs", json=request, headers=AUTH).json()[
        "id"
    ]

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.params["probe"]["retrieval_top_k"] == 9
        target = session.get(Target, KEY)
        assert target is not None
        assert target.probe["retrieval_top_k"] == 3


@needs_db
def test_a_job_running_when_the_service_died_is_closed_on_restart(clean: Any) -> None:
    """Otherwise it is an eternally live measurement and a queue locked forever."""
    with session_scope() as session:
        session.add(
            Job(
                id="pytest-stale-job",
                target=KEY,
                state=JobState.RUNNING.value,
                phase=JobPhase.EVALUATE.value,
            )
        )
    try:
        assert job_queue.sweep() >= 1
        with session_scope() as session:
            job = session.get(Job, "pytest-stale-job")
            assert job is not None
            assert job.state == JobState.FAILED.value
            # A code, not a phrase: the job's row is read by a foreign UI.
            assert job.error == job_queue.SERVICE_RESTARTED
    finally:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.id == "pytest-stale-job"))


# --- the field descriptions -------------------------------------------------


def test_every_setting_is_placed_in_a_group() -> None:
    """A field without a group lands in the wrong place, and only the eye notices.

    Forty fields in one column in declaration order means "similarity
    threshold" sitting between "panel of judges" and "freshness window".
    """
    from syft_benchmark.control.formfields import GROUPS, catalogue

    named = {f["name"] for f in catalogue()["instrument"]} | {
        f["name"] for f in catalogue()["probe"]
    }
    assert named <= set(GROUPS), f"without a group: {sorted(named - set(GROUPS))}"


def test_the_field_catalogue_carries_no_prose() -> None:
    """Labels belong to whoever displays them, and in their reader's language.

    A field description in one language arriving in a UI written in another is
    not a translation, it is a breakage. The same rule by which the card hands
    out ``trust.flags`` as codes rather than sentences.
    """
    from syft_benchmark.control.formfields import catalogue

    allowed = {
        "name",
        "type",
        "group",
        "choices",
        # The name of a list too long to inline, not a word to show anybody.
        "catalog",
        "item_type",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
    fields = catalogue()["instrument"] + catalogue()["probe"]
    extra = {key for field in fields for key in field} - allowed
    assert not extra, f"more than intended travelled outwards: {sorted(extra)}"


def test_a_choice_field_says_what_the_choices_are() -> None:
    """Otherwise the form will offer the set mode as free text and accept a typo."""
    from syft_benchmark.control.formfields import catalogue

    by_name = {f["name"]: f for f in catalogue()["probe"]}
    assert by_name["dataset_mode"]["choices"] == ["incremental", "rolling", "rebuild"]
    assert by_name["similarity_threshold"]["maximum"] == 1.0


def test_a_list_of_choices_keeps_both_the_shape_and_the_choices() -> None:
    """The arms are a list drawn from an enum, and the form has to know both facts."""
    from syft_benchmark.control.formfields import catalogue

    arms = next(f for f in catalogue()["instrument"] if f["name"] == "arms")
    assert arms["type"] == "array"
    assert arms["item_type"] == "string"
    assert "closed_book" in arms["choices"]


def test_a_blocked_arm_travels_as_a_code() -> None:
    """The reason is displayed by a foreign UI, in the language of its own reader.

    A sentence in one language arriving on an owner's page written in another
    is not a translation, it is a breakage. The same rule by which the card
    hands out ``trust.flags`` as codes.
    """
    from syft_benchmark.config import ContextSource
    from syft_benchmark.runs.execute import (
        NO_ANSWER_TO_GRADE,
        arm_blocker,
        blocker_code,
    )

    code = blocker_code(ContextMode.OPEN_BOOK, "raw", ContextSource.ENDPOINT_FRAGMENTS)
    assert code == NO_ANSWER_TO_GRADE
    assert " " not in code
    # The prose stays — it is ours, for the console and for a run note.
    assert arm_blocker(ContextMode.OPEN_BOOK, "raw", ContextSource.ENDPOINT_FRAGMENTS)


def test_a_measurable_arm_is_not_blocked_by_anything() -> None:
    """An empty code means "the arm is measurable" and needs no separate check."""
    from syft_benchmark.config import ContextSource
    from syft_benchmark.runs.execute import blocker_code

    assert blocker_code(ContextMode.OPEN_BOOK, "summary", ContextSource.NONE) == ""
    # The node's mode did not read — that is a diagnostic failure, not a known
    # incompatibility, and a run must not be cancelled over it.
    assert blocker_code(ContextMode.OPEN_BOOK, "", ContextSource.NONE) == ""


def test_the_job_row_says_nothing_a_renderer_would_have_to_translate() -> None:
    """The job's row is read by a foreign UI, in the language of its own reader.

    The state and the phase are codes by construction; so are our own reasons
    for a refusal. Only the text of a failed call passes through as is: it
    cannot be enumerated, and hiding it is worse than showing it untranslated.
    """
    ours = {
        job_queue.TARGET_GONE,
        job_queue.NO_CARD,
        job_queue.PUBLISH_REFUSED,
        job_queue.SERVICE_RESTARTED,
        job_queue.NOTHING_GRADED,
        job_queue.NO_QUESTIONS,
        job_queue.NOTHING_GENERATED,
    }
    assert all(" " not in code for code in ours)
    assert all(code == code.lower() for code in ours)


def test_a_run_that_graded_nothing_does_not_count_as_a_measurement() -> None:
    """Reaching the end and measuring something are different things.

    A model provider that is down gives a full pass over the set, zero verdicts
    and a perfectly comfortable outcome. The owner, looking at "Finished",
    would go looking for numbers that are not there.
    """
    from syft_benchmark.scheduler import Measured

    assert Measured(asked=20, graded=0, failed=20).measured_nothing is True
    assert Measured(asked=20, graded=18, failed=2).measured_nothing is False
    # Not a single question was asked — that is an empty set, not a failed
    # measurement.
    assert Measured().measured_nothing is False


def test_a_set_nobody_could_build_is_not_an_empty_set() -> None:
    """The two look the same from outside and ask opposite things of the owner.

    Nothing built because there were no new chunks is the ordinary outcome of a
    corpus that has not moved; nothing built because every call was refused is a
    broken rig.
    """
    from syft_benchmark.scheduler import Measured

    refused = Measured(generated_nothing=True, generation_failure_sample="qa: 401")
    assert refused.generated_nothing is True
    # Nothing built and nothing refused: a corpus with no new chunks.
    assert Measured().generated_nothing is False


def test_the_generation_that_built_nothing_carries_the_call_that_failed() -> None:
    """The same rule as for grading: the code says what, the text says which."""
    line = job_queue._with_sample(
        job_queue.NOTHING_GENERATED,
        "qa: anthropic/claude-sonnet-4.6: [Errno 101] Network is unreachable",
    )
    assert line.startswith(f"{job_queue.NOTHING_GENERATED}: ")
    assert "Network is unreachable" in line


def test_the_run_that_graded_nothing_carries_the_call_that_failed() -> None:
    """The code says nothing was graded; which failure it was is text.

    A spent key, a model name with quotes round it, a dropped network and a
    node that is down all end a run the same way. On the rig the wording
    guessed at "the provider is down" while the provider was answering 400 —
    and the search went to the network instead of to the name.
    """
    line = job_queue._with_sample(
        job_queue.NOTHING_GRADED,
        'ERROR: "qwen/qwen3.6-plus" -> 400: not a valid model ID; retry 2',
    )
    assert line.startswith(f"{job_queue.NOTHING_GRADED}: ")
    assert "not a valid model ID" in line
    # The reasons are joined with semicolons and split apart again by whoever
    # renders them: one inside the sample would tear it into meaningless lines.
    assert ";" not in line
    assert len(line) <= len(job_queue.NOTHING_GRADED) + 2 + job_queue.SAMPLE_CHARS


def test_with_nothing_to_show_the_code_stands_alone() -> None:
    """No sample, no trailing colon: the code is read as a code."""
    assert job_queue._with_sample(job_queue.NOTHING_GRADED, "") == (
        job_queue.NOTHING_GRADED
    )


def test_a_run_with_an_empty_set_says_so_instead_of_reporting_success() -> None:
    """There were runs and nothing to ask — that is not a good measurement.

    Most often this is what a freshness window that let no document through
    looks like.
    """
    from syft_benchmark.scheduler import Measured

    assert Measured(passes=2, asked=0).had_nothing_to_ask is True
    # Resuming is the opposite case: the questions were not asked because there
    # are already verdicts for them.
    assert Measured(passes=2, asked=0, resumed=30).had_nothing_to_ask is False
    assert Measured(passes=2, asked=30, graded=30).had_nothing_to_ask is False


# --- the model provider -----------------------------------------------------


def test_the_provider_is_described_without_naming_the_key() -> None:
    """The key leaves the service's environment neither by value nor as a hint of place.

    The benchmark does the computing, the bill goes to the key's owner, and
    there is no reason for a second copy of the secret to live in a service
    that never talks to the provider. What travels outwards is exactly what
    tells the owner what they are being measured with and at whose expense.
    """
    from syft_benchmark.control.app import _provider

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-v1-secret-value",
        llm_app_name="stand",
        external_hosts=["openrouter.ai"],
    )
    info = _provider(conf)
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
    from syft_benchmark.control.app import _provider

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="outer",
        generator_url="http://localhost:11434",
    )
    roles = {role.role: role for role in _provider(conf).roles}
    assert roles["generator"].own is True
    assert roles["generator"].url == "http://localhost:11434"
    assert roles["subject"].own is False
    assert roles["subject"].url == "https://openrouter.ai/api/v1"


def test_the_provider_is_not_editable_from_outside() -> None:
    """The provider is set by the service's environment, and the form displays it.

    Editing it from here would mean a copy of the key in the benchmark's
    database — and, on a shared installation, that one owner changes the bill
    for everyone else.
    """
    from syft_benchmark.control.app import _provider

    assert _provider(Settings()).editable is False


# --- the progress of a measurement ------------------------------------------


def test_progress_counts_passes_and_questions_separately() -> None:
    """Runs and questions inside a run are different units.

    Merged into one bar they both lie: "43 of 120" is the questions of one run,
    while a measurement holds dozens of runs.
    """
    from syft_benchmark.control.schemas import JobView

    job = JobView(
        id="j",
        target="t",
        state="running",
        phase="evaluate",
        done=2,
        total=6,
        step_done=30,
        step_total=120,
        message="",
        trigger="manual",
        error="",
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
    )
    assert job.share == 2 / 6
    assert job.questions_total == 720
    assert job.questions_done == 2 * 120 + 30


def test_the_scale_of_the_run_is_unknown_until_the_first_pass_picks_tasks() -> None:
    """Zero means "still counting", not "nothing to ask".

    Until then there is nothing to draw a bar from, and drawn from a zero it
    would show a finished measurement.
    """
    from syft_benchmark.control.schemas import JobView

    job = JobView(
        id="j",
        target="t",
        state="running",
        phase="generate",
        done=0,
        total=0,
        message="",
        trigger="manual",
        error="",
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
    )
    assert job.share is None
    assert job.questions_total == 0


# --- carrying the cancellation into the measurement -------------------------


@needs_db
def test_the_cancellation_is_read_even_when_the_progress_write_is_held_back(
    clean: Any,
) -> None:
    """Holding back an UPDATE is thrift; holding back the flag is spending.

    Progress is written no more often than once every BEAT_SECONDS, and the
    flag used to ride along with it. A run that reported twice in a second
    therefore went on asking paid questions for the rest of the interval after
    the owner had pressed stop.
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

    reporter = job_queue.Reporter("pytest-beat")
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


@needs_db
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

    reporter = job_queue.Reporter("pytest-ask")
    assert reporter.stop_requested() is False

    with session_scope() as session:
        job = session.get(Job, "pytest-ask")
        assert job is not None
        job.cancel_requested = True

    assert reporter.stop_requested() is True

    with session_scope() as session:
        session.execute(delete(Job).where(Job.id == "pytest-ask"))
