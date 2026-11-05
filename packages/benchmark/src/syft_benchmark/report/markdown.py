"""The Markdown report of a Space: the metrics as tables, section by section.

Built from ``Metrics`` rows and the cuts of ``slices`` and ``stability``; it
computes nothing of its own.
"""

from __future__ import annotations

from syft_benchmark.config import ContextMode, ExpectedBehavior
from syft_benchmark.report import stability
from syft_benchmark.report.metrics import (
    Metrics,
    context_effect_pairs,
    discrimination_pairs,
)
from syft_benchmark.report.slices import (
    AGREEMENT_FLOOR,
    agreement_rows,
    average_agreement,
    generator_rows,
    text_scores,
)


def _discrimination_section(
    answerable: list[Metrics], control: list[Metrics]
) -> list[str]:
    """Whether the pair can tell "there is an answer" from "there is none"."""
    rows = discrimination_pairs([*answerable, *control])
    if not rows:
        return []
    return [
        "",
        "## Abstention discrimination",
        "",
        "The share of abstentions on unanswerable questions minus the share of",
        "abstentions on answerable ones. Someone who always abstains gets 0, and",
        "someone who always answers also gets 0: the maximum belongs only to the",
        "one that tells them apart.",
        "",
        "Questions with a false premise are not included here: there the right",
        "thing is to refute the premise, not to stay silent.",
        "",
        "| Space | Arm | Model | Judge | Questions | Discrimination |",
        "| --- | --- | --- | --- | ---: | ---: |",
        *(
            f"| {a.space} | {a.arm_label} | {a.model or '—'} "
            f"| {a.judge or '—'} | {a.graded}+{c.graded} | {value:+.0%} |"
            for a, c, value in rows
        ),
    ]


def _context_effect_section(
    answerable: list[Metrics], control: list[Metrics]
) -> list[str]:
    """What the context that appeared did to the model honesty."""
    lines = [
        f"| {m.space} | {m.model or '—'} | {m.judge or '—'} "
        f"| {m.behaviour_label} | {m.graded} | {value:+.0%} |"
        for _, m, value in context_effect_pairs([*control, *answerable])
    ]
    if not lines:
        return []
    return [
        "",
        "## The price of context",
        "",
        "The share of inventions in arm C minus the share in arm A for ONE model.",
        "A minus means the material helped it abstain; a plus means it removed the",
        "caution and the model that stayed silent without context set about",
        "answering.",
        "",
        "| Space | Model | Judge | Correct behaviour | Questions "
        "| Change in inventions |",
        "| --- | --- | --- | --- | ---: | ---: |",
        *lines,
    ]


