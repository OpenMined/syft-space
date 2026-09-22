"""Text metrics: how far the answer RESEMBLES the gold answer.

A port of BLEU / ROUGE / BERTScore from LiveTruth's `eval_arena/scoring.py`. Off
by default, and that is not caution but what they are here.

**What they are here for.** Our headline assessment is the judge verdict, that
is, a model opinion about a text. And it should be the headline one: comparing
prose with prose is a lottery, an explanation can be correct and unlike the gold
answer. But the judge opinion has exactly one trouble: there is nothing to check
it with except another opinion. Text metrics are computed mechanically, do not
depend on any judge, and therefore work as a second, independent view. If the
verdict and the textual match diverge, that is grounds for a look with your own
eyes, not a figure for the storefront.

**What they are not.** Neither BLEU nor ROUGE knows whether the answer is right:
they measure word overlap. A retelling in one own words gets a low score with a
correct answer, while a verbatim quotation off the point gets a high one. So they
enter no share of the report, are not published and take no part in the verdict.
It makes sense to compare them between the models of ONE report, not against
numbers from other people papers.

**Where they apply.** Only where the answer is prose: ``multihop_synthesis``,
``tiered_explanation``, ``qa``. Masking has a one-word gold answer, and ROUGE
over it degenerates into "matched or not", which the judge already measures; for
multiple-choice the answer is a letter.

BLEU and ROUGE are computed right here, without third-party packages: the
definitions are settled and short, and an extra dependency for two formulas costs
more than they do. BERTScore is built differently — it is a model run — and lives
behind an optional dependency: no package, the metric is skipped with a note in
the log, and the run carries on.
"""

from __future__ import annotations

import re
from collections import Counter
from math import exp, log
from typing import Any

from loguru import logger

from syft_benchmark.config import Settings, TextMetric

# The generators whose answer is prose. For the rest the gold answer is too
# short for word overlap to mean anything.
PROSE_GENERATORS = frozenset({"multihop_synthesis", "tiered_explanation", "qa"})

