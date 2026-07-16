"""Entry point for the syft-space-backend executable.

Dispatches based on CLI arguments:
  (no args)            → start the FastAPI backend server
  --chroma-server ...  → forward to the ChromaDB CLI

This module is the PyInstaller entry point and also supports
``python -m syft_space``.  The heavy application imports live in
``syft_space.main`` and are only loaded when actually starting the
backend, keeping the ChromaDB and multiprocessing code paths fast.
"""

import multiprocessing
import sys


def _run_chroma_server() -> None:
    """Forward to the ``chroma`` CLI (used as a subprocess in frozen bundles)."""
    sys.argv = ["chroma"] + sys.argv[2:]
    from chromadb.cli.cli import app as chroma_cli

    chroma_cli()


def _run_backend() -> None:
    """Start the FastAPI backend via uvicorn."""
    import uvicorn

    from syft_space.config import app_settings
    from syft_space.main import app

    uvicorn.run(app, host=app_settings.host, port=app_settings.port)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    if len(sys.argv) > 1 and sys.argv[1] == "--convert-pdf-pages":
        from syft_space.components.vector_stores.docling_local import (
            _worker_convert_pages,
        )

        _worker_convert_pages()
    elif len(sys.argv) > 1 and sys.argv[1] == "--chroma-server":
        _run_chroma_server()
    else:
        _run_backend()
