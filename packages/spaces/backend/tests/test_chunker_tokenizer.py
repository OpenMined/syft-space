"""Prose tokenizer loading: never authenticated, cache first, degrades to the
heuristic counter rather than failing ingestion.

The tokenizer tests stub docling's HF tokenizer module so they run with or
without docling installed. The two chunker tests need the real HybridChunker
and skip when it is absent.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import Any

import pytest

from syft_space.components.chunking import chunker as chunker_mod
from syft_space.components.chunking.chunker import (
    _build_hybrid_chunker,
    _build_prose_tokenizer,
    _heuristic_count_tokens,
)

_HF_TOKENIZER_MODULE = "docling_core.transforms.chunker.tokenizer.huggingface"


def _docling_installed() -> bool:
    try:
        return importlib.util.find_spec("docling_core") is not None
    except ModuleNotFoundError:
        return False


# Decided at import time: the `loader` fixture stubs docling into sys.modules,
# which would fool a pytest.importorskip inside a test body.
requires_docling = pytest.mark.skipif(
    not _docling_installed(), reason="docling is not installed"
)


class _FakeTokenizer:
    def get_max_tokens(self) -> int:
        return chunker_mod._PROSE_TOKENIZER_MAX_TOKENS

    def get_tokenizer(self):
        return None


class _StubLoader:
    """Stands in for docling's HuggingFaceTokenizer, recording every call.

    ``fails_when`` returns the exception to raise for a given call's kwargs, or
    None to succeed.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fails_when = lambda kwargs: None

    def from_pretrained(self, **kwargs: Any) -> _FakeTokenizer:
        self.calls.append(kwargs)
        exc = self.fails_when(kwargs)
        if exc is not None:
            raise exc
        return _FakeTokenizer()

    @property
    def local_flags(self) -> list[bool]:
        return [call["local_files_only"] for call in self.calls]


@pytest.fixture
def loader(monkeypatch) -> _StubLoader:
    stub = _StubLoader()
    module = types.ModuleType(_HF_TOKENIZER_MODULE)
    module.HuggingFaceTokenizer = stub  # type: ignore[attr-defined]

    if _docling_installed():
        # Swap just the class, so the real module keeps serving the rest of
        # docling (HybridChunker imports get_default_tokenizer from it).
        real = importlib.import_module(_HF_TOKENIZER_MODULE)
        monkeypatch.setattr(real, "HuggingFaceTokenizer", stub)
        return stub

    # Without docling, stand in for the module and its parent packages so the
    # `from ... import` inside _build_prose_tokenizer resolves.
    name = ""
    for part in _HF_TOKENIZER_MODULE.split(".")[:-1]:
        name = f"{name}.{part}" if name else part
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, _HF_TOKENIZER_MODULE, module)
    return stub


# ============== credentials and cache order ==============


def test_never_sends_a_credential(loader):
    _build_prose_tokenizer()

    assert loader.calls, "tokenizer loader was not called"
    assert all(call["token"] is False for call in loader.calls)


def test_tries_the_local_cache_first(loader):
    _build_prose_tokenizer()

    assert loader.local_flags[0] is True


def test_max_tokens_is_passed_so_docling_does_not_fetch_the_config(loader):
    _build_prose_tokenizer()

    assert all(
        call["max_tokens"] == chunker_mod._PROSE_TOKENIZER_MAX_TOKENS
        for call in loader.calls
    )


def test_warm_cache_never_touches_the_network(loader):
    _build_prose_tokenizer()

    assert loader.local_flags == [True]


# ============== fallback ladder ==============


def test_cold_cache_downloads_once_without_falling_back(loader, caplog):
    """First run on a fresh machine: cache miss, then a download, real tokenizer."""
    loader.fails_when = lambda kw: (
        OSError("not in cache") if kw["local_files_only"] else None
    )

    with caplog.at_level("DEBUG"):
        assert _build_prose_tokenizer() is not None

    assert loader.local_flags == [True, False]
    assert not [r for r in caplog.records if "heuristic counter" in r.getMessage()]


def test_returns_none_when_both_attempts_fail(loader):
    loader.fails_when = lambda kw: OSError("offline")

    assert _build_prose_tokenizer() is None
    assert loader.local_flags == [True, False]


# ============== diagnostics ==============


def test_cache_failure_reason_is_recorded_even_when_the_download_succeeds(
    loader, caplog
):
    """A corrupt cache must not be swallowed just because the download worked."""
    loader.fails_when = lambda kw: (
        OSError("cache is corrupt") if kw["local_files_only"] else None
    )

    with caplog.at_level("ERROR"):
        assert _build_prose_tokenizer() is not None

    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1
    assert "cache is corrupt" in errors[0].exc_text


def test_failure_warning_carries_the_traceback(loader, caplog):
    loader.fails_when = lambda kw: OSError("connection refused")

    with caplog.at_level("WARNING"):
        assert _build_prose_tokenizer() is None

    (record,) = [r for r in caplog.records if r.levelname == "WARNING"]
    assert "connection refused" in record.exc_text


def test_warns_only_when_both_attempts_fail(loader, caplog):
    loader.fails_when = lambda kw: OSError("offline")

    with caplog.at_level("WARNING"):
        _build_prose_tokenizer()

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "heuristic counter" in warnings[0].getMessage()


# ============== chunker wiring (needs the real HybridChunker) ==============


@requires_docling
@pytest.mark.parametrize(
    "failure",
    [OSError("offline"), RuntimeError("401 Client Error"), ValueError("broken cache")],
)
def test_prose_chunker_degrades_instead_of_failing_ingestion(loader, failure):
    """A Hub problem must cost chunk precision, not the whole ingestion."""
    loader.fails_when = lambda kw: failure

    chunker = _build_hybrid_chunker(heuristic=False)

    assert chunker.tokenizer.get_tokenizer() is _heuristic_count_tokens
    assert chunker.tokenizer.get_max_tokens() == chunker_mod._PROSE_TOKENIZER_MAX_TOKENS


@requires_docling
def test_tabular_chunker_never_loads_the_hf_tokenizer(loader):
    chunker = _build_hybrid_chunker(heuristic=True)

    assert loader.calls == []
    assert chunker.tokenizer.get_tokenizer() is _heuristic_count_tokens
