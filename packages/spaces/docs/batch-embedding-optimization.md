# Batch Embedding Optimization (ChromaDB ingest path)

**Status:** implemented
**File:** `backend/syft_space/components/vector_stores/chromadb_local/chromadb_vector_store.py`
**Symbols:** `ChromaDBLocalVectorStore._store_chunks`, `ChromaDBLocalVectorStore.ingest`

## Problem

During ingestion, `_store_chunks` embeds and writes chunks **one at a time** in a
Python `for` loop. For a document that produces N chunks this means:

- **N** separate `asyncio.to_thread(self._generate_embeddings, [one_chunk])` calls
- **N** separate `await collection.add(...)` HTTP round-trips to the ChromaDB server

Each `to_thread` call hops onto the thread pool and runs CPU-bound ONNX inference,
which **holds the Python GIL** while it runs. Doing this N times sequentially keeps
a worker thread (and the GIL) busy for the whole document, so while a large doc is
ingesting the event loop is starved and **every other API response slows down**.
The per-chunk `collection.add` round-trips add N network latencies on top.

Measured effect of GIL-bound background work on API latency (see
`backend/scripts/loadtest_gil.py`): a single background CPU thread raised request
latency ~16x; the cost scales with how long that thread stays busy.

### Current code (for reference)

```python
async def _store_chunks(self, collection, chunks: list[dict]) -> None:
    if not chunks:
        return

    doc_id = chunks[0]["doc_id"]
    chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

    for i, chunk in enumerate(chunks):
        prev_chunk_id = chunk_ids[i - 1] if i > 0 else ""
        next_chunk_id = chunk_ids[i + 1] if i < len(chunks) - 1 else ""

        embeddings = await asyncio.to_thread(
            self._generate_embeddings, [chunk["embedding_text"]]
        )

        await collection.add(
            ids=[chunk_ids[i]],
            documents=[chunk["text"]],
            embeddings=embeddings,
            metadatas=[{ ... }],
        )
```

`_generate_embeddings` already accepts a **list** of texts and returns a list of
vectors — it is batch-capable today; the caller just never uses it that way.
`collection.add` likewise accepts parallel lists for `ids` / `documents` /
`embeddings` / `metadatas`.

## Proposed change

Embed **all chunks of a document in one `to_thread` call**, then write them in a
**single `collection.add`**. This collapses 2N hops into 2, and the one CPU burst
is shorter and bounded (one ONNX batch) instead of N interleaved bursts.

```python
async def _store_chunks(self, collection, chunks: list[dict]) -> None:
    if not chunks:
        return

    doc_id = chunks[0]["doc_id"]
    n = len(chunks)
    chunk_ids = [f"{doc_id}_{i}" for i in range(n)]

    # One batched embedding call for the whole document (ONNX batches internally).
    embedding_texts = [c["embedding_text"] for c in chunks]
    embeddings = await asyncio.to_thread(self._generate_embeddings, embedding_texts)

    metadatas = [
        {
            "doc_id": doc_id,
            "chunk_index": i,
            "prev_chunk_id": chunk_ids[i - 1] if i > 0 else "",
            "next_chunk_id": chunk_ids[i + 1] if i < n - 1 else "",
            "file_name": chunk["file_name"],
            "file_type": chunk["file_type"] or "",
            "file_size": chunk["file_size"],
            "page_numbers": ",".join(map(str, chunk["page_numbers"])),
            "headings": " > ".join(chunk["headings"]),
            "picture_ids": ",".join(chunk["picture_ids"]),
        }
        for i, chunk in enumerate(chunks)
    ]

    # Single write for the whole document.
    await collection.add(
        ids=chunk_ids,
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=metadatas,
    )
```

The neighbor pointer logic (`prev_chunk_id` / `next_chunk_id`) is preserved exactly
— it was already derived purely from index position, so batching does not change it.

### Optional: cap very large batches

For a pathologically large document, a single `add` payload and one ONNX batch could
get big (memory / request size). If that turns out to matter, chunk the batch into
fixed-size windows (e.g. 256) and still get the bulk of the win:

```python
BATCH = 256
for start in range(0, n, BATCH):
    sl = slice(start, start + BATCH)
    embeddings = await asyncio.to_thread(
        self._generate_embeddings, embedding_texts[sl]
    )
    await collection.add(
        ids=chunk_ids[sl],
        documents=[c["text"] for c in chunks[sl]],
        embeddings=embeddings,
        metadatas=metadatas[sl],
    )
```

This still yields between the loop the right number of times to let other tasks run,
while keeping each CPU burst bounded.

## Why this helps the "all APIs are slow" symptom

- Fewer, shorter GIL-holding bursts → the event loop gets the GIL back sooner → other
  API requests stop stalling during ingestion.
- 2 network round-trips per document instead of 2N → ingestion itself is much faster,
  so the window during which the server is under load shrinks.

## Expected behavior changes / risks

- **Functional output is identical**: same ids, documents, embeddings, metadata, and
  neighbor pointers. Only the call batching changes.
- **Atomicity**: today a crash mid-loop leaves a partially-written document (some
  chunks present). With a single `add` the document is written all-or-nothing per
  batch — arguably an improvement, but worth noting if any downstream code relies on
  partial writes.
- **Memory**: one batch holds all chunk embeddings in memory briefly. For normal docs
  this is small; use the capped variant above if huge documents are expected.
- **`ingest` loop unchanged**: `ingest` still parses + stores one file at a time
  (`for file in request.files:`). This change is scoped to within a single document's
  chunk write. Batching across files is a separate, larger change.

## Further optimization (out of scope here)

To fully escape the GIL for embeddings, run `_generate_embeddings` in a
`ProcessPoolExecutor` instead of `asyncio.to_thread` (mirrors how PDF page conversion
already uses a subprocess in `chunking.py`). That removes ONNX inference from the
main process entirely. Larger change; not required for the batching win above.

## Testing checklist

- Ingest a multi-chunk document; verify chunk count, ids, and `prev/next_chunk_id`
  pointers match the pre-change output.
- Verify search still returns neighbor context (`_enrich_with_neighbor_context`
  depends on the pointer metadata).
- Ingest while hitting `/api/v1/health` and a list endpoint concurrently; confirm
  request latency / event-loop lag is lower than before (reuse
  `backend/scripts/loadtest_blocking.py` as a harness).
- Empty-chunk document (`chunks == []`) still early-returns.
