"""The audit export: what is in it and what is not.

The point of the export is to let a checker not take the benchmark at its word.
Which means the record has to hold both prompts and the judge raw answer, the
answers of all the arms have to lie side by side, and a trimmed export is obliged
to say honestly that a verdict cannot be rechecked from it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from syft_benchmark.db.models import Result, Run
from syft_benchmark.report import render_audit_markdown
from syft_benchmark.report.audit import _answer_record


def _run(mode: str = "model_with_context") -> Run:
    return Run(
        id="run1",
        space="docs",
        endpoint="kb",
        context_mode=mode,
        context_source="endpoint_fragments",
        profile="default",
        params={"similarity_threshold": 0.45, "retrieval_top_k": 5},
        block="direct",
        model="anthropic/claude-sonnet-4",
        model_vendor="anthropic",
        judge_model="openai/gpt-4o",
        started_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def _result() -> Result:
    return Result(
        id="res1",
        run_id="run1",
        qa_id="qa1",
        space="docs",
        endpoint="kb",
        endpoint_response_type="both",
        answer="Port 5442.",
        verdict="correct",
        reasoning="matches the gold answer",
        expected_behavior="answer",
        grounded=True,
        grounded_note="",
        retrieval_hit=True,
        retrieval_rank=1,
        retrieved=[{"file_name": "setup.md", "score": 0.81, "content": "Port 5442."}],
        extra={},
        audit={
            "responder_system": "Answer the question using the material",
            "responder_prompt": "Question:\nWhich port?\n\nMaterial:\n[1] setup.md",
            "context": "[1] setup.md\nPort 5442.",
            "context_source": "endpoint_fragments",
            "judge_system": "You are a strict grading assistant.",
            "judge_prompt": "Question... Expected answer... Model answer...",
            "judge_raw": '{"correct": true}',
        },
        latency_s=0.4,
        model="anthropic/claude-sonnet-4",
        judge_model="openai/gpt-4o",
        created_at=datetime(2026, 9, 12, tzinfo=UTC),
    )


def test_the_record_carries_everything_needed_to_recheck_a_verdict() -> None:
    """The answerer prompt, the judge prompt and the judge raw answer before parsing."""
    record = _answer_record(_result(), _run(), include_context=True)

    assert record["arm"] == "C"
    assert record["prompts"]["responder_prompt"].startswith("Question:")
    assert record["prompts"]["judge_raw"] == '{"correct": true}'
    assert record["prompts"]["context"]
    # The settings the run was obtained with: in six months it must still be
    # visible from a report row which threshold produced it.
    assert record["run"]["params"]["similarity_threshold"] == 0.45


def test_the_record_keeps_the_retrieval_split() -> None:
    """The retrieval hit — the cut without which arm C is uninterpretable."""
    record = _answer_record(_result(), _run(), include_context=True)
    assert record["retrieval"]["hit"] is True
    assert record["retrieval"]["rank"] == 1
    assert record["retrieval"]["fragments"][0]["content"] == "Port 5442."


def test_a_trimmed_export_says_so_instead_of_pretending() -> None:
    """A trimmed export does not pretend to be complete.

    The corpus text is cut out of it — which means a verdict cannot be checked
    against it, and that is said outright in the record itself, not in a covering
    letter.
    """
    record = _answer_record(_result(), _run(), include_context=False)

    assert "cut out" in record["prompts"]["responder_prompt"]
    assert "cut out" in record["prompts"]["judge_prompt"]
    assert "context" not in record["prompts"]
    # The metadata of what was found stays: a file name and a similarity score do
    # not disclose the corpus, and without them there is no seeing what was
    # searched for at all.
    assert record["retrieval"]["fragments"][0]["file_name"] == "setup.md"
    assert "content" not in record["retrieval"]["fragments"][0]


def test_arms_are_rendered_in_order() -> None:
    """A, B, C in a row: the comparison of the arms is the subject of the check."""
    record = {
        "qa_id": "qa1",
        "generator": "qa",
        "expected_behavior": "answer",
        "question": "Which port?",
        "gold": "5442",
        "source": {"file_name": "setup.md", "chunk_id": "c1"},
        "dataset": {"status_note": ""},
        "answers": [
            {
                "arm": "C",
                "context_mode": "model_with_context",
                "block": "direct",
                "responder": "m",
                "context_source": "endpoint_fragments",
                "verdict": "correct",
                "judge": "j",
                "reasoning": "",
                "answer": "5442",
                "prompts": {},
            },
            {
                "arm": "A",
                "context_mode": "closed_book",
                "block": "direct",
                "responder": "m",
                "context_source": "none",
                "verdict": "abstain",
                "judge": "j",
                "reasoning": "",
                "answer": "I don't know",
                "prompts": {},
            },
        ],
    }
    text = render_audit_markdown([record])
    assert text.index("Arm A") < text.index("Arm C")
    assert "Which port?" in text
