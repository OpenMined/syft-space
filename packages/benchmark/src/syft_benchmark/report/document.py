"""Stage 5: the report as a document — tables, charts, observations, conclusion.

The Markdown report from ``metrics.py`` stays: it reads in a console, goes into
git and is compared line by line between runs. This one assembles from the same
metrics a document to hand to a human — with charts, with an explanation of what
each quantity means, and with a conclusion at the end.

Two rules that shaped the module.

**The report is built from aggregates and from nothing else.** The input is a
list of ``Metrics`` — the same numbers that are published to the storefront.
Neither a question, nor a gold answer, nor a corpus chunk is here or can appear:
the document leaves the owner hands further than the audit export, and it must
not carry corpus text. The raw records live in ``audit.py``, are marked there as
corpus, and are handed over separately.

**A chart does not compute.** Everything drawn has already been computed in
``metrics.py`` — otherwise a picture will one day diverge from the table beneath it.

The sections go in order of the importance of the question rather than in order
of convenience of assembly: first the behaviour where there is no answer in the
corpus (the measurement was set up for it), then the price of context, and only
at the end the reliability of the measurement itself.
"""

from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.document import Document as Doc
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from syft_benchmark.config import (
    ARM_LETTER,
    BEHAVIOUR_LABEL,
    ContextMode,
    ExpectedBehavior,
    Settings,
    get_settings,
)
from syft_benchmark.report import charts
from syft_benchmark.report.metrics import (
    Metrics,
    context_effect_pairs,
    discrimination_pairs,
)
from syft_benchmark.report.narrative import Finding, analysis, findings, numbers_block
from syft_benchmark.report.slices import (
    AGREEMENT_FLOOR,
    GeneratorSlice,
    JudgePair,
    average_agreement,
    by_generator,
    judge_agreement,
)

TABLE_STYLE = "Light Grid Accent 1"
ACCENT = RGBColor(0x1A, 0x5C, 0x97)
MUTED = RGBColor(0x55, 0x55, 0x55)

ARM_MEANING: dict[str, str] = {
    "A": "the model alone, without a single corpus chunk. Measures the honesty of "
    "the model itself: a correct answer here means not node quality but that the "
    "corpus is already familiar to it",
    "B": "the whole endpoint — its retrieval, its model, its system prompt. An "
    "assessment of the owner product",
    "C": "the same model as in arm A, plus what the endpoint returned. A and C "
    "differ by exactly the presence of context, so their difference is interpretable",
}


def _heading(doc: Doc, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


class _Sections:
    """Continuous section numbering by what is actually written.

    The number in a heading cannot be set by hand: a section with nothing to show
    does not appear at all — and a run without the control half or without the
    repeats block would leave a gap of the form "3, 5, 7" in the document. The
    reader cannot explain such a gap: they do not know what was not measured.
    """

    def __init__(self, doc: Doc) -> None:
        self.doc = doc
        self._number = 0
        self._sub = 0

    def open(self, title: str) -> None:
        self._number += 1
        self._sub = 0
        _heading(self.doc, f"{self._number}. {title}", level=1)

    def sub(self, title: str) -> None:
        self._sub += 1
        _heading(self.doc, f"{self._number}.{self._sub} {title}", level=2)


def _para(doc: Doc, text: str, *, bold: bool = False, italic: bool = False) -> None:
    run = doc.add_paragraph().add_run(text)
    run.bold = bold
    run.italic = italic


def _note(doc: Doc, text: str) -> None:
    """An explanation under a section: what the quantity means and what it is not."""
    run = doc.add_paragraph().add_run(text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED


def _image(doc: Doc, png: bytes, width: float = 6.0) -> None:
    doc.add_picture(io.BytesIO(png), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def _table(doc: Doc, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers), style=TABLE_STYLE)
    for cell, name in zip(table.rows[0].cells, headers, strict=True):
        cell.text = name
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row, strict=True):
            cell.text = value
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)
    doc.add_paragraph()


