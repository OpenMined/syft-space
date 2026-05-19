"""Publish endpoint handler — marketplace integration, sync, and health."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    MarketplaceAvailabilityResult,
    PublishEndpointResponse,
    PublishResult,
    SlugAvailabilityResponse,
    UnpublishResult,
)
from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.gateway.xendit.config import XenditWalletConfig
from syft_space.components.wallets.repository import WalletRepository
from syft_space.config import app_settings


class PublishEndpointHandler:
    """Handler for endpoint marketplace publishing, sync, and health checks."""

    def __init__(
        self,
        endpoint_repository: EndpointRepository,
        marketplace_repository: MarketplaceRepository,
        dataset_repository: DatasetRepository,
        model_repository: ModelRepository,
        dataset_registry: DatasetTypeRegistry,
        model_registry: ModelTypeRegistry,
        wallet_repository: WalletRepository | None = None,
    ):
        self.endpoint_repository = endpoint_repository
        self.marketplace_repository = marketplace_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.wallet_repository = wallet_repository

    async def publish_endpoint(
        self,
        slug: str,
        marketplace_ids: list[UUID] | None,
        publish_to_all_marketplaces: bool,
        tenant: Tenant,
    ) -> PublishEndpointResponse:
        """Publish an endpoint to one or more marketplaces."""
        # Validate that either marketplace_ids or publish_to_all_marketplaces is provided
        if not publish_to_all_marketplaces and not marketplace_ids:
            raise HTTPException(
                status_code=400,
                detail="Either marketplace_ids or publish_to_all_marketplaces must be provided",
            )

        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        if publish_to_all_marketplaces:
            marketplaces = await self.marketplace_repository.get_active(tenant.id)
            if not marketplaces:
                raise HTTPException(
                    status_code=400, detail="No active marketplaces found"
                )
        else:
            marketplaces = await self.marketplace_repository.get_by_ids(
                marketplace_ids, tenant.id
            )
            found_ids = {m.id for m in marketplaces}
            missing_ids = set(marketplace_ids) - found_ids
            if missing_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Marketplaces not found: {[str(id) for id in missing_ids]}",
                )

        results: list[PublishResult] = []
        for marketplace in marketplaces:
            result = await self._publish_to_marketplace(endpoint, marketplace)
            results.append(result)

        return PublishEndpointResponse(endpoint_slug=slug, results=results)

    async def unpublish_endpoint(
        self, slug: str, tenant: Tenant
    ) -> list[UnpublishResult]:
        """Unpublish an endpoint from all its marketplaces."""
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        if not endpoint.published_to:
            raise HTTPException(status_code=400, detail="Endpoint is not published")

        marketplace_ids = [UUID(mid) for mid in endpoint.published_to]
        marketplaces = await self.marketplace_repository.get_by_ids(
            marketplace_ids, tenant.id
        )
        if not marketplaces:
            raise HTTPException(status_code=404, detail="Marketplaces not found")

        results: list[UnpublishResult] = []
        for marketplace in marketplaces:
            result = await self._unpublish_endpoint(endpoint, marketplace)
            results.append(result)

        return results

    async def check_slug_availability(
        self,
        slug: str,
        marketplace_ids: list[UUID] | None,
        check_all_marketplaces: bool,
        tenant: Tenant,
    ) -> SlugAvailabilityResponse:
        """Check if a slug is available locally and optionally on marketplaces."""
        existing_endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        local_available = existing_endpoint is None

        should_check_marketplaces = check_all_marketplaces or marketplace_ids
        if not should_check_marketplaces:
            return SlugAvailabilityResponse(
                slug=slug, local_available=local_available, marketplaces=None
            )

        if check_all_marketplaces:
            marketplaces = await self.marketplace_repository.get_active(tenant.id)
            missing_ids: set[UUID] = set()
        else:
            marketplaces = await self.marketplace_repository.get_by_ids(
                marketplace_ids, tenant.id
            )
            found_ids = {m.id for m in marketplaces}
            missing_ids = set(marketplace_ids) - found_ids

        marketplace_results: list[MarketplaceAvailabilityResult] = []

        for missing_id in missing_ids:
            marketplace_results.append(
                MarketplaceAvailabilityResult(
                    marketplace_id=missing_id,
                    available=None,
                    error="Marketplace not found",
                )
            )

        for marketplace in marketplaces:
            result = await self._check_marketplace_availability(slug, marketplace)
            marketplace_results.append(result)

        return SlugAvailabilityResponse(
            slug=slug,
            local_available=local_available,
            marketplaces=marketplace_results,
        )

    async def get_published_endpoint_health(
        self, tenant: Tenant, health_timeout: float = 5.0
    ) -> list[dict[str, Any]]:
        """Get health status of all published endpoints.

        Checks health of each endpoint's linked dataset and model concurrently.
        """
        endpoints = await self.endpoint_repository.get_published_endpoints(tenant.id)
        if not endpoints:
            return []

        async def _check_endpoint_health(endpoint: Endpoint) -> dict[str, Any]:
            checked_at = datetime.now(timezone.utc).isoformat()
            is_healthy = True

            if endpoint.dataset_id:
                try:
                    dataset = await self.dataset_repository.get_by_id(
                        endpoint.dataset_id, tenant.id
                    )
                    if dataset:
                        dataset_type_cls = self.dataset_registry.get_dataset_type(
                            dataset.dtype
                        )
                        dataset_type = dataset_type_cls(dataset.configuration)
                        response = await asyncio.wait_for(
                            dataset_type.healthcheck(), timeout=health_timeout
                        )
                        if response.status != HealthcheckStatus.HEALTHY:
                            is_healthy = False
                    else:
                        is_healthy = False
                except Exception:
                    is_healthy = False

            if endpoint.model_id:
                try:
                    model = await self.model_repository.get_by_id(
                        endpoint.model_id, tenant.id
                    )
                    if model:
                        model_type_cls = self.model_registry.get_model_type(model.dtype)
                        model_type = model_type_cls(model.configuration)
                        response = await asyncio.wait_for(
                            model_type.healthcheck(), timeout=health_timeout
                        )
                        if response.status != HealthcheckStatus.HEALTHY:
                            is_healthy = False
                    else:
                        is_healthy = False
                except Exception:
                    is_healthy = False

            return {
                "slug": endpoint.slug,
                "status": "healthy" if is_healthy else "unhealthy",
                "checked_at": checked_at,
            }

        results = await asyncio.gather(
            *[_check_endpoint_health(ep) for ep in endpoints],
            return_exceptions=True,
        )

        return [r for r in results if isinstance(r, dict)]

    async def sync_endpoints_to_marketplaces(
        self, tenant: Tenant
    ) -> dict[str, list[str]]:
        """Sync all published endpoints to their respective marketplaces."""
        endpoints = await self.endpoint_repository.get_published_endpoints(tenant.id)
        if not endpoints:
            logger.debug("No published endpoints to sync")
            return {}

        marketplace_endpoints: dict[UUID, list[Endpoint]] = {}
        for endpoint in endpoints:
            for marketplace_id in endpoint.published_to:
                marketplace_endpoints.setdefault(marketplace_id, []).append(endpoint)

        results: dict[str, list[str]] = {}

        for marketplace_id, eps in marketplace_endpoints.items():
            try:
                marketplace = await self.marketplace_repository.get_by_id(
                    UUID(marketplace_id), tenant.id
                )
                if not marketplace:
                    logger.warning(f"Marketplace {marketplace_id} not found, skipping")
                    continue
                if not marketplace.is_active:
                    logger.warning(f"Marketplace {marketplace_id} not active, skipping")
                    continue
                if not marketplace.email or not marketplace.password:
                    logger.warning(
                        f"Marketplace {marketplace_id} missing credentials, skipping"
                    )
                    continue

                payloads = [await self._build_publish_payload(ep) for ep in eps]

                async with SyftHubClient(base_url=marketplace.url) as client:
                    await client.login(
                        username=marketplace.email, password=marketplace.password
                    )
                    await client.sync_endpoints(payloads)

                results[marketplace_id] = [ep.slug for ep in eps]
                logger.info(
                    f"Synced {len(eps)} endpoints to marketplace {marketplace.name}"
                )

            except SyftHubError as e:
                logger.warning(
                    f"Failed to sync to marketplace {marketplace_id}: {e.message}"
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error syncing to marketplace {marketplace_id}: {e}"
                )

        return results

    # ── Private helpers ──────────────────────────────────────────

    async def _publish_to_marketplace(
        self, endpoint: Endpoint, marketplace: Marketplace
    ) -> PublishResult:
        """Publish endpoint to a single marketplace."""
        if not marketplace.is_active:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace is not active",
            )
        if not marketplace.email or not marketplace.password:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace credentials not configured",
            )

        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                payload = await self._build_publish_payload(endpoint)
                await client.publish_endpoint(payload, overwrite=True)
        except SyftHubError as e:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )

        try:
            await self.endpoint_repository.add_publication(
                endpoint.id, marketplace.id, endpoint.tenant_id
            )
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=True,
                message=f"Published successfully to {marketplace.name}: {marketplace.url}",
            )
        except Exception as e:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=str(e),
            )

    async def _unpublish_endpoint(
        self, endpoint: Endpoint, marketplace: Marketplace
    ) -> UnpublishResult:
        """Unpublish endpoint from a single marketplace."""
        if not marketplace.email or not marketplace.password:
            return UnpublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace credentials not configured",
            )
        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                await client.unpublish_endpoint(endpoint.slug)
                await self.endpoint_repository.remove_publication(
                    endpoint.id, marketplace.id, endpoint.tenant_id
                )
                return UnpublishResult(
                    marketplace_id=marketplace.id,
                    marketplace_name=marketplace.name,
                    success=True,
                    message=f"Unpublished successfully from {marketplace.name}",
                )
        except SyftHubError as e:
            return UnpublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )
        except Exception as e:
            logger.exception(
                f"Failed to unpublish endpoint {endpoint.slug} "
                f"from {marketplace.name}: {str(e)}"
            )
            return UnpublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=str(e),
            )

    async def _check_marketplace_availability(
        self, slug: str, marketplace: Marketplace
    ) -> MarketplaceAvailabilityResult:
        """Check slug availability on a single marketplace."""
        if not marketplace.is_active:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id,
                available=None,
                error="Marketplace is not active",
            )
        if not marketplace.email or not marketplace.password:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id,
                available=None,
                error="Marketplace credentials not configured",
            )

        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                exists = await client.endpoint_exists(slug)
                return MarketplaceAvailabilityResult(
                    marketplace_id=marketplace.id, available=not exists, error=None
                )
        except SyftHubError as e:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id, available=None, error=e.message
            )
        except Exception as e:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id, available=None, error=str(e)
            )

    async def _build_publish_payload(self, endpoint: Endpoint) -> dict[str, Any]:
        """Build the publish payload for an endpoint.

        Enriches payment policies with wallet_type and payment URLs.
        """
        endpoint_type = (
            "model_data_source"
            if endpoint.model_id is not None and endpoint.dataset_id is not None
            else "model"
            if endpoint.model_id is not None
            else "data_source"
        )

        # Batch-fetch wallets for payment policies
        wallets_by_id: dict[str, Any] = {}
        if self.wallet_repository:
            wallet_ids = [
                p.wallet_id for p in endpoint.policies if p.wallet_id is not None
            ]
            if wallet_ids:
                wallets = await self.wallet_repository.get_by_ids(
                    wallet_ids, endpoint.tenant_id
                )
                wallets_by_id = {str(w.id): w for w in wallets}

        policies = []
        for policy in endpoint.policies:
            policy_data: dict[str, Any] = {
                "type": policy.policy_type,
                "version": "1.0",
                "enabled": True,
                "description": policy.name,
                "config": dict(policy.configuration),
            }

            # Enrich payment policies with wallet info + wallet-scoped URLs.
            # URLs are identical across endpoints sharing the same wallet —
            # balance is fungible across them.
            if policy.wallet_id:
                wallet = wallets_by_id.get(str(policy.wallet_id))
                if wallet:
                    # Wire format: `type` is the provider (xendit/mpp);
                    # `config.unit_type` is a typed field on the policy's
                    # config class, so it's already in policy.configuration.
                    policy_data["type"] = wallet.wallet_type
                    policy_data["config"]["currency"] = wallet.currency
                    if wallet.country:
                        policy_data["config"]["country"] = wallet.country
                    if wallet.wallet_type == "xendit":
                        # Bundles drive the SyftHub purchase UI; without them
                        # the marketplace has no plans to render.
                        xendit_config = XenditWalletConfig(**wallet.configuration)
                        policy_data["config"]["bundles"] = [
                            {"name": b.name, "amount": b.amount}
                            for b in xendit_config.prepaid_balance_bundles
                        ]
                        if app_settings.public_url:
                            base = str(app_settings.public_url).rstrip("/")
                            policy_data["config"]["payment_url"] = (
                                f"{base}/api/v1/payments/gateway/wallets/{wallet.id}/invoices"
                            )
                            policy_data["config"]["invoices_url"] = (
                                f"{base}/api/v1/payments/gateway/wallets/{wallet.id}/invoices/me"
                            )
                            policy_data["config"]["credits_url"] = (
                                f"{base}/api/v1/payments/gateway/wallets/{wallet.id}/balance"
                            )

            policies.append(policy_data)

        connection_config = {
            "path": f"/api/v1/endpoints/{endpoint.slug}/query",
        }

        return {
            "name": endpoint.name,
            "description": endpoint.summary or "",
            "type": endpoint_type,
            "visibility": "public",
            "version": "0.1.0",
            "readme": endpoint.description or "",
            "slug": endpoint.slug,
            "policies": policies,
            "connect": [
                {
                    "type": "https",
                    "enabled": True,
                    "description": "",
                    "config": connection_config,
                }
            ],
        }
