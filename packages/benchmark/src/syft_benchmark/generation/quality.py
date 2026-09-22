"""Screening out questions that cannot be asked apart from the source.

A port from `OMSyft/scripts/generate_qa.py`. Every check here appeared after
analysing a specific pair that was spoiling the metrics: the endpoint answered
correctly and the benchmark scored it a miss.

There are two groups of checks. Self-sufficiency is always needed: during
testing the answerer sees only the question, without the chunk. Unambiguity only
where the answer is not picked from ready-made options; the options make the
question unambiguous by themselves.

The patterns below are English. They are lexical, so a corpus in another
language passes through them unscreened rather than wrongly screened.
"""

from __future__ import annotations

import re

# A question that refers to "the text" or "the article" is useless in a
# benchmark: during testing the answerer will see only the question itself,
# without the source.
#
# We catch a REFERENCE, not a mention. In LiveTruth's news corpus a list of
# words was enough: "the document" there almost always meant "this article".
# Our corpus is documentation about storing documents, and "the documents are
# never uploaded" is an ordinary subject-matter phrase, not a reference to the
# source. The difference is in the construction: a reference stands with a
# preposition or beside a verb of speech.
_SOURCE_NOUNS = r"article|text|document|fragment|passage|excerpt"
_SAID_VERBS = r"says?|said|states?|mentions?|describes?|notes?|explains?|claims?"
_REFERRING_RE = re.compile(
    rf"\b(?:according to|based on|in|from|per)\s+"
    rf"(?:the\s+)?(?:{_SOURCE_NOUNS})\b"
    rf"|\b(?:the\s+)?(?:{_SOURCE_NOUNS})\s+(?:{_SAID_VERBS})\b",
    re.IGNORECASE,
)

# --- a demonstrative without an antecedent ----------------------------------
# "Where did President Trump make THIS STATEMENT about Iran?" lives only in a
# pair with the previous question of the same chunk: "this statement" points not
# at the world but at a neighbouring pair. We catch the pattern "demonstrative +
# referring noun": "this year" and "that city" point at the world and pass.
_DEMONSTRATIVES = (
    "this", "that", "these", "those", "such", "said", "aforementioned",
)  # fmt: skip

# Nouns that name nothing by themselves and refer back to what has already been
# said. The words "year", "city", "team" are deliberately absent: with a
# demonstrative they give an ordinary anchor to the world rather than a
# reference to a neighbouring question.
_DEICTIC_NOUNS = (
    "statement", "remark", "comment", "quote", "quotation", "phrase", "word",
    "claim", "announcement", "post", "message", "speech", "answer", "reply",
    "decision", "measure", "policy", "rule", "law", "order", "ban", "deal",
    "event", "incident", "episode", "case", "situation", "problem", "issue",
    "change", "move", "step", "action", "effort", "program", "project",
    "plan", "proposal", "agreement", "meeting", "trip", "visit",
    "study", "report", "finding", "result", "number", "figure", "amount",
)  # fmt: skip

# Between the demonstrative and the noun we allow one word: "this recent
# statement" is no better than "this statement".
_DEMONSTRATIVES_RE = "|".join(_DEMONSTRATIVES)
_NOUNS_RE = "|".join(_DEICTIC_NOUNS)
_DEICTIC_RE = re.compile(
    rf"\b(?:{_DEMONSTRATIVES_RE})\s+(?:\w+\s+)?(?:{_NOUNS_RE})s?\b",
    re.IGNORECASE,
)

# --- a pronoun with nothing to lean on --------------------------------------
# "When did this happen?", "What did he say about it?" — the same defect, but
# without a referring noun. The question is fit if it has something to hold on
# to in itself: a proper name, a number or a quoted phrase.
_PRONOUNS_RE = re.compile(
    r"\b(?:it|its|this|that|these|those|they|them|their|theirs|"
    r"he|him|his|she|her|hers)\b",
    re.IGNORECASE,
)
_ANCHOR_RE = re.compile(r"[A-Z][\w’'-]|\d|[«\"“]")

# --- a question with several correct answers --------------------------------
# "What did coach Dan Hurley say about the victory?" — the document has several
# of his quotes, and any of them is correct. The judge, though, compares against
# one gold answer and scores a correct answer as a miss.
_SAY_VERBS = (
    r"(?:says?|said|tells?|told|states?|stated|claims?|claimed|calls?|called|"
    r"describes?|described|notes?|noted|remarks?|remarked|argues?|argued|"
    r"writes?|wrote|adds?|added|explains?|explained|comments?|commented|"
    r"answers?|answered|replies|replied|responds?|responded)"
)
_ABOUT_QUOTE_RE = re.compile(
    r"\bwhat\s+(?:did|does|do|has|have|had)\s+(?P<who>.{2,60}?)\s+(?:\w+ly\s+)?"
    + _SAY_VERBS
    + r"\b"
    r"|\bwhat\s+(?:was|were|is|are)\s+(?P<who2>.{2,60}?)(?:'s|’s)\s+"
    r"(?:comments?|remarks?|responses?|reactions?|assessments?|takes?|"
    r"verdicts?|opinions?|views?|answers?|statements?|words?|quotes?)\b",
    re.IGNORECASE,
)

