# Collectives UI - Setup & Overview

## What Was Created

A separate, simplified UI application for managing Data Collectives has been created in the `collectives-ui/` folder. This application runs independently from the main SyftAI Space frontend and focuses exclusively on collective management features.

## Architecture Overview

### Separate Applications

1. **Main Frontend** (`frontend/`) - Port 5173
   - Manages datasets, models, and endpoints
   - **Updated to include collective features:**
     - Collective hosting option when creating datasets/models (already implemented in `CreateResourceDialog.vue`)
     - Collective membership section in Settings page
     - Collective membership request example in Inbox

2. **Collectives UI** (`collectives-ui/`) - Port 5174
   - Simplified UI for collective administrators and members
   - Create and manage collectives
   - Handle member requests and invitations
   - Configure collective terms (pricing and access)
   - Manage multi-tenancy hosting

## Getting Started

### Prerequisites

- Node.js ^20.19.0 or >=22.12.0
- npm or equivalent package manager

### Installation

```bash
# Navigate to the collectives-ui directory
cd collectives-ui

# Install dependencies
npm install
```

### Running the Applications

```bash
# Terminal 1 - Run main frontend (port 5173)
cd frontend
npm run dev

# Terminal 2 - Run collectives UI (port 5174)
cd collectives-ui
npm run dev
```

The applications will be available at:
- Main Frontend: http://localhost:5173
- Collectives UI: http://localhost:5174

## Features Implemented

### Collectives UI (`collectives-ui/`)

#### 1. Home Page
- Overview dashboard showing collective statistics
- Quick access cards to key features
- List of user's collectives

#### 2. Collectives Management
- **Create Collective** (`/create`)
  - Basic information (name, slug, description)
  - Configure capabilities:
    - Collective Endpoint (unified query endpoint)
    - Multi-Tenancy Hosting (subdomain provisioning)
    - Member Vetting (approval workflow)
    - Collective Terms (shared pricing/access policies)
  - Membership visibility (anyone can join vs. invite-only)

- **Collective Detail** (`/collectives/:slug`)
  - Tabbed interface:
    - **Overview**: About, capabilities, membership visibility
    - **Members**: List of members with roles and subdomain status
    - **Terms**: Pricing and access terms configuration
    - **Settings**: Collective configuration (admin only)
  - Invite members functionality

- **Collectives List** (`/collectives`)
  - Grid view of all user's collectives
  - Shows role (admin/member) and key capabilities

#### 3. Requests Management (`/requests`)
- View pending membership requests
- Approve or reject requests
- Statistics on pending/approved/rejected requests
- Detailed request information with user messages

### Main Frontend Updates (`frontend/`)

#### 1. Settings Page (Updated)
- **Collectives Section** added
- Shows collectives the user is a member of
- Displays collective domain and role
- Empty state when not a member of any collective

#### 2. Inbox (Updated)
- **Collective Membership Request** example added
- Item source: "Collective Membership"
- Shows invitation details and benefits
- Accept/Reject actions

#### 3. Dataset/Model Creation (Already Implemented)
- **Host Collective** dropdown in `CreateResourceDialog.vue`
- Optional selection of collective for hosting
- Available for both datasets and models
- Shows collective domain (e.g., "Harvard (irina.harvard.syftbox.net)")

## Data Flow & Integration

### Mock Data
The collectives UI uses mock data stored in `collectives-ui/src/stores/collectives.ts`:
- Sample collectives (Harvard, TCP Collective)
- Sample members with roles and subdomain status
- Sample membership requests
- Pricing tiers and access rules

### Integration Points
While the applications run separately, they share the same conceptual data model:

1. **User's Collectives**: Settings page shows collectives the user is part of
2. **Collective Hosting**: When creating datasets/models, users can select a collective to host under
3. **Membership Requests**: Inbox receives collective membership invitations
4. **Collective Terms**: Endpoints can adopt collective pricing and access terms (configured in endpoint creation flow)

## Product Spec Implementation

