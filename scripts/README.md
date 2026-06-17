# Upload Service

A small, **standalone** file upload service. It is intentionally independent of
syft-space — it has no shared imports and declares its own dependencies inline
(PEP 723), so it runs on its own with `uv`.

## What it does

- Accepts authenticated file uploads over HTTP.
- Requires a bearer token; only callers presenting the configured token can upload.
- Saves each file under a folder **namespaced by the uploader's email address**:
  `<upload-dir>/<email>/<filename>`.

## Quick start (one command)

`run.sh` bootstraps everything — it installs `uv` if missing, pins Python 3.12,
downloads `upload_service.py`, and runs it. The service then **prompts you for
the upload folder path and auth token**. Safe to pipe straight from curl:

```bash
curl -fsSL https://raw.githubusercontent.com/OpenMined/syft-space/upload-service/scripts/run.sh | bash
```

## Run manually

```bash
uv run scripts/upload_service.py
```

This prompts for the upload folder and auth token interactively. You can skip
the prompts by passing flags or environment variables:

```bash
# Via CLI flags
uv run scripts/upload_service.py --upload-dir ./uploads --auth-token secret123

# Or via environment variables
UPLOAD_DIR=./uploads UPLOAD_AUTH_TOKEN=secret123 uv run scripts/upload_service.py
```

Optional flags: `--host` (default `0.0.0.0`), `--port` (default `8082`).

## Upload a file

```bash
curl -X POST http://localhost:8082/upload \
    -H "Authorization: Bearer secret123" \
    -F "email=alice@example.com" \
    -F "file=@./report.pdf"
```

Result on disk: `./uploads/alice@example.com/report.pdf`

## Endpoints

| Method | Path      | Auth   | Body                                  |
| ------ | --------- | ------ | ------------------------------------- |
| GET    | `/health` | none   | —                                     |
| POST   | `/upload` | Bearer | `email` (form), `file` (multipart)    |

## Notes

- Emails are validated and lowercased before being used as a directory name, and
  filenames are reduced to a safe basename — so neither can be used for path
  traversal outside the upload directory.
- Interactive API docs are available at `http://localhost:8082/docs`.
