"""The settings layers: defaults, the target's instrument and probe, a run's own.

The nearer layer wins, an unset field inherits, and an explicit value (an
empty list included) is a decision that survives. Model names are cleaned of
what a paste leaves round them and refused when no trimming can repair them.
A target keeps only what was set on it; a run's layers stay the run's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from syft_benchmark.config import DatasetMode, Settings
from syft_benchmark.control import targets as registry
from syft_benchmark.control.compose import merge, settings_for
from syft_benchmark.control.schemas import (
    Instrument,
    Layer,
    Probe,
    RunRequest,
    TargetSpec,
)
from syft_benchmark.db.models import Job, Target
from syft_benchmark.db.session import session_scope

from support import AUTH

KEY = "pytest-target"


# --- the merge -------------------------------------------------------------


def test_the_nearer_layer_wins() -> None:
    """The probe outranks the instrument, the instrument the defaults.

    The order is asymmetric in meaning: the closer a layer is to a particular
    node, the more whoever set it knew about that node.
    """
    base = Settings(retrieval_top_k=5, judge_model="base-judge")
    out = merge(base, Instrument(judge_model="panel"), Probe(retrieval_top_k=11))
    assert out.judge_model == "panel"
    assert out.retrieval_top_k == 11


def test_an_unset_field_inherits_and_does_not_zero_anything() -> None:
    """An unset field means "take it from above", not zero.

    Without that distinction a settings form opened and closed without a single
    edit would have zeroed the freshness window and the similarity threshold.
    """
    base = Settings(document_window_days=30, similarity_threshold=0.4)
    out = merge(base, Probe())
    assert out.document_window_days == 30
    assert out.similarity_threshold == 0.4


def test_an_explicit_empty_list_is_a_decision_and_survives() -> None:
    """An empty list of disabled generators means "do not disable any".

    It is indistinguishable from unset by looks and opposite in meaning, which
    is why merging goes by the fields that were set, not by the non-empty ones.
    """
    base = Settings(disabled_generators=["mcq"])
    assert merge(base, Probe(disabled_generators=[])).disabled_generators == []


def test_merging_the_source_settings_leaves_them_alone() -> None:
    """One process measures several nodes: an edit to the shared object would leak."""
    base = Settings(retrieval_top_k=5)
    merge(base, Probe(retrieval_top_k=42))
    assert base.retrieval_top_k == 5


def test_a_field_the_settings_do_not_know_is_refused() -> None:
    """A typo in the contract is a setting that silently changes nothing."""

    class Odd(Layer):
        nonsense: int = 0

    with pytest.raises(ValueError, match="do not know the field"):
        merge(Settings(), Odd(nonsense=1))


# --- model names -----------------------------------------------------------


def test_a_model_name_keeps_the_quotes_of_nowhere_it_came_from() -> None:
    """A list pasted in the shape it has in a config file is still a list.

    On the DemoSyft rig every one of 288 calls was refused with 400 because the
    names reached the provider as `"qwen/qwen3.6-plus"`, quotes and all: the
    form split the pasted list on the comma and took nothing off. The run went
    through all six passes and came back with no verdicts.
    """
    instrument = Instrument(
        subject_models=[
            '"deepseek/deepseek-r1-0528"',
            '["x-ai/grok-4.20"',
            '"qwen/qwen3.6-plus"]',
        ],
        generator_model=" anthropic/claude-opus-5 ",
    )
    assert instrument.subject_models == [
        "deepseek/deepseek-r1-0528",
        "x-ai/grok-4.20",
        "qwen/qwen3.6-plus",
    ]
    assert instrument.generator_model == "anthropic/claude-opus-5"


def test_a_value_that_is_not_one_model_name_is_refused_here_not_at_the_provider() -> (
    None
):
    """What no trimming can repair is refused, and the reason is said.

    The wrappers at the ends are leftovers of a copy; a comma or a space in the
    middle is a whole list in one field, and guessing where to split it is not
    this layer's business. Refusing costs a message; passing it on costs a run.
    """
    for bad in ('"a/b", "c/d"', "a b", "openai/gpt 5"):
        with pytest.raises(ValidationError):
            Instrument(subject_models=[bad])
    with pytest.raises(ValidationError):
        Instrument(judge_model='"a/b"x"')
    with pytest.raises(ValidationError):
        Instrument(judge_models=[""])


def test_a_stored_layer_still_opens_after_the_check_arrived() -> None:
    """A row saved before the check must not be readable only from the database.

    The target the owner has to fix is read back through this same model. If
    reading it raised, the form that fixes it would not open either, and the
    one way out would be an UPDATE by hand.
    """
    saved = {"subject_models": ['"qwen/qwen3.6-plus"'], "judge_model": '"x/y"'}
    healed = Instrument.model_validate(saved)
    assert healed.subject_models == ["qwen/qwen3.6-plus"]
    assert healed.judge_model == "x/y"


# --- the target's layers ---------------------------------------------------


def test_the_target_layers_reach_the_settings() -> None:
    row = Target(
        key="k",
        url="http://space",
        endpoint="ep",
        instrument={"judge_model": "panel"},
        probe={"dataset_mode": DatasetMode.ROLLING.value, "retrieval_top_k": 7},
    )
    conf, space = settings_for(row, Settings())
    assert conf.judge_model == "panel"
    assert conf.dataset_mode is DatasetMode.ROLLING
    assert conf.retrieval_top_k == 7
    assert space.key == "k" and space.endpoint == "ep"


def test_search_parameters_live_in_one_place_only() -> None:
    """The retrieval parameters are settings; the node's description has none."""
    row = Target(
        key="k", url="http://space", endpoint="ep", probe={"retrieval_top_k": 7}
    )
    conf, space = settings_for(row, Settings())
    assert conf.retrieval_top_k == 7
    assert "retrieval_top_k" not in type(space).model_fields


