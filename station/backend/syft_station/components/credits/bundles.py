"""Prepaid bundle catalog — the station's price list for bundle purchases.

CONTRACT MIRROR: this table must match syft-space's ``CLUSTER_PREPAID_BUNDLES``
(``components/wallets/cluster/config.py``). Spaces publish that catalog on
their paid endpoints; SyftHub then buys by bundle *name* against the station's
``POST /credits/{wallet_id}/invoices`` — this table is what prices the name.
If the two drift, the hub offers bundles the station won't sell.
"""

PREPAID_BUNDLES: dict[str, list[dict]] = {
    "IDR": [
        {"name": "Starter", "amount": 10_000},
        {"name": "Basic", "amount": 50_000},
        {"name": "Pro", "amount": 100_000},
        {"name": "Enterprise", "amount": 500_000},
    ],
    "PHP": [
        {"name": "Starter", "amount": 100},
        {"name": "Basic", "amount": 500},
        {"name": "Pro", "amount": 1_000},
        {"name": "Enterprise", "amount": 5_000},
    ],
    "SGD": [
        {"name": "Starter", "amount": 1},
        {"name": "Basic", "amount": 5},
        {"name": "Pro", "amount": 10},
        {"name": "Enterprise", "amount": 50},
    ],
    "MYR": [
        {"name": "Starter", "amount": 5},
        {"name": "Basic", "amount": 20},
        {"name": "Pro", "amount": 50},
        {"name": "Enterprise", "amount": 200},
    ],
    "VND": [
        {"name": "Starter", "amount": 25_000},
        {"name": "Basic", "amount": 100_000},
        {"name": "Pro", "amount": 250_000},
        {"name": "Enterprise", "amount": 1_000_000},
    ],
    "THB": [
        {"name": "Starter", "amount": 35},
        {"name": "Basic", "amount": 150},
        {"name": "Pro", "amount": 350},
        {"name": "Enterprise", "amount": 1_500},
    ],
}


def bundle_amount(currency: str, bundle_name: str) -> float | None:
    """The price of a named bundle in a currency, or None if not in the catalog."""
    for bundle in PREPAID_BUNDLES.get(currency, []):
        if bundle["name"] == bundle_name:
            return float(bundle["amount"])
    return None
