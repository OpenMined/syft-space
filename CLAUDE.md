# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SyftAI Server is a full-stack application with a FastAPI backend and Vue 3 frontend. The backend uses FastSyftBox framework and serves the frontend as static files from `/syftai-server` subpath. The application includes modular components for accounting, integrations, policies, profiles, services, and settings management.

## Architecture

### Backend Structure (`/backend`)
- **Framework**: FastAPI with FastSyftBox wrapper
- **Structure**: Domain-driven design with components organized by feature
- **Components**: Each component has entities, handlers, interfaces, repositories, routes, and schemas
- **Main Components**:
  - `accounting/` - Financial tracking and billing
  - `integrations/` - External service integrations (Weaviate, vLLM models)
  - `policies/` - Rate limiting and accounting guards
  - `profile/` - User profile management
  - `service/` - Core service functionality
  - `settings/` - Application configuration
  - `shared/` - Common utilities (database, errors, logging)

### Frontend Structure (`/frontend`)
- **Framework**: Vue 3 with Composition API, TypeScript, Tailwind CSS
- **UI Library**: shadcn/ui components (located in `src/components/ui/`)
- **State Management**: Pinia stores
- **Routing**: Vue Router with pages in `src/pages/`
- **Components**: Reusable components in `src/components/`
- **Composables**: Shared logic in `src/composables/`

## Development Commands

### Backend Development
```bash
# Setup and run backend (from project root)
./run.sh

# Manual setup
rm -rf .venv
uv venv -p 3.12
uv pip install -e backend/

# Run server
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8080

# Code quality (from backend/ directory)
black .                    # Format code
isort .                    # Sort imports
flake8 .                   # Lint code
mypy .                     # Type checking
pytest                     # Run tests
```

### Frontend Development
```bash
cd frontend

# Package management (use bun, not npm)
bun install                # Install dependencies
bun add <package>          # Add dependency
bun add -D <package>       # Add dev dependency

# Development
bun dev                    # Start dev server
bun run build              # Build for production
bun run preview            # Preview production build

# Code quality - ALWAYS run these after making changes
bun run lint               # Lint with ESLint and Oxlint
bun run typecheck          # TypeScript type checking
bun run format             # Format code with Prettier

# Testing
bun run test:unit          # Unit tests with Vitest
bun run test:e2e:dev       # E2E tests in development
bun run test:e2e           # E2E tests against production build
```

## Development Patterns

### Backend Patterns
- Each component follows the same structure: entities, handlers, interfaces, repositories, routes, schemas
- Use SQLModel for database models
- Pydantic for request/response schemas
- FastAPI dependency injection for shared services
- Environment-based configuration via `config.py`

### Frontend Patterns
- **UI Components**: Always use shadcn/ui components. If needed component doesn't exist, install with `npx shadcn-vue@latest add <component-name>`
- **Icons**: Use lucide-vue-next icons
- **Styling**: Tailwind CSS classes following existing patterns
- **Forms**: Use shadcn/ui form components with consistent validation
- **File Organization**: 
  - Pages in `src/pages/`
  - Reusable components in `src/components/`
  - UI components in `src/components/ui/`
  - Shared logic in `src/composables/`
  - State management in `src/stores/`

### Code Style
- **Backend**: Black formatting (line-length 88), isort with black profile, type hints required
- **Frontend**: Vue 3 Composition API with `<script setup>`, TypeScript, ESLint + Oxlint for linting

## Server Configuration
- Backend runs on configurable port (default 8080, set via `SYFTBOX_ASSIGNED_PORT`)
- Frontend served from `/syftai-server` subpath
- CORS enabled for localhost:5173 (frontend dev server)
- Uses SyftBox configuration from `~/.syftbox/config.json`
- SQLite database at `~/.syai-server/app.db`

## Important Notes
- The frontend has its own CLAUDE.md with detailed UI component guidance
- Always run lint and typecheck commands after making changes
- Use bun for all frontend package operations
- Backend uses UV for Python package management
- The app serves frontend static files and redirects root to `/syftai-server`