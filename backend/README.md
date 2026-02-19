# Syft Space Backend

A FastAPI-based RAG (Retrieval-Augmented Generation) platform for creating, managing, and querying AI-powered endpoints backed by vector databases and language models.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Docker](#docker)
- [Development](#development)
- [Key Concepts](#key-concepts)

## Features

- **Dataset Management** - Connect to Weaviate vector databases (local with auto-provisioning or remote instances)
- **Model Integration** - Configure OpenAI-compatible LLMs for chat completions
- **Endpoint-Based RAG** - Create queryable endpoints that combine datasets and models
- **Policy System** - Apply rate limiting, access control, and accounting policies to endpoints
- **Auto-Provisioning** - Automatically manage Docker containers for local Weaviate instances
- **File Ingestion** - Watch directories and automatically ingest files into datasets
- **Marketplace Integration** - Publish endpoints to SyftHub marketplace
- **Multi-Tenancy** - Optional tenant isolation for multi-user deployments

## Prerequisites

- Python 3.12+
- Docker (required for local Weaviate provisioning)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Installation

### Using uv (recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv venv -p 3.12
uv pip install -e ".[dev]"
```

### Using pip

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quick Start

### 1. Start the Server

```bash
# Development mode with auto-reload
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port 8080
```

The server starts at `http://localhost:8080`. Visit `http://localhost:8080/docs` for interactive API documentation.

### 2. Create a Dataset

```bash
# List available dataset types
curl http://localhost:8080/api/v1/datasets/types/

# Create a local Weaviate dataset (auto-provisions Docker container)
curl -X POST http://localhost:8080/api/v1/datasets/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-docs",
    "dtype": "local_file",
    "configuration": {
      "httpPort": 8081,
      "grpcPort": 50051,
      "collectionName": "Documents",
      "ingestionPath": "/path/to/documents"
    },
    "summary": "My document collection"
  }'
```

### 3. Create a Model

```bash
# List available model types
curl http://localhost:8080/api/v1/models/types/

# Create an OpenAI model
curl -X POST http://localhost:8080/api/v1/models/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpt-4",
    "dtype": "openai",
    "configuration": {
      "api_key": "sk-your-api-key",
      "model": "gpt-4"
    }
  }'
```

### 4. Create an Endpoint

```bash
# Create a RAG endpoint combining dataset and model
curl -X POST http://localhost:8080/api/v1/endpoints/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Document QA",
    "slug": "doc-qa",
    "dataset_id": "<dataset-id-from-step-2>",
    "model_id": "<model-id-from-step-3>",
    "response_type": "both"
  }'
```

### 5. Query the Endpoint

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/doc-qa/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <syfthub-token>" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the main topics in my documents?"}
    ],
    "similarity_threshold": 0.7,
    "limit": 5
  }'
