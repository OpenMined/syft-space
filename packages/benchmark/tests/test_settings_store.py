"""Where a setting is allowed to live, and what a secret costs to store.

Two halves. The settings move out of the environment into a row, because a
value that can be written in two places is a value that disagrees with itself
on the day somebody edits the wrong one. The secrets move out of both into a
table of their own, sealed, because the settings travel — into a job's
snapshot, into every run's params, into ``/defaults`` and into the log — and a
provider key travelling with them would arrive everywhere they arrive.

The sealing is checked for the properties that were the reason to choose it,
not for "it encrypts": that a ciphertext will not open in a slot it was not
written for, that a wrong key fails rather than returning rubbish, and that
rotation is a step somebody can take twice.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import delete

from syft_benchmark.config import Settings, env_settings
from syft_benchmark.control import targets as registry
from syft_benchmark.control.compose import settings_for
from syft_benchmark.control.schemas import TargetSpec
from syft_benchmark.db import store
from syft_benchmark.db.crypto import (
    SecretsNotConfigured,
    SecretUnreadable,
    cipher_from,
    new_key,
)
from syft_benchmark.db.models import Credential, InstallationSettings, Target
from syft_benchmark.db.session import session_scope

KEY = "pytest-store-target"


# --- the sealing ------------------------------------------------------------


def test_a_secret_comes_back_as_it_went_in() -> None:
    box = cipher_from(new_key())
    blob, nonce, key_id = box.seal("llm_api_key", "sk-not-a-real-one")
    assert box.open("llm_api_key", blob, nonce, key_id) == "sk-not-a-real-one"


def test_a_secret_will_not_open_in_a_slot_it_was_not_written_for() -> None:
    """The whole reason the name is bound to the ciphertext.

    Somebody who can write to the table but knows not one key could otherwise
    copy the judge's key into the subject's slot and quietly redirect the model
    under test to a provider of their choosing.
    """
    box = cipher_from(new_key())
    blob, nonce, key_id = box.seal("judge_key", "sk-judge")
    with pytest.raises(SecretUnreadable):
        box.open("subject_key", blob, nonce, key_id)


def test_the_wrong_key_fails_rather_than_returning_rubbish() -> None:
    """GCM authenticates as well as encrypts, and that is what is wanted here.

    A cipher that decrypted with any key would hand a corrupted string to a
    provider, and the failure would surface as somebody else's 401.
    """
    sealed = cipher_from(new_key())
    blob, nonce, _ = sealed.seal("llm_api_key", "sk-one")
    other = cipher_from(new_key())
    with pytest.raises(SecretUnreadable):
        other.open("llm_api_key", blob, nonce, other.active_id)


def test_a_retired_key_still_opens_what_it_sealed() -> None:
    """Without this, rotation would be "re-enter every secret by hand"."""
    old_raw = new_key()
    old = cipher_from(old_raw)
    blob, nonce, old_id = old.seal("llm_api_key", "sk-old")

    rotated = cipher_from(new_key(), {old_id: old_raw})
    assert rotated.open("llm_api_key", blob, nonce, old_id) == "sk-old"


def test_without_a_master_key_nothing_is_stored() -> None:
    """Fail closed. A fallback to plain text is how an installation ends up
    with half its secrets encrypted and no record of which half."""
    with pytest.raises(SecretsNotConfigured):
        cipher_from("")


def test_a_key_that_is_not_a_key_is_refused_by_name() -> None:
    """The message has to say what to do: this is read off somebody's .env."""
    with pytest.raises(SecretsNotConfigured, match="BENCH_SECRET_KEY"):
        cipher_from("not-base64-at-all!!")
    with pytest.raises(SecretsNotConfigured, match="AES-256"):
        cipher_from("c2hvcnQ=")  # valid base64, five bytes


# --- what may be written where ----------------------------------------------


def _conf() -> Settings:
    """The environment's settings with a master key, whatever the host has."""
    return env_settings().model_copy(update={"secret_key": new_key()})


def test_a_secret_is_refused_by_the_settings() -> None:
    """It would otherwise be copied into every job snapshot and every run."""
    with pytest.raises(store.SettingRejected, match="secret"):
        store.validate(_conf(), {"llm_api_key": "sk-nope"})