def _label(m: Metrics, *, with_judge: bool) -> str:
    """The label of a row on a chart.

    The judge is in the label when there are several judges: one and the same
    answers assessed by different judges give different shares, and without the
    name two bars would look like inexplicable duplicates of one measurement.
    """
    who = (m.model or m.endpoint or "—").split("/")[-1]
    judge = f"\n{m.judge.split('/')[-1]}" if with_judge and m.judge else ""
    return f"{m.arm} {who}{judge}"


def _many_judges(results: Sequence[Metrics]) -> bool:
    return len({m.judge for m in results if m.judge}) > 1


def _parts(m: Metrics) -> dict[str, float]:
    return {
        "correct": m.accuracy,
        "abstain": m.abstain_rate,
        "hallucinate": m.hallucination_rate,
    }


def _insight(doc: Doc, numbers: str, question: str, settings: Settings) -> None:
    """A paragraph written by a model. Does not appear if the model is unreachable."""
    text = analysis(numbers, question, settings=settings)
    if not text:
        return
    run = doc.add_paragraph().add_run(text)
    run.italic = True


def _title_page(doc: Doc, results: list[Metrics], conf: Settings) -> None:
    spaces = sorted({m.space for m in results})
    doc.add_heading("Endpoint honesty benchmark — report", level=0)
    _para(doc, f"Nodes: {', '.join(spaces) or '—'}")
    _para(doc, f"Report assembled: {datetime.now():%Y-%m-%d %H:%M}")

    stamps = [m.checked_at for m in results if m.checked_at]
    if stamps:
        first, last = min(stamps), max(stamps)
        _para(doc, f"Verdicts issued: {first:%Y-%m-%d %H:%M} — {last:%Y-%m-%d %H:%M}")

    judges = sorted({m.judge for m in results if m.judge})
    _para(doc, f"Judges: {', '.join(judges) or '—'}")
    models = sorted({m.model for m in results if m.model})
    _para(doc, f"Models tested: {', '.join(models) or '—'}")
    doc.add_paragraph()

    _heading(doc, "How this report was obtained", level=2)
    _note(
        doc,
        "Thresholds and retrieval parameters are axes of the measurement, not "
        "constants: one and the same pair at a different similarity threshold gives "
        "different numbers. The settings snapshot stands here so that this report "
        "cannot be compared with a report obtained under different ones.",
    )
    sources = sorted({m.context_source for m in results if m.context_source})
    _table(
        doc,
        ("Parameter", "Value"),
        [
            ("Methodology profile", conf.methodology_profile),
            ("Similarity threshold in retrieval", f"{conf.similarity_threshold}"),
            ("Chunks requested from the endpoint", f"{conf.retrieval_top_k}"),
            ("Chunks in the arm C prompt", f"{conf.context_docs}"),
            ("What the context is mixed with in arm C", ", ".join(sources) or "—"),
            ("Test blocks", ", ".join(b.value for b in conf.blocks)),
            ("Consistency floor", f"{conf.consistency_floor:.0%}"),
            ("Share of facts covered for correct", f"{conf.key_facts_threshold:.0%}"),
            ("Judge independence", conf.judge_policy.value),
        ],
    )

    _heading(doc, "What is not in this report", level=2)
    _para(
        doc,
        "The report is assembled from aggregated numbers. There are no questions, "
        "gold answers or corpus chunks in it — not one, and that is a property of "
        "the build rather than a decision by the author: the document leaves the "
        "owner perimeter further than anything else in this pipeline. The raw "
        "records of the measurement — the question, the answers of all the arms "
        "side by side, the whole prompts and the reasoning of every judge — are "
        "handed over by the audit command; such an export contains corpus text and "
        "should be handled like the corpus itself.",
    )
    # python-docx does not annotate this call, and strict demands annotations.
    doc.add_page_break()  # type: ignore[no-untyped-call]


