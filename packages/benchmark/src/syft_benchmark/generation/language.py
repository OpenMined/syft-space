"""Detecting the language of a text by its function words.

Used to drop generated items written in a language other than their
document's; the detection itself is ``syft_benchmark.languages``.
"""

from __future__ import annotations

import re

from syft_benchmark.generation.abstractive import TIERS, TTIL_HEAD
from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.negative import NOT_IN_CORPUS
from syft_benchmark.generation.pair import Pair
from syft_benchmark.languages import LANGUAGES, STOP_WORDS, detect_language

# The fixed English wording the cleaners put around what the writer wrote.
_SCAFFOLDING: tuple[str, ...] = (
    TTIL_HEAD,
    *(tier["instruction"] for tier in TIERS.values()),
    "Topic:",
    FILL_IN_PREFIX,
    NOT_IN_CORPUS,
)
# An option letter opening a line: "A) ...".
_OPTION_LETTER_RE = re.compile(r"^\s*[A-D]\)\s*", re.MULTILINE)

__all__ = ["LANGUAGES", "STOP_WORDS", "detect_language", "written_text"]


def written_text(pair: Pair) -> str:
    """An item's text as its writer wrote it, for telling its language.

    The fixed English wording around it (an instruction, "Fill in the blank:",
    option letters) is left out: counted in, it tips a short item in another
    language towards English.
    """
    text = "\n".join([pair.question, pair.answer, *pair.distractors])
    for fixed in _SCAFFOLDING:
        text = text.replace(fixed, " ")
    return _OPTION_LETTER_RE.sub(" ", text)