```

## Architecture

### Project Structure

```
backend/
├── syft_space/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Environment configuration
│   ├── alembic/                   # Database migrations
│   └── components/
│       ├── auth/                  # Authentication & authorization
│       ├── datasets/              # Dataset CRUD & management
│       ├── dataset_types/         # Dataset type implementations
│       │   ├──chormadb_local/     # Local Chromadb
│       │   └── weaviate_remote/   # Remote Weaviate
│       ├── models/                # Model CRUD & management
│       ├── model_types/           # Model type implementations
│       │   └── openai/            # OpenAI-compatible models
│       ├── endpoints/             # Endpoint CRUD & query orchestration
│       ├── policies/              # Policy CRUD & management
│       ├── policy_types/          # Policy implementations
│       │   ├── rate_limit/        # Rate limiting
│       │   ├── access/            # Access control
│       │   └── accounting/        # Usage tracking
│       ├── ingestion/             # File watching & ingestion
│       ├── marketplaces/          # SyftHub integration
│       ├── settings/              # App settings
│       ├── tenants/               # Multi-tenancy
│       └── shared/                # Common utilities
└── pyproject.toml                 # Dependencies
```

### Component Pattern

Each component follows a consistent structure:

```
component/
├── entities.py      # SQLModel database models
├── repository.py    # Data access layer (CRUD)
├── handlers.py      # Business logic
├── schemas.py       # Pydantic request/response models
├── routes.py        # FastAPI endpoints
└── __init__.py
```

### Core Flow

1. **Startup**: Migrations run, default tenant created, type registries populated, services started
2. **Request**: Middleware resolves tenant → authenticates → routes to handler
3. **Query**: Token verified → policies enforced → dataset searched → model queried → response returned

## API Reference

Base URL: `/api/v1`

### Datasets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/datasets/types/` | List available dataset types |
| `GET` | `/datasets/types/{name}/schema` | Get configuration schema for type |
| `POST` | `/datasets/` | Create a dataset |
| `GET` | `/datasets/` | List all datasets |
| `GET` | `/datasets/{name}` | Get dataset details |
| `PATCH` | `/datasets/{name}` | Update dataset |
| `DELETE` | `/datasets/{name}` | Delete dataset |
| `GET` | `/datasets/{name}/health` | Check dataset health |
| `GET` | `/datasets/browse` | Browse filesystem for ingestion paths |
| `GET` | `/datasets/provisioners/` | List all provisioners and status |
| `POST` | `/datasets/provisioners/{dtype}/start` | Start a provisioner |
| `POST` | `/datasets/provisioners/{dtype}/stop` | Stop a provisioner |

### Models

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/models/types/` | List available model types |
| `GET` | `/models/types/{name}/schema` | Get configuration schema for type |
| `POST` | `/models/` | Create a model |
| `GET` | `/models/` | List all models |
| `GET` | `/models/{name}` | Get model details |
| `PATCH` | `/models/{name}` | Update model |
| `DELETE` | `/models/{name}` | Delete model |
| `GET` | `/models/{name}/health` | Check model health |

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/endpoints/` | Create an endpoint |
| `GET` | `/endpoints/` | List all endpoints |
| `GET` | `/endpoints/{slug}` | Get endpoint details |
| `PATCH` | `/endpoints/{slug}` | Update endpoint |
| `DELETE` | `/endpoints/{slug}` | Delete endpoint |
| `POST` | `/endpoints/{slug}/query` | Query the endpoint (public) |
| `POST` | `/endpoints/validate-slug` | Check slug availability |
| `POST` | `/endpoints/{slug}/publish` | Publish to marketplace(s) |
| `DELETE` | `/endpoints/{slug}/unpublish` | Unpublish from marketplaces |

### Policies

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/policies/types/` | List available policy types |
| `GET` | `/policies/types/{name}/schema` | Get configuration schema for type |
| `POST` | `/policies/` | Create a policy |
| `GET` | `/policies/` | List all policies |
| `GET` | `/policies/{id}` | Get policy details |
| `PATCH` | `/policies/{id}` | Update policy |
| `DELETE` | `/policies/{id}` | Delete policy |

### Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ingestion/datasets/{id}/status` | Get ingestion status |
| `GET` | `/ingestion/datasets/{id}/jobs` | List ingestion jobs |
| `POST` | `/ingestion/datasets/{id}/start` | Start ingestion |
| `POST` | `/ingestion/datasets/{id}/stop` | Stop ingestion |
| `POST` | `/ingestion/datasets/{id}/retry` | Retry failed jobs |