def test_the_perimeter_is_not_settable_through_the_api() -> None:
    """The one refusal here that is not bookkeeping.

    The ban on calls outside is a check rather than an agreement, because the
    questions are built from private documents. A list of allowed hosts
    editable by whoever holds an API key is not a perimeter.
    """
    with pytest.raises(store.SettingRejected, match="perimeter"):
        store.validate(_conf(), {"external_hosts": ["evil.example"]})
    with pytest.raises(store.SettingRejected):
        store.validate(_conf(), {"allow_external_models": True})


def test_the_bootstrap_is_not_settable_either() -> None:
    """The address of the database holding the settings cannot be in them, and
    neither can the key to the API through which they are edited."""
    for field in ("database_url", "control_token", "secret_key"):
        with pytest.raises(store.SettingRejected):
            store.validate(_conf(), {field: "anything"})


def test_a_field_the_settings_do_not_have_is_refused() -> None:
    """Swallowed, it would be a setting that changes nothing — and the owner
    would be looking at a form that appeared to work."""
    with pytest.raises(store.SettingRejected, match="do not know"):
        store.validate(_conf(), {"retrieval_top_kk": 5})


def test_a_value_out_of_bounds_is_refused_at_the_door() -> None:
    """The check is a real one: the settings are built with the value applied.

    A temperature above two would otherwise be found at three in the morning,
    by the schedule, in somebody else's provider's error message.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        store.validate(_conf(), {"llm_temperature": 11.0})


def test_what_is_stored_is_only_what_was_sent() -> None:
    """A sparse overlay, not a snapshot of every setting.

    A full snapshot would freeze today's defaults on the day of the write, and
    a raised default would then never reach this installation again.
    """
    checked = store.validate(_conf(), {"retrieval_top_k": 9})
    assert checked == {"retrieval_top_k": 9}


# --- the store over a live table --------------------------------------------


def _db_ready() -> bool:
    try:
        with session_scope() as session:
            session.execute(delete(Target).where(Target.key == KEY))
        return True
    except Exception:  # noqa: BLE001 - the database may simply not be at hand
        return False


needs_db = pytest.mark.skipif(
    not _db_ready(), reason="the benchmark database is unavailable"
)


@pytest.fixture
def clean() -> Any:
    """Nothing of this test's survives it — and the cache is not carried over."""

    def wipe() -> None:
        # The environment's settings, so that opening a session does not go
        # through get_settings and seed the very row about to be deleted.
        with session_scope(env_settings()) as session:
            session.execute(delete(Target).where(Target.key == KEY))
            session.execute(delete(Credential))
            session.execute(delete(InstallationSettings))
        # After the deletes, not before: the cache is what the store would
        # otherwise go on answering from.
        store.invalidate()

    wipe()
    yield
    wipe()


@needs_db
def test_a_stored_setting_beats_the_built_in_default(clean: Any) -> None:
    conf = _conf()
    store.write(conf, {"retrieval_top_k": 9})
    assert store.apply(conf).retrieval_top_k == 9


@needs_db
def test_an_override_dropped_goes_back_to_the_default(clean: Any) -> None:
    """The document is written whole, so removing a key is how a field is
    unset. With "absent means unchanged" there would be no way back."""
    conf = _conf()
    default = conf.retrieval_top_k
    store.write(conf, {"retrieval_top_k": 9})
    store.write(conf, {})
    assert store.apply(conf).retrieval_top_k == default


@needs_db
def test_a_secret_is_never_handed_back(clean: Any) -> None:
    """What may be said is that there is one and when it was set."""
    conf = _conf()
    store.set_secret(conf, "llm_api_key", "sk-secret")
    listed = store.secrets(conf)
    assert [item.name for item in listed] == ["llm_api_key"]
    assert "sk-secret" not in str(listed)


@needs_db
def test_a_stored_key_reaches_the_settings(clean: Any) -> None:
    """The point of storing it: the call that needs it sees it as a setting,
    and nothing downstream had to learn where keys live now."""
    conf = _conf()
    store.set_secret(conf, "llm_api_key", "sk-stored")
    assert store.apply(conf).llm_api_key == "sk-stored"


