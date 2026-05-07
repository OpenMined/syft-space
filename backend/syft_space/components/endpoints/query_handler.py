"""Query endpoint handler — RAG pipeline with policy enforcement."""

import asyncio
import re
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from loguru import logger

from syft_space.components.analytics.entities import QueryEventStatus

from syft_space.components.dataset_types.interfaces import (
    SearchContext,
    SearchParameters,
)
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint, ResponseType
from syft_space.components.endpoints.interfaces import MetadataEnricher
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    ChatMessageRequest,
    DocumentResponse,
    MessageResponse,
    ProviderInfo,
    QueryEndpointResponse,
    ReferencesResponse,
    SummaryResponse,
    TokenUsage,
)
from syft_space.components.model_types.interfaces import (
    ChatContext,
    ChatMessage,
    ChatParameters,
)
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policy_types.interfaces import (
    PaymentRequiredError,
    PolicyContext,
    PolicyViolationError,
)
from syft_space.components.policy_types.registry import PolicyTypeRegistry
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.repository import WalletRepository

if TYPE_CHECKING:
    from syft_space.components.analytics.collector import QueryEventCollector


# SyftHub's aggregator wraps every forwarded query in a prompt-builder
# template. All four template variants (NO_CONTEXT, EMPTY_CONTEXT,
# DEFAULT, CITATION) put the actual question between
# `USER QUESTION:\n` and a trailing `\n---` marker. We peel that out so
# analytics captures only what the user typed, not the prompt scaffolding.
_AGGREGATOR_QUESTION_RE = re.compile(
    r"USER QUESTION:\s*\n(?P<q>.*?)\n---",
    re.DOTALL,
)


def _strip_aggregator_wrapper(content: str) -> str:
    """If `content` is a SyftHub-aggregator-wrapped payload, return just
    the question. Otherwise return content unchanged.
    """
    match = _AGGREGATOR_QUESTION_RE.search(content)
    if match:
        return match.group("q").strip()
    return content.strip()


def _extract_user_query(messages: str | list[ChatMessageRequest]) -> str:
    """Extract the user's actual query from a request payload.

    Returns the last user-role message content (or the raw string if
    `messages` is a string), with SyftHub-aggregator scaffolding peeled
    off. System prompts, assistant turns, and earlier user turns are
    discarded — the analytics layer treats *this* request as a single
    question, and earlier turns were captured as their own events when
    they originally fired.
    """
    if isinstance(messages, str):
        return _strip_aggregator_wrapper(messages)
    if isinstance(messages, list):
        for m in reversed(messages):
            if m.role == "user" and m.content:
                return _strip_aggregator_wrapper(m.content)
    return ""


