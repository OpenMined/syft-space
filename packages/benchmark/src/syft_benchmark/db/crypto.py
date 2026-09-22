"""Sealing a secret before it reaches the database.

Two kinds pass through this service and neither is its own: the keys to the
model providers, which cost money, and the Space tokens, which speak for their
owner. Both used to sit in the environment, and the Space tokens in a plain text
column — which put them in every dump, backup and replica.

AES-256-GCM, with the credential's name as associated data. The name binds a
ciphertext to its slot: without it, somebody who can write to the table but
knows no key could copy the row of `judge_key` into `subject_key` and quietly
redirect the model under test to a provider of their choosing.

This protects what leaves the database — dumps, backups, replicas, a stolen
volume. It does not protect against someone who can read the process's
environment, where the master key is. That is the ordinary bargain of envelope
encryption with the key outside, and the step beyond it is an external KMS.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32

# What GCM is defined for; a longer nonce is hashed down and gains nothing.
NONCE_BYTES = 12

# Six bytes of SHA-256 will not collide across the handful of keys one
# installation ever has. A fingerprint rather than a serial number, so the id
# cannot drift apart from the key it names.
FINGERPRINT_CHARS = 12


class SecretsNotConfigured(RuntimeError):
    """There is no master key, so there is nowhere to put a secret."""


class SecretUnreadable(RuntimeError):
    """A stored secret will not open with any key this process has."""


def new_key() -> str:
    """A fresh master key, base64.

    It exists so that nobody invents one: a key typed by a human is a password.
    """
    return base64.b64encode(os.urandom(KEY_BYTES)).decode()


def _decode(raw: str, where: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001 - any malformed base64 means the same
        raise SecretsNotConfigured(
            f"{where} is not valid base64 — generate one with "
            f"`syft-benchmark secrets keygen`"
        ) from exc
    if len(key) != KEY_BYTES:
        raise SecretsNotConfigured(
            f"{where} is {len(key)} bytes, and AES-256 needs {KEY_BYTES} — "
            f"generate one with `syft-benchmark secrets keygen`"
        )
    return key


def fingerprint(key: bytes) -> str:
    """The id a key is known by in the rows it sealed."""
    return hashlib.sha256(key).hexdigest()[:FINGERPRINT_CHARS]


@dataclass(frozen=True, slots=True)
class Cipher:
    """The keys this process can seal with and open with.

    One key seals; every key opens. That asymmetry is the whole of rotation.
    """

    active: bytes
    retired: dict[str, bytes]

    @property
    def active_id(self) -> str:
        return fingerprint(self.active)

    def _key_for(self, key_id: str) -> bytes:
        if key_id == self.active_id:
            return self.active
        key = self.retired.get(key_id)
        if key is None:
            raise SecretUnreadable(
                f"the secret was sealed with key {key_id}, which this process "
                f"does not have. Put it back in BENCH_SECRET_KEYS_RETIRED, or "
                f"set the secret again"
            )
        return key

    def seal(self, name: str, value: str) -> tuple[bytes, bytes, str]:
        """Encrypt one secret, bound to its name.

        Returns:
            The ciphertext, the nonce and the id of the key that sealed it
        """
        nonce = os.urandom(NONCE_BYTES)
        blob = AESGCM(self.active).encrypt(
            nonce, value.encode("utf-8"), name.encode("utf-8")
        )
        return blob, nonce, self.active_id

    def open(self, name: str, blob: bytes, nonce: bytes, key_id: str) -> str:
        """Decrypt one secret.

        Raises:
            SecretUnreadable: no key opens it, or the row was written for
                another name
        """
        try:
            plain = AESGCM(self._key_for(key_id)).decrypt(
                nonce, blob, name.encode("utf-8")
            )
        except InvalidTag as exc:
            raise SecretUnreadable(
                f"the secret {name!r} did not open: either the key is wrong, or "
                f"the row was written for a different name"
            ) from exc
        return plain.decode("utf-8")


def cipher_from(active: str, retired: dict[str, str] | None = None) -> Cipher:
    """The cipher for this installation.

    Args:
        active: The master key, base64
        retired: Keys kept only so that rows sealed under them still open

    Raises:
        SecretsNotConfigured: there is no key, or it is not a key
    """
    if not active:
        raise SecretsNotConfigured(
            "BENCH_SECRET_KEY is not set, and secrets are not stored in the "
            "clear. Generate one with `syft-benchmark secrets keygen`"
        )
    key = _decode(active, "BENCH_SECRET_KEY")
    kept = {
        key_id: _decode(raw, f"BENCH_SECRET_KEYS_RETIRED[{key_id}]")
        for key_id, raw in (retired or {}).items()
    }
    return Cipher(active=key, retired=kept)
