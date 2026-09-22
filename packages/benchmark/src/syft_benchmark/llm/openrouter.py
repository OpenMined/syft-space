"""OpenRouter's model list, turned into catalogue entries.

Their payload carries some twenty fields per model; what is kept here is what a
measurement turns on. The snapshot is a file in the repository, read in diffs,
and a field nobody uses is noise in every one of them.

Three of their fields decide the shape of an entry:

  * **``canonical_slug``** is the dated build behind a name — kept as ``build``.
    The identifier has to be the name the provider will accept in a request,
    which is ``id``; ``build`` is how a later reader sees that the thing behind
    the name moved.

  * **``alias_target``** marks a moving pointer such as
    ``~anthropic/claude-sonnet-latest``. It becomes a ``pins`` entry rather than
    a model of its own: a run under such a name cannot be repeated.

  * **``:free`` and ``:batch``** are routes to the same weights at a different
    price. They become routes on one entry, not three entries each collecting
    its own history.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

MODELS_URL = "https://openrouter.ai/api/v1/models"
SOURCE = "openrouter"

# The request parameters a measurement depends on: ``temperature`` is what the
# monte_carlo block varies, and structured output is how a judge is made to
# answer in a shape that parses.
KEPT_PARAMETERS = frozenset(
    {
        "temperature",
        "seed",
        "structured_outputs",
        "response_format",
        "tools",
        "reasoning",
    }
)

# The suffix after the colon is the route, not the model.
KNOWN_ROUTES = ("free", "batch")

# How long to wait for a list of four hundred models. Generous: this runs on an
# explicit refresh, never in the path of a measurement.
FETCH_TIMEOUT_SECONDS = 60


def fetch(
    url: str = MODELS_URL, *, timeout: int = FETCH_TIMEOUT_SECONDS
) -> list[dict[str, Any]]:
    """The provider's list, raw.

    No key is needed: the catalogue is public, so a refresh works on an
    installation that has not been given one yet.

    Args:
        url: The list's address; overridable for a mirror or a test
        timeout: Seconds to wait

    Returns:
        The provider's model records, as they came

    Raises:
        httpx.HTTPError: the provider did not answer, or answered with an error
        ValueError: the answer was not a model list
    """
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("data")
    if not isinstance(models, list):
        raise ValueError("the model list carries no 'data' array")
    return models


def _base_and_route(model_id: str) -> tuple[str, str]:
    """The model, and the route it was named with.

    An unknown suffix is left alone: more likely a name with a colon in it than
    a route nobody has heard of, and guessing would merge two models into one.
    """
    base, sep, suffix = model_id.partition(":")
    if sep and suffix in KNOWN_ROUTES:
        return base, suffix
    return model_id, ""


def _vendor(model_id: str) -> str:
    """The vendor, from the slug: here the prefix really is one, because this is
    the provider's own namespace and every id carries it."""
    head, sep, _ = model_id.partition("/")
    return head.lower() if sep else ""


def _price(pricing: dict[str, Any], key: str) -> str | None:
    """One price as the provider states it, or None if it does not.

    Kept as a string: these are dollars per token to nine decimal places, and a
    float would round the cheap models to zero.
    """
    value = pricing.get(key)
    if value in (None, ""):
        return None
    return str(value)


def to_entries(
    models: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Catalogue entries and pins, out of the provider's own records.

    Args:
        models: The provider's list, as ``fetch`` returned it

    Returns:
        The entries, ordered by id, and the map of moving names to what each one
        points at today.
    """
    entries: dict[str, dict[str, Any]] = {}
    pins: dict[str, str] = {}

    for raw in models:
        model_id = str(raw.get("id") or "")
        if not model_id:
            continue

        alias_target = raw.get("alias_target")
        if isinstance(alias_target, dict) and alias_target.get("slug"):
            # A redirect, not an entry: applied when a setting is saved.
            pins[model_id] = str(alias_target["slug"])
            continue

        base, route = _base_and_route(model_id)

        entry = entries.get(base)
        if entry is None:
            architecture = raw.get("architecture") or {}
            top_provider = raw.get("top_provider") or {}
            pricing = raw.get("pricing") or {}
            supported = set(raw.get("supported_parameters") or [])
            entry = {
                "id": base,
                "name": str(raw.get("name") or base),
                "vendor": _vendor(base),
                "build": str(raw.get("canonical_slug") or base),
                "context_length": raw.get("context_length"),
                "max_output_tokens": top_provider.get("max_completion_tokens"),
                "input_modalities": sorted(architecture.get("input_modalities") or []),
                "supports": sorted(supported & KEPT_PARAMETERS),
                "pricing": {
                    "prompt": _price(pricing, "prompt"),
                    "completion": _price(pricing, "completion"),
                },
                "retires_on": raw.get("expiration_date") or None,
                "routes": {},
                "aliases": {SOURCE: base},
            }
            entries[base] = entry

        if route:
            entry["routes"][route] = model_id

    return sorted(entries.values(), key=lambda item: item["id"]), pins


def snapshot(
    models: list[dict[str, Any]] | None = None, *, url: str = MODELS_URL
) -> dict[str, Any]:
    """A whole catalogue document for this source.

    Args:
        models: The provider's records; fetched when not given
        url: Where to fetch them from

    Returns:
        The document as it is stored — in the shipped file and in the table.
    """
    raw = fetch(url) if models is None else models
    entries, pins = to_entries(raw)
    return {
        "version": 1,
        "source": SOURCE,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": entries,
        "pins": pins,
    }
