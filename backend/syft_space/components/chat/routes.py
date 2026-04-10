"""Local chat API routes."""

from fastapi import APIRouter, Depends

from syft_space.components.chat.handlers import LocalChatHandler
from syft_space.components.chat.schemas import LocalChatRequest, LocalChatResponse
from syft_space.components.tenants.dependency import get_tenant_dependency
from syft_space.components.tenants.entities import Tenant


def build_chat_routes(handler: LocalChatHandler) -> APIRouter:
    """Build the local chat routes.

    Args:
        handler: Local chat handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/chat", tags=["chat"])

    def get_handler() -> LocalChatHandler:
        return handler

    @router.post("/", response_model=LocalChatResponse)
    async def local_chat(
        request: LocalChatRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: LocalChatHandler = Depends(get_handler),
    ) -> LocalChatResponse:
        """Local chat — test a model with an optional data source.

        Sends messages to a local model, optionally augmented with search
        results from a data source. No endpoint or SyftHub auth required.

        Args:
            request: Chat request with model_id, optional dataset_id, and messages
            tenant: Current tenant (injected)
            handler: Chat handler (injected)

        Returns:
            Chat response with model summary and optional references
        """
        return await handler.chat(request, tenant)

    return router
