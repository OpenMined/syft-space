from backend.components.data_sources.schemas import DataSourceInfo
from backend.components.data_sources.handlers import DataSourceHandler
from typing import List, Dict, Any
from fastapi import APIRouter, Depends


def build_data_source_routes(handler: DataSourceHandler) -> APIRouter:
    router = APIRouter(prefix="/data-sources")

    def get_handler() -> DataSourceHandler:
        """Get the data source handler."""
        return handler

    @router.get("/list")
    async def list_data_source_info(
        handler: DataSourceHandler = Depends(get_handler),
    ) -> List[DataSourceInfo]:
        """List all data source info."""
        return handler.list_data_source_info()

    @router.get("/{source_name}")
    async def get_data_source_info(
        source_name: str,
        handler: DataSourceHandler = Depends(get_handler),
    ) -> DataSourceInfo:
        """Get the data source info for the given source name."""
        return handler.get_data_source_info(source_name)

    @router.get("/{source_name}/schema")
    async def get_configuration_schema(
        source_name: str,
        handler: DataSourceHandler = Depends(get_handler),
    ) -> Dict[str, Any]:
        """Get the configuration schema for the given source name."""
        return handler.get_configuration_schema(source_name)

    return router
