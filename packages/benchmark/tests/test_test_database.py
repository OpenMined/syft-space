"""The suite's own database: derived from the live URL, never equal to it."""

from __future__ import annotations

from conftest import _sibling, _test_database

LIVE = "postgresql+psycopg://bench:pw@localhost:5442/benchmark"


def test_the_sibling_is_the_same_server_with_a_suffixed_name() -> None:
    assert (
        _sibling(LIVE) == "postgresql+psycopg://bench:pw@localhost:5442/benchmark_tests"
    )


def test_the_sibling_keeps_the_query_after_the_name() -> None:
    assert (
        _sibling(f"{LIVE}?sslmode=require")
        == "postgresql+psycopg://bench:pw@localhost:5442/benchmark_tests?sslmode=require"
    )


def test_a_url_without_a_database_name_has_no_sibling() -> None:
    assert _sibling("postgresql+psycopg://bench:pw@localhost:5442/") == ""
    assert _sibling("benchmark") == ""


def test_without_an_override_the_sibling_is_used() -> None:
    assert _test_database(LIVE, "") == _sibling(LIVE)


def test_an_override_is_taken_when_it_is_another_database() -> None:
    other = "postgresql+psycopg://ci:ci@db:5432/ci_bench"
    assert _test_database(LIVE, other) == other


def test_an_override_naming_the_live_database_is_refused() -> None:
    assert _test_database(LIVE, LIVE) == ""


def test_a_live_url_with_no_sibling_is_refused() -> None:
    assert _test_database("benchmark", "") == ""
