"""Extract wallets into standalone table.

- Create wallets table
- Add wallet_id FK to policies (for payment policies)
- Migrate MPP data: marketplace wallet fields + settings mpp_secret_key → wallets table
- Link existing mpp_accounting policies to migrated wallet
- Drop wallet_address, wallet_private_key from marketplaces
- Drop mpp_secret_key from settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-30

"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create wallets table
    op.create_table(
        "wallets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("wallet_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # 2. Add wallet_id FK to policies (batch mode for SQLite compatibility)
    with op.batch_alter_table("policies") as batch_op:
        batch_op.add_column(
            sa.Column("wallet_id", sa.String(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_policy_wallet_id",
            "wallets",
            ["wallet_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 3. Data migration: marketplace wallet → wallets table, link mpp_accounting policies
    conn = op.get_bind()

    # Find marketplaces with wallet_address set
    marketplaces = conn.execute(
        sa.text(
            "SELECT id, tenant_id, wallet_address, wallet_private_key "
            "FROM marketplaces WHERE wallet_address IS NOT NULL"
        )
    ).fetchall()

    for mp in marketplaces:
        mp_id, tenant_id, wallet_address, wallet_private_key = mp

        # Get mpp_secret_key from settings (or generate one)
        settings_row = conn.execute(
            sa.text("SELECT mpp_secret_key FROM settings LIMIT 1")
        ).fetchone()
        mpp_secret_key = (
            settings_row[0] if settings_row and settings_row[0] else None
        ) or secrets.token_hex(32)

        # Generate wallet ID
        import uuid

        wallet_id = str(uuid.uuid4())

        # Insert wallet row
        import json
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        configuration = json.dumps(
            {
                "wallet_address": wallet_address,
                "wallet_private_key": wallet_private_key or "",
                "mpp_secret_key": mpp_secret_key,
            }
        )

        conn.execute(
            sa.text(
                "INSERT INTO wallets (id, tenant_id, wallet_type, name, configuration, is_active, created_at, updated_at) "
                "VALUES (:id, :tenant_id, :wallet_type, :name, :configuration, :is_active, :created_at, :updated_at)"
            ),
            {
                "id": wallet_id,
                "tenant_id": tenant_id,
                "wallet_type": "mpp",
                "name": "MPP Wallet",
                "configuration": configuration,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        )

        # Link existing mpp_accounting policies for this tenant to the new wallet
        conn.execute(
            sa.text(
                "UPDATE policies SET wallet_id = :wallet_id "
                "WHERE tenant_id = :tenant_id AND policy_type = 'mpp_accounting'"
            ),
            {"wallet_id": wallet_id, "tenant_id": tenant_id},
        )

    # 4. Drop old wallet fields from marketplaces
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.drop_column("wallet_address")
        batch_op.drop_column("wallet_private_key")

    # 5. Drop mpp_secret_key from settings
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("mpp_secret_key")


def downgrade() -> None:
    # Re-add mpp_secret_key to settings
    op.add_column(
        "settings",
        sa.Column("mpp_secret_key", sa.String(), nullable=True),
    )

    # Re-add wallet fields to marketplaces
    op.add_column(
        "marketplaces",
        sa.Column("wallet_address", sa.String(), nullable=True),
    )
    op.add_column(
        "marketplaces",
        sa.Column("wallet_private_key", sa.String(), nullable=True),
    )

    # Reverse data migration: copy credentials back from wallets to marketplaces
    conn = op.get_bind()
    wallets = conn.execute(
        sa.text(
            "SELECT tenant_id, configuration FROM wallets WHERE wallet_type = 'mpp'"
        )
    ).fetchall()

    import json

    for wallet_row in wallets:
        tenant_id, config_json = wallet_row
        config = (
            json.loads(config_json) if isinstance(config_json, str) else config_json
        )
        wallet_address = config.get("wallet_address")
        wallet_private_key = config.get("wallet_private_key")
        mpp_secret_key = config.get("mpp_secret_key")

        # Update marketplace
        conn.execute(
            sa.text(
                "UPDATE marketplaces SET wallet_address = :wa, wallet_private_key = :wpk "
                "WHERE tenant_id = :tid AND is_default = 1"
            ),
            {"wa": wallet_address, "wpk": wallet_private_key, "tid": tenant_id},
        )

        # Update settings
        if mpp_secret_key:
            conn.execute(
                sa.text("UPDATE settings SET mpp_secret_key = :key"),
                {"key": mpp_secret_key},
            )

    # Drop wallet_id from policies
    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_column("wallet_id")

    # Drop wallets table
    op.drop_table("wallets")