@needs_db
def test_a_secret_can_be_taken_away(clean: Any) -> None:
    conf = _conf()
    store.set_secret(conf, "judge_key", "sk-judge")
    assert store.clear_secret(conf, "judge_key") is True
    assert store.clear_secret(conf, "judge_key") is False
    assert store.secrets(conf) == []


@needs_db
def test_rotation_moves_the_secrets_and_can_be_run_twice(clean: Any) -> None:
    """Interrupted halfway, it is finished by running it again: rows already on
    the active key are skipped rather than re-sealed."""
    first_raw = new_key()
    conf = env_settings().model_copy(update={"secret_key": first_raw})
    store.set_secret(conf, "llm_api_key", "sk-rotating")
    old_id = cipher_from(first_raw).active_id

    rotated = env_settings().model_copy(
        update={"secret_key": new_key(), "secret_keys_retired": {old_id: first_raw}}
    )
    store.invalidate()
    assert store.rotate(rotated) == 1
    assert store.rotate(rotated) == 0
    assert store.secret(rotated, "llm_api_key") == "sk-rotating"


@needs_db
def test_a_target_token_is_sealed_and_still_reaches_the_call(clean: Any) -> None:
    """The token is what publishes the card. It must survive the move out of
    its column — and it must not come back as a column."""
    conf = _conf()
    spec = TargetSpec(key=KEY, url="http://space.invalid", endpoint="kb", token="tok-1")
    with session_scope(conf) as session:
        registry.save(session, spec, conf)
        assert registry.has_token(session, KEY) is True

    # In a second transaction on purpose: the token is opened at the moment of
    # the call that needs it, which is never the request that stored it.
    with session_scope(conf) as session:
        row = session.get(Target, KEY)
        assert row is not None
        _, space = settings_for(row, conf)
    assert space.token == "tok-1"


@needs_db
def test_saving_a_target_without_a_token_keeps_the_one_it_has(clean: Any) -> None:
    """The form does not know the previous token and cannot send it back.

    Without that provision any edit to a target's title would wipe its access,
    and it would come to light at night, at the publishing of the card.
    """
    conf = _conf()
    with session_scope(conf) as session:
        registry.save(
            session,
            TargetSpec(key=KEY, url="http://space.invalid", token="tok-1"),
            conf,
        )
    with session_scope(conf) as session:
        registry.save(
            session,
            TargetSpec(key=KEY, url="http://space.invalid", title="Renamed"),
            conf,
        )
    assert store.secret(conf, store.target_secret(KEY)) == "tok-1"


@needs_db
def test_an_empty_token_withdraws_access(clean: Any) -> None:
    """The owner must be able to take it back, and an empty string is that."""
    conf = _conf()
    with session_scope(conf) as session:
        registry.save(
            session,
            TargetSpec(key=KEY, url="http://space.invalid", token="tok-1"),
            conf,
        )
    with session_scope(conf) as session:
        registry.save(
            session,
            TargetSpec(key=KEY, url="http://space.invalid", token=""),
            conf,
        )
        assert registry.has_token(session, KEY) is False


@needs_db
def test_a_deleted_target_does_not_leave_its_token_behind(clean: Any) -> None:
    """A sealed secret nobody can name any more is one nobody will remove."""
    conf = _conf()
    with session_scope(conf) as session:
        registry.save(
            session,
            TargetSpec(key=KEY, url="http://space.invalid", token="tok-1"),
            conf,
        )
    with session_scope(conf) as session:
        assert registry.drop(session, KEY, conf) is True
    assert store.secret(conf, store.target_secret(KEY)) is None


@needs_db
def test_the_environment_is_the_layer_under_the_row(clean: Any) -> None:
    """Read-only, and it goes on applying — it is not copied in and forgotten.

    This is the case that killed the first design. The container's compose file
    sets the addresses that differ inside a container, because `localhost`
    there is the container. Carried into the row once and then ignored, those
    would apply on the first start and silently stop applying afterwards,
    leaving an installation pointed at a model provider inside itself.
    """
    conf = _conf()
    from_deploy = conf.model_copy(update={"ollama_url": "http://ollama:11434"})

    # Nothing was written, and the deployment's value is in force.
    assert store.apply(from_deploy).ollama_url == "http://ollama:11434"
    assert store.read(conf) == {}

    # It goes on being in force at every later start, not only the first.
    store.invalidate()
    assert store.apply(from_deploy).ollama_url == "http://ollama:11434"


