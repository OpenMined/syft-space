"""The helpers a source validation is built from (``sources/validation.py``)."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, ConfigDict, Field

from syft_space.components.sources.validation import (
    changed_fields,
    gather_bounded,
    parse_config,
    previous_config,
)


class _Browse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    site_url: str = Field(alias="siteUrl")
    api_key: str = Field(alias="apiKey")


class _Dataset(_Browse):
    poll: int = 60


class TestParseConfig:
    def test_reads_the_model(self):
        cfg = parse_config(_Browse, {"siteUrl": "https://a", "apiKey": "k"}, "x")
        assert cfg.site_url == "https://a"

    def test_refusal_is_a_value_error_naming_what(self):
        with pytest.raises(ValueError, match="Invalid browse configuration"):
            parse_config(_Browse, {"siteUrl": "https://a"}, "browse configuration")


class TestPreviousConfig:
    def test_absent_is_none(self):
        assert previous_config(_Browse, None) is None

    def test_unreadable_is_none(self):
        assert previous_config(_Browse, {"siteUrl": "https://a"}) is None

    def test_reads_either_spelling(self):
        prev = previous_config(_Browse, {"site_url": "https://a", "api_key": "k"})
        assert prev is not None and prev.api_key == "k"


class TestChangedFields:
    def test_no_previous_means_every_field(self):
        cur = _Dataset(site_url="https://a", api_key="k")
        assert changed_fields(_Browse, cur, None) == {"site_url", "api_key"}

    def test_only_differing_fields(self):
        cur = _Dataset(site_url="https://a", api_key="new")
        prev = _Browse(site_url="https://a", api_key="k")
        assert changed_fields(_Browse, cur, prev) == {"api_key"}

    def test_fields_outside_the_model_do_not_count(self):
        """A dataset-only field (poll) changing is not a connection change."""
        cur = _Dataset(site_url="https://a", api_key="k", poll=900)
        prev = _Browse(site_url="https://a", api_key="k")
        assert changed_fields(_Browse, cur, prev) == set()


class TestGatherBounded:
    async def test_results_in_item_order_with_failures_inline(self):
        async def fn(n: int) -> int:
            if n == 2:
                raise ValueError("two")
            return n * 10

        results = await gather_bounded([1, 2, 3], fn)
        assert results[0] == 10 and results[2] == 30
        assert isinstance(results[1], ValueError)

    async def test_at_most_limit_in_flight(self):
        running = 0
        peak = 0

        async def fn(_: int) -> None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0)
            running -= 1

        await gather_bounded(range(10), fn, limit=3)
        assert peak <= 3

    async def test_empty_is_empty(self):
        async def fn(n: int) -> int:
            return n

        assert await gather_bounded([], fn) == []
