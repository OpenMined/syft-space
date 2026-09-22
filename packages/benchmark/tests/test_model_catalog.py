"""The model catalogue: one identity per model, whoever serves it.

What is checked here is not that the importer copies fields. It is the three
decisions the catalogue exists to carry: that a route is not a model, that a
moving name is resolved before it is stored, and that a vendor's own API is
told the vendor's own name for the same model.
"""

from __future__ import annotations

from typing import Any

import pytest

from syft_benchmark.llm import catalog, openrouter
from syft_benchmark.llm.providers import ProviderKind, kind_for_url


def _raw(model_id: str, **extra: Any) -> dict[str, Any]:
    """One record in the shape the provider hands it over."""
    record: dict[str, Any] = {
        "id": model_id,
        "canonical_slug": f"{model_id}-20260101",
        "name": model_id,
        "context_length": 128000,
        "architecture": {"input_modalities": ["text"]},
        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        "top_provider": {"max_completion_tokens": 8192},
        "supported_parameters": ["temperature", "tools", "top_p"],
    }
    record.update(extra)
    return record


def _catalogue(*records: dict[str, Any]) -> catalog.Catalog:
    """A catalogue built from these records alone, with nothing shipped behind."""
    return catalog.from_documents([openrouter.snapshot(list(records))])


# --- what is one model, and what is not -------------------------------------


def test_a_route_is_not_a_model() -> None:
    """``:free`` and ``:batch`` reach the same weights at a different price.

    Three entries would each collect their own history, and a report would hold
    three models where one was measured.
    """
    built = _catalogue(
        _raw("z-ai/glm-5.3"),
        _raw("z-ai/glm-5.3:free"),
        _raw("z-ai/glm-5.3:batch"),
    )

    assert list(built.models) == ["z-ai/glm-5.3"]
    entry = built.models["z-ai/glm-5.3"]
    assert entry.routes == {
        "free": "z-ai/glm-5.3:free",
        "batch": "z-ai/glm-5.3:batch",
    }


def test_a_colon_that_is_not_a_route_stays_in_the_name() -> None:
    """An unknown suffix is more likely part of a name than a route.

    The merge is the expensive direction: two models measured as one cannot be
    told apart afterwards, while two entries for one only look untidy.
    """
    built = _catalogue(_raw("amazon/nova-pro-v1:0"))

    assert list(built.models) == ["amazon/nova-pro-v1:0"]
    assert built.models["amazon/nova-pro-v1:0"].routes == {}


def test_the_dated_build_is_recorded_but_is_not_the_identity() -> None:
    """A vendor refreshing what a name serves must not fork the history.

    The number is reported so a reader can see that it moved; it is not the
    identifier, because two builds of one model still belong on one line of one
    report.
    """
    built = _catalogue(_raw("openai/gpt-6-astra"))

    entry = built.models["openai/gpt-6-astra"]
    assert entry.id == "openai/gpt-6-astra"
    assert entry.build == "openai/gpt-6-astra-20260101"


# --- moving names -----------------------------------------------------------


def test_a_moving_name_is_not_an_entry_but_a_pin() -> None:
    """``~vendor/thing-latest`` points somewhere else every few months."""
    built = _catalogue(
        _raw("anthropic/claude-sonnet-5"),
        _raw(
            "~anthropic/claude-sonnet-latest",
            alias_target={
                "name": "Claude Sonnet 5",
                "slug": "anthropic/claude-sonnet-5",
            },
        ),
    )

    assert list(built.models) == ["anthropic/claude-sonnet-5"]
    assert built.pin("~anthropic/claude-sonnet-latest") == "anthropic/claude-sonnet-5"
    # And it is still attributed to its vendor while it is being shown.
    assert built.vendor_of("~anthropic/claude-sonnet-latest") == "anthropic"


