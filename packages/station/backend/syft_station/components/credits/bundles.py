"""Prepaid bundle catalog — the station's price list for bundle purchases.

Keyed provider → currency → bundles. Providers support disjoint currency
sets (Xendit has no USD; Stripe has no IDR) and may price the currencies
they share differently (SGD below), so the catalogs are kept separate —
a gateway's supported currencies ARE its catalog keys.

SOURCE OF TRUTH: at provisioning the station injects the wallet's slice of
this table (as JSON) into every managed space as ``SYFT_CLUSTER_BUNDLES``,
and spaces publish it on their paid endpoints. SyftHub then buys by bundle
*name* against ``POST /credits/{wallet_id}/invoices``, which prices the
name from this same table — so buyers are only ever offered what a
purchase will actually cost.

syft-space keeps a static copy (``CLUSTER_PREPAID_BUNDLES``) purely as a
fallback for spaces started before their station injected a catalog.
"""

PREPAID_BUNDLES: dict[str, dict[str, list[dict]]] = {
    "xendit": {
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
    },
    "stripe": {
        "USD": [
            {"name": "Starter", "amount": 5},
            {"name": "Basic", "amount": 25},
            {"name": "Pro", "amount": 100},
            {"name": "Enterprise", "amount": 500},
        ],
        "EUR": [
            {"name": "Starter", "amount": 5},
            {"name": "Basic", "amount": 25},
            {"name": "Pro", "amount": 100},
            {"name": "Enterprise", "amount": 500},
        ],
        "GBP": [
            {"name": "Starter", "amount": 5},
            {"name": "Basic", "amount": 20},
            {"name": "Pro", "amount": 80},
            {"name": "Enterprise", "amount": 400},
        ],
        "SGD": [
            {"name": "Starter", "amount": 7},
            {"name": "Basic", "amount": 35},
            {"name": "Pro", "amount": 140},
            {"name": "Enterprise", "amount": 700},
        ],
        "AUD": [
            {"name": "Starter", "amount": 8},
            {"name": "Basic", "amount": 40},
            {"name": "Pro", "amount": 150},
            {"name": "Enterprise", "amount": 750},
        ],
        "CAD": [
            {"name": "Starter", "amount": 7},
            {"name": "Basic", "amount": 35},
            {"name": "Pro", "amount": 140},
            {"name": "Enterprise", "amount": 700},
        ],
        "JPY": [
            # Zero-decimal currency: whole-yen amounts only (see the
            # gateway's minor-unit converter).
            {"name": "Starter", "amount": 500},
            {"name": "Basic", "amount": 2_500},
            {"name": "Pro", "amount": 10_000},
            {"name": "Enterprise", "amount": 50_000},
        ],
        "BRL": [
            {"name": "Starter", "amount": 25},
            {"name": "Basic", "amount": 125},
            {"name": "Pro", "amount": 500},
            {"name": "Enterprise", "amount": 2_500},
        ],
    },
}


def bundle_amount(provider: str, currency: str, bundle_name: str) -> float | None:
    """The price of a named bundle in a provider's currency catalog, or
    None if not listed."""
    for bundle in PREPAID_BUNDLES.get(provider, {}).get(currency, []):
        if bundle["name"] == bundle_name:
            return float(bundle["amount"])
    return None
