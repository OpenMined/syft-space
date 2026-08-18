# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Syft Space Server is a full-stack application with a FastAPI backend and Vue 3 frontend. The backend uses FastSyftBox framework and serves the frontend as static files from `/frontend` subpath. The application includes modular components for accounting, integrations, policies, profiles, services, and settings management.

## Architecture

### Backend Structure (`packages/spaces/backend`)

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

### Frontend Structure (`packages/spaces/frontend`)

- **Framework**: Vue 3 with Composition API, TypeScript, Tailwind CSS
- **UI Library**: shadcn/ui components (located in `src/components/ui/`)
- **State Management**: Pinia stores
- **Routing**: Vue Router with pages in `src/pages/`
- **Components**: Reusable components in `src/components/`
- **Composables**: Shared logic in `src/composables/`

## Development Commands

### Backend Development

```bash
# Setup and run backend (self-cds to packages/spaces)
packages/spaces/run.sh

# Manual setup (from packages/spaces/)
rm -rf .venv
uv venv -p 3.12
uv pip install -e backend/

# Run server
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port 8080

# Code quality (from packages/spaces/backend/ directory)
black .                    # Format code
isort .                    # Sort imports
flake8 .                   # Lint code
mypy .                     # Type checking
pytest                     # Run tests
```

### Frontend Development

```bash
cd packages/spaces/frontend

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
- Frontend served from `/syft-space-server` subpath
- CORS enabled for localhost:5173 (frontend dev server)
- Uses SyftBox configuration from `~/.syftbox/config.json`
- SQLite database at `~/.syai-server/app.db`

## API Integration Guide

### Adding New API Endpoints to Frontend

When integrating a backend API endpoint into the frontend:

1. **Create API types** in `packages/spaces/frontend/src/api/types/index.ts`:

   ```typescript
   export interface MyResponse {
     // Match the backend Pydantic schema
   }
   ```

2. **Add API function** in `packages/spaces/frontend/src/api/endpoints/`:

   ```typescript
   export const myApi = {
     fetch: async (params): Promise<MyResponse> => {
       const response = await apiClient.get('/my-endpoint', { params })
       return response.data
     }
   }
   ```

3. **Create composable** for complex logic in `packages/spaces/frontend/src/composables/`:

   ```typescript
   export function useMyFeature() {
     // Handle loading states, errors, data transformation
   }
   ```

4. **Update components** to use the API through stores or composables

### Example: File Browser Integration

- API types: `packages/spaces/frontend/src/api/types/index.ts`
- API endpoint: `packages/spaces/frontend/src/api/endpoints/datasets.ts`
- Composable: `packages/spaces/frontend/src/composables/useDatasetBrowser.ts`
- Component: `packages/spaces/frontend/src/components/FileExplorer.vue`

## Important Notes

- The frontend has its own CLAUDE.md with detailed UI component guidance
- Always run lint and typecheck commands after making changes
- Use bun for all frontend package operations
- Backend uses UV for Python package management
- The app serves frontend static files and redirects root to `/syft-space-server`

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **redesign_ux** (2333 symbols, 5605 relationships, 171 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/redesign_ux/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/redesign_ux/context` | Codebase overview, check index freshness |
| `gitnexus://repo/redesign_ux/clusters` | All functional areas |
| `gitnexus://repo/redesign_ux/processes` | All execution flows |
| `gitnexus://repo/redesign_ux/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
