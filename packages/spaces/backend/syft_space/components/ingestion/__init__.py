"""Ingestion component for watch-based file ingestion.

This component provides:
- File system watching for datasets with IngestableDatasetType
- Per-file ingestion job tracking
- Background worker for processing pending jobs
- API endpoints for ingestion status and control
"""

from syft_space.components.ingestion.entities import IngestionJob, IngestionJobStatus
from syft_space.components.ingestion.handlers import IngestionHandler
from syft_space.components.ingestion.manager import IngestionManager
from syft_space.components.ingestion.repository import IngestionJobRepository
from syft_space.components.ingestion.routes import build_ingestion_routes

__all__ = [
    "IngestionJob",
    "IngestionJobStatus",
    "IngestionJobRepository",
    "IngestionManager",
    "IngestionHandler",
    "build_ingestion_routes",
]
