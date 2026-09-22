"""settings and sealed credentials

Two tables and one column removed, and together they say where a setting is
allowed to live.

``installation_settings`` is the bottom of the three settings layers. The other
two — the Space's instrument and the node's probe — have always been rows here;
this one was the environment, which is why .env.example ran to three hundred
lines and why changing a default meant going to the host. It is the same kind
of thing as the other two and it is stored the same way: one row, a sparse set
of overrides in JSONB, because an unset field means "take the built-in default"
and for several fields the empty value is itself a decision.

``credentials`` holds what must not be in that document. The settings are read
on every launch, copied into a job's snapshot and every run's params, handed
out by /defaults and written to the log; a provider key kept with them would
travel to all of those places. Each row is sealed with AES-256-GCM, bound to
its own name so a row cannot be moved from one slot into another, and stamped
with the fingerprint of the key that sealed it so that rotation is a step
rather than a guess.

``targets.token`` goes away and its contents move into that table. The Space
tokens speak for their owners and sat in a plain text column, which means they
were in every dump, backup and replica. They are carried over here rather than
discarded — but only if there is a master key to seal them with. Without one
this refuses to run rather than dropping them: an upgrade that silently loses
the access tokens of every endpoint would be discovered at the next
publication, which is exactly when it is most expensive.

The sealing is written out in full below rather than imported from the
package. A migration has to keep working when the code around it has moved on,
and pinning it to a function somebody may rename is how a chain of migrations
stops being replayable.

Revision ID: c4d81ab6f207
Revises: b1c7f2a90e14
Create Date: 2026-09-17 11:48:02.554119

"""

import base64
import hashlib
import os
from collections.abc import Sequence

import sqlalchemy as sa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from alembic import op

revision: str = "c4d81ab6f207"
down_revision: str | Sequence[str] | None = "b1c7f2a90e14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KEY_BYTES = 32
NONCE_BYTES = 12
FINGERPRINT_CHARS = 12
TARGET_PREFIX = "target:"

NO_KEY = (
    "there are Space tokens stored in targets.token and no BENCH_SECRET_KEY to "
    "seal them with. Generate one with `syft-benchmark secrets keygen`, put it "
    "in the environment and run the upgrade again. Refusing rather than "
    "dropping them: an endpoint that quietly lost its token fails at the next "
    "publication, hours after the upgrade looked like it worked"
)


def _master_key() -> bytes | None:
    """The master key from the environment, or from .env if that is where it is.

    The import is local and guarded: this file must still run if the settings
    class is rearranged, and the only thing wanted from it is one string.
    """
    raw = os.environ.get("BENCH_SECRET_KEY", "")
    if not raw:
        try:
            from syft_benchmark.config import env_settings

            raw = env_settings().secret_key
        except Exception:  # noqa: BLE001 - no settings to read is simply no key
            raw = ""
    if not raw:
        return None
    key = base64.b64decode(raw, validate=True)
    if len(key) != KEY_BYTES:
        raise RuntimeError(
            f"BENCH_SECRET_KEY is {len(key)} bytes and AES-256 needs {KEY_BYTES}"
        )
    return key


def _fingerprint(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()[:FINGERPRINT_CHARS]


def upgrade() -> None:
    op.create_table(
        "installation_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "values",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="installation_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "credentials",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("secret", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
    )

    bind = op.get_bind()
    tokens = list(
        bind.execute(
            sa.text(
                "SELECT key, token FROM targets "
                "WHERE token IS NOT NULL AND token <> ''"
            )
        )
    )
    if tokens:
        key = _master_key()
        if key is None:
            raise RuntimeError(NO_KEY)
        key_id = _fingerprint(key)
        box = AESGCM(key)
        for target_key, token in tokens:
            name = f"{TARGET_PREFIX}{target_key}"
            nonce = os.urandom(NONCE_BYTES)
            blob = box.encrypt(nonce, token.encode("utf-8"), name.encode("utf-8"))
            bind.execute(
                sa.text(
                    "INSERT INTO credentials (name, secret, nonce, key_id) "
                    "VALUES (:name, :secret, :nonce, :key_id)"
                ),
                {"name": name, "secret": blob, "nonce": nonce, "key_id": key_id},
            )

    op.drop_column("targets", "token")


def downgrade() -> None:
    op.add_column("targets", sa.Column("token", sa.Text(), nullable=True))

    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT name, secret, nonce FROM credentials WHERE name LIKE :like"
            ),
            {"like": f"{TARGET_PREFIX}%"},
        )
    )
    if rows:
        key = _master_key()
        if key is None:
            raise RuntimeError(
                "the Space tokens are sealed and there is no BENCH_SECRET_KEY to "
                "open them with — going back would put empty tokens in the column"
            )
        box = AESGCM(key)
        for name, secret, nonce in rows:
            token = box.decrypt(bytes(nonce), bytes(secret), name.encode("utf-8"))
            bind.execute(
                sa.text("UPDATE targets SET token = :token WHERE key = :key"),
                {
                    "token": token.decode("utf-8"),
                    "key": name[len(TARGET_PREFIX) :],
                },
            )
        bind.execute(
            sa.text("DELETE FROM credentials WHERE name LIKE :like"),
            {"like": f"{TARGET_PREFIX}%"},
        )

    op.drop_table("credentials")
    op.drop_table("installation_settings")
