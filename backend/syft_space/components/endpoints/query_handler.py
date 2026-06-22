"""Query endpoint handler — RAG pipeline with policy enforcement."""

from typing import Any

from fastapi import HTTPException
from loguru import logger

from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.endpoints.entities import Endpoint, ResponseType
from syft_space.components.endpoints.interfaces import (
    QueryEventReporter,
    QueryOutcome,
    QueryOutcomeEvent,
)
from syft_space.components.endpoints.policy_charging import build_payment_chargers
from syft_space.components.endpoints.repository import EndpointRepository
from syft_space.components.endpoints.schemas import (
    AuthenticatedQueryRequest,
    DocumentResponse,
    MessageResponse,
    ProviderInfo,
    QueryEndpointResponse,
    ReferencesResponse,
    SummaryResponse,
    TokenUsage,
)
from syft_space.components.marketplaces.repository import MarketplaceRepository
from syft_space.components.model_types.interfaces import (
    ChatContext,
    ChatMessage,
    ChatParameters,
)
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.payments.gateway.balance_service import BalanceService
from syft_space.components.policies.repository import PolicyRepository
from syft_space.components.policy_types.interfaces import (
    PaymentRequiredError,
    PolicyContext,
    PolicyMetadata,
    PolicyViolationError,
    QueryRejectedError,
    Recipient,
)
from syft_space.components.policy_types.registry import PolicyTypeRegistry
from syft_space.components.shared.search_types import SearchContext, SearchParameters
from syft_space.components.tenants.entities import Tenant
from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.repository import WalletRepository


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
        balance_service: BalanceService | None = None,
        event_reporter: QueryEventReporter | None = None,
        marketplace_repository: MarketplaceRepository | None = None,
    ):
        self.endpoint_repository = endpoint_repository
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.policy_repository = policy_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry
        self.policy_registry = policy_registry
        self.wallet_repository = wallet_repository
        self.balance_service = balance_service
        self.event_reporter = event_reporter
        self.marketplace_repository = marketplace_repository

    async def query_endpoint(
        self,
        slug: str,
        request: AuthenticatedQueryRequest,
        tenant: Tenant,
        x_payment: str | None = None,
    ) -> QueryEndpointResponse:
        """Query an endpoint - main RAG flow.

        Returns:
            The query response, including `policy_metadata` describing what
            each policy charged, to whom, and the rail-native transaction id.

        Raises:
            HTTPException: If endpoint not found or query fails
            QueryRejectedError: If a policy blocked the query (payment/access/
                rate-limit); the route renders it as 402/403 with metadata.
        """
        endpoint: Endpoint | None = None
        outcome: QueryOutcome = QueryOutcome.SUCCESS
        final_response: QueryEndpointResponse | None = None

        try:
            endpoint = await self.endpoint_repository.get_by_slug(slug, tenant.id)
            if not endpoint:
                outcome = QueryOutcome.NOT_FOUND
                raise HTTPException(
                    status_code=404, detail=f"Endpoint '{slug}' not found"
                )

            # Check if published
            if not endpoint.published:
                outcome = QueryOutcome.NOT_PUBLISHED
                raise HTTPException(status_code=403, detail="Endpoint is not published")

            # Get policies grouped by type and extract configurations
            policies_by_type = await self.policy_repository.get_by_endpoint_id_grouped(
                endpoint.id, tenant.id
            )
            configs_by_type: dict[str, list[dict]] = {
                policy_type: [p.configuration for p in policies]
                for policy_type, policies in policies_by_type.items()
            }

            # An endpoint has at most one wallet (CapabilityChecker rejects
            # siblings pointing elsewhere), so grab the first wallet_id we
            # find across policies and fetch it.
            wallet_id = next(
                (
                    p.wallet_id
                    for policies in policies_by_type.values()
                    for p in policies
                    if p.wallet_id
                ),
                None,
            )
            wallet: Wallet | None = None
            if wallet_id and self.wallet_repository:
                wallet = await self.wallet_repository.get_by_id(wallet_id, tenant.id)

            # Build typed payment chargers bag from the attached wallet;
            # policies access chargers via context.payment_chargers.{mpp,xendit}().
            payment_chargers = build_payment_chargers(
                wallet=wallet,
                balance_service=self.balance_service,
                tenant_id=tenant.id,
                endpoint_id=endpoint.id,
                endpoint_slug=slug,
                x_payment=x_payment,
            )

            # Resolve the recipient ("to whom") once, only when a wallet is
            # attached. Recipient is read solely by payment-policy metadata,
            # and payment policies require a wallet, so non-paid endpoints skip
            # the marketplace lookup entirely (no DB hit on the free hot path).
            recipient = (
                await self._resolve_recipient(tenant, wallet)
                if wallet is not None
                else None
            )

            # Create policy context with verified sender email
            policy_context = PolicyContext(
                endpoint_slug=slug,
                sender_email=request.sender_email,
                request=request.model_dump(),
                payment_chargers=payment_chargers,
                recipient=recipient,
            )

            # Apply pre-hooks per type (one instance per type, all configs passed).
            # PolicyViolationError (403) / PaymentRequiredError (402) raised from
            # anywhere in this body are converted once in the outer handler.
            for policy_type_name, configs in configs_by_type.items():
                policy_type_cls = self.policy_registry.get_policy_type(policy_type_name)
                policy_instance = policy_type_cls()
                policy_context = await policy_instance.pre_hook(configs, policy_context)

            # Execute query based on response_type
            references: ReferencesResponse | None = None
            summary: SummaryResponse | None = None

            response_type = ResponseType(endpoint.response_type)

            # Search dataset if needed
            if (
                response_type in [ResponseType.RAW, ResponseType.BOTH]
                and endpoint.dataset_id
            ):
                # Pass the query through unchanged for retrieval. The
                # aggregator-wrapper stripping is an analytics concern.
                if isinstance(request.messages, str):
                    search_query = request.messages
                else:
                    search_query = next(
                        (
                            m.content
                            for m in reversed(request.messages)
                            if m.role == "user" and m.content
                        ),
                        "",
                    )
                references = await self._search_dataset(endpoint, request, search_query)

            # Chat with model if needed
            if (
                response_type in [ResponseType.SUMMARY, ResponseType.BOTH]
                and endpoint.model_id
            ):
                summary, _model_instance, _model_id = await self._chat_with_model(
                    endpoint, request, references
                )
                if "pii_filter" in configs_by_type:
                    policy_context.metadata["model_instance"] = _model_instance
                    policy_context.metadata["model_id"] = _model_id

            # Create response
            query_response = QueryEndpointResponse(
                summary=summary, references=references
            )

            # Update policy context with response
            policy_context.response = query_response.model_dump()

            # Apply post-hooks per type
            for policy_type_name, configs in configs_by_type.items():
                policy_type_cls = self.policy_registry.get_policy_type(policy_type_name)
                policy_instance = policy_type_cls()
                policy_context = await policy_instance.post_hook(
                    configs, policy_context
                )

            # Attach the success policy_metadata envelope onto the response.
            response_dict = policy_context.response or {}
            response_dict["policy_metadata"] = PolicyMetadata(
                outcome=QueryOutcome.SUCCESS.value,
                entries=policy_context.policy_metadata,
            ).model_dump()

            final_response = QueryEndpointResponse.model_validate(response_dict)
            return final_response

        except PolicyViolationError as e:
            # A policy blocked the request from any point in the pipeline.
            outcome = self._safe_outcome(e.outcome)
            raise self._reject_violation(e) from e
        except PaymentRequiredError as e:
            outcome = QueryOutcome.PAYMENT_REQUIRED
            raise self._reject_payment(e) from e
        except HTTPException:
            if outcome == QueryOutcome.SUCCESS:
                outcome = QueryOutcome.INTERNAL_ERROR
            raise
        except Exception:
            outcome = QueryOutcome.INTERNAL_ERROR
            raise
        finally:
            if self.event_reporter:
                # Extract IDs here so the adapter never touches a possibly-detached ORM instance.
                try:
                    await self.event_reporter(
                        QueryOutcomeEvent(
                            tenant_id=tenant.id,
                            user_email=str(request.sender_email),
                            endpoint_slug=slug,
                            endpoint_id=endpoint.id if endpoint else None,
                            dataset_id=endpoint.dataset_id if endpoint else None,
                            outcome=outcome,
                            messages=request.messages,
                            response=(
                                final_response
                                if outcome == QueryOutcome.SUCCESS
                                else None
                            ),
                        )
                    )
                except Exception:
                    # Reporter runs in `finally`; raising here would mask the user-facing exception.
                    logger.exception("event_reporter failed; continuing")

    async def _resolve_recipient(
        self, tenant: Tenant, wallet: Wallet | None
    ) -> Recipient | None:
        """Resolve the endpoint owner (the 'to whom') plus MPP wallet address.

        Identity comes from the space's default marketplace; the public wallet
        address is added for MPP wallets only (never a private key).
        """
        username: str | None = None
        email: str | None = None
        if self.marketplace_repository:
            marketplace = await self.marketplace_repository.get_default(tenant.id)
            if marketplace:
                username = marketplace.username or None
                email = marketplace.email or None

        wallet_address: str | None = None
        if wallet and wallet.wallet_type == "mpp":
            wallet_address = wallet.configuration.get("wallet_address") or None

        if not (username or email or wallet_address):
            return None
        return Recipient(username=username, email=email, wallet_address=wallet_address)

    @staticmethod
    def _safe_outcome(outcome: str) -> QueryOutcome:
        """Map a policy's outcome string to a QueryOutcome, never raising.

        A policy may supply any string; an unrecognized value falls back to
        POLICY_VIOLATION so a deliberate rejection is never masked as a 500.
        """
        try:
            return QueryOutcome(outcome)
        except ValueError:
            return QueryOutcome.POLICY_VIOLATION

    def _reject_violation(self, e: PolicyViolationError) -> QueryRejectedError:
        """Build a 403 rejection carrying the policy_metadata envelope."""
        entry = e.metadata_entry
        return QueryRejectedError(
            status_code=403,
            detail=f"Policy '{e.policy_type}' blocked request: {e.details}",
            policy_metadata=PolicyMetadata(
                outcome=e.outcome,
                entries=[entry] if entry else [],
            ),
        )

    def _reject_payment(self, e: PaymentRequiredError) -> QueryRejectedError:
        """Build a 402 rejection carrying the policy_metadata envelope."""
        entry = e.metadata_entry
        return QueryRejectedError(
            status_code=402,
            detail=e.description or "Payment required",
            policy_metadata=PolicyMetadata(
                outcome=QueryOutcome.PAYMENT_REQUIRED.value,
                entries=[entry] if entry else [],
            ),
            headers={"WWW-Authenticate": e.www_authenticate},
        )

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
        )

    async def _chat_with_model(
        self,
        endpoint: Endpoint,
        request: AuthenticatedQueryRequest,
        references: ReferencesResponse | None,
    ) -> tuple[SummaryResponse, Any, str]:
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

        summary = SummaryResponse(
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
            provider_info=ProviderInfo(api_version="v1"),
        )
        return summary, model_instance, str(model.id)
