"""A question's gold for measuring retrieval: where its answer lives in the corpus.

Stored at generation time in ``QaPair.meta["gold"]``:

    {
      "version": 1,
      "control": false,
      "articles": [{"file_name", "absolute_path", "doc_id", "fingerprint",
                    "chunk_ids"}],
      "evidence": [{"role", "target", "match", "coverage",
                    "passages": [{"text", "chunk_id"}]}]
    }

A retrieval hit is matched by file name, not doc id or chunk id: another
dataset of the same corpus gives the file another doc id and other chunks.
``chunk_ids`` only say where the evidence sat in the dataset the question was
written from. ``fingerprint`` (``sources.text_fingerprint``) tells whether
another dataset's copy of the file is the same text; None — unknown.

Evidence passages are whole sentences copied verbatim from the text the
question was written from, so they can be found in any other chunking of the
article with ``normalize`` and a substring test. One evidence item per thing
the gold rests on (``role``):

  * ``answer`` — the gold answer itself: the masked sentence, the free answer,
    the correct option, the passage the lie of "two truths, one lie" alters;
  * ``claim`` — a true statement of "two truths, one lie";
  * ``hop`` — one fact a multi-hop answer connects (all are needed);
  * ``key_fact`` — one fact a tiered explanation must cover;
  * ``correction`` — a fact refuting a false premise.

A target found verbatim is ``match: "exact"``; a reworded one is found by its
content words (``"overlap"``, ``coverage`` the share found); one not located
keeps its ``target`` with no passages and ``match: "none"``. Control
questions are marked ``control: true``: an unanswerable one has no evidence,
a false premise has its corrections.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from syft_benchmark.generation.extractive import FILL_IN_PREFIX
from syft_benchmark.generation.validate import _content_tokens
from syft_benchmark.sources import Chunk, Document
from syft_benchmark.sources.chroma import FINGERPRINT_SCHEME

META = "gold"
VERSION = 1

ANSWER = "answer"
CLAIM = "claim"
HOP = "hop"
KEY_FACT = "key_fact"
CORRECTION = "correction"

EXACT = "exact"
OVERLAP = "overlap"
NONE = "none"

_MASK = "______"

# Share of a reworded target's content words its passages must hold.
MIN_COVERAGE = 0.6
# A reworded answer may spread over a few sentences, no more.
_MAX_SENTENCES = 3
# The share of a target's words past which no more sentences are added.
_ENOUGH = 0.8
# Targets this short are a single fact: all of it must be in one sentence.
_SHORT_TOKENS = 3

_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
        "−": "-",
        " ": " ",
    }
)
_SPACE = re.compile(r"\s+")
# Where a sentence ends: terminal punctuation, with any closing quotes or
# brackets, before whitespace; or a line break.
_SENTENCE_END = re.compile(r"[.!?…][\"'”’»)\]]*(?=\s)|\n")
# A period after one of these ends an abbreviation ("U.S.", "Nov.", "Co.",
# "W. H. Auden"), not a sentence.
_ABBREVIATION = re.compile(
    r"(?:^|[\s(\"“'‘])(?:[A-Z]|(?:[A-Za-z]\.)+[A-Za-z]|Mr|Mrs|Ms|Dr|Prof|Gov|Sen"
    r"|Rep|Gen|Col|Lt|Sgt|St|Mt|Jr|Sr|Co|Corp|Inc|Ltd|No|Jan|Feb|Mar|Apr|Jun"
    r"|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.$"
)
# A year the writer adds to a date by the anchor rule ("in December" becomes
# "in December 2026"); the article itself may not repeat it.
_YEAR = re.compile(r"^(19|20)\d\d$")
# Words this long are compared by their first letters, so inflections and
# derivations ("defeated", "defeat") count as the same word.
_PREFIX = 5


def normalize(text: str) -> str:
    """Text as evidence is matched: NFKC, casefolded, typographic quotes and
    dashes made plain, whitespace collapsed."""
    plain = unicodedata.normalize("NFKC", text).translate(_QUOTES).casefold()
    return _SPACE.sub(" ", plain).strip()


def sentences(text: str) -> list[str]:
    """The sentences of a text, verbatim, without the surrounding whitespace."""
    found: list[str] = []
    start = 0
    for end in _SENTENCE_END.finditer(text):
        if end.group() != "\n":
            after = text[end.end() :].lstrip()
            if _ABBREVIATION.search(text[start : end.end()]) or (
                after[:1].islower() or after[:1].isdigit()
            ):
                continue
        found.append(text[start : end.end()].strip())
        start = end.end()
    found.append(text[start:].strip())
    return [sentence for sentence in found if sentence]


def _stems(text: str) -> frozenset[str]:
    return frozenset(t[:_PREFIX] for t in _content_tokens(normalize(text)))


def _wanted(target: str) -> frozenset[str]:
    """A target's words, less the years the anchor rule may have added."""
    stems = _stems(target)
    dated = frozenset(s for s in stems if _YEAR.match(s))
    return stems - dated if stems - dated else stems


