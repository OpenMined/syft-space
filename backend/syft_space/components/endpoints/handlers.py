"""Endpoint handlers for business logic."""

from uuid import UUID

from fastapi import HTTPException

from syft_space.components.dataset_types.interfaces import SearchParameters
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint, ResponseType
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    CreateEndpointRequest,
    DocumentResponse,
    EndpointCreateResponse,
    EndpointDetailResponse,
    EndpointListItem,
    MarketplaceAvailabilityResult,
    MessageResponse,
    ProviderInfo,
    PublishEndpointResponse,
    PublishResult,
    QueryEndpointResponse,
    ReferencesResponse,
    SlugAvailabilityResponse,
    SummaryResponse,
    TokenUsage,
    UpdateEndpointRequest,
)
from syft_space.components.marketplaces.entities import Marketplace
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.marketplaces.utils import ensure_valid_accounting_credentials
from syft_space.components.model_types.interfaces import ChatMessage, ChatParameters
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policy_types.interfaces import (
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.policy_types.registry import PolicyTypeRegistry
from syft_space.components.shared.domain_types import Context
from syft_space.components.shared.syfthub_client import SyftHubClient, SyftHubError
from syft_space.components.tenants.entities import Tenant


class EndpointHandler:
    """Handler for endpoint business logic."""

    def __init__(
        self,
        endpoint_repository: EndpointRepository,
        dataset_repository: DatasetRepository,
        model_repository: ModelRepository,
        policy_repository: PolicyRepository,
        dataset_registry: DatasetTypeRegistry,
        model_registry: ModelTypeRegistry,
        policy_registry: PolicyTypeRegistry,
        marketplace_repository: MarketplaceRepository | None = None,
    ):
        """Initialize the endpoint handler.

        Args:
            endpoint_repository: Endpoint repository
            dataset_repository: Dataset repository
            model_repository: Model repository
            policy_repository: Policy repository
            dataset_registry: Dataset type registry
            model_registry: Model type registry
            policy_registry: Policy type registry
            marketplace_repository: Marketplace repository (optional, for publish and accounting)
        """
        self.endpoint_repository = endpoint_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.policy_repository = policy_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.policy_registry = policy_registry
        self.marketplace_repository = marketplace_repository

    async def create_endpoint(
        self, request: CreateEndpointRequest, tenant: Tenant
    ) -> EndpointCreateResponse:
        """Create a new endpoint.

        Args:
            request: Endpoint creation request
            tenant: Tenant context

        Returns:
            Created endpoint

        Raises:
            HTTPException: If validation fails
        """
        # Validate at least one of dataset_id or model_id is provided
        if request.dataset_id is None and request.model_id is None:
            raise HTTPException(
                status_code=400,
                detail="At least one of dataset_id or model_id must be provided",
            )

        # Check if slug already exists within tenant
        existing = await self.endpoint_repository.get_by_slug(request.slug, tenant.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Endpoint slug '{request.slug}' already exists"
            )

        # Verify dataset exists if provided (within tenant)
        if request.dataset_id:
            dataset = await self.dataset_repository.get_by_id(
                request.dataset_id, tenant.id
            )
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{request.dataset_id}' not found"
                )

        # Verify model exists if provided (within tenant)
        if request.model_id:
            model = await self.model_repository.get_by_id(request.model_id, tenant.id)
            if not model:
                raise HTTPException(
                    status_code=404, detail=f"Model '{request.model_id}' not found"
                )

        # Create endpoint entity
        endpoint = Endpoint(
            name=request.name,
            slug=request.slug,
            description=request.description,
            summary=request.summary,
            dataset_id=request.dataset_id,
            model_id=request.model_id,
            response_type=request.response_type,
            published=request.published,
            tags=request.tags,
            tenant_id=tenant.id,  # Set tenant_id explicitly
        )

        # Save to database
        created = await self.endpoint_repository.create(endpoint)

        return EndpointCreateResponse.model_validate(created)

    async def list_endpoints(self, tenant: Tenant) -> list[EndpointListItem]:
        """List all endpoints for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of endpoints
        """
        endpoints = await self.endpoint_repository.get_all(tenant.id)
        return [EndpointListItem.model_validate(ep) for ep in endpoints]

    async def get_endpoint(self, slug: str, tenant: Tenant) -> EndpointDetailResponse:
        """Get a specific endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant: Tenant context

        Returns:
            Endpoint details

        Raises:
            HTTPException: If endpoint not found
        """
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return EndpointDetailResponse.model_validate(endpoint)

    async def update_endpoint(
        self, slug: str, request: UpdateEndpointRequest, tenant: Tenant
    ) -> EndpointDetailResponse:
        """Update an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            request: Update request with fields to update
            tenant: Tenant context

        Returns:
            Updated endpoint details

        Raises:
            HTTPException: If endpoint not found
        """
        updated_endpoint = await self.endpoint_repository.update_by_slug(
            slug,
            tenant.id,
            name=request.name,
            summary=request.summary,
            description=request.description,
        )
        if not updated_endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return EndpointDetailResponse.model_validate(updated_endpoint)

    async def delete_endpoint(self, slug: str, tenant: Tenant) -> dict:
        """Delete an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If endpoint not found
        """
        deleted = await self.endpoint_repository.delete_by_slug(slug, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return {"message": f"Successfully deleted endpoint '{slug}'"}

    async def query_endpoint(
        self,
        slug: str,
        request: AuthenticatedQueryRequest,
        tenant: Tenant,
    ) -> QueryEndpointResponse:
        """Query an endpoint - main RAG flow.

        Args:
            slug: Endpoint slug
            request: Authenticated query request (includes verified sender_email)
            tenant: Tenant context

        Returns:
            Query response with summary and/or references

        Raises:
            HTTPException: If endpoint not found or query fails
        """
        # Get endpoint
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        # Check if published
        if not endpoint.published:
            raise HTTPException(status_code=403, detail="Endpoint is not published")

        # Build policy context metadata with validated accounting credentials
        metadata: dict = {}
        if self.marketplace_repository:
            try:
                default_marketplace = await self.marketplace_repository.get_default(
                    tenant.id
                )
                if default_marketplace:
                    # Validate credentials upfront (refreshes from SyftHub if expired)
                    creds = await ensure_valid_accounting_credentials(
                        default_marketplace, self.marketplace_repository
                    )
                    # Inject validated accounting credentials
                    metadata["accounting_email"] = creds["email"]
                    metadata["accounting_password"] = creds["password"]
                    metadata["accounting_url"] = creds["url"]
            except HTTPException:
                # No marketplace configured or credentials invalid - accounting policies will fail
                pass

        # Get policies grouped by type and extract configurations
        policies_by_type = await self.policy_repository.get_by_endpoint_id_grouped(
            endpoint.id, tenant.id
        )
        configs_by_type: dict[str, list[dict]] = {
            policy_type: [p.configuration for p in policies]
            for policy_type, policies in policies_by_type.items()
        }

        # Create policy context with verified sender email
        policy_context = PolicyContext(
            endpoint_slug=slug,
            sender_email=request.sender_email,
            request=request.model_dump(),
            metadata=metadata,
        )

        # Apply pre-hooks per type (one instance per type, all configs passed)
        for policy_type_name, configs in configs_by_type.items():
            try:
                policy_type_cls = self.policy_registry.get_policy_type(policy_type_name)
                policy_instance = policy_type_cls()
                # Run pre-hook asynchronously
                policy_context = await policy_instance.pre_hook(configs, policy_context)
            except PolicyViolationError as e:
                raise HTTPException(
                    status_code=403,
                    detail=f"Policy '{e.policy_type}' blocked request: {e.details}",
                ) from e

        # Execute query based on response_type
        references: ReferencesResponse | None = None
        summary: SummaryResponse | None = None

        response_type = ResponseType(endpoint.response_type)

        # Search dataset if needed
        if (
            response_type in [ResponseType.RAW, ResponseType.BOTH]
            and endpoint.dataset_id
        ):
            references = await self._search_dataset(endpoint, request)

        # Chat with model if needed
        if (
            response_type in [ResponseType.SUMMARY, ResponseType.BOTH]
            and endpoint.model_id
        ):
            summary = await self._chat_with_model(endpoint, request, references)

        # Create response
        query_response = QueryEndpointResponse(summary=summary, references=references)

        # Update policy context with response
        policy_context.response = query_response.model_dump()

        # Apply post-hooks per type (also block on failure for data integrity)
        for policy_type_name, configs in configs_by_type.items():
            try:
                policy_type_cls = self.policy_registry.get_policy_type(policy_type_name)
                policy_instance = policy_type_cls()
                # Run post-hook asynchronously
                policy_context = await policy_instance.post_hook(
                    configs, policy_context
                )
            except PolicyViolationError as e:
                raise HTTPException(
                    status_code=403,
                    detail=f"Policy '{e.policy_type}' blocked request: {e.details}",
                ) from e

        return QueryEndpointResponse.model_validate(policy_context.response)

    async def _search_dataset(
        self, endpoint: Endpoint, request: AuthenticatedQueryRequest
    ) -> ReferencesResponse:
        """Search the dataset.

        Args:
            endpoint: Endpoint entity
            request: Authenticated query request

        Returns:
            References response

        Raises:
            HTTPException: If search fails
        """
        # Get dataset (use endpoint's tenant_id for authorization)
        dataset = await self.dataset_repository.get_by_id(
            endpoint.dataset_id, endpoint.tenant_id
        )
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Get dataset type
        try:
            dataset_type_cls = self.dataset_registry.get_dataset_type(dataset.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Dataset type '{dataset.dtype}' not registered"
            ) from None

        # Create dataset instance
        dataset_instance = dataset_type_cls(dataset.configuration)

        # Prepare query
        if isinstance(request.messages, str):
            query = request.messages
        else:
            # Use last user message as query
            user_messages = [m for m in request.messages if m.role == "user"]
            query = user_messages[-1].content if user_messages else ""

        # Search with verified sender email
        ctx = Context(sender=request.sender_email)
        search_params = SearchParameters(
            similarity_threshold=request.similarity_threshold,
            limit=request.limit,
            include_metadata=request.include_metadata,
        )

        try:
            search_result = await dataset_instance.search(ctx, query, search_params)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Dataset search failed: {str(e)}"
            ) from e

        # Convert to response format
        documents = [
            DocumentResponse(
                document_id=doc.document_id,
                content=doc.content,
                metadata=doc.metadata,
                similarity_score=doc.similarity_score,
            )
            for doc in search_result.documents
        ]

        return ReferencesResponse(
            documents=documents,
            provider_info=ProviderInfo(search_engine=dataset.dtype),
            cost=0.0,  # TODO: Implement cost tracking
        )

    async def _chat_with_model(
        self,
        endpoint: Endpoint,
        request: AuthenticatedQueryRequest,
        references: ReferencesResponse | None,
    ) -> SummaryResponse:
        """Chat with the model.

        Args:
            endpoint: Endpoint entity
            request: Authenticated query request
            references: Optional search references to include in context

        Returns:
            Summary response

        Raises:
            HTTPException: If chat fails
        """
        # Get model (use endpoint's tenant_id for authorization)
        model = await self.model_repository.get_by_id(
            endpoint.model_id, endpoint.tenant_id
        )
        if not model:
            raise HTTPException(status_code=500, detail="Model not found")

        # Get model type
        try:
            model_type_cls = self.model_registry.get_model_type(model.dtype)
        except KeyError:
            raise HTTPException(
                status_code=500, detail=f"Model type '{model.dtype}' not registered"
            ) from None

        # Create model instance
        model_instance = model_type_cls(model.configuration)

        # Prepare messages
        if isinstance(request.messages, str):
            messages = [ChatMessage(role="user", content=request.messages)]
        else:
            messages = [
                ChatMessage(role=m.role, content=m.content) for m in request.messages
            ]

        # Add references to context if available
        if references and references.documents:
            context_content = "\\n\\n".join(
                [
                    f"[{doc.document_id}] {doc.content}"
                    for doc in references.documents[:3]
                ]
            )
            context_message = ChatMessage(
                role="system",
                content=f"Use the following context to answer:\\n{context_content}",
            )
            messages.insert(0, context_message)

        # Chat with verified sender email
        ctx = Context(sender=request.sender_email)
        chat_params = ChatParameters(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
        )

        try:
            # Chat with the model
            chat_result = await model_instance.chat(ctx, messages, chat_params)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Model chat failed: {str(e)}"
            ) from e

        # Convert to response format
        # For simplicity, take the last message
        last_message = chat_result.messages[-1] if chat_result.messages else None
        if not last_message:
            raise HTTPException(status_code=500, detail="Model returned no messages")

        return SummaryResponse(
            id=chat_result.id,
            model=chat_result.model,
            message=MessageResponse(
                role=last_message.role,
                content=last_message.content,
                tokens=last_message.tokens,
            ),
            finish_reason=chat_result.finish_reason,
            usage=TokenUsage(
                prompt_tokens=chat_result.usage.prompt_tokens,
                completion_tokens=chat_result.usage.completion_tokens,
                total_tokens=chat_result.usage.total_tokens,
            ),
            cost=0.0,  # TODO: Implement cost tracking
            provider_info=ProviderInfo(api_version="v1"),
        )

    async def publish_endpoint(
        self,
        slug: str,
        marketplace_ids: list[UUID] | None,
        publish_to_all_marketplaces: bool,
        tenant: Tenant,
    ) -> PublishEndpointResponse:
        """Publish an endpoint to one or more marketplaces.

        Args:
            slug: Endpoint slug
            marketplace_ids: List of marketplace IDs to publish to (required if publish_to_all_marketplaces is False)
            publish_to_all_marketplaces: If True, publish to all active marketplaces (takes precedence)
            tenant: Tenant context

        Returns:
            Publish results for each marketplace

        Raises:
            HTTPException: If endpoint not found or marketplace repository not configured
        """
        if not self.marketplace_repository:
            raise HTTPException(
                status_code=500,
                detail="Marketplace publishing is not configured",
            )

        # Validate that either marketplace_ids or publish_to_all_marketplaces is provided
        if not publish_to_all_marketplaces and not marketplace_ids:
            raise HTTPException(
                status_code=400,
                detail="Either marketplace_ids or publish_to_all_marketplaces must be provided",
            )

        # Get endpoint
        endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        # Get marketplaces to publish to
        if publish_to_all_marketplaces:
            # Get all active marketplaces (flag takes precedence)
            marketplaces = await self.marketplace_repository.get_active(tenant.id)
            if not marketplaces:
                raise HTTPException(
                    status_code=400,
                    detail="No active marketplaces found",
                )
        else:
            # Get specific marketplaces by IDs
            marketplaces = await self.marketplace_repository.get_by_ids(
                marketplace_ids, tenant.id
            )
            found_ids = {m.id for m in marketplaces}

            # Check for missing marketplaces
            missing_ids = set(marketplace_ids) - found_ids
            if missing_ids:
                raise HTTPException(
                    status_code=404,
                    detail=f"Marketplaces not found: {[str(id) for id in missing_ids]}",
                )

        # Publish to each marketplace
        results: list[PublishResult] = []
        for marketplace in marketplaces:
            result = await self._publish_to_marketplace(endpoint, marketplace)
            results.append(result)

        return PublishEndpointResponse(
            endpoint_slug=slug,
            results=results,
        )

    async def _publish_to_marketplace(
        self,
        endpoint: Endpoint,
        marketplace: Marketplace,
    ) -> PublishResult:
        """Publish endpoint info to a marketplace using SDK.

        Args:
            endpoint: Endpoint to publish
            marketplace: Target marketplace

        Returns:
            Publish result
        """
        # Validate marketplace is active
        if not marketplace.is_active:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace is not active",
            )

        # Validate marketplace has credentials
        if not marketplace.email or not marketplace.password:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error="Marketplace credentials not configured",
            )

        try:
            async with SyftHubClient(base_url=marketplace.url) as client:
                # Note: marketplace.email is used as username
                await client.login(
                    username=marketplace.email, password=marketplace.password
                )

                endpoint_type = (
                    "model" if endpoint.model_id is not None else "data_source"
                )
                policies = [
                    {
                        "type": policy.policy_type,
                        "version": "1.0",
                        "enabled": True,
                        "description": policy.name,
                        "config": policy.configuration,
                    }
                    for policy in endpoint.policies
                ]
                connection_config = {
                    "path": f"/api/v1/endpoints/{endpoint.slug}/query",
                }

                payload = {
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
                await client.publish_endpoint(payload, overwrite=True)

        except SyftHubError as e:
            return PublishResult(
                marketplace_id=marketplace.id,
                marketplace_name=marketplace.name,
                success=False,
                error=e.message,
            )

        try:
            # Record the publication in endpoint's published_to list
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

    async def check_slug_availability(
        self,
        slug: str,
        marketplace_ids: list[UUID] | None,
        check_all_marketplaces: bool,
        tenant: Tenant,
    ) -> SlugAvailabilityResponse:
        """Check if a slug is available locally and optionally on marketplaces.

        Args:
            slug: Slug to check
            marketplace_ids: Optional list of marketplace IDs to check
            check_all_marketplaces: If True, check all active marketplaces (takes precedence)
            tenant: Tenant context

        Returns:
            Availability status for local and each requested marketplace
        """
        # Check local availability
        existing_endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
        local_available = existing_endpoint is None

        # Determine if we need to check marketplaces
        should_check_marketplaces = check_all_marketplaces or marketplace_ids

        # If no marketplace check needed, return local-only result
        if not should_check_marketplaces:
            return SlugAvailabilityResponse(
                slug=slug,
                local_available=local_available,
                marketplaces=None,
            )

        # Check marketplace availability
        if not self.marketplace_repository:
            raise HTTPException(
                status_code=500,
                detail="Marketplace checking is not configured",
            )

        # Get marketplaces to check
        if check_all_marketplaces:
            # Get all active marketplaces (flag takes precedence)
            marketplaces = await self.marketplace_repository.get_active(tenant.id)
            missing_ids: set[UUID] = set()
        else:
            # Get specific marketplaces by IDs
            marketplaces = await self.marketplace_repository.get_by_ids(
                marketplace_ids, tenant.id
            )
            found_ids = {m.id for m in marketplaces}
            missing_ids = set(marketplace_ids) - found_ids

        # Build results for each requested marketplace
        marketplace_results: list[MarketplaceAvailabilityResult] = []

        # Add results for missing marketplaces (only when using marketplace_ids)
        for missing_id in missing_ids:
            marketplace_results.append(
                MarketplaceAvailabilityResult(
                    marketplace_id=missing_id,
                    available=None,
                    error="Marketplace not found",
                )
            )

        # Check each found marketplace
        for marketplace in marketplaces:
            result = await self._check_marketplace_availability(slug, marketplace)
            marketplace_results.append(result)

        return SlugAvailabilityResponse(
            slug=slug,
            local_available=local_available,
            marketplaces=marketplace_results,
        )

    async def _check_marketplace_availability(
        self,
        slug: str,
        marketplace: Marketplace,
    ) -> MarketplaceAvailabilityResult:
        """Check if a slug is available on a specific marketplace.

        Args:
            slug: Slug to check
            marketplace: Marketplace to check on

        Returns:
            Availability result for the marketplace
        """
        # Validate marketplace is active
        if not marketplace.is_active:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id,
                available=None,
                error="Marketplace is not active",
            )

        # Validate marketplace has credentials
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
                    marketplace_id=marketplace.id,
                    available=not exists,
                    error=None,
                )
        except SyftHubError as e:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id,
                available=None,
                error=e.message,
            )
        except Exception as e:
            return MarketplaceAvailabilityResult(
                marketplace_id=marketplace.id,
                available=None,
                error=str(e),
            )
