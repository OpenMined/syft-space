# <a href="https://github.com/OpenMined"><img src="https://avatars.githubusercontent.com/u/30185530?s=200&v=4" alt="OpenMined" width="32" align="center" style="border-radius: 8px;"></a> Syft Space Server

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/node.js-20%2B-green)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D)](https://vuejs.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/badge/uv-package%20manager-blueviolet)](https://github.com/astral-sh/uv)
[![Bun](https://img.shields.io/badge/bun-runtime-f9f1e1)](https://bun.sh/)

A space where you can turn data and models into shareable workflows — exposing them through secure endpoints under your own rules for privacy, payments, and human oversight.

## At a Glance

Syft Space Server lets you create **secure, shareable AI endpoints**. In plain terms, it helps you:

- **Connect your data** to searchable vector databases
- **Integrate language models** (OpenAI-compatible APIs)
- **Build endpoints** that combine data and models into queryable workflows
- **Set your own rules** for access control, rate limiting, and usage tracking

Think of it as your personal control plane for AI workflows — you decide who can access what, under what terms.

## Why Syft Space?

- **Own your data** — self-host instead of sending everything to third parties
- **Control access** — define policies for privacy, payments, and oversight
- **Share securely** — expose endpoints without exposing raw data
- **Stay flexible** — works with your existing models and databases

## Prerequisites

- **Docker** (recommended) - [Install Docker](https://docs.docker.com/get-docker/)

Or for running from source:
- **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
- **Bun** - [Install Bun](https://bun.sh/)

## Quick Start

The fastest way to get started is with the pre-built Docker image:

```bash
docker run -d \
    --name syft-space \
    -p 8080:8080 \
    -v syft-space-data:/data \
    ghcr.io/openmined/syft-space:latest
```

Open your browser to [http://localhost:8080](http://localhost:8080) to access the application.

## Docker Usage

### With Local Directory Mount

Mount your local home directory to access local files from within the container:

```bash
docker run -d \
    --name syft-space \
    --restart unless-stopped \
    -p 8080:8080 \
    -v syft-space-data:/data \
    -v ${HOME}:/root \
    -v ${HOME}/.docker/run/docker.sock:/var/run/docker.sock \
    -e DOCKER_HOST=unix:///var/run/docker.sock \
    --add-host=host.docker.internal:host-gateway \
    ghcr.io/openmined/syft-space:latest
```

### With Environment Variables

Run with custom environment variables for authentication and debugging:

```bash
docker run -d \
    --name syft-space \
    --restart unless-stopped \
    -p 8080:8080 \
    -v syft-space-data:/data \
    -e SYFT_PORT=8080 \
    -e SYFT_DEBUG=true \
    -e SYFT_ADMIN_API_KEY=your-secret-key \
    -e SYFT_SQLITE_DB_PATH=/data/app.db \
    ghcr.io/openmined/syft-space:latest
```

### Using Docker Compose

For more control over configuration, clone the repository and use Docker Compose:

```bash
git clone https://github.com/OpenMined/syft-space.git
cd syft-space
cp .env.example .env
docker compose up -d
```

To stop the server:

```bash
docker compose down
```

To check that it's running:

```bash
curl http://localhost:8080/health
```

## Running from Source

If you prefer to run the code directly:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OpenMined/syft-space.git
   cd syft-space
   ```

2. **Run the quick start script:**
   ```bash
   ./run.sh
   ```

   This script sets up a Python virtual environment and starts the server.

3. **Access the application** at [http://localhost:8080](http://localhost:8080)

### Frontend Development

If you're working on the frontend separately:

```bash
cd frontend
bun install
bun dev
```

The frontend development server runs at [http://localhost:5173](http://localhost:5173).
For detailed reference to frontend and development instructions, see [`frontend/README.md`](frontend/README.md).

## Configuration

The server works out of the box with sensible defaults. For customization, edit the `.env` file or pass environment variables to Docker:

| Variable | Default | Description |
|----------|---------|-------------|
| `SYFT_PORT` | `8080` | Port the server runs on |
| `SYFT_DEBUG` | `false` | Enable detailed logging |
| `SYFT_ADMIN_API_KEY` | (empty) | Set this to require authentication |
| `SYFT_SQLITE_DB_PATH` | `~/.syai-server/app.db` | Path to SQLite database file |

When `SYFT_ADMIN_API_KEY` is empty, the server runs in development mode with no authentication required. Set a value to enable API key authentication.

See `.env.example` for all available options.

## API Docs

Interactive API documentation is available at:

- **Swagger UI:** [http://localhost:8080/docs](http://localhost:8080/docs)

For detailed API reference and backend development instructions, see [`backend/README.md`](backend/README.md).

## Project Structure

```
syft-space/
├── backend/       # Python FastAPI server
├── frontend/      # Vue 3 web interface
├── Dockerfile     # Container build instructions
└── docker-compose.yml
```

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is part of the OpenMined ecosystem. See the repository for license details.
