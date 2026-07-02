"""Tests for the Phase 3 cutover: picks → change_stream(selected_ids).

Covers the three testable units of the uniform-pick cutover:
- ``extract_selected_items`` (create-path: provider-owned, no dtype knowledge
  in generic code),
- ``LocalFileSource._enumerate_paths`` (directory picks expand, file picks
  are emitted directly — classification is live and source-private),
- ``SourceScanner`` reads picks and passes their ids as-is to
  ``change_stream(selected_ids)``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.scanner import SourceScanner
from syft_space.components.sources.local_file.local_file_source import (
    LocalFileProvider,
)
from syft_space.components.sources.noop_source import NoOpProvider
from syft_space.components.sources.wordpress.wordpress_source import (
    WordPressProvider,
)

# ============== extract_selected_items (create path, provider-owned) ==============


class TestExtractSelectedItems:
    def test_local_file_paths_and_descriptions(self, tmp_path: Path):
        cfg = {
            "filePaths": [
                {"path": str(tmp_path), "description": "folder"},
                {"path": str(tmp_path / "a.txt"), "description": "file"},
            ]
        }
        assert LocalFileProvider.extract_selected_items(cfg) == [
            (str(tmp_path), "folder"),
            (str(tmp_path / "a.txt"), "file"),
        ]

    def test_wordpress_ids(self):
        cfg = {
            "siteUrl": "https://example.com",
            "username": "u",
            "applicationPassword": "p",
            "selectedItems": ["post:1", "page:9"],
        }
        assert WordPressProvider.extract_selected_items(cfg) == [
            ("post:1", None),
            ("page:9", None),
        ]

    def test_noop_has_no_selection(self):
        assert NoOpProvider.extract_selected_items({"anything": True}) == []


# ============== LocalFileSource._enumerate_paths (expansion) ==============


def _local_source(exts=(".txt",)):
    return LocalFileProvider.for_ingest(
        {"filePaths": [], "allowedExtensions": list(exts)}
    )


class TestEnumeratePaths:
    async def test_dir_expands_file_included_wrong_ext_skipped(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "skip.md").write_text("m")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("c")
        standalone = tmp_path / "note.txt"
        standalone.write_text("n")

        items = await _local_source()._enumerate_paths([str(tmp_path), str(standalone)])
        ids = {i.external_id for i in items}
        # directory pick (tmp_path) expands to a.txt + sub/c.txt; file pick
        # note.txt included; wrong-extension skip.md excluded.
        assert ids == {
            str(tmp_path / "a.txt"),
            str(sub / "c.txt"),
            str(standalone),
        }


# ============== SourceScanner → change_stream(selected_ids) ==============


class _RecordingSource:
    def __init__(self):
        self.calls: list[list[str]] = []

    def change_stream(self, selected_ids):
        self.calls.append(selected_ids)
        return self._empty()

    async def _empty(self):
        if False:  # pragma: no cover
            yield


class _Binding:
    def __init__(self, source):
        self.source = source


class _Factory:
    def __init__(self, binding):
        self._binding = binding

    def build(self, dataset):
        return self._binding


class _SelRepo:
    def __init__(self, picks):
        self._picks = picks

    async def list_for_dataset(self, dataset_id):
        return self._picks


class TestScannerPassesPicks:
    async def test_pick_ids_passed_as_is(self):
        source = _RecordingSource()
        picks = [
            SimpleNamespace(item_id="~/docs"),
            SimpleNamespace(item_id="~/pics"),
            SimpleNamespace(item_id="~/a.txt"),
        ]
        scanner = SourceScanner(
            dataset_repository=Mock(),
            ingestion_repository=Mock(
                get_completed_fingerprints=AsyncMock(return_value={})
            ),
            selection_repository=_SelRepo(picks),
            factory=_Factory(_Binding(source)),
        )
        dataset = Dataset(
            name="d", dtype="local_file", configuration={}, tenant_id=uuid4()
        )

        await scanner.start(dataset)
        # change_stream yields nothing, so the task completes promptly.
        await scanner._source_tasks[dataset.id]

        assert source.calls == [["~/docs", "~/pics", "~/a.txt"]]
