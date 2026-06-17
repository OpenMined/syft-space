# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi==0.116.2",
#     "uvicorn[standard]==0.35.0",
#     "pydantic==2.11.9",
#     "python-multipart==0.0.31",
#     "loguru>=0.7.3",
# ]
# ///
"""Standalone file upload service.

An independent, self-contained service (not part of syft-space). It accepts
authenticated file uploads and stores them on disk in a folder namespaced by
a unique identifier for the uploading user.

Run it with uv (dependencies are declared inline above, PEP 723). With no
arguments it prompts for the upload folder and auth token:

    uv run scripts/upload_service.py

Or supply them up front via flags or environment variables (skips the prompts):

    uv run scripts/upload_service.py --upload-dir ./uploads --auth-token secret123
    UPLOAD_DIR=./uploads UPLOAD_AUTH_TOKEN=secret123 uv run scripts/upload_service.py

Upload a file (the token must match, identifier + file are required):

    curl -X POST http://localhost:8082/upload \\
        -H "Authorization: Bearer secret123" \\
        -F "identifier=alice@example.com" \\
        -F "file=@./report.pdf"

The file above lands at: <upload-dir>/alice@example.com/report.pdf
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

# Bytes read/written per chunk while streaming uploads to disk.
CHUNK_SIZE = 1024 * 1024  # 1 MiB

# A unique identifier becomes a single folder name, so restrict it to
# filesystem-safe characters. This still accepts email addresses.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._@+-]+$")


class Config:
    """Runtime configuration, resolved from CLI args then environment."""

    def __init__(self, upload_dir: Path, auth_token: str) -> None:
        self.upload_dir = upload_dir
        self.auth_token = auth_token


# Populated in main() before the server starts.
config: Config


def _sanitize_identifier(identifier: str) -> str:
    """Validate a unique identifier and turn it into a safe path segment.

    Accepts any identifier made of filesystem-safe characters and rejects
    path-traversal payloads (e.g. "../../etc") so they never reach the
    filesystem. The result is a single folder name.
    """
    candidate = (identifier or "").strip()
    if (
        candidate in {"", ".", ".."}
        or not _IDENTIFIER_RE.match(candidate)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid identifier.",
        )
    # Lowercase for stable, case-insensitive namespacing on disk.
    return candidate.lower()


def _sanitize_filename(filename: str | None) -> str:
    """Reduce an uploaded filename to a safe basename.

    Strips any directory components and rejects empty/dot-only names so a
    client cannot escape its identifier-namespaced folder.
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is missing a filename.",
        )
    # Keep only the final path component, regardless of separator style.
    base = os.path.basename(filename.replace("\\", "/")).strip()
    if base in {"", ".", ".."} or not re.sub(r"[.\s]", "", base):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid filename.",
        )
    return base


_bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Reject any request that doesn't carry the configured bearer token."""
    if credentials is None or credentials.credentials != config.auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing auth token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


app = FastAPI(title="Upload Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe; no auth required."""
    return {"status": "ok"}


@app.post("/upload", dependencies=[Depends(require_auth)])
async def upload(
    identifier: str = Form(
        ..., description="Unique identifier of the uploading user."
    ),
    file: UploadFile = File(..., description="File to store."),
) -> dict[str, object]:
    """Store an uploaded file under <upload-dir>/<identifier>/<filename>."""
    namespace = _sanitize_identifier(identifier)
    filename = _sanitize_filename(file.filename)

    target_dir = config.upload_dir / namespace
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    size = 0
    try:
        with target_path.open("wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                out.write(chunk)
                size += len(chunk)
    except OSError as exc:
        logger.error("Failed to write upload {}: {}", target_path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file.",
        )
    finally:
        await file.close()

    logger.info("Stored {} bytes at {}", size, target_path)
    return {
        "identifier": namespace,
        "filename": filename,
        "size": size,
        "path": str(target_path),
    }


def _resolve_config(args: argparse.Namespace) -> Config:
    """Resolve config from CLI args, falling back to environment variables."""
    upload_dir = args.upload_dir or os.environ.get("UPLOAD_DIR")
    auth_token = args.auth_token or os.environ.get("UPLOAD_AUTH_TOKEN")

    # Interactive fallback: prompt for anything not supplied via CLI/env.
    if not upload_dir:
        upload_dir = input("Upload folder path: ").strip()
    if not auth_token:
        auth_token = getpass.getpass("Auth token: ").strip()

    if not upload_dir:
        raise SystemExit("error: upload folder path is required.")
    if not auth_token:
        raise SystemExit("error: auth token is required.")

    # The upload dir is the parent folder; per-identifier subfolders live
    # inside it. Validate the path, and create it (with parents) if missing.
    resolved_dir = Path(upload_dir).expanduser().resolve()
    if resolved_dir.exists() and not resolved_dir.is_dir():
        raise SystemExit(
            f"error: upload path exists but is not a directory: {resolved_dir}"
        )
    try:
        resolved_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            f"error: could not create upload directory {resolved_dir}: {exc}"
        )
    if not os.access(resolved_dir, os.W_OK):
        raise SystemExit(f"error: upload directory is not writable: {resolved_dir}")
    return Config(upload_dir=resolved_dir, auth_token=auth_token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone file upload service.")
    parser.add_argument(
        "--upload-dir",
        help="Folder where uploaded files are saved (env: UPLOAD_DIR).",
    )
    parser.add_argument(
        "--auth-token",
        help="Bearer token required to upload (env: UPLOAD_AUTH_TOKEN).",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0).")
    parser.add_argument(
        "--port", type=int, default=8082, help="Bind port (default: 8082)."
    )
    args = parser.parse_args()

    global config
    config = _resolve_config(args)

    logger.info("Upload directory: {}", config.upload_dir)
    logger.info("Listening on {}:{}", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
