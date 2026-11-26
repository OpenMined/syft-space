"""One guarded first import of transformers for the whole process."""

from __future__ import annotations

import threading

_LOCK = threading.Lock()
_READY = False


def ensure_transformers() -> None:
    """Import transformers and resolve the names we use, once, under a lock.

    Its lazy module is not safe to initialise from two threads at once: a
    search and an ingestion that import it together after a restart see
    ``AutoModel`` missing and fail with ImportError.
    """
    global _READY
    if _READY:
        return
    with _LOCK:
        if _READY:
            return
        import transformers

        _ = (transformers.AutoModel, transformers.AutoTokenizer)
        _READY = True
