"""Matching a fill-in-the-blank answer against its gold span without a judge.

Conservative on purpose: a match is graded correct with no model call, and
anything that does not match goes to the judge. Equivalence covers case,
accents, whitespace, punctuation, a leading article, unicode quotes and dashes,
thousands separators, numbers written as words up to twenty, percent, and dates
in the usual forms, in en, es, pt, fr and de. The language is told from the
masked sentence (``languages.py``); a sentence too short to tell is English, so
"Los Angeles" never loses its "Los" in an English sentence.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime

from syft_benchmark.languages import detect_language

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

# Wording around the span that says nothing: "The answer is X.", "Blank: X",
# "La respuesta es X", "Antwort: X".
_LEAD_IN = re.compile(
    r"^(?:the\s+)?(?:answer|missing\s+word|blank)\b\s*"
    r"(?::|is\s+filled\s+(?:in\s+)?with\b|should\s+be\b|is\b)\s*:?\s*"
    r"|^(?:la\s+|a\s+|die\s+)?(?:respuesta|resposta|réponse|antwort)\b\s*"
    r"(?::|es\b|é\b|est\b|ist\b)\s*:?\s*",
    re.IGNORECASE,
)
# Fewer words than an item's language check needs still tell a sentence's.
_SENTENCE_MIN_WORDS = 6
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
# Where the comma is the decimal mark: "1.500" or "1 500" is 1500, "1,5" is 1.5.
_DOT_THOUSANDS = re.compile(r"(?<=\d)[.\s](?=\d{3}(?!\d))")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_PERCENT_WORDS = re.compile(
    r"\b(?:por\s+ciento|por\s+cento|pour\s*cent|prozent)\b", re.IGNORECASE
)
_MINUS = re.compile(r"(?<!\w)-(?=\d)")
# A full stop that is not a decimal point: "U.S." is "US".
_STRAY_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_SYMBOL = re.compile(r"([%$€£¥])")
_OTHER = re.compile(r"[^\w\s.%$€£¥]")
_ARTICLES: dict[str, frozenset[str]] = {
    "en": frozenset({"a", "an", "the"}),
    "es": frozenset({"el", "la", "los", "las", "un", "una", "unos", "unas", "lo"}),
    "pt": frozenset({"o", "a", "os", "as", "um", "uma", "uns", "umas"}),
    "fr": frozenset({"le", "la", "les", "l", "un", "une", "des", "du"}),
    "de": frozenset(
        {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
         "einer", "eines"}
    ),
}  # fmt: skip
# "1st", "1er", "1.º" (NFKC makes it "1.o"), "15." (German): the day without
# its ordinal mark.
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th|er|\.?[ºª°oa]|\.)(?!\w)", re.I)

_WORDS = {
    word: str(n)
    for n, word in enumerate(
        (
            "zero one two three four five six seven eight nine ten eleven twelve "
            "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
        ).split()
    )
} | {"percent": "%"}
# Number words up to twenty; "-" stands for one, which is also each
# language's article.
_FOREIGN_WORDS: dict[str, list[str]] = {
    "es": (
        "cero - dos tres cuatro cinco seis siete ocho nueve diez once doce trece "
        "catorce quince dieciséis diecisiete dieciocho diecinueve veinte"
    ).split(),
    "pt": (
        "zero - dois três quatro cinco seis sete oito nove dez onze doze treze "
        "catorze quinze dezesseis dezessete dezoito dezenove vinte"
    ).split(),
    "fr": (
        "zéro - deux trois quatre cinq six sept huit neuf dix onze douze treize "
        "quatorze quinze seize dix-sept dix-huit dix-neuf vingt"
    ).split(),
    "de": (
        "null - zwei drei vier fünf sechs sieben acht neun zehn elf zwölf "
        "dreizehn vierzehn fünfzehn sechzehn siebzehn achtzehn neunzehn zwanzig"
    ).split(),
}
_NUMBER_WORDS: dict[str, dict[str, str]] = {"en": _WORDS} | {
    lang: {word: str(n) for n, word in enumerate(words) if word != "-"}
    for lang, words in _FOREIGN_WORDS.items()
}

# Month names to English, whatever the sentence's language: none is a word of
# another language that a date could hold.
_MONTHS: dict[str, str] = {
    **dict.fromkeys(("enero", "janeiro", "janvier", "januar"), "January"),
    **dict.fromkeys(("febrero", "fevereiro", "février", "februar"), "February"),
    **dict.fromkeys(("marzo", "março", "mars", "märz"), "March"),
    **dict.fromkeys(("abril", "avril"), "April"),
    **dict.fromkeys(("mayo", "maio", "mai"), "May"),
    **dict.fromkeys(("junio", "junho", "juin", "juni"), "June"),
    **dict.fromkeys(("julio", "julho", "juillet", "juli"), "July"),
    **dict.fromkeys(("agosto", "août"), "August"),
    **dict.fromkeys(("septiembre", "setiembre", "setembro", "septembre"), "September"),
    **dict.fromkeys(("octubre", "outubro", "octobre", "oktober"), "October"),
    **dict.fromkeys(("noviembre", "novembro", "novembre"), "November"),
    **dict.fromkeys(("diciembre", "dezembro", "décembre", "dezember"), "December"),
}
_MONTH_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
# "15 de marzo de 2026", "1 de março de 2026": the words between day, month
# and year.
_DATE_LINKS = re.compile(r"\b(?:de|del)\b", re.IGNORECASE)

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
    return text.strip(" \t\n\"'.,;:!?¿¡")


def _unaccented(word: str) -> str:
    decomposed = unicodedata.normalize("NFKD", word)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _number(word: str, language: str = "en") -> str | None:
    """A number's one spelling: "12.0", "twelve" and "doce" are "12"."""
    words = _NUMBER_WORDS.get(language, _WORDS)
    if word in words:
        return words[word]
    try:
        value = float(word)
    except ValueError:
        return None
    return f"{value:g}" if math.isfinite(value) else None


