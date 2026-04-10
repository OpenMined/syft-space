# Syft Space UX Redesign

## Project Branch: `redesign_ux`

## Vision

Reduce cognitive load by restructuring the app around a two-layer mental model:

1. **Your Resources** — what you have (data sources, models)
2. **Live** — what you've shared with the world (composed from resources + inline rules)

Policies dissolve into inline settings on a "share." The user never thinks about "endpoints" or "policies" as standalone concepts.

---

## Mental Model Analysis

### The Problem

The current app surfaces **67 distinct concepts** a user may encounter. The heaviest flow (Create Data Endpoint) requires ~22 concepts in a single sitting. The flat 4-tab navbar (Home, Datasets, Models, Endpoints) treats everything as peer-level technical jargon.

### The Core Insight

Users have three intentions, not seven concepts:

1. **I have stuff** (data files, AI models)
2. **I want to share it** (with rules about who, how much, how often)
3. **I want to get paid** (optionally)

### Concept Count Target

- **Before**: ~33-40 concepts for first-time data sharing flow
- **After**: ~11 concepts for the same flow (70% reduction)

### Concept Hierarchy

```
Your Space
├── Resources (what you have)
│   ├── Data Sources (files, folders, databases — was "Datasets")
│   └── Models (AI models)
└── Live (what you share — was "Endpoints")
    └── Each live resource has:
        ├── What you're sharing (data source, model, or both as a workflow)
        ├── Response mode (search, AI-generated, or both — data sources only)
        ├── Who can access (was: Authorization policy)
        ├── Usage limits (was: Rate Limiting policy)
        └── Price (was: Pricing policy)
```

### Concept Dependency Chain

The longest dependency chain is 7 levels deep:

```
Syft Space → Dataset → Dataset Type → Watched Paths → Ingestion → Job Statuses
Syft Space → Endpoint → Policy → Pricing → Wallet → MPP → Private Key
```

Advanced concepts (vector DB config, wildcards, rate limit scoping, Ethereum addresses) should be behind progressive disclosure gates, not in primary flows.

---

## Terminology Changes

| Current | New | Status |
|---------|-----|--------|
| Datasets | **Data Sources** | ✅ Done (Phase 1) |
| Endpoints | **Live** | ✅ Done (Phase 1) |
| Published | **Live** | ✅ Done (Phase 1) |
| Draft | **Offline** | ✅ Done (Phase 1) |
| Publish to SyftHub | **Go Live** | ✅ Done (Phase 1) |
| Unpublish | **Take Offline** | ✅ Done (Phase 1) |
| Policy | *(dissolves into inline settings)* | Phase 2 |
| Authorization Policy | **"Who can access?"** | Phase 2 |
| Rate Limiting Policy | **"Usage limits"** | Phase 2 |
| Pricing Policy | **"Price"** | Phase 2 |
| Query | **Query** (kept as-is) | — |
| Slug | Auto-generated, editable as "URL" | Phase 2 |
| Response type | **Response mode** (settings section) | Phase 2 |

---

## Terminology Inconsistencies Found (To Fix)

These exist in the current codebase and should be unified:

| What it is | Sometimes called | Also called |
|------------|-----------------|-------------|
| The thing consumers hit | "Endpoint" | "Resource", "Content" (hero copy) |
| Data source | "Dataset" | "Data source", "Source", "Files" |
| AI model provider | "Provider" | "Source" (create model step 1) |
| Policy | "Policy" | "Rule" (Add Authorization Rule), "Access controls" |

---

## Phase 1: Sidebar Navigation + Terminology (COMPLETE)

### What was built

**New files:**
- `frontend/src/composables/useSidebar.ts` — Reactive collapsed/expanded state with localStorage persistence
- `frontend/src/components/AppSidebar.vue` — Collapsible sidebar with sections:
  - Logo header (collapses to icon-only)
  - Home
  - YOUR RESOURCES: Data Sources, Models
  - LIVE: with live resource count badge
  - Bottom: Inbox (with unread badge), Settings
  - Footer: theme toggle, collapse toggle, user card with email + balance
  - Tooltips on all items when collapsed
  - Active route highlighting with route grouping
- `frontend/src/components/AppLayout.vue` — Flex layout shell:
  - Desktop: sidebar + scrollable content area
  - Mobile: hamburger top bar + Sheet-based drawer overlay

**Modified files:**
- `App.vue` — Replaced `AppNavbar` with `AppLayout`; standalone pages (create flows, onboarding, updates, about) render without sidebar
- `EndpointsPage.vue` — "Your Endpoints" → "Live", "Add Endpoint" → "Go Live"
- `EndpointCard.vue` — "Published" → "Live", "Draft" → "Offline"
- `EndpointDetailPage.vue` — Breadcrumb "Endpoints" → "Live", "Publish" → "Go Live", "Draft" → "Offline"
- `DatasetsPage.vue` — "Your Datasets" → "Your Data Sources"
- `DatasetDetailPage.vue` — Breadcrumb "Datasets" → "Data Sources"
- `HomePage.vue` — Stats: "Datasets" → "Data Sources", "Endpoints" → "Live"; action card: "Go live with your first resource"
- `useNavigation.ts` — Added `goToLive`, `goToDataSources`, `goToAnalytics` with backwards-compatible aliases

