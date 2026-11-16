"""One-off rewrite of comma-joined list metadata into arrays.

Chunks written before list fields became arrays hold ``"a,b"`` strings,
which ``$contains`` never matches. ``collection.update`` merges per key
and leaves documents and embeddings alone, so only the changed keys of
the changed chunks are written back. A collection is marked in its own
metadata once done, so a restart skips it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from loguru import logger

from syft_space.components.shared.metadata_types import MetadataType

__all__ = [
    "MIGRATED_FLAG",
    "migrate_collection",
    "migrate_datasets",
    "split_legacy_lists",
]

MIGRATED_FLAG = "list_fields_as_arrays"
_BATCH = 500

# How each list key was joined before arrays; anything else used a comma.
_SEPARATORS = {"headings": " > "}


def split_legacy_lists(
    metadata: dict[str, Any], list_fields: dict[str, MetadataType]
) -> dict[str, Any]:
    """The keys to rewrite for one chunk: a list, or None to drop an empty one.

    A tag that itself held a comma splits in two; the join was already lossy.
    """
    changed: dict[str, Any] = {}
    for key, type in list_fields.items():
        value = metadata.get(key)
        if not isinstance(value, str):
            continue
        parts = [p.strip() for p in value.split(_SEPARATORS.get(key, ","))]
        parts = [p for p in parts if p]
        if type is MetadataType.NUMBER_LIST:
            try:
                parts = [_number(p) for p in parts]
            except ValueError:
                continue  # not ours to guess; leave the string
        changed[key] = parts or None
    return changed


def _number(text: str) -> int | float:
    return float(text) if "." in text else int(text)


async def migrate_collection(
    collection: Any, list_fields: dict[str, MetadataType]
) -> int:
    """Rewrite every chunk of ``collection`` whose list fields are strings.

    Returns the number of chunks changed. Batches are independent, so a
    failure mid-way leaves the flag unset and the next start resumes.
    """
    if not list_fields or (collection.metadata or {}).get(MIGRATED_FLAG):
        return 0

    changed = 0
    offset = 0
    while True:
        page = await collection.get(limit=_BATCH, offset=offset, include=["metadatas"])
        ids = page["ids"]
        if not ids:
            break
        update_ids: list[str] = []
        update_metas: list[dict[str, Any]] = []
        for id, meta in zip(ids, page["metadatas"] or [], strict=False):
            delta = split_legacy_lists(meta or {}, list_fields)
            if delta:
                update_ids.append(id)
                update_metas.append(delta)
        if update_ids:
            await collection.update(ids=update_ids, metadatas=update_metas)
            changed += len(update_ids)
        offset += len(ids)

    await collection.modify(
        metadata={**(collection.metadata or {}), MIGRATED_FLAG: True}
    )
    if changed:
        logger.info(f"Rewrote list metadata of {changed} chunks in {collection.name}")
    return changed


async def migrate_datasets(
    datasets: Iterable[Any], dataset_type_for: Callable[[str], type]
) -> None:
    """Run the rewrite for every dataset whose store supports it.

    Builds only the vector store, never the source, and logs a failure
    instead of raising so one dataset cannot block the others.
    """
    for dataset in datasets:
        try:
            cls = dataset_type_for(dataset.dtype)
        except KeyError:
            continue
        store_cls = getattr(cls, "VECTOR_STORE_CLS", None)
        if not hasattr(store_cls, "migrate_list_fields"):
            continue
        try:
            _, store_cfg = cls.split_config(dataset.configuration)
            store = store_cls(store_cfg)
            await store.migrate_list_fields(cls.metadata_for(dataset.configuration))
        except Exception as e:
            logger.warning(f"List metadata rewrite skipped for '{dataset.name}': {e}")
