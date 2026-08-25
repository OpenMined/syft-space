"""Transport-level failure handling on the browse path.

Two regressions this pins:

* A WordPress site that canonicalises REST paths with a trailing-slash 301
  must still be browsable. httpx does not follow redirects by default, so
  omitting ``follow_redirects`` broke every such site.
* A transport failure the source's own error mapping doesn't recognise must
  reach the picker as a readable 502, not escape as an unhandled 500 with a
  traceback.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from syft_space.components.datasets.handlers import DatasetHandler
from syft_space.components.sources.errors import SourceAuthError
from syft_space.components.sources.wordpress.wordpress_source import (
    WordPressBrowseConfig,
    _make_client,
)

WP_CONF = {
    "siteUrl": "https://example.com",
    "username": "someone",
    "applicationPassword": "xxxx yyyy zzzz",
}


class TestWordPressRedirects:
    def test_client_follows_redirects(self):
        # Without this, a site that 301s /types -> /types/ fails outright.
        client = _make_client(WordPressBrowseConfig.model_validate(WP_CONF))
        assert client.follow_redirects is True

    async def test_trailing_slash_redirect_is_followed(self):
        """A canonicalising 301 resolves instead of raising."""
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            if not request.url.path.endswith("/"):
                return httpx.Response(
                    301, headers={"Location": f"{request.url.path}/"}, request=request
                )
            return httpx.Response(200, json={"post": {"slug": "post"}}, request=request)

        cfg = WordPressBrowseConfig.model_validate(WP_CONF)
        async with httpx.AsyncClient(
            base_url=f"{cfg.site_url}/wp-json/wp/v2",
            follow_redirects=True,
            transport=httpx.MockTransport(handler),
        ) as client:
            response = await client.get("/types")

        assert response.status_code == 200
        assert seen == ["/wp-json/wp/v2/types", "/wp-json/wp/v2/types/"]

    async def test_authorization_is_dropped_across_origins(self):
        """A redirect to another host must not carry the Application Password."""
        seen: list[tuple[str, str | None]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.host, request.headers.get("Authorization")))
            if request.url.host == "example.com":
                return httpx.Response(
                    301, headers={"Location": "https://evil.test/x"}, request=request
                )
            return httpx.Response(200, json={}, request=request)

        cfg = WordPressBrowseConfig.model_validate(WP_CONF)
        async with httpx.AsyncClient(
            base_url=f"{cfg.site_url}/wp-json/wp/v2",
            auth=(cfg.username, cfg.application_password),
            follow_redirects=True,
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.get("/types")

        hosts = dict(seen)
        assert hosts["example.com"] is not None
        assert hosts["evil.test"] is None


class TestWordPressMissingRestApi:
    async def test_404_says_the_site_is_not_wordpress(self, monkeypatch):
        """A non-WordPress URL must not read as a credentials problem."""
        from syft_space.components.sources.wordpress import wordpress_source as wp

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="<!DOCTYPE html>", request=request)

        def fake_client(_cfg):
            return httpx.AsyncClient(
                base_url="https://example.com/wp-json/wp/v2",
                transport=httpx.MockTransport(handler),
            )

        monkeypatch.setattr(wp, "_make_client", fake_client)
        with pytest.raises(ValueError) as exc:
            await wp.WordPressProvider.validate_browse_config(WP_CONF)
        assert "No WordPress REST API" in str(exc.value)
        assert "example.com" in str(exc.value)


class TestBrowseErrorMapping:
    """``_browse_with_provider`` maps failures to a status the picker can show."""

    def _provider(self, error: Exception) -> MagicMock:
        provider = MagicMock()

        async def _raise(_configuration):
            raise error

        provider.validate_browse_config = _raise
        return provider

    async def _browse(self, error: Exception) -> HTTPException:
        handler = DatasetHandler.__new__(DatasetHandler)
        with pytest.raises(HTTPException) as exc:
            await handler._browse_with_provider(
                self._provider(error), "wordpress", {}, None, None
            )
        return exc.value

    async def test_unrecognised_transport_error_becomes_502(self):
        # Previously escaped as an unhandled 500 with a full traceback.
        result = await self._browse(
            httpx.HTTPStatusError(
                "Redirect response '301 Moved Permanently'",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(301),
            )
        )
        assert result.status_code == 502
        assert "Source request failed" in result.detail

    async def test_connect_error_becomes_502(self):
        result = await self._browse(httpx.ConnectError("name resolution failed"))
        assert result.status_code == 502

    async def test_source_errors_keep_their_own_status(self):
        # The typed source errors must not be swallowed by the new catch-all.
        result = await self._browse(SourceAuthError("bad credentials"))
        assert result.status_code == 401

    async def test_value_error_still_maps_to_400(self):
        result = await self._browse(ValueError("no ingestable post types"))
        assert result.status_code == 400
