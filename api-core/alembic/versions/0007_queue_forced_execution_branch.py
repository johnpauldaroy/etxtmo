"""add superadmin-forced execution branch override for message queue"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_queue_forced_branch"
down_revision = "0006_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    queue_columns = {column["name"] for column in inspector.get_columns("message_queue")}
    with op.batch_alter_table("message_queue") as batch:
        if "forced_execution_branch_id" not in queue_columns:
            batch.add_column(sa.Column("forced_execution_branch_id", sa.Uuid(), nullable=True))
            batch.create_foreign_key(
                "fk_queue_forced_execution_branch",
                "branches",
                ["forced_execution_branch_id"],
                ["id"],
            )
    op.create_index(
        "ix_message_queue_forced_branch_pick",
        "message_queue",
        ["forced_execution_branch_id", "status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_queue_forced_branch_pick", table_name="message_queue")
    with op.batch_alter_table("message_queue") as batch:
        batch.drop_constraint("fk_queue_forced_execution_branch", type_="foreignkey")
        batch.drop_column("forced_execution_branch_id")
