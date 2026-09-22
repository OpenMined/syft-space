"""The frozen slice: that exact set of questions, not "roughly the same one".

A port of `eval_arena/question_set.py` from LiveTruth. The task is the same, and
it is not about convenience but about comparability.

Our set is alive: ``generate`` adds items every cycle, screening moves pairs to
``rejected``, the labelling of the control half gets refined. As long as "which
questions" is decided by selection on the fly, two runs take different sets — and
the difference in numbers between them means not what was measured but that the
set has grown. This is especially visible where the comparison is the whole point
of the measurement: arms A and C are obliged to go over one set, otherwise "the
price of context" is computed between different halves.

The slice pins the list of ``qa_id`` in order, together with a **fingerprint** of
the question and the gold answer. Identifiers alone are not enough: a pair
survives regeneration, its text does not. The gold answer was refined, the
question reworded — the identifier is the same, the item is different, and the
answers collected relate to the previous one. The fingerprint turns that
substitution from silent into a refusal.

A slice is the WHOLE selection. ``--limit`` does not apply with it: the limit
would select from what has already been selected and would bring back exactly the
drift the slice exists to prevent.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from syft_benchmark.db import QaPair

# The format version. A slice outlives a run and survives code edits: if the
# format ever changes, an old file should say so itself rather than fall apart
# during parsing.
SLICE_VERSION = 1


class SliceMismatch(RuntimeError):
    """The set no longer matches the frozen slice."""


def fingerprint(question: str, answer: str) -> str:
    """A short fingerprint of the question together with the gold answer.

    The gold answer enters the fingerprint on a par with the question: a refined
    gold answer changes the item no less than a reworded question does — the
    judge compares the answer against precisely that.
    """
    payload = "\x00".join([question.strip(), answer.strip()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build(
    space: str, pairs: list[QaPair], *, selection: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Assemble a slice out of the selected items.

    Args:
        space: The Space key — a slice belongs to one node
        pairs: The items in the order they were selected
        selection: What they were selected with; written for a human, not used
            when the slice is applied — the choice has already been made and
            recorded by name

    Returns:
        A slice ready to be written
    """
    return {
        "slice_version": SLICE_VERSION,
        "space": space,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "selection": selection or {},
        "count": len(pairs),
        "generators": sorted({p.generator for p in pairs}),
        "questions": [
            {
                "id": p.id,
                "generator": p.generator,
                "expected_behavior": p.expected_behavior,
                "sha256": fingerprint(p.question, p.answer),
            }
            for p in pairs
        ],
    }


def write(path: Path, data: dict[str, Any]) -> Path:
    """Write the slice. The format is readable: it goes into the repo and is read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def load(path: Path) -> dict[str, Any]:
    """Read a slice.

    Raises:
        SliceMismatch: there is no such file, or it is not a slice
    """
    if not path.exists():
        raise SliceMismatch(f"there is no frozen slice: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SliceMismatch(f"{path} does not parse: {exc}") from exc
    if not isinstance(data, dict) or "questions" not in data:
        raise SliceMismatch(f"{path} is not a frozen-slice file")
    if int(data.get("slice_version") or 0) != SLICE_VERSION:
        raise SliceMismatch(
            f"{path}: slice version {data.get('slice_version')}, "
            f"this build understands {SLICE_VERSION}"
        )
    return data


def apply(
    data: dict[str, Any],
    pairs: list[QaPair],
    *,
    space: str = "",
    strict: bool = True,
) -> list[QaPair]:
    """Select from the set exactly what the slice names, and in its order.

    Args:
        data: The slice that was read
        pairs: The Space active items
        space: What it is being applied to; empty — do not check
        strict: A divergence is a refusal. ``False`` lowers it to a warning and
            throws out the diverged items

    Returns:
        The slice items in the slice order

    Raises:
        SliceMismatch: the slice is not from this Space, or items have
            disappeared, or their text has changed
    """
    owner = str(data.get("space") or "")
    if space and owner and owner != space:
        # Not a soft divergence but a different node: strict has nothing to do
        # with it.
        raise SliceMismatch(
            f"the slice was built for Space {owner!r} and is being applied to "
            f"{space!r} — these are different sets of questions"
        )

    by_id = {pair.id: pair for pair in pairs}
    selected: list[QaPair] = []
    missing: list[str] = []
    changed: list[str] = []

    for entry in data["questions"]:
        pair = by_id.get(str(entry.get("id")))
        if pair is None:
            # The pair is not among the active ones: it was screened out,
            # deleted, or it belongs to a different set.
            missing.append(str(entry.get("id")))
            continue
        expected = str(entry.get("sha256") or "")
        if expected and fingerprint(pair.question, pair.answer) != expected:
            changed.append(pair.id)
            continue
        selected.append(pair)

    if missing or changed:
        details = []
        if missing:
            details.append(
                f"{len(missing)} items are no longer among the active ones "
                f"({_head(missing)})"
            )
        if changed:
            details.append(
                f"{len(changed)} had their question or gold answer changed "
                f"({_head(changed)})"
            )
        message = (
            "the set has diverged from the frozen slice: "
            + "; ".join(details)
            + ". The answers collected relate to the previous items — rebuild "
            "the slice only for a new measurement, not in the middle of one"
        )
        if strict:
            raise SliceMismatch(message)
        logger.warning(f"{message}. Carrying on without them: strict matching is off")

    return selected


def _head(items: list[str], limit: int = 5) -> str:
    shown = ", ".join(items[:limit])
    return f"{shown} …" if len(items) > limit else shown
