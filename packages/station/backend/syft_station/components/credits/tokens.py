"""Space credits token minting and hashing.

The plaintext token is minted at provisioning, injected into the space's
k8s Secret (SYFT_CLUSTER_CREDITS_TOKEN), and never stored — the station
keeps only the sha256 hash and verifies bearers by hash lookup.
"""

import hashlib
import secrets

CREDIT_TOKEN_PREFIX = "sct_"


def generate_credit_token() -> str:
    """Mint a space credits service token."""
    return f"{CREDIT_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_credit_token(token: str) -> str:
    """sha256 hex digest — the only form the station stores or compares."""
    return hashlib.sha256(token.encode()).hexdigest()
