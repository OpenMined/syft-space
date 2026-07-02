"""Tests for the selection cutover: picks → change_stream(selected_ids).

Covers the three testable units of the uniform-pick model:
- ``selection_covers`` (provider-owned pick↔item id-space matching),
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

# ============== selection_covers (provider-owned id-space matching) ==============


class TestSelectionCovers:
    def test_local_file_self_and_under_directory(self):
        covers = LocalFileProvider.selection_covers
        assert covers("/a/b", "/a/b") is True
        assert covers("/a/b", "/a/b/c.txt") is True
        assert covers("/a/b", "/a/b/x/y.txt") is True
        assert covers("/a/b", "/a/bc.txt") is False  # common prefix, not under

    def test_wordpress_exact_id(self):
        assert WordPressProvider.selection_covers("post:1", "post:1") is True
        assert WordPressProvider.selection_covers("post:1", "post:11") is False

    def test_noop_never_covers(self):
        assert NoOpProvider.selection_covers("x", "x") is False


# ============== LocalFileSource._enumerate_paths (expansion) ==============


def _local_source(exts=(".txt",)):
    return LocalFileProvider.for_ingest({"allowedExtensions": list(exts)})


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