@needs_db
def test_the_row_beats_the_environment_and_nothing_beats_the_row(
    clean: Any,
) -> None:
    """The owner's decision outranks the deployment's default — that is the
    whole point of there being a row — and it survives a restart."""
    conf = _conf()
    from_deploy = conf.model_copy(update={"ollama_url": "http://ollama:11434"})
    store.write(conf, {"ollama_url": "https://openrouter.ai/api/v1"})

    assert store.apply(from_deploy).ollama_url == "https://openrouter.ai/api/v1"
    store.invalidate()
    assert store.apply(from_deploy).ollama_url == "https://openrouter.ai/api/v1"


@needs_db
def test_a_key_left_in_the_environment_is_named_rather_than_hidden(
    clean: Any,
) -> None:
    """Nothing copies it into the store behind the operator's back.

    It would leave the plaintext in the file regardless — the part that
    actually matters — while making "the keys are encrypted at rest" true of
    everything except the one nobody was told about.
    """
    conf = _conf().model_copy(update={"llm_api_key": "sk-in-a-file"})
    assert store.env_secrets(conf) == ["llm_api_key"]

    store.set_secret(conf, "llm_api_key", "sk-stored")
    assert store.env_secrets(conf) == []
    assert store.apply(conf).llm_api_key == "sk-stored"


# --- through the API --------------------------------------------------------


TOKEN = "test-store-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client() -> Any:
    """An API client with a key and a master key.

    Deliberately without a context manager: it would raise the worker and the
    ticker, and those would set about measuring against a node that is not
    there.
    """
    from fastapi.testclient import TestClient

    from syft_benchmark.control.app import create_app

    conf = env_settings().model_copy(
        update={"control_token": TOKEN, "secret_key": new_key()}
    )
    return TestClient(create_app(conf))


@needs_db
def test_the_settings_go_in_and_come_back(client: Any, clean: Any) -> None:
    assert (
        client.put(
            "/settings", json={"values": {"retrieval_top_k": 9}}, headers=AUTH
        ).status_code
        == 200
    )
    assert client.get("/settings", headers=AUTH).json() == {
        "values": {"retrieval_top_k": 9}
    }


@needs_db
def test_the_api_refuses_a_secret_among_the_settings(client: Any, clean: Any) -> None:
    """With the reason, not a bare 422: the form is drawn by somebody else."""
    reply = client.put(
        "/settings", json={"values": {"llm_api_key": "sk-nope"}}, headers=AUTH
    )
    assert reply.status_code == 422
    assert "secret" in reply.json()["detail"]


@needs_db
def test_the_api_refuses_to_open_the_perimeter(client: Any, clean: Any) -> None:
    """The check exists because the corpus is private. A key to the API is not
    authority over where the corpus may go."""
    reply = client.put(
        "/settings", json={"values": {"external_hosts": ["evil.example"]}}, headers=AUTH
    )
    assert reply.status_code == 422


@needs_db
def test_a_bound_is_checked_before_the_value_is_stored(client: Any, clean: Any) -> None:
    reply = client.put(
        "/settings", json={"values": {"llm_temperature": 11.0}}, headers=AUTH
    )
    assert reply.status_code == 422


@needs_db
def test_a_secret_goes_in_through_the_api_and_does_not_come_out(
    client: Any, clean: Any
) -> None:
    assert (
        client.put(
            "/credentials/llm_api_key", json={"value": "sk-api"}, headers=AUTH
        ).status_code
        == 204
    )
    listed = client.get("/credentials", headers=AUTH)
    assert [row["name"] for row in listed.json()] == ["llm_api_key"]
    assert "sk-api" not in listed.text

    assert client.delete("/credentials/llm_api_key", headers=AUTH).status_code == 204
    assert client.delete("/credentials/llm_api_key", headers=AUTH).status_code == 404


@needs_db
def test_a_credential_may_not_take_a_bootstrap_name(client: Any, clean: Any) -> None:
    """It would be a secret that is definitely set and definitely never read —
    and nothing is harder to work out than that."""
    reply = client.put("/credentials/control_token", json={"value": "x"}, headers=AUTH)
    assert reply.status_code == 422