def _how_to_read(sections: _Sections, results: list[Metrics]) -> None:
    doc = sections.doc
    sections.open("How to read these numbers")
    _para(
        doc,
        "The measurement is built as a comparison of three arms. Their shares must "
        "not be added into one: the arms measure three different things.",
    )
    seen = {m.context_mode for m in results}
    _table(
        doc,
        ("Arm", "Mode", "What it measures", "Present in this run"),
        [
            (
                letter,
                mode,
                ARM_MEANING[letter],
                "yes" if ContextMode(mode) in seen else "no",
            )
            for mode, letter in ARM_LETTER.items()
        ],
    )

    _para(doc, "The halves of the set are counted separately:", bold=True)
    _para(
        doc,
        "\u2022 Answerable questions — there is an answer in the corpus, the item "
        "was built from a chunk. Accuracy and LMI are meaningful here.",
    )
    _para(
        doc,
        "\u2022 Control questions — there is no answer in the corpus. There is no "
        'share of "correct" there: any non-abstention is an invention. LMI is not '
        "computed — its denominator holds a quantity that does not occur.",
    )
    _note(
        doc,
        "Accuracy computed over both halves at once drops simply because there came "
        "to be more control questions. So they are not mixed anywhere in the report, "
        "charts included.",
    )

    _para(doc, "The judge is a model.", bold=True)
    _para(
        doc,
        "All the shares in the report are computed from a judge model verdicts "
        "rather than from a human labelling. Different judges diverge on borderline "
        "answers, so the judge is named in every table, and the rows of different "
        "judges are never folded into one.",
    )


def _answerable_section(
    sections: _Sections, rows: list[Metrics], conf: Settings
) -> None:
    doc = sections.doc
    sections.open("Answerable questions: there is an answer in the corpus")
    _para(
        doc,
        "The item was built from a corpus chunk, which means a correct answer exists "
        "and is known. What is measured here is the usefulness of the node: did "
        "retrieval find the right thing and did the model use it.",
    )
    if not rows:
        _para(doc, "No answerable questions were assessed in this run.")
        return

    with_judge = _many_judges(rows)
    _image(
        doc,
        charts.composition(
            [_label(m, with_judge=with_judge) for m in rows],
            [_parts(m) for m in rows],
            title="The composition of outcomes on answerable questions",
        ),
    )
    _note(
        doc,
        "The whole bar is all the assessed answers. It should be read not by the "
        "green but by the rest: an abstention on an answerable question is a missed "
        "benefit, an invention is harm.",
    )

    _table(
        doc,
        (
            "Arm",
            "Block",
            "Model",
            "Judge",
            "Questions",
            "Correct",
            "Inventions",
            "Abstentions",
            "LMI",
            "Retrieval",
        ),
        [
            (
                f"{m.arm} {m.context_mode.value}",
                m.block.value,
                m.model or m.endpoint or "—",
                m.judge or "—",
                str(m.graded),
                f"{m.accuracy:.0%}",
                f"{m.hallucination_rate:.0%}",
                f"{m.abstain_rate:.0%}",
                f"{m.lmi:.2f}" if m.lmi is not None else "—",
                f"{m.retrieval_rate:.0%}" if m.retrieval_checked else "—",
            )
            for m in rows
        ],
    )

    lmi_rows = [m for m in rows if m.lmi is not None]
    if lmi_rows:
        sections.sub("The share of inventions among attempts to answer (LMI)")
        _note(
            doc,
            "H / (H + C): out of the cases where the answerer set about answering, "
            "how many times it answered wrongly. Abstentions do not enter the "
            "denominator — otherwise the metric could be improved simply by "
            "abstaining more often.",
        )
        _image(
            doc,
            charts.bars(
                [_label(m, with_judge=with_judge) for m in lmi_rows],
                [m.lmi or 0.0 for m in lmi_rows],
                title="LMI — inventions among attempts to answer (less is better)",
                colour=charts.BAD,
            ),
        )

    _insight(
        doc,
        numbers_block(rows),
        "Analyse the results on the answerable questions: which arm gives more "
        "benefit, where abstentions mean missed benefit and where inventions mean "
        "harm, and what the difference between arms B and C says about the endpoint.",
        conf,
    )


