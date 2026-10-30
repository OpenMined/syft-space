"""The two ways into the control API, as FastAPI dependencies.

The **service routes** — everything except ``/console/*`` — never carry a
question or a reference answer, only targets, settings and job state. One
shared ``control_token`` guards them for the whole installation, and it is
handed only to the Space's own backend, never to a browser.

The **console routes** do return question and answer text, verdicts and
reasoning: an owner reviewing what was generated, filtered or judged has to
see it. They take a short-lived session token (``control/session.py``) minted
for one target by something that already holds the installation token, so a
leaked console link exposes one target until it expires.

Without ``control_token`` the service still answers ``/health`` and tells every
other route that it is not configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from syft_benchmark.config import Settings
from syft_benchmark.control import session as console_sessions
from syft_benchmark.control.session import InvalidSession
from syft_benchmark.db import store


def _bootstrap(request: Request) -> Settings:
    """The settings the app was built with, or a 503 without a control token."""
    conf: Settings = request.app.state.settings
    if not conf.control_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "control is not configured: set BENCH_CONTROL_TOKEN",
        )
    return conf


def authorised(
    request: Request, authorization: Annotated[str, Header()] = ""
) -> Settings:
    """Check the installation key, and hand back a fresh read of the settings.

    The settings are a database row the API edits, so each request reads them
    afresh; the key itself comes from the environment and does not change while
    the process lives.
    """
    conf = _bootstrap(request)
    token = authorization.removeprefix("Bearer ").strip()
    # Constant time: an ordinary `!=` leaks, over many requests, how much of
    # the key is right.
    if not compare_digest(token, conf.control_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "the key did not match")
    return store.apply(conf)


# Module level on purpose: with deferred annotations an alias declared inside a
# function would not resolve, and FastAPI would take the settings for a request
# parameter and answer 422 instead of 401.
Guard = Annotated[Settings, Depends(authorised)]


@dataclass(frozen=True, slots=True)
class ConsoleAuth:
    """What a console session token resolves to: one target, current settings."""

    target_key: str
    settings: Settings


def console_session(
    request: Request, authorization: Annotated[str, Header()] = ""
) -> ConsoleAuth:
    """Check a console session token and resolve it to the one target it names.

    A session token is only ever verified against ``control_token``, never
    compared with it: the two both travel as ``Authorization: Bearer`` and are
    not interchangeable.
    """
    conf = _bootstrap(request)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no session token was given")
    try:
        target_key = console_sessions.verify(token, conf)
    except InvalidSession as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return ConsoleAuth(target_key=target_key, settings=store.apply(conf))


ConsoleGuard = Annotated[ConsoleAuth, Depends(console_session)]
