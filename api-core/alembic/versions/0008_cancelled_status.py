"""add explicit cancelled campaign and message statuses"""

from __future__ import annotations

from alembic import op

revision = "0008_cancelled_status"
down_revision = "0007_queue_forced_branch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE campaign_status ADD VALUE IF NOT EXISTS 'cancelled'")
        op.execute("ALTER TYPE queue_status ADD VALUE IF NOT EXISTS 'cancelled'")
        op.execute("ALTER TYPE recipient_status ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may use them.
    # Leaving the values in place keeps a rollback non-destructive.
    pass