def _control_section(sections: _Sections, rows: list[Metrics], conf: Settings) -> None:
    doc = sections.doc
    sections.open("Control questions: there is NO answer in the corpus")
    _para(
        doc,
        "The most frequent question a live user asks is the one with no answer in "
        "the corpus. No correct answer exists here, so there is no share of "
        '"correct" in this section: any non-abstention is an invention.',
    )
    if not rows:
        _para(
            doc,
            "No control questions were assessed in this run — half of the pair "
            "behaviour was measured.",
        )
        return

    with_judge = _many_judges(rows)
    labels = [_label(m, with_judge=with_judge) for m in rows]
    _image(
        doc,
        charts.bars(
            labels,
            [m.fabrication_rate for m in rows],
            title="The share of inventions where no answer exists (less is better)",
            colour=charts.BAD,
        ),
    )
    _table(
        doc,
        (
            "Arm",
            "Model",
            "Judge",
            "Correct behaviour",
            "Questions",
            "Abstentions",
            "Inventions",
        ),
        [
            (
                f"{m.arm} {m.context_mode.value}",
                m.model or m.endpoint or "—",
                m.judge or "—",
                BEHAVIOUR_LABEL.get(m.expected.value, m.expected.value),
                str(m.graded),
                f"{m.abstain_rate:.0%}",
                f"{m.fabrication_rate:.0%}",
            )
            for m in rows
        ],
    )
    _note(
        doc,
        "The control half is not homogeneous. On a question without an answer the "
        "right thing is to stay silent, on a question with a false premise to refute "
        'it: silence is no merit there, so the "correct behaviour" column is '
        "mandatory, otherwise the rows read as duplicates.",
    )

    _insight(
        doc,
        numbers_block(rows),
        "Analyse the behaviour on questions with no answer in the corpus. How "
        "dangerous the shares of inventions found are for a live user who cannot "
        "check them, and whether the behaviour of the arms differs.",
        conf,
    )


def _discrimination_section(sections: _Sections, results: list[Metrics]) -> None:
    doc = sections.doc
    pairs = discrimination_pairs(results)
    if not pairs:
        return
    sections.open("Abstention discrimination")
    _para(
        doc,
        'Whether the answerer tells "there is an answer" from "there is none". '
        "The share of abstentions on the control half minus the share on the "
        "answerable one: someone who always abstains gets zero, and someone who "
        "always answers also gets zero. The maximum belongs only to the one that "
        "tells them apart.",
    )
    with_judge = _many_judges([a for a, _, _ in pairs])
    _image(
        doc,
        charts.diverging(
            [_label(a, with_judge=with_judge) for a, _, _ in pairs],
            [value for _, _, value in pairs],
            title="Abstention discrimination (more is better)",
            plus_is_bad=False,
        ),
    )
    _table(
        doc,
        (
            "Arm",
            "Model",
            "Judge",
            "Abstentions: no answer",
            "Abstentions: answer exists",
            "Discrimination",
        ),
        [
            (
                f"{a.arm} {a.context_mode.value}",
                a.model or a.endpoint or "—",
                a.judge or "—",
                f"{c.abstain_rate:.0%}",
                f"{a.abstain_rate:.0%}",
                f"{value:+.0%}",
            )
            for a, c, value in pairs
        ],
    )
    _note(
        doc,
        "Questions with a false premise do not enter this count: there the right "
        "thing is to refute the premise rather than stay silent, and counting an "
        "abstention as a merit would mean rewarding silence where the answer was "
        "known.",
    )


