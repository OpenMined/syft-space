<<<<<<< Current (Your changes)
=======
# Welcome to Syft Space

## Collective Intelligence, Individual Control

Syft Space connects knowledge across a decentralized network—each Space contributes while keeping data under its owner's control.

You have valuable knowledge—documents, research, data, expertise. Today, sharing that knowledge often means losing control of it. You either lock it away or give it away. Syft Space offers a third option: **make your knowledge queryable without giving it up**.

A Syft Space is a decentralized node operated by anyone with knowledge to share: a publisher, a research lab, a journalist, an institution, or just an individual. Each Space holds data locally and makes it queryable on terms the operator defines—attribution, control, traceability, payments, or extra layers of privacy-preserving tools if sensitive. Knowledge stays at the source; AI queries it in place.

Like querying a hospital's medical database: you get answers based on their clinical data, but you never see patient records. Or asking questions about a paywalled research journal: you access the knowledge without copying the content. Syft Space respects IP and privacy—you share insights, not sources.

This isn't about locking things down. It's about making the flow of information **accountable**. You can change terms, grant or revoke access, and track exactly how your knowledge is being used—all in real time.

## How It Works (The Simple Version)

A Syft Space has three building blocks:

1. **Your Resources** — the knowledge you want to make queryable
   - **Datasets**: Your documents, files, research papers, or any information you want to share
   - **Models**: The AI that understands questions and generates helpful answers

2. **Endpoints** — the door to the world
   - An endpoint combines your datasets and models into something people can actually use
   - It's a simple address where others can send questions and receive answers

3. **Policies** — your rules
   - Control who can access your endpoints
   - Set usage limits and pricing
   - Track how your knowledge is being used

**That's it.** Resources in, endpoint out, policies to control the flow.

## Who Is This For?

Anyone with knowledge worth sharing:

- **Researchers** who want their papers to be discoverable and citable
- **Organizations** with documentation, FAQs, or internal knowledge bases
- **Data owners** who want to monetize insights without exposing raw data
- **Teams** who need AI-powered search over their collective knowledge
- **Individuals** with expertise they want to make accessible on their terms

If you have knowledge you want to make queryable—on your terms—you can run a Space.

## What Can You Do With It?

- **Answer questions** about your document collections
- **Build AI assistants** trained on your specific knowledge
- **Create help systems** that actually understand your content
- **Share research** in a way that's discoverable and attributable
- **Monetize expertise** without giving away your underlying data

---

## Getting Technical

Ready to dive deeper? Here's what's under the hood.

### The Building Blocks

| Component | What It Does |
|-----------|--------------|
| **Datasets** | Connect to vector databases (Weaviate, Qdrant, ChromaDB) or upload files for automatic indexing |
| **Models** | Configure AI providers (OpenAI, Anthropic, Ollama, vLLM, and more) |
| **Endpoints** | Combine datasets + models into queryable RAG (Retrieval-Augmented Generation) endpoints |
| **Policies** | Rate limiting, access control, usage tracking, and pricing |

### Key Features

- **Multi-database support**: Works with Weaviate, Qdrant, ChromaDB, or remote data sources
- **Multi-model support**: OpenAI, Anthropic, vLLM, Ollama, and other providers
- **Auto-provisioning**: Automatically manages Docker containers for local databases
- **Desktop & web interface**: Run it as an app or deploy as a service
- **Usage analytics**: Monitor costs, tokens, and performance
- **Marketplace integration**: Publish to SyftHub for discovery

### Quick Start

1. **Install** Syft Space (desktop app or Docker)
2. **Set up connectivity** — if running locally (not in a VM), enter your [developer token](#developer-token) during onboarding
3. **Add your resources** — upload documents or connect a database, configure an AI model
4. **Create an endpoint** — combine your dataset and model
5. **Set your policies** — decide who can access and on what terms
6. **Share** — give out your endpoint URL and start answering questions

### Developer Token

Running Syft Space on your local machine? You'll need a **developer token** from OpenMined to make your Space reachable by others. Without a public URL (like you'd have in a VM or cloud deployment), this token creates a secure tunnel so others can query your endpoints.

- **Required for**: Publishing endpoints and receiving queries on local machines
- **Not required for**: VM/cloud deployments with public URLs, or local-only testing
- **How to get one**: Contact OpenMined directly (beta program)
- **Configure in**: Onboarding (first launch) or Settings → Network

```bash
# Example: Query your endpoint
curl -X POST http://localhost:8080/api/v1/endpoints/my-docs/query \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the main topics in my documents?"}
    ]
  }'
```

## Part of the Syft Network

Your Space can connect to **[SyftHub](https://syfthub.openmined.org)**, a registry that maps who has knowledge, what they're willing to share, and how to reach them. You don't need SyftHub to run a Space, but it makes finding and sharing knowledge easier.

When someone queries the network, their request is routed to the relevant Spaces. Each Space that contributes to an answer is tracked—attribution isn't metadata you have to trust, it's built into how the system works.

**Query other Spaces:** Discover and query Spaces shared by others at [syfthub.openmined.org](https://syfthub.openmined.org)

The network gets better as more Spaces join. But the architecture matters: we're building on open protocols so that no single entity—including us—controls the whole. The infrastructure belongs to everyone who participates.

## Next Steps

- [Installation Guide](installation/desktop-app.md) — Get started with the desktop app
- [Components Overview](components/overview.md) — Learn about datasets, models, and endpoints
- [API Reference](api.md) — Integrate with your applications
>>>>>>> Incoming (Background Agent changes)
