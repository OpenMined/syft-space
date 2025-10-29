from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from .handlers import DatasetHandler
from .schemas import DatasetType


def build_dataset_routes(handler: DatasetHandler) -> APIRouter:
    """Build the dataset routes."""
    router = APIRouter(prefix="/datasets")

    def get_handler() -> DatasetHandler:
        """Get the dataset handler."""
        return handler

    @router.get("/types/list")
    async def list_dataset_types(
        handler: DatasetHandler = Depends(get_handler),
    ) -> List[DatasetType]:
        """List all dataset types."""
        return handler.list_dataset_types()

    @router.get("/types/{name}")
    async def get_dataset_type(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> DatasetType:
        """Get the dataset type for the given name."""
        return handler.get_dataset_type(name)

    @router.get("/types/{name}/schema")
    async def get_dataset_type_schema(
        name: str,
        handler: DatasetHandler = Depends(get_handler),
    ) -> Dict[str, Any]:
        """Get the configuration schema for the given dataset type name."""
        return handler.get_dataset_type_schema(name)

    return router
