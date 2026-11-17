"""Feature flags: /settings/features follows AppSettings."""

from unittest.mock import MagicMock

import pytest

from syft_space.components.settings.handlers import SettingsHandler
from syft_space.config import AppSettings, app_settings


@pytest.fixture
def handler() -> SettingsHandler:
    return SettingsHandler(
        settings_repository=MagicMock(),
        marketplace_repository=MagicMock(),
        proxy_service=None,
    )


def test_benchmark_off_by_default(monkeypatch):
    monkeypatch.delenv("SYFT_BENCHMARK_ENABLED", raising=False)

    assert AppSettings(_env_file=None).benchmark_enabled is False


def test_benchmark_enabled_from_env(monkeypatch):
    monkeypatch.setenv("SYFT_BENCHMARK_ENABLED", "true")

    assert AppSettings(_env_file=None).benchmark_enabled is True


@pytest.mark.parametrize("enabled", [False, True])
def test_features_report_benchmark_flag(handler, monkeypatch, enabled):
    monkeypatch.setattr(app_settings, "benchmark_enabled", enabled)

    assert handler.get_features().benchmark is enabled
