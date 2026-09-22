"""The catalogue of models: one identity per model, whoever serves it.

A model has **one identifier**, the vendor-namespaced slug
``anthropic/claude-sonnet-5``, and the provider's own name for it is a detail of
transport. That is what lets an installation move from one provider to another
without rewriting its settings or losing the comparability of what it measured
before.

``build`` carries the dated snapshot a provider serves under that name today. It
is recorded, not part of the identity: treating two builds as one model averages
incomparable numbers, and splitting them loses a model's history the day its
vendor refreshes it. The number is reported; the judgement is the reader's.

The catalogue is not a whitelist. A model released this morning is in no
snapshot, and an identifier nobody recognises passes through marked as unknown —
refusing it would make the form less capable than a text box.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from syft_benchmark.config import Settings
from syft_benchmark.llm.providers import ProviderKind

# The settings that hold model identifiers. One list: the form description marks
# these fields as catalogue-backed, and the write path pins their values.
MODEL_FIELDS: tuple[str, ...] = (
    "generator_model",
    "judge_model",
    "subject_models",
    "judge_models",
)

# The snapshot that ships with the code: the floor under the table, read
# wherever a refresh has stored nothing newer. It is what lets an installation
# with no way out of the perimeter still draw a form with models in it.
DATA_PACKAGE = "syft_benchmark.data"
SNAPSHOT_FILE = "models.json"


class ModelEntry(BaseModel):
    """One model, as this installation knows it."""

    id: str = Field(description="The identifier this service uses, everywhere")
    name: str = Field(description="What to show a person")
    vendor: str = Field(default="", description="Who made it. Empty — a local model")
    build: str = Field(
        default="",
        description="The dated build behind the name today; reported, not identity",
    )
    context_length: int | None = None
    max_output_tokens: int | None = None
    input_modalities: list[str] = Field(default_factory=list)
    supports: list[str] = Field(
        default_factory=list,
        description=(
            "The request parameters it honours. Without 'temperature' it cannot "
            "serve the monte_carlo block, which is nothing but varied temperature"
        ),
    )
    pricing: dict[str, str | None] = Field(default_factory=dict)
    retires_on: str | None = Field(
        default=None, description="The date the provider withdraws it, if it said one"
    )
    routes: dict[str, str] = Field(
        default_factory=dict,
        description="Cheaper or slower ways to the same weights: free, batch",
    )
    aliases: dict[str, str] = Field(
        default_factory=dict, description="The name each provider knows it by"
    )
    source: str = Field(default="", description="Which catalogue it came from")
    local: bool = Field(default=False, description="Served from inside the perimeter")


@dataclass(frozen=True, slots=True)
class Catalog:
    """Every model this installation can offer, and what it knows about them."""

    models: dict[str, ModelEntry] = field(default_factory=dict)
    # A moving name -> what it resolves to today. A setting that keeps
    # ``~anthropic/claude-sonnet-latest`` keeps a measurement nobody can repeat.
    pins: dict[str, str] = field(default_factory=dict)
    # Source -> when it was last fetched. A catalogue whose age is invisible is
    # one nobody thinks to refresh.
    fetched: dict[str, str] = field(default_factory=dict)

    def get(self, model: str) -> ModelEntry | None:
        """The entry for an identifier, or None if it is not in the catalogue."""
        return self.models.get(self.pin(model))

    def pin(self, model: str) -> str:
        """A moving name replaced by what it points at; anything else unchanged."""
        return self.pins.get(model, model)

    def vendor_of(self, model: str) -> str:
        """Who made this model.

        The catalogue first, then the namespace in the identifier — the
        convention every gateway follows, so a model newer than the snapshot is
        still attributed. A name with no namespace is a local model and has no
        vendor; the judge-independence check compares those by name instead.
        """
        entry = self.get(model)
        if entry is not None:
            return entry.vendor
        head, sep, _ = self.pin(model).partition("/")
        return head.lower() if sep else ""

    def native(self, model: str, kind: ProviderKind) -> str:
        """The name to put in the request to this kind of provider.

        Args:
            model: Our identifier
            kind: Whose API is about to be called

        Returns:
            The provider's own name for the model, or the identifier itself when
            nothing better is known.
        """
        pinned = self.pin(model)
        entry = self.models.get(pinned)
        if entry is not None:
            alias = entry.aliases.get(kind.value)
            if alias:
                return alias

        if kind in (ProviderKind.OPENAI, ProviderKind.ANTHROPIC):
            # A vendor's own API does not repeat the vendor: "anthropic/x" is
            # "x" at Anthropic. Only that vendor's own prefix comes off —
            # stripping any would turn a Llama into an Anthropic model.
            head, sep, rest = pinned.partition("/")
            if sep and head.lower() == kind.value:
                return rest

        return pinned

    def search(
        self,
        *,
        query: str = "",
        vendor: str = "",
        supports: tuple[str, ...] = (),
        include_retired: bool = False,
        limit: int = 0,
    ) -> list[ModelEntry]:
        """The models matching a form's filters.

        Args:
            query: Free text; matched against the identifier and the shown name
            vendor: Only this vendor
            supports: Only models honouring all of these request parameters
            include_retired: Whether to keep models with a withdrawal date
            limit: Cap on the answer; zero — no cap

        Returns:
            Local models first, then the rest by identifier: the generator works
            over documents and belongs inside the perimeter.
        """
        needle = query.strip().lower()
        wanted = vendor.strip().lower()
        found: list[ModelEntry] = []

        for entry in self.models.values():
            if wanted and entry.vendor != wanted:
                continue
            if (
                needle
                and needle not in entry.id.lower()
                and needle not in entry.name.lower()
            ):
                continue
            if supports and not set(supports).issubset(entry.supports):
                continue
            if entry.retires_on and not include_retired:
                continue
            found.append(entry)

        found.sort(key=lambda item: (not item.local, item.id))
        return found[:limit] if limit > 0 else found

    def vendors(self) -> list[str]:
        """Every vendor present, for the picker's filter."""
        return sorted({entry.vendor for entry in self.models.values() if entry.vendor})


