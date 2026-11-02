"""WordPress validation: the site is probed only when how we reach it changed.

Stubbed below the delta rule, at the REST call, so the rule itself runs."""

from __future__ import annotations

import pytest

from syft_space.components.sources.wordpress import wordpress_source as wp
from syft_space.components.sources.wordpress.wordpress_source import WordPressProvider

CONF = {
    "siteUrl": "https://blog.example",
    "username": "editor",
    "applicationPassword": "abcd efgh",
}


@pytest.fixture
def probed(monkeypatch) -> list[str]:
    calls: list[str] = []

    async def fetch_post_types(client):
        calls.append(client.base_url.host)
        return {"post": {"name": "Posts", "rest_base": "posts"}}

    monkeypatch.setattr(wp, "_fetch_post_types", fetch_post_types)
    return calls


class TestValidationScope:
    async def test_a_new_configuration_is_probed(self, probed):
        await WordPressProvider.validate_configuration(CONF)
        assert probed == ["blog.example"]

    async def test_an_ingest_only_edit_is_not_probed(self, probed):
        await WordPressProvider.validate_configuration(
            {**CONF, "pollIntervalSeconds": 60}, previous=CONF
        )
        assert probed == []

    async def test_a_credential_change_is_probed(self, probed):
        await WordPressProvider.validate_configuration(
            {**CONF, "applicationPassword": "new"}, previous=CONF
        )
        assert probed == ["blog.example"]

    async def test_a_malformed_payload_fails_before_any_probe(self, probed):
        with pytest.raises(ValueError):
            await WordPressProvider.validate_configuration(
                {"siteUrl": "x"}, previous=CONF
            )
        assert probed == []
