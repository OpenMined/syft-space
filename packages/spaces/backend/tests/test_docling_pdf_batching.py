"""Long PDFs are converted in bounded batches, and a failing batch is narrowed
down instead of every page being retried on its own.

A 962-page book once ran out of memory as one batch and then took over an
hour as 962 single-page runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from loguru import logger

from syft_space.components.chunking.docling_local import (
    BATCH_PAGES,
    LocalDoclingBackend,
    _format_duration,
)
from syft_space.components.shared.cancellation import CancelToken
from syft_space.components.shared.ingest_types import IngestFile

FILE = IngestFile(external_id="book.pdf", path=Path("book.pdf"), filename="book.pdf")


def page_chunk(page: int) -> dict:
    return {"text": f"page {page}", "page_numbers": [page]}


class FakeWorker:
    """Stands in for the conversion subprocess; records each range it is given."""

    def __init__(self, respond):
        self.respond = respond
        self.runs: list[tuple[int, int]] = []

    def __call__(self, pdf_path, start, end, images_dir, doc_id, file, cancel):
        self.runs.append((start, end))
        return self.respond(list(range(start, end + 1)))


def convert(total_pages: int, respond) -> tuple[list[int], FakeWorker]:
    """Run the batching over a fake worker; returns (pages converted, worker)."""
    worker = FakeWorker(respond)
    backend = LocalDoclingBackend()
    backend._run_page_subprocess = worker  # type: ignore[method-assign]
    chunks = backend._convert_batched_pages(
        FILE.path, FILE, total_pages, Path("images"), "doc", CancelToken()
    )
    return sorted(c["page_numbers"][0] for c in chunks), worker


def all_fine(pages):
    return [page_chunk(p) for p in pages], []


def killed(pages):
    """What a killed subprocess looks like: nothing back, every page failed."""
    return [], pages


def test_a_long_pdf_is_split_into_bounded_batches():
    total = 2 * BATCH_PAGES + 20

    converted, worker = convert(total, all_fine)

    assert converted == list(range(1, total + 1))
    assert worker.runs == [
        (1, BATCH_PAGES),
        (BATCH_PAGES + 1, 2 * BATCH_PAGES),
        (2 * BATCH_PAGES + 1, total),
    ]


def test_one_bad_page_is_isolated_by_halving_not_by_retrying_every_page():
    bad = BATCH_PAGES // 2 + 3

    def respond(pages):
        return killed(pages) if bad in pages else all_fine(pages)

    converted, worker = convert(BATCH_PAGES, respond)

    assert converted == [p for p in range(1, BATCH_PAGES + 1) if p != bad]
    # Halving needs about 2 * log2(batch) runs; retrying each page needs one per page.
    assert len(worker.runs) <= 15
    assert (bad, bad) in worker.runs


def test_a_batch_too_big_for_memory_is_halved_until_it_fits():
    def respond(pages):
        return killed(pages) if len(pages) > 10 else all_fine(pages)

    converted, worker = convert(BATCH_PAGES, respond)

    assert converted == list(range(1, BATCH_PAGES + 1))
    assert all(end - start + 1 > 1 for start, end in worker.runs)


def test_pages_the_worker_reports_as_failed_are_retried_alone():
    def respond(pages):
        if len(pages) == 1:
            return all_fine(pages)
        return [page_chunk(p) for p in pages if p != 7], [7]

    converted, worker = convert(20, respond)

    assert converted == list(range(1, 21))
    assert worker.runs == [(1, 20), (7, 7)]


def test_a_page_reported_failed_but_covered_by_a_chunk_is_not_retried():
    def respond(pages):
        return [page_chunk(p) for p in pages], [3]

    _, worker = convert(10, respond)

    assert worker.runs == [(1, 10)]


def test_a_page_that_fails_alone_is_skipped_and_the_rest_kept():
    def respond(pages):
        return killed(pages) if 2 in pages else all_fine(pages)

    converted, _ = convert(4, respond)

    assert converted == [1, 3, 4]


def test_an_empty_page_is_not_treated_as_a_failure():
    """A blank page converts cleanly to no chunks; it must not be retried."""

    def respond(pages):
        return [page_chunk(p) for p in pages if p != 2], []

    converted, worker = convert(4, respond)

    assert converted == [1, 3, 4]
    assert worker.runs == [(1, 4)]


# ── progress in the logs ────────────────────────────────────────────────


@pytest.fixture
def log_lines():
    seen: list[str] = []
    handle = logger.add(lambda m: seen.append(m.record["message"]), level="INFO")
    yield seen
    logger.remove(handle)


def test_one_progress_line_per_batch_and_one_when_done(log_lines):
    total = 2 * BATCH_PAGES + 20

    convert(total, all_fine)

    assert [line.split(",")[0] for line in log_lines] == [
        f"Converting book.pdf: {BATCH_PAGES}/{total} pages "
        f"({BATCH_PAGES * 100 // total}%)",
        f"Converting book.pdf: {2 * BATCH_PAGES}/{total} pages "
        f"({2 * BATCH_PAGES * 100 // total}%)",
        f"Converted book.pdf: {total} pages in 0s",
    ]


def test_a_short_pdf_logs_only_the_final_line(log_lines):
    convert(5, all_fine)

    assert log_lines == ["Converted book.pdf: 5 pages in 0s, 0 skipped"]


def test_the_final_line_counts_skipped_pages(log_lines):
    def respond(pages):
        return killed(pages) if 2 in pages else all_fine(pages)

    convert(4, respond)

    assert log_lines[-1] == "Converted book.pdf: 4 pages in 0s, 1 skipped"


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0.4, "0s"), (42, "42s"), (185, "3m05s"), (3725, "1h02m")],
)
def test_durations_read_naturally(seconds, text):
    assert _format_duration(seconds) == text