@needs_db
def test_without_a_master_key_the_api_refuses_rather_than_storing_plain_text(
    clean: Any,
) -> None:
    from fastapi.testclient import TestClient

    from syft_benchmark.control.app import create_app

    conf = env_settings().model_copy(update={"control_token": TOKEN, "secret_key": ""})
    keyless = TestClient(create_app(conf))
    reply = keyless.put(
        "/credentials/llm_api_key", json={"value": "sk-api"}, headers=AUTH
    )
    assert reply.status_code == 503
    assert "BENCH_SECRET_KEY" in reply.json()["detail"]


@needs_db
def test_a_changed_setting_is_visible_to_the_very_next_request(
    client: Any, clean: Any
) -> None:
    """The form reads /defaults to show what an unset field comes to.

    A route answering from the settings assembled when the process came up
    would show the owner the old value a second after accepting the new one,
    and the only cure they would find is restarting the service.
    """
    before = client.get("/defaults", headers=AUTH).json()["probe"]["retrieval_top_k"]
    client.put(
        "/settings", json={"values": {"retrieval_top_k": before + 3}}, headers=AUTH
    )
    after = client.get("/defaults", headers=AUTH).json()["probe"]["retrieval_top_k"]
    assert after == before + 3


@needs_db
def test_the_form_can_be_drawn_for_all_three_layers(client: Any, clean: Any) -> None:
    """A layer with no schema is a layer no UI can offer.

    The installation's settings had none while they lived in the environment,
    because the form for them was somebody's text editor.
    """
    schema = client.get("/schema", headers=AUTH).json()
    assert {"installation", "instrument", "probe"} <= set(schema)
    assert len(schema["installation"]) > 40
    assert all(field["group"] in schema["groups"] for field in schema["installation"])


@needs_db
def test_no_secret_and_no_bootstrap_field_is_ever_offered_or_answered(
    client: Any, clean: Any
) -> None:
    """The two endpoints a settings form is built from must not name them.

    Offered, a secret would be a text box that writes a key into the settings
    document — the very thing the separate table exists to prevent. Answered,
    the key itself would be on the wire.
    """
    from syft_benchmark.config import BOOTSTRAP_FIELDS, SECRET_FIELDS

    forbidden = BOOTSTRAP_FIELDS | SECRET_FIELDS
    offered = {
        f["name"] for f in client.get("/schema", headers=AUTH).json()["installation"]
    }
    answered = set(client.get("/defaults", headers=AUTH).json()["installation"])

    assert offered & forbidden == set()
    assert answered & forbidden == set()


@needs_db
def test_the_defaults_show_what_is_actually_in_force(client: Any, clean: Any) -> None:
    """Not the built-in value — the one this installation will really use."""
    client.put("/settings", json={"values": {"concurrency": 3}}, headers=AUTH)
    assert (
        client.get("/defaults", headers=AUTH).json()["installation"]["concurrency"] == 3
    )


@needs_db
def test_naming_an_external_provider_does_not_kill_the_settings_page(
    client: Any, clean: Any
) -> None:
    """Describing a configuration must never raise.

    The perimeter check used to run while working out where a role points, and
    that is also how /defaults and /capabilities report the models each role is
    set to. So typing an external provider's address into the form answered
    with a 500 on the page the owner was standing on — with no way to undo the
    thing that caused it.

    Egress is still barred: the guard that matters is in the client, before
    every call, and a measurement refuses to start. What changed is that saying
    what is configured is no longer an attempt to act on it.
    """
    assert (
        client.put(
            "/settings",
            json={"values": {"ollama_url": "https://openrouter.ai/api/v1"}},
            headers=AUTH,
        ).status_code
        == 200
    )
    assert client.get("/defaults", headers=AUTH).status_code == 200
    assert client.get("/capabilities", headers=AUTH).status_code == 200


def test_a_measurement_refuses_to_start_outside_the_perimeter() -> None:
    """The early warning, in its proper place: before any question is asked."""
    from syft_benchmark.config import ExternalCallBlocked
    from syft_benchmark.llm import check_perimeter

    outside = Settings(ollama_url="https://openrouter.ai/api/v1")
    with pytest.raises(ExternalCallBlocked):
        check_perimeter(outside)

    allowed = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    check_perimeter(allowed)
