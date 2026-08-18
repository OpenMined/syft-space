"""rename payment policy_type values to per-request

Revision ID: 7a3c1b9e2f04
Revises: cd1cf206c880
Create Date: 2026-05-14 00:00:00.000000

Renames Policy.policy_type values to align with the per-request /
per-document naming convention introduced for the per-document policy work:

- 'mpp_accounting' -> 'mpp_per_request'
- 'xendit'         -> 'xendit_per_request'

SyftHub publish payload is unaffected: publish_handler overrides
policy_data['type'] with wallet.wallet_type ('mpp' / 'xendit') for any
policy with a wallet, which is the case for all payment policies.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a3c1b9e2f04"
down_revision: str | None = "cd1cf206c880"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE policies SET policy_type = 'mpp_per_request' "
        "WHERE policy_type = 'mpp_accounting'"
    )
    op.execute(
        "UPDATE policies SET policy_type = 'xendit_per_request' "
        "WHERE policy_type = 'xendit'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE policies SET policy_type = 'mpp_accounting' "
        "WHERE policy_type = 'mpp_per_request'"
    )
    op.execute(
        "UPDATE policies SET policy_type = 'xendit' "
        "WHERE policy_type = 'xendit_per_request'"
    )
