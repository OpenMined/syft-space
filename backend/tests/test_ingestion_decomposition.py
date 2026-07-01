"""Tests locking the IngestionManager decomposition (Phase 2).

There was no prior ingestion test coverage, so these protect the contract the
decomposition introduced: the shared factory, the facade's delegation, and the
fact that startup binds the same coordination primitives into both the scanner
and the job processor. These target the stable seams (not the change_stream
internals that Phase 3 rewrites), so they survive the next phase.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from syft_space.components.datasets.entities import Dataset
from syft_space.components.ingestion.factory import DatasetTypeFactory
from syft_space.components.ingestion.manager import IngestionManager


def _binding_cls(source):
    """A dataset_type class whose instances expose ``.source``."""

    class _Binding:
        def __init__(self, configuration):
            self.source = source

    return _Binding


class _FakeRegistry:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_dataset_type(self, dtype):
        return self._mapping[dtype]  # KeyError for unknown, like the real one


def _dataset(dtype: str = "local_file") -> Dataset:
    return Dataset(name=f"ds-{dtype}", dtype=dtype, configuration={}, tenant_id=uuid4())


class _RealSource:
    pass


class _NoopSource:
    IS_NOOP = True


# ============== DatasetTypeFactory ==============


class TestDatasetTypeFactory:
    def test_has_source_true_for_real_source(self):
        factory = DatasetTypeFactory(
            _FakeRegistry({"local_file": _binding_cls(_RealSource())})
        )
        assert factory.has_source(_dataset()) is True

    def test_has_source_false_for_noop_source(self):
        factory = DatasetTypeFactory(
            _FakeRegistry({"local_file": _binding_cls(_NoopSource())})
        )
        assert factory.has_source(_dataset()) is False

    def test_has_source_false_when_binding_has_no_source(self):
        factory = DatasetTypeFactory(_FakeRegistry({"local_file": _binding_cls(None)}))
        assert factory.has_source(_dataset()) is False

    def test_has_source_false_on_build_failure(self):
        # Unknown dtype -> KeyError inside build -> swallowed as "no source".
        factory = DatasetTypeFactory(_FakeRegistry({}))
        assert factory.has_source(_dataset("weaviate")) is False


# ============== Facade delegation ==============


class _FakeIngestionRepo:
    def __init__(self, reset_return: int):
        self._reset_return = reset_return
        self.reset_failed_jobs = AsyncMock(return_value=reset_return)


class TestRetryFailedJobs:
    async def test_notifies_processor_when_jobs_reset(self):
        mgr = IngestionManager(
            dataset_repository=Mock(),
            ingestion_repository=_FakeIngestionRepo(3),
            registry=_FakeRegistry({}),
        )
        mgr._job_processor.notify = Mock()

        n = await mgr.retry_failed_jobs(uuid4(), uuid4())

        assert n == 3
        mgr._job_processor.notify.assert_called_once()

    async def test_no_notify_when_nothing_reset(self):
        mgr = IngestionManager(
            dataset_repository=Mock(),
            ingestion_repository=_FakeIngestionRepo(0),
            registry=_FakeRegistry({}),
        )
        mgr._job_processor.notify = Mock()

        n = await mgr.retry_failed_jobs(uuid4(), uuid4())

        assert n == 0
        mgr._job_processor.notify.assert_not_called()


# ============== Startup wiring ==============


class TestStartupBinding:
    async def test_startup_binds_same_primitives_to_both_collaborators(self):
        dataset_repo = Mock()
        dataset_repo.get_all_with_provisioner_state_id = AsyncMock(return_value=[])
        mgr = IngestionManager(
            dataset_repository=dataset_repo,
            ingestion_repository=Mock(),
            registry=_FakeRegistry({}),
        )

        await mgr.startup()
        try:
            # The scanner and job processor must share the exact same cache,
            # wake signal, and shutdown event owned by the facade.
            assert mgr._scanner._sources is mgr._sources
            assert mgr._job_processor._sources is mgr._sources
            assert mgr._scanner._job_signal is mgr._job_signal
            assert mgr._job_processor._job_signal is mgr._job_signal
            assert mgr._scanner._shutdown_event is mgr._shutdown_event
            assert mgr._job_processor._shutdown_event is mgr._shutdown_event
        finally:
            await mgr.shutdown()