def _context_price_section(
    sections: _Sections, results: list[Metrics], conf: Settings
) -> None:
    doc = sections.doc
    pairs = context_effect_pairs(results)
    if not pairs:
        return
    sections.open("The price of context: what RAG did to the model")
    _para(
        doc,
        "The share of inventions in arm C minus the share in arm A for one and the "
        "same model. The arms differ by exactly the presence of context, so the "
        "difference is interpretable, and the sign is not known in advance — that is "
        "the point of the measurement.",
    )
    _para(
        doc,
        '\u2022 A minus — the material helped it abstain: saying "this is not in '
        'the documents provided" is easier than "I do not know".',
    )
    _para(
        doc,
        "\u2022 A plus — the material removed the caution: the question started "
        "looking as if the answer were somewhere here, and the model that stayed "
        "silent without context answered.",
    )
    with_judge = _many_judges([c for _, c, _ in pairs])
    _image(
        doc,
        charts.diverging(
            [
                f"{_label(c, with_judge=with_judge)}\n"
                f"{BEHAVIOUR_LABEL.get(c.expected.value, c.expected.value)}"
                for _, c, _ in pairs
            ],
            [value for _, _, value in pairs],
            title="The change in the share of inventions on going A → C",
        ),
    )
    _table(
        doc,
        (
            "Model",
            "Judge",
            "Correct behaviour",
            "Questions",
            "Inventions A",
            "Inventions C",
            "Change",
        ),
        [
            (
                c.model or "—",
                c.judge or "—",
                BEHAVIOUR_LABEL.get(c.expected.value, c.expected.value),
                str(c.graded),
                f"{a.hallucination_rate:.0%}",
                f"{c.hallucination_rate:.0%}",
                f"{value:+.0%}",
            )
            for a, c, value in pairs
        ],
    )
    _note(
        doc,
        "On the control half this is the most important number in the whole "
        "measurement: it is the price the model honesty pays for being wired to RAG.",
    )
    _insight(
        doc,
        "\n".join(
            f"{c.model or '—'} / "
            f"{BEHAVIOUR_LABEL.get(c.expected.value, c.expected.value)}: "
            f"inventions A {a.hallucination_rate:.0%} → C {c.hallucination_rate:.0%} "
            f"({value:+.0%}), questions {c.graded}"
            for a, c, value in pairs
        ),
        "Explain what happened to the model honesty when context appeared and what "
        "that threatens the endpoint user with.",
        conf,
    )


def _retrieval_section(sections: _Sections, rows: list[Metrics]) -> None:
    doc = sections.doc
    rows = [m for m in rows if m.retrieval_checked]
    if not rows:
        return
    sections.open("Retrieval found it — did the model use it?")
    _para(
        doc,
        "The cut by retrieval hit. Without it two different ailments merge into one "
        "share: an abstention on a retrieval miss is correct behaviour by the model, "
        "an abstention on a hit is its blindness, and an answer on a miss is an "
        "invention assembled out of topically neighbouring chunks and looking "
        "confirmed.",
    )
    with_judge = _many_judges(rows)
    labels = [_label(m, with_judge=with_judge) for m in rows]
    _image(
        doc,
        charts.grouped(
            labels,
            [
                ("retrieval hit", [m.retrieval_rate for m in rows], charts.NEUTRAL),
                # None reaches the chart as a gap rather than as a zero: where
                # retrieval never hit, a false abstention does not exist, and a zero
                # bar would read as "the model never erred".
                (
                    "false abstention",
                    [m.false_abstain_rate for m in rows],
                    charts.VERDICT_COLOUR["abstain"],
                ),
                (
                    "answer on a miss",
                    [m.blind_answer_rate for m in rows],
                    charts.BAD,
                ),
            ],
            title="Retrieval and the model: whose error this is",
        ),
    )
    _table(
        doc,
        (
            "Arm",
            "Model",
            "Judge",
            "Retrieval hit",
            "False abstentions",
            "Answers on a miss",
        ),
        [
            (
                f"{m.arm} {m.context_mode.value}",
                m.model or m.endpoint or "—",
                m.judge or "—",
                f"{m.retrieval_rate:.0%}",
                f"{m.false_abstain_rate:.0%}"
                if m.false_abstain_rate is not None
                else "—",
                f"{m.blind_answer_rate:.0%}"
                if m.blind_answer_rate is not None
                else "—",
            )
            for m in rows
        ],
    )
    _note(
        doc,
        "The shares are computed against different denominators: a false abstention "
        "against retrieval hits, an answer on a miss against misses. They have no "
        "common total, so the bars stand side by side rather than one inside the "
        "other.",
    )


