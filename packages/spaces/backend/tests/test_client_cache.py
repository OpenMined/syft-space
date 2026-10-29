"""client_cache: one connect per (namespace, key), closed on evict."""

from __future__ import annotations

import asyncio

import pytest

from syft_space.components.shared import client_cache


class Counter:
    def __init__(self):
        self.built = 0
        self.closed: list[int] = []

    async def connect(self):
        self.built += 1
        await asyncio.sleep(0)  # yield so concurrent callers interleave
        return self.built

    async def close(self, client):
        self.closed.append(client)


async def test_hit_returns_same_client_without_reconnecting():
    c = Counter()

    first = await client_cache.get_client("ns", ("a",), c.connect)
    second = await client_cache.get_client("ns", ("a",), c.connect)

    assert first == second == 1
    assert c.built == 1


async def test_namespace_and_key_both_separate_clients():
    c = Counter()

    assert await client_cache.get_client("ns", ("a",), c.connect) == 1
    assert await client_cache.get_client("ns", ("b",), c.connect) == 2
    assert await client_cache.get_client("other", ("a",), c.connect) == 3


async def test_concurrent_first_callers_connect_once():
    c = Counter()

    clients = await asyncio.gather(
        *[client_cache.get_client("ns", ("a",), c.connect) for _ in range(10)]
    )

    assert set(clients) == {1}
    assert c.built == 1


async def test_failing_connect_caches_nothing():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("down")
        return "up"

    with pytest.raises(ConnectionError):
        await client_cache.get_client("ns", ("a",), flaky)

    assert await client_cache.get_client("ns", ("a",), flaky) == "up"


async def test_evict_runs_close_and_allows_reconnect():
    c = Counter()
    await client_cache.get_client("ns", ("a",), c.connect, close=c.close)

    await client_cache.evict("ns", ("a",))

    assert c.closed == [1]
    assert await client_cache.get_client("ns", ("a",), c.connect, close=c.close) == 2


async def test_evict_without_close_or_unknown_key_is_fine():
    c = Counter()
    await client_cache.get_client("ns", ("a",), c.connect)  # no close given

    await client_cache.evict("ns", ("a",))
    await client_cache.evict("ns", ("missing",))

    assert c.closed == []


async def test_close_all_closes_every_client_and_survives_a_bad_close():
    closed: list[str] = []

    async def connect_value(v):
        return v

    async def close(client):
        if client == "bad":
            raise RuntimeError("boom")
        closed.append(client)

    await client_cache.get_client(
        "ns", ("x",), lambda: connect_value("bad"), close=close
    )
    await client_cache.get_client(
        "ns", ("y",), lambda: connect_value("good"), close=close
    )

    await client_cache.close_all()

    assert closed == ["good"]
    assert (
        await client_cache.get_client("ns", ("y",), lambda: connect_value("new"))
        == "new"
    )
