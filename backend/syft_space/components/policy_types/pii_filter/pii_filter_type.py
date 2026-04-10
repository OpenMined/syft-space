"""PII filter policy type implementation.

Redacts common personally identifiable information (PII) from endpoint
responses using regular expressions. Runs in the ``post_hook`` phase and
mutates ``PolicyContext.response`` in place while preserving the JSON
structure — only string leaves are touched.
"""

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from syft_space.components.policy_types.interfaces import (
    BasePolicyType,
    PolicyContext,
)
from syft_space.components.shared.utils import ConfigSchemaGenerator

#: Categories of PII that this policy knows how to redact.
SUPPORTED_CATEGORIES: tuple[str, ...] = (
    "email",
    "phone",
    "ssn",
    "credit_card",
)

#: Default replacement token if none is supplied in the config.
DEFAULT_REPLACEMENT = "[REDACTED]"


# Pattern order matters: more specific patterns (SSN) run before broader
# ones (credit card) so they are not swallowed by overlapping matches.
_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(
        # International (+country code) or North American formats. Requires
        # at least one separator to avoid matching arbitrary 10-digit runs
        # that would better be classified as credit cards.
        r"(?:\+\d{1,3}[\s.-]?)?\(\d{3}\)[\s.-]?\d{3}[\s.-]?\d{4}"
        r"|(?:\+\d{1,3}[\s.-]?)?\d{3}[\s.-]\d{3}[\s.-]\d{4}"
    ),
    # 13–19 digit runs, optionally separated by single spaces or dashes.
    "credit_card": re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
}


def _passes_luhn(digits: str) -> bool:
    """Return True if a bare digit string passes the Luhn checksum."""
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class PiiFilterConfig(BaseModel):
    """Configuration schema for PII filter policy."""

    categories: list[str] = Field(
        default_factory=lambda: list(SUPPORTED_CATEGORIES),
        description=(
            "Categories of PII to redact. Supported values: "
            f"{', '.join(SUPPORTED_CATEGORIES)}."
        ),
    )
    replacement: str = Field(
        default=DEFAULT_REPLACEMENT,
        description="Token used to replace detected PII.",
    )

    @field_validator("categories")
    @classmethod
    def _validate_categories(cls, value: list[str]) -> list[str]:
        """Reject unknown categories and de-duplicate the list."""
        unknown = [c for c in value if c not in SUPPORTED_CATEGORIES]
        if unknown:
            raise ValueError(
                "Unknown PII categories: "
                f"{', '.join(unknown)}. "
                f"Supported: {', '.join(SUPPORTED_CATEGORIES)}."
            )
        # Preserve order while removing duplicates.
        seen: set[str] = set()
        deduped: list[str] = []
        for cat in value:
            if cat not in seen:
                seen.add(cat)
                deduped.append(cat)
        return deduped


class PiiFilterType(BasePolicyType):
    """Policy that redacts PII from endpoint responses.

    Aggregation: UNION — every configured policy contributes its own
    category set; the effective redaction set is the union across all
    attached ``pii_filter`` policies. This means adding another policy
    can only *add* redaction, never weaken it.

    The policy is stateless and only mutates ``context.response``.
    """

    NAME = "pii_filter"

    def __init__(self) -> None:
        """Policy is stateless — no per-instance setup required."""
        return None

    @classmethod
    def name(cls) -> str:
        """Return the policy type name."""
        return cls.NAME

    @classmethod
    def description(cls) -> str:
        """Return a human description of the policy type."""
        return (
            "Redact common personally identifiable information (email, phone, "
            "SSN, credit card) from endpoint responses before returning them "
            "to the caller."
        )

    @classmethod
    def icon(cls) -> str:
        """Return the display icon for the policy type."""
        return "🛡️"

    @classmethod
    def configuration_schema(cls) -> dict[str, Any]:
        """Return the JSON schema describing this policy's configuration."""
        return PiiFilterConfig.model_json_schema(schema_generator=ConfigSchemaGenerator)

    async def pre_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """No pre-request work — PII redaction only runs on responses."""
        return context

    async def post_hook(
        self, configs: list[dict[str, Any]], context: PolicyContext
    ) -> PolicyContext:
        """Redact configured PII categories from ``context.response``."""
        if not configs or context.response is None:
            return context

        validated = [PiiFilterConfig(**c) for c in configs]

        # Union the categories across all policies; use the first non-default
        # replacement token if any is supplied, otherwise the default.
        category_set: set[str] = set()
        replacement = DEFAULT_REPLACEMENT
        for cfg in validated:
            category_set.update(cfg.categories)
            if cfg.replacement and cfg.replacement != DEFAULT_REPLACEMENT:
                replacement = cfg.replacement

        if not category_set:
            return context

        patterns = [
            (cat, _CATEGORY_PATTERNS[cat])
            for cat in SUPPORTED_CATEGORIES
            if cat in category_set
        ]

        context.response = self._redact(context.response, patterns, replacement)
        return context

    @classmethod
    def enabled(cls) -> bool:
        """PII filter is always available."""
        return True

    @classmethod
    async def validate_config(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalise a configuration dictionary."""
        try:
            validated = PiiFilterConfig(**config)
            return validated.model_dump()
        except Exception as e:
            raise ValueError(f"Invalid pii_filter policy config: {e}") from e

    def _redact(
        self,
        value: Any,
        patterns: list[tuple[str, re.Pattern[str]]],
        replacement: str,
    ) -> Any:
        """Recursively redact PII from ``value`` preserving JSON structure."""
        if isinstance(value, dict):
            return {k: self._redact(v, patterns, replacement) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(item, patterns, replacement) for item in value]
        if isinstance(value, str):
            return self._redact_string(value, patterns, replacement)
        return value

    def _redact_string(
        self,
        text: str,
        patterns: list[tuple[str, re.Pattern[str]]],
        replacement: str,
    ) -> str:
        """Apply each configured category pattern to a single string leaf."""
        for category, pattern in patterns:
            if category == "credit_card":
                text = pattern.sub(
                    lambda m: self._redact_credit_card(m.group(0), replacement),
                    text,
                )
            else:
                text = pattern.sub(replacement, text)
        return text

    @staticmethod
    def _redact_credit_card(match_text: str, replacement: str) -> str:
        """Only redact credit-card-shaped digits that pass the Luhn check."""
        digits = re.sub(r"[ -]", "", match_text)
        if _passes_luhn(digits):
            return replacement
        return match_text