# The n-gram order for BLEU. Four is the accepted default.
_BLEU_ORDER = 4

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Words in lower case.

    The tokenisation is deliberately simple and the same for both metrics: they
    are compared with each other, and a divergence of tokenisers would add a
    difference of parsing to the difference of metrics.
    """
    return _WORD_RE.findall(text.lower())


def _ngrams(tokens: list[str], size: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1))


def bleu(candidate: str, reference: str, order: int = _BLEU_ORDER) -> float:
    """BLEU with smoothing and a brevity penalty.

    Smoothing is mandatory: without it one missed n-gram order zeroes out the
    whole score, and on short answers — and they are short here — 4-grams almost
    never match, so the metric would silently become a constant zero.
    """
    cand = tokenize(candidate)
    ref = tokenize(reference)
    if not cand or not ref:
        return 0.0

    logs = 0.0
    for size in range(1, order + 1):
        cand_grams = _ngrams(cand, size)
        if not cand_grams:
            # The candidate is shorter than this order: nothing to compute.
            return 0.0
        ref_grams = _ngrams(ref, size)
        overlap = sum(min(count, ref_grams[gram]) for gram, count in cand_grams.items())
        total = sum(cand_grams.values())
        # "Plus one" smoothing on the numerator and denominator of a missed
        # order: method 1 from Chen & Cherry, the simplest of the accepted ones.
        precision = (overlap or 1e-9) / total if overlap else 1.0 / (2 * total)
        logs += log(precision)

    penalty = 1.0 if len(cand) > len(ref) else exp(1 - len(ref) / len(cand))
    return round(penalty * exp(logs / order), 4)


def _lcs(left: list[str], right: list[str]) -> int:
    """The length of the longest common subsequence.

    Memory is held to two rows of the table: answers can be long, and the full
    matrix is not needed for them.
    """
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0] * (len(right) + 1)
        for j, other in enumerate(right, start=1):
            current[j] = (
                previous[j - 1] + 1
                if token == other
                else max(previous[j], current[j - 1])
            )
        previous = current
    return previous[-1]


def _f1(overlap: int, cand_total: int, ref_total: int) -> float:
    if not overlap or not cand_total or not ref_total:
        return 0.0
    precision = overlap / cand_total
    recall = overlap / ref_total
    return round(2 * precision * recall / (precision + recall), 4)


def rouge_n(candidate: str, reference: str, size: int) -> float:
    """ROUGE-N by F1: the n-gram overlap of the answer and the gold answer."""
    cand = _ngrams(tokenize(candidate), size)
    ref = _ngrams(tokenize(reference), size)
    overlap = sum(min(count, ref[gram]) for gram, count in cand.items())
    return _f1(overlap, sum(cand.values()), sum(ref.values()))


def rouge_l(candidate: str, reference: str) -> float:
    """ROUGE-L by F1: the longest common subsequence.

    Unlike ROUGE-N it does not require the words to run consecutively — so it
    does not zero out a reordered but substantively correct answer.
    """
    cand = tokenize(candidate)
    ref = tokenize(reference)
    return _f1(_lcs(cand, ref), len(cand), len(ref))


def bertscore(candidate: str, reference: str, model: str) -> float | None:
    """BERTScore F1, or None if there is nothing to compute it with.

    The only metric here that is itself a model run. The package may be absent —
    it drags in torch, and demanding it of everyone for an optional metric is
    wrong — so its absence is not an error: the metric is skipped, a note goes
    into the log, the run continues.
    """
    try:
        from bert_score import score as bert_score_fn
    except ImportError:
        logger.warning(
            "BERTScore is on, but the bert-score package is missing. "
            "Install it: uv sync --extra metrics — or remove bertscore from "
            "BENCH_TEXT_METRICS"
        )
        return None

    try:
        _p, _r, f1 = bert_score_fn(
            [candidate], [reference], model_type=model, verbose=False
        )
    except Exception as exc:  # noqa: BLE001 - foreign code, no reason to die over it
        logger.warning(f"BERTScore did not compute: {exc}")
        return None
    return round(float(f1.mean()), 4)


def applies_to(generator: str) -> bool:
    """Whether it makes sense to compute text similarity for this generator."""
    return generator in PROSE_GENERATORS


def score_text(answer: str, expected: str, settings: Settings) -> dict[str, float]:
    """Compute the similarity metrics that are switched on.

    Args:
        answer: What the answerer said
        expected: The gold answer
        settings: The settings — the list of enabled metrics comes from them

    Returns:
        Metric -> value; empty if there is nothing to compute or all are off
    """
    wanted = set(settings.text_metrics)
    if not wanted or not answer.strip() or not expected.strip():
        return {}

    scores: dict[str, float] = {}
    if TextMetric.BLEU in wanted:
        scores["bleu"] = bleu(answer, expected)
    if TextMetric.ROUGE in wanted:
        scores["rouge1_f"] = rouge_n(answer, expected, 1)
        scores["rouge2_f"] = rouge_n(answer, expected, 2)
        scores["rougeL_f"] = rouge_l(answer, expected)
    if TextMetric.BERTSCORE in wanted:
        value = bertscore(answer, expected, settings.bertscore_model)
        if value is not None:
            scores["bertscore_f1"] = value
    return scores


def average(records: list[dict[str, Any]]) -> dict[str, float]:
    """Averages over a set of ``extra["text_metrics"]`` records.

    Each metric is averaged over the records that have it: BERTScore may have
    been switched on later than the rest, and dividing its sum by all the rows
    would understate it by exactly the factor by which it was not computed.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for record in records:
        for key, value in record.items():
            if isinstance(value, int | float):
                sums[key] = sums.get(key, 0.0) + float(value)
                counts[key] = counts.get(key, 0) + 1
    return {key: round(sums[key] / counts[key], 4) for key in sorted(sums)}
