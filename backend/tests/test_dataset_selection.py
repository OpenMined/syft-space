"""Tests for the normalized dataset selection layer (Phase 1).

Covers the ``DatasetSelectionRepository`` CRUD/dedup behavior and the pure
backfill-parsing helpers in the Alembic migration (the risky dual-shape logic
that reads both local_file dict entries and WordPress string entries).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

from syft_space.components.datasets.selection_repository import (
    DatasetSelectionRepository,
)
from syft_space.components.shared.database import AsyncDatabase

# ============== Repository ==============


class TestDatasetSelectionRepository:
    """DatasetSelectionRepository add / remove / list / dedup."""

    async def test_add_returns_true_then_false_on_duplicate(
        self, main_db: AsyncDatabase
    ):
        repo = DatasetSelectionRepository(main_db)
        ds = uuid4()

        assert await repo.add(ds, "~/docs/a.txt", "first") is True
        # Same (dataset_id, item_id) is a no-op dedup, reported as not-added.
        assert await repo.add(ds, "~/docs/a.txt", "second") is False

        rows = await repo.list_for_dataset(ds)
        assert len(rows) == 1
        # The duplicate did not overwrite the original description.
        assert rows[0].description == "first"

    async def test_list_is_scoped_per_dataset(self, main_db: AsyncDatabase):
        repo = DatasetSelectionRepository(main_db)
        ds1, ds2 = uuid4(), uuid4()

        await repo.add(ds1, "post:1")
        await repo.add(ds1, "post:2")
        await repo.add(ds2, "post:3")

        assert {r.item_id for r in await repo.list_for_dataset(ds1)} == {
            "post:1",
            "post:2",
        }
        assert {r.item_id for r in await repo.list_for_dataset(ds2)} == {"post:3"}

    async def test_same_item_id_allowed_across_datasets(self, main_db: AsyncDatabase):
        repo = DatasetSelectionRepository(main_db)
        ds1, ds2 = uuid4(), uuid4()

        # The UNIQUE constraint is (dataset_id, item_id) — same item in two
        # datasets is allowed.
        assert await repo.add(ds1, "shared:1") is True
        assert await repo.add(ds2, "shared:1") is True

    async def test_remove(self, main_db: AsyncDatabase):
        repo = DatasetSelectionRepository(main_db)
        ds = uuid4()
        await repo.add(ds, "x")

        assert await repo.remove(ds, "x") is True
        assert await repo.list_for_dataset(ds) == []
        # Removing a missing item is a no-op, reported as not-removed.
        assert await repo.remove(ds, "x") is False

    async def test_description_optional(self, main_db: AsyncDatabase):
        repo = DatasetSelectionRepository(main_db)
        ds = uuid4()
        await repo.add(ds, "wordpress:42")  # no description

        rows = await repo.list_for_dataset(ds)
        assert rows[0].description is None


# ============== Migration backfill parsing ==============


def _load_migration_module():
    """Import the migration module by path (versions dir is not a package)."""
    path = (
        Path(__file__).resolve().parent.parent
        / "syft_space"
        / "alembic"
        / "versions"
        / "f1a2b3c4d5e6_add_dataset_selection_table.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_dataset_selection", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigrationBackfillParsing:
    """The dual-shape selection parsing used by the migration backfill."""

    def setup_method(self):
        self.mig = _load_migration_module()

    def test_local_file_dict_entries(self):
        cfg = {
            "collectionName": "Docs",
            "filePaths": [
                {"path": "~/a.txt", "description": "notes"},
                {"path": "~/dir", "description": None},
            ],
        }
        items = list(self.mig._iter_selection_items("local_file", cfg))
        assert items == [("~/a.txt", "notes"), ("~/dir", None)]

    def test_wordpress_string_entries(self):
        cfg = {"siteUrl": "https://x", "selectedItems": ["post:1", "page:9"]}
        items = list(self.mig._iter_selection_items("wordpress", cfg))
        assert items == [("post:1", None), ("page:9", None)]

    def test_unknown_dtype_yields_nothing(self):
        cfg = {"filePaths": [{"path": "~/a.txt"}]}
        assert list(self.mig._iter_selection_items("weaviate", cfg)) == []

    def test_missing_or_empty_key_yields_nothing(self):
        assert list(self.mig._iter_selection_items("local_file", {})) == []
        assert (
            list(self.mig._iter_selection_items("local_file", {"filePaths": None}))
            == []
        )

    def test_entries_without_path_are_skipped(self):
        cfg = {"filePaths": [{"description": "orphan"}, {"path": "~/ok"}]}
        items = list(self.mig._iter_selection_items("local_file", cfg))
        assert items == [("~/ok", None)]

    def test_load_config_handles_text_dict_and_junk(self):
        assert self.mig._load_config('{"a": 1}') == {"a": 1}
        assert self.mig._load_config({"a": 1}) == {"a": 1}
        assert self.mig._load_config(None) == {}
        assert self.mig._load_config("not json") == {}
