"""Shuffling the answer options.

The position of the correct option used to be set by the generator model, and
the distribution came out as anything but uniform: in the original the false
statement of "two truths and a lie" stood at position C in 26 cases out of 26,
and MCQ's guessing base turned out to be 0.60 instead of 0.25. A model always
answering "C" got excellent accuracy on such a dataset while knowing nothing
about the corpus.

For the measurement this breaks the main thing: a correct answer in arm A has
to mean that the corpus is known to the model — whereas it would mean a match
with the generator's favourite letter.

The shuffling is deterministic: the seed is derived from the item's text, so
one and the same question is always laid out the same way. This is not
pedantry — regenerating the dataset must not change answers already collected,
and an auditor has to be able to reproduce the layout from the question alone.
"""

from __future__ import annotations

import hashlib
import random

LETTERS = "ABCDEFGH"


def seed_of(text: str) -> int:
    """The seed from the item's text: same question, same layout."""
    digest = hashlib.sha256(" ".join(text.split()).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def shuffle_options(
    values: list[str], correct: int, seed_text: str
) -> tuple[list[str], int, int]:
    """Lay the options out and say where the correct one went.

    Args:
        values: The options in the order the generator produced them
        correct: The index of the correct option in that order
        seed_text: The text the seed is taken from — usually the question

    Returns:
        The shuffled options, the correct one's new index and the seed
    """
    seed = seed_of(seed_text)
    order = list(range(len(values)))
    random.Random(seed).shuffle(order)
    shuffled = [values[i] for i in order]
    return shuffled, order.index(correct), seed
