# <a href="https://github.com/OpenMined"><img src="https://avatars.githubusercontent.com/u/30185530?s=200&v=4" alt="OpenMined" width="32" align="center" style="border-radius: 8px;"></a> Syft Space

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/node.js-20%2B-green)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D)](https://vuejs.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet)](https://github.com/astral-sh/uv)
[![Bun](https://img.shields.io/badge/bun-runtime-f9f1e1)](https://bun.sh/)

**Collective Intelligence, Individual Control.** Syft Space connects knowledge across a decentralized network—each Space contributes while keeping data under its owner's control.

![Syft Space Dashboard](image.png)

## What is Syft Space?

A Syft Space is a decentralized node operated by anyone with knowledge to share: a publisher, a research lab, a journalist, an institution, or just an individual.

Each Space holds data locally and makes it queryable on terms the operator defines—attribution, control, traceability, payments, or extra layers of privacy-preserving tools if sensitive. Knowledge stays at the source; AI queries it in place.

Like querying a hospital's medical database: you get answers based on their clinical data, but you never see patient records. Or asking questions about a paywalled research journal: you access the knowledge without copying the content. Syft Space respects IP and privacy—you share insights, not sources.

## How It Works

Syft Space has three building blocks:

| Component | What It Does |
|-----------|--------------|
| **Datasets** | Your documents, files, or vector databases—the knowledge you want to make queryable |
| **Models** | AI providers (OpenAI, Anthropic, Ollama, vLLM) that understand questions and generate answers |
| **Endpoints** | Combine datasets + models into queryable RAG services with a simple URL |
| **Policies** | Rate limiting, access control, usage tracking, and pricing—your rules |

**That's it.** Resources in, endpoint out, policies to control the flow.

## Who Is This For?

- **Researchers** who want their papers to be discoverable and citable
- **Organizations** with documentation, FAQs, or internal knowledge bases
- **Data owners** who want to monetize insights without exposing raw data
- **Teams** who need AI-powered search over their collective knowledge
- **Individuals** with expertise they want to make accessible on their terms

## Installation

### Option 1: Desktop App (Recommended for Local Use)

Download the native app for a system tray experience with automatic server management.

- **macOS**: Download `.dmg` from [Releases](https://github.com/OpenMined/syft-space/releases)
- **Linux**: Download `.AppImage`, `.deb`, or `.rpm` from [Releases](https://github.com/OpenMined/syft-space/releases)

See the [Desktop App Guide](http://syft.docs.openmined.org/space/installation) for detailed instructions.

### Option 2: Docker (Recommended for Cloud/Server)

```bash
docker run -d \
  --name syft-space \
  -p 8080:8080 \
  -v syft-data:/data \
  -e SYFT_SQLITE_DB_PATH=/data/app.db \
  openmined/syft-space:latest
```

Open [http://localhost:8080](http://localhost:8080) to access the interface.

See the [Docker Installation Guide](http://syft.docs.openmined.org/space/installation/docker) for advanced configuration.

### Option 3: From Source

```bash
git clone https://github.com/OpenMined/syft-space.git
cd syft-space
./run.sh
```

## Developer Token (Local Deployments)

Running Syft Space on your local machine? You'll need a **developer token** from OpenMined to make your Space reachable by others.

- **Required for**: Publishing endpoints and receiving queries on local machines
- **Not required for**: VM/cloud deployments with public URLs, or local-only testing
- **How to get one**: Contact OpenMined directly (beta program)
- **Configure in**: Onboarding (first launch) or Settings → Network

Without a token, you can still use Syft Space locally for development and query other published endpoints.

**Query other Spaces:** Discover and query Spaces shared by others at [syfthub.openmined.org](https://syfthub.openmined.org)

## Quick Start

1. **Install** Syft Space (desktop app or Docker)
2. **Set up connectivity** — enter your developer token during onboarding if running locally
3. **Add your resources** — upload documents or connect a database, configure an AI model
4. **Create an endpoint** — combine your dataset and model
5. **Set your policies** — decide who can access and on what terms
6. **Share** — give out your endpoint URL and start answering questions

### Example: Query an Endpoint

```bash
curl -X POST http://localhost:8080/api/v1/endpoints/my-docs/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the main topics in my documents?"}
    ]
  }'
```

## Key Features

- **Multi-database support**: Weaviate, Qdrant, ChromaDB, or remote data sources
- **Multi-model support**: OpenAI, Anthropic, vLLM, Ollama, and other providers
- **Auto-provisioning**: Automatically manages Docker containers for local databases
- **Desktop & web interface**: Run it as an app or deploy as a service
- **Usage analytics**: Monitor costs, tokens, and performance
- **Marketplace integration**: Publish to SyftHub for discovery

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SYFT_PORT` | `8080` | Port the server runs on |
| `SYFT_DEBUG` | `false` | Enable detailed logging |
| `SYFT_ADMIN_API_KEY` | (empty) | Admin authentication key |
| `SYFT_SQLITE_DB_PATH` | `/data/app.db` | Path to SQLite database |
| `SYFT_PUBLIC_URL` | auto-detected | Public URL for the instance |

See `.env.example` for all available options.

## Project Structure

```
syft-space/
├── backend/         # Python FastAPI server
│   └── syft_space/  # Main application code
├── frontend/        # Vue 3 web interface
├── docs/            # Documentation
├── Dockerfile       # Container build
└── docker-compose.yml
```

## Documentation

- [Quick Start](http://syft.docs.openmined.org/quickstart) — Get started in 3 steps: add data, create endpoint, publish
- [Introduction](http://syft.docs.openmined.org/space) — Understand the concepts
- [Components Overview](http://syft.docs.openmined.org/space/components/overview) — Datasets, models, endpoints, and policies
- [Datasets](http://syft.docs.openmined.org/space/components/datasets) — Managing your data sources
- [Models](http://syft.docs.openmined.org/space/components/models) — AI providers and configuration
- [Endpoints](http://syft.docs.openmined.org/space/components/endpoints) — Queryable RAG services
- [Policies](http://syft.docs.openmined.org/space/components/policies) — Access control and rate limiting
- [API Reference](http://syft.docs.openmined.org/space/api) — REST API documentation
- [Installation Guide](http://syft.docs.openmined.org/installation) — Complete setup instructions

Interactive API docs available at [http://localhost:8080/docs](http://localhost:8080/docs) when running.

## Part of the Syft Network

Your Space can connect to **[SyftHub](https://syfthub.openmined.org)**, a registry that maps who has knowledge, what they're willing to share, and how to reach them. When someone queries the network, their request is routed to the relevant Spaces. Each Space that contributes to an answer is tracked—attribution is built into how the system works.

**Query other Spaces:** Discover and query Spaces shared by others at [syfthub.openmined.org](https://syfthub.openmined.org)

The network gets better as more Spaces join. But the architecture matters: we're building on open protocols so that no single entity—including us—controls the whole. The infrastructure belongs to everyone who participates.

## Contributing

Contributions are welcome! See the [Development Documentation](http://syft.docs.openmined.org) for setup instructions and contribution guidelines.

## License

This project is part of the OpenMined ecosystem. See the repository for license details.
