"""Model handlers for business logic."""

from fastapi import HTTPException

from components.model_types.registry import ModelTypeRegistry

from .entities import Model
from .repository import ModelRepository
from .schemas import (
    CreateModelRequest,
    ModelListItem,
    ModelResponse,
    ModelTypeInfoResponse,
)


class ModelHandler:
    """Handler for model business logic."""

    def __init__(self, registry: ModelTypeRegistry, repository: ModelRepository):
        """Initialize the model handler.

        Args:
            registry: Model type registry
            repository: Model repository
        """
        self.registry = registry
        self.repository = repository

    def list_model_types(self) -> list[ModelTypeInfoResponse]:
        """List all available model types.

        Returns:
            List of model type information
        """
        type_names = self.registry.list_model_types()
        types_info = []

        for name in type_names:
            model_type_cls = self.registry.get_model_type(name)
            types_info.append(
                ModelTypeInfoResponse(
                    name=model_type_cls.name(),
                    description=model_type_cls.description(),
                    config_schema=model_type_cls.configuration_schema(),
                    icon=model_type_cls.icon(),
                    enabled=model_type_cls.enabled(),
                )
            )

        return types_info

    def get_model_type(self, name: str) -> ModelTypeInfoResponse:
        """Get information about a specific model type.

        Args:
            name: Model type name

        Returns:
            Model type information

        Raises:
            HTTPException: If model type not found
        """
        try:
            model_type_cls = self.registry.get_model_type(name)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"Model type '{name}' not found"
            ) from None

        return ModelTypeInfoResponse(
            name=model_type_cls.name(),
            description=model_type_cls.description(),
            config_schema=model_type_cls.configuration_schema(),
            icon=model_type_cls.icon(),
            enabled=model_type_cls.enabled(),
        )

    def create_model(self, request: CreateModelRequest) -> ModelResponse:
        """Create a new model.

        Args:
            request: Model creation request

        Returns:
            Created model

        Raises:
            HTTPException: If model type not found or name already exists
        """
        # Verify model type exists
        try:
            self.registry.get_model_type(request.dtype)
        except KeyError:
            raise HTTPException(
                status_code=400, detail=f"Model type '{request.dtype}' not found"
            ) from None

        # Check if name already exists
        existing = self.repository.get_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=409, detail=f"Model '{request.name}' already exists"
            )

        # Create model entity
        model = Model(
            name=request.name,
            dtype=request.dtype,
            configuration=request.configuration,
            summary=request.summary,
            tags=request.tags,
        )

        # Save to database
        created = self.repository.create(model)

        return ModelResponse.model_validate(created)

    def list_models(self) -> list[ModelListItem]:
        """List all models.

        Returns:
            List of models
        """
        models = self.repository.get_all()
        return [ModelListItem.model_validate(m) for m in models]

    def get_model(self, name: str) -> ModelResponse:
        """Get a specific model by name.

        Args:
            name: Model name

        Returns:
            Model details

        Raises:
            HTTPException: If model not found
        """
        model = self.repository.get_by_name(name)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model '{name}' not found")

        return ModelResponse.model_validate(model)

    def delete_model(self, name: str) -> dict:
        """Delete a model by name.

        Args:
            name: Model name

        Returns:
            Success message

        Raises:
            HTTPException: If model not found
        """
        deleted = self.repository.delete_by_name(name)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Model '{name}' not found")

        return {"message": f"Successfully deleted model '{name}'"}