def _tokens(text: str, language: str = "en") -> list[str]:
    """Lower-case unaccented words; punctuation, a leading article and
    thousands separators gone.

    Only a leading article: "Series A" is not "Series".
    """
    text = text.lower()
    if language == "en":
        text = _THOUSANDS.sub("", text)
    else:
        text = _DECIMAL_COMMA.sub(".", _DOT_THOUSANDS.sub("", text))
    text = _PERCENT_WORDS.sub(" % ", text)
    text = _MINUS.sub(" minus ", text)
    # A French elision is a word of its own: "l'Élysée" is "l Élysée".
    text = _STRAY_DOT.sub("", text.replace("'", " " if language == "fr" else ""))
    words = _SYMBOL.sub(r" \1 ", _OTHER.sub(" ", text)).split()
    if words and words[0] in _ARTICLES.get(language, _ARTICLES["en"]):
        words = words[1:]
    return [_unaccented(_number(w, language) or w) for w in words]


def _date(text: str) -> str | None:
    """A date in one of the usual forms, as ISO text of its precision."""
    text = _MONTH_RE.sub(lambda m: _MONTHS[m.group(1).lower()], text)
    text = _DATE_LINKS.sub(" ", text)
    text = " ".join(_ORDINAL.sub(r"\1", text.replace(",", " ")).split())
    text = re.sub(r"^(?:on|in|el|em|le|am)\s+", "", text, flags=re.IGNORECASE)
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


def _same(answer: str, expected: str, language: str = "en") -> bool:
    if not answer or not expected:
        return False
    tokens = _tokens(answer, language)
    if tokens and tokens == _tokens(expected, language):
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
    sentence = _PREFIX.sub("", question.strip())
    language = (
        detect_language(sentence.replace(_MASK, " "), min_words=_SENTENCE_MIN_WORDS)
        or "en"
    )
    if _same(_clean(_LEAD_IN.sub("", reply)), gold, language):
        return True
    if _MASK not in sentence:
        return False
    return _same(reply, _clean(sentence.replace(_MASK, expected.strip(), 1)), language)
