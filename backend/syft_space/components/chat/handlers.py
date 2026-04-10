"""Local chat handler for testing models and data sources."""

from uuid import UUID

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
            HTTPException: If model/dataset not found or query fails
        """
        references: ReferencesResponse | None = None
        summary: SummaryResponse | None = None

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

        ctx = SearchContext(sender="local-chat", dataset_id=dataset.id)
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
                status_code=500,
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

        ctx = ChatContext(sender="local-chat", model_id=model.id)
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
