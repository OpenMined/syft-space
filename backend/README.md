# Syft Space

A powerful RAG (Retrieval-Augmented Generation) platform that enables you to create, manage, and query AI-powered endpoints backed by vector databases and language models.

## Features

- 🗃️ **Flexible Dataset Management** - Connect to multiple vector databases (Weaviate, Qdrant, ChromaDB) or remote data sources
- 🤖 **Multi-Model Support** - Integrate with various LLM providers (vLLM, OpenAI, Anthropic, Ollama)
- 🔌 **Endpoint-Based Architecture** - Create queryable endpoints that combine datasets and models for RAG workflows
- 🛡️ **Policy System** - Apply pre/post-processing hooks for rate limiting, access control, and custom logic
- 📦 **Auto-Provisioning** - Automatically manage infrastructure (Docker containers, processes) for local services
- 🔄 **Restart-Safe** - Persistent state tracking allows resource re-discovery after server restarts

## Prerequisites

- Python 3.9 or higher
- Docker (if using local vector databases like Weaviate)
- uv (recommended) or pip for package management

## Installation

### Using uv (recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e ".[dev]"
```

### Using pip

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Start the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or run directly
python -m main
```

The server will start at `http://localhost:8000`

### 2. Explore the API

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

### 3. Create Your First Dataset

```bash
# List available dataset types
curl http://localhost:8000/api/v1/datasets/types/

# Create a Weaviate dataset (auto-provisions Docker container)
curl -X POST http://localhost:8000/api/v1/datasets/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-docs",
    "type": "weaviate",
    "configuration": {
      "httpPort": 8080,
      "grpcPort": 50051,
      "collectionName": "Documents"
    },
    "summary": "My document collection"
  }'
```

### 4. Create a Model

```bash
# List available model types
curl http://localhost:8000/api/v1/models/types/

# Create a model instance
curl -X POST http://localhost:8000/api/v1/models/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpt-4-chat",
    "type": "openai",
    "configuration": {
      "api_key": "your-api-key",
      "model": "gpt-4"
    }
  }'
```

### 5. Create an Endpoint

```bash
# Create a RAG endpoint combining dataset and model
curl -X POST http://localhost:8000/api/v1/endpoints/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Doc QA Endpoint",
    "slug": "doc-qa",
    "dataset_id": "<dataset-id>",
    "model_id": "<model-id>",
    "response_type": "both",
    "visibility": ["*"],
    "published": true
  }'
```

### 6. Query the Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/endpoints/doc-qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "user@example.com",
    "messages": [
      {"role": "user", "content": "What is the main topic?"}
    ],
    "similarity_threshold": 0.8,
    "limit": 5
  }'
```

## Project Structure

```
backend/
├── syft_space/
│  ├── components/
│  │   ├── dataset_types/       # Dataset type definitions and provisioners
│  │   │   ├── interfaces.py    # Base protocols
│  │   │   ├── registry.py      # Type registry
│  │   │   └── weaviate/        # Weaviate implementation
│  │   ├── datasets/            # Dataset CRUD and management
│  │   ├── model_types/         # Model type definitions
│  │   ├── models/              # Model CRUD and management
│  │   ├── policy_types/        # Policy type definitions
│  │   ├── policies/            # Policy CRUD and management
│  │   ├── endpoints/           # Endpoint CRUD and query orchestration
│  │   └── shared/              # Shared utilities and types
│  ├── main.py                  # FastAPI application entry point
│  ├── config.py                # Application configuration
└── pyproject.toml           # Project dependencies and metadata
```

## Configuration

The server uses environment variables and defaults:

- **Database**: SQLite at `~/.syftai/syftai.db` (configurable via `database_path`)
- **CORS**: Allows `http://localhost:5173` by default (frontend)
- **Debug Mode**: Set via `debug` config

## Development

### Run Linters

```bash
# Run ruff linter
ruff check .

# Run ruff formatter
ruff format .

# Run type checking
mypy .
```

### Run Pre-commit Hooks

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Run Tests

```bash
pytest
```

## Documentation

- **[API Specification](./API_SPECIFICATION.md)** - Complete API documentation with endpoints, schemas, and architecture
- **[API Docs (Interactive)](http://localhost:8000/docs)** - Swagger UI (when server is running)

## Key Concepts

### Dataset Types
Define how to connect and interact with different vector databases or data sources. Supports custom implementations.

### Model Types
Define how to connect and interact with different LLM providers. Supports custom implementations.

### Provisioners
Handle infrastructure lifecycle for local services (e.g., Docker containers). Auto-start/stop resources with persistent state tracking.

### Endpoints
Combine datasets and models to create queryable RAG endpoints with policies for access control and rate limiting.

### Policies
Pre/post-processing hooks applied to endpoint requests and responses (e.g., rate limiting, authentication, custom transformations).

## License

[Add License]

## Contributing

[Add Contributing Guidelines]

## Support

For issues, questions, or contributions, please visit [Add Repository URL]