def _stability_section(
    sections: _Sections, results: list[Metrics], conf: Settings
) -> None:
    doc = sections.doc
    pressured = [m for m in results if m.flip_rate is not None]
    repeated = [m for m in results if m.consistency is not None]
    if not pressured and not repeated:
        return
    sections.open("The stability of the answer")

    if pressured:
        sections.sub("Under pressure")
        _para(
            doc,
            "The share of correct answers the model gave up under objections. The "
            "pressure was applied only to a correct answer: an answer given up is "
            "spoiled by the disagreement of an interlocutor, not by an error.",
        )
        _image(
            doc,
            charts.bars(
                [_label(m, with_judge=_many_judges(pressured)) for m in pressured],
                [m.flip_rate or 0.0 for m in pressured],
                title="Gave in under pressure (less is better)",
                colour=charts.BAD,
            ),
        )

    if repeated:
        sections.sub("On repeats")
        _para(
            doc,
            "How far the answer repeats when the question is repeated at different "
            "temperatures. Below the floor any accuracy measured speaks about which "
            "run made it into the report rather than about the model.",
        )
        _image(
            doc,
            charts.bars(
                [_label(m, with_judge=_many_judges(repeated)) for m in repeated],
                [m.consistency or 0.0 for m in repeated],
                title="The consistency of repeats (more is better)",
                colour=charts.GOOD,
                floor=conf.consistency_floor,
                floor_label="trust floor",
            ),
        )
        _table(
            doc,
            ("Arm", "Model", "Judge", "Consistency", "Trust the accuracy"),
            [
                (
                    f"{m.arm} {m.context_mode.value}",
                    m.model or m.endpoint or "—",
                    m.judge or "—",
                    f"{m.consistency:.0%}" if m.consistency is not None else "—",
                    "yes" if m.is_reliable else "NO",
                )
                for m in repeated
            ],
        )


def _exposure_section(sections: _Sections, rows: list[Metrics]) -> None:
    doc = sections.doc
    closed = [m for m in rows if m.context_mode is ContextMode.CLOSED_BOOK]
    if not closed:
        return
    sections.open("How public the corpus is")
    _para(
        doc,
        "The share of questions the model answered correctly without access to the "
        "corpus. This is not the endpoint quality: a high value means the corpus is "
        "already known to the model — public or part of its training — and the "
        "merits of retrieval in the other arms are overstated by exactly as much.",
    )
    _image(
        doc,
        charts.bars(
            [_label(m, with_judge=_many_judges(closed)) for m in closed],
            [m.corpus_exposure_rate for m in closed],
            title="Correct without access to the corpus (less — the corpus is closed)",
            colour=charts.NEUTRAL,
        ),
    )


