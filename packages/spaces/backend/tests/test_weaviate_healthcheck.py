"""Remote Weaviate healthcheck is one GET of the readiness probe.

Opening a full weaviate client (HTTP + gRPC handshake under a 2 s init
timeout) just to ask "are you up" failed at random when several endpoints
checked the same host concurrently.
"""

from __future__ import annotations

import httpx

from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.vector_stores.weaviate_remote import (
    weaviate_vector_store as ws_module,
)
from syft_space.components.vector_stores.weaviate_remote.weaviate_vector_store import (
    WeaviateVectorStore,
)

CONFIG = {
    "http_url": "https://weaviate.example.com:8443",
    "grpc_url": "https://weaviate.example.com:50051",
    "api_key": "secret",
    "collection_name": "Docs",
    "headers": {"X-OpenAI-Api-Key": "third-party"},
}


def _mock_httpx(monkeypatch, handler):
    """Route the store's AsyncClient through a MockTransport, capturing requests."""
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def make_client(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(_handler), **kwargs)

    monkeypatch.setattr(ws_module, "httpx", type("H", (), {"AsyncClient": make_client}))
    monkeypatch.setattr(ws_module, "enabled", True)
    return seen


async def test_ready_probe_200_is_healthy(monkeypatch):
    seen = _mock_httpx(monkeypatch, lambda r: httpx.Response(200))

    response = await WeaviateVectorStore(CONFIG).healthcheck()

    assert response.status == HealthcheckStatus.HEALTHY
    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == "https://weaviate.example.com:8443/v1/.well-known/ready"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.headers["X-OpenAI-Api-Key"] == "third-party"


async def test_ready_probe_non_200_is_unhealthy_with_status(monkeypatch):
    _mock_httpx(monkeypatch, lambda r: httpx.Response(503))

    response = await WeaviateVectorStore(CONFIG).healthcheck()

    assert response.status == HealthcheckStatus.UNHEALTHY
    assert "503" in response.message


async def test_transport_failure_is_unhealthy_with_reason(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("connection refused", request=request)

    _mock_httpx(monkeypatch, boom)

    response = await WeaviateVectorStore(CONFIG).healthcheck()

    assert response.status == HealthcheckStatus.UNHEALTHY
    assert "connection refused" in response.message


async def test_missing_dependency_is_unhealthy_without_a_request(monkeypatch):
    seen = _mock_httpx(monkeypatch, lambda r: httpx.Response(200))
    monkeypatch.setattr(ws_module, "enabled", False)

    response = await WeaviateVectorStore(CONFIG).healthcheck()

    assert response.status == HealthcheckStatus.UNHEALTHY
    assert seen == []
