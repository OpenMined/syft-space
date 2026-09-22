"""Invariant 2: questions do not leave the perimeter.

The check lives in the tests rather than in review, because it can be broken
with one line of configuration and noticed only after the corpus has leaked.
"""

import pytest

from syft_benchmark.config import ExternalCallBlocked, Settings, check_model_host


def _settings(**kwargs: object) -> Settings:
    return Settings(spaces_file="config/spaces.json", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434/v1",
        "http://ollama:11434/v1",  # a service name on the docker network
        "http://host.docker.internal:11434",
    ],
)
def test_local_hosts_pass(url: str) -> None:
    check_model_host(url, _settings())


@pytest.mark.parametrize(
    "url",
    [
        "https://openrouter.ai/api/v1",
        "https://api.openai.com/v1",
        "https://generativelanguage.googleapis.com",
    ],
)
def test_external_hosts_blocked_by_default(url: str) -> None:
    with pytest.raises(ExternalCallBlocked):
        check_model_host(url, _settings())


def test_external_host_needs_both_flag_and_list() -> None:
    """A flag alone is not enough: the host has to be named explicitly.

    Otherwise turning on "allow external" opens the road anywhere at all,
    including places the owner never intended.
    """
    only_flag = _settings(allow_external_models=True)
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://openrouter.ai/api/v1", only_flag)

    only_list = _settings(external_hosts=["openrouter.ai"])
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://openrouter.ai/api/v1", only_list)

    both = _settings(allow_external_models=True, external_hosts=["openrouter.ai"])
    check_model_host("https://openrouter.ai/api/v1", both)


def test_allowlist_does_not_leak_to_other_hosts() -> None:
    settings = _settings(allow_external_models=True, external_hosts=["openrouter.ai"])
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://api.openai.com/v1", settings)


# ---------------------------------------------------------------------------
# An external provider in development mode
# ---------------------------------------------------------------------------


def test_local_ollama_gets_no_api_key() -> None:
    """A local Ollama needs no key and is not sent one."""
    from syft_benchmark.llm.ollama import _headers

    assert _headers(_settings()) == {}


def test_external_provider_gets_the_key() -> None:
    from syft_benchmark.llm.ollama import _headers

    conf = _settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-test",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    headers = _headers(conf)
    assert headers["Authorization"] == "Bearer sk-or-test"


def test_openrouter_url_is_assembled_correctly() -> None:
    """The provider's base already holds /v1 — it must not be appended twice."""
    from syft_benchmark.llm.ollama import _api_root

    root = _api_root("https://openrouter.ai/api/v1")
    assert f"{root}/v1/chat/completions" == (
        "https://openrouter.ai/api/v1/chat/completions"
    )


def test_a_key_alone_does_not_open_the_perimeter() -> None:
    """A key is not a permission.

    Configuring an external provider is not enough: until the ban is lifted
    explicitly, calling it stays an error. Otherwise accidentally leaving a key
    in the environment would be enough for questions about a private corpus to
    go outwards.
    """
    conf = _settings(
        ollama_url="https://openrouter.ai/api/v1", llm_api_key="sk-or-test"
    )
    with pytest.raises(ExternalCallBlocked):
        check_model_host(conf.ollama_url, conf)


def test_model_check_follows_the_role_not_the_common_settings() -> None:
    """A role is checked against ITS OWN address.

    The shared settings may point inside the perimeter while a role points
    outside. If the check looked at the shared address, it would report on a
    connection the real call will not take, and the perimeter ban would come to
    light in the middle of a run.
    """
    from syft_benchmark.llm import Provider, check_model_available

    conf = _settings(ollama_url="http://localhost:11434")
    outside = Provider(
        role="judge",
        url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        model="anthropic/claude-sonnet-4",
    )
    with pytest.raises(ExternalCallBlocked):
        check_model_available(outside.model, conf, outside)
