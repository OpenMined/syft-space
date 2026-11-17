"""What a job and a run report outwards: codes, with the failed call as text.

A foreign UI words the codes in its reader's language; only the text of a
failed call passes through as it is. A run that graded nothing, a set nobody
could build and a set with nothing to ask are each told apart from success.
"""

from __future__ import annotations

from syft_benchmark.config import ContextMode
from syft_benchmark.control import jobs as job_queue

# --- codes -----------------------------------------------------------------


def test_a_blocked_arm_travels_as_a_code() -> None:
    """The reason is displayed by a foreign UI, in the language of its own reader.

    A sentence in one language arriving on an owner's page written in another
    is not a translation, it is a breakage.
    """
    from syft_benchmark.config import ContextSource
    from syft_benchmark.runs.execute import (
        NO_FRAGMENTS_TO_MIX,
        arm_blocker,
        blocker_code,
    )

    arm = ContextMode.MODEL_WITH_CONTEXT
    code = blocker_code(arm, "summary", ContextSource.ENDPOINT_FRAGMENTS)
    assert code == NO_FRAGMENTS_TO_MIX
    assert " " not in code
    # The prose stays — it is ours, for the console and for a run note.
    assert arm_blocker(arm, "summary", ContextSource.ENDPOINT_FRAGMENTS)


def test_a_measurable_arm_is_not_blocked_by_anything() -> None:
    """An empty code means "the arm is measurable" and needs no separate check."""
    from syft_benchmark.config import ContextSource
    from syft_benchmark.runs.execute import blocker_code

    assert blocker_code(ContextMode.CLOSED_BOOK, "summary", ContextSource.NONE) == ""
    # The node's mode did not read — that is a diagnostic failure, not a known
    # incompatibility, and a run must not be cancelled over it.
    arm = ContextMode.MODEL_WITH_CONTEXT
    assert blocker_code(arm, "", ContextSource.ENDPOINT_FRAGMENTS) == ""


def test_the_job_row_says_nothing_a_renderer_would_have_to_translate() -> None:
    """The job's row is read by a foreign UI, in the language of its own reader.

    The state and the phase are codes by construction; so are our own reasons
    for a refusal. Only the text of a failed call passes through as is: it
    cannot be enumerated, and hiding it is worse than showing it untranslated.
    """
    ours = {
        job_queue.TARGET_GONE,
        job_queue.SERVICE_RESTARTED,
        job_queue.NOTHING_GRADED,
        job_queue.NO_QUESTIONS,
        job_queue.NOTHING_GENERATED,
    }
    assert all(" " not in code for code in ours)
    assert all(code == code.lower() for code in ours)


# --- measured nothing, built nothing, nothing to ask -----------------------


def test_a_run_that_graded_nothing_does_not_count_as_a_measurement() -> None:
    """Reaching the end and measuring something are different things.

    A model provider that is down gives a full pass over the set, zero verdicts
    and a perfectly comfortable outcome. The owner, looking at "Finished",
    would go looking for numbers that are not there.
    """
    from syft_benchmark.scheduler import Measured

    assert Measured(asked=20, graded=0, failed=20).measured_nothing is True
    assert Measured(asked=20, graded=18, failed=2).measured_nothing is False
    # Not a single question was asked — that is an empty set, not a failed
    # measurement.
    assert Measured().measured_nothing is False


def test_a_set_nobody_could_build_is_not_an_empty_set() -> None:
    """The two look the same from outside and ask opposite things of the owner.

    Nothing built because there were no new chunks is the ordinary outcome of a
    corpus that has not moved; nothing built because every call was refused is a
    broken rig.
    """
    from syft_benchmark.scheduler import Measured

    refused = Measured(generated_nothing=True, generation_failure_sample="qa: 401")
    assert refused.generated_nothing is True
    # Nothing built and nothing refused: a corpus with no new chunks.
    assert Measured().generated_nothing is False


def test_a_run_with_an_empty_set_says_so_instead_of_reporting_success() -> None:
    """There were runs and nothing to ask — that is not a good measurement.

    Most often this is what a freshness window that let no document through
    looks like.
    """
    from syft_benchmark.scheduler import Measured

    assert Measured(passes=2, asked=0).had_nothing_to_ask is True
    # Resuming is the opposite case: the questions were not asked because there
    # are already verdicts for them.
    assert Measured(passes=2, asked=0, resumed=30).had_nothing_to_ask is False
    assert Measured(passes=2, asked=30, graded=30).had_nothing_to_ask is False


# --- the failed call beside the code ---------------------------------------


def test_the_generation_that_built_nothing_carries_the_call_that_failed() -> None:
    """The same rule as for grading: the code says what, the text says which."""
    line = job_queue._with_sample(
        job_queue.NOTHING_GENERATED,
        "qa: anthropic/claude-sonnet-4.6: [Errno 101] Network is unreachable",
    )
    assert line.startswith(f"{job_queue.NOTHING_GENERATED}: ")
    assert "Network is unreachable" in line


def test_the_run_that_graded_nothing_carries_the_call_that_failed() -> None:
    """The code says nothing was graded; which failure it was is text.

    A spent key, a model name with quotes round it, a dropped network and a
    node that is down all end a run the same way. On the rig the wording
    guessed at "the provider is down" while the provider was answering 400 —
    and the search went to the network instead of to the name.
    """
    line = job_queue._with_sample(
        job_queue.NOTHING_GRADED,
        'ERROR: "qwen/qwen3.6-plus" -> 400: not a valid model ID; retry 2',
    )
    assert line.startswith(f"{job_queue.NOTHING_GRADED}: ")
    assert "not a valid model ID" in line
    # The reasons are joined with semicolons and split apart again by whoever
    # renders them: one inside the sample would tear it into meaningless lines.
    assert ";" not in line
    assert len(line) <= len(job_queue.NOTHING_GRADED) + 2 + job_queue.SAMPLE_CHARS


def test_with_nothing_to_show_the_code_stands_alone() -> None:
    """No sample, no trailing colon: the code is read as a code."""
    assert job_queue._with_sample(job_queue.NOTHING_GRADED, "") == (
        job_queue.NOTHING_GRADED
    )
