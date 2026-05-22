"""CapabilityChecker — verifies a policy's declared capabilities are
satisfied by the surrounding system before attaching it to an endpoint.

Reads `cls.capabilities()` and enforces a fixed set of checks driven by
the declaration. The checker knows about each kind of requirement, never
about each kind of policy — adding a new policy type that reuses existing
requirement kinds needs no changes here.

To add a new requirement kind:
  1. extend `Capabilities` with a new field
  2. teach this checker to enforce it
  3. policy classes declare it via `capabilities()`

`PolicyHandler` calls `check()` and converts any raised `PolicyAttach*Error`
into the appropriate `HTTPException`. The checker itself has no HTTP
knowledge.
"""

from syft_space.components.policies.interfaces import (
    EndpointLookup,
    EndpointPolicyQuery,
    WalletLookup,
)
from syft_space.components.policies.schemas import CreatePolicyRequest
from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
    PolicyAttachConflictError,
    PolicyAttachInputError,
    PolicyAttachNotFoundError,
)
from syft_space.components.tenants.entities import Tenant


class CapabilityChecker:
    """Verify a policy's declared capabilities against current system state."""

    def __init__(
        self,
        wallet_lookup: WalletLookup,
        endpoint_lookup: EndpointLookup,
        endpoint_policy_query: EndpointPolicyQuery,
    ) -> None:
        self._wallet_lookup = wallet_lookup
        self._endpoint_lookup = endpoint_lookup
        self._endpoint_policy_query = endpoint_policy_query

    async def check(
        self,
        policy_type_cls: type[BasePolicyType],
        request: CreatePolicyRequest,
        tenant: Tenant,
    ) -> None:
        """Raise PolicyAttach*Error if the policy cannot be attached.

        Returns None on success.
        """
        caps = policy_type_cls.capabilities()
        await self._check_wallet_rules(caps, policy_type_cls.NAME, request, tenant)
        await self._check_endpoint_rules(caps, request, tenant)

    async def _check_wallet_rules(
        self,
        caps: Capabilities,
        policy_name: str,
        request: CreatePolicyRequest,
        tenant: Tenant,
    ) -> None:
        if not caps.requires_wallet:
            if request.wallet_id is not None:
                raise PolicyAttachInputError(
                    f"wallet_id is not applicable for {policy_name} policies"
                )
            return

        if request.wallet_id is None:
            raise PolicyAttachInputError(
                f"wallet_id is required for {policy_name} policies. "
                "Please create a wallet first."
            )

        wallet = await self._wallet_lookup.get_by_id(request.wallet_id, tenant.id)
        if wallet is None:
            raise PolicyAttachNotFoundError("Wallet not found")

        if (
            caps.required_wallet_type
            and wallet.wallet_type != caps.required_wallet_type
        ):
            raise PolicyAttachConflictError(
                f"This policy requires a '{caps.required_wallet_type}' wallet, "
                f"got '{wallet.wallet_type}'."
            )

        if await self._endpoint_policy_query.has_different_wallet(
            request.endpoint_id, tenant.id, request.wallet_id
        ):
            raise PolicyAttachConflictError(
                "All payment policies on an endpoint must use the same wallet."
            )

    async def _check_endpoint_rules(
        self,
        caps: Capabilities,
        request: CreatePolicyRequest,
        tenant: Tenant,
    ) -> None:
        if not caps.requires_endpoint_dataset:
            return

        endpoint = await self._endpoint_lookup.get_by_id(request.endpoint_id, tenant.id)
        if endpoint is None:
            raise PolicyAttachNotFoundError("Endpoint not found")
        if endpoint.dataset_id is None:
            raise PolicyAttachConflictError(
                "This policy requires the endpoint to have a dataset attached "
                "(e.g., per-document pricing counts retrieved documents). "
                "Attach a per-request pricing policy instead, or add a dataset "
                "to the endpoint."
            )