def test_pinning_touches_the_model_fields_and_nothing_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A setting is pinned as it is saved, not as a run starts: resolved at run
    time, the stored configuration would describe a measurement nobody can
    repeat."""
    built = _catalogue(
        _raw("anthropic/claude-sonnet-5"),
        _raw(
            "~anthropic/claude-sonnet-latest",
            alias_target={
                "name": "Claude Sonnet 5",
                "slug": "anthropic/claude-sonnet-5",
            },
        ),
    )
    monkeypatch.setattr(catalog, "load", lambda settings=None: built)

    pinned = catalog.pin_values(
        {
            "generator_model": "~anthropic/claude-sonnet-latest",
            "judge_models": ["~anthropic/claude-sonnet-latest", "gemma3-4b-gpu"],
            "methodology_profile": "~anthropic/claude-sonnet-latest",
        }
    )

    assert pinned["generator_model"] == "anthropic/claude-sonnet-5"
    assert pinned["judge_models"] == ["anthropic/claude-sonnet-5", "gemma3-4b-gpu"]
    # Not a model field: a name that happens to look like one is left alone.
    assert pinned["methodology_profile"] == "~anthropic/claude-sonnet-latest"


def test_an_unset_field_does_not_become_a_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent setting means "inherit", and pinning must not decide for it."""
    monkeypatch.setattr(catalog, "load", lambda settings=None: _catalogue())

    assert catalog.pin_values({"judge_model": "x/y"}).keys() == {"judge_model"}


# --- the same model under someone else's name -------------------------------


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://openrouter.ai/api/v1", ProviderKind.OPENROUTER),
        ("https://api.anthropic.com", ProviderKind.ANTHROPIC),
        ("https://api.openai.com/v1", ProviderKind.OPENAI),
        ("http://ollama:11434", ProviderKind.OLLAMA),
        ("http://localhost:11434", ProviderKind.OLLAMA),
        ("https://llm.example.com/v1", ProviderKind.UNKNOWN),
    ],
)
def test_the_provider_is_read_from_the_address(url: str, kind: ProviderKind) -> None:
    """There is already a URL per role; a second field saying what it is would
    be a second thing to keep in step."""
    assert kind_for_url(url) == kind


def test_a_vendors_own_api_is_told_its_own_name() -> None:
    """``anthropic/claude-sonnet-5`` is ``claude-sonnet-5`` at Anthropic.

    This is the whole point of storing an identifier of ours: moving an
    installation from one provider to another must not rewrite every setting.
    """
    built = _catalogue(_raw("anthropic/claude-sonnet-5"))

    assert built.native("anthropic/claude-sonnet-5", ProviderKind.ANTHROPIC) == (
        "claude-sonnet-5"
    )
    assert built.native("anthropic/claude-sonnet-5", ProviderKind.OPENROUTER) == (
        "anthropic/claude-sonnet-5"
    )


def test_only_that_vendors_own_prefix_comes_off() -> None:
    """A Llama is not an OpenAI model, whoever is being asked for it."""
    built = _catalogue(_raw("meta-llama/llama-4-scout"))

    assert built.native("meta-llama/llama-4-scout", ProviderKind.OPENAI) == (
        "meta-llama/llama-4-scout"
    )


def test_an_unknown_model_travels_unchanged() -> None:
    """The catalogue is not a whitelist: a model released this morning is in no
    snapshot, and refusing it would make the picker less capable than a text
    box."""
    built = _catalogue(_raw("anthropic/claude-sonnet-5"))

    assert built.get("vendor/released-today") is None
    assert built.native("vendor/released-today", ProviderKind.OPENROUTER) == (
        "vendor/released-today"
    )
    assert built.vendor_of("vendor/released-today") == "vendor"


# --- what the picker asks for -----------------------------------------------


def test_the_filter_keeps_only_models_that_can_do_the_job() -> None:
    """The monte_carlo block is nothing but varied temperature.

    A model that does not honour the parameter cannot serve it, and offering it
    for that role is an hour of a run spent measuring the same answer.
    """
    built = _catalogue(
        _raw("a/with-temperature"),
        _raw("b/without-temperature", supported_parameters=["tools"]),
    )

    found = built.search(supports=("temperature",))

    assert [entry.id for entry in found] == ["a/with-temperature"]


def test_a_withdrawn_model_is_out_of_the_way_but_not_gone() -> None:
    """It is still configured somewhere, so it must still be nameable."""
    built = _catalogue(
        _raw("a/current"),
        _raw("b/going-away", expiration_date="2026-12-01"),
    )

    assert [entry.id for entry in built.search()] == ["a/current"]
    assert [entry.id for entry in built.search(include_retired=True)] == [
        "a/current",
        "b/going-away",
    ]