# A title does not count as a name: finding quotes takes a surname.
_NOT_A_NAME = frozenset(
    {
        "president", "coach", "senator", "governor", "secretary", "minister",
        "mr", "mrs", "ms", "dr", "professor", "the", "a", "an", "us", "u.s",
        "chinese", "american", "russian", "former", "then", "in", "what",
        "did", "does", "do", "has", "have", "had", "was", "were", "is", "are",
    }
)  # fmt: skip

_NAME_RE = re.compile(r"\b[A-Z][\w’'-]*")
_QUOTE_RE = re.compile(r"[“\"«]([^”\"»]{15,400})[”\"»]")

# A gap between quoted pieces shorter than this is one utterance broken up by an
# attribution: "Indisputably a genius," the poet W. H. Auden put it, "but ...".
_QUOTE_JOIN_CHARS = 60

# How far from an utterance we look for the speaker surname. An attribution
# stands both before and after a quote, so the window is two-sided.
_ATTRIBUTION_WINDOW = 220

# Wordings that themselves invite one of several correct answers.
_OPEN_ENDED = (
    "one of the", "some of the", "an example of", "give an example",
    "name one", "name a ", "list some", "what are some", "such as what",
)  # fmt: skip


def quoted_spans(document: str) -> list[tuple[int, int]]:
    """The bounds of direct speech; an utterance broken by attribution is joined."""
    spans: list[tuple[int, int]] = []
    for match in _QUOTE_RE.finditer(document):
        if spans and match.start() - spans[-1][1] < _QUOTE_JOIN_CHARS:
            spans[-1] = (spans[-1][0], match.end())
        else:
            spans.append((match.start(), match.end()))
    return spans


def quote_subject(question: str) -> str | None:
    """Whose utterance is being asked about. None — the question is not about speech."""
    match = _ABOUT_QUOTE_RE.search(question)
    if not match:
        return None
    who = match.group("who") or match.group("who2") or ""
    names = [
        name
        for name in _NAME_RE.findall(who)
        if name.lower().strip(".") not in _NOT_A_NAME
    ]
    return names[-1] if names else None


def count_attributed_quotes(document: str, name: str) -> int:
    """How many of the document utterances can be attributed to this person."""
    speaker = re.compile(rf"\b{re.escape(name)}\b")
    return sum(
        1
        for start, end in quoted_spans(document)
        if speaker.search(
            document[max(0, start - _ATTRIBUTION_WINDOW) : end + _ATTRIBUTION_WINDOW]
        )
    )


def reject_reason(
    question: str,
    document: str,
    *,
    task_type: str = "abstractive",
) -> str | None:
    """Why an item should not be taken into the dataset. None — it is fit.

    The set of checks depends on the item type, and that is not a convenience but
    a condition of the thing working. An extractive item is a sentence from the
    document with a span cut out; pronouns and "this" legitimately stand in it,
    because the antecedent is nearby, in the same sentence. Running it through
    the rules for a free-form question means screening out almost all masking.

    Args:
        question: The item text — a question or a statement
        document: The whole document rather than a single chunk: during testing
            the endpoint searches the entire collection, and a second suitable
            quote beyond the chunk breaks the assessment exactly as a
            neighbouring one does
        task_type: What kind of item —

            * ``extractive`` — a masked sentence. The context is right there, and
              only the length is checked: a short stub is restored by guesswork
              and measures nothing.
            * ``abstractive`` — a free-form question. The full set: both
              self-sufficiency and unambiguity.
            * ``choice`` — a multiple-choice question. Unambiguity is provided by
              the options themselves; self-sufficiency remains.
            * ``statement`` — a statement from "two truths and a lie". As choice:
              "this solution" in a statement is just as unreadable out of context.

    Returns:
        The reason for screening out, or None
    """
    if task_type == "extractive":
        # The mask is in place and the sentence is not a stub — nothing more is
        # required of it: the answer context stands around the mask itself.
        if "______" not in question:
            return "no mask"
        if len(question) < 45:
            return "the sentence is too short for masking"
        return None

    lowered = question.lower()
    if _REFERRING_RE.search(question):
        return "a reference to the source"
    if _DEICTIC_RE.search(question):
        return "a demonstrative without an antecedent"
    if _PRONOUNS_RE.search(question):
        tail = question.split(None, 1)[1] if " " in question else ""
        # The pronoun itself does not count as an anchor: "What did He say about
        # it?" would otherwise pass the check thanks to the capital in "He".
        tail = _PRONOUNS_RE.sub(" ", tail)
        if not _ANCHOR_RE.search(tail):
            return "a pronoun without an antecedent"

    if task_type in ("choice", "statement"):
        return None  # options and statements are unambiguous on their own

    if any(marker in lowered for marker in _OPEN_ENDED):
        return "several correct answers by the wording"
    name = quote_subject(question)
    if name and count_attributed_quotes(document, name) > 1:
        return f"the document has more than one utterance by: {name}"
    return None
