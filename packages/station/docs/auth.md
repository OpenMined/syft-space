# Auth

The station has no user table and no passwords. SyftHub is the identity
provider; the station turns a successful hub sign-in into its own signed
session cookie and never holds hub credentials longer than the sign-in
call.

## Sign-in: a one-shot proxy

`POST /api/v1/auth/login` (`AuthHandler.login`):

1. `SyftHubIdentityClient.authenticate(email, password)` performs a
   one-shot hub login and fetches the profile (`GET /api/v1/users/me`).
   The hub access token is **used for that one request and discarded** —
   the station stores no hub tokens for members.
2. The role is decided by config: `admin` iff the profile email equals
   `SYFT_STATION_ADMIN_EMAIL`, else `member`. There is exactly one admin,
   and it's a deploy-time decision, not a database row.
3. A `SessionUser` (email, username, name, role) becomes the session
   cookie payload.

Hub failures map to clean HTTP errors: bad credentials → 401, hub
unreachable → 502 ("SyftHub is unavailable — try again shortly").

## Sessions: stateless signed cookies

`auth/session.py`. The session lives entirely in a cryptographically
signed cookie — there is no server-side session table, so sessions survive
pod restarts as long as the signing key is stable (the chart preserves it
across `helm upgrade`; see [deployment.md](deployment.md)).

- Cookie name: `__Host-syft_station_session` when
  `session_cookie_secure` is on. The `__Host-` prefix binds the cookie to
  host-only + Secure + Path=/ — browsers then guarantee a space served on
  a sibling subdomain can neither read, set, nor shadow the station's
  session. Plain-HTTP dev falls back to the bare name; the signature is
  the forgery backstop either way.
- Expiry is enforced at verification (`max_age`,
  `session_max_age_seconds`, default 7 days).
- `get_current_user` is the FastAPI dependency (401 without a valid
  cookie); `require_admin` layers the role check (403).

## Emails are one lowercase identity

Every email is lowercased at its parse boundary by the `NormalizedEmail`
type (`shared/email.py`, `Annotated[EmailStr, AfterValidator(str.lower)]`),
applied at all four doors an email can enter through:

| Field | Door |
|---|---|
| `SyftHubProfile.email` | hub sign-in / PAT minting responses |
| `VerifiedBuyer.email` | buyer satellite-token verification |
| `SubmitRequestBody.owner_email` | admin typing an owner in submit-on-behalf |
| `SessionUser.email` | cookie payloads (heals cookies minted before normalization) |

Downstream code — ownership guards, the one-live-request unique index,
balance rows keyed by email — compares verbatim, which is only correct
because lowercase is an invariant established at these boundaries. SyftHub
normalizes the same way, so lowering never conflates two hub accounts. A
data migration (`b13bbb37fe06`) lowercased pre-existing rows and aborts,
listing offenders, if two rows differ only by case.

## Buyer verification (credits)

Buyers never sign in to the station. SyftHub mints them a **satellite
token**, and the station verifies it server-side against the hub
(`POST /api/v1/verify`) using the wallet's **PAT** — a hub API token the
admin pastes at wallet setup or mints one-shot from their password
(`SyftHubIdentityClient.mint_pat` / `whoami`). Guest tokens are rejected;
the verified claims (`VerifiedBuyer`: email + expiry) are what the credits
component bills against. Verification results are cached in memory
(token-hash → email, capped by the token's own expiry) because `/verify`
is a network call on the buyer request path — see
[credits.md](credits.md).

## Testing seams

`SyftHubIdentityClient._build_http_client()` exists so tests inject an
`httpx.MockTransport`; every auth test stubs the hub at the HTTP layer,
never by patching handler internals.