@dataclass(frozen=True, slots=True)
class _Sentence:
    text: str
    chunk_id: str
    norm: str
    stems: frozenset[str]


def _index(chunks: Sequence[tuple[str, str]]) -> list[_Sentence]:
    """The sentences of ``(chunk_id, text)`` pairs, in order."""
    return [
        _Sentence(
            text=sentence,
            chunk_id=chunk_id,
            norm=normalize(sentence),
            stems=_stems(sentence),
        )
        for chunk_id, text in chunks
        for sentence in sentences(text)
    ]


def _passages(found: Sequence[_Sentence]) -> list[dict[str, str]]:
    return [{"text": s.text, "chunk_id": s.chunk_id} for s in found]


def _evidence(
    role: str,
    target: str,
    found: Sequence[_Sentence],
    match: str,
    coverage: float,
) -> dict[str, Any]:
    return {
        "role": role,
        "target": target,
        "match": match if found else NONE,
        "coverage": round(coverage, 3),
        "passages": _passages(found),
    }


def _exact(
    target: str, index: Sequence[_Sentence], question: str = ""
) -> list[_Sentence] | None:
    """The shortest run of consecutive sentences holding ``target`` verbatim
    (after ``normalize``), within one chunk; of several, the one sharing most
    words with the question."""
    wanted = normalize(target)
    if not wanted:
        return None
    asked = _stems(question)

    def shared(run: Iterable[_Sentence]) -> int:
        return sum(len(asked & s.stems) for s in run)

    for width in range(1, _MAX_SENTENCES + 1):
        runs = [
            run
            for run in (
                index[start : start + width] for start in range(len(index) - width + 1)
            )
            if len({s.chunk_id for s in run}) == 1
            and wanted in " ".join(s.norm for s in run)
        ]
        if runs:
            return list(max(runs, key=shared))
    return None


def _overlap(
    target: str,
    index: Sequence[_Sentence],
    question: str = "",
    must_contain: str = "",
) -> tuple[list[_Sentence], float]:
    """The sentences that hold most of a reworded target's content words.

    A short target is one fact and must sit whole in one sentence; the
    question's words pick between sentences that hold it. A longer one is
    covered greedily by up to ``_MAX_SENTENCES`` sentences, each adding a fair
    share of the words still missing. ``must_contain`` (normalised) must be
    in the first sentence taken.
    """
    wanted = _wanted(target)
    if not wanted:
        return [], 0.0
    asked = _stems(question) - wanted
    needle = normalize(must_contain)
    first = [s for s in index if needle in s.norm] if needle else list(index)

    if len(wanted) <= _SHORT_TOKENS:
        holding = [s for s in first if wanted <= s.stems]
        if not holding:
            return [], 0.0
        return [max(holding, key=lambda s: len(asked & s.stems))], 1.0

    chosen: list[_Sentence] = []
    covered: set[str] = set()
    floor = max(2, round(len(wanted) * 0.15))
    while len(chosen) < _MAX_SENTENCES and len(covered) < len(wanted) * _ENOUGH:
        best_gain, best = 0, None
        for sentence in first if not chosen else index:
            if sentence in chosen:
                continue
            gain = len((wanted - covered) & sentence.stems)
            if gain > best_gain or (
                best is not None
                and gain == best_gain
                and len(asked & sentence.stems) > len(asked & best.stems)
            ):
                best_gain, best = gain, sentence
        if best is None or best_gain < (1 if not chosen else floor):
            break
        chosen.append(best)
        covered |= wanted & best.stems
    coverage = len(covered) / len(wanted)
    if coverage < MIN_COVERAGE:
        return [], coverage
    chosen.sort(key=index.index)
    return chosen, coverage


