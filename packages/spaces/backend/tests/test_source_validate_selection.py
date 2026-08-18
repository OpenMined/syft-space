"""Tests for ``validate_selection`` — the pick validity check at create/add.

Restores the guarantee lost when watched paths moved out of the configuration:
a pick that no longer exists (typo, or removed between browse and confirm) must
be rejected instead of silently ingesting nothing. Existence only — an empty
directory is a valid pick, since content may be added later.
"""

from __future__ import annotations

import pytest

from syft_space.components.sources.local_file.local_file_source import (
    LocalFileProvider,
)
from syft_space.components.sources.noop_source import NoOpProvider
from syft_space.components.sources.wordpress.wordpress_source import WordPressProvider


class TestLocalFileValidateSelection:
    async def test_existing_file_passes(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("hi")
        await LocalFileProvider.validate_selection([str(f)])  # no raise

    async def test_existing_dir_passes(self, tmp_path):
        await LocalFileProvider.validate_selection([str(tmp_path)])  # no raise

    async def test_empty_dir_is_valid(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        # Empty is fine — content may be added later.
        await LocalFileProvider.validate_selection([str(empty)])

    async def test_empty_selection_passes(self):
        await LocalFileProvider.validate_selection([])  # no raise

    async def test_missing_path_raises(self, tmp_path):
        missing = str(tmp_path / "nope.txt")
        with pytest.raises(ValueError) as exc:
            await LocalFileProvider.validate_selection([missing])
        assert missing in str(exc.value)

    async def test_reports_only_the_missing_paths(self, tmp_path):
        present = tmp_path / "here.txt"
        present.write_text("x")
        missing = str(tmp_path / "gone.txt")

        with pytest.raises(ValueError) as exc:
            await LocalFileProvider.validate_selection([str(present), missing])

        msg = str(exc.value)
        assert missing in msg
        assert str(present) not in msg


class TestNoOpAndWordPressValidateSelection:
    async def test_noop_accepts_anything(self):
        await NoOpProvider.validate_selection(["whatever", "/not/real"])  # no raise

    async def test_wordpress_accepts_anything(self):
        await WordPressProvider.validate_selection(["post:1", "post:999"])  # no raise