### Marketplaces

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/marketplaces/register` | Register new marketplace account |
| `POST` | `/marketplaces/connect` | Connect to existing marketplace |
| `GET` | `/marketplaces/` | List connected marketplaces |
| `GET` | `/marketplaces/{id}` | Get marketplace details |
| `GET` | `/marketplaces/balance` | Get account balance |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/settings/public-url` | Get current public URL |
| `PATCH` | `/settings/public-url` | Update public URL |
| `GET` | `/settings/proxy` | Get proxy (ngrok) status |
| `POST` | `/settings/proxy` | Configure ngrok tunnel |
| `DELETE` | `/settings/proxy` | Disconnect proxy |

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (no auth required) |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SYFT_SQLITE_DB_PATH` | `~/.syft-space/app.db` | SQLite database path |
| `SYFT_DEBUG` | `false` | Enable debug mode |
| `SYFT_RESET_DB` | `false` | Reset database on startup (destructive) |
| `SYFT_ADMIN_API_KEY` | (empty) | Admin API key; empty = dev mode (no auth) |
| `SYFT_ENABLE_MULTI_TENANCY` | `false` | Enable multi-tenant mode |
| `SYFT_DEFAULT_TENANT_NAME` | `root` | Default tenant name |
| `SYFT_DEFAULT_ACCOUNTING_URL` | `https://syftaccounting...` | Accounting service URL |
| `SYFT_DEFAULT_MARKETPLACE_URL` | `https://syfthub.openmined.org` | SyftHub marketplace URL |
| `SYFT_PUBLIC_URL` | (empty) | Public URL for callbacks |

### Authentication

- **Admin API Key**: Set `SYFT_ADMIN_API_KEY` to require `Authorization: Bearer <key>` for protected routes
- **Dev Mode**: Leave `SYFT_ADMIN_API_KEY` empty to disable authentication (development only)
- **SyftHub Token**: The `/endpoints/{slug}/query` route requires a valid SyftHub token for user identification

### Multi-Tenancy

When `SYFT_ENABLE_MULTI_TENANCY=true`:
- Include `X-Tenant-Name` header in requests
- Data is isolated per tenant
- Default tenant is created on startup

## Docker

### Build

```bash
# Build frontend first (served as static files)
cd ../frontend && bun install && bun run build && cd ../backend

# Build Docker image
docker build -t syft-space-server ..
```

### Run with Environment Variables

```bash
docker run -d -p 8080:8080 \
  -e SYFT_DEBUG=false \
  -e SYFT_ADMIN_API_KEY=your-secret-key \
  -e SYFT_SQLITE_DB_PATH=/data/app.db \
  -v syft-data:/data \
  syft-space-server
```

### Run with .env File

```bash
cp .env.example .env
# Edit .env with your values

docker run -d -p 8080:8080 \
  --env-file .env \
  -v syft-data:/data \
  syft-space-server
```

### Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

## Development

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy .
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Testing

```bash
pytest
```

### Database Migrations

Migrations run automatically when the server starts. No manual commands are needed.

- On startup, the server applies all pending migrations
- In debug mode (`SYFT_DEBUG=true`), if migrations fail, it falls back to creating tables directly
- Set `SYFT_RESET_DB=true` to drop and recreate all tables (use with caution)

For creating new migrations or advanced workflows, see the [Migrations Guide](./MIGRATIONS.md).

## Key Concepts

### Dataset Types

Dataset types define how to connect to vector databases:

- **`local_file`**: Uses a local ChromaDB instance for vector storage. Automatically manages lifecycle (start/stop).
- **`weaviate_remote`**: Connects to an existing remote Weaviate instance.

### Model Types

Model types define how to interact with LLMs:

- **`openai`**: OpenAI-compatible API. Supports custom `base_url` for vLLM, Ollama, or other compatible servers.

### Provisioners

Provisioners manage infrastructure for local services:

- Track state: `STOPPED` → `STARTING` → `RUNNING` → `STOPPING`
- Shared across datasets of the same type
- State persists across server restarts

### Endpoints

Endpoints combine datasets and models for RAG queries:

- **Response Types**:
  - `raw`: Return dataset search results only
  - `summary`: Return model response only
  - `both`: Return both search results and model summary

### Policies

Policies are pre/post-processing hooks applied to endpoint requests:

- **`rate_limit`**: Limit requests per time window (e.g., "100/minute")
- **`access`**: Control access via email allowlist/denylist
- **`accounting`**: Track token usage for billing

### Ingestion

The ingestion system watches directories and indexes files into datasets:

- Uses file fingerprinting (size + mtime) for change detection
- Supports retry of failed jobs
- State persists across restarts

## License

Apache 2.0

## Support

For issues and questions, visit [github.com/OpenMined/syft-space](https://github.com/OpenMined/syft-space)
