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

# --- direct speech in a masked sentence --------------------------------------
# A quote is someone's wording, not a fact: "THE ENEMY," I'll yell, ... cannot
# be restored from any corpus, and an attribution beyond the sentence leaves the
# speaker unknown. A quoted term ("auto", “Live Text”) is a name, not speech, and
# passes. Straight and typographic double quotes, German „“ and guillemets; the
# single ’ is left out, as it is first of all an apostrophe.
_QUOTE_MARKS_RE = re.compile(r"[\"“”„«»]")
_QUOTED_SPAN_RE = re.compile(r"\"[^\"]*\"|„[^„“”]*[“”]|“[^“”]*”|«[^«»]*»|»[^«»]*«")

# A quoted span this long is wording rather than a term.
_QUOTE_MIN_WORDS = 4

# A speech verb this many words from a quoted span attributes it to a speaker.
_SPEECH_WINDOW_WORDS = 4
_SPEECH_RE = re.compile(
    r"\b(?:says?|said|tells?|told|asks?|asked|adds?|added|writes?|wrote|"
    r"yells?|yelled|shouts?|shouted|replie[sd]|reply|insists?|insisted|"
    r"declares?|declared|according\s+to)\b",
    re.IGNORECASE,
)

_FILL_IN_PREFIX = "Fill in the blank:"

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


def _unanchored_reason(text: str) -> str | None:
    """Why the text leans on something outside itself. None — it stands alone."""
    if _DEICTIC_RE.search(text):
        return "a demonstrative without an antecedent"
    if _PRONOUNS_RE.search(text):
        # The first word is skipped: it is capitalised anyway.
        tail = text.split(None, 1)[1] if " " in text else ""
        # The pronoun itself does not count as an anchor: "What did He say about
        # it?" would otherwise pass the check thanks to the capital in "He".
        tail = _PRONOUNS_RE.sub(" ", tail)
        if not _ANCHOR_RE.search(tail):
            return "a pronoun without an antecedent"
    return None


def _is_quotation(sentence: str) -> bool:
    """Whether the sentence carries someone's wording rather than a quoted term.

    A mark left without its pair means the sentence was cut from inside a quote.
    A quoted span is wording when it is long or stands beside a speech verb; the
    blank counts as one word.
    """
    if _QUOTE_MARKS_RE.search(_QUOTED_SPAN_RE.sub(" ", sentence)):
        return True
    for match in _QUOTED_SPAN_RE.finditer(sentence):
        if len(match.group().split()) >= _QUOTE_MIN_WORDS:
            return True
        before = sentence[: match.start()].split()[-_SPEECH_WINDOW_WORDS:]
        after = sentence[match.end() :].split()[:_SPEECH_WINDOW_WORDS]
        if _SPEECH_RE.search(" ".join(before + after)):
            return True
    return False


def reject_reason(
    question: str,
    document: str,
    *,
    task_type: str = "abstractive",
) -> str | None:
    """Why an item should not be taken into the dataset. None — it is fit.

    The set of checks depends on the item type. An extractive item is a sentence
    from the document with a span cut out: it is read without the rest of the
    story, so "he" or "this" must have their subject named in the same sentence,
    and someone's quoted wording is not a fact to restore.

    Args:
        question: The item text — a question or a statement
        document: The whole document rather than a single chunk: during testing
            the endpoint searches the entire collection, and a second suitable
            quote beyond the chunk breaks the assessment exactly as a
            neighbouring one does
        task_type: What kind of item —

            * ``extractive`` — a masked sentence. The length (a short stub is
              restored by guesswork and measures nothing), self-sufficiency and
              no direct speech; the unambiguity rules are for free-form
              questions.
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
        if "______" not in question:
            return "no mask"
        if len(question) < 45:
            return "the sentence is too short for masking"
        # The checks run on the sentence itself, so the first word they skip is
        # the sentence's own rather than the "Fill" of the prefix. The blank is
        # no anchor: a hidden name does not tell the reader who "he" is.
        sentence = question.removeprefix(_FILL_IN_PREFIX).strip()
        reason = _unanchored_reason(sentence)
        if reason:
            return reason
        if _is_quotation(sentence):
            return "a quote"
        return None

    lowered = question.lower()
    if _REFERRING_RE.search(question):
        return "a reference to the source"
    reason = _unanchored_reason(question)
    if reason:
        return reason

    if task_type in ("choice", "statement"):
        return None  # options and statements are unambiguous on their own

    if any(marker in lowered for marker in _OPEN_ENDED):
        return "several correct answers by the wording"
    name = quote_subject(question)
    if name and count_attributed_quotes(document, name) > 1:
        return f"the document has more than one utterance by: {name}"
    return None
