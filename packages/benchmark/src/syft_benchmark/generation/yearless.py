"""Dates without a year in a question: the year added from the publish date,
or the question dropped.

"The October 20 interview" names no day a reader can place. Every writer
prompt asks for the year, and still such questions made 14% of the entity
check's rejects, each after a paid call. The year is added here, before that
check: the date's last occurrence on or before the publish date, or its next
one when that is under 90 days ahead and nearer; "pasado" / "passado" pick the
first, "próximo" the second. A question with no publish date to count from is
dropped.

A text that writes a year anywhere is left as it is: the year may be the
date's, and one counted from the publish date would contradict it. So is a
date next to the blank of a fill-in: the blank may be its year.

English, Spanish, Portuguese, French, Italian and German dates are read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from syft_benchmark.generation.abstractive import TTIL_HEAD
from syft_benchmark.generation.pair import Dropped, Pair

# The drop reason.
NO_YEAR = "a date without its year"
# ``meta`` key listing the repairs: [{"from": "20 de octubre", "to": "..."}].
META = "year_added"

_MASK = "______"

_EN_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_EN_SHORT = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
# Spanish and Portuguese: "20 de octubre", "en octubre".
_ES_PT_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
# French and Italian: "20 octobre", "20 ottobre".
_FR_IT_MONTHS = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "dicembre": 12,
}
_DE_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}


def _names(months: dict[str, int], capital: bool = False) -> str:
    ordered = sorted(months, key=len, reverse=True)
    return "|".join(name.capitalize() if capital else name for name in ordered)


_DAY = r"(?P<day>[0-3]?\d)(?:st|nd|rd|th|º|°)?"
_YEAR = re.compile(r"\b(?:1[89]|20)\d\d\b")
# "octubre pasado": the relative word goes, the year says it.
_RELATIVE_AFTER = re.compile(
    r"^\s+(?P<word>pasad[oa]|passad[oa]|próxim[oa]|últim[oa])\b", re.IGNORECASE
)
# "el pasado 20 de octubre".
_RELATIVE_BEFORE = re.compile(
    r"\b(?P<word>pasad[oa]|passad[oa]|próxim[oa])\s+$", re.IGNORECASE
)
_PAST = ("pasad", "passad", "últim")
# News mostly reports what has happened; a date ahead of the story is one it
# announces, and those are weeks away, not seasons.
_SOON_DAYS = 90


@dataclass(frozen=True, slots=True)
class _Form:
    """One way of writing a date: its pattern, month names and the year
    appended to it (``{year}``)."""

    pattern: re.Pattern[str]
    months: dict[str, int]
    suffix: str


_FORMS = (
    # "October 20", "Oct. 20th": English months are capitalised.
    _Form(
        re.compile(
            rf"\b(?P<month>{_names({**_EN_MONTHS, **_EN_SHORT}, capital=True)})"
            rf"\.?\s+{_DAY}\b"
        ),
        {**_EN_MONTHS, **_EN_SHORT},
        ", {year}",
    ),
    # "20 October", "20th of October".
    _Form(
        re.compile(rf"\b{_DAY}\s+(?:of\s+)?(?P<month>{_names(_EN_MONTHS, True)})\b"),
        _EN_MONTHS,
        " {year}",
    ),
    # "in October", "since early March".
    _Form(
        re.compile(
            r"\b(?:in|since|until|through|by|from|during|before|after)\s+"
            r"(?:early\s+|late\s+|mid-)?"
            rf"(?P<month>{_names(_EN_MONTHS, True)})\b(?!\.?\s*[0-3]?\d\b)"
        ),
        _EN_MONTHS,
        " {year}",
    ),
    # "20 de octubre", "1º de maio".
    _Form(
        re.compile(rf"\b{_DAY}\s+de\s+(?P<month>{_names(_ES_PT_MONTHS)})\b", re.I),
        _ES_PT_MONTHS,
        " de {year}",
    ),
    # "en octubre", "a fines de marzo", "em outubro".
    _Form(
        re.compile(
            r"\b(?:en|desde|hasta|durante|em|até|"
            r"(?:a|al)\s+(?:fines|finales|principios|comienzos|mediados)\s+de|"
            r"(?:no|nos)\s+(?:início|inicio|fim|final)\s+de)\s+"
            rf"(?P<month>{_names(_ES_PT_MONTHS)})\b",
            re.I,
        ),
        _ES_PT_MONTHS,
        " de {year}",
    ),
    # "20 octobre", "1er mars", "20 ottobre".
    _Form(
        re.compile(
            r"\b(?P<day>[0-3]?\d|1er)\s+" rf"(?P<month>{_names(_FR_IT_MONTHS)})\b",
            re.I,
        ),
        _FR_IT_MONTHS,
        " {year}",
    ),
    # "20. Oktober".
    _Form(
        re.compile(rf"\b(?P<day>[0-3]?\d)\.\s*(?P<month>{_names(_DE_MONTHS)})\b", re.I),
        _DE_MONTHS,
        " {year}",
    ),
)


@dataclass(frozen=True, slots=True)
class _Hit:
    start: int
    end: int
    month: int
    day: int | None
    suffix: str


def _hits(text: str) -> list[_Hit]:
    """The dates in ``text``, left to right, none overlapping."""
    found: list[_Hit] = []
    for form in _FORMS:
        for match in form.pattern.finditer(text):
            month = form.months.get(match.group("month").lower())
            if month is None:
                continue
            raw_day = match.groupdict().get("day")
            day = None
            if raw_day:
                day = 1 if raw_day.lower() == "1er" else int(raw_day)
                if not 1 <= day <= 31:
                    continue
            found.append(_Hit(match.start(), match.end(), month, day, form.suffix))
    found.sort(key=lambda h: (h.start, -h.end))
    out: list[_Hit] = []
    for hit in found:
        if out and hit.start < out[-1].end:
            continue
        out.append(hit)
    return out


def _year(hit: _Hit, published: date, direction: int) -> int:
    """The year of a date: its last occurrence on or before the publish date,
    or its next one after it when ``direction`` says so (-1 before, 1 after)
    or when that is nearer and within ``_SOON_DAYS``."""

    def when(year: int) -> date:
        return date(year, hit.month, min(hit.day or 1, 28))

    past = published.year if when(published.year) <= published else published.year - 1
    future = past + 1
    if direction < 0:
        return past
    if direction > 0:
        return future
    ahead = (when(future) - published).days
    behind = (published - when(past)).days
    return future if ahead <= _SOON_DAYS and ahead < behind else past


@dataclass(slots=True)
class Fixed:
    """A text with its years added; ``missing`` — the dates that could not be
    given one (no publish date)."""

    text: str
    repairs: list[dict[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def add_years(text: str, published: date | None) -> Fixed:
    """``text`` with a year after every date that has none."""
    hits = _hits(text)
    if not hits or _YEAR.search(text):
        return Fixed(text)
    for hit in hits:
        near = text[max(0, hit.start - 8) : hit.end + 16]
        if _MASK in near:
            return Fixed(text)
    if published is None:
        return Fixed(text, missing=[text[h.start : h.end] for h in hits])
    out: list[str] = []
    repairs: list[dict[str, str]] = []
    at = 0
    for hit in hits:
        start, end, direction = hit.start, hit.end, 0
        before = _RELATIVE_BEFORE.search(text, at, start)
        if before is not None and before.end() == start:
            start = before.start()
            direction = -1 if before.group("word").lower().startswith(_PAST) else 1
        after = _RELATIVE_AFTER.match(text[end:])
        consumed = 0
        if after is not None:
            consumed = after.end()
            direction = -1 if after.group("word").lower().startswith(_PAST) else 1
        written = text[hit.start : hit.end]
        dated = written + hit.suffix.format(year=_year(hit, published, direction))
        out.append(text[at:start])
        out.append(dated)
        repairs.append({"from": text[start : end + consumed].strip(), "to": dated})
        at = end + consumed
    out.append(text[at:])
    return Fixed("".join(out), repairs)


def _statement(line: str, published: date | None) -> Fixed:
    """A "two truths, one lie" line, ``  B) text`` or ``B) text``: its text."""
    head, sep, body = line.partition(") ")
    if not sep or len(head.strip()) != 1:
        return add_years(line, published)
    fixed = add_years(body, published)
    fixed.text = f"{head}{sep}{fixed.text}"
    return fixed


def _merge(into: Fixed, part: Fixed) -> str:
    into.repairs += [r for r in part.repairs if r not in into.repairs]
    into.missing += [m for m in part.missing if m not in into.missing]
    return part.text


def _fix_pair(key: str, pair: Pair, published: date | None) -> tuple[Pair, Fixed]:
    """The pair with its years added where its reader sees them: the stem of a
    choice question, the statements of a two-truths item (in every field that
    repeats them), the topic of an explanation, otherwise the question."""
    total = Fixed("")
    meta: dict[str, Any] = dict(pair.meta)
    if key == "mcq":
        stem, sep, options = pair.question.partition("\n")
        question = _merge(total, add_years(stem, published)) + sep + options
        return replace(pair, question=question), total
    if key == "two_truths_one_lie" and pair.question.startswith(TTIL_HEAD):
        lines = pair.question.split("\n")
        question = "\n".join(
            [lines[0]]
            + [_merge(total, _statement(line, published)) for line in lines[1:]]
        )
        answer = _merge(total, _statement(pair.answer, published))
        distractors = [
            _merge(total, add_years(text, published)) for text in pair.distractors
        ]
        claims = meta.get("claims")
        if isinstance(claims, list):
            meta["claims"] = [
                _merge(total, add_years(str(text), published)) for text in claims
            ]
        return (
            replace(
                pair,
                question=question,
                answer=answer,
                distractors=distractors,
                meta=meta,
            ),
            total,
        )
    if key == "tiered_explanation" and isinstance(meta.get("topic"), str):
        topic = meta["topic"]
        meta["topic"] = _merge(total, add_years(topic, published))
        question = pair.question.replace(f"Topic: {topic}", f"Topic: {meta['topic']}")
        return replace(pair, question=question, meta=meta), total
    question = _merge(total, add_years(pair.question, published))
    return replace(pair, question=question), total


def screen(
    key: str, pairs: list[Pair], published: date | None
) -> tuple[list[Pair], list[Dropped]]:
    """Add the missing years to one kind's questions; a question whose dates
    cannot be given one is dropped."""
    kept: list[Pair] = []
    dropped: list[Dropped] = []
    for pair in pairs:
        fixed, total = _fix_pair(key, pair, published)
        if total.missing:
            dropped.append(Dropped(NO_YEAR, pair.question, pair.answer))
            continue
        if total.repairs:
            fixed = replace(fixed, meta={**fixed.meta, META: total.repairs})
        kept.append(fixed)
    return kept, dropped
