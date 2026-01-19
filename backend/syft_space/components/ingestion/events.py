"""File event types for ingestion queue.

This module defines the data structures for file events that flow through
the janus queue between watchdog (sync) and the event processor (async).
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import UUID


class FileEventType(str, Enum):
    """Type of file event."""

    CREATED = "created"
    DELETED = "deleted"


@dataclass(frozen=True)
class FileEvent:
    """Immutable file event for queue transmission.

    This is the only interface between watchdog and IngestionManager.
    Complete decoupling - handler doesn't need to know about manager.

    Attributes:
        event_type: Type of file event (created/deleted)
        dataset_id: UUID of the dataset this file belongs to
        tenant_id: UUID of the tenant
        file_path: Path to the file
        file_size: Size of the file in bytes (only for CREATED events)
        file_mtime_ns: Modification time in nanoseconds (only for CREATED events)
    """

    event_type: FileEventType
    dataset_id: UUID
    tenant_id: UUID
    file_path: Path
    file_size: int | None = None
    file_mtime_ns: int | None = None
