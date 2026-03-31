"""Utilities for querying the Tempo blockchain."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from web3 import Web3

from syft_space.config import app_settings

logger = logging.getLogger(__name__)

# Tempo RPC endpoints
TEMPO_MAINNET_RPC_URL = "https://rpc.tempo.xyz"
TEMPO_TESTNET_RPC_URL = "https://rpc.moderato.tempo.xyz"

# pathUSD token contract address (same on both networks)
PATH_USD_ADDRESS = "0x20c0000000000000000000000000000000000000"


def _get_rpc_url() -> str:
    """Get the appropriate Tempo RPC URL based on config."""
    return TEMPO_TESTNET_RPC_URL if app_settings.tempo_testnet else TEMPO_MAINNET_RPC_URL


_w3_instance: Web3 | None = None
_w3_rpc_url: str | None = None


def _get_w3() -> Web3:
    """Get or create a cached Web3 instance."""
    global _w3_instance, _w3_rpc_url
    rpc_url = _get_rpc_url()
    if _w3_instance is None or _w3_rpc_url != rpc_url:
        _w3_instance = Web3(Web3.HTTPProvider(rpc_url))
        _w3_rpc_url = rpc_url
    return _w3_instance


# Minimal ERC-20 ABI for balance queries
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
]

TRANSFER_EVENT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]


def _sync_get_balance(wallet_address: str) -> float:
    """Synchronous balance query (runs in thread pool)."""
    w3 = _get_w3()
    checksum_address = Web3.to_checksum_address(wallet_address)
    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(PATH_USD_ADDRESS),
        abi=ERC20_ABI,
    )

    raw_balance = token_contract.functions.balanceOf(checksum_address).call()

    decimals = 6
    try:
        decimals = token_contract.functions.decimals().call()
    except Exception:
        pass

    return raw_balance / (10**decimals)


def _sync_get_transactions(wallet_address: str) -> list[dict[str, Any]]:
    """Synchronous transaction query (runs in thread pool)."""
    w3 = _get_w3()
    checksum_address = Web3.to_checksum_address(wallet_address)

    latest_block = w3.eth.block_number
    from_block = max(0, latest_block - 1000)

    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(PATH_USD_ADDRESS),
        abi=TRANSFER_EVENT_ABI,
    )

    decimals = 6
    incoming_logs: list = []
    outgoing_logs: list = []

    try:
        incoming_logs = token_contract.events.Transfer.get_logs(
            from_block=from_block,
            to_block=latest_block,
            argument_filters={"to": checksum_address},
        )
    except Exception as e:
        logger.warning(f"Failed to fetch incoming transfers: {e}")

    try:
        outgoing_logs = token_contract.events.Transfer.get_logs(
            from_block=from_block,
            to_block=latest_block,
            argument_filters={"from": checksum_address},
        )
    except Exception as e:
        logger.warning(f"Failed to fetch outgoing transfers: {e}")

    # Batch-fetch all unique blocks to avoid N+1 RPC calls
    all_logs = list(incoming_logs) + list(outgoing_logs)
    block_numbers = {log.blockNumber for log in all_logs}
    block_cache = {}
    for bn in block_numbers:
        block_cache[bn] = w3.eth.get_block(bn)

    transactions = []

    for log in incoming_logs:
        amount = log.args["value"] / (10**decimals)
        block = block_cache[log.blockNumber]
        transactions.append(
            {
                "id": log.transactionHash.hex(),
                "sender_email": log.args["from"],
                "recipient_email": log.args["to"],
                "amount": amount,
                "status": "confirmed",
                "created_at": _timestamp_to_iso(block.timestamp),
                "app_name": "MPP Payment",
                "app_ep_path": "",
            }
        )

    for log in outgoing_logs:
        amount = log.args["value"] / (10**decimals)
        block = block_cache[log.blockNumber]
        transactions.append(
            {
                "id": log.transactionHash.hex(),
                "sender_email": log.args["from"],
                "recipient_email": log.args["to"],
                "amount": -amount,
                "status": "confirmed",
                "created_at": _timestamp_to_iso(block.timestamp),
                "app_name": "MPP Payment",
                "app_ep_path": "",
            }
        )

    transactions.sort(key=lambda t: t["created_at"], reverse=True)
    return transactions


async def get_wallet_balance(wallet_address: str) -> float:
    """Query pathUSD balance for a wallet address from Tempo blockchain.

    Runs the blocking Web3 RPC call in a thread pool to avoid blocking the event loop.
    """
    try:
        return await asyncio.to_thread(_sync_get_balance, wallet_address)
    except Exception as e:
        logger.error(f"Failed to query Tempo balance for {wallet_address}: {e}")
        return 0.0


async def get_wallet_transactions(wallet_address: str) -> list[dict[str, Any]]:
    """Query recent transactions for a wallet address from Tempo blockchain.

    Runs the blocking Web3 RPC calls in a thread pool to avoid blocking the event loop.
    """
    try:
        return await asyncio.to_thread(_sync_get_transactions, wallet_address)
    except Exception as e:
        logger.error(f"Failed to query Tempo transactions for {wallet_address}: {e}")
        return []


def _timestamp_to_iso(timestamp: int) -> str:
    """Convert Unix timestamp to ISO 8601 string."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
