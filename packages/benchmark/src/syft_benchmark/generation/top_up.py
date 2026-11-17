"""Sizing the top-up: how many more of each kind a build writes after its checks.

A kind the checks left short of its target gets its shortfall written again,
scaled up by how many of its pairs usually survive the checks on this target.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from sqlalchemy import or_, select

from syft_benchmark.config import PairStatus, Settings, StatusReason
from syft_benchmark.db import QaPair, session_scope

# Top-up rounds after the build, at most.
TOP_UP_ROUNDS = 2
# A kind's survival rate is read from its newest decided pairs on the target.
SURVIVAL_WINDOW = 200
# The lowest survival rate a top-up sizes its writes by.
MIN_SURVIVAL = 0.1


def kind_targets(keys: Sequence[str], cap: int, conf: Settings) -> dict[str, int]:
    """How many of each kind should pass the checks: its write budget, and
    with a set cap (``dataset_max_pairs``) no more than an even share of it."""
    share = cap
    if conf.dataset_max_pairs and keys:
        share = math.ceil(conf.dataset_max_pairs / len(keys))
    return {key: min(cap, share) for key in keys}


def survival_rates(space: str, keys: Sequence[str], conf: Settings) -> dict[str, float]:
    """Each kind's share of decided pairs on this target that passed the checks.

    Read from its newest ``SURVIVAL_WINDOW`` pairs that are active, retired
    or rejected, an owner's rejection left out, as (kept + 1) / (decided + 2):
    a kind with no history reads as one half.
    """
    decided = (
        PairStatus.ACTIVE.value,
        PairStatus.RETIRED.value,
        PairStatus.REJECTED.value,
    )
    rates: dict[str, float] = {}
    with session_scope(conf) as session:
        for key in keys:
            statuses = list(
                session.execute(
                    select(QaPair.status)
                    .where(
                        QaPair.space == space,
                        QaPair.generator == key,
                        QaPair.status.in_(decided),
                        or_(
                            QaPair.status_reason.is_(None),
                            QaPair.status_reason != StatusReason.OWNER.value,
                        ),
                    )
                    .order_by(QaPair.created_at.desc(), QaPair.id.desc())
                    .limit(SURVIVAL_WINDOW)
                ).scalars()
            )
            kept = sum(1 for status in statuses if status != PairStatus.REJECTED.value)
            rates[key] = (kept + 1) / (len(statuses) + 2)
    return rates


def top_up_plan(
    targets: Mapping[str, int],
    survived: Mapping[str, int],
    rates: Mapping[str, float],
    cap: int,
) -> dict[str, int]:
    """How many more of each kind to write: its shortfall over its survival
    rate (at least ``MIN_SURVIVAL``), at most ``cap``. Kinds at their target
    are left out."""
    plan: dict[str, int] = {}
    for key, target in targets.items():
        short = target - survived.get(key, 0)
        if short > 0 and cap > 0:
            rate = max(rates.get(key, 0.5), MIN_SURVIVAL)
            plan[key] = min(cap, math.ceil(short / rate - 1e-9))
    return plan


def survivors(written: Mapping[str, Sequence[str]], conf: Settings) -> dict[str, int]:
    """Per kind, how many of the pairs written are active or still pending."""
    ids = [pair_id for group in written.values() for pair_id in group]
    if not ids:
        return {}
    with session_scope(conf) as session:
        rows = session.execute(
            select(QaPair.generator, QaPair.status).where(QaPair.id.in_(ids))
        ).all()
    alive = (PairStatus.ACTIVE.value, PairStatus.PENDING.value)
    counts: dict[str, int] = {}
    for generator, status in rows:
        if status in alive:
            counts[generator] = counts.get(generator, 0) + 1
    return counts
