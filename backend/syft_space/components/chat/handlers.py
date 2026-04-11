"""Local chat handler for testing models and data sources."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
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


@asynccontextmanager
async def _classify_upstream_errors(
    operation: str, identifier: object
) -> AsyncIterator[None]:
    """Translate upstream/timeout/unknown errors into classified HTTPExceptions."""
    try:
        yield
    except asyncio.TimeoutError as e:
        logger.warning(f"{operation} timed out: id={identifier}")
        raise HTTPException(
            status_code=504, detail=f"{operation} timed out"
        ) from e
    except _UPSTREAM_ERRORS as e:
        logger.warning(f"{operation} upstream error: {e}")
        raise HTTPException(
            status_code=502, detail=f"{operation} upstream error: {e}"
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"{operation} failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"{operation} failed: {e}"
        ) from e


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
        """Run a local chat query against a model, optionally with data source context."""
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

        async with _classify_upstream_errors("Dataset search", dataset_id):
            search_result = await asyncio.wait_for(
                dataset_instance.search(ctx, query, search_params),
                timeout=app_settings.chat_timeout_seconds,
            )

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

        messages: list[ChatMessage] = []
        if request.system_prompt:
            messages.append(
                ChatMessage(role="system", content=request.system_prompt)
            )
        if references and references.documents:
            context_content = "\n\n".join(
                f"[{doc.document_id}] {doc.content}" for doc in references.documents[:3]
            )
            messages.append(
                ChatMessage(
                    role="system",
                    content=f"Use the following context to answer:\n{context_content}",
                )
            )
        messages.extend(
            ChatMessage(role=m.role, content=m.content) for m in request.messages
        )

        ctx = ChatContext(sender=_LOCAL_CHAT_SENDER, model_id=model.id)
        chat_params = ChatParameters(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences,
            presence_penalty=request.presence_penalty,
            frequency_penalty=request.frequency_penalty,
        )

        async with _classify_upstream_errors("Model chat", model_id):
            chat_result = await asyncio.wait_for(
                model_instance.chat(ctx, messages, chat_params),
                timeout=app_settings.chat_timeout_seconds,
            )

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
