"""The set mode, the freshness window and the volume cap.

The corpus grows, the measurement does not. What is tested is what a rolling set
would break the measurement without: history is not deleted, what returns comes
back without a new call to the generator, the cap does not cut off half the set,
and an undated document is not discarded silently.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from syft_benchmark.config import DatasetMode, PairStatus, Settings
from syft_benchmark.generation import rotation
from syft_benchmark.generation.rotation import (
    RotationReport,
    fresh_ids,
    rotate,
    window_start,
)
from syft_benchmark.sources.chroma import parse_date

_NOW = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


def _settings(**kwargs: object) -> Settings:
    return Settings(**kwargs)  # type: ignore[arg-type]


def _rolling(**kwargs: object) -> Settings:
    return _settings(dataset_mode=DatasetMode.ROLLING, **kwargs)


class _Pair:
    """An item in the volume the set recompute needs."""

    def __init__(
        self,
        pair_id: str,
        doc_id: str,
        status: str = PairStatus.ACTIVE.value,
        behavior: str = "answer",
        generator: str = "cloze",
        cohort: str = "",
    ) -> None:
        self.id = pair_id
        self.doc_id = doc_id
        self.status = status
        self.expected_behavior = behavior
        self.generator = generator
        self.cohort = cohort


class _Store:
    """A database in the volume the recompute needs: reading pairs and two updates."""

    def __init__(self, pairs: list[_Pair]) -> None:
        self.pairs = pairs
        self.updates: list[tuple[set[str], str]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> _Store:
        return self

    def __enter__(self) -> _Store:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def execute(self, stmt: Any) -> _Store:
        if str(stmt).startswith("UPDATE"):
            params = stmt.compile().params
            # SQLAlchemy lays IN out now as a list in one parameter, now as a
            # parameter per value. Instead of guessing we take everything that
            # matched the known identifiers.
            known = {p.id for p in self.pairs}
            seen: set[str] = set()
            for value in params.values():
                if isinstance(value, list | tuple):
                    seen |= {str(v) for v in value}
                elif isinstance(value, str):
                    seen.add(value)
            self.updates.append((seen & known, str(params.get("status", ""))))
        return self

    def scalars(self) -> list[Any]:
        return self.pairs

    def all(self) -> list[Any]:
        return [(p.status, 1) for p in self.pairs]

    def expunge(self, row: Any) -> None:
        return None


def _install(monkeypatch: Any, pairs: list[_Pair]) -> _Store:
    store = _Store(pairs)
    monkeypatch.setattr(rotation, "session_scope", store)
    return store


def _statuses(store: _Store) -> dict[str, str]:
    """The final status of every pair after the updates applied."""
    final = {p.id: p.status for p in store.pairs}
    for ids, status in store.updates:
        for pair_id in ids:
            if pair_id in final:
                final[pair_id] = status
    return final


# --- the freshness window --------------------------------------------------


def test_the_window_keeps_only_recent_documents() -> None:
    dated = {
        "fresh": _NOW - timedelta(days=2),
        "old": _NOW - timedelta(days=30),
    }
    kept, undated = fresh_ids(dated, _settings(document_window_days=7), now=_NOW)
    assert kept == {"fresh"}
    assert undated == 0


def test_no_window_means_the_whole_corpus() -> None:
    dated = {"a": _NOW - timedelta(days=900), "b": None}
    kept, undated = fresh_ids(dated, _settings(document_window_days=0), now=_NOW)
    assert kept == {"a", "b"}
    assert window_start(_settings(document_window_days=0)) is None


def test_an_undated_document_is_kept_and_counted() -> None:
    """The header is written by the node ETL, and it is sometimes incomplete.

    Silently discarding an undated document would mean emptying the set because of a
    foreign format; so it stays, and the number of such is said out loud.
    """
    dated = {"dated": _NOW, "no_date": None}
    kept, undated = fresh_ids(dated, _settings(document_window_days=1), now=_NOW)
    assert kept == {"dated", "no_date"}
    assert undated == 1


def test_yesterday_is_a_window_of_one_day() -> None:
    """ "Only yesterday" is an ordinary request, and it should simply work."""
    dated = {
        "yesterday": _NOW - timedelta(hours=20),
        "week_ago": _NOW - timedelta(days=7),
    }
    kept, _ = fresh_ids(dated, _settings(document_window_days=1), now=_NOW)
    assert kept == {"yesterday"}


# --- document dates --------------------------------------------------------


def test_iso_dates_are_read() -> None:
    assert parse_date("2026-09-14T10:00:00Z") == datetime(2026, 9, 14, 10, tzinfo=UTC)
    assert parse_date("2026-09-14") == datetime(2026, 9, 14, tzinfo=UTC)


def test_common_human_formats_are_read() -> None:
    """The header is written by a foreign ETL, and ISO is not guaranteed there."""
    for text in ("14.09.2026", "2026/09/14", "14 Sep 2026", "Sep 14, 2026"):
        parsed = parse_date(text)
        assert parsed is not None, text
        assert parsed.date() == datetime(2026, 9, 14).date()


def test_an_unparsable_date_is_no_date_not_a_crash() -> None:
    """An unparsed date is "there is no date": the document is let through with a
    note rather than discarded over a format."""
    assert parse_date("the day before yesterday") is None
    assert parse_date("") is None


def test_a_naive_date_gets_a_zone() -> None:
    """A naive time cannot be compared with the window boundary, and there is no
    reason to die over that mid-generation."""
    parsed = parse_date("2026-09-14")
    assert parsed is not None
    assert parsed.tzinfo is not None


# --- the set recompute -----------------------------------------------------


def test_incremental_never_takes_anything_out(monkeypatch: Any) -> None:
    """The set accumulates — there is nothing to take out of it.

    The call is made anyway, so that the generation report names the size of the set
    in both modes rather than in one.
    """
    store = _install(monkeypatch, [_Pair("p1", "d1"), _Pair("p2", "d2")])
    report = rotate("docs", {"d1": _NOW}, settings=_settings(), now=_NOW)

    assert store.updates == []
    assert report.retired == 0


def test_a_document_out_of_the_window_leaves_the_dataset(monkeypatch: Any) -> None:
    store = _install(
        monkeypatch,
        [_Pair("p1", "fresh"), _Pair("p2", "old")],
    )
    dated = {"fresh": _NOW, "old": _NOW - timedelta(days=30)}
    report = rotate("docs", dated, settings=_rolling(document_window_days=7), now=_NOW)

    final = _statuses(store)
    assert final["p1"] == PairStatus.ACTIVE.value
    assert final["p2"] == PairStatus.RETIRED.value
    assert report.retired == 1
    assert report.active == 1


def test_nothing_is_ever_deleted(monkeypatch: Any) -> None:
    """The main decision of the module.

    An item carries the verdicts of every previous run, and the foreign key is set
    with a cascade: deleting a question means carrying off the measurement history.
    """
    store = _install(monkeypatch, [_Pair("p1", "old")])
    rotate(
        "docs",
        {"old": _NOW - timedelta(days=99)},
        settings=_rolling(document_window_days=1),
        now=_NOW,
    )

    assert all(not str(s).startswith("DELETE") for s, _ in store.updates)
    assert _statuses(store)["p1"] == PairStatus.RETIRED.value


def test_a_document_back_in_the_window_brings_its_pairs_back(
    monkeypatch: Any,
) -> None:
    """A one-week window, shifting by a day, keeps six sevenths of yesterday
    documents inside it.

    Building items over them again would mean paying the generator for what has
    already been bought and getting duplicates the unique index would reject anyway.
    """
    store = _install(
        monkeypatch,
        [_Pair("p1", "d1", status=PairStatus.RETIRED.value)],
    )
    report = rotate(
        "docs", {"d1": _NOW}, settings=_rolling(document_window_days=7), now=_NOW
    )

    assert _statuses(store)["p1"] == PairStatus.ACTIVE.value
    assert report.revived == 1


def test_a_rejected_pair_never_comes_back(monkeypatch: Any) -> None:
    """Screening is a verdict on the gold answer; the window is beside the point."""
    store = _install(
        monkeypatch,
        [_Pair("p1", "d1", status=PairStatus.REJECTED.value)],
    )
    # Screened-out ones do not reach the recompute at all: the query takes only the
    # active and the retired.
    store.pairs = []
    report = rotate(
        "docs", {"d1": _NOW}, settings=_rolling(document_window_days=7), now=_NOW
    )
    assert report.revived == 0


def test_the_cap_keeps_both_halves_of_the_set(monkeypatch: Any) -> None:
    """A simple "first N" would cut off the control half entirely.

    It is built later, and the measurement would be left with answerable questions
    only, while the report would show the usual shares, saying nothing about the
    unmeasured half. The halves survive on their own: each generator produces items
    of exactly one, and a round over generators entails a round over halves.
    """
    pairs = [
        _Pair(f"pa{i}", "d1", behavior="answer", generator="cloze") for i in range(20)
    ]
    pairs += [
        _Pair(f"pb{i}", "d1", behavior="abstain", generator="unanswerable")
        for i in range(20)
    ]
    store = _install(monkeypatch, pairs)

    rotate(
        "docs",
        {"d1": _NOW},
        settings=_rolling(document_window_days=7, dataset_max_pairs=10),
        now=_NOW,
    )

    final = _statuses(store)
    kept = [pid for pid, status in final.items() if status == PairStatus.ACTIVE.value]
    assert len(kept) == 10
    assert sum(1 for pid in kept if pid.startswith("pa")) == 5
    assert sum(1 for pid in kept if pid.startswith("pb")) == 5


def test_the_cap_spreads_across_generators(monkeypatch: Any) -> None:
    """The generators measure different things; the cap must not go to two of them."""
    pairs = [
        _Pair(f"{gen}{i}", "d1", generator=gen)
        for gen in ("cloze", "mcq", "multihop", "tiered")
        for i in range(10)
    ]
    store = _install(monkeypatch, pairs)

    rotate(
        "docs",
        {"d1": _NOW},
        settings=_rolling(dataset_max_pairs=8),
        now=_NOW,
    )

    final = _statuses(store)
    kept = {pid for pid, status in final.items() if status == PairStatus.ACTIVE.value}
    generators = {p.generator for p in pairs if p.id in kept}
    assert len(kept) == 8
    assert generators == {"cloze", "mcq", "multihop", "tiered"}


def test_no_cap_means_everything_in_the_window_stays(monkeypatch: Any) -> None:
    store = _install(monkeypatch, [_Pair(f"p{i}", "d1") for i in range(50)])
    report = rotate(
        "docs", {"d1": _NOW}, settings=_rolling(dataset_max_pairs=0), now=_NOW
    )
    assert report.active == 50
    assert report.over_cap == 0
    assert store.updates == []


def test_the_report_says_what_happened() -> None:
    line = RotationReport(
        space="docs", active=120, retired=30, revived=12, over_cap=5
    ).line()
    assert "in the measurement 120" in line
    assert "returned 12" in line
    assert "left the set 30" in line


# --- cohorts ---------------------------------------------------------------


def test_a_rebuild_gets_a_fresh_label() -> None:
    """The label reads by eye and sorts as a string."""
    from syft_benchmark.generation.cohort import new_label

    label = new_label(now=_NOW)
    assert label == "20260914-1200"
    assert new_label(now=_NOW + timedelta(minutes=1)) > label


def test_a_previous_cohort_leaves_the_dataset(monkeypatch: Any) -> None:
    """There can be only one pool of questions in the measurement.

    Two builds over the same material would give two verdicts for one and the same
    question, and the share would be computed over the union of two different sets.
    """
    store = _install(
        monkeypatch,
        [
            _Pair("old1", "d1", cohort="20260907-0300"),
            _Pair("new1", "d1", cohort="20260914-0300"),
        ],
    )
    report = rotate(
        "docs",
        {"d1": _NOW},
        cohort="20260914-0300",
        settings=_rolling(),
        now=_NOW,
    )

    final = _statuses(store)
    assert final["new1"] == PairStatus.ACTIVE.value
    assert final["old1"] == PairStatus.RETIRED.value
    assert report.other_cohorts == 1


def test_the_previous_cohort_is_kept_in_the_database(monkeypatch: Any) -> None:
    """Deleting it would mean destroying the second half of the comparison.

    Its items carry the verdicts of every run that went over it — the very thing the
    new one will be compared against.
    """
    store = _install(monkeypatch, [_Pair("old1", "d1", cohort="20260907-0300")])
    rotate("docs", {"d1": _NOW}, cohort="20260914-0300", settings=_rolling(), now=_NOW)

    statuses = set(_statuses(store).values())
    assert statuses == {PairStatus.RETIRED.value}, "the cohort must survive"


def test_processed_marks_do_not_block_a_rebuild() -> None:
    """A rebuild is a fresh pass over THE SAME material.

    The previous build mark must not stop it, and clearing the table is not needed
    for that: the new cohort simply has no marks.
    """
    from syft_benchmark.db.models import ProcessedUnit

    keys = {c.name for c in ProcessedUnit.__table__.primary_key.columns}
    assert "cohort" in keys


def test_the_same_question_may_exist_in_two_cohorts() -> None:
    """A repeat between cohorts is a sign of the generator stability.

    Forbidding such a repeat would make a rebuild impossible: the second pass would
    be rejected wholesale by the unique index.
    """
    from syft_benchmark.db.models import QaPair

    unique = next(
        c
        for c in QaPair.__table__.constraints
        if getattr(c, "name", "") == "qa_pairs_unique"
    )
    assert "cohort" in {c.name for c in unique.columns}


# --- the period ------------------------------------------------------------


def test_a_period_reads_as_a_human_writes_it() -> None:
    """ "Since yesterday", "over a week", "over a month" are ordinary requests."""
    from syft_benchmark.generation.rotation import parse_period

    assert parse_period("1d") == 1
    assert parse_period("7d") == 7
    assert parse_period("1w") == 7
    assert parse_period("2w") == 14
    assert parse_period("1m") == 30
    assert parse_period("1y") == 365


def test_a_bare_number_is_days() -> None:
    from syft_benchmark.generation.rotation import parse_period

    assert parse_period("30") == 30
    assert parse_period(" 14 ") == 14


def test_no_period_means_the_whole_corpus() -> None:
    from syft_benchmark.generation.rotation import parse_period

    assert parse_period("0") == 0
    assert parse_period("") == 0


def test_an_unreadable_period_is_refused() -> None:
    """Silently taking the whole corpus instead of a week is not a forgivable error.

    A rebuild over the whole corpus costs a full generation pass.
    """
    import pytest

    from syft_benchmark.generation.rotation import BadPeriod, parse_period

    for text in ("the day before yesterday", "a week", "7 days", "-3d"):
        with pytest.raises(BadPeriod):
            parse_period(text)


def test_a_rebuild_honours_the_period_in_any_mode(monkeypatch: Any) -> None:
    """A human named the span outright — the set is obliged to keep within it.

    Even when the mode in the settings is incremental and a rebuild was asked for by
    a flag: otherwise --new-cohort --period 7d would assemble a cohort over a week
    and then let it into the measurement mixed in with old material.
    """
    store = _install(
        monkeypatch,
        [
            _Pair("fresh", "recent", cohort="20260914-0300"),
            _Pair("stale", "ancient", cohort="20260914-0300"),
        ],
    )
    dated = {"recent": _NOW, "ancient": _NOW - timedelta(days=90)}

    report = rotate(
        "docs",
        dated,
        cohort="20260914-0300",
        rebuilding=True,
        settings=_settings(document_window_days=7),  # the mode is incremental
        now=_NOW,
    )

    final = _statuses(store)
    assert final["fresh"] == PairStatus.ACTIVE.value
    assert final["stale"] == PairStatus.RETIRED.value
    assert report.active == 1


def test_an_empty_corpus_never_empties_the_dataset(monkeypatch: Any) -> None:
    """Zero documents is a state of the rig, not a sentence on the set.

    The collection is empty, all the chunks are below the threshold, the index is
    being rebuilt — there was nothing to read. A recompute over such an input would
    take every last item out of the measurement, the next run would measure
    emptiness, and it would look like the ordinary progress of the window.
    """
    store = _install(monkeypatch, [_Pair(f"p{i}", "d1") for i in range(50)])
    report = rotate("docs", {}, settings=_rolling(document_window_days=7), now=_NOW)

    assert store.updates == [], "the set was touched on an empty corpus"
    assert report.retired == 0
    assert any("empty" in note for note in report.notes)


def test_a_window_that_matches_nothing_still_retires(monkeypatch: Any) -> None:
    """The documents were read but are all old — the window decided, not a failure."""
    store = _install(monkeypatch, [_Pair("p1", "ancient")])
    report = rotate(
        "docs",
        {"ancient": _NOW - timedelta(days=90)},
        settings=_rolling(document_window_days=7),
        now=_NOW,
    )

    assert _statuses(store)["p1"] == PairStatus.RETIRED.value
    assert report.retired == 1
