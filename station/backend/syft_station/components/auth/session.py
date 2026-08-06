"""Stateless signed-cookie sessions.

The session is an itsdangerous-signed payload in a cookie — no server-side
session table. Expiry is enforced at verification time via the serializer's
timestamp (max_age).
"""

import secrets

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from loguru import logger
from pydantic import BaseModel

from syft_station.config import app_settings

# The __Host- prefix binds the cookie to host-only + Secure + Path=/, which
# browsers enforce: a space served on a sibling/child subdomain can then
# neither read, set, nor shadow the station's session. Browsers only honor
# __Host- on Secure cookies, so the dev loops (plain HTTP) fall back to the
# bare name; the signed payload is the real forgery backstop in both cases.
SESSION_COOKIE = (
    "__Host-syft_station_session"
    if app_settings.session_cookie_secure
    else "syft_station_session"
)

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"


class SessionUser(BaseModel):
    """The signed session payload."""

    email: str
    username: str
    name: str
    role: str


def _session_secret() -> str:
    """Configured secret, or a per-process random one (dev fallback)."""
    if app_settings.session_secret:
        return app_settings.session_secret
    if not hasattr(_session_secret, "_generated"):
        _session_secret._generated = secrets.token_urlsafe(32)  # type: ignore[attr-defined]
        logger.warning(
            "SYFT_STATION_SESSION_SECRET is unset — using a random secret; "
            "sessions will not survive a restart"
        )
    return _session_secret._generated  # type: ignore[attr-defined]


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_session_secret(), salt="syft-station-session")


def set_session_cookie(response: Response, user: SessionUser) -> None:
    token = _serializer().dumps(user.model_dump())
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=app_settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=app_settings.session_cookie_secure,
        path="/",  # required for the __Host- prefix
    )


def clear_session_cookie(response: Response) -> None:
    # Match the set attributes so the browser clears the __Host- cookie.
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=app_settings.session_cookie_secure,
    )


def get_current_user(request: Request) -> SessionUser:
    """Dependency: the signed-in user, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in"
        )
    try:
        payload = _serializer().loads(
            token, max_age=app_settings.session_max_age_seconds
        )
    except SignatureExpired as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        ) from e
    except BadSignature as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        ) from e
    return SessionUser.model_validate(payload)


def require_admin(user: SessionUser = Depends(get_current_user)) -> SessionUser:
    """Dependency: the signed-in admin, or 403."""
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