def locate(
    role: str,
    target: str,
    index: Sequence[_Sentence],
    *,
    question: str = "",
    must_contain: str = "",
) -> dict[str, Any]:
    """One evidence item: ``target`` found verbatim, else by word overlap."""
    found = _exact(target, index, question)
    if found is not None:
        return _evidence(role, target, found, EXACT, 1.0)
    near, coverage = _overlap(target, index, question, must_contain)
    return _evidence(role, target, near, OVERLAP, coverage)


def _option_text(answer: str) -> str:
    """``"B) text"`` -> ``"text"``."""
    head, sep, rest = answer.partition(") ")
    return rest.strip() if sep and len(head) == 1 else answer.strip()


def _filled_sentence(question: str, answer: str) -> str:
    """A fill-in question with its blank filled: the sentence as written."""
    sentence = question.removeprefix(FILL_IN_PREFIX).strip()
    return sentence.replace(_MASK, answer)


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def evidence_for(
    generator: str,
    question: str,
    answer: str,
    meta: dict[str, Any],
    index: Sequence[_Sentence],
) -> list[dict[str, Any]]:
    """The evidence items of one question, by its generator."""
    if generator in ("named_entity_masking", "numeric_masking", "temporal_masking"):
        return [
            locate(
                ANSWER,
                _filled_sentence(question, answer),
                index,
                must_contain=answer,
            )
        ]
    if generator == "mcq":
        stem = question.split("\n", 1)[0]
        return [locate(ANSWER, _option_text(answer), index, question=stem)]
    if generator == "two_truths_one_lie":
        detail = str(meta.get("source_detail") or "").strip()
        items = [locate(ANSWER, detail, index)] if detail else []
        return items + [
            locate(CLAIM, claim, index) for claim in _strings(meta.get("claims"))
        ]
    if generator == "multihop_synthesis":
        return [locate(HOP, hop, index) for hop in _strings(meta.get("hop_facts"))]
    if generator == "tiered_explanation":
        return [
            locate(KEY_FACT, fact, index) for fact in _strings(meta.get("key_facts"))
        ]
    if generator == "false_premise":
        # The grounds refuting the premise; the correction when none are listed.
        grounds = _strings(meta.get("claims")) or [answer]
        return [locate(CORRECTION, ground, index) for ground in grounds]
    if generator == "unanswerable_property":
        return []
    return [locate(ANSWER, answer, index, question=question)]


def evidence_in_text(
    generator: str,
    question: str,
    answer: str,
    meta: dict[str, Any],
    chunk_id: str,
    text: str,
) -> list[dict[str, Any]]:
    """The evidence items of one question, located in one stored text (a
    pair's ``context``) instead of its document."""
    return evidence_for(generator, question, answer, meta, _index([(chunk_id, text)]))


def _article(doc: Document, chunk_ids: Iterable[str]) -> dict[str, Any]:
    return {
        "file_name": doc.file_name,
        "absolute_path": doc.absolute_path,
        "doc_id": doc.doc_id,
        "fingerprint": (
            {"scheme": FINGERPRINT_SCHEME, "sha256": doc.fingerprint}
            if doc.fingerprint
            else None
        ),
        "chunk_ids": list(dict.fromkeys(chunk_ids)),
    }


def unit_chunks(doc: Document, chunk_id: str) -> list[Chunk]:
    """The chunks a question was written from: its own chunk, or every chunk
    of the document for a document-scope question (``doc:<id>``)."""
    own = [c for c in doc.chunks if c.chunk_id == chunk_id]
    return own or list(doc.chunks)


def build_gold(
    generator: str,
    question: str,
    answer: str,
    meta: dict[str, Any],
    doc: Document,
    chunk_id: str,
    *,
    control: bool,
) -> dict[str, Any]:
    """The gold of one question written from ``doc`` (``chunk_id`` as stored)."""
    chunks = unit_chunks(doc, chunk_id)
    index = _index([(c.chunk_id, c.text) for c in chunks])
    evidence = evidence_for(generator, question, answer, meta, index)
    found = [p["chunk_id"] for item in evidence for p in item["passages"]]
    return {
        "version": VERSION,
        "control": control,
        "articles": [_article(doc, found or [c.chunk_id for c in chunks])],
        "evidence": evidence,
    }
