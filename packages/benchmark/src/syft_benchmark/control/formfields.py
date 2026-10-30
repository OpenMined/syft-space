"""The shape of the settings fields, served by ``/schema`` so the Space can
draw the form without keeping its own list of them.

Name, type, bounds, allowed values and a group code per field — no labels: the
wording belongs to whoever displays it, in their reader's language.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from syft_benchmark.config import (
    JudgePolicy,
    Settings,
    stored_fields,
)
from syft_benchmark.control.schemas import Instrument, Probe
from syft_benchmark.llm.catalog import MODEL_FIELDS


class FieldGroup(StrEnum):
    """A field's group: a code, the heading is written by the displayer.

    Declared in the order the form shows the groups.
    """

    ARMS = "arms"
    MODELS = "models"
    FILTER = "filter"
    JUDGING = "judging"
    DATASET = "dataset"
    ENDPOINT = "endpoint"
    RUN = "run"
    PROVIDERS = "providers"
    INDEX = "index"


GROUPS: dict[str, FieldGroup] = {
    # --- the instrument
    "arms": FieldGroup.ARMS,
    "blocks": FieldGroup.ARMS,
    "denial_rounds": FieldGroup.ARMS,
    "monte_carlo_temperatures": FieldGroup.ARMS,
    "monte_carlo_trials": FieldGroup.ARMS,
    "context_source": FieldGroup.ARMS,
    "context_docs": FieldGroup.ARMS,
    "fragment_max_chars": FieldGroup.ARMS,
    # A parameter of the measurement: it decides whether a long answer is
    # graded whole or graded cut off.
    "answer_max_tokens": FieldGroup.ARMS,
    "generator_model": FieldGroup.MODELS,
    "subject_models": FieldGroup.MODELS,
    "judge_model": FieldGroup.MODELS,
    "judge_models": FieldGroup.MODELS,
    "filter_model": FieldGroup.FILTER,
    "filter_judge_model": FieldGroup.FILTER,
    "manual_status_priority": FieldGroup.FILTER,
    # Web search sits where its role is set: the tested model with the arms,
    # the question writer with the dataset, the judges with judging.
    "web_search_engine": FieldGroup.ARMS,
    "web_search_closed_book": FieldGroup.ARMS,
    "web_search_with_context": FieldGroup.ARMS,
    "web_search_max_results": FieldGroup.ARMS,
    "web_search_max_calls": FieldGroup.ARMS,
    "web_search_generator": FieldGroup.DATASET,
    "entity_check": FieldGroup.DATASET,
    "web_search_judge": FieldGroup.JUDGING,
    "judge_temperature": FieldGroup.JUDGING,
    "judge_reasoning_effort": FieldGroup.JUDGING,
    "judge_policy": FieldGroup.JUDGING,
    "key_facts_threshold": FieldGroup.JUDGING,
    "answer_coverage_threshold": FieldGroup.JUDGING,
    "consistency_floor": FieldGroup.JUDGING,
    "text_metrics": FieldGroup.JUDGING,
    "methodology_profile": FieldGroup.RUN,
    "max_consecutive_failures": FieldGroup.RUN,
    "max_job_usd": FieldGroup.RUN,
    "reuse_answers": FieldGroup.RUN,
    "audit_log": FieldGroup.RUN,
    # --- the node probe
    "dataset_mode": FieldGroup.DATASET,
    "document_window_days": FieldGroup.DATASET,
    "dataset_max_pairs": FieldGroup.DATASET,
    "top_up_max_usd": FieldGroup.DATASET,
    "disabled_generators": FieldGroup.DATASET,
    "chunks_per_run": FieldGroup.DATASET,
    "pairs_per_chunk": FieldGroup.DATASET,
    "min_chunk_chars": FieldGroup.DATASET,
    "generate_in_cycle": FieldGroup.DATASET,
    "retrieval_top_k": FieldGroup.ENDPOINT,
    "similarity_threshold": FieldGroup.ENDPOINT,
    "endpoint_max_tokens": FieldGroup.ENDPOINT,
    "endpoint_temperature": FieldGroup.ENDPOINT,
    "endpoint_concurrency": FieldGroup.ENDPOINT,
    # --- the installation's own layer, under both
    #
    # Where a model is reached and with what patience. The keys are not here
    # and cannot be: they are secrets, they are sealed, and `stored_fields`
    # leaves them out of this catalogue by construction.
    "ollama_url": FieldGroup.PROVIDERS,
    "generator_url": FieldGroup.PROVIDERS,
    "subject_url": FieldGroup.PROVIDERS,
    "judge_url": FieldGroup.PROVIDERS,
    "filter_url": FieldGroup.PROVIDERS,
    "llm_app_name": FieldGroup.PROVIDERS,
    "llm_timeout": FieldGroup.PROVIDERS,
    "llm_temperature": FieldGroup.PROVIDERS,
    "bertscore_model": FieldGroup.PROVIDERS,
    # The Space's index, as this installation reaches it.
    "chroma_tenant": FieldGroup.INDEX,
    "chroma_database": FieldGroup.INDEX,
    "chroma_internal_port": FieldGroup.INDEX,
    # How a run behaves, as against what it measures.
    "concurrency": FieldGroup.RUN,
    "resume": FieldGroup.RUN,
    "resume_window_hours": FieldGroup.RUN,
    "question_set": FieldGroup.RUN,
    "strict_question_set": FieldGroup.RUN,
    "audit_max_chars": FieldGroup.RUN,
}


# A field whose values come from a list too long to inline. ``choices`` carries
# its own — two arms, four blocks; three hundred models cannot travel that
# way and change on a refresh rather than on a release, so the field names the
# catalogue and the form fetches it from ``/models``. Naming these fields on the
# other side instead is the coupling ``/schema`` exists to prevent.
CATALOGUES: dict[str, str] = dict.fromkeys(MODEL_FIELDS, "models")

# Values a field accepts but the form does not offer: they are set by hand.
OFFERED: dict[str, list[str]] = {
    "judge_policy": [JudgePolicy.STRICT.value, JudgePolicy.WARN.value],
}


def _unwrap(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    """Strip ``anyOf`` with null and unwrap a reference to an enum.

    Every field of a layer is optional, and so in the schema it looks like
    "either a value or null". By itself that says nothing and the form does not
    need it: "may be left unset" is true of every field here.
    """
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return dict(defs.get(name, {}))
    options = [
        s
        for s in schema.get("anyOf", [])
        if s.get("type") != "null" and "const" not in s
    ]
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
            "group": GROUPS.get(name, FieldGroup.RUN),
        }
        # A word a number field also takes, such as "default" for the model's own.
        special = [s["const"] for s in raw.get("anyOf", []) if "const" in s]
        if special:
            field["special"] = special
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
        if name in OFFERED and "choices" in field:
            field["choices"] = list(OFFERED[name])
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
        "groups": list(FieldGroup),
        "installation": installation_fields(),
        "instrument": describe(Instrument),
        "probe": describe(Probe),
    }
