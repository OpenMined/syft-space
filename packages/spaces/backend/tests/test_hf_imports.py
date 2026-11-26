"""The first import of transformers is guarded for concurrent callers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from syft_space.components.embeddings import hf_imports


def test_concurrent_first_imports_all_see_the_lazy_names() -> None:
    hf_imports._READY = False

    def load() -> object:
        hf_imports.ensure_transformers()
        from transformers import AutoModel

        return AutoModel

    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(pool.map(lambda _: load(), range(16)))

    assert hf_imports._READY
    assert all(item is loaded[0] for item in loaded)