def test_the_shipped_snapshot_is_readable_and_is_a_catalogue() -> None:
    """The floor under the table: a rig that cannot leave the perimeter, and one
    whose provider is down, both still get a form with models in it."""
    built = catalog.from_documents([catalog.shipped()])

    assert len(built.models) > 100
    assert built.vendors()
    assert built.fetched.get(openrouter.SOURCE)


# --- what the form is handed ------------------------------------------------


def _client(**overrides: Any) -> Any:
    """An API client that needs neither a database nor a model host.

    Both are reached by the catalogue routes and both are optional to them: the
    stored catalogue falls back to the shipped snapshot, and an unreachable
    Ollama costs the local models and nothing else. A form is for configuring
    things, including configuring them while half the rig is down.
    """
    from fastapi.testclient import TestClient

    from syft_benchmark.config import Settings
    from syft_benchmark.control.app import create_app

    catalog.invalidate()
    conf = Settings(control_token="test-control-token", **overrides)
    return TestClient(create_app(conf))


AUTH = {"Authorization": "Bearer test-control-token"}


def test_the_form_is_offered_the_catalogue_over_the_wire() -> None:
    """The picker's whole reason to exist: names it cannot get wrong."""
    answer = _client().get("/models", params={"q": "claude"}, headers=AUTH)

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["total"] > 0
    assert all("claude" in entry["id"].lower() for entry in body["models"])
    assert "anthropic" in body["vendors"]
    # The moving names travel too, with what they mean today beside them: the
    # form can offer the convenient name and still store the repeatable one.
    assert body["pins"]


def test_the_field_description_says_which_fields_have_a_catalogue() -> None:
    """So the form does not have to recognise the model fields by name.

    That is the coupling /schema exists to prevent: a fifth model field would
    otherwise need a release on the other side before anyone could pick a model
    for it.
    """
    from syft_benchmark.control.formfields import catalogue

    by_name = {field["name"]: field for field in catalogue()["instrument"]}

    assert by_name["subject_models"]["catalog"] == "models"
    assert by_name["judge_models"]["catalog"] == "models"
    assert "catalog" not in by_name["denial_rounds"]


def test_a_refresh_is_a_call_outside_and_the_perimeter_rules() -> None:
    """The one route here that goes out to somebody who is not a provider.

    It says which permission is missing rather than failing as a timeout: the
    catalogue is public, so "forbidden" is a decision of this installation and
    reads as nothing else.
    """
    answer = _client(allow_external_models=False).post("/models/refresh", headers=AUTH)

    assert answer.status_code == 403, answer.text
    assert "external_hosts" in answer.json()["detail"]


# --- what a run records about what answered it ------------------------------


def test_a_role_can_say_what_was_actually_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The identifier is what was asked for; these are what answered.

    Written into the run's own columns, so that six months later two rows under
    one model name can be told apart when the vendor moved what the name serves.
    """
    from syft_benchmark.llm.roles import Provider

    built = _catalogue(_raw("anthropic/claude-sonnet-5"))
    monkeypatch.setattr(catalog, "load", lambda settings=None: built)

    role = Provider(
        role="subject",
        url="https://api.anthropic.com",
        api_key="k",
        model="anthropic/claude-sonnet-5",
    )

    assert role.vendor == "anthropic"
    assert role.kind is ProviderKind.ANTHROPIC
    assert role.wire_model == "claude-sonnet-5"
    assert role.build == "anthropic/claude-sonnet-5-20260101"


def test_a_model_outside_the_catalogue_admits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty, not guessed. A guess would be indistinguishable from a fact in the
    run it gets written into."""
    from syft_benchmark.llm.roles import Provider

    monkeypatch.setattr(catalog, "load", lambda settings=None: _catalogue())
    role = Provider(role="generator", url="http://ollama:11434", api_key="", model="g")

    assert role.build == ""
    assert role.wire_model == "g"


def test_the_served_model_is_not_in_the_settings_snapshot() -> None:
    """The snapshot decides whether yesterday's answers may be reused.

    It is compared for exact equality, so anything in it that moves on its own
    — and the dated build does — would make every measurement unresumable the
    day it moved, and the next pass would pay to ask again what it already
    knows. Evidence about one run does not belong among the conditions for
    comparing two.
    """
    from syft_benchmark.config import Settings

    snapshot = Settings().measurement_params()

    assert not {"model_sent_as", "model_provider", "model_build"} & set(snapshot)


# --- who actually served the call -------------------------------------------


