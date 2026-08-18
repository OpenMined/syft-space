"""Image catalog API schemas."""

from datetime import datetime

from pydantic import BaseModel


class ImageTagResponse(BaseModel):
    """One available syft-space image tag."""

    tag: str
    created: datetime
    revision: str | None
    is_latest: bool
