"""Helpers shared by the benchmark tests."""

from unittest.mock import AsyncMock


def make_settings_repo() -> AsyncMock:
    """A Space with no public address."""
    repo = AsyncMock()
    repo.get_public_url = AsyncMock(return_value="")
    return repo