class QueryEndpointHandler:
    """Handler for the endpoint query pipeline (RAG + policy enforcement)."""

    def __init__(
        self,
        endpoint_repository: EndpointRepository,
        dataset_repository: DatasetRepository,
        model_repository: ModelRepository,
        policy_repository: PolicyRepository,
        dataset_registry: DatasetTypeRegistry,
        model_registry: ModelTypeRegistry,
        policy_registry: PolicyTypeRegistry,
        wallet_repository: WalletRepository | None = None,
        metadata_enricher: MetadataEnricher | None = None,
        event_collector: "QueryEventCollector | None" = None,
    ):
        self.endpoint_repository = endpoint_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.policy_repository = policy_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.policy_registry = policy_registry
        self.wallet_repository = wallet_repository
        self.metadata_enricher = metadata_enricher
        self.event_collector = event_collector

    async def query_endpoint(
        self,
        slug: str,
        request: AuthenticatedQueryRequest,
        tenant: Tenant,
        x_payment: str | None = None,
    ) -> tuple[QueryEndpointResponse, str | None]:
        """Query an endpoint - main RAG flow.

        Returns:
            Tuple of (query response, payment_receipt_header or None)

        Raises:
            HTTPException: If endpoint not found or query fails
            PaymentRequiredError: If MPP payment is required (caller returns 402)
        """
        # Extract the user's actual query (last user-role message) for
        # analytics. System prompts and assistant turns are excluded so they
        # don't pollute the word cloud. Capped to bound DB row size and the
        # downstream NLP pass on the wordcloud handler.
        user_query = _extract_user_query(request.messages)
        event_data: dict[str, Any] = {
            "tenant_id": tenant.id,
            "user_email": request.sender_email,
            "endpoint_slug": slug,
            "endpoint_id": None,
            "dataset_id": None,
            "revenue_amount": 0.0,
            "currency": "USD",
            "status": QueryEventStatus.SUCCESS.value,
            "query_text": user_query[:4000],
        }

        try:
            endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
            if not endpoint:
                event_data["status"] = QueryEventStatus.NOT_FOUND.value
                raise HTTPException(
                    status_code=404, detail=f"Endpoint '{slug}' not found"
                )

            event_data["endpoint_id"] = endpoint.id
            event_data["dataset_id"] = endpoint.dataset_id

            # Check if published
            if not endpoint.published:
                event_data["status"] = QueryEventStatus.NOT_PUBLISHED.value
                raise HTTPException(status_code=403, detail="Endpoint is not published")

            # Get policies grouped by type and extract configurations
            policies_by_type = await self.policy_repository.get_by_endpoint_id_grouped(
                endpoint.id, tenant.id
            )
            configs_by_type: dict[str, list[dict]] = {
                policy_type: [p.configuration for p in policies]
                for policy_type, policies in policies_by_type.items()
            }

            # Build policy context metadata
            metadata: dict = {
                "endpoint_id": endpoint.id,
                "tenant_id": tenant.id,
            }

            # Enrich metadata with cross-component services (e.g., balance_service)
            if self.metadata_enricher:
                await self.metadata_enricher(metadata)

            # Load wallets referenced by payment policies (single batch query)
            wallet_ids = list(
                {
                    p.wallet_id
                    for policies in policies_by_type.values()
                    for p in policies
                    if p.wallet_id
                }
            )
            if wallet_ids and self.wallet_repository:
                wallets = await self.wallet_repository.get_by_ids(wallet_ids, tenant.id)
                metadata["wallets"] = {w.wallet_type: w.configuration for w in wallets}
                # Surface wallet identity per type for prepaid policies (they need
                # the wallet_id + currency to record balance movements).
                for w in wallets:
                    metadata[f"{w.wallet_type}_wallet_id"] = w.id
                    metadata[f"{w.wallet_type}_wallet_currency"] = w.currency

            # Inject X-Payment credential for MPP accounting policy
            if x_payment:
                metadata["x_payment"] = x_payment

            # Create policy context with verified sender email
            policy_context = PolicyContext(
                endpoint_slug=slug,
                sender_email=request.sender_email,
                request=request.model_dump(),
                metadata=metadata,
            )

            # Apply pre-hooks per type (one instance per type, all configs passed)
            # Note: PaymentRequiredError is intentionally NOT caught here -
            # it propagates to the route handler which returns HTTP 402.
            for policy_type_name, configs in configs_by_type.items():
                try:
                    policy_type_cls = self.policy_registry.get_policy_type(
                        policy_type_name
                    )
                    policy_instance = policy_type_cls()
                    policy_context = await policy_instance.pre_hook(
                        configs, policy_context
                    )
                except PolicyViolationError as e:
                    event_data["status"] = QueryEventStatus.POLICY_VIOLATION.value
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
                references = await self._search_dataset(endpoint, request, user_query)

            # Chat with model if needed
            if (
                response_type in [ResponseType.SUMMARY, ResponseType.BOTH]
                and endpoint.model_id
            ):
                summary = await self._chat_with_model(endpoint, request, references)

            # Create response
            query_response = QueryEndpointResponse(
                summary=summary, references=references
            )

            # Update policy context with response
            policy_context.response = query_response.model_dump()

            # Apply post-hooks per type
            for policy_type_name, configs in configs_by_type.items():
                try:
                    policy_type_cls = self.policy_registry.get_policy_type(
                        policy_type_name
                    )
                    policy_instance = policy_type_cls()
                    policy_context = await policy_instance.post_hook(
                        configs, policy_context
                    )
                except PolicyViolationError as e:
                    event_data["status"] = QueryEventStatus.POLICY_VIOLATION.value
                    raise HTTPException(
                        status_code=403,
                        detail=f"Policy '{e.policy_type}' blocked request: {e.details}",
                    ) from e

            # Extract payment receipt header if present (set by MppAccountingPolicy post-hook)
            payment_receipt = policy_context.metadata.get("payment_receipt_header")

            # Capture recognized revenue for analytics. Each accounting policy
            # publishes its outcome to context.metadata; xendit clears its keys
            # in post_hook on a refund, so what we read here is post-cancel.
            # Xendit is preferred because it carries the wallet's real currency;
            # MPP falls back to USD by convention. The two are mutually exclusive
            # in practice — only one accounting policy fires per query.
            xendit_amount = policy_context.metadata.get("xendit_revenue_amount", 0.0)
            xendit_currency = policy_context.metadata.get("xendit_revenue_currency")
            if xendit_amount and xendit_currency:
                event_data["revenue_amount"] = float(xendit_amount)
                event_data["currency"] = str(xendit_currency)
            else:
                mpp_amount = policy_context.metadata.get("mpp_total_amount", 0.0)
                if mpp_amount:
                    event_data["revenue_amount"] = float(mpp_amount)
                    event_data["currency"] = "USD"

            return (
                QueryEndpointResponse.model_validate(policy_context.response),
                payment_receipt,
            )

        except PaymentRequiredError:
            event_data["status"] = QueryEventStatus.PAYMENT_REQUIRED.value
            raise
        except HTTPException:
            if event_data["status"] == QueryEventStatus.SUCCESS.value:
                event_data["status"] = QueryEventStatus.INTERNAL_ERROR.value
            raise
        except Exception:
            event_data["status"] = QueryEventStatus.INTERNAL_ERROR.value
            raise
        finally:
            if self.event_collector:
                asyncio.create_task(self.event_collector.capture(**event_data))

    async def _search_dataset(
        self,
        endpoint: Endpoint,
        request: AuthenticatedQueryRequest,
        query: str,
    ) -> ReferencesResponse:
        """Search the dataset linked to this endpoint."""
        dataset = await self.dataset_repository.get_by_id(
            endpoint.dataset_id, endpoint.tenant_id
        )
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        try:
            dataset_type_cls = self.dataset_registry.get_dataset_type(dataset.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Dataset type '{dataset.dtype}' not registered"
            ) from None

        dataset_instance = dataset_type_cls(dataset.configuration)

        ctx = SearchContext(sender=request.sender_email, dataset_id=dataset.id)
        search_params = SearchParameters(
            similarity_threshold=request.similarity_threshold,
            limit=request.limit,
            include_metadata=request.include_metadata,
        )

        try:
            search_result = await dataset_instance.search(ctx, query, search_params)
        except Exception as e:
            logger.exception(f"Dataset search failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Dataset search failed: {str(e)}"
            ) from e

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
            cost=0.0,
        )

    async def _chat_with_model(
        self,
        endpoint: Endpoint,
        request: AuthenticatedQueryRequest,
        references: ReferencesResponse | None,
    ) -> SummaryResponse:
        """Chat with the model linked to this endpoint."""
        model = await self.model_repository.get_by_id(
            endpoint.model_id, endpoint.tenant_id
        )
        if not model:
            logger.error(
                f"Model not found: model_id={endpoint.model_id}, "
                f"tenant_id={endpoint.tenant_id}"
            )
            raise HTTPException(status_code=500, detail="Model not found")

        try:
            model_type_cls = self.model_registry.get_model_type(model.dtype)
        except KeyError:
            logger.exception(f"Model type '{model.dtype}' not registered")
            raise HTTPException(
                status_code=500, detail=f"Model type '{model.dtype}' not registered"
            ) from None

        model_instance = model_type_cls(model.configuration)

        if isinstance(request.messages, str):
            messages = [ChatMessage(role="user", content=request.messages)]
        else:
            messages = [
                ChatMessage(role=m.role, content=m.content) for m in request.messages
            ]

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

        ctx = ChatContext(sender=request.sender_email, model_id=model.id)
        chat_params = ChatParameters(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
        )

        try:
            chat_result = await model_instance.chat(ctx, messages, chat_params)
        except Exception as e:
            logger.exception(f"Model chat failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Model chat failed: {str(e)}"
            ) from e

        last_message = chat_result.messages[-1] if chat_result.messages else None
        if not last_message:
            logger.error(
                "Model returned no messages: "
                f"model_id={endpoint.model_id}, "
                f"chat_result_id={chat_result.id}"
            )
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
            cost=0.0,
            provider_info=ProviderInfo(api_version="v1"),
        )
