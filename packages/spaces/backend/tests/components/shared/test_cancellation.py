"""CancelToken: set once, and whoever is listening reacts at once."""

from __future__ import annotations

from syft_space.components.shared.cancellation import CancelToken


def test_cancel_runs_the_action_registered_for_the_active_block():
    token = CancelToken()
    ran: list[str] = []

    with token.on_cancel(lambda: ran.append("stopped")):
        token.cancel()

    assert token.cancelled
    assert ran == ["stopped"]


def test_an_action_registered_after_cancel_runs_at_once():
    token = CancelToken()
    token.cancel()
    ran: list[str] = []

    with token.on_cancel(lambda: ran.append("stopped")):
        pass

    assert ran == ["stopped"]


def test_an_action_is_dropped_when_its_block_ends():
    token = CancelToken()
    ran: list[str] = []
    with token.on_cancel(lambda: ran.append("stopped")):
        pass

    token.cancel()

    assert ran == []


def test_cancelling_twice_runs_the_action_once():
    token = CancelToken()
    ran: list[str] = []

    with token.on_cancel(lambda: ran.append("stopped")):
        token.cancel()
        token.cancel()

    assert ran == ["stopped"]
