# Getting Started

This guide takes you from a clean checkout to a working, queryable RAG endpoint.

## Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** (recommended) or pip
- **Docker** — *optional*. The built-in `local_file` dataset type runs ChromaDB
  as a local **subprocess**, so you do **not** need Docker for the default
  local workflow. Docker is only relevant if you self-host external services
  (e.g. a Weaviate cluster) yourself.

## Install

```bash
cd backend

# Recommended: uv
uv venv -p 3.12
uv pip install -e ".[dev]"

# Or with pip
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run the server

```bash
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port 8080
```

- App: <http://localhost:8080>
- **Interactive API docs (Swagger):** <http://localhost:8080/docs>
- OpenAPI schema: <http://localhost:8080/openapi.json>

> **Auth note:** with no `SYFT_ADMIN_API_KEY` set, the server runs in **dev
> mode** — admin routes require no authentication. That's the easiest way to
> follow this tutorial. See [Configuration](./configuration.md#authentication)
> for production auth.

---

## Tutorial: create a queryable endpoint

We'll build a document-QA endpoint: index a folder of files, attach an LLM, and
query it.

### 1. Discover what you can create

Configuration is **type-specific**. Always fetch the schema for a type before
creating an instance, so you send exactly the fields it expects.

```bash
# What dataset types exist? (local_file, remote_weaviate, …)
curl http://localhost:8080/api/v1/datasets/types/

# Get the config schema for one of them
curl http://localhost:8080/api/v1/datasets/types/local_file/schema

# Same idea for models
curl http://localhost:8080/api/v1/models/types/
```

### 2. Create a dataset

`local_file` indexes files from disk into a local ChromaDB instance. The vector
store subprocess is **auto-provisioned** for you.

```bash
curl -X POST http://localhost:8080/api/v1/datasets/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-docs",
    "dtype": "local_file",
    "summary": "My document collection",
    "tags": "docs,demo",
    "configuration": {
      "collectionName": "Documents",
      "filePaths": [{ "path": "/path/to/documents", "description": "source docs" }],
      "ingestFileTypeOptions": [".pdf", ".txt", ".md", ".docx"]
    }
  }'
```

Files matching the allowed extensions are watched and ingested automatically.
Track progress with the ingestion routes:

```bash
curl http://localhost:8080/api/v1/ingestion/datasets/<dataset-id>/status
```

The status reports per-job counts; ingestion is done once there are no
`pending`/`running` jobs left (each file typically takes a few seconds, more for
large PDFs). You can start querying as soon as the first documents land.

### 3. Create a model

Any OpenAI-compatible API works (OpenAI, vLLM, Ollama, …) by setting `base_url`.

```bash
curl -X POST http://localhost:8080/api/v1/models/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpt-4o-mini",
    "dtype": "openai",
    "configuration": {
      "api_key": "sk-your-api-key",
      "model": "gpt-4o-mini",
      "base_url": "https://api.openai.com/v1"
    }
  }'
```

### 4. Create an endpoint

Combine the dataset and model. `response_type: "both"` gives you full RAG —
search the dataset, then feed the hits to the model as context.

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Document QA",
    "slug": "doc-qa",
    "summary": "Ask questions about my documents",
    "dataset_id": "<dataset-id-from-step-2>",
    "model_id": "<model-id-from-step-3>",
    "response_type": "both"
  }'
```

| `response_type` | Uses | Returns |
| --- | --- | --- |
| `raw` | dataset only | search hits |
| `summary` | model only | LLM answer |
| `both` | dataset → model | search hits **and** an LLM answer grounded in them |

### 5. Query it

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/doc-qa/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin-key-or-syfthub-token>" \
  -d '{
    "messages": [
      { "role": "user", "content": "What are the main topics in my documents?" }
    ],
    "similarity_threshold": 0.7,
    "limit": 5
  }'
```

The response contains `references` (search hits) and/or `summary` (LLM answer),
depending on `response_type`. For the full request/response shape and the
authentication rules on this route, see [Query Flow](./query-flow.md).

---

## Next steps

- **Protect the endpoint** with [Policies](./concepts.md#policies) — restrict
  access, add a rate limit, or charge per query.
- **Publish it** to SyftHub so external users can discover and query it through
  a tunnel — see [Architecture › Marketplace](./architecture.md#external-integration-syfthub).
- **Charge for it** — see [Payments & Wallets](./payments.md).
</content>
