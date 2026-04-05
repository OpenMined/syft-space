"""MPP wallet provider — adapter for Tempo blockchain wallets.

This is an interface adapter (outer layer) that implements the
WalletProvider Protocol. All external dependencies (eth_account,
pympp) are isolated here — the WalletHandler never imports them.
"""

import secrets
from typing import Any

from eth_account import Account
from mpp.methods.tempo import TempoAccount
from pydantic import BaseModel

from syft_space.components.wallets.interfaces import SetupResult
from syft_space.components.wallets.mpp.config import MppWalletConfig


class MppWalletProvider:
    """Adapter for MPP/Tempo blockchain wallets."""

    NAME = "mpp"

    @property
    def config_class(self) -> type[BaseModel]:
        return MppWalletConfig

    async def setup_wallet(self, raw_credentials: dict[str, Any]) -> SetupResult:
        """Create or import MPP wallet.

        - Empty dict → generate new keypair
        - {"private_key": "0x..."} → import and derive address
        """
        if "private_key" in raw_credentials:
            try:
                tempo_acct = TempoAccount.from_key(raw_credentials["private_key"])
            except Exception as e:
                raise ValueError(f"Invalid private key: {e}") from e
        else:
            acct = Account.create()
            tempo_acct = TempoAccount.from_key(acct.key.hex())

        mpp_secret_key = secrets.token_hex(32)

        return SetupResult(
            credentials={
                "wallet_address": tempo_acct.address,
                "wallet_private_key": tempo_acct.private_key,
                "mpp_secret_key": mpp_secret_key,
            },
            display={"wallet_address": tempo_acct.address},
        )
