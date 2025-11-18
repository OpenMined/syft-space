"""Model API routes."""

from typing import Any

from fastapi import APIRouter, Depends

from syftai_space.components.models.handlers import ModelHandler
from syftai_space.components.models.schemas import (
    CreateModelRequest,
    ModelListItem,
    ModelResponse,
    ModelTypeInfoResponse,
)
from syftai_space.components.tenants.dependency import get_tenant_dependency
from syftai_space.components.tenants.entities import Tenant


def build_model_routes(handler: ModelHandler) -> APIRouter:
    """Build the model routes.

    Args:
        handler: Model handler instance

    Returns:
        Configured API router
    """
    router = APIRouter(prefix="/models", tags=["models"])

    def get_handler() -> ModelHandler:
        """Dependency to get the model handler."""
        return handler

    @router.get("/types/", response_model=list[ModelTypeInfoResponse])
    async def list_model_types(
        handler: ModelHandler = Depends(get_handler),
    ) -> list[ModelTypeInfoResponse]:
        """List all available model types.

        Returns:
            List of model type information including configuration schemas
        """
        return handler.list_model_types()

    @router.get("/types/{name}", response_model=ModelTypeInfoResponse)
    async def get_model_type(
        name: str,
        handler: ModelHandler = Depends(get_handler),
    ) -> ModelTypeInfoResponse:
        """Get information about a specific model type.

        Args:
            name: Model type name

        Returns:
            Model type information
        """
        return handler.get_model_type(name)

    @router.get("/types/{name}/schema", response_model=dict[str, Any])
    async def get_model_type_schema(
        name: str,
        handler: ModelHandler = Depends(get_handler),
    ) -> dict[str, Any]:
        """Get the configuration schema for a specific model type.

        Args:
            name: Model type name

        Returns:
            Configuration schema dictionary
        """
        type_info = handler.get_model_type(name)
        return type_info.config_schema

    @router.post("/", response_model=ModelResponse, status_code=201)
    async def create_model(
        request: CreateModelRequest,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: ModelHandler = Depends(get_handler),
    ) -> ModelResponse:
        """Create a new model.

        Args:
            request: Model creation request with configuration
            tenant: Current tenant (injected)

        Returns:
            Created model details
        """
        return handler.create_model(request, tenant)

    @router.get("/", response_model=list[ModelListItem])
    async def list_models(
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: ModelHandler = Depends(get_handler),
    ) -> list[ModelListItem]:
        """List all models.

        Args:
            tenant: Current tenant (injected)

        Returns:
            List of models with summary information
        """
        return handler.list_models(tenant)

    @router.get("/{name}", response_model=ModelResponse)
    async def get_model(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: ModelHandler = Depends(get_handler),
    ) -> ModelResponse:
        """Get details of a specific model.

        Args:
            name: Model name
            tenant: Current tenant (injected)

        Returns:
            Model details including configuration
        """
        return handler.get_model(name, tenant)

    @router.delete("/{name}", response_model=dict[str, str])
    async def delete_model(
        name: str,
        tenant: Tenant = Depends(get_tenant_dependency),
        handler: ModelHandler = Depends(get_handler),
    ) -> dict[str, str]:
        """Delete a model.

        Args:
            name: Model name
            tenant: Current tenant (injected)

        Returns:
            Success message
        """
        return handler.delete_model(name, tenant)

    return router
