"""MPP charging adapter — concrete impl of policy_types.MppCharger.

Bound at request time to a specific MPP wallet config (recipient address,
HMAC secret, realm) and the inbound X-Payment header. Hides Mpp.server
construction and the Tempo/PATH_USD wiring from the policy layer.
"""

from typing import ClassVar

from mpp import Challenge, Credential, Receipt
from mpp.methods.tempo import PATH_USD, TESTNET_CHAIN_ID, ChargeIntent, tempo
from mpp.server import Mpp

from syft_space.config import app_settings


class MppChargingAdapter:
    """Per-request charger for one MPP wallet.

    The underlying Mpp.server.Mpp instance is cached per (wallet_address,
    realm) because HMAC challenge verification must use a consistent realm
    across the 402 → pay → verify roundtrip. The cache lives at class level
    so it survives across requests.
    """

    _mpp_instances: ClassVar[dict[str, Mpp]] = {}

    def __init__(
        self,
        *,
        wallet_address: str,
        secret_key: str,
        realm: str,
        x_payment: str | None,
    ) -> None:
        self._wallet_address = wallet_address
        self._secret_key = secret_key
        self._realm = realm
        self._x_payment = x_payment

    def _get_or_build_mpp(self) -> Mpp:
        cache_key = f"{self._wallet_address}:{self._realm}"
        if cache_key not in MppChargingAdapter._mpp_instances:
            chain_id = TESTNET_CHAIN_ID if app_settings.tempo_testnet else None
            method = tempo(
                currency=PATH_USD,
                recipient=self._wallet_address,
                chain_id=chain_id,
                intents={"charge": ChargeIntent(chain_id=chain_id)},
            )
            MppChargingAdapter._mpp_instances[cache_key] = Mpp.create(
                method=method,
                secret_key=self._secret_key,
                realm=self._realm,
            )
        return MppChargingAdapter._mpp_instances[cache_key]

    async def charge(
        self, *, amount: float, description: str
    ) -> Challenge | tuple[Credential, Receipt]:
        """Attempt to charge `amount` using the bound X-Payment credential.

        If no credential is bound (or it doesn't cover the amount), the
        underlying mpp.charge returns a Challenge — the policy converts that
        into a PaymentRequiredError. Otherwise returns (credential, receipt).
        """
        mpp = self._get_or_build_mpp()
        return await mpp.charge(
            authorization=self._x_payment,
            amount=str(amount),
            description=description,
        )