def _generator_section(
    sections: _Sections, answerable: list[Metrics], conf: Settings
) -> None:
    """Where exactly the model errs, rather than how many times.

    The summary gives one share laid over ten generators, and they measure different
    skills. A model that holds dates confidently and falls apart on connecting facts
    gets "accuracy 71%" in the summary — a number by which there is nothing to fix.
    """
    rows: list[tuple[str, str, GeneratorSlice]] = []
    for m in answerable:
        if not m.graded:
            continue
        arm = f"{m.arm} {m.context_mode.value}"
        for entry in by_generator(
            m.space, m.context_mode, m.block, m.model or None, m.judge or None
        ):
            if entry.graded:
                rows.append((arm, m.model or m.endpoint or "—", entry))
    if not rows:
        return

    sections.open("By item type")
    _para(
        sections.doc,
        "The generators measure different skills: number masking — precision about "
        "a figure, multihop — the ability to connect two facts, tiered — an extended "
        "explanation. A summary share averages them and therefore hides exactly what "
        "the owner needs: which kind of question breaks.",
    )
    _para(
        sections.doc,
        "Worst first. The half of the set is the answerable one: on the control half "
        'there is nothing to compute "accuracy by item type" from, no correct '
        "answer occurs there.",
    )

    worst = sorted(rows, key=lambda item: item[2].accuracy)
    _table(
        sections.doc,
        ("Arm", "Model", "Item type", "Questions", "Accuracy", "Hallucinations"),
        [
            (
                arm,
                model,
                entry.generator,
                str(entry.graded),
                f"{entry.accuracy:.0%}",
                f"{entry.hallucination_rate:.0%}",
            )
            for arm, model, entry in worst
        ],
    )

    head = worst[0]
    _insight(
        sections.doc,
        "\n".join(
            f"{arm} / {model} / {entry.generator}: accuracy "
            f"{entry.accuracy:.0%}, inventions {entry.hallucination_rate:.0%}, "
            f"questions {entry.graded}"
            for arm, model, entry in worst[:12]
        ),
        f"Which kind of item is hardest and what does that say about the corpus? "
        f"The worst cut is {head[2].generator}.",
        conf,
    )


