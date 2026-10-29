"""An endpoint reported unhealthy leaves a WARNING with the reason in the log.

The health-check failures used to be swallowed, so a flapping endpoint on
the Hub had no trace on the Space side.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from loguru import logger

from syft_space.components.endpoints.publish_handler import PublishEndpointHandler
from syft_space.components.shared.domain_types import (
    HealthcheckResponse,
    HealthcheckStatus,
)

TENANT = SimpleNamespace(id=uuid4())


@pytest.fixture
def warnings():
    captured: list[str] = []
    sink_id = logger.add(
        lambda m: captured.append(m.record["message"]), level="WARNING"
    )
    yield captured
    logger.remove(sink_id)


def make_handler(dataset_healthcheck, endpoint_slug="news", dataset_found=True):
    endpoint = SimpleNamespace(slug=endpoint_slug, dataset_id=uuid4(), model_id=None)
    dataset = SimpleNamespace(dtype="remote_weaviate", configuration={})

    class DatasetType:
        def __init__(self, configuration):
            pass

        async def healthcheck(self):
            return await dataset_healthcheck()

    async def get_published_endpoints(tenant_id):
        return [endpoint]

    async def get_by_id(dataset_id, tenant_id):
        return dataset if dataset_found else None

    return PublishEndpointHandler(
        endpoint_repository=SimpleNamespace(
            get_published_endpoints=get_published_endpoints
        ),
        marketplace_repository=SimpleNamespace(),
        dataset_repository=SimpleNamespace(get_by_id=get_by_id),
        model_repository=SimpleNamespace(),
        dataset_registry=SimpleNamespace(get_dataset_type=lambda dtype: DatasetType),
        model_registry=SimpleNamespace(),
    )


async def test_healthy_endpoint_logs_nothing(warnings):
    async def ok():
        return HealthcheckResponse(status=HealthcheckStatus.HEALTHY, message="fine")

    [result] = await make_handler(ok).get_published_endpoint_health(TENANT)

    assert result["status"] == "healthy"
    assert warnings == []


async def test_unhealthy_response_logs_its_message(warnings):
    async def down():
        return HealthcheckResponse(
            status=HealthcheckStatus.UNHEALTHY, message="ready probe returned 503"
        )

    [result] = await make_handler(down).get_published_endpoint_health(TENANT)

    assert result["status"] == "unhealthy"
    assert warnings == [
        "Endpoint news reported unhealthy (dataset): ready probe returned 503"
    ]


async def test_raising_healthcheck_logs_the_exception(warnings):
    async def boom():
        raise ConnectionError("connection refused")

    [result] = await make_handler(boom).get_published_endpoint_health(TENANT)

    assert result["status"] == "unhealthy"
    assert warnings == [
        "Endpoint news reported unhealthy (dataset): "
        "ConnectionError: connection refused"
    ]


async def test_timeout_logs_the_budget(warnings):
    async def slow():
        await asyncio.sleep(10)

    [result] = await make_handler(slow).get_published_endpoint_health(
        TENANT, health_timeout=0.01
    )

    assert result["status"] == "unhealthy"
    assert warnings == [
        "Endpoint news reported unhealthy (dataset): health check timed out after 0s"
    ]


async def test_missing_dataset_logs_not_found(warnings):
    async def never():
        raise AssertionError("not reached")

    [result] = await make_handler(
        never, dataset_found=False
    ).get_published_endpoint_health(TENANT)

    assert result["status"] == "unhealthy"
    assert warnings == ["Endpoint news reported unhealthy (dataset): dataset not found"]
