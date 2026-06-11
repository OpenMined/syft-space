# Syft Space Backend — Documentation

The Syft Space backend is a **FastAPI RAG platform** (retrieval-augmented
generation — search your documents, then let an LLM answer from what it found).
You connect **datasets** (documents indexed in a vector store) and **models**
(OpenAI-compatible LLMs),
combine them into **endpoints**, protect those endpoints with **policies**
(access, rate limits, payments), and **publish** them to the SyftHub
marketplace where others can query them — without ever handing over your raw data.

```
[Your data] + [An AI model] → [A queryable endpoint] + [Your rules] = controlled knowledge sharing
```

## Start here

| If you want to… | Read |
| --- | --- |
| Install it and create your first endpoint | [Getting Started](./getting-started.md) |
| Understand how the pieces fit together | [Architecture](./architecture.md) |
| Learn the domain model (datasets, sources, policies, …) | [Core Concepts](./concepts.md) |
| Call the HTTP API | [API Overview](./api-overview.md) |
| Trace exactly what happens during a query | [Query Flow](./query-flow.md) |
| Charge for queries (wallets, invoices, crypto) | [Payments & Wallets](./payments.md) |
| Add a new source, vector store, model, or policy | [Extending the Platform](./extending.md) |
| Configure env vars, auth, multi-tenancy, Docker | [Configuration](./configuration.md) |
| Work with the database schema | [Database Migrations](./migrations.md) |

## The 30-second mental model

- A **Source** answers *“where does the data come from?”* (e.g. local files).
- A **Vector Store** answers *“where is it indexed for search?”* (e.g. ChromaDB).
- A **Dataset Type** is a **binding** of one source to one vector store
  (e.g. `local_file` = local files → ChromaDB).
- A **Dataset** is a configured instance of a dataset type.
- A **Model** is a configured LLM (currently OpenAI-compatible).
- An **Endpoint** combines a dataset and/or a model and answers queries as
  `raw` (search hits), `summary` (LLM answer), or `both` (RAG).
- A **Policy** is a pre/post hook on an endpoint — access control, rate
  limiting, PII filtering, or payment.
- A **Wallet** stores payment credentials; **Payments** track the money
  (invoices, balances, receipts).

See [Core Concepts](./concepts.md) for the full picture.

## Conventions used in these docs

- **Diagrams are [Mermaid](https://mermaid.js.org/)** — they render natively on
  GitHub and most Markdown viewers.
- The **live, exhaustive API reference** is served by the running app at
  `/docs` (Swagger UI) and `/openapi.json`. These docs describe the *shape* and
  *intent* of the API, not every field — the OpenAPI schema is the source of truth.
</content>
</invoke>
