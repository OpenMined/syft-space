"""Model roles, the judge independence, the test blocks and the manual mode."""

from __future__ import annotations

import pytest

from syft_benchmark.config import EvalBlock, JudgePolicy, Settings
from syft_benchmark.llm import (
    JudgeConflict,
    check_judge_independence,
    generator_provider,
    is_recused,
    judge_provider,
    judge_providers,
    subject_providers,
    vendor_of,
)
from syft_benchmark.runs import DENIAL_PHRASES
from syft_benchmark.runs.console import parse_answers


def _settings(**kwargs: object) -> Settings:
    return Settings(spaces_file="config/spaces.json", **kwargs)  # type: ignore[arg-type]


# --- roles ------------------------------------------------------------------


def test_roles_fall_back_to_the_common_provider() -> None:
    """A configuration with a single local model stays one line long."""
    conf = _settings()
    for provider in (generator_provider(conf), judge_provider(conf)):
        assert provider.url == conf.ollama_url
        assert not provider.is_external


def test_roles_can_be_split_between_providers() -> None:
    """Generator inside the perimeter, model under test outside — a working case."""
    conf = _settings(
        subject_url="https://openrouter.ai/api/v1",
        subject_key="sk-or-test",
        subject_models=["anthropic/claude-sonnet-4", "openai/gpt-4o"],
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    generator = generator_provider(conf)
    subjects = subject_providers(conf)

    assert not generator.is_external
    assert [s.model for s in subjects] == [
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o",
    ]
    assert all(s.is_external for s in subjects)


def test_no_subjects_configured_means_the_local_model() -> None:
    """A rig that never calls outside at all tests its own model."""
    conf = _settings()
    assert [s.model for s in subject_providers(conf)] == [conf.generator_model]


@pytest.mark.parametrize(
    ("model", "vendor"),
    [
        ("anthropic/claude-sonnet-4", "anthropic"),
        ("openai/gpt-4o", "openai"),
        ("google/gemini-2.5-pro", "google"),
        ("gemma3-4b-gpu", ""),
        # A namespace nobody has heard of is still a vendor: an empty one is
        # what `conflict_between` reads as nothing to compare.
        ("some/unknown-thing", "some"),
    ],
)
def test_vendor_is_read_from_the_model_id(model: str, vendor: str) -> None:
    assert vendor_of(model) == vendor


# --- the judge independence -------------------------------------------------


def test_same_vendor_is_a_conflict() -> None:
    """A model more readily approves an answer in its own style."""
    conf = _settings(
        judge_url="https://openrouter.ai/api/v1",
        judge_key="k",
        judge_model="anthropic/claude-sonnet-4",
        subject_url="https://openrouter.ai/api/v1",
        subject_key="k",
        subject_models=["anthropic/claude-opus-4"],
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    warning = check_judge_independence(
        judge_provider(conf), subject_providers(conf)[0], conf
    )
    assert warning is not None
    assert "anthropic" in warning


def test_different_vendors_pass() -> None:
    conf = _settings(
        judge_url="https://openrouter.ai/api/v1",
        judge_key="k",
        judge_model="openai/gpt-4o",
        subject_url="https://openrouter.ai/api/v1",
        subject_key="k",
        subject_models=["anthropic/claude-sonnet-4"],
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    assert (
        check_judge_independence(judge_provider(conf), subject_providers(conf)[0], conf)
        is None
    )


def test_a_local_model_judging_itself_is_a_conflict_too() -> None:
    """There are no providers, but the interest is the same."""
    conf = _settings()
    warning = check_judge_independence(
        judge_provider(conf), subject_providers(conf)[0], conf
    )
    assert warning is not None
    assert "judges itself" in warning


def test_strict_policy_refuses_to_run() -> None:
    conf = _settings(judge_policy=JudgePolicy.STRICT)
    with pytest.raises(JudgeConflict):
        check_judge_independence(judge_provider(conf), subject_providers(conf)[0], conf)


def test_policy_off_asks_no_questions() -> None:
    conf = _settings(judge_policy=JudgePolicy.OFF)
    assert (
        check_judge_independence(judge_provider(conf), subject_providers(conf)[0], conf)
        is None
    )


# --- blocks -----------------------------------------------------------------


def test_all_blocks_are_on_by_default() -> None:
    assert set(_settings().blocks) == {
        EvalBlock.DIRECT,
        EvalBlock.DENIAL_LOOP,
        EvalBlock.MONTE_CARLO,
    }


def test_blocks_can_be_narrowed() -> None:
    conf = _settings(blocks=[EvalBlock.DIRECT])
    assert conf.blocks == [EvalBlock.DIRECT]


def test_denial_phrases_escalate() -> None:
    """The order matters: the round number shows at what pressure it gave in."""
    assert DENIAL_PHRASES[0].endswith("?")  # a gentle doubt
    assert "disappointed" in DENIAL_PHRASES[9]  # pressure
    assert len(DENIAL_PHRASES) >= 12


def test_all_generators_on_by_default() -> None:
    from syft_benchmark.generation import GENERATORS, enabled_generators

    assert set(enabled_generators()) == set(GENERATORS)


def test_generators_can_be_switched_off_by_name() -> None:
    from syft_benchmark.generation import enabled_generators

    left = enabled_generators(["tiered_explanation", "multihop_synthesis"])
    assert "tiered_explanation" not in left
    assert "qa" in left


# --- the manual mode --------------------------------------------------------


def test_console_answers_parse_from_json() -> None:
    text = 'Sure!\n[{"id": "abc123", "answer": "PostgreSQL"}]\nHope that helps.'
    assert parse_answers(text) == {"abc123": "PostgreSQL"}


def test_console_answers_parse_from_a_numbered_list() -> None:
    """A chat answers now with an array, now with a list; one form is impossible."""
    text = "abc123: PostgreSQL\ndef456) Port 8100\n"
    assert parse_answers(text) == {"abc123": "PostgreSQL", "def456": "Port 8100"}


def test_console_answers_without_content_are_dropped() -> None:
    assert parse_answers('[{"id": "abc123", "answer": ""}]') == {}


def test_console_nothing_recognisable() -> None:
    assert parse_answers("I would rather not answer these questions.") == {}


# --- the panel of judges ----------------------------------------------------


def test_one_judge_by_default() -> None:
    """While there is one judge, the panel consists of it."""
    conf = _settings()
    judges = judge_providers(conf)
    assert [j.model for j in judges] == [conf.judge_model]
    assert judge_provider(conf).model == conf.judge_model


def test_panel_runs_every_judge() -> None:
    """The list of judges sets how many times the same answers get assessed."""
    conf = _settings(
        judge_models=[
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
        ],
        judge_url="https://openrouter.ai/api/v1",
        judge_key="k",
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )
    assert [j.model for j in judge_providers(conf)] == [
        "anthropic/claude-sonnet-4",
        "openai/gpt-4o",
        "google/gemini-2.5-pro",
    ]
    # The first judge is the one the expensive blocks are computed by and the
    # one that goes to the storefront.
    assert judge_provider(conf).model == "anthropic/claude-sonnet-4"


def test_duplicate_judges_are_collapsed() -> None:
    """The same judge twice would give two identical assessments and double the bill."""
    conf = _settings(judge_models=["gemma3-4b-gpu", "gemma3-4b-gpu"])
    assert len(judge_providers(conf)) == 1


# --- recusal ----------------------------------------------------------------


def _panel_settings(policy: JudgePolicy) -> Settings:
    return _settings(
        judge_url="https://openrouter.ai/api/v1",
        judge_key="k",
        judge_model="anthropic/claude-sonnet-4",
        subject_url="https://openrouter.ai/api/v1",
        subject_key="k",
        subject_models=["anthropic/claude-opus-4", "openai/gpt-4o"],
        judge_policy=policy,
        allow_external_models=True,
        external_hosts=["openrouter.ai"],
    )


def test_recusal_skips_only_the_judges_own_vendor() -> None:
    """A judge does not assess "its own", but assesses others as usual."""
    conf = _panel_settings(JudgePolicy.RECUSE)
    judge = judge_provider(conf)
    own, foreign = subject_providers(conf)

    assert is_recused(judge, own, conf)
    assert not is_recused(judge, foreign, conf)


def test_recusal_only_applies_under_its_own_policy() -> None:
    """Under warn and strict a conflict is handled differently; no recusal."""
    judge = judge_provider(_panel_settings(JudgePolicy.RECUSE))
    for policy in (JudgePolicy.OFF, JudgePolicy.WARN, JudgePolicy.STRICT):
        conf = _panel_settings(policy)
        own = subject_providers(conf)[0]
        assert not is_recused(judge, own, conf)


def test_local_model_judging_itself_is_recusable() -> None:
    """A local model has no provider, and the conflict shows only by name."""
    conf = _settings(judge_policy=JudgePolicy.RECUSE)
    judge = judge_provider(conf)
    subject = subject_providers(conf)[0]
    assert judge.model == subject.model
    assert is_recused(judge, subject, conf)
