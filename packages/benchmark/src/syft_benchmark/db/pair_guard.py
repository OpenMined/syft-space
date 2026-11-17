"""The one way a pair is deleted.

A pair that took part in a run (has any ``results`` row) is never deleted:
``results.qa_id`` cascades, so a plain delete would take the run's history
with it. Every deletion of ``qa_pairs`` rows goes through ``delete_pairs``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from syft_benchmark.db.models import QaPair, Result


@dataclass(slots=True)
class PairDeletion:
    """What a deletion did: removed ids, and ids kept because they took part."""

    deleted: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)


def delete_pairs(session: Session, pair_ids: Iterable[str]) -> PairDeletion:
    """Delete the given pairs that never took part in a run; skip the rest.

    One statement, so a result written between a check and the delete cannot
    slip through. Ids that do not exist are in neither list.
    """
    wanted = list(dict.fromkeys(pair_ids))
    if not wanted:
        return PairDeletion()
    gone = set(
        session.execute(
            delete(QaPair)
            .where(
                QaPair.id.in_(wanted),
                ~exists().where(Result.qa_id == QaPair.id),
            )
            .returning(QaPair.id)
        ).scalars()
    )
    kept = set(
        session.execute(
            select(QaPair.id).where(QaPair.id.in_([i for i in wanted if i not in gone]))
        ).scalars()
    )
    return PairDeletion(
        deleted=[i for i in wanted if i in gone],
        kept=[i for i in wanted if i in kept],
    )