**Verification:** TypeScript 0 errors, ESLint + Oxlint 0 errors, Prettier formatted.

**Note:** `AppNavbar.vue` was NOT deleted — kept for reference. The sidebar is the primary navigation now.

---

## Phase 2: Redesigned "Go Live" Flow (NOT STARTED)

### Goal

Replace the 5-step Create Endpoint wizard (~22 concepts) with a streamlined "Go Live" flow (~8 concepts).

### Proposed Flow

**Page 1: What are you sharing?**
- Pick from existing data sources or models (or add new inline)
- If sharing a model directly → skip response mode config

**Page 2: Configure (single page with sections)**

```
RESPONSE (data sources only)
  How should queries be answered?
  ○ Search results     (return matching content)
  ○ AI-generated       (smart answers) → [Select a model ▾]
  ○ Both               (search + AI)   → [Select a model ▾]

ACCESS
  Who can access?
  ○ Everyone
  ○ Specific people ▾  → [email list, wildcards]

LIMITS
  Usage limits
  ○ Unlimited
  ○ Custom ▾           → [amount] per [hour/day ▾]
                       → Scope: [per user / global ▾] (advanced)

PRICE
  ○ Free
  ○ Paid ▾             → $[amount] per query
                       → Apply to: [everyone / specific ▾]
                       → (payment setup prompt if no wallet)
```

Key points:
- Response mode ONLY shows for data sources (not standalone models)
- Model selection appears conditionally via progressive disclosure
- Sensible defaults pre-selected: Everyone, Unlimited, Free
- Advanced options (rate limit scope, per-user pricing, wildcards) expand only when needed

**Page 3: Details (metadata)**
- Name (auto-generates URL slug, editable via "Edit URL" link)
- Short description
- Tags (with suggestions)
- Optional long description

**Page 4: Review & Go Live**
- Summary of configuration
- Single "Go Live" button

### Files to create/modify
- New: `frontend/src/pages/GoLivePage.vue` (or refactor `CreateDataEndpointPage` + `CreateModelEndpointPage` into one)
- New: `frontend/src/composables/useGoLive.ts`
- Modified: `CreateEndpointModal.vue` → points to new flow
- Modified: router to add `/go-live` route
- Keep: `PolicyFormDialog.vue` internals (still used, just invoked differently)
- Keep: All API calls unchanged (`endpointsApi`, `policiesApi`)

### Nothing gets deleted
All backend endpoints remain the same. All API calls remain the same. This is purely a frontend reorganization.

---

## Phase 3: Additional Improvements (NOT STARTED)

### Settings expansion
- Move wallet setup from navbar dropdown to Settings > Payments section
- Multi-section settings: Account, Network, Payments, Appearance

### Detail page updates
- Endpoint detail: show policies as inline settings, not separate cards with "Add Rule" buttons
- Dataset detail: rename to "Data Source" throughout
- Surface analytics tab or link from Live detail

### Dashboard rethink
- Replace hero + action cards with operational dashboard
- Live endpoint stats, ingestion status, recent activity, health indicators

---

## Key Design Principles

1. **Two layers, not four** — Resources (what you have) and Live (what you share)
2. **Progressive disclosure** — Simple defaults expand to advanced options. Nothing disappears; complexity is hidden behind expandable sections.
3. **Unified terminology** — One word per concept used consistently everywhere
4. **Policies dissolve** — They become natural settings (access, limits, price) within the sharing flow, not standalone objects
5. **Wallet is plumbing** — Payment setup lives in Settings, not the main flow. Prompted inline only when user sets a price.

---

## Running the App

```bash
# Backend (from project root)
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port 8080

# Frontend (from frontend/)
bun dev
# Opens at http://localhost:5173/
# Backend CORS allows localhost:5173 only
```

---

## Files Reference

### New files (Phase 1)
- `frontend/src/composables/useSidebar.ts`
- `frontend/src/components/AppSidebar.vue`
- `frontend/src/components/AppLayout.vue`
- `frontend/src/components/ui/sheet/` (shadcn component, installed)

### Key existing files
- `frontend/src/App.vue` — Root layout, sidebar visibility logic
- `frontend/src/router/index.ts` — All routes (route names unchanged, paths unchanged)
- `frontend/src/composables/useNavigation.ts` — Navigation helpers (updated with aliases)
- `frontend/src/stores/endpoints.ts` — Endpoint store (still uses "endpoints" internally)
- `frontend/src/stores/inbox.ts` — Inbox store (mock data, no backend)
- `frontend/src/stores/user.ts` — User/wallet/marketplace state
- `frontend/src/config/policyTypes.ts` — Policy type definitions
- `frontend/src/config/providers.ts` — AI model provider list
- `frontend/DESIGN_STANDARDS.md` — UI component standards
- `frontend/CLAUDE.md` — Frontend development guidelines
