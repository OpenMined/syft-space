"""Cluster wallet (managed credits): registry, credits client, charger
journaling, exclusivity guards, and seed-on-boot."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from syft_space.components.payments.cluster.charger import ClusterCreditsCharger
from syft_space.components.payments.cluster.credits_client import (
    ClusterCreditsClient,
    ClusterCreditsError,
    InsufficientCreditsError,
)
from syft_space.components.policy_types.interfaces import BalanceShortfallError
from syft_space.components.wallets import seed as seed_module
from syft_space.components.wallets.cluster.config import ClusterWalletConfig
from syft_space.components.wallets.seed import seed_cluster_wallet
from syft_space.components.wallets.wallet_configs import (
    WALLET_CONFIG_REGISTRY,
    WALLET_TYPE_CATEGORIES,
    WalletCategory,
    WalletType,
)
from syft_space.config import app_settings

TENANT = uuid4()
ENDPOINT = uuid4()
WALLET = uuid4()

# ============== Registry ==============


def test_cluster_type_registered_with_own_category():
    assert WALLET_TYPE_CATEGORIES[WalletType.CLUSTER] is WalletCategory.CLUSTER
    assert WALLET_CONFIG_REGISTRY[WalletType.CLUSTER] is ClusterWalletConfig


def test_cluster_policy_types_require_cluster_wallet():
    from syft_space.components.policy_types.cluster.cluster_per_request import (
        ClusterPerRequestPolicy,
    )

    caps = ClusterPerRequestPolicy.capabilities()
    assert caps.requires_wallet is True
    assert caps.required_wallet_type == "cluster"


# ============== Credits client ==============


class _FakeCreditsServer:
    def __init__(self, debit_status: int = 200, refund_status: int = 200):
        self.debit_status = debit_status
        self.refund_status = refund_status
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/api/v1/credits/debit":
            if self.debit_status == 402:
                return httpx.Response(402, json={"balance": 0.01, "required": 0.05})
            return httpx.Response(
                self.debit_status,
                json={"transaction_id": "x", "balance_after": 9.95},
            )
        if request.url.path == "/api/v1/credits/refund":
            return httpx.Response(self.refund_status, json={"refunded": True})
        if request.url.path == "/api/v1/credits/balance":
            return httpx.Response(200, json={"balance": 12.4, "currency": "USD"})
        raise AssertionError(f"unexpected path {request.url.path}")


def _make_client(server: _FakeCreditsServer) -> ClusterCreditsClient:
    client = ClusterCreditsClient("http://cluster:9000", "space-token")
    client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        base_url=client.base_url,
        headers={"Authorization": "Bearer space-token"},
        transport=httpx.MockTransport(server.handler),
    )
    return client


async def test_client_debit_sends_contract_payload_and_bearer():
    server = _FakeCreditsServer()
    tx = uuid4()

    await _make_client(server).debit(
        transaction_id=tx,
        user_email="user@test.com",
        amount=0.05,
        endpoint="my-endpoint",
        charge_unit="request",
        charge_quantity=1,
    )

    request = server.requests[0]
    assert request.headers["authorization"] == "Bearer space-token"
    body = request.read().decode()
    for expected in (str(tx), "user@test.com", "0.05", "my-endpoint"):
        assert expected in body


async def test_client_debit_402_raises_insufficient():
    server = _FakeCreditsServer(debit_status=402)

    with pytest.raises(InsufficientCreditsError) as exc:
        await _make_client(server).debit(
            transaction_id=uuid4(),
            user_email="u@t.co",
            amount=0.05,
            endpoint="e",
            charge_unit="request",
            charge_quantity=1,
        )
    assert exc.value.balance == 0.01
    assert exc.value.required == 0.05


async def test_client_unreachable_raises_credits_error():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = ClusterCreditsClient("http://cluster:9000", "t")
    client._build_http_client = lambda: httpx.AsyncClient(  # type: ignore[method-assign]
        base_url=client.base_url, transport=httpx.MockTransport(refuse)
    )

    with pytest.raises(ClusterCreditsError, match="unavailable"):
        await client.get_balance("u@t.co")


async def test_client_refund_tolerates_unknown_transaction():
    server = _FakeCreditsServer(refund_status=404)
    await _make_client(server).refund(uuid4())  # must not raise


# ============== Charger ==============


class _FakeClient:
    def __init__(self, insufficient: bool = False, unreachable: bool = False):
        self.insufficient = insufficient
        self.unreachable = unreachable
        self.debits: list[dict[str, Any]] = []
        self.refunds: list[UUID] = []

    async def debit(self, **kwargs):
        if self.unreachable:
            raise ClusterCreditsError("cluster credits service unavailable")
        if self.insufficient:
            raise InsufficientCreditsError(balance=0.0, required=kwargs["amount"])
        self.debits.append(kwargs)
        return {"balance_after": 1.0}

    async def refund(self, transaction_id):
        self.refunds.append(transaction_id)

    async def get_balance(self, user_email):
        return 12.4


class _FakeBalanceService:
    def __init__(self, journal_fails: bool = False):
        self.journal_fails = journal_fails
        self.debit_records: list[dict[str, Any]] = []
        self.cancel_records: list[UUID] = []

    async def record_external_debit(self, **kwargs):
        if self.journal_fails:
            raise RuntimeError("db down")
        self.debit_records.append(kwargs)

    async def record_external_cancel(self, transaction_id):
        if self.journal_fails:
            raise RuntimeError("db down")
        self.cancel_records.append(transaction_id)


def _make_charger(client, balance_service) -> ClusterCreditsCharger:
    return ClusterCreditsCharger(
        client=client,
        balance_service=balance_service,
        wallet_id=WALLET,
        currency="USD",
        tenant_id=TENANT,
        endpoint_id=ENDPOINT,
        endpoint_slug="my-endpoint",
    )


async def test_reserve_debits_then_journals():
    client, journal = _FakeClient(), _FakeBalanceService()
    charger = _make_charger(client, journal)

    tx = await charger.reserve(
        user_email="u@t.co", amount=0.05, charge_unit="request", charge_quantity=1
    )

    assert client.debits[0]["transaction_id"] == tx
    assert client.debits[0]["endpoint"] == "my-endpoint"
    record = journal.debit_records[0]
    assert record["transaction_id"] == tx
    assert record["wallet_id"] == WALLET
    assert record["amount"] == 0.05


async def test_reserve_insufficient_maps_to_shortfall_no_journal():
    client, journal = _FakeClient(insufficient=True), _FakeBalanceService()

    with pytest.raises(BalanceShortfallError) as exc:
        await _make_charger(client, journal).reserve(
            user_email="u@t.co", amount=0.05, charge_unit="request", charge_quantity=1
        )
    assert exc.value.currency == "USD"
    assert journal.debit_records == []


async def test_reserve_fails_closed_when_cluster_unreachable():
    client, journal = _FakeClient(unreachable=True), _FakeBalanceService()

    with pytest.raises(ClusterCreditsError):
        await _make_charger(client, journal).reserve(
            user_email="u@t.co", amount=0.05, charge_unit="request", charge_quantity=1
        )
    assert journal.debit_records == []


async def test_journal_failure_does_not_fail_the_query():
    client = _FakeClient()
    charger = _make_charger(client, _FakeBalanceService(journal_fails=True))

    tx = await charger.reserve(  # must not raise
        user_email="u@t.co", amount=0.05, charge_unit="request", charge_quantity=1
    )
    assert client.debits[0]["transaction_id"] == tx


async def test_cancel_refunds_then_journals():
    client, journal = _FakeClient(), _FakeBalanceService()
    tx = uuid4()

    await _make_charger(client, journal).cancel(tx)

    assert client.refunds == [tx]
    assert journal.cancel_records == [tx]


# ============== Seed-on-boot ==============


class _FakeWalletRepo:
    def __init__(self, existing=None):
        self.existing = existing
        self.created: list[dict[str, Any]] = []
        self.updated: list[tuple[UUID, dict]] = []

    async def get_by_type_and_currency(self, wallet_type, currency, tenant_id):
        return self.existing

    async def create_wallet(self, **kwargs):
        self.created.append(kwargs)

        class _W:
            id = uuid4()

        return _W()

    async def update_configuration(self, wallet_id, tenant_id, configuration):
        self.updated.append((wallet_id, configuration))

    async def get_all(self, tenant_id):
        return [self.existing] if self.existing else []


async def test_seed_noop_without_env():
    repo = _FakeWalletRepo()
    await seed_cluster_wallet(repo, TENANT)
    assert repo.created == []


async def test_seed_creates_wallet_from_env(monkeypatch):
    monkeypatch.setattr(app_settings.cluster, "credits_url", "http://cluster:9000")
    monkeypatch.setattr(app_settings.cluster, "credits_token", "tok-1")
    repo = _FakeWalletRepo()

    await seed_cluster_wallet(repo, TENANT)

    created = repo.created[0]
    assert created["wallet_type"] == "cluster"
    assert created["currency"] == "USD"
    assert created["configuration"]["service_token"] == "tok-1"


async def test_seed_upserts_rotated_token(monkeypatch):
    monkeypatch.setattr(app_settings.cluster, "credits_url", "http://cluster:9000")
    monkeypatch.setattr(app_settings.cluster, "credits_token", "tok-2")

    class _Existing:
        id = uuid4()
        configuration = {
            "credits_url": "http://cluster:9000",
            "service_token": "tok-1",
            "currency": "USD",
        }

    repo = _FakeWalletRepo(existing=_Existing())
    await seed_cluster_wallet(repo, TENANT)

    assert repo.created == []
    assert repo.updated[0][1]["service_token"] == "tok-2"


async def test_seed_noop_when_config_unchanged(monkeypatch):
    monkeypatch.setattr(app_settings.cluster, "credits_url", "http://cluster:9000")
    monkeypatch.setattr(app_settings.cluster, "credits_token", "tok-1")

    class _Existing:
        id = uuid4()
        configuration = {
            "credits_url": "http://cluster:9000",
            "service_token": "tok-1",
            "currency": "USD",
        }

    repo = _FakeWalletRepo(existing=_Existing())
    await seed_cluster_wallet(repo, TENANT)

    assert repo.created == [] and repo.updated == []


def test_seed_module_reads_settings_lazily():
    # Guard against import-time env capture: the module must consult
    # app_settings at call time (monkeypatched settings must be honored).
    assert seed_module.app_settings is app_settings


def test_display_managed_by_from_env(monkeypatch):
    from syft_space.components.wallets.cluster.provider import ClusterWalletProvider
    from syft_space.config import ClusterSettings

    provider = ClusterWalletProvider()
    monkeypatch.setattr(app_settings.cluster, "managed_by", "Acme Research Station")
    assert provider.extract_display({}, uuid4()) == {
        "managed_by": "Acme Research Station"
    }

    assert ClusterSettings.model_fields["managed_by"].default == "Syft Space Host"


async def test_seed_adopts_injected_wallet_id(monkeypatch):
    """The station's wallet id is used verbatim as the cluster wallet's id."""
    station_wallet_id = uuid4()
    monkeypatch.setattr(app_settings.cluster, "credits_url", "http://cluster:9000")
    monkeypatch.setattr(app_settings.cluster, "credits_token", "tok-1")
    monkeypatch.setattr(app_settings.cluster, "credits_wallet_id", station_wallet_id)
    repo = _FakeWalletRepo()

    await seed_cluster_wallet(repo, TENANT)

    assert repo.created[0]["wallet_id"] == station_wallet_id


def _cluster_config(currency: str = "PHP") -> dict[str, Any]:
    return ClusterWalletConfig(
        credits_url="http://cluster:9000",
        service_token="sct_x",
        currency=currency,
    ).model_dump()


def test_cluster_payment_info_points_at_station(monkeypatch):
    from syft_space.components.wallets.cluster.provider import ClusterWalletProvider

    monkeypatch.setattr(
        app_settings.cluster, "public_url", "https://station.example.com"
    )
    wallet_id = uuid4()
    info = ClusterWalletProvider().payment_info(_cluster_config("PHP"), wallet_id)

    # Bundles come from the per-currency catalog...
    assert {"name": "Starter", "amount": 100} in info.bundles
    # ...and every URL targets the station, scoped to this wallet id, with
    # the same suffixes as the self-hosted gateway routes.
    base = f"https://station.example.com/api/v1/credits/{wallet_id}"
    assert info.payment_url == f"{base}/invoices"
    assert info.invoices_url == f"{base}/invoices/me"
    assert info.credits_url == f"{base}/balance"
    # ...and it's flagged managed with the station's URL for the marketplace.
    assert info.managed is True
    assert info.station_url == "https://station.example.com"


def test_cluster_payment_info_without_public_url(monkeypatch):
    from syft_space.components.wallets.cluster.provider import ClusterWalletProvider

    monkeypatch.setattr(app_settings.cluster, "public_url", None)
    info = ClusterWalletProvider().payment_info(_cluster_config("PHP"), uuid4())

    # Bundles still ship so a marketplace can render them; URLs are withheld.
    assert info.bundles
    assert info.payment_url is None
    assert info.invoices_url is None
    assert info.credits_url is None
    # Still recognizably managed, just without a link.
    assert info.managed is True
    assert info.station_url is None


# ============== Exclusivity guards ==============


class _GuardRepo:
    """Repo stub: one cluster wallet present."""

    def __init__(self, wallets):
        self.wallets = wallets

    async def get_all(self, tenant_id):
        return self.wallets

    async def get_by_id(self, wallet_id, tenant_id):
        return next((w for w in self.wallets if w.id == wallet_id), None)


class _StubWallet:
    def __init__(self, wallet_type):
        self.id = uuid4()
        self.wallet_type = wallet_type


class _StubTenant:
    id = TENANT


@pytest.fixture
def handler_with_cluster_wallet():
    from syft_space.components.wallets.handlers import WalletHandler

    handler = WalletHandler.__new__(WalletHandler)
    handler.repository = _GuardRepo([_StubWallet("cluster")])
    handler.providers = {}
    handler.deletion_check = None
    return handler


async def test_create_blocked_while_managed_wallet_exists(
    handler_with_cluster_wallet,
):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await handler_with_cluster_wallet.create_wallet(
            "xendit", {"api_key": "x"}, _StubTenant()
        )
    assert exc.value.status_code == 403


async def test_cluster_type_never_creatable(handler_with_cluster_wallet):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await handler_with_cluster_wallet.create_wallet("cluster", {}, _StubTenant())
    assert exc.value.status_code == 403


async def test_managed_wallet_not_deletable(handler_with_cluster_wallet):
    from fastapi import HTTPException

    wallet_id = handler_with_cluster_wallet.repository.wallets[0].id
    with pytest.raises(HTTPException) as exc:
        await handler_with_cluster_wallet.delete_wallet(wallet_id, _StubTenant())
    assert exc.value.status_code == 403
