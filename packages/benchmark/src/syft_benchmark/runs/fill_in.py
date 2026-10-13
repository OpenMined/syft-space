"""Matching a fill-in-the-blank answer against its gold span without a judge.

Conservative on purpose: a match is graded correct with no model call, and
anything that does not match goes to the judge. Equivalence covers case,
whitespace, punctuation, a leading article, unicode quotes and dashes, thousands
separators, numbers written as words up to twenty, and dates in the usual
English forms.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime

# The masked sentence as generation.extractive asks it; not imported, as
# the generation package imports the judge.
_MASK = "______"
_PREFIX = re.compile(r"^fill in the blank:\s*", re.IGNORECASE)

_PLAIN = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
    }
)

# Wording around the span that says nothing: "The answer is X.", "Blank: X".
_LEAD_IN = re.compile(
    r"^(?:the\s+)?(?:answer|missing\s+word|blank)\b\s*"
    r"(?::|is\s+filled\s+(?:in\s+)?with\b|should\s+be\b|is\b)\s*:?\s*",
    re.IGNORECASE,
)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_MINUS = re.compile(r"(?<!\w)-(?=\d)")
# A full stop that is not a decimal point: "U.S." is "US".
_STRAY_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_SYMBOL = re.compile(r"([%$€£¥])")
_OTHER = re.compile(r"[^\w\s.%$€£¥]")
_ARTICLES = frozenset({"a", "an", "the"})
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)

_WORDS = {
    word: str(n)
    for n, word in enumerate(
        (
            "zero one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
        ).split()
    )
} | {"percent": "%"}

# Each format with what it fixes: a full date never equals a month and year.
_DATE_FORMATS = (
    ("%B %d %Y", "%Y-%m-%d"),
    ("%d %B %Y", "%Y-%m-%d"),
    ("%b %d %Y", "%Y-%m-%d"),
    ("%d %b %Y", "%Y-%m-%d"),
    ("%Y-%m-%d", "%Y-%m-%d"),
    ("%B %Y", "%Y-%m"),
    ("%b %Y", "%Y-%m"),
)
# Day and month alone, parsed in a leap year so 29 February reads.
_DAY_MONTH_FORMATS = ("%B %d", "%d %B", "%b %d", "%d %b")


def _clean(text: str) -> str:
    """Unicode folded, quotes and dashes plain, emphasis and wrapping stripped."""
    text = unicodedata.normalize("NFKC", text).translate(_PLAIN)
    text = text.replace("*", "").replace("`", "").strip()
    return text.strip(" \t\n\"'.,;:!?")


def _number(word: str) -> str | None:
    """A number's one spelling: "12.0" and "twelve" are "12"."""
    if word in _WORDS:
        return _WORDS[word]
    try:
        value = float(word)
    except ValueError:
        return None
    return f"{value:g}" if math.isfinite(value) else None


def _tokens(text: str) -> list[str]:
    """Lower-case words; punctuation, a leading article and thousands separators gone.

    Only a leading article: "Series A" is not "Series".
    """
    text = _THOUSANDS.sub("", text.lower())
    text = _MINUS.sub(" minus ", text)
    text = _STRAY_DOT.sub("", text.replace("'", ""))
    words = _SYMBOL.sub(r" \1 ", _OTHER.sub(" ", text)).split()
    if words and words[0] in _ARTICLES:
        words = words[1:]
    return [_number(w) or w for w in words]


def _date(text: str) -> str | None:
    """A date in one of the usual English forms, as ISO text of its precision."""
    text = " ".join(_ORDINAL.sub(r"\1", text.replace(",", " ")).split())
    text = re.sub(r"^(?:on|in)\s+", "", text, flags=re.IGNORECASE)
    for fmt, shown in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime(shown)
        except ValueError:
            continue
    for fmt in _DAY_MONTH_FORMATS:
        try:
            return datetime.strptime(f"{text} 2000", f"{fmt} %Y").strftime("%m-%d")
        except ValueError:
            continue
    return None


def _same(answer: str, expected: str) -> bool:
    if not answer or not expected:
        return False
    tokens = _tokens(answer)
    if tokens and tokens == _tokens(expected):
        return True
    dated = _date(answer)
    return dated is not None and dated == _date(expected)


def match_fill_in(question: str, expected: str, answer: str) -> bool:
    """Whether the answer is the gold span, alone or put back in its sentence.

    False means "no verdict here", never "wrong": the judge decides those.
    """
    reply = _clean(answer)
    gold = _clean(expected)
    if "\n" in reply or not gold:
        return False
    if _same(_clean(_LEAD_IN.sub("", reply)), gold):
        return True
    sentence = _PREFIX.sub("", question.strip())
    if _MASK not in sentence:
        return False
    return _same(reply, _clean(sentence.replace(_MASK, expected.strip(), 1)))
