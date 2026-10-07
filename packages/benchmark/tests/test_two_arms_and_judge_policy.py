"""Two arms, the web check model field, and the same-company rule.

The page offers two arms and two judge policies, and refuses a judge from the
same company as a tested model. The API refuses it too, so it cannot be
bypassed; stored rows that still list the retired arm keep opening.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import delete

from syft_benchmark.config import (
    ContextMode,
    ContextSource,
    JudgePolicy,
    Settings,
    get_settings,
)
from syft_benchmark.control.app import create_app
from syft_benchmark.control.formfields import catalogue
from syft_benchmark.control.schemas import Instrument, RunRequest, TargetSpec
from syft_benchmark.db.models import Job, Target
from syft_benchmark.db.session import session_scope
from syft_benchmark.llm import Provider
from syft_benchmark.llm.roles import clash_refusal, company_of, judge_clashes

TOKEN = "test-control-token"
WEB_CHECK_MODEL = "openai/gpt-5.1"
KEY = "pytest-judge-policy"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


# --- the web check model ----------------------------------------------------


def test_the_web_check_model_is_a_catalogue_field_of_its_own_group() -> None:
    by_name = {f["name"]: f for f in catalogue()["instrument"]}
    field = by_name["filter_model"]
    assert field["catalog"] == "models"
    assert field["group"] == "filter"
    assert "filter" in catalogue()["groups"]


def test_the_web_check_is_off_unless_a_model_is_named() -> None:
    assert Settings().filter_model is None
    assert Instrument(filter_model=' "openai/gpt-5.1" ').filter_model == (
        "openai/gpt-5.1"
    )
    with pytest.raises(ValidationError):
        Instrument(filter_model="openai/gpt-5.1, x-ai/grok-4.6")


# --- two arms -----------------------------------------------------------------


def test_the_retired_arm_is_not_offered_or_defaulted() -> None:
    arms = next(f for f in catalogue()["instrument"] if f["name"] == "arms")
    assert arms["choices"] == ["closed_book", "model_with_context"]
    assert Settings().arms == [ContextMode.CLOSED_BOOK, ContextMode.MODEL_WITH_CONTEXT]


def test_a_stored_row_with_the_retired_arm_still_opens() -> None:
    layer = Instrument.model_validate({"arms": ["closed_book", "open_book"]})
    assert layer.arms == [ContextMode.CLOSED_BOOK]
    request = RunRequest.model_validate({"instrument": {"arms": ["open_book"]}})
    assert request.instrument is not None and request.instrument.arms == []
    conf = Settings(arms=[ContextMode.OPEN_BOOK, ContextMode.MODEL_WITH_CONTEXT])
    assert conf.arms == [ContextMode.MODEL_WITH_CONTEXT]


def test_the_retired_arm_is_not_run() -> None:
    from syft_benchmark.config import SpaceConfig
    from syft_benchmark.runs import run_pass

    space = SpaceConfig(key="s", url="http://space.invalid", endpoint="ep")
    with pytest.raises(ValueError, match="no longer measured"):
        run_pass(space, ContextMode.OPEN_BOOK, settings=Settings())


def test_closed_book_asks_with_web_search(monkeypatch: Any) -> None:
    """Both roads of arm A: the direct call and the repeats of monte_carlo."""
    import syft_benchmark.runs.execute as execute

    seen: list[dict[str, Any]] = []

    def chat(system: str, user: str, **kwargs: Any) -> Any:
        seen.append(kwargs)
        return "I don't know", {"finish_reason": "stop"}

    monkeypatch.setattr(execute, "chat", chat)
    subject = Provider(role="subject", url="http://x", api_key="", model="a/b")
    pair: Any = type("Pair", (), {"question": "Which port?", "context": ""})()

    execute.ask_once(
        pair,
        ContextMode.CLOSED_BOOK,
        space=None,  # type: ignore[arg-type]
        settings=Settings(),
        subject=subject,
        source=ContextSource.NONE,
    )
    execute._ask_model("Which port?", 0.9, provider=subject, settings=Settings())
    execute._ask_model_with_context(
        "Which port?", 0.9, provider=subject, settings=Settings(), context="x"
    )
    assert [call.get("web_search", False) for call in seen] == [True, True, False]


# --- the same-company rule ----------------------------------------------------


def test_a_company_with_several_prefixes_is_one_company() -> None:
    assert company_of("x-ai/grok-4.6") == company_of("xai/grok-4.6") == "xai"
    assert company_of("meta-llama/llama-4") == company_of("meta/llama-5") == "meta"
    assert company_of("mistralai/m") == company_of("mistral/m") == "mistral"
    assert company_of("gemini/g") == company_of("google/gemini-3.1-pro-preview")
    assert company_of("gemma3-4b-gpu") == ""


def _clashing(policy: JudgePolicy) -> Settings:
    return Settings(
        judge_model="google/gemini-3.1-pro-preview",
        judge_models=["google/gemini-3.1-pro-preview", "openai/gpt-5.1"],
        subject_models=["gemini/some-model", "x-ai/grok-4.6"],
        judge_policy=policy,
    )


def test_every_clash_is_named() -> None:
    assert judge_clashes(_clashing(JudgePolicy.WARN)) == [
        "Judge google/gemini-3.1-pro-preview and tested model gemini/some-model "
        "are from the same company"
    ]


def test_strict_refuses_and_warn_allows() -> None:
    reason = clash_refusal(_clashing(JudgePolicy.STRICT))
    assert reason is not None and "gemini/some-model" in reason
    assert clash_refusal(_clashing(JudgePolicy.WARN)) is None


def test_only_strict_and_warn_are_offered() -> None:
    by_name = {f["name"]: f for f in catalogue()["instrument"]}
    assert by_name["judge_policy"]["choices"] == ["strict", "warn"]
    # A stored row keeps reading.
    assert (
        Instrument(judge_policy=JudgePolicy.RECUSE).judge_policy is JudgePolicy.RECUSE
    )


# --- the API refuses it too -------------------------------------------------


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
    def wipe() -> None:
        with session_scope() as session:
            session.execute(delete(Job).where(Job.target == KEY))
            session.execute(delete(Target).where(Target.key == KEY))

    wipe()
    yield
    wipe()


@pytest.fixture
def client() -> Any:
    conf = get_settings().model_copy(
        update={"control_token": TOKEN, "filter_model": WEB_CHECK_MODEL}
    )
    return TestClient(create_app(conf))


def _spec(policy: JudgePolicy, subjects: list[str]) -> dict[str, Any]:
    return TargetSpec(
        key=KEY,
        url="http://space.invalid",
        instrument=Instrument(
            judge_model="google/gemini-3.1-pro-preview",
            judge_models=["google/gemini-3.1-pro-preview", "openai/gpt-5.1"],
            subject_models=subjects,
            judge_policy=policy,
        ),
    ).model_dump(mode="json")


@needs_db
def test_a_clashing_save_is_refused_under_strict(
    client: TestClient, clean: Any
) -> None:
    reply = client.put(
        f"/targets/{KEY}",
        json=_spec(JudgePolicy.STRICT, ["openai/gpt-5.1", "x-ai/grok-4.6"]),
        headers=AUTH,
    )
    assert reply.status_code == 422
    assert reply.json()["detail"].startswith(
        "Judge openai/gpt-5.1 and tested model openai/gpt-5.1"
    )
    assert client.get(f"/targets/{KEY}", headers=AUTH).status_code == 404


@needs_db
def test_a_clashing_save_is_allowed_under_warn(client: TestClient, clean: Any) -> None:
    reply = client.put(
        f"/targets/{KEY}",
        json=_spec(JudgePolicy.WARN, ["openai/gpt-5.1"]),
        headers=AUTH,
    )
    assert reply.status_code == 200, reply.text
    assert client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).status_code == (
        202
    )


@needs_db
def test_a_run_whose_request_brings_a_clash_is_refused_under_strict(
    client: TestClient, clean: Any
) -> None:
    saved = client.put(
        f"/targets/{KEY}",
        json=_spec(JudgePolicy.STRICT, ["x-ai/grok-4.6"]),
        headers=AUTH,
    )
    assert saved.status_code == 200, saved.text
    request = RunRequest(
        instrument=Instrument(subject_models=["google/gemini-3.5-flash"])
    ).model_dump(mode="json", exclude_none=True)
    reply = client.post(f"/targets/{KEY}/runs", json=request, headers=AUTH)
    assert reply.status_code == 422
    assert "google/gemini-3.5-flash" in reply.json()["detail"]
    assert client.post(f"/targets/{KEY}/runs", json={}, headers=AUTH).status_code == (
        202
    )


def test_the_web_check_model_is_inside_the_perimeter_check() -> None:
    from syft_benchmark.config import ExternalCallBlocked
    from syft_benchmark.llm.roles import check_perimeter, filter_provider

    assert filter_provider(Settings()) is None
    conf = Settings(
        filter_model="openai/gpt-5.1", subject_url="https://openrouter.ai/api/v1"
    )
    provider = filter_provider(conf)
    assert provider is not None and provider.model == "openai/gpt-5.1"
    with pytest.raises(ExternalCallBlocked):
        check_perimeter(conf)