def test_a_target_keeps_only_what_was_set() -> None:
    """A target holds an overlay, not a snapshot: a default must reach it itself."""
    row = registry._row(
        TargetSpec(
            key="k",
            url="http://space",
            endpoint="ep",
            probe=Probe(retrieval_top_k=7),
        )
    )
    assert row.probe == {"retrieval_top_k": 7}


def test_a_broken_seed_file_seeds_nothing(tmp_path: Path) -> None:
    """A seed file that is not UTF-8, not JSON, or not a list of Spaces, is
    logged and seeds nothing: the service and every CLI command come up without
    it."""
    session = MagicMock()
    not_utf8 = tmp_path / "latin1.json"
    not_utf8.write_bytes('[{"key": "é"}]'.encode("latin-1"))
    not_json = tmp_path / "broken.json"
    not_json.write_text("[{", encoding="utf-8")
    not_a_space = tmp_path / "entries.json"
    not_a_space.write_text('[{"key": "k"}]', encoding="utf-8")
    for path in (not_utf8, not_json, not_a_space, tmp_path / "missing.json"):
        assert registry.seed(session, Settings(spaces_file=path)) == 0
    session.execute.assert_not_called()


@pytest.mark.needs_db
def test_the_seed_file_carries_its_retrieval_keys_into_the_probe(
    tmp_path: Path, clean: Any
) -> None:
    """The file may set the two retrieval keys; they land in the target's
    probe, the one place they are edited from then on."""
    seed = tmp_path / "spaces.json"
    entry = {"key": KEY, "url": "http://space.invalid", "endpoint": "ep"}
    seed.write_text(json.dumps([{**entry, "retrieval_top_k": 8}]), encoding="utf-8")
    with session_scope() as session:
        assert registry.seed(session, Settings(spaces_file=seed)) == 1
        target = session.get(Target, KEY)
        assert target is not None
        assert target.probe == {"retrieval_top_k": 8}
        conf, _ = settings_for(target, Settings())
        assert conf.retrieval_top_k == 8


@pytest.mark.needs_db
def test_a_run_keeps_the_layers_it_was_asked_with(
    client: TestClient, clean: Any
) -> None:
    """A trial run with a different threshold must not rewrite the target's setting."""
    client.put(
        f"/targets/{KEY}",
        json=TargetSpec(
            key=KEY, url="http://space.invalid", probe=Probe(retrieval_top_k=3)
        ).model_dump(mode="json"),
        headers=AUTH,
    )
    request = RunRequest(probe=Probe(retrieval_top_k=9)).model_dump(mode="json")
    job_id = client.post(f"/targets/{KEY}/runs", json=request, headers=AUTH).json()[
        "id"
    ]

    with session_scope() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.params["probe"]["retrieval_top_k"] == 9
        target = session.get(Target, KEY)
        assert target is not None
        assert target.probe["retrieval_top_k"] == 3
