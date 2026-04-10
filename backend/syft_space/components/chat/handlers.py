"""Local chat handler for testing models and data sources."""

import asyncio
from uuid import UUID

import httpx
from fastapi import HTTPException
from loguru import logger

from syft_space.components.chat.schemas import (
    DocumentResponse,
    LocalChatRequest,
    LocalChatResponse,
    MessageResponse,
    ReferencesResponse,
    SummaryResponse,
    TokenUsage,
)
from syft_space.components.dataset_types.interfaces import (
    SearchContext,
    SearchParameters,
)
from syft_space.components.dataset_types.registry import DatasetTypeRegistry
from syft_space.components.datasets.repository import DatasetRepository
from syft_space.components.model_types.interfaces import (
    ChatContext,
    ChatMessage,
    ChatParameters,
)
from syft_space.components.model_types.registry import ModelTypeRegistry
from syft_space.components.models.repository import ModelRepository
from syft_space.components.tenants.entities import Tenant
from syft_space.config import app_settings

# Network-level errors that indicate an upstream failure (bad gateway, 502).
# asyncio.TimeoutError is handled separately as a 504.
_UPSTREAM_ERRORS: tuple[type[BaseException], ...] = (
    httpx.HTTPError,
    ConnectionError,
)

# Synthetic sender used for local-chat model/dataset contexts. Local chat has
# no authenticated SyftBox identity, so we inject a placeholder email that
# satisfies the EmailStr validator on Context.
_LOCAL_CHAT_SENDER = "local-chat@syft-space.example.com"


class LocalChatHandler:
    """Handler for local chat — direct model + data source testing."""

    def __init__(
        self,
        dataset_repository: DatasetRepository,
        model_repository: ModelRepository,
        dataset_registry: DatasetTypeRegistry,
        model_registry: ModelTypeRegistry,
    ):
        self.dataset_repository = dataset_repository
        self.model_repository = model_repository
        self.dataset_registry = dataset_registry
        self.model_registry = model_registry

    async def chat(
        self, request: LocalChatRequest, tenant: Tenant
    ) -> LocalChatResponse:
        """Run a local chat query against a model, optionally with data source context.

        Args:
            request: Chat request with model_id, optional dataset_id, and messages
            tenant: Tenant context

        Returns:
            Response with model summary and optional search references

        Raises:
            HTTPException: Classified error:
                - 400 if required model/dataset type is not registered
                - 404 if the model or dataset does not exist in the tenant
                - 502 if an upstream model/dataset call fails with a network error
                - 504 if the upstream call exceeds ``chat_timeout_seconds``
                - 500 on unexpected failures
        """
        references: ReferencesResponse | None = None

        if request.dataset_id:
            references = await self._search_dataset(request.dataset_id, request, tenant)

        summary = await self._chat_with_model(
            request.model_id, request, references, tenant
        )

        return LocalChatResponse(summary=summary, references=references)

    async def _search_dataset(
        self,
        dataset_id: UUID,
        request: LocalChatRequest,
        tenant: Tenant,
    ) -> ReferencesResponse:
        dataset = await self.dataset_repository.get_by_id(dataset_id, tenant.id)
        if not dataset:
            raise HTTPException(
                status_code=404, detail=f"Dataset '{dataset_id}' not found"
            )

        try:
            dataset_type_cls = self.dataset_registry.get_dataset_type(dataset.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset type '{dataset.dtype}' not registered",
            ) from None

        dataset_instance = dataset_type_cls(dataset.configuration)

        user_messages = [m for m in request.messages if m.role == "user"]
        query = user_messages[-1].content if user_messages else ""

        ctx = SearchContext(sender=_LOCAL_CHAT_SENDER, dataset_id=dataset.id)
        search_params = SearchParameters(
            similarity_threshold=request.similarity_threshold,
            limit=request.limit,
            include_metadata=request.include_metadata,
        )

        timeout = app_settings.chat_timeout_seconds
        try:
            search_result = await asyncio.wait_for(
                dataset_instance.search(ctx, query, search_params),
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            logger.warning(
                f"Dataset search timed out after {timeout}s: dataset_id={dataset_id}"
            )
            raise HTTPException(
                status_code=504, detail="Dataset search timed out"
            ) from e
        except _UPSTREAM_ERRORS as e:
            logger.warning(f"Dataset search upstream error: {e}")
            raise HTTPException(
                status_code=502, detail=f"Dataset upstream error: {e}"
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Dataset search failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Dataset search failed: {e}"
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

        return ReferencesResponse(documents=documents, search_engine=dataset.dtype)

    async def _chat_with_model(
        self,
        model_id: UUID,
        request: LocalChatRequest,
        references: ReferencesResponse | None,
        tenant: Tenant,
    ) -> SummaryResponse:
        model = await self.model_repository.get_by_id(model_id, tenant.id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

        try:
            model_type_cls = self.model_registry.get_model_type(model.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Model type '{model.dtype}' not registered",
            ) from None

        model_instance = model_type_cls(model.configuration)

        messages = [
            ChatMessage(role=m.role, content=m.content) for m in request.messages
        ]

        if references and references.documents:
            context_content = "\n\n".join(
                f"[{doc.document_id}] {doc.content}" for doc in references.documents[:3]
            )
            context_message = ChatMessage(
                role="system",
                content=f"Use the following context to answer:\n{context_content}",
            )
            messages.insert(0, context_message)

        ctx = ChatContext(sender=_LOCAL_CHAT_SENDER, model_id=model.id)
        chat_params = ChatParameters(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
        )

        timeout = app_settings.chat_timeout_seconds
        try:
            chat_result = await asyncio.wait_for(
                model_instance.chat(ctx, messages, chat_params),
                timeout=timeout,
            )
        except asyncio.TimeoutError as e:
            logger.warning(
                f"Model chat timed out after {timeout}s: model_id={model_id}"
            )
            raise HTTPException(status_code=504, detail="Chat request timed out") from e
        except _UPSTREAM_ERRORS as e:
            logger.warning(f"Model chat upstream error: {e}")
            raise HTTPException(
                status_code=502, detail=f"Model upstream error: {e}"
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Model chat failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Model chat failed: {e}"
            ) from e

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
        )
