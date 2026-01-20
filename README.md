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

The fastest way to get started is with Docker:

```bash
# Clone the repository
git clone https://github.com/OpenMined/syft-space.git
cd syft-space

# Copy the example environment file
cp .env.example .env

# Start with Docker Compose
docker compose up -d
```

Open your browser to [http://localhost:8080](http://localhost:8080) to access the application.

## Installation

### Option 1: Using Docker (Recommended)

Docker is the simplest way to run Syft Space Server.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/OpenMined/syft-space.git
   cd syft-space
   ```

2. **Create your environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Start the server:**
   ```bash
   docker compose up -d
   ```

4. **Check that it's running:**
   ```bash
   curl http://localhost:8080/health
   ```

To stop the server:
```bash
docker compose down
```

### Option 2: Running from Source

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

#### Running the Frontend Separately (for development)

If you're working on the frontend:

```bash
cd frontend
bun install
bun dev
```

The frontend development server runs at [http://localhost:5173](http://localhost:5173).
For detailed reference to frontend and development instructions, see [`frontend/README.md`](frontend/README.md).

## Configuration

The server works out of the box with sensible defaults. For customization, edit the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `SYFT_PORT` | `8080` | Port the server runs on |
| `SYFT_DEBUG` | `false` | Enable detailed logging |
| `SYFT_ADMIN_API_KEY` | (empty) | Set this to require authentication |

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
