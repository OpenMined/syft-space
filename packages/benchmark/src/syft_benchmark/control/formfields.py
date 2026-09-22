"""A description of the settings fields — so anyone can draw the form.

The UI lives in the Space, while the settings belong to the benchmark. The
Space could have repeated their list on its own side, and at first that would
have been simpler; but then every new field here would mean a migration there,
and a forgotten migration would mean a form that silently cannot configure
something that already works.

So what goes out is not a form but the **shape** of the fields: name, type,
bounds, allowed values, group. It is drawn by whoever has to display it.

There are deliberately no labels here. This is the same rule under which the
card hands over ``trust.flags`` as codes: the wording belongs to whoever is
displaying it, and in their reader's language. A field description in one
language arriving in a UI in another is not a translation, it is a breakage.

The group is the only concession to display, and it is a code too. Without it
forty fields would lie in one column in declaration order, and "similarity
threshold" would end up between "the panel of judges" and "the freshness
window".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from syft_benchmark.config import Settings, stored_fields
from syft_benchmark.control.schemas import Instrument, Probe
from syft_benchmark.llm.catalog import MODEL_FIELDS

# Field groups. Codes, not headings: the heading is written by the displayer.
ARMS = "arms"
MODELS = "models"
JUDGING = "judging"
DATASET = "dataset"
ENDPOINT = "endpoint"
RUN = "run"
PROVIDERS = "providers"
INDEX = "index"

GROUPS: dict[str, str] = {
    # --- the instrument
    "arms": ARMS,
    "blocks": ARMS,
    "denial_rounds": ARMS,
    "monte_carlo_temperatures": ARMS,
    "monte_carlo_trials": ARMS,
    "context_source": ARMS,
    "context_docs": ARMS,
    "generator_model": MODELS,
    "subject_models": MODELS,
    "judge_model": MODELS,
    "judge_models": MODELS,
    "judge_policy": JUDGING,
    "key_facts_threshold": JUDGING,
    "answer_coverage_threshold": JUDGING,
    "consistency_floor": JUDGING,
    "text_metrics": JUDGING,
    "extractive_mode": DATASET,
    "methodology_profile": RUN,
    "max_consecutive_failures": RUN,
    "reuse_answers": RUN,
    "audit_log": RUN,
    # --- the node probe
    "dataset_mode": DATASET,
    "document_window_days": DATASET,
    "dataset_max_pairs": DATASET,
    "disabled_generators": DATASET,
    "chunks_per_run": DATASET,
    "pairs_per_chunk": DATASET,
    "min_chunk_chars": DATASET,
    "generate_in_cycle": DATASET,
    "retrieval_top_k": ENDPOINT,
    "similarity_threshold": ENDPOINT,
    "endpoint_max_tokens": ENDPOINT,
    "endpoint_temperature": ENDPOINT,
    "endpoint_concurrency": ENDPOINT,
    # --- the installation's own layer, under both
    #
    # Where a model is reached and with what patience. The keys are not here
    # and cannot be: they are secrets, they are sealed, and `stored_fields`
    # leaves them out of this catalogue by construction.
    "ollama_url": PROVIDERS,
    "generator_url": PROVIDERS,
    "subject_url": PROVIDERS,
    "judge_url": PROVIDERS,
    "llm_app_name": PROVIDERS,
    "llm_timeout": PROVIDERS,
    "llm_temperature": PROVIDERS,
    "answer_max_tokens": PROVIDERS,
    "bertscore_model": PROVIDERS,
    # The Space's index, as this installation reaches it.
    "chroma_tenant": INDEX,
    "chroma_database": INDEX,
    "chroma_internal_port": INDEX,
    # How a run behaves, as against what it measures.
    "concurrency": RUN,
    "resume": RUN,
    "resume_window_hours": RUN,
    "question_set": RUN,
    "strict_question_set": RUN,
    "audit_max_chars": RUN,
    "spacy_models": DATASET,
}


# A field whose values come from a list too long to inline. ``choices`` carries
# its own — three arms, four blocks; three hundred models cannot travel that
# way and change on a refresh rather than on a release, so the field names the
# catalogue and the form fetches it from ``/models``. Naming these fields on the
# other side instead is the coupling ``/schema`` exists to prevent.
CATALOGUES: dict[str, str] = dict.fromkeys(MODEL_FIELDS, "models")


def _unwrap(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Strip ``anyOf`` with null and unwrap a reference to an enum.

    Every field of a layer is optional, and so in the schema it looks like
    "either a value or null". By itself that says nothing and the form does not
    need it: "may be left unset" is true of every field here.
    """
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return dict(defs.get(name, {}))
    options = [s for s in schema.get("anyOf", []) if s.get("type") != "null"]
    if len(options) == 1:
        return _unwrap(options[0], defs)
    return schema


def describe(model: type[BaseModel]) -> list[dict[str, Any]]:
    """A layer's fields in a shape a form can be built from.

    Returns:
        One dictionary per field: name, type, bounds, allowed values, group.
        The order is the declaration order: it is the intent, the fields stand
        in a meaningful sequence.
    """
    schema = model.model_json_schema()
    defs = schema.get("$defs", {})
    out: list[dict[str, Any]] = []

    for name, raw in schema.get("properties", {}).items():
        body = _unwrap(raw, defs)
        field: dict[str, Any] = {
            "name": name,
            "type": body.get("type", "string"),
            "group": GROUPS.get(name, RUN),
        }
        if name in CATALOGUES:
            field["catalog"] = CATALOGUES[name]
        if "enum" in body:
            field["choices"] = body["enum"]
        for bound in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
            if bound in body:
                field[bound] = body[bound]
        if field["type"] == "array":
            item = _unwrap(body.get("items", {}), defs)
            field["item_type"] = item.get("type", "string")
            if "enum" in item:
                field["choices"] = item["enum"]
        out.append(field)
    return out


def installation_fields() -> list[dict[str, Any]]:
    """The installation's own layer, described from the settings themselves.

    From ``Settings`` rather than from a model that mirrors it. A mirror would
    be a second list of sixty-odd fields to keep in step, and the one that fell
    behind would be this one — a form quietly unable to configure something
    that already works, which is the very thing ``/schema`` exists to prevent.

    The bootstrap and the secrets fall out here, not by being listed again but
    because ``stored_fields`` is what decides where a setting may live. A field
    that stops being storable stops being offered, in one place.
    """
    allowed = stored_fields()
    return [field for field in describe(Settings) if field["name"] in allowed]


def catalogue() -> dict[str, Any]:
    """All three layers at once — one request for the whole settings form."""
    return {
        "groups": [ARMS, MODELS, JUDGING, DATASET, ENDPOINT, RUN, PROVIDERS, INDEX],
        "installation": installation_fields(),
        "instrument": describe(Instrument),
        "probe": describe(Probe),
    }
