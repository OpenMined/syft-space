"""Text processing utilities for word cloud generation.

Uses spaCy for robust NLP: normalization, stop word removal,
lemmatization, and domain-specific filtering.

spaCy itself and its English model are imported lazily inside the
_get_nlp() / _get_stop_words() helpers. Both are slow on cold disk
cache and are only needed by the wordcloud pipeline, not by callers
that just want extract_user_query() — keep app startup fast.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import spacy

    from syft_space.components.endpoints.schemas import ChatMessageRequest

# SyftHub's aggregator wraps every forwarded query in a prompt-builder
# template. All four template variants (NO_CONTEXT, EMPTY_CONTEXT,
# DEFAULT, CITATION) put the actual question between
# `USER QUESTION:\n` and a trailing `\n---` marker. We peel that out so
# analytics captures only what the user typed, not the prompt scaffolding.
_AGGREGATOR_QUESTION_RE = re.compile(
    r"USER QUESTION:\s*\n(?P<q>.*?)\n---",
    re.DOTALL,
)


def _strip_aggregator_wrapper(content: str) -> str:
    """If `content` is a SyftHub-aggregator-wrapped payload, return just
    the question. Otherwise return content unchanged.
    """
    match = _AGGREGATOR_QUESTION_RE.search(content)
    if match:
        return match.group("q").strip()
    return content.strip()


def extract_user_query(messages: str | list[ChatMessageRequest]) -> str:
    """Extract the user's actual query from a request payload.

    Returns the last user-role message content (or the raw string if
    `messages` is a string), with SyftHub-aggregator scaffolding peeled
    off. System prompts, assistant turns, and earlier user turns are
    discarded — analytics treats *this* request as a single question;
    earlier turns were captured as their own events when they fired.
    """
    if isinstance(messages, str):
        return _strip_aggregator_wrapper(messages)
    if isinstance(messages, list):
        for m in reversed(messages):
            if m.role == "user" and m.content:
                return _strip_aggregator_wrapper(m.content)
    return ""


# Compile patterns once at module level
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_NUMBER_RE = re.compile(r"\b\d+\b")
_WHITESPACE_RE = re.compile(r"\s+")

# Lazy-loaded spaCy artifacts
_nlp: spacy.language.Language | None = None
_stop_words: set[str] | None = None


def _get_nlp() -> spacy.language.Language:
    """Get or lazily load the spaCy English model.

    Uses the small model (en_core_web_sm) for speed. Falls back to
    a blank English model if the trained model is not installed.
    """
    global _nlp
    if _nlp is None:
        import spacy  # heavy; defer until first wordcloud call

        try:
            _nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


def _get_stop_words() -> set[str]:
    """Get or lazily load spaCy's English stop word list.

    Returned set is the cached canonical copy — callers that mutate
    (e.g., to merge custom stop words) must copy first.
    """
    global _stop_words
    if _stop_words is None:
        from spacy.lang.en.stop_words import STOP_WORDS

        _stop_words = set(STOP_WORDS)
    return _stop_words


def clean_text_for_wordcloud(
    text: str,
    custom_stop_words: list[str] | None = None,
    min_token_length: int = 2,
) -> str:
    """Clean and tokenize text for word cloud generation.

    Pipeline:
        1. Lowercase and strip URLs, emails, punctuation, numbers
        2. Remove standard English stop words
        3. Remove custom domain-specific stop words
        4. Lemmatize tokens to their base form
        5. Filter short tokens

    Args:
        text: Raw input text to process.
        custom_stop_words: Optional list of domain-specific words to filter
            (e.g., ["endpoint", "query", "dataset"]).
        min_token_length: Minimum character length for a token to be kept.

    Returns:
        Space-separated string of cleaned, lemmatized tokens ready for
        word cloud generation.
    """
    if not text or not text.strip():
        return ""

    # 1. Text normalization
    normalized = text.lower()
    normalized = _URL_RE.sub(" ", normalized)
    normalized = _EMAIL_RE.sub(" ", normalized)
    normalized = _PUNCTUATION_RE.sub(" ", normalized)
    normalized = _NUMBER_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()

    if not normalized:
        return ""

    # 2. Build combined stop word set
    stop_words = set(_get_stop_words())
    if custom_stop_words:
        stop_words.update(w.lower() for w in custom_stop_words)

    # 3. Lemmatize with spaCy and filter
    nlp = _get_nlp()
    doc = nlp(normalized)

    tokens = [
        token.lemma_
        for token in doc
        if (
            not token.is_stop
            and not token.is_punct
            and not token.is_space
            and token.lemma_ not in stop_words
            and len(token.lemma_) >= min_token_length
        )
    ]

    return " ".join(tokens)


def clean_texts_batch(
    texts: list[str],
    custom_stop_words: list[str] | None = None,
    min_token_length: int = 2,
) -> list[str]:
    """Batch-clean multiple texts using spaCy's nlp.pipe() for efficiency.

    Same pipeline as clean_text_for_wordcloud but processes all texts
    in a single pass through spaCy, which is significantly faster than
    calling the single-text function in a loop.

    Args:
        texts: List of raw input texts.
        custom_stop_words: Optional domain-specific words to filter.
        min_token_length: Minimum character length for tokens.

    Returns:
        List of space-separated cleaned token strings (same length as input,
        empty strings for texts that produce no tokens).
    """
    if not texts:
        return []

    stop_words = set(_get_stop_words())
    if custom_stop_words:
        stop_words.update(w.lower() for w in custom_stop_words)

    # Pre-normalize all texts (regex passes are cheap)
    normalized = []
    for text in texts:
        if not text or not text.strip():
            normalized.append("")
            continue
        t = text.lower()
        t = _URL_RE.sub(" ", t)
        t = _EMAIL_RE.sub(" ", t)
        t = _PUNCTUATION_RE.sub(" ", t)
        t = _NUMBER_RE.sub(" ", t)
        t = _WHITESPACE_RE.sub(" ", t).strip()
        normalized.append(t)

    # Batch through spaCy pipeline
    nlp = _get_nlp()
    results: list[str] = []

    non_empty_indices = [i for i, t in enumerate(normalized) if t]
    non_empty_texts = [normalized[i] for i in non_empty_indices]

    processed_docs = list(nlp.pipe(non_empty_texts, batch_size=64))

    doc_by_index: dict[int, object] = dict(
        zip(non_empty_indices, processed_docs, strict=True)
    )

    for i in range(len(normalized)):
        doc = doc_by_index.get(i)
        if doc is None:
            results.append("")
            continue
        tokens = [
            token.lemma_
            for token in doc  # type: ignore[union-attr]
            if (
                not token.is_stop
                and not token.is_punct
                and not token.is_space
                and token.lemma_ not in stop_words
                and len(token.lemma_) >= min_token_length
            )
        ]
        results.append(" ".join(tokens))

    return results


def extract_ngrams(cleaned_text: str, n: int = 1) -> list[str]:
    """Extract n-grams from already-cleaned text.

    Args:
        cleaned_text: Space-separated cleaned tokens from clean_text_for_wordcloud.
        n: N-gram size (1 = unigrams, 2 = bigrams, 3 = trigrams).

    Returns:
        List of n-gram strings (tokens joined by space).
    """
    if not cleaned_text:
        return []

    tokens = cleaned_text.split()

    if n <= 1:
        return tokens

    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
