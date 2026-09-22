"""Publish endpoint handler — marketplace integration, sync, and health."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint, ResponseType
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    KIND_ANSWERING,
    KIND_RETRIEVAL,
    EndpointQualityResponse,
    MarketplaceAvailabilityResult,
    PublishEndpointResponse,
    PublishResult,
    QualityMarketplaceResult,
    ReportQualityRequest,
    ReportQualityResponse,
    RetractQualityResponse,
    SlugAvailabilityResponse,
    UnpublishResult,
)
from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.satellites import SatelliteRegistrar
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.settings.repository import SettingsRepository
from syft_space.components.shared.domain_types import HealthcheckStatus
from syft_space.components.shared.syfthub_client import (
    NotFoundError,
    SyftHubClient,
    SyftHubError,
)
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.interfaces import WalletProvider
from syft_space.components.wallets.repository import WalletRepository
from syft_space.config import app_settings

PUBLISH_TIMEOUT_SECONDS = 60.0


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
        wallet_providers: dict[str, WalletProvider] | None = None,
        settings_repository: SettingsRepository | None = None,
    ):
        self.endpoint_repository = endpoint_repository
        self.marketplace_repository = marketplace_repository
        self.satellites = SatelliteRegistrar(marketplace_repository)
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.wallet_repository = wallet_repository
        self.wallet_providers = wallet_providers or {}
        # Optional so existing construction sites keep working. Absent, the
        # benchmark API stays closed, which is the safe reading of "unknown".
        self.settings_repository = settings_repository

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

    async def report_quality(
        self,
        slug: str,
        report: ReportQualityRequest,
        tenant: Tenant,
    ) -> ReportQualityResponse:
        """Record a benchmark's card and publish it to the marketplaces.

        The benchmark measures; the Space publishes. That split is the whole
        design: marketplace credentials live here and nowhere else, so a
        benchmark never needs - and never gets - an account on the hub. It
        hands its figures to the Space that owns the endpoint, and the Space
        speaks for itself, exactly as it already does for endpoint health.

        Gated on the benchmarks ``mode`` setting, which is "off" until the
        owner turns it on. While off this reads as 404: not "you may not" but
        "there is nothing here", because a Space that has not opted in should
        not advertise a way to speak in its name.

        The card is stored whole and summarised into columns at the same time.
        The columns are what a list of endpoints paints a badge from; the whole
        card is what the owner reads before deciding whether he vouches for it.

        Appended, not overwritten. The previous run is not made untrue by this
        one; it becomes the figure this one is read against.

        Args:
            slug: Endpoint the benchmark evaluated
            report: The card
            tenant: Tenant owning the endpoint

        Returns:
            ReportQualityResponse with the local write and one result per
            marketplace

        Raises:
            HTTPException: 404 if reporting is off or the endpoint is unknown
        """
        await self._require_benchmarks_enabled()

        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        # A benchmark may measure an endpoint in a mode it no longer serves -
        # the owner is free to switch response_type between runs. Say so rather
        # than refusing: the card describes what was measured, and a stale kind
        # is information, not a fault.
        if not self._kind_matches(endpoint, report.kind):
            logger.info(
                f"Benchmark reports '{report.kind}' for {slug}, which now "
                f"serves '{endpoint.response_type}' - storing as reported"
            )

        card = report.model_dump(mode="json")

        # Local first. A marketplace may be down, and the run that produced
        # these figures may have taken hours - losing them to a network blip
        # would be the expensive kind of mistake.
        stored = await self.endpoint_repository.record_quality(
            endpoint.id,
            tenant.id,
            kind=report.kind,
            score=report.score,
            fabrication_rate=report.fabrication_rate,
            samples=report.samples,
            reliable=report.reliable,
            checked_at=report.checked_at,
            report=card,
        )

        results: list[QualityMarketplaceResult] = []
        if stored is None:
            # The endpoint was deleted between the check above and this write
            # - nothing to publish under a name that no longer exists.
            logger.info(f"Endpoint '{slug}' vanished before its card could be stored")
        else:
            payload: dict[str, Any] = {"slug": endpoint.slug, **card}
            for marketplace in await self._marketplaces_for(endpoint, tenant):
                results.append(await self._push_quality(marketplace, payload))

        return ReportQualityResponse(
            endpoint_slug=slug, stored=stored is not None, results=results
        )

    async def get_quality(self, slug: str, tenant: Tenant) -> EndpointQualityResponse:
        """The stored card, for the owner's own page.

        Not gated on the benchmarks ``mode`` setting: this is the owner reading what is
        being said in his name, and a card published while reporting was on
        must stay visible after he switches it off - otherwise he cannot find
        what he needs to retract.

        Args:
            slug: Endpoint to read
            tenant: Tenant owning it

        Returns:
            EndpointQualityResponse; ``reported`` is False when no benchmark
            has ever reported - or every card has since been withdrawn - which
            is not a score of zero

        Raises:
            HTTPException: 404 if the endpoint is unknown
        """
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        card = await self.endpoint_repository.get_current_quality(
            endpoint.id, tenant.id
        )
        if card is None:
            return EndpointQualityResponse(
                endpoint_slug=slug,
                reported=False,
                published_to=list(endpoint.published_to or []),
            )

        return EndpointQualityResponse(
            endpoint_slug=slug,
            reported=True,
            kind=card.kind,
            score=card.score,
            fabrication_rate=card.fabrication_rate,
            samples=card.samples,
            reliable=card.reliable,
            checked_at=card.checked_at,
            published_to=list(endpoint.published_to or []),
            report=card.report,
        )

    async def retract_quality(
        self,
        slug: str,
        tenant: Tenant,
    ) -> RetractQualityResponse:
        """Withdraw an endpoint's published benchmark card.

        Not gated on the benchmarks ``mode`` setting, and that is deliberate.
        Reporting is a claim the owner lets a benchmark make on their behalf;
        retracting is an act of ownership over that claim. Turning reporting
        off must not also strand whatever was published while it was on - that
        would make the setting a one-way door.

        The cards are marked withdrawn, not deleted. Retracting is a claim
        about what the outside world may show, not an instruction to the Space
        to forget what it measured - and a history with the awkward runs
        removed would be worth less than no history.

        Args:
            slug: Endpoint whose card is withdrawn
            tenant: Tenant owning the endpoint

        Returns:
            RetractQualityResponse with the local wipe and one result per
            marketplace

        Raises:
            HTTPException: 404 if the endpoint is unknown
        """
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        # Marketplaces first, this time. What the outside world can see matters
        # more than the local copy, and if a marketplace refuses, the owner is
        # left able to see that it still has a card to take down.
        results: list[QualityMarketplaceResult] = []
        for marketplace in await self._marketplaces_for(endpoint, tenant):
            results.append(await self._retract_quality(endpoint, marketplace))

        withdrawn = await self.endpoint_repository.retract_quality(
            endpoint.id, tenant.id
        )

        return RetractQualityResponse(
            endpoint_slug=slug, cleared=withdrawn > 0, results=results
        )

    @staticmethod
    def _kind_matches(endpoint: Endpoint, kind: str) -> bool:
        """Whether the measured kind still describes what this endpoint serves.

        ``raw`` never writes an answer, so it can only be measured as
        retrieval; ``summary`` and ``both`` write one and are measured by it.
        """
        serving = str(endpoint.response_type)
        if serving == ResponseType.RAW.value:
            return kind == KIND_RETRIEVAL
        return kind == KIND_ANSWERING

    async def _require_benchmarks_enabled(self) -> None:
        """Reject reporting unless the owner switched it on."""
        mode = "off"
        if self.settings_repository is not None:
            mode = await self.settings_repository.get_benchmarks_mode()
        if mode == "off":
            raise HTTPException(status_code=404, detail="Not Found")

    async def _marketplaces_for(
        self, endpoint: Endpoint, tenant: Tenant
    ) -> list[Marketplace]:
        """Marketplaces this endpoint is published to.

        A card follows publication: an endpoint nobody can find in a
        marketplace has no figures to show there either.
        """
        if not endpoint.published_to:
            return []
        return await self.marketplace_repository.get_by_ids(
            [UUID(mid) for mid in endpoint.published_to], tenant.id
        )

    async def _push_quality(
        self, marketplace: Marketplace, payload: dict[str, Any]
    ) -> QualityMarketplaceResult:
        """Send one endpoint's card to a single marketplace."""
        if not marketplace.email or not marketplace.password:
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace credentials not configured",
            )
        try:
            async with SyftHubClient(
                base_url=marketplace.url, timeout=PUBLISH_TIMEOUT_SECONDS
            ) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                result = await client.update_endpoint_quality([payload])
                accepted = int(result.get("updated", 0)) > 0
                return QualityMarketplaceResult(
                    marketplace_id=marketplace.id,
                    marketplace_name=marketplace.name,
                    success=accepted,
                    message=(
                        f"Card reported to {marketplace.name}" if accepted else None
                    ),
                    error=(
                        None
                        if accepted
                        else f"{marketplace.name} did not recognise this endpoint"
                    ),
                )
        except NotFoundError:
            # The marketplace predates benchmark cards. Expected against an
            # unmodified hub, and not the Space's problem to fix - say so
            # plainly rather than reporting a failure the owner cannot act on.
            logger.info(f"Marketplace {marketplace.name} has no quality API, skipping")
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                supported=False,
                message=f"{marketplace.name} does not support benchmark cards",
            )
        except SyftHubError as e:
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )
        except Exception as e:
            logger.exception(f"Failed to report card to {marketplace.name}: {str(e)}")
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=str(e),
            )

    async def _retract_quality(
        self, endpoint: Endpoint, marketplace: Marketplace
    ) -> QualityMarketplaceResult:
        """Withdraw one endpoint's card from a single marketplace."""
        if not marketplace.email or not marketplace.password:
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace credentials not configured",
            )
        try:
            async with SyftHubClient(
                base_url=marketplace.url, timeout=PUBLISH_TIMEOUT_SECONDS
            ) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                await client.clear_endpoint_quality(endpoint.slug)
                return QualityMarketplaceResult(
                    marketplace_id=marketplace.id,
                    marketplace_name=marketplace.name,
                    success=True,
                    message=f"Card withdrawn from {marketplace.name}",
                )
        except NotFoundError:
            # Either the marketplace has no benchmark API, or it does not know
            # this endpoint. For a retraction both mean the same thing: there
            # is nothing there to take down, so the goal is already met.
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=True,
                supported=False,
                message=f"Nothing published at {marketplace.name}",
            )
        except SyftHubError as e:
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )
        except Exception as e:
            logger.exception(
                f"Failed to withdraw card from {marketplace.name}: {str(e)}"
            )
            return QualityMarketplaceResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=str(e),
            )

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
                    satellite_id = await self.satellites.resolve_id(
                        client, marketplace, self._public_url(), tenant.id
                    )
                    if satellite_id is None:
                        logger.warning(
                            f"Marketplace {marketplace_id} has no satellite "
                            "(no public URL set), skipping sync"
                        )
                        continue
                    try:
                        await client.sync_endpoints(payloads, satellite_id)
                    except NotFoundError:
                        # Hub no longer knows this satellite (deleted there,
                        # or the row was re-pointed at another account).
                        # Re-register so the catalogue still syncs this boot.
                        await self.satellites.forget_id(marketplace, tenant.id)
                        retry_id = await self.satellites.resolve_id(
                            client, marketplace, self._public_url(), tenant.id
                        )
                        if retry_id is None:
                            continue
                        await client.sync_endpoints(payloads, retry_id)

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

    @staticmethod
    def _public_url() -> str | None:
        """The origin a satellite would be registered at."""
        return str(app_settings.public_url) if app_settings.public_url else None

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
            async with SyftHubClient(
                base_url=marketplace.url, timeout=PUBLISH_TIMEOUT_SECONDS
            ) as client:
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )
                satellite_id = await self.satellites.resolve_id(
                    client, marketplace, self._public_url(), endpoint.tenant_id
                )
                if satellite_id is None:
                    return PublishResult(
                        marketplace_id=marketplace.id,
                        marketplace_name=marketplace.name,
                        success=False,
                        error="Set this space's public URL before publishing",
                    )
                payload = await self._build_publish_payload(endpoint)
                # Slugs are unique per account, not per space: a 400 on a
                # slug we never published means another space holds it, and
                # overwriting would replace their listing's contents.
                ours = str(marketplace.id) in endpoint.published_to
                await client.publish_endpoint(payload, satellite_id, overwrite=ours)
        except NotFoundError as e:
            await self.satellites.forget_id(marketplace, endpoint.tenant_id)
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )
        except SyftHubError as e:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )
        except Exception as e:
            # Everything the hub says arrives as a SyftHubError; what is left
            # here is the hub not saying anything — a timeout, a dropped
            # connection, a reply we could not parse. That is a failed
            # publication, not a broken space, so it is reported as one rather
            # than escaping as a 500 the caller cannot read.
            logger.exception(
                f"Failed to publish endpoint {endpoint.slug} "
                f"to {marketplace.name}: {str(e)}"
            )
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=f"{type(e).__name__}: {e}",
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

        # An endpoint has at most one wallet across its policies (enforced
        # at attach time by CapabilityChecker). Fetch it once and reuse.
        wallet: Wallet | None = None
        if self.wallet_repository:
            wallet_id = next(
                (p.wallet_id for p in endpoint.policies if p.wallet_id is not None),
                None,
            )
            if wallet_id:
                wallet = await self.wallet_repository.get_by_id(
                    wallet_id, endpoint.tenant_id
                )

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
            if policy.wallet_id and wallet is not None:
                # Wire format: `type` is the provider (xendit/stripe/mpp);
                # `config.unit_type` is a typed field on the policy's
                # config class, so it's already in policy.configuration.
                policy_data["type"] = wallet.wallet_type
                policy_data["config"]["currency"] = wallet.currency
                if wallet.country:
                    policy_data["config"]["country"] = wallet.country
                # Prepaid-balance wallets publish payment info: bundles,
                # a stable wallet id, and the URLs where buyers top up and read
                # their balance. Each provider builds its own URLs so they point
                # at wherever the balance lives — this space, or a managing
                # station. Non-prepaid providers (MPP) return None.
                provider = self.wallet_providers.get(wallet.wallet_type)
                info = (
                    provider.payment_info(wallet.configuration, wallet.id)
                    if provider is not None
                    else None
                )
                if info is not None:
                    # Identical across every space sharing this wallet, so a
                    # marketplace groups them as one fungible balance.
                    # wallet_owner (a hub user id) appears only when someone
                    # other than the publishing user owns the wallet — its
                    # presence is the "managed" signal, and it tells the hub
                    # whose audience to mint buyer tokens for and who to
                    # credit as the host. Absent = the publishing user.
                    policy_data["config"]["wallet_id"] = str(wallet.id)
                    if info.owner is not None:
                        policy_data["config"]["wallet_owner"] = info.owner
                    policy_data["config"]["bundles"] = info.bundles
                    if info.payment_url:
                        policy_data["config"]["payment_url"] = info.payment_url
                        policy_data["config"]["invoices_url"] = info.invoices_url
                        policy_data["config"]["credits_url"] = info.credits_url

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
