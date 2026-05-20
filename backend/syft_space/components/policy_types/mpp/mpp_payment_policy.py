"""Base class for MPP payment policies.

Subclasses bind a specific config class (which carries `unit_type` as a
typed Literal field) and provide pre/post-hook bodies. Everything else —
config validation, schema export, tier matching, identity boilerplate —
lives here.

Adding a new unit type is one new config + one new policy subclass:

    # In mpp/policy_config.py
    class MppPerTokenConfig(MppPaymentConfig):
        unit_type: Literal["token"] = "token"

    # In mpp/mpp_per_token.py
    class MppPerTokenPolicy(MppPaymentPolicy):
        NAME = "mpp_per_token"
        DESCRIPTION = "Charge per generated token via MPP on Tempo blockchain"
        CONFIG_CLS = MppPerTokenConfig

        @classmethod
        def capabilities(cls):
            return Capabilities(
                requires_wallet=True,
                required_wallet_type="mpp",
                # No requires_endpoint_dataset — tokens come from model output
            )

        async def pre_hook(self, configs, context): ...
        async def post_hook(self, configs, context): ...

Register it in policy_types/__init__.py:register_builtin_types. SyftHub
sees `type: "mpp"` + `config.unit_type: "token"` automatically — no
publish-side changes needed.
"""

from typing import Any, ClassVar

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    Capabilities,
)
from syft_space.components.policy_types.mpp.policy_config import MppPaymentConfig
from syft_space.components.shared.utils import matches_any_pattern


class MppPaymentPolicy(BasePolicyType):
    """Shared scaffolding for all MPP-based payment policies."""

    NAME: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    CONFIG_CLS: ClassVar[type[MppPaymentConfig]]

    def __init__(self) -> None:
        pass

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        return cls.DESCRIPTION

    @classmethod
    def icon(cls) -> str:
        return "💳"

    @classmethod
    def enabled(cls) -> bool:
        return True

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        return cls.CONFIG_CLS.model_json_schema()

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(requires_wallet=True, required_wallet_type="mpp")

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the user-supplied config.

        `unit_type` is a typed Literal field on the subclass's CONFIG_CLS,
        so it flows through `model_dump()` naturally. No injection here.
        """
        validated = cls.CONFIG_CLS(**config)
        return validated.model_dump()

    def _find_matching_price(
        self, sender_email: str, configs: list[dict[str, Any]]
    ) -> float | None:
        """Find the most specific matching price for a user.

        More specific patterns (longer, non-wildcard) take priority.
        Returns None if no config matches.
        """
        best_price: float | None = None
        best_specificity = -1

        for config in configs:
            validated = self.CONFIG_CLS(**config)
            for pattern in validated.applied_to:
                if not matches_any_pattern(sender_email, [pattern]):
                    continue
                specificity = 0 if pattern == "*" else len(pattern.replace("*", ""))
                if specificity > best_specificity:
                    best_specificity = specificity
                    best_price = validated.price

        return best_price