def _agreement_section(
    sections: _Sections, answerable: list[Metrics], conf: Settings
) -> None:
    """Whether whoever computed this can be trusted.

    A panel is set up so that the divergence of assessments can be seen, but by
    themselves three columns show nothing. If the judges diverge on a third of the
    questions, any difference between models smaller than a third is noise, and that
    has to be said before the reader starts comparing percentages.
    """
    rows: list[tuple[str, str, JudgePair]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for m in answerable:
        key = (m.space, m.context_mode.value, m.block.value, m.model)
        if not m.graded or key in seen:
            continue
        seen.add(key)
        arm = f"{m.arm} {m.context_mode.value}"
        for pair in judge_agreement(m.space, m.context_mode, m.block, m.model or None):
            rows.append((arm, m.model or m.endpoint or "—", pair))
    if not rows:
        return

    average = average_agreement([pair for *_, pair in rows])
    sections.open("Judge agreement")
    _para(
        sections.doc,
        "The assessment is made by a model, and models differ in their opinions. "
        "Here is the share of questions on which two judges issued ONE verdict. "
        "Computed over the questions both of them saw: a recusal and an interrupted "
        "run leave the judges with different sets, and someone else gap is not a "
        "disagreement.",
    )
    _table(
        sections.doc,
        ("Arm", "Model", "Judge", "Judge", "Shared questions", "Agreement"),
        [
            (
                arm,
                model,
                pair.left,
                pair.right,
                str(pair.shared),
                f"{pair.rate:.0%}",
            )
            for arm, model, pair in rows
        ],
    )
    if average is None:
        return

    _para(sections.doc, f"Average agreement — {average:.0%}.", bold=True)
    if average < AGREEMENT_FLOOR:
        _note(
            sections.doc,
            f"That is below {AGREEMENT_FLOOR:.0%}. The judges diverge too often: a "
            f"difference between models smaller than that spread means nothing, and "
            f"they cannot be compared on such a measurement. Look at which items the "
            f"verdicts diverge on before reading the shares.",
        )
    else:
        _para(
            sections.doc,
            f"The judges agree more often than in {AGREEMENT_FLOOR:.0%} of cases — a "
            f"difference between models exceeding the spread of assessments can be "
            f"read as a difference between models.",
        )


def _reliability_section(sections: _Sections, results: list[Metrics]) -> None:
    doc = sections.doc
    failures = [m for m in results if m.failed]
    waiting = [m for m in results if m.pending]
    if not failures and not waiting:
        return
    if not failures:
        sections.open("Answers without a verdict")
        _para(
            doc,
            "The answer was received, the judge has not seen it. These rows do not "
            "enter the shares: an outcome nobody issued is not an outcome. It is "
            "cured not by rerunning but by judging.",
        )
        _table(
            doc,
            ("Node", "Arm", "Block", "Model", "Awaiting a verdict"),
            [
                (
                    m.space,
                    f"{m.arm} {m.context_mode.value}",
                    m.block.value,
                    m.model or m.endpoint or "—",
                    str(m.pending),
                )
                for m in waiting
            ],
        )
        return
    sections.open("Failed calls")
    _para(
        doc,
        "Requests that did not reach an answer. They do not enter the shares: a "
        "failed call speaks about the rig, not about the quality of the answers. But "
        "if there are many, the report describes the part of the set that happened "
        "to get through.",
    )
    _table(
        doc,
        ("Node", "Arm", "Block", "Model", "Failed", "Assessed"),
        [
            (
                m.space,
                f"{m.arm} {m.context_mode.value}",
                m.block.value,
                m.model or m.endpoint or "—",
                str(m.failed),
                str(m.graded),
            )
            for m in failures
        ],
    )
    if waiting:
        _note(
            doc,
            f"Besides them, {sum(m.pending for m in waiting)} answers are recorded "
            f"without a verdict: the judge has not seen them. That is not a failure "
            f"and is not cured by rerunning — they have to be judged.",
        )


def _conclusions(
    sections: _Sections,
    results: list[Metrics],
    observed: list[Finding],
    conf: Settings,
) -> None:
    doc = sections.doc
    sections.open("Conclusions")
    _para(doc, "Observations", bold=True)
    _note(
        doc,
        "Each follows directly from the tables above and is computed rather than "
        "written: an observation appears only where the quantity was measured.",
    )
    if not observed:
        _para(doc, "There are not enough measured quantities for observations.")
    for item in observed:
        run = doc.add_paragraph().add_run(item.title)
        run.bold = True
        run.font.color.rgb = ACCENT
        run.font.size = Pt(10)
        _para(doc, item.detail)

    text = analysis(
        numbers_block(results),
        "Write the overall conclusion of the report: can the answers of this endpoint "
        "be trusted, what turned out to be the most dangerous for the user in this "
        "measurement, what the most reassuring, and what is worth checking in the "
        "next run.",
        settings=conf,
    )
    if text:
        _para(doc, "Overall conclusion", bold=True)
        _note(
            doc,
            "The paragraph below was written by a model from the aggregated numbers "
            "of this report alone. It is a retelling, not a measurement: it is "
            "checked against the tables above.",
        )
        _para(doc, text, italic=True)


def build_docx(
    results: list[Metrics],
    path: Path,
    *,
    settings: Settings | None = None,
) -> Path:
    """Assemble the report document and put it at the given path.

    Args:
        results: The metrics of the runs; the same the Markdown report is built from
        path: Where to put the .docx
        settings: The settings; the snapshot of measurement parameters comes from them

    Returns:
        The path of the file written
    """
    conf = settings or get_settings()
    answerable = [m for m in results if m.expected is ExpectedBehavior.ANSWER]
    control = [m for m in results if m.expected is not ExpectedBehavior.ANSWER]

    doc = Document()
    doc.styles["Normal"].font.size = Pt(10)

    sections = _Sections(doc)
    _title_page(doc, results, conf)
    _how_to_read(sections, results)
    _answerable_section(sections, answerable, conf)
    _control_section(sections, control, conf)
    _discrimination_section(sections, results)
    _context_price_section(sections, results, conf)
    _retrieval_section(sections, answerable)
    _stability_section(sections, results, conf)
    _exposure_section(sections, answerable)
    _generator_section(sections, answerable, conf)
    _agreement_section(sections, answerable, conf)
    _reliability_section(sections, results)
    _conclusions(sections, results, findings(results, settings=conf), conf)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
