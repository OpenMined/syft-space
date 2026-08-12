"""requests table replaces space_requests

Splits the single-purpose ``space_requests`` model into typed ``requests``.
Every old row becomes a ``create_space`` request (its status mapped); a
``deleted`` row additionally gets a paired approved ``delete_space`` request
so the deletion survives as history and deleted-space earnings attribution
keeps working. The one-space rule gains a unique index on ``spaces.owner_email``.

Revision ID: 7aac9a29ff18
Revises: b13bbb37fe06
Create Date: 2026-08-12 12:00:00.000000
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "7aac9a29ff18"
down_revision: str | None = "b13bbb37fe06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# old create-status → new generic status
_STATUS_MAP = {
    "pending": "pending",
    "provisioning": "provisioning",
    "active": "approved",
    "failed": "failed",
    "rejected": "rejected",
    "withdrawn": "withdrawn",
    "deleted": "approved",  # the create succeeded; a delete request is synthesized
}
_TERMINAL = {"approved", "rejected", "withdrawn"}


def _new_id() -> str:
    return uuid.uuid4().hex


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "requests",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("owner_email", sa.String(), nullable=False),
        sa.Column("space_id", sa.CHAR(32), nullable=True),
        sa.Column("space_name", sa.String(), nullable=True),
        sa.Column("subdomain", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=False, server_default=""),
        sa.Column("resolution_note", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("origin", sa.String(), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_requests_type", "requests", ["type"])
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_owner_email", "requests", ["owner_email"])
    op.create_index("ix_requests_subdomain", "requests", ["subdomain"])

    old = conn.execute(
        sa.text(
            "SELECT id, space_name, subdomain, owner_email, reason, origin, "
            "status, reject_reason, space_id, created_at, updated_at "
            "FROM space_requests"
        )
    ).mappings()

    insert = sa.text(
        "INSERT INTO requests (id, type, status, owner_email, space_id, "
        "space_name, subdomain, reason, resolution_note, payload, origin, "
        "created_at, updated_at, resolved_at) VALUES (:id, :type, :status, "
        ":owner_email, :space_id, :space_name, :subdomain, :reason, "
        ":resolution_note, '{}', :origin, :created_at, :updated_at, :resolved_at)"
    )

    for r in old:
        new_status = _STATUS_MAP.get(r["status"], r["status"])
        resolved = r["updated_at"] if new_status in _TERMINAL else None
        conn.execute(
            insert,
            {
                "id": r["id"],
                "type": "create_space",
                "status": new_status,
                "owner_email": r["owner_email"],
                "space_id": r["space_id"],
                "space_name": r["space_name"],
                "subdomain": r["subdomain"],
                "reason": r["reason"] or "",
                "resolution_note": r["reject_reason"],
                "origin": r["origin"] or "member",
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "resolved_at": resolved,
            },
        )
        # A deleted space: synthesize the approved delete_space request that
        # the new model would have produced, so history + earnings survive.
        if r["status"] == "deleted":
            conn.execute(
                insert,
                {
                    "id": _new_id(),
                    "type": "delete_space",
                    "status": "approved",
                    "owner_email": r["owner_email"],
                    "space_id": r["space_id"],
                    "space_name": r["space_name"],
                    "subdomain": r["subdomain"],
                    "reason": "",
                    "resolution_note": None,
                    "origin": "admin",
                    "created_at": r["updated_at"],
                    "updated_at": r["updated_at"],
                    "resolved_at": r["updated_at"],
                },
            )

    # One live space per owner — the backstop the create-slot guard relies on.
    op.create_index("uq_space_owner", "spaces", ["owner_email"], unique=True)

    op.drop_table("space_requests")


def downgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(UTC).isoformat()

    op.create_table(
        "space_requests",
        sa.Column("id", sa.CHAR(32), primary_key=True),
        sa.Column("space_name", sa.String(), nullable=False),
        sa.Column("subdomain", sa.String(), nullable=False),
        sa.Column("owner_email", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False, server_default=""),
        sa.Column("origin", sa.String(), nullable=False, server_default="member"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("reject_reason", sa.String(), nullable=True),
        sa.Column("space_id", sa.CHAR(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_space_requests_owner_email", "space_requests", ["owner_email"])
    op.create_index("ix_space_requests_subdomain", "space_requests", ["subdomain"])
    op.create_index("ix_space_requests_status", "space_requests", ["status"])

    # Spaces with an approved delete_space request map back to a 'deleted' row.
    deleted_ids = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT space_id FROM requests WHERE type = 'delete_space' "
                "AND status = 'approved' AND space_id IS NOT NULL"
            )
        )
    }
    reverse = {
        "approved": "active",
        "pending": "pending",
        "provisioning": "provisioning",
        "failed": "failed",
        "rejected": "rejected",
        "withdrawn": "withdrawn",
    }
    creates = conn.execute(
        sa.text(
            "SELECT id, space_name, subdomain, owner_email, reason, origin, "
            "status, resolution_note, space_id, created_at, updated_at "
            "FROM requests WHERE type = 'create_space'"
        )
    ).mappings()
    for r in creates:
        status_ = (
            "deleted"
            if r["space_id"] in deleted_ids
            else reverse.get(r["status"], r["status"])
        )
        conn.execute(
            sa.text(
                "INSERT INTO space_requests (id, space_name, subdomain, "
                "owner_email, reason, origin, status, reject_reason, space_id, "
                "created_at, updated_at) VALUES (:id, :space_name, :subdomain, "
                ":owner_email, :reason, :origin, :status, :reject_reason, "
                ":space_id, :created_at, :updated_at)"
            ),
            {
                "id": r["id"],
                "space_name": r["space_name"] or "",
                "subdomain": r["subdomain"] or "",
                "owner_email": r["owner_email"],
                "reason": r["reason"] or "",
                "origin": r["origin"] or "member",
                "status": status_,
                "reject_reason": r["resolution_note"],
                "space_id": r["space_id"],
                "created_at": r["created_at"] or now,
                "updated_at": r["updated_at"] or now,
            },
        )

    op.drop_index("uq_space_owner", table_name="spaces")
    op.drop_table("requests")
