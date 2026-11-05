"""Invariant 2: questions do not leave the perimeter.

The check lives in the tests rather than in review, because it can be broken
with one line of configuration and noticed only after the corpus has leaked.
"""

import pytest

from syft_benchmark.config import (
    ExternalCallBlocked,
    Settings,
    check_model_host,
    host_is_inside,
    model_host,
    url_is_inside,
)


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
    check_model_host(url, Settings())


@pytest.mark.parametrize(
    "url",
    [
        "https://openrouter.ai/api/v1",
        "https://api.openai.com/v1",
        "https://generativelanguage.googleapis.com",
        "http://[2606:4700::1111]/v1",
        "http://8.8.8.8/v1",
        "api.example.com:443/v1",
        "//ollama:11434/v1",
        "",
    ],
)
def test_external_hosts_blocked_by_default(url: str) -> None:
    with pytest.raises(ExternalCallBlocked):
        check_model_host(url, Settings())


@pytest.mark.parametrize(
    ("url", "host", "inside"),
    [
        # Loopback and the docker host, by name
        ("http://localhost:11434", "localhost", True),
        ("http://LOCALHOST:11434/v1", "localhost", True),
        ("http://host.docker.internal:11434", "host.docker.internal", True),
        # A docker-network service: one label
        ("http://ollama:11434/v1", "ollama", True),
        ("http://Ollama-2/v1", "ollama-2", True),
        # IP literals: only loopback is inside
        ("http://127.0.0.1:11434", "127.0.0.1", True),
        ("http://0.0.0.0:11434", "0.0.0.0", False),
        ("http://10.0.0.5:11434", "10.0.0.5", False),
        ("http://172.17.0.2:11434", "172.17.0.2", False),
        ("http://192.168.1.20:11434", "192.168.1.20", False),
        ("http://169.254.1.1/", "169.254.1.1", False),
        ("http://8.8.8.8/v1", "8.8.8.8", False),
        ("https://1.1.1.1:443/v1", "1.1.1.1", False),
        # IPv6 literals: no dot, still classified as addresses
        ("http://[::]:11434", "::", False),
        ("http://[::1]:11434", "::1", True),
        ("http://[fd00::5]:11434", "fd00::5", False),
        ("http://[fe80::1]/", "fe80::1", False),
        ("http://[2606:4700::1111]/v1", "2606:4700::1111", False),
        ("http://[2606:4700::1111]:8443/v1", "2606:4700::1111", False),
        ("http://[::ffff:8.8.8.8]/", "::ffff:8.8.8.8", False),
        ("http://[::ffff:127.0.0.1]/", "::ffff:127.0.0.1", True),
        # Dotless names a resolver reads as an IPv4 address
        ("http://2130706433/", "2130706433", False),
        ("http://0x08080808/", "0x08080808", False),
        # Names with a dot
        ("https://openrouter.ai/api/v1", "openrouter.ai", False),
        ("https://API.OpenAI.com/v1", "api.openai.com", False),
        ("http://ollama.:11434", "ollama.", False),
        # Nothing callable: no http(s) scheme, no host
        ("api.example.com:443/v1", "", False),
        ("localhost:11434", "", False),
        ("//ollama:11434/v1", "", False),
        ("//localhost:11434", "", False),
        ("ftp://localhost/", "", False),
        ("ollama://ollama:11434", "", False),
        ("HTTP://localhost:11434", "localhost", True),
        ("", "", False),
        ("http://", "", False),
        ("http://[::1/", "", False),
    ],
)
def test_where_an_address_points(url: str, host: str, inside: bool) -> None:
    assert model_host(url) == host
    assert host_is_inside(host) is inside
    assert url_is_inside(url) is inside


def test_an_unreadable_address_stays_blocked_even_with_permission() -> None:
    """A host that cannot be read cannot be matched against the allow-list."""
    conf = Settings(allow_external_models=True, external_hosts=[""])
    with pytest.raises(ExternalCallBlocked, match="cannot be read"):
        check_model_host("api.example.com:443/v1", conf)


def test_an_ipv6_literal_passes_only_through_the_allow_list() -> None:
    conf = Settings(allow_external_models=True, external_hosts=["2606:4700::1111"])
    check_model_host("http://[2606:4700::1111]/v1", conf)


def test_external_host_needs_both_flag_and_list() -> None:
    """A flag alone is not enough: the host has to be named explicitly.

    Otherwise turning on "allow external" opens the road anywhere at all,
    including places the owner never intended.
    """
    only_flag = Settings(allow_external_models=True)
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://openrouter.ai/api/v1", only_flag)

    only_list = Settings(external_hosts=["openrouter.ai"])
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://openrouter.ai/api/v1", only_list)

    both = Settings(allow_external_models=True, external_hosts=["openrouter.ai"])
    check_model_host("https://openrouter.ai/api/v1", both)


def test_allowlist_does_not_leak_to_other_hosts() -> None:
    settings = Settings(allow_external_models=True, external_hosts=["openrouter.ai"])
    with pytest.raises(ExternalCallBlocked):
        check_model_host("https://api.openai.com/v1", settings)


# ---------------------------------------------------------------------------
# An external provider in development mode
# ---------------------------------------------------------------------------


def test_local_ollama_gets_no_api_key() -> None:
    """A local Ollama needs no key and is not sent one."""
    from syft_benchmark.llm.client import _headers_for

    conf = Settings()
    assert _headers_for(conf.llm_api_key, conf.llm_app_name) == {}


def test_external_provider_gets_the_key() -> None:
    from syft_benchmark.llm.client import _headers_for

    conf = Settings(
        ollama_url="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-test",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    headers = _headers_for(conf.llm_api_key, conf.llm_app_name)
    assert headers["Authorization"] == "Bearer sk-or-test"


def test_openrouter_url_is_assembled_correctly() -> None:
    """The provider's base already holds /v1 — it must not be appended twice."""
    from syft_benchmark.llm.providers import api_root

    root = api_root("https://openrouter.ai/api/v1")
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
    conf = Settings(ollama_url="https://openrouter.ai/api/v1", llm_api_key="sk-or-test")
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

    conf = Settings(ollama_url="http://localhost:11434")
    outside = Provider(
        role="judge",
        url="https://openrouter.ai/api/v1",
        api_key="sk-or-test",
        model="anthropic/claude-sonnet-4",
    )
    with pytest.raises(ExternalCallBlocked):
        check_model_available(outside.model, conf, outside)
