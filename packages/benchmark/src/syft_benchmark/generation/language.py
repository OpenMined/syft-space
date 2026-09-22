"""Detecting a chunk's language and choosing the path for extractive generators.

The task is not "English or not". Extractive generators cut a span out of a
sentence using spaCy, and spaCy handles a couple of dozen languages — the
question is whether a model is installed for a particular document's language.
If so, we go through it: that is deterministic, free, and the gold answer is cut
out of the text rather than composed. If not, the same chunk is processed by an
LLM, which is indifferent to the language.

The decision is made per document and is never put to the user: a corpus may be
mixed, and the choice of path is an implementation detail, not a matter of
meaning.

Language detection goes by the function words spaCy carries around for each
language. A separate library is not needed here: the question asked is not
"what language is this at all" but "does the text look like one of those we have
a model for", and stop words answer it more precisely than a universal detector.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from loguru import logger

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# The share of function words below which we take the language to be a
# different one. The threshold is low: technical documentation has noticeably
# fewer function words than prose.
_HIT_THRESHOLD = 0.08

# How many words are enough to judge the language by.
_MIN_WORDS = 12


@lru_cache(maxsize=1)
def spacy_available() -> bool:
    """Whether spaCy itself is installed.

    It is optional: without it the extractive generators work through an LLM,
    and that is a working mode, not a degradation.
    """
    try:
        import spacy  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=16)
def load_model(name: str) -> Any | None:
    """Load a spaCy model by name. None — it is not installed."""
    if not spacy_available():
        return None
    import spacy

    try:
        return spacy.load(name)
    except OSError:
        logger.debug(f"the spaCy model {name!r} is not installed")
        return None


@lru_cache(maxsize=16)
def _stopwords(lang: str) -> frozenset[str]:
    """A language's function words from spaCy's own distribution."""
    if not spacy_available():
        return frozenset()
    try:
        module = __import__(f"spacy.lang.{lang}.stop_words", fromlist=["STOP_WORDS"])
    except ImportError:
        return frozenset()
    words: set[str] = getattr(module, "STOP_WORDS", set())
    return frozenset(w.lower() for w in words)


def detect_language(text: str, candidates: tuple[str, ...]) -> str | None:
    """Which of the candidate languages the text most resembles.

    Args:
        text: A chunk of the document
        candidates: The codes of the languages we have models for

    Returns:
        A language code, or None if none of them reached the threshold
    """
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if len(words) < _MIN_WORDS:
        return None

    best: tuple[float, str] | None = None
    for lang in candidates:
        stop = _stopwords(lang)
        if not stop:
            continue
        share = sum(1 for w in words if w in stop) / len(words)
        if share >= _HIT_THRESHOLD and (best is None or share > best[0]):
            best = (share, lang)

    return best[1] if best else None


def pick_spacy_model(text: str, models: dict[str, str]) -> Any | None:
    """The spaCy model for this text's language, if there is one.

    Args:
        text: The chunk whose language we choose by
        models: The mapping "language code -> model name" from the settings

    Returns:
        A loaded model, or None — then the chunk will go through the LLM
    """
    if not models or not spacy_available():
        return None

    lang = detect_language(text, tuple(models))
    if lang is None:
        return None

    model = load_model(models[lang])
    if model is None:
        logger.info(
            f"the language was detected as {lang!r}, but the model "
            f"{models[lang]!r} is not installed — the chunk will go through the LLM"
        )
    return model
