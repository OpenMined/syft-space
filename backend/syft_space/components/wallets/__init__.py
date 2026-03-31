"""Wallets component — credential management for payment providers."""

from syft_space.components.wallets.entities import Wallet
from syft_space.components.wallets.interfaces import SetupResult, WalletProvider
from syft_space.components.wallets.repository import WalletRepository

__all__ = ["Wallet", "WalletProvider", "SetupResult", "WalletRepository"]
