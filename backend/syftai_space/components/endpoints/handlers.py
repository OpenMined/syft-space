"""Endpoint handlers for business logic."""

from typing import Optional

from fastapi import HTTPException

from syftai_space.components.dataset_types.interfaces import SearchParameters
from syftai_space.components.dataset_types.registry import DatasetTypeRegistry
from syftai_space.components.datasets.repository import DatasetRepository
from syftai_space.components.endpoints.entities import Endpoint, ResponseType
from syftai_space.components.endpoints.repository import EndpointRepository
from syftai_space.components.endpoints.schemas import (
    CreateEndpointRequest,
    DocumentResponse,
    EndpointListItem,
    EndpointResponse,
    MessageResponse,
    ProviderInfo,
    QueryEndpointRequest,
    QueryEndpointResponse,
    ReferencesResponse,
    SummaryResponse,
    TokenUsage,
)
from syftai_space.components.model_types.interfaces import ChatMessage, ChatParameters
from syftai_space.components.model_types.registry import ModelTypeRegistry
from syftai_space.components.models.repository import ModelRepository
from syftai_space.components.policies.repository import PolicyRepository
from syftai_space.components.policy_types.interfaces import PolicyContext
from syftai_space.components.policy_types.registry import PolicyTypeRegistry
from syftai_space.components.shared.domain_types import Context
from syftai_space.components.tenants.entities import Tenant


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
        """
        self.endpoint_repository = endpoint_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.policy_repository = policy_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.policy_registry = policy_registry

    def create_endpoint(
        self, request: CreateEndpointRequest, tenant: Tenant
    ) -> EndpointResponse:
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
        existing = self.endpoint_repository.get_by_slug(request.slug, tenant.id)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Endpoint slug '{request.slug}' already exists"
            )

        # Verify dataset exists if provided (within tenant)
        if request.dataset_id:
            dataset = self.dataset_repository.get_by_id(request.dataset_id, tenant.id)
            if not dataset:
                raise HTTPException(
                    status_code=404, detail=f"Dataset '{request.dataset_id}' not found"
                )

        # Verify model exists if provided (within tenant)
        if request.model_id:
            model = self.model_repository.get_by_id(request.model_id, tenant.id)
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
            visibility=request.visibility,
            published=request.published,
            tags=request.tags,
            tenant_id=tenant.id,  # Set tenant_id explicitly
        )

        # Save to database
        created = self.endpoint_repository.create(endpoint)

        return EndpointResponse.model_validate(created)

    def list_endpoints(self, tenant: Tenant) -> list[EndpointListItem]:
        """List all endpoints for a tenant.

        Args:
            tenant: Tenant context

        Returns:
            List of endpoints
        """
        endpoints = self.endpoint_repository.get_all(tenant.id)
        return [EndpointListItem.model_validate(ep) for ep in endpoints]

    def get_endpoint(self, slug: str, tenant: Tenant) -> EndpointResponse:
        """Get a specific endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant: Tenant context

        Returns:
            Endpoint details

        Raises:
            HTTPException: If endpoint not found
        """
        endpoint = self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return EndpointResponse.model_validate(endpoint)

    def delete_endpoint(self, slug: str, tenant: Tenant) -> dict:
        """Delete an endpoint by slug within a tenant.

        Args:
            slug: Endpoint slug
            tenant: Tenant context

        Returns:
            Success message

        Raises:
            HTTPException: If endpoint not found
        """
        deleted = self.endpoint_repository.delete_by_slug(slug, tenant.id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        return {"message": f"Successfully deleted endpoint '{slug}'"}

    def query_endpoint(
        self, slug: str, request: QueryEndpointRequest, tenant: Tenant
    ) -> QueryEndpointResponse:
        """Query an endpoint - main RAG flow.

        Args:
            slug: Endpoint slug
            request: Query request
            tenant: Tenant context

        Returns:
            Query response with summary and/or references

        Raises:
            HTTPException: If endpoint not found or query fails
        """
        # Get endpoint
        endpoint = self.endpoint_repository.get_by_slug(slug, tenant.id)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"Endpoint '{slug}' not found")

        # Check if published
        if not endpoint.published:
            raise HTTPException(status_code=403, detail="Endpoint is not published")

        # Check visibility (TODO: implement proper email pattern matching)
        if "*" not in endpoint.visibility:
            # For now, just check if user_email is in the list
            if request.user_email not in endpoint.visibility:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied - user not in visibility list",
                )

        # Get policies for this endpoint
        policies = self.policy_repository.get_by_endpoint_id(endpoint.id, tenant.id)

        # Create policy context
        policy_context = PolicyContext(
            endpoint_slug=slug,
            sender_email=request.user_email,
            request=request.model_dump(),
        )

        # Apply pre-hooks
        for policy in policies:
            try:
                policy_type_cls = self.policy_registry.get_policy_type(
                    policy.policy_type
                )
                policy_instance = policy_type_cls(policy.configuration)
                policy_context = policy_instance.pre_hook(policy_context)
            except Exception as e:
                raise HTTPException(
                    status_code=403,
                    detail=f"Policy '{policy.name}' pre-hook failed: {str(e)}",
                ) from e

        # Execute query based on response_type
        references: Optional[ReferencesResponse] = None
        summary: Optional[SummaryResponse] = None

        response_type = ResponseType(endpoint.response_type)

        # Search dataset if needed
        if (
            response_type in [ResponseType.RAW, ResponseType.BOTH]
            and endpoint.dataset_id
        ):
            references = self._search_dataset(endpoint, request)

        # Chat with model if needed
        if (
            response_type in [ResponseType.SUMMARY, ResponseType.BOTH]
            and endpoint.model_id
        ):
            summary = self._chat_with_model(endpoint, request, references)

        # Create response
        query_response = QueryEndpointResponse(summary=summary, references=references)

        # Update policy context with response
        policy_context.response = query_response.model_dump()

        # Apply post-hooks
        for policy in policies:
            try:
                policy_type_cls = self.policy_registry.get_policy_type(
                    policy.policy_type
                )
                policy_instance = policy_type_cls(policy.configuration)
                policy_context = policy_instance.post_hook(policy_context)
            except Exception as e:
                # Post-hooks failures are logged but don't block response
                print(f"Policy '{policy.name}' post-hook failed: {str(e)}")

        return query_response

    def _search_dataset(
        self, endpoint: Endpoint, request: QueryEndpointRequest
    ) -> ReferencesResponse:
        """Search the dataset.

        Args:
            endpoint: Endpoint entity
            request: Query request

        Returns:
            References response

        Raises:
            HTTPException: If search fails
        """
        # Get dataset (use endpoint's tenant_id for authorization)
        dataset = self.dataset_repository.get_by_id(
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

        # Search
        ctx = Context(sender=request.user_email)
        search_params = SearchParameters(
            similarity_threshold=request.similarity_threshold,
            limit=request.limit,
            include_metadata=request.include_metadata,
        )

        try:
            search_result = dataset_instance.search(ctx, query, search_params)
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

    def _chat_with_model(
        self,
        endpoint: Endpoint,
        request: QueryEndpointRequest,
        references: Optional[ReferencesResponse],
    ) -> SummaryResponse:
        """Chat with the model.

        Args:
            endpoint: Endpoint entity
            request: Query request
            references: Optional search references to include in context

        Returns:
            Summary response

        Raises:
            HTTPException: If chat fails
        """
        # Get model (use endpoint's tenant_id for authorization)
        model = self.model_repository.get_by_id(endpoint.model_id, endpoint.tenant_id)
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

        # Chat
        ctx = Context(sender=request.user_email)
        chat_params = ChatParameters(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
        )

        try:
            chat_result = model_instance.chat(ctx, messages, chat_params)
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