def test_the_upstream_that_served_a_call_is_recorded() -> None:
    """A provider is not always the model's owner.

    A router picks between hosts per request — the same weights at different
    quantisations, context windows an order of magnitude apart — and that
    changes the answers. Unrecorded, it reads as the endpoint having got worse.
    """
    import httpx

    from syft_benchmark.config import Settings
    from syft_benchmark.llm import chat

    def reply(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "provider": "DeepInfra",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 1},
            },
            request=httpx.Request("POST", url),
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(httpx, "post", reply)
        _, usage = chat(
            "s",
            "u",
            settings=Settings(ollama_url="http://localhost:11434"),  # type: ignore[call-arg]
        )

    assert usage["served_by"] == "DeepInfra"


def test_a_provider_that_names_no_upstream_leaves_it_empty() -> None:
    """A local Ollama routes nothing, and neither does a vendor's own API.

    Empty is the honest record there. A placeholder would later have to be told
    apart from a real host name by whoever reads the table.
    """
    import httpx

    from syft_benchmark.config import Settings
    from syft_benchmark.llm import chat

    def reply(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {},
            },
            request=httpx.Request("POST", url),
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(httpx, "post", reply)
        _, usage = chat(
            "s",
            "u",
            settings=Settings(ollama_url="http://localhost:11434"),  # type: ignore[call-arg]
        )

    assert usage["served_by"] == ""


def test_the_upstream_is_not_in_the_settings_snapshot() -> None:
    """For the same reason the dated build is not.

    The snapshot decides whether yesterday's answers may be reused, and it is
    compared for exact equality. A value the router changes by itself would
    make every measurement unresumable on a day nothing was configured.
    """
    from syft_benchmark.config import Settings

    assert "served_by" not in Settings().measurement_params()


# --- what "check access" is for ---------------------------------------------


def test_the_access_check_asks_whether_the_models_can_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The misconfiguration this button exists to catch.

    Models are named in the instrument, edited in a UI; the address and key
    reaching them are the installation's own layer. Nothing refuses the
    combination — a provider that has never heard of the name does, per call.
    """
    from importlib import import_module

    from syft_benchmark.config import Settings
    from syft_benchmark.llm import LLMError

    # By module, not `from ... import check`: the package re-exports the
    # function of that name, and patching would land on the wrong object.
    access = import_module("syft_benchmark.control.check")

    conf = Settings(  # type: ignore[call-arg]
        ollama_url="http://localhost:11434",
        generator_model="anthropic/claude-sonnet-5",
        judge_model="local-judge",
    )

    def refuse(*, provider: Any, settings: Any) -> str:
        if provider.model.startswith("anthropic/"):
            raise LLMError('Ollama has no model "anthropic/claude-sonnet-5"')
        return provider.model

    monkeypatch.setattr(access, "check_model_available", refuse)

    problems = access._unreachable_models(conf)

    assert len(problems) == 1
    assert "generator" in problems[0]
    assert "anthropic/claude-sonnet-5" in problems[0]


def test_one_question_per_address_and_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """A panel of three judges on one gateway is three names, not three
    providers — and the check is a paid call on an external one."""
    from importlib import import_module

    from syft_benchmark.config import Settings

    access = import_module("syft_benchmark.control.check")

    conf = Settings(  # type: ignore[call-arg]
        ollama_url="http://localhost:11434",
        generator_model="one",
        judge_models=["one", "one", "two"],
        subject_models=["two"],
    )
    asked: list[str] = []

    def record(*, provider: Any, settings: Any) -> str:
        asked.append(provider.model)
        return provider.model

    monkeypatch.setattr(access, "check_model_available", record)

    assert access._unreachable_models(conf) == []
    assert sorted(asked) == ["one", "two"]


def test_a_gateway_is_not_asked_for_the_models_it_has_pulled() -> None:
    """It has pulled none, and it has no route to answer the question with.

    An installation that measures entirely with external models would
    otherwise pay for a doomed request on every draw of the form, and log a
    warning about it that says nothing is wrong.
    """
    from importlib import import_module

    from syft_benchmark.config import Settings

    control = import_module("syft_benchmark.control.app")
    gateway = Settings(ollama_url="https://openrouter.ai/api/v1")  # type: ignore[call-arg]

    assert control._local_models(gateway, query="", vendor="") == []
