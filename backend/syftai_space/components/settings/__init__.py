"""Settings component for public URL management."""

from syftai_space.components.settings.handlers import SettingsHandler
from syftai_space.components.settings.schemas import (
    PublicUrlResponse,
    UpdatePublicUrlRequest,
)

__all__ = [
    "SettingsHandler",
    "PublicUrlResponse",
    "UpdatePublicUrlRequest",
]
