"""Prose tokenizer loading: never authenticated, cache first, degrades to the
heuristic counter rather than failing ingestion."""

from __future__ import annotations

from typing import Any

import pytest

from syft_space.components.chunking import chunker as chunker_mod
from syft_space.components.chunking.chunker import (
    _build_hybrid_chunker,
    _build_prose_tokenizer,
    _heuristic_count_tokens,
)


def _record_from_pretrained(monkeypatch, side_effect=None):
    """Capture the kwargs docling's tokenizer factory is called with."""
    calls: list[dict[str, Any]] = []

    class _FakeTokenizer:
        def get_max_tokens(self) -> int:
            return 256

        def count_tokens(self, text: str) -> int:
            return len(text.split())

        def get_tokenizer(self):
            return self.count_tokens

    def fake_from_pretrained(**kwargs):
        calls.append(kwargs)
        if side_effect is not None:
            raise side_effect
        return _FakeTokenizer()

    import docling_core.transforms.chunker.tokenizer.huggingface as hf_mod

    monkeypatch.setattr(
        hf_mod.HuggingFaceTokenizer, "from_pretrained", fake_from_pretrained
    )
    return calls


def test_prose_tokenizer_never_sends_a_credential(monkeypatch):
    calls = _record_from_pretrained(monkeypatch)

    _build_prose_tokenizer()

    assert calls, "tokenizer factory was not called"
    assert all(c["token"] is False for c in calls)


def test_prose_tokenizer_tries_the_local_cache_first(monkeypatch):
    calls = _record_from_pretrained(monkeypatch)

    _build_prose_tokenizer()

    assert calls[0]["local_files_only"] is True


def test_prose_tokenizer_falls_back_to_the_network_when_uncached(monkeypatch):
    calls = _record_from_pretrained(monkeypatch, side_effect=OSError("not cached"))

    assert _build_prose_tokenizer() is None
    assert [c["local_files_only"] for c in calls] == [True, False]


def test_cold_cache_downloads_once_and_stays_quiet(monkeypatch, caplog):
    """First run on a fresh machine: cache miss, then a download. Not a problem."""
    calls: list[dict[str, Any]] = []

    class _FakeTokenizer:
        def get_max_tokens(self) -> int:
            return 256

        def get_tokenizer(self):
            return None

    def fake_from_pretrained(**kwargs):
        calls.append(kwargs)
        if kwargs["local_files_only"]:
            raise OSError("not in cache")
        return _FakeTokenizer()

    import docling_core.transforms.chunker.tokenizer.huggingface as hf_mod

    monkeypatch.setattr(
        hf_mod.HuggingFaceTokenizer, "from_pretrained", fake_from_pretrained
    )

    with caplog.at_level("WARNING"):
        tokenizer = _build_prose_tokenizer()

    assert tokenizer is not None
    assert [c["local_files_only"] for c in calls] == [True, False]
    assert caplog.records == []


def test_cache_failure_reason_is_recorded_even_when_the_download_succeeds(
    monkeypatch, caplog
):
    """A corrupt cache must not be swallowed just because the download worked."""

    class _FakeTokenizer:
        def get_max_tokens(self) -> int:
            return 256

        def get_tokenizer(self):
            return None

    def fake_from_pretrained(**kwargs):
        if kwargs["local_files_only"]:
            raise OSError("cache is corrupt")
        return _FakeTokenizer()

    import docling_core.transforms.chunker.tokenizer.huggingface as hf_mod

    monkeypatch.setattr(
        hf_mod.HuggingFaceTokenizer, "from_pretrained", fake_from_pretrained
    )

    with caplog.at_level("DEBUG"):
        assert _build_prose_tokenizer() is not None

    debug = [r for r in caplog.records if r.levelname == "DEBUG"]
    assert len(debug) == 1
    assert "cache is corrupt" in debug[0].exc_text


def test_failure_warning_carries_the_traceback(monkeypatch, caplog):
    _record_from_pretrained(monkeypatch, side_effect=OSError("connection refused"))

    with caplog.at_level("WARNING"):
        assert _build_prose_tokenizer() is None

    (record,) = [r for r in caplog.records if r.levelname == "WARNING"]
    assert "connection refused" in record.exc_text


def test_warns_only_when_both_attempts_fail(monkeypatch, caplog):
    _record_from_pretrained(monkeypatch, side_effect=OSError("offline"))

    with caplog.at_level("WARNING"):
        assert _build_prose_tokenizer() is None

    assert len(caplog.records) == 1
    assert "heuristic counter" in caplog.records[0].getMessage()


def test_max_tokens_is_passed_so_docling_does_not_fetch_the_config(monkeypatch):
    calls = _record_from_pretrained(monkeypatch)

    _build_prose_tokenizer()

    assert all(
        c["max_tokens"] == chunker_mod._PROSE_TOKENIZER_MAX_TOKENS for c in calls
    )


@pytest.mark.parametrize(
    "failure",
    [OSError("offline"), RuntimeError("401 Client Error"), ValueError("broken cache")],
)
def test_prose_chunker_degrades_instead_of_failing_ingestion(monkeypatch, failure):
    """A Hub problem must cost chunk precision, not the whole ingestion."""
    _record_from_pretrained(monkeypatch, side_effect=failure)

    chunker = _build_hybrid_chunker(heuristic=False)

    assert chunker.tokenizer.get_tokenizer() is _heuristic_count_tokens
    assert chunker.tokenizer.get_max_tokens() == chunker_mod._PROSE_TOKENIZER_MAX_TOKENS


def test_tabular_chunker_never_loads_the_hf_tokenizer(monkeypatch):
    calls = _record_from_pretrained(monkeypatch)

    chunker = _build_hybrid_chunker(heuristic=True)

    assert calls == []
    assert chunker.tokenizer.get_tokenizer() is _heuristic_count_tokens