def _retrieval_split_section(answerable: list[Metrics]) -> list[str]:
    """The cut by retrieval hit: whose ailment this is.

    An abstention on a retrieval miss is correct behaviour by the model; an
    abstention on a hit is its blindness; an answer on a miss is an invention over
    someone else context. In one accuracy share they are indistinguishable.
    """
    rows = [m for m in answerable if m.retrieval_checked]
    if not rows:
        return []
    lines = [
        "",
        "## Retrieval found it — did the model use it?",
        "",
        "Computed only where retrieval took part. A false abstention is the",
        "model fault: the material lay in front of it. An answer on a miss is an",
        "invention assembled out of topically neighbouring chunks.",
        "",
        "| Space | Arm | Model | Judge | Hits | False abstentions "
        "| Answers on a miss |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for m in rows:
        false_abstain = (
            f"{m.false_abstain_rate:.0%}" if m.false_abstain_rate is not None else "—"
        )
        blind = f"{m.blind_answer_rate:.0%}" if m.blind_answer_rate is not None else "—"
        # The judge is in a column for the same reason as in the main table: one
        # and the same answers assessed by different judges give different figures,
        # and without the name the rows would read as inexplicable duplicates.
        lines.append(
            f"| {m.space} | {m.arm_label} | {m.model or '—'} "
            f"| {m.judge or '—'} | {m.retrieval_rate:.0%} | {false_abstain} "
            f"| {blind} |"
        )
    return lines


def _stability_lines(results: list[Metrics]) -> list[str]:
    """The section on the stability of the set, if there is anything to compare.

    Computed over the first combination where two cohorts have verdicts: the
    section answers one question — does the pool of questions affect the numbers —
    and repeating it for every model would drown the answer in a table.
    """
    for m in results:
        if m.expected is not ExpectedBehavior.ANSWER or not m.graded:
            continue
        comparison = stability.compare(
            m.space, m.context_mode, m.block, m.model or None, m.judge or None
        )
        if comparison is not None:
            return stability.lines(comparison)
    return []


def generator_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "by item type"."""
    rows = generator_rows(results)
    if not rows:
        return []

    lines = [
        "",
        "## By item type",
        "",
        "The generators measure different skills: number masking — precision",
        "about a figure, multihop — the ability to connect two facts, tiered —",
        "an extended explanation. One share laid over all of them hides exactly",
        "what the owner needs; worst first.",
        "",
        "| Space | Arm | Block | Model | Item type | Questions | Accuracy "
        "| Hallucinations | Abstentions | Incomplete |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        entry = row.entry
        lines.append(
            f"| {row.space} | {row.arm} | {row.block} | {row.model or '—'} "
            f"| {entry.generator} | {entry.graded} | {entry.accuracy:.0%} "
            f"| {entry.hallucination_rate:.0%} | {entry.abstain_rate:.0%} "
            f"| {entry.incomplete_rate:.0%} |"
        )
    return lines


def agreement_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "judge agreement"."""
    rows = agreement_rows(results)
    if not rows:
        return []

    average = average_agreement([row.pair for row in rows])
    lines = [
        "",
        "## Judge agreement",
        "",
        "The share of questions on which two judges issued ONE verdict. Computed",
        "over the questions both of them saw: a recusal and an interrupted run",
        "leave the judges with different sets, and someone else gap is not a",
        "disagreement.",
        "",
        "| Space | Arm | Model | Judge | Judge | Shared | Agreement |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in rows:
        pair = row.pair
        lines.append(
            f"| {row.space} | {row.arm} | {row.model or '—'} | {pair.left} "
            f"| {pair.right} | {pair.shared} | {pair.rate:.0%} |"
        )
    if average is not None:
        lines += ["", f"Average agreement — {average:.0%}."]
        if average < AGREEMENT_FLOOR:
            lines.append(
                f"That is below {AGREEMENT_FLOOR:.0%}: the judges diverge too "
                f"often, and the difference between models is smaller than that "
                f"spread — noise. Models cannot be compared on such a measurement."
            )
    return lines


def text_metric_lines(results: list[Metrics]) -> list[str]:
    """The Markdown section "similarity to the gold answer"."""
    rows = text_scores(results)
    if not rows:
        return []

    keys = sorted({key for row in rows for key in row.scores})
    header = " | ".join(keys)
    dashes = " | ".join("---:" for _ in keys)
    lines = [
        "",
        "## Similarity to the gold answer",
        "",
        "Mechanical measures of word overlap. They do NOT know correctness: a",
        "retelling in one own words gets a low score with a correct answer,",
        "while a verbatim quotation off the point gets a high one. They enter no",
        "share of the report; they are needed as a view of",
        "the same answers that is independent of the judge. Comparing them makes",
        "sense within one report, not against other people numbers.",
        "",
        f"| Space | Arm | Block | Model | Judge | Answers | {header} |",
        f"| --- | --- | --- | --- | --- | ---: | {dashes} |",
    ]
    for row in rows:
        values = " | ".join(
            f"{row.scores[key]:.3f}" if key in row.scores else "—" for key in keys
        )
        lines.append(
            f"| {row.space} | {row.arm} | {row.block} | {row.model} "
            f"| {row.judge or '—'} | {row.counted} | {values} |"
        )
    return lines


def render_markdown(results: list[Metrics]) -> str:
    """The report by mode, block, model and judge.

    A cut by block rather than a fold into one row: the blocks answer different
    questions, and adding their shares into one gives a number about nothing. The
    judge is put in a column for the same reason: one and the same answers assessed
    by different judges give different figures, and without the judge name the rows
    would look like inexplicable duplicates.
    """
    answerable = [m for m in results if m.expected is ExpectedBehavior.ANSWER]
    control = [m for m in results if m.expected is not ExpectedBehavior.ANSWER]

    lines = [
        "# Benchmark report",
        "",
        "## Answerable questions",
        "",
        "There is an answer to them in the corpus: the item was built from a chunk.",
        "",
        "| Space | Arm | Block | Model | Judge | Questions | Accuracy "
        "| Hallucinations | Abstentions | Incomplete | LMI | Retrieval |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: |",
    ]
    for m in answerable:
        retrieval = f"{m.retrieval_rate:.0%}" if m.retrieval_checked else "—"
        lmi = f"{m.lmi:.2f}" if m.lmi is not None else "—"
        lines.append(
            f"| {m.space} | {m.arm_label} | {m.block.value} "
            f"| {m.model or '—'} | {m.judge or '—'} | {m.graded} "
            f"| {m.accuracy:.0%} "
            f"| {m.hallucination_rate:.0%} | {m.abstain_rate:.0%} "
            f"| {m.incomplete_rate:.0%} | {lmi} "
            f"| {retrieval} |"
        )

    if control:
        lines += [
            "",
            "## Control questions — there is NO answer in the corpus",
            "",
            "Abstaining is right, and so is refuting a false premise; anything",
            "else is an invention, except specifics the answer's web search",
            "supports, counted on their own. LMI is not computed — its",
            "denominator holds a quantity that does not occur.",
            "",
            "| Space | Arm | Model | Judge | Correct behaviour | Questions "
            "| Abstentions | Inventions | From the web |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for m in control:
            # The correct behaviour is in a column: the control half is not
            # homogeneous. On a question without an answer the right thing is to
            # stay silent, on a question with a false premise to refute it, and
            # without this column the rows would read as inexplicable duplicates.
            lines.append(
                f"| {m.space} | {m.arm_label} | {m.model or '—'} "
                f"| {m.judge or '—'} | {m.behaviour_label} "
                f"| {m.graded} | {m.abstain_rate:.0%} "
                f"| {m.fabrication_rate:.0%} | {m.web_sourced} |"
            )

        lines += _discrimination_section(answerable, control)
        lines += _context_effect_section(answerable, control)

    lines += _retrieval_split_section(answerable)

    pressured = [m for m in results if m.flip_rate is not None]
    if pressured:
        lines += [
            "",
            "## Resistance to pressure",
            "",
            "The share of correct answers the model gave up under objections.",
            "Counted against those that were pressured: pressure is applied only",
            "to a correct answer.",
            "",
            "| Space | Model | Gave in |",
            "| --- | --- | ---: |",
        ]
        for m in pressured:
            lines.append(f"| {m.space} | {m.model or '—'} | {m.flip_rate:.0%} |")

    repeated = [m for m in results if m.consistency is not None]
    if repeated:
        lines += [
            "",
            "## Resistance to randomness",
            "",
            "How far the answer repeats when the question is repeated at different",
            "temperatures. Below 50% any accuracy measured speaks about which run",
            "made it into the report rather than about the model.",
            "",
            "| Space | Model | Consistency | Trust the accuracy |",
            "| --- | --- | ---: | --- |",
        ]
        for m in repeated:
            lines.append(
                f"| {m.space} | {m.model or '—'} | {m.consistency:.0%} "
                f"| {'yes' if m.is_reliable else 'NO'} |"
            )

    # The answerable half only: "answered correctly without the corpus" is
    # meaningful only where a correct answer exists.
    closed = [m for m in answerable if m.context_mode is ContextMode.CLOSED_BOOK]
    if closed:
        lines += [
            "",
            "## How public the corpus is",
            "",
            "The share of questions the model answered correctly without access to",
            "the corpus. This is not the endpoint quality: a high value means the",
            "corpus is already known to the model — public or part of its training.",
            "",
        ]
        for m in closed:
            judge = f" (judge {m.judge})" if m.judge else ""
            lines.append(
                f"* {m.space} / {m.model or '—'}{judge}: {m.corpus_exposure_rate:.0%}"
            )

    lines += generator_lines(results)
    lines += text_metric_lines(results)
    lines += agreement_lines(results)
    lines += _stability_lines(results)

    failures = [m for m in results if m.failed]
    if failures:
        lines += ["", "## Failed calls", ""]
        for m in failures:
            lines.append(
                f"* {m.space} / {m.context_mode.value} / {m.block.value}: "
                f"{m.failed} (not included in the shares)"
            )

    # Awaiting a verdict is not a failure, and it is cured not by rerunning but by
    # judging. On separate lines, so that this is visible.
    waiting = [m for m in results if m.pending]
    if waiting:
        lines += [
            "",
            "## Answers without a verdict",
            "",
            "The answer was received, the judge has not seen it. Not included in",
            "the shares. To judge them: `export-judging --only-pending`, then",
            "`import-judging`.",
            "",
        ]
        for m in waiting:
            lines.append(
                f"* {m.space} / {m.context_mode.value} / {m.block.value} "
                f"/ {m.model or '—'}: {m.pending}"
            )

    judges = sorted({m.judge for m in results if m.judge})
    if judges:
        lines += ["", "---", "", f"Judge: {', '.join(judges)}"]

    return "\n".join(lines) + "\n"
