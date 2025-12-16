# Collectives UI

A simplified UI for managing Data Collectives in the SyftAI ecosystem.

## Overview

This application provides collective administrators and members with tools to:
- Create and manage collectives
- Handle member requests and invitations
- Configure collective terms (pricing and access)
- Manage multi-tenancy hosting
- View collective analytics

## Getting Started

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Architecture

This is a simplified version of the main SyftAI Space frontend, focused exclusively on collective management features.

### Key Features

1. **Collective Creation & Profile**
   - Create new collectives
   - Configure collective capabilities
   - Public profile visibility

2. **Membership Management**
   - Review join requests
   - Invite members
   - Manage member roles

3. **Collective Terms**
   - Define pricing tiers
   - Set access rules

4. **Hosting Management**
   - Multi-tenancy subdomain provisioning
   - Hosting status monitoring

5. **Collective Endpoint**
   - Unified query endpoint
   - Request routing and aggregation

## Port

Runs on port **5174** by default (different from main frontend on 5173).


