"""The first heartbeat waits for provisioner startup, with a bound.

Local provisioners (ChromaDB) boot in a background task; reporting before
they are up marked every local dataset unhealthy once per boot.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from loguru import logger

from syft_space.components.endpoints.endpoint_heartbeat_manager import (
    EndpointHeartbeatManager,
)


def make_manager(get_active) -> EndpointHeartbeatManager:
    async def get_public_url():
        return "https://space.example.com"

    manager = EndpointHeartbeatManager(
        health_checker=SimpleNamespace(),
        marketplace_repository=SimpleNamespace(get_active=get_active),
        settings_repository=SimpleNamespace(get_public_url=get_public_url),
    )
    manager.set_tenant(SimpleNamespace(id=uuid4()))
    return manager


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_no_event_means_no_wait():
    manager = make_manager(get_active=None)

    await asyncio.wait_for(manager._wait_for_provisioners(), timeout=0.1)


async def test_first_report_waits_for_provisioner_event():
    reports: list[int] = []

    async def get_active(tenant_id):
        reports.append(1)
        return []  # nothing to deliver; reaching here is the observable

    manager = make_manager(get_active)
    ready = asyncio.Event()
    manager.set_provisioner_ready_event(ready)

    await manager.startup()
    try:
        await _settle()
        assert reports == []

        ready.set()
        await _settle()
        assert reports == [1]
    finally:
        await manager.shutdown()


async def test_wait_is_bounded_and_warns(monkeypatch):
    captured: list[str] = []
    sink_id = logger.add(
        lambda m: captured.append(m.record["message"]), level="WARNING"
    )
    monkeypatch.setattr(EndpointHeartbeatManager, "PROVISIONER_WAIT_TIMEOUT", 0.01)
    manager = make_manager(get_active=None)
    manager.set_provisioner_ready_event(asyncio.Event())  # never set

    try:
        await asyncio.wait_for(manager._wait_for_provisioners(), timeout=1.0)
    finally:
        logger.remove(sink_id)

    assert any("Provisioner startup not complete" in m for m in captured)
