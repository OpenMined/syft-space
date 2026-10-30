"""Deterministic shuffling of answer options.

A writer model places the correct option far from uniformly (the lie of "two
truths and a lie" lands last almost always), so a model answering one fixed
letter would score without knowing the corpus. The seed comes from the item's
text: the same question is always laid out the same way, so regenerating the
dataset does not change collected answers and the layout is reproducible from
the question alone.
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