def _document_entries(
    document: dict[str, Any],
) -> tuple[list[ModelEntry], dict[str, str]]:
    """One catalogue document, validated into entries.

    A malformed entry is dropped with a line in the log: a catalogue that
    refuses to load leaves the form with no models at all.
    """
    source = str(document.get("source") or "")
    entries: list[ModelEntry] = []
    for raw in document.get("models") or []:
        try:
            entries.append(ModelEntry.model_validate({**raw, "source": source}))
        except ValueError as error:
            logger.warning(f"catalogue {source}: skipping a model — {error}")
    pins = {str(k): str(v) for k, v in (document.get("pins") or {}).items()}
    return entries, pins


def from_documents(documents: list[dict[str, Any]]) -> Catalog:
    """A catalogue assembled out of the documents of every source.

    Later documents win on a clash of identifiers. The order is the caller's:
    the shipped snapshot goes in first, what a refresh stored goes in after it.
    """
    models: dict[str, ModelEntry] = {}
    pins: dict[str, str] = {}
    fetched: dict[str, str] = {}

    for document in documents:
        entries, document_pins = _document_entries(document)
        for entry in entries:
            models[entry.id] = entry
        pins.update(document_pins)
        source = str(document.get("source") or "")
        if source:
            fetched[source] = str(document.get("fetched_at") or "")

    return Catalog(models=models, pins=pins, fetched=fetched)


def shipped() -> dict[str, Any]:
    """The snapshot that travels with the code.

    Returns:
        The document, or an empty one when the file cannot be read. A missing
        snapshot must not stop the service.
    """
    try:
        text = (resources.files(DATA_PACKAGE) / SNAPSHOT_FILE).read_text("utf-8")
        document: dict[str, Any] = json.loads(text)
        return document
    except (OSError, ValueError, ModuleNotFoundError) as error:
        logger.warning(f"the shipped model catalogue could not be read: {error}")
        return {}


# Kept for the life of the process: read on every form draw, every settings
# write and once per role when a run starts, and changed only by a refresh.
_cached: Catalog | None = None


def invalidate() -> None:
    """Forget the assembled catalogue. Called after a refresh."""
    global _cached
    _cached = None


def stored(settings: Settings | None = None) -> list[dict[str, Any]]:
    """The catalogue documents a refresh has stored, oldest source first.

    Returns:
        The stored documents, or an empty list when the table cannot be read —
        the shipped snapshot stands behind it, so this is never worth raising.
    """
    from sqlalchemy import select

    from syft_benchmark.db.models import ModelCatalog
    from syft_benchmark.db.session import session_scope

    try:
        with session_scope(settings) as session:
            rows = session.scalars(select(ModelCatalog).order_by(ModelCatalog.source))
            return [row.document for row in rows if isinstance(row.document, dict)]
    except Exception as error:  # noqa: BLE001 — see the docstring
        logger.warning(f"the stored model catalogue could not be read: {error}")
        return []


def load(settings: Settings | None = None) -> Catalog:
    """The catalogue this installation goes by.

    The shipped snapshot with whatever a refresh has stored laid over it.
    """
    global _cached
    if _cached is None:
        _cached = from_documents([shipped(), *stored(settings)])
    return _cached


def pin_values(
    values: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any]:
    """The same settings with every moving model name replaced by what it means.

    Done as a setting is saved, not as a run starts: ``~vendor/thing-latest``
    points at a different model every few months, so resolved at run time the
    stored configuration would describe a measurement nobody can repeat.

    Args:
        values: A settings document, or the overrides of one layer
        settings: The settings, for reaching the stored catalogue

    Returns:
        A copy with the model fields pinned. Fields that are not there stay not
        there — an absent setting means "inherit" and must not become a value.
    """
    catalogue = load(settings)
    out = dict(values)
    for name in MODEL_FIELDS:
        if name not in out:
            continue
        current = out[name]
        if isinstance(current, str):
            out[name] = catalogue.pin(current)
        elif isinstance(current, list):
            out[name] = [
                catalogue.pin(item) if isinstance(item, str) else item
                for item in current
            ]
    return out


def replace(document: dict[str, Any], settings: Settings | None = None) -> Catalog:
    """Store a freshly fetched catalogue for its source and reload.

    A replacement, not a merge: a model the provider has stopped serving must
    stop being offered, and a merged one would look configured and fail at the
    first call.

    Args:
        document: A whole catalogue document, as ``openrouter.snapshot`` builds
        settings: The settings, for reaching the database

    Returns:
        The catalogue as it now stands, with the new document in it

    Raises:
        ValueError: the document names no source
    """
    from syft_benchmark.db.models import ModelCatalog
    from syft_benchmark.db.session import session_scope

    source = str(document.get("source") or "")
    if not source:
        raise ValueError("a catalogue document must say which source it came from")

    with session_scope(settings) as session:
        row = session.get(ModelCatalog, source)
        if row is None:
            row = ModelCatalog(source=source)
            session.add(row)
        row.document = document
        row.fetched_at = datetime.now(UTC)
        row.model_count = len(document.get("models") or [])

    invalidate()
    return load(settings)