The implementation follows the Data Collectives Product Spec:

### Option 2 - Collective-Hosted Infra, Member Fully Control & Configure
✅ Members configure through the main frontend (datasets, models, endpoints)
✅ Collectives manage infrastructure through the collectives UI
✅ Hosting location selection available when creating resources
✅ Members retain control over their policies and pricing

### Key Features

1. **Collective Creation & Profile** ✅
   - Create collectives with name, slug, description
   - Configure capabilities (endpoint, hosting, vetting, terms)
   - Set membership visibility

2. **Membership Management** ✅
   - Review join requests
   - Invite members
   - Manage member roles
   - Track subdomain utilization

3. **Collective Terms** ✅
   - Structure for pricing tiers
   - Structure for access rules
   - (Full configuration UI can be expanded)

4. **Hosting Management** ✅
   - Multi-tenancy subdomain concept
   - Subdomain status tracking (utilized/not-utilized)

5. **Collective Endpoint** ✅
   - Concept demonstrated in capabilities
   - Unified query endpoint structure

## File Structure

```
collectives-ui/
├── src/
│   ├── components/
│   │   ├── ui/              # Shared UI component library (copied from main frontend)
│   │   └── ...
│   ├── lib/                 # Utility functions
│   ├── pages/
│   │   ├── HomePage.vue              # Dashboard
│   │   ├── CollectivesPage.vue       # List of collectives
│   │   ├── CollectiveDetailPage.vue  # Collective detail with tabs
│   │   ├── CreateCollectivePage.vue  # Create new collective
│   │   ├── RequestsPage.vue          # Membership requests
│   │   ├── MembersPage.vue           # Members management (placeholder)
│   │   ├── CollectiveTermsPage.vue   # Terms config (placeholder)
│   │   └── CollectiveSettingsPage.vue # Settings (placeholder)
│   ├── router/
│   │   └── index.ts         # Route configuration
│   ├── stores/
│   │   └── collectives.ts   # Pinia store with mock data
│   ├── App.vue              # Main app component with navigation
│   ├── main.ts              # App entry point
│   └── style.css            # Global styles
├── public/
│   └── favicon.svg
├── package.json
├── vite.config.ts
├── tsconfig.json
├── README.md
└── .gitignore
```

## Design Principles

The Collectives UI follows these design principles:

1. **Simplified Interface**: Cleaner, more focused UI than main frontend
2. **Consistent Styling**: Uses same design tokens and component library
3. **Role-Based Features**: Shows different options for admins vs. members
4. **Progressive Disclosure**: Advanced features are collapsed by default
5. **Clear Navigation**: Simple top navigation with distinct sections

## Next Steps & Extensions

To further develop the collectives functionality:

1. **Backend Integration**
   - Replace mock data with API calls
   - Implement real collective creation and management
   - Add authentication and authorization

2. **Full Terms Configuration**
   - Complete UI for pricing tiers management
   - Complete UI for access rules management
   - Allow members to adopt terms in endpoint creation

3. **Analytics Dashboard**
   - Collective-level analytics
   - Member-level analytics
   - Revenue tracking and attribution

4. **Collective Endpoint Implementation**
   - Actual query routing logic
   - Response aggregation
   - Pricing calculation across members

5. **Advanced Features**
   - Member onboarding workflow
   - Subdomain provisioning automation
   - Collective branding customization
   - Notification system for requests

## Testing

To test the collectives functionality:

1. Start both applications
2. In Collectives UI:
   - Create a new collective
   - View collective details
   - Review membership requests
   - Invite members
3. In Main Frontend:
   - Check Settings > Collectives section
   - Check Inbox for collective membership request
   - Create a dataset/model and select a collective for hosting
   - Create an endpoint and associate with a collective

## Support & Documentation

For more information:
- Product Spec: See the data collectives product specification
- Main Frontend: `frontend/README.md`
- Collectives UI: `collectives-ui/README.md`
- Design Standards: `frontend/DESIGN_STANDARDS.md`


